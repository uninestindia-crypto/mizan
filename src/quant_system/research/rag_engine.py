"""QuantPaperRAG: High-performance semantic retrieval engine for quantitative finance research."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from quant_system.research.arxiv_client import ArxivClient, PaperMetadata
from quant_system.research.embedding_gemma import EmbeddingGemmaProvider


@dataclass(frozen=True, slots=True)
class RAGResult:
    """Structured response from the QuantPaperRAG semantic engine."""

    query: str
    top_papers: list[tuple[PaperMetadata, float]]  # (paper, similarity_score)
    synthesized_context: str
    citations: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class QuantPaperRAG:
    """Retrieval-Augmented Generation engine for quantitative trading algorithms."""

    STOPWORDS = {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "paper",
        "show",
        "using",
    }

    def __init__(
        self,
        arxiv_client: ArxivClient | None = None,
        embedding_provider: EmbeddingGemmaProvider | None = None,
        use_embeddings: bool = True,
        dense_weight: float = 0.65,
    ) -> None:
        self.arxiv_client = arxiv_client or ArxivClient()
        self.embedding_provider = (
            embedding_provider
            if embedding_provider is not None
            else (EmbeddingGemmaProvider() if use_embeddings else None)
        )
        self.dense_weight = max(0.0, min(1.0, dense_weight))
        self.papers: list[PaperMetadata] = []
        self.dense_vectors: list[list[float]] = []
        # Which backend generation made dense_vectors; vectors from two backends must never be compared.
        self._dense_generation = (
            self.embedding_provider.generation if self.embedding_provider is not None else 0
        )
        self.doc_vectors: list[dict[str, float]] = []
        self.doc_lengths: list[float] = []
        self.idf: dict[str, float] = {}
        # Pre-seed with curated institutional research library
        self.index_papers(self.arxiv_client.get_curated_institutional_library())

    @classmethod
    def tokenize(cls, text: str) -> list[str]:
        """Cleans, normalizes, and tokenizes input text."""
        words = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())
        return [w for w in words if w not in cls.STOPWORDS]

    def index_papers(self, papers: Sequence[PaperMetadata]) -> None:
        """Indexes paper titles, abstracts, and categories into dense & sparse vector spaces."""
        new_papers: list[PaperMetadata] = []
        for p in papers:
            if not any(existing.arxiv_id == p.arxiv_id for existing in self.papers):
                self.papers.append(p)
                new_papers.append(p)

        n_docs = len(self.papers)
        if n_docs == 0:
            return

        # 1. Update dense embeddings if provider is active
        if self.embedding_provider is not None and new_papers:
            provider = self.embedding_provider
            new_dense = provider.embed_texts([self._paper_text(p) for p in new_papers])
            self.dense_vectors.extend(new_dense)
            if provider.generation != self._dense_generation:
                self._rebuild_dense()

        # 2. Compute Document Frequencies
        df_counts: Counter[str] = Counter()
        tokenized_docs: list[list[str]] = []

        for p in self.papers:
            # Title tokens get 3x weight
            title_tokens = self.tokenize(p.title) * 3
            summary_tokens = self.tokenize(p.summary)
            cat_tokens = self.tokenize(p.primary_category) * 2
            doc_tokens = title_tokens + summary_tokens + cat_tokens
            tokenized_docs.append(doc_tokens)
            df_counts.update(set(doc_tokens))

        # 3. Compute IDF: log((N + 1) / (DF + 1)) + 1
        self.idf = {
            term: math.log((n_docs + 1.0) / (count + 1.0)) + 1.0
            for term, count in df_counts.items()
        }

        # 4. Compute normalized TF-IDF vectors
        self.doc_vectors = []
        self.doc_lengths = []

        for tokens in tokenized_docs:
            tf = Counter(tokens)
            vec: dict[str, float] = {}
            for term, count in tf.items():
                tfidf = (1.0 + math.log(count)) * self.idf.get(term, 1.0)
                vec[term] = tfidf

            norm = math.sqrt(sum(v * v for v in vec.values()))
            self.doc_vectors.append(vec)
            self.doc_lengths.append(norm if norm > 0 else 1.0)

    @staticmethod
    def _paper_text(paper: PaperMetadata) -> str:
        return f"{paper.title}. {paper.summary} Category: {paper.primary_category}"

    def _rebuild_dense(self) -> None:
        """Embeds every paper again with the backend that is active now (it changed after the first vectors)."""
        provider = self.embedding_provider
        if provider is None:
            return
        self.dense_vectors = provider.embed_texts([self._paper_text(p) for p in self.papers])
        self._dense_generation = provider.generation

    def search_and_index_arxiv(self, query: str, max_results: int = 5) -> int:
        """Queries arXiv live, parses results, and adds them to the semantic index."""
        fetched = self.arxiv_client.search_papers(query=query, max_results=max_results)
        initial_count = len(self.papers)
        self.index_papers(fetched)
        return len(self.papers) - initial_count

    def query(self, question: str, top_k: int = 3) -> RAGResult:
        """Performs dense / hybrid semantic similarity search over indexed quantitative research papers."""
        q_tokens = self.tokenize(question)
        if (not q_tokens and self.embedding_provider is None) or not self.papers:
            return RAGResult(
                query=question,
                top_papers=[],
                synthesized_context="No relevant research papers indexed.",
                citations=[],
            )

        # 1. Sparse TF-IDF Scores
        tfidf_scores: list[float] = [0.0] * len(self.papers)
        if q_tokens and self.doc_vectors:
            q_tf = Counter(q_tokens)
            q_vec: dict[str, float] = {}
            for term, count in q_tf.items():
                tfidf = (1.0 + math.log(count)) * self.idf.get(term, 1.0)
                q_vec[term] = tfidf

            q_norm = math.sqrt(sum(v * v for v in q_vec.values()))
            if q_norm == 0:
                q_norm = 1.0

            for idx, doc_vec in enumerate(self.doc_vectors):
                dot_product = sum(doc_vec.get(t, 0.0) * w for t, w in q_vec.items())
                sim = dot_product / (q_norm * self.doc_lengths[idx])
                tfidf_scores[idx] = max(0.0, sim)

        # 2. Dense EmbeddingGemma Scores
        dense_scores: list[float] = [0.0] * len(self.papers)
        retrieval_mode = "tfidf"
        if self.embedding_provider is not None and self.dense_vectors:
            q_dense = self.embedding_provider.embed_text(question, kind="query")
            if self.embedding_provider.generation != self._dense_generation:
                self._rebuild_dense()
                q_dense = self.embedding_provider.embed_text(question, kind="query")
            for idx, d_vec in enumerate(self.dense_vectors):
                # Normalized vectors: dot product equals cosine similarity
                dense_sim = sum(q_dense[k] * d_vec[k] for k in range(min(len(q_dense), len(d_vec))))
                dense_scores[idx] = max(0.0, dense_sim)
            retrieval_mode = (
                "embedding_gemma_hybrid"
                if any(s > 0 for s in tfidf_scores)
                else "embedding_gemma_dense"
            )

        # 3. Combine scores
        scores: list[tuple[int, float]] = []
        for idx in range(len(self.papers)):
            if self.embedding_provider is not None and self.dense_vectors:
                combined = (
                    self.dense_weight * dense_scores[idx]
                    + (1.0 - self.dense_weight) * tfidf_scores[idx]
                )
            else:
                combined = tfidf_scores[idx]
            scores.append((idx, combined))

        # Sort by similarity
        scores.sort(key=lambda x: x[1], reverse=True)
        top_indices = scores[:top_k]

        matched_papers: list[tuple[PaperMetadata, float]] = [
            (self.papers[i], round(score, 4)) for i, score in top_indices if score > 0.0
        ]

        if not matched_papers and top_indices:
            # Fallback to first available papers if scores are zero
            matched_papers = [(self.papers[i], round(score, 4)) for i, score in top_indices]

        # Synthesize context
        context_parts = []
        citations = []

        for paper, score in matched_papers:
            citations.append(paper.citation)
            context_parts.append(
                f"### [{paper.primary_category}] {paper.title} (Relevance: {score:.2f})\n"
                f"- **Citation**: {paper.citation}\n"
                f"- **Key Findings / Abstract**: {paper.summary}\n"
            )

        synthesized = "\n".join(context_parts)

        return RAGResult(
            query=question,
            top_papers=matched_papers,
            synthesized_context=synthesized,
            citations=citations,
            metadata={
                "retrieval_mode": retrieval_mode,
                "dense_weight": self.dense_weight if self.embedding_provider else 0.0,
                # What really produced the vectors, not just which model was asked for.
                "embedding_model": (
                    self.embedding_provider.served_model if self.embedding_provider else None
                ),
                "embedding_label": (
                    self.embedding_provider.label if self.embedding_provider else None
                ),
                "embedding_is_real_model": (
                    self.embedding_provider.uses_real_model if self.embedding_provider else False
                ),
                "embedding_dimension": (
                    self.embedding_provider.dimensions if self.embedding_provider else None
                ),
                "backend": (
                    self.embedding_provider.active_backend if self.embedding_provider else None
                ),
            },
        )

    def format_advisor_context(self, question: str, top_k: int = 2) -> str:
        """Formats concise academic context to inject into AI multi-agent prompts."""
        result = self.query(question, top_k=top_k)
        if not result.citations:
            return ""

        return f"\n[ACADEMIC RESEARCH GROUNDING (arXiv q-fin)]:\n{result.synthesized_context}\n"
