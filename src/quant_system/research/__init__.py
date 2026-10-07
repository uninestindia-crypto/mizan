"""Quantitative research, arXiv q-fin literature search, and RAG retrieval."""

from quant_system.research.arxiv_client import ArxivClient, PaperMetadata
from quant_system.research.embedding_gemma import (
    SUPPORTED_DIMENSIONS,
    EmbeddingGemmaProvider,
    EmbeddingStats,
)
from quant_system.research.rag_engine import QuantPaperRAG, RAGResult

__all__ = [
    "ArxivClient",
    "EmbeddingGemmaProvider",
    "EmbeddingStats",
    "PaperMetadata",
    "QuantPaperRAG",
    "RAGResult",
    "SUPPORTED_DIMENSIONS",
]
