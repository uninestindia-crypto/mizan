"""Unit tests for EmbeddingGemma 2 provider and its integration with QuantPaperRAG."""

from __future__ import annotations

import math
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from quant_system.research.arxiv_client import ArxivClient, PaperMetadata
from quant_system.research.embedding_gemma import (
    SUPPORTED_DIMENSIONS,
    EmbeddingGemmaProvider,
    EmbeddingStats,
)
from quant_system.research.rag_engine import QuantPaperRAG


def test_supported_dimensions_and_validation() -> None:
    assert SUPPORTED_DIMENSIONS == (128, 256, 512, 768)

    # Valid dimensions initialize cleanly
    for dim in (128, 256, 512, 768):
        provider = EmbeddingGemmaProvider(dimensions=dim, mode="synthetic")
        assert provider.dimensions == dim

    # Invalid dimension raises ValueError
    with pytest.raises(ValueError, match="Invalid dimension"):
        EmbeddingGemmaProvider(dimensions=64, mode="synthetic")

    with pytest.raises(ValueError, match="Invalid dimension"):
        EmbeddingGemmaProvider(dimensions=1024, mode="synthetic")


def test_matryoshka_dimension_and_unit_norm() -> None:
    for dim in (128, 256, 512, 768):
        provider = EmbeddingGemmaProvider(dimensions=dim, mode="synthetic")
        vec = provider.embed_text("High-frequency algorithmic market making on NSE order books")

        assert len(vec) == dim
        norm = math.sqrt(sum(x * x for x in vec))
        assert pytest.approx(norm, rel=1e-3) == 1.0


def test_embedding_determinism_and_cache() -> None:
    provider = EmbeddingGemmaProvider(dimensions=256, mode="synthetic")
    text = "Deflated Sharpe Ratio prevents multiple testing bias in systematic strategies"

    vec1 = provider.embed_text(text)
    assert provider.get_stats().cached_hits == 0

    vec2 = provider.embed_text(text)
    assert provider.get_stats().cached_hits == 1
    assert vec1 == vec2

    stats: EmbeddingStats = provider.get_stats()
    assert stats.dimension == 256
    assert stats.backend == "synthetic"
    assert stats.total_embedded >= 1


def test_batch_embedding() -> None:
    provider = EmbeddingGemmaProvider(dimensions=512, mode="synthetic")
    queries = [
        "Momentum cross-sectional alpha",
        "Ornstein-Uhlenbeck volatility jump diffusion",
        "Shariah screening debt-to-market-cap ratio",
    ]
    vectors = provider.embed_texts(queries)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 512
        norm = math.sqrt(sum(x * x for x in v))
        assert pytest.approx(norm, rel=1e-3) == 1.0


def test_semantic_cluster_similarity_in_synthetic_mode() -> None:
    provider = EmbeddingGemmaProvider(dimensions=768, mode="synthetic")

    v_sharpe = provider.embed_text("Deflated Sharpe ratio and backtest overfitting")
    v_overfit = provider.embed_text("Overfitting bias in backtesting strategies")
    v_shariah = provider.embed_text("Shariah compliance AAOIFI financial screening rules")

    sim_related = sum(a * b for a, b in zip(v_sharpe, v_overfit, strict=True))
    sim_unrelated = sum(a * b for a, b in zip(v_sharpe, v_shariah, strict=True))

    assert sim_related > sim_unrelated


def test_ollama_mock_and_fallback() -> None:
    provider = EmbeddingGemmaProvider(dimensions=256, mode="ollama")

    # Mock successful Ollama response
    mock_raw_vector = [0.1] * 256
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embedding": mock_raw_vector}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        vec = provider.embed_text("Order flow imbalance")
        assert len(vec) == 256
        norm = math.sqrt(sum(x * x for x in vec))
        assert pytest.approx(norm, rel=1e-3) == 1.0

    # Test error handling falls back gracefully to synthetic
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.side_effect = RuntimeError("Connection refused")
        mock_client_cls.return_value = mock_client

        fallback_vec = provider.embed_text("Fallback test on connection loss")
        assert len(fallback_vec) == 256
        assert math.sqrt(sum(x * x for x in fallback_vec)) > 0.99


def test_quant_paper_rag_dense_and_hybrid_search() -> None:
    provider = EmbeddingGemmaProvider(dimensions=512, mode="synthetic")

    # 1. Pure dense search
    rag_dense = QuantPaperRAG(embedding_provider=provider, dense_weight=1.0)
    res_dense = rag_dense.query("How to avoid backtest overfitting with Sharpe ratio?", top_k=2)

    assert len(res_dense.top_papers) > 0
    assert res_dense.metadata["retrieval_mode"] in (
        "embedding_gemma_dense",
        "embedding_gemma_hybrid",
    )
    assert res_dense.metadata["dense_weight"] == 1.0
    assert res_dense.metadata["embedding_dimension"] == 512

    # 2. Hybrid search (dense + sparse)
    rag_hybrid = QuantPaperRAG(embedding_provider=provider, dense_weight=0.60)
    res_hybrid = rag_hybrid.query("Limit order book optimal spread market making", top_k=2)

    assert len(res_hybrid.top_papers) > 0
    assert res_hybrid.metadata["retrieval_mode"] == "embedding_gemma_hybrid"
    assert res_hybrid.metadata["dense_weight"] == 0.60

    # 3. Sparse TF-IDF fallback when use_embeddings=False
    rag_sparse = QuantPaperRAG(use_embeddings=False)
    res_sparse = rag_sparse.query("Limit order book optimal spread", top_k=2)

    assert len(res_sparse.top_papers) > 0
    assert res_sparse.metadata["retrieval_mode"] == "tfidf"
    assert res_sparse.metadata["dense_weight"] == 0.0


def test_quant_paper_rag_new_paper_incremental_indexing() -> None:
    provider = EmbeddingGemmaProvider(dimensions=256, mode="synthetic")
    client = ArxivClient()
    rag = QuantPaperRAG(arxiv_client=client, embedding_provider=provider)

    initial_papers = len(rag.papers)
    initial_dense = len(rag.dense_vectors)
    assert initial_papers == initial_dense

    # Add a mock paper
    new_paper = PaperMetadata(
        arxiv_id="2610.99999",
        title="High-Frequency Statistical Arbitrage in Indian Markets",
        summary="Novel microstructure factor engineering for NSE equities using order flow imbalance.",
        authors=["Quant Team"],
        published=datetime(2026, 10, 1),
        pdf_url="https://arxiv.org/pdf/2610.99999.pdf",
        primary_category="q-fin.TR",
    )

    rag.index_papers([new_paper])
    assert len(rag.papers) == initial_papers + 1
    assert len(rag.dense_vectors) == initial_dense + 1

    res = rag.query("statistical arbitrage microstructure factor NSE equities", top_k=1)
    assert len(res.top_papers) > 0
    assert res.top_papers[0][0].arxiv_id == "2610.99999"
