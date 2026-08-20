"""QuantPaperRAG: High-performance semantic retrieval engine for quantitative finance research."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from quant_system.research.arxiv_client import ArxivClient, PaperMetadata


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

    def __init__(self, arxiv_client: ArxivClient | None = None) -> None:
        self.arxiv_client = arxiv_client or ArxivClient()
        self.papers: list[PaperMetadata] = []
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
        """Indexes paper titles, abstracts, and categories into a TF-IDF vector space."""
        for p in papers:
            if not any(existing.arxiv_id == p.arxiv_id for existing in self.papers):
                self.papers.append(p)

        n_docs = len(self.papers)
        if n_docs == 0:
            return

        # 1. Compute Document Frequencies
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

        # 2. Compute IDF: log((N + 1) / (DF + 1)) + 1
        self.idf = {
            term: math.log((n_docs + 1.0) / (count + 1.0)) + 1.0
            for term, count in df_counts.items()
        }

        # 3. Compute normalized TF-IDF vectors
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

    def search_and_index_arxiv(self, query: str, max_results: int = 5) -> int:
        """Queries arXiv live, parses results, and adds them to the semantic index."""
        fetched = self.arxiv_client.search_papers(query=query, max_results=max_results)
        initial_count = len(self.papers)
        self.index_papers(fetched)
        return len(self.papers) - initial_count

    def query(self, question: str, top_k: int = 3) -> RAGResult:
        """Performs semantic cosine similarity search over indexed quantitative research papers."""
        q_tokens = self.tokenize(question)
        if not q_tokens or not self.doc_vectors:
            return RAGResult(
                query=question,
                top_papers=[],
                synthesized_context="No relevant research papers indexed.",
                citations=[],
            )

        q_tf = Counter(q_tokens)
        q_vec: dict[str, float] = {}
        for term, count in q_tf.items():
            tfidf = (1.0 + math.log(count)) * self.idf.get(term, 1.0)
            q_vec[term] = tfidf

        q_norm = math.sqrt(sum(v * v for v in q_vec.values()))
        if q_norm == 0:
            q_norm = 1.0

        scores: list[tuple[int, float]] = []
        for idx, doc_vec in enumerate(self.doc_vectors):
            dot_product = sum(doc_vec.get(t, 0.0) * w for t, w in q_vec.items())
            sim = dot_product / (q_norm * self.doc_lengths[idx])
            scores.append((idx, sim))

        # Sort by similarity
        scores.sort(key=lambda x: x[1], reverse=True)
        top_indices = scores[:top_k]

        matched_papers: list[tuple[PaperMetadata, float]] = [
            (self.papers[i], round(score, 4)) for i, score in top_indices if score > 0.0
        ]

        if not matched_papers:
            # Fallback to first available papers if exact keywords had low overlap
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
        )

    def format_advisor_context(self, question: str, top_k: int = 2) -> str:
        """Formats concise academic context to inject into AI multi-agent prompts."""
        result = self.query(question, top_k=top_k)
        if not result.citations:
            return ""

        return f"\n[ACADEMIC RESEARCH GROUNDING (arXiv q-fin)]:\n{result.synthesized_context}\n"
