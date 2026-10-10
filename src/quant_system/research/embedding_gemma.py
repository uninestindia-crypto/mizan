"""EmbeddingGemma 2 text embeddings for Quant OS, with an honest account of what actually ran.

EmbeddingGemma 2 (``google/embeddinggemma-2``, Google, October 2026, Apache 2.0) is a 740M-parameter multimodal embedding model built
on Gemma 4. Quant OS only needs text, so the real backend loads its text-only configuration (about 270M parameters) through
sentence-transformers, the library the model card recommends. That library applies the model's own mean pooling, 512 to 768
projection and normalisation. This module adds the task prefixes the card requires, Matryoshka truncation (128, 256, 512, 768) and
re-normalisation.

Backends, tried in this order when ``mode="auto"``:

- ``transformers``: the real model, in this process. Needs sentence-transformers, torch, torchvision and pillow (the model's
  processor imports the image libraries even for text; none is bundled with the installed app) and a one-time download of about
  1.5 GB. ``auto`` only picks it when the weights are already on this computer, so nothing downloads by surprise. Measured on
  the reference laptop (Snapdragon X, 8 cores, float32): load about 4 s, five short texts 0.35 s, one 1,300-token text 3.9 s,
  peak memory about 2 GB. The checkpoint's own bfloat16 was 9 to 10 times slower on that CPU for the same vectors.
- ``ollama``: a local Ollama server. The model it serves is whatever ``QUANTOS_EMBEDDING_OLLAMA_MODEL`` names (default
  ``embeddinggemma``, the first-generation model). It is never reported as EmbeddingGemma 2.
- ``synthetic``: a deterministic keyword-and-hash substitute for CI and for computers with neither of the above. It is **not** a
  neural model. ``label`` and ``uses_real_model`` always say which one produced the vectors.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import math
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SUPPORTED_DIMENSIONS = (128, 256, 512, 768)
DEFAULT_DIMENSION = 768
DEFAULT_MODEL_NAME = "google/embeddinggemma-2"
DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434/api/embeddings"
DEFAULT_OLLAMA_MODEL = "embeddinggemma"
# The task prefixes from the model card. Queries and documents are embedded differently on purpose.
QUERY_PREFIX = "task: search result | query: "
DOCUMENT_PREFIX = "title: none | text: "
# The vision and audio towers are not needed for text; leaving them out loads about 270M of the 740M parameters.
TEXT_ONLY_CONFIG: dict[str, Any] = {"vision_config": None, "audio_config": None}
# float32, not the checkpoint's bfloat16: the card allows both, and on a laptop CPU float32 measured 9 to 10 times faster with the
# same vectors (cosine 0.9997 or better). The model's limit is 8,192 tokens; the library reports none, so it is set here.
MODEL_DTYPE = "float32"
MAX_TOKENS = 8192
# What the model needs to load even for text only: its processor imports the image libraries.
REQUIRED_PACKAGES = ("sentence_transformers", "torch", "torchvision", "PIL")


def _weights_cached(model_name: str = DEFAULT_MODEL_NAME) -> bool:
    """True when the model's weights file is already in the Hugging Face cache on this computer."""
    hub = os.getenv("HF_HUB_CACHE")
    root = (
        Path(hub)
        if hub
        else Path(os.getenv("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"
    )
    snapshots = root / ("models--" + model_name.replace("/", "--")) / "snapshots"
    try:
        return any((snap / "model.safetensors").is_file() for snap in snapshots.iterdir())
    except OSError:
        return False


def real_model_status(model_name: str = DEFAULT_MODEL_NAME) -> str:
    """Whether the real model could run here, without loading anything.

    ``READY`` (packages and weights present), ``NEEDS_DOWNLOAD`` (packages present, weights not yet on this computer) or
    ``NOT_INSTALLED`` (the packages are missing).
    """
    try:
        packages = all(importlib.util.find_spec(name) for name in REQUIRED_PACKAGES)
    except (ImportError, ValueError):
        packages = False
    if not packages:
        return "NOT_INSTALLED"
    return "READY" if _weights_cached(model_name) else "NEEDS_DOWNLOAD"


@dataclass(frozen=True, slots=True)
class EmbeddingStats:
    """Telemetry and operational metadata for embedding generation."""

    model_name: str
    dimension: int
    backend: str
    cached_hits: int
    total_embedded: int
    is_real_model: bool = False
    label: str = ""
    fallback_reason: str | None = None


class EmbeddingGemmaProvider:
    """EmbeddingGemma 2 embeddings with Matryoshka truncation, and a truthful report of the backend that ran."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        dimensions: int = DEFAULT_DIMENSION,
        mode: str = "auto",  # 'auto', 'ollama', 'transformers', 'synthetic'
        endpoint_url: str | None = None,
        cache_size: int = 4096,
        ollama_model: str | None = None,
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
        self.ollama_model: str = (
            ollama_model or os.getenv("QUANTOS_EMBEDDING_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        )
        self.cache_size = max(64, cache_size)

        self._cache: dict[str, list[float]] = {}
        self._cache_hits = 0
        self._total_calls = 0
        self._model: Any = None
        self._model_ready = False
        self._fallback_reason: str | None = None
        self._generation = 0
        self._switched_off = self.mode == "synthetic" or os.getenv("QUANTOS_SYNTHETIC_MODE") == "1"
        self._active_backend = self._determine_backend()

    @property
    def active_backend(self) -> str:
        """Returns the backend that produces vectors right now: transformers, ollama or synthetic."""
        return self._active_backend

    @property
    def generation(self) -> int:
        """Counts backend changes. A holder of earlier vectors must rebuild them when this moves."""
        return self._generation

    @property
    def uses_real_model(self) -> bool:
        """True only once EmbeddingGemma 2 itself has produced vectors in this process."""
        return self._active_backend == "transformers" and self._model_ready

    @property
    def served_model(self) -> str:
        """The name of what actually produces the vectors."""
        if self._active_backend == "transformers":
            return self.model_name
        if self._active_backend == "ollama":
            return self.ollama_model
        return "built-in keyword matching"

    @property
    def label(self) -> str:
        """A plain sentence for a screen: what is producing the vectors."""
        if self._active_backend == "transformers":
            if self._model_ready:
                return "EmbeddingGemma 2 (running on this computer)"
            return "EmbeddingGemma 2 (loads the first time it is used)"
        if self._active_backend == "ollama":
            return f"A local model through Ollama ({self.ollama_model})"
        return f"Built-in keyword matching (EmbeddingGemma 2 {self._why_not_real()})"

    def _why_not_real(self) -> str:
        if self._fallback_reason:
            return "could not run here"
        if self._switched_off:
            return "is switched off"
        reasons = {
            "NOT_INSTALLED": "is not installed on this computer",
            "NEEDS_DOWNLOAD": "has not been downloaded yet",
        }
        return reasons.get(real_model_status(self.model_name), "is not in use")

    def _determine_backend(self) -> str:
        """Determines the appropriate execution backend."""
        if self.mode == "synthetic":
            return "synthetic"

        if os.getenv("QUANTOS_SYNTHETIC_MODE") == "1":
            logger.info(
                "QUANTOS_SYNTHETIC_MODE=1 enabled; using the built-in substitute for embeddings."
            )
            return "synthetic"

        if self.mode == "ollama":
            return "ollama"

        if self.mode == "transformers":
            return "transformers"

        # In 'auto' mode the real model comes first, but only when it is already on this computer.
        if real_model_status(self.model_name) == "READY":
            return "transformers"

        # Then a local Ollama server, if one answers quickly.
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

        # Safe zero-dependency fallback for standalone desktop and CI
        return "synthetic"

    def _key(self, kind: str, clean_text: str) -> str:
        return f"{kind}\x00{clean_text}"

    def embed_text(self, text: str, *, kind: str = "document") -> list[float]:
        """Generates a normalized dense vector for a single text. ``kind`` is ``document`` or ``query``."""
        clean = text.strip()
        if not clean:
            return [0.0] * self.dimensions

        cached = self._cache.get(self._key(kind, clean))
        if cached is not None:
            self._cache_hits += 1
            return cached

        return self.embed_texts([text], kind=kind)[0]

    def embed_texts(self, texts: Sequence[str], *, kind: str = "document") -> list[list[float]]:
        """Generates normalized dense vectors for a sequence of texts. ``kind`` is ``document`` or ``query``."""
        if not texts:
            return []

        results: list[list[float]] = []
        to_compute_indices: list[int] = []
        to_compute_texts: list[str] = []

        for idx, text in enumerate(texts):
            clean_text = text.strip()
            cached = self._cache.get(self._key(kind, clean_text))
            if cached is not None:
                self._cache_hits += 1
                results.append(cached)
            else:
                results.append([])
                to_compute_indices.append(idx)
                to_compute_texts.append(clean_text)

        if to_compute_texts:
            computed_vectors = self._compute(to_compute_texts, kind)

            for text_str, vec, orig_idx in zip(
                to_compute_texts, computed_vectors, to_compute_indices, strict=True
            ):
                # Matryoshka truncation and normalization
                processed = self._apply_matryoshka_norm(vec)
                results[orig_idx] = processed

                # Add to cache
                if len(self._cache) < self.cache_size:
                    self._cache[self._key(kind, text_str)] = processed
                self._total_calls += 1

        return results

    def _compute(self, texts: Sequence[str], kind: str) -> list[list[float]]:
        """Runs the active backend; if a real backend fails, switches to the substitute and says so."""
        backend = self._active_backend
        if backend == "synthetic":
            return self._embed_synthetic(texts)
        try:
            if backend == "transformers":
                return self._embed_via_model(texts, kind)
            return self._embed_via_ollama(texts)
        except Exception as exc:
            self._fall_back(backend, exc)
            return self._embed_synthetic(texts)

    def _fall_back(self, backend: str, exc: Exception) -> None:
        """Stays on the substitute from now on, and forgets vectors from the backend that failed."""
        self._fallback_reason = f"{backend} failed: {type(exc).__name__}: {exc}"
        logger.warning("%s; using the built-in substitute from now on.", self._fallback_reason)
        self._active_backend = "synthetic"
        self._model_ready = False
        self._model = None
        self._cache.clear()
        self._generation += 1

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

    def _check_width(self, vectors: Sequence[Sequence[float]], source: str) -> None:
        for vec in vectors:
            if len(vec) < self.dimensions:
                raise ValueError(
                    f"{source} returned {len(vec)} numbers per text, fewer than the {self.dimensions} asked for"
                )

    def _load_model(self) -> Any:
        """Loads EmbeddingGemma 2 (text only) once and keeps it for later calls."""
        if self._model is None:
            library = importlib.import_module("sentence_transformers")
            model = library.SentenceTransformer(
                self.model_name,
                config_kwargs=dict(TEXT_ONLY_CONFIG),
                model_kwargs={"dtype": MODEL_DTYPE},
            )
            model.max_seq_length = MAX_TOKENS
            self._model = model
        return self._model

    def _embed_via_model(self, texts: Sequence[str], kind: str) -> list[list[float]]:
        """Embeds with EmbeddingGemma 2 itself: its own pooling, projection and normalisation, plus the task prefix."""
        prefix = QUERY_PREFIX if kind == "query" else DOCUMENT_PREFIX
        model = self._load_model()
        rows = model.encode(
            [prefix + text for text in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors = [[float(v) for v in row] for row in rows]
        self._check_width(vectors, "EmbeddingGemma 2")
        self._model_ready = True
        return vectors

    def _embed_via_ollama(self, texts: Sequence[str]) -> list[list[float]]:
        """Queries a local Ollama server for embeddings from the model named by ``ollama_model``."""
        import httpx

        vectors: list[list[float]] = []
        with httpx.Client(timeout=10.0) as client:
            for text in texts:
                payload: dict[str, Any] = {"model": self.ollama_model, "prompt": text}
                resp = client.post(self.endpoint_url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                vectors.append(data.get("embedding", []))
        self._check_width(vectors, "Ollama")
        return vectors

    def _embed_synthetic(self, texts: Sequence[str]) -> list[list[float]]:
        """Deterministic pseudo-semantic embedding generation for offline & CI testing.

        Maps financial and quantitative terms into correlated semantic subspace
        clusters so cosine similarities behave predictably in tests. This is keyword
        matching and hashing, not a neural model, and it ignores the query/document kind.
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
        """Returns operational metrics, cache statistics and which backend really produced the vectors."""
        return EmbeddingStats(
            model_name=self.model_name,
            dimension=self.dimensions,
            backend=self._active_backend,
            cached_hits=self._cache_hits,
            total_embedded=self._total_calls,
            is_real_model=self.uses_real_model,
            label=self.label,
            fallback_reason=self._fallback_reason,
        )
