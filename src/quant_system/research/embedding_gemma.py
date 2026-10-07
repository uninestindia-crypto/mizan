"""EmbeddingGemma 2 provider: On-device multimodal & text embeddings for Quant OS.

Supports:
- Matryoshka Representation Learning (MRL) dimension truncation (128, 256, 512, 768).
- Multiple backends: Local Ollama / HTTP endpoint, in-process PyTorch/Transformers,
  and deterministic synthetic fallback for offline/CI environments.
- High-speed in-memory vector caching for sub-millisecond retrieval.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

SUPPORTED_DIMENSIONS = (128, 256, 512, 768)
DEFAULT_DIMENSION = 768
DEFAULT_MODEL_NAME = "google/embeddinggemma-270m"
DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/embeddings"


@dataclass(frozen=True, slots=True)
class EmbeddingStats:
    """Telemetry and operational metadata for embedding generation."""

    model_name: str
    dimension: int
    backend: str
    cached_hits: int
    total_embedded: int


class EmbeddingGemmaProvider:
    """High-performance EmbeddingGemma 2 provider with Matryoshka truncation."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        dimensions: int = DEFAULT_DIMENSION,
        mode: str = "auto",  # 'auto', 'ollama', 'transformers', 'synthetic'
        endpoint_url: str | None = None,
        cache_size: int = 4096,
    ) -> None:
        if dimensions not in SUPPORTED_DIMENSIONS:
            valid_dims = ", ".join(str(d) for d in SUPPORTED_DIMENSIONS)
            raise ValueError(
                f"Invalid dimension {dimensions}. Supported MRL dimensions: {valid_dims}"
            )

        self.model_name = model_name
        self.dimensions = dimensions
        self.mode = mode
        endpoint = endpoint_url or os.getenv("QUANTOS_EMBEDDING_ENDPOINT")
        self.endpoint_url: str = endpoint if endpoint else DEFAULT_OLLAMA_ENDPOINT
        self.cache_size = max(64, cache_size)

        self._cache: dict[str, list[float]] = {}
        self._cache_hits = 0
        self._total_calls = 0
        self._active_backend = self._determine_backend()

    @property
    def active_backend(self) -> str:
        """Returns the currently active execution backend."""
        return self._active_backend

    def _determine_backend(self) -> str:
        """Determines the appropriate execution backend."""
        if self.mode == "synthetic":
            return "synthetic"

        if os.getenv("QUANTOS_SYNTHETIC_MODE") == "1":
            logger.info(
                "QUANTOS_SYNTHETIC_MODE=1 enabled; using synthetic EmbeddingGemma provider."
            )
            return "synthetic"

        if self.mode == "ollama":
            return "ollama"

        if self.mode == "transformers":
            return "transformers"

        # In 'auto' mode, test if Ollama endpoint is reachable
        try:
            import httpx

            resp = httpx.get(
                self.endpoint_url.replace("/api/embeddings", "/api/version"),
                timeout=0.3,
            )
            if resp.status_code == 200:
                logger.info("Local Ollama embedding endpoint reachable at %s", self.endpoint_url)
                return "ollama"
        except Exception:
            pass

        # Check if transformers and torch are installed
        try:
            import importlib.util

            if importlib.util.find_spec("torch") and importlib.util.find_spec("transformers"):
                return "transformers"
        except Exception:
            pass

        # Safe zero-dependency fallback for standalone desktop and CI
        return "synthetic"

    def embed_text(self, text: str) -> list[float]:
        """Generates a normalized dense vector for a single text string."""
        normalized_key = text.strip().lower()
        if not normalized_key:
            return [0.0] * self.dimensions

        cached = self._cache.get(normalized_key)
        if cached is not None:
            self._cache_hits += 1
            return cached

        vectors = self.embed_texts([text])
        return vectors[0]

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Generates normalized dense vectors for a sequence of texts."""
        if not texts:
            return []

        results: list[list[float]] = []
        to_compute_indices: list[int] = []
        to_compute_texts: list[str] = []

        for idx, text in enumerate(texts):
            clean_text = text.strip()
            cache_key = clean_text.lower()
            if cache_key in self._cache:
                self._cache_hits += 1
                results.append(self._cache[cache_key])
            else:
                results.append([])
                to_compute_indices.append(idx)
                to_compute_texts.append(clean_text)

        if to_compute_texts:
            computed_vectors: list[list[float]]
            if self._active_backend == "ollama":
                computed_vectors = self._embed_via_ollama(to_compute_texts)
            elif self._active_backend == "transformers":
                computed_vectors = self._embed_via_transformers(to_compute_texts)
            else:
                computed_vectors = self._embed_synthetic(to_compute_texts)

            for text_str, vec, orig_idx in zip(
                to_compute_texts, computed_vectors, to_compute_indices, strict=True
            ):
                # Matryoshka truncation and normalization
                processed = self._apply_matryoshka_norm(vec)
                results[orig_idx] = processed

                # Add to cache
                if len(self._cache) < self.cache_size:
                    self._cache[text_str.lower()] = processed
                self._total_calls += 1

        return results

    def _apply_matryoshka_norm(self, vector: Sequence[float]) -> list[float]:
        """Applies Matryoshka slicing and L2 unit-norm normalization."""
        truncated = list(vector[: self.dimensions])
        if len(truncated) < self.dimensions:
            truncated.extend([0.0] * (self.dimensions - len(truncated)))

        norm_sq = sum(x * x for x in truncated)
        if norm_sq <= 1e-12:
            return [0.0] * self.dimensions

        inv_norm = 1.0 / math.sqrt(norm_sq)
        return [round(x * inv_norm, 6) for x in truncated]

    def _embed_via_ollama(self, texts: Sequence[str]) -> list[list[float]]:
        """Queries local Ollama endpoint for embeddings."""
        import httpx

        vectors: list[list[float]] = []
        try:
            with httpx.Client(timeout=10.0) as client:
                for text in texts:
                    payload: dict[str, Any] = {
                        "model": "embeddinggemma",
                        "prompt": text,
                        "options": {"embedding_dim": self.dimensions},
                    }
                    resp = client.post(self.endpoint_url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    raw_vec = data.get("embedding", [])
                    vectors.append(raw_vec)
            return vectors
        except Exception as exc:
            logger.warning("Ollama embedding call failed (%s); falling back to synthetic.", exc)
            return self._embed_synthetic(texts)

    def _embed_via_transformers(self, texts: Sequence[str]) -> list[list[float]]:
        """Generates embeddings using PyTorch & Hugging Face Transformers."""
        try:
            import importlib

            torch = importlib.import_module("torch")
            transformers = importlib.import_module("transformers")

            tokenizer = transformers.AutoTokenizer.from_pretrained(self.model_name)
            model = transformers.AutoModel.from_pretrained(self.model_name).eval()

            inputs = tokenizer(
                list(texts),
                padding=True,
                truncation=True,
                max_length=8192,
                return_tensors="pt",
            )
            with torch.no_grad():
                outputs = model(**inputs)
                mask = inputs["attention_mask"].unsqueeze(-1)
                sum_embed = (outputs.last_hidden_state * mask).sum(dim=1)
                counts = mask.sum(dim=1).clamp(min=1e-9)
                mean_pooled = sum_embed / counts
                raw_list = mean_pooled.cpu().tolist()
                return [[float(v) for v in row] for row in raw_list]
        except Exception as exc:
            logger.warning(
                "In-process transformers embedding failed (%s); falling back to synthetic.", exc
            )
            return self._embed_synthetic(texts)

    def _embed_synthetic(self, texts: Sequence[str]) -> list[list[float]]:
        """Deterministic pseudo-semantic embedding generation for offline & CI testing.

        Maps financial and quantitative terms into correlated semantic subspace
        clusters so cosine similarities behave predictably in tests.
        """
        vectors: list[list[float]] = []
        # Key concept clusters for realistic synthetic similarity
        clusters: dict[str, int] = {
            "sharpe": 10,
            "overfit": 10,
            "deflated": 10,
            "backtest": 10,
            "order": 20,
            "book": 20,
            "microstructure": 20,
            "spread": 20,
            "liquidity": 20,
            "shariah": 30,
            "halal": 30,
            "zakat": 30,
            "tasis": 30,
            "aaoifi": 30,
            "volatility": 40,
            "garch": 40,
            "regime": 40,
            "jump": 40,
            "momentum": 50,
            "trend": 50,
            "reversal": 50,
        }

        for text in texts:
            vec = [0.0] * 768
            clean = text.lower()
            words = re.findall(r"\b[a-z]{3,}\b", clean)

            # Determine dominant semantic cluster
            cluster_weights: dict[int, float] = {}
            for w in words:
                for keyword, cluster_id in clusters.items():
                    if keyword in w:
                        cluster_weights[cluster_id] = cluster_weights.get(cluster_id, 0.0) + 2.0

            # Assign cluster subspace components
            for cluster_id, weight in cluster_weights.items():
                offset = cluster_id * 10
                for i in range(offset, offset + 30):
                    vec[i % 768] += weight * (1.0 + math.sin(i * 0.5))

            # Add hashed token components
            for w in words:
                h = int(hashlib.sha256(w.encode("utf-8")).hexdigest()[:8], 16)
                idx1 = h % 768
                idx2 = (h >> 4) % 768
                vec[idx1] += 1.0
                vec[idx2] += 0.5

            # Base hash to guarantee uniqueness and non-zero norm
            doc_hash = hashlib.sha256(clean.encode("utf-8")).digest()
            for i in range(min(len(doc_hash), 32)):
                byte_val = (doc_hash[i] - 128) / 128.0
                vec[i * 24] += byte_val

            vectors.append(vec)

        return vectors

    def get_stats(self) -> EmbeddingStats:
        """Returns operational metrics and cache statistics."""
        return EmbeddingStats(
            model_name=self.model_name,
            dimension=self.dimensions,
            backend=self._active_backend,
            cached_hits=self._cache_hits,
            total_embedded=self._total_calls,
        )
