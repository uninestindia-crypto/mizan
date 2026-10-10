"""EmbeddingGemma 2: the provider loads the real model when it can, and never calls the substitute the model.

No download happens here. A fake ``sentence_transformers`` module stands in for the real package, so these tests check how the
provider uses it (model id, text-only config, task prefixes, width, fallback) and what it reports, not the model's own numbers.
"""

from __future__ import annotations

import importlib
import math
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from quant_system.research import embedding_gemma
from quant_system.research.embedding_gemma import (
    DEFAULT_MODEL_NAME,
    DOCUMENT_PREFIX,
    QUERY_PREFIX,
    EmbeddingGemmaProvider,
)
from quant_system.research.rag_engine import QuantPaperRAG
from quant_system.server.v2 import hardware
from quant_system.server.v2.router import quant_slm_status

ROOT = Path(__file__).resolve().parents[1]


class FakeModel:
    """Records how the provider built and called it."""

    def __init__(
        self,
        name: str,
        config_kwargs: dict[str, Any] | None,
        model_kwargs: dict[str, Any] | None,
        plan: dict[str, Any],
    ) -> None:
        self.name = name
        self.config_kwargs = config_kwargs
        self.model_kwargs = model_kwargs
        self.max_seq_length: int | None = (
            None  # the real library reports no limit; the provider sets it
        )
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []
        self._plan = plan

    def encode(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        self.calls.append(list(texts))
        self.kwargs.append(kwargs)
        if self._plan.get("fail_on_encode_call") == len(self.calls):
            raise RuntimeError("out of memory")
        width = int(self._plan.get("width", 768))
        return [[float((sum(map(ord, t)) + i * 31) % 17 + 1) for i in range(width)] for t in texts]


def install_fake(monkeypatch: pytest.MonkeyPatch, **plan: Any) -> list[FakeModel]:
    """Make ``import sentence_transformers`` return a fake; the returned list collects every model built."""
    built: list[FakeModel] = []

    class FakeSentenceTransformer:
        def __new__(  # type: ignore[misc]
            cls,
            name: str,
            config_kwargs: dict[str, Any] | None = None,
            model_kwargs: dict[str, Any] | None = None,
        ) -> FakeModel:
            if "init_error" in plan:
                raise plan["init_error"]
            model = FakeModel(name, config_kwargs, model_kwargs, plan)
            built.append(model)
            return model

    fake_module = MagicMock()
    fake_module.SentenceTransformer = FakeSentenceTransformer
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None) -> Any:
        return fake_module if name == "sentence_transformers" else real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    return built


def norm(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


# ----------------------------------------------------------------------------- the model id is a real one


def test_the_default_model_is_the_published_embeddinggemma_2() -> None:
    assert DEFAULT_MODEL_NAME == "google/embeddinggemma-2"
    # the text the model card tells callers to put in front of queries and documents
    assert QUERY_PREFIX == "task: search result | query: "
    assert DOCUMENT_PREFIX == "title: none | text: "


def test_the_id_that_does_not_exist_is_nowhere_in_the_product() -> None:
    dead = "embeddinggemma-" + "270m"
    offenders = []
    for folder in ("src", "scripts", "frontend/src"):
        for path in (ROOT / folder).rglob("*"):
            if path.suffix in {".py", ".ts", ".tsx", ".html", ".json"} and path.is_file():
                if dead in path.read_text(encoding="utf-8", errors="ignore"):
                    offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


# ----------------------------------------------------------------------------- the real path


def test_the_real_model_is_loaded_text_only_once_with_the_card_prefixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = install_fake(monkeypatch)
    provider = EmbeddingGemmaProvider(dimensions=256, mode="transformers")
    assert provider.uses_real_model is False  # nothing has run yet
    assert "loads the first time" in provider.label

    doc = provider.embed_texts(["Deflated Sharpe ratio"], kind="document")[0]
    query = provider.embed_text("how do I avoid overfitting", kind="query")

    assert len(built) == 1  # loaded once, reused
    model = built[0]
    assert model.name == "google/embeddinggemma-2"
    assert model.config_kwargs == {
        "vision_config": None,
        "audio_config": None,
    }  # text only, about 270M
    # float32 (9 to 10 times faster than the checkpoint's bfloat16 on a laptop CPU) and the card's 8,192-token limit
    assert model.model_kwargs == {"dtype": "float32"}
    assert model.max_seq_length == 8192
    assert model.calls == [
        [DOCUMENT_PREFIX + "Deflated Sharpe ratio"],
        [QUERY_PREFIX + "how do I avoid overfitting"],
    ]
    assert all(kw["normalize_embeddings"] is True for kw in model.kwargs)
    assert len(doc) == 256 and len(query) == 256  # Matryoshka truncation
    assert pytest.approx(norm(doc), rel=1e-3) == 1.0  # and re-normalised

    assert provider.uses_real_model is True
    assert provider.label == "EmbeddingGemma 2 (running on this computer)"
    stats = provider.get_stats()
    assert stats.is_real_model is True and stats.backend == "transformers"
    assert stats.fallback_reason is None
    assert provider.served_model == "google/embeddinggemma-2"


def test_a_document_and_a_query_with_the_same_words_are_not_confused_in_the_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = install_fake(monkeypatch)
    provider = EmbeddingGemmaProvider(dimensions=128, mode="transformers")
    as_doc = provider.embed_text("order flow imbalance", kind="document")
    as_query = provider.embed_text("order flow imbalance", kind="query")
    assert as_doc != as_query
    assert len(built[0].calls) == 2


# ----------------------------------------------------------------------------- when the real model cannot run


def test_a_model_that_fails_to_load_is_replaced_and_the_report_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = install_fake(monkeypatch, init_error=OSError("no weights on this computer"))
    provider = EmbeddingGemmaProvider(dimensions=256, mode="transformers")

    vec = provider.embed_text("Shariah screening")
    assert len(vec) == 256 and pytest.approx(norm(vec), rel=1e-3) == 1.0  # still answers

    assert provider.active_backend == "synthetic"
    assert provider.uses_real_model is False
    assert provider.generation == 1
    stats = provider.get_stats()
    assert stats.is_real_model is False
    assert stats.fallback_reason is not None and "transformers failed" in stats.fallback_reason
    assert "no weights" in stats.fallback_reason
    assert provider.label == "Built-in keyword matching (EmbeddingGemma 2 could not run here)"
    assert provider.served_model == "built-in keyword matching"

    provider.embed_text("another sentence")
    assert built == []  # it does not try to load the model again on every call


def test_a_model_that_answers_with_too_few_numbers_is_not_padded_with_zeros(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake(monkeypatch, width=512)
    provider = EmbeddingGemmaProvider(dimensions=768, mode="transformers")
    provider.embed_text("momentum")
    assert provider.active_backend == "synthetic"
    assert "512 numbers" in (provider.get_stats().fallback_reason or "")


def test_vectors_from_a_failed_backend_are_forgotten(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake(monkeypatch, fail_on_encode_call=2)
    provider = EmbeddingGemmaProvider(dimensions=128, mode="transformers")
    first = provider.embed_text("alpha")
    assert provider.uses_real_model is True
    provider.embed_text("beta")  # the second call to the model fails
    assert provider.active_backend == "synthetic"
    again = provider.embed_text("alpha")
    assert again != first  # not the real model's cached vector, a substitute one


# ----------------------------------------------------------------------------- Ollama is never called version 2


def test_ollama_uses_the_named_model_and_is_never_labelled_embeddinggemma_2() -> None:
    provider = EmbeddingGemmaProvider(dimensions=128, mode="ollama", ollama_model="my-embedder")
    response = MagicMock()
    response.json.return_value = {"embedding": [0.5] * 768}
    with patch("httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = response
        client_cls.return_value = client
        provider.embed_text("liquidity")
    assert client.post.call_args.kwargs["json"] == {"model": "my-embedder", "prompt": "liquidity"}
    assert provider.label == "A local model through Ollama (my-embedder)"
    assert "EmbeddingGemma 2" not in provider.label
    assert provider.uses_real_model is False
    assert provider.served_model == "my-embedder"


# ----------------------------------------------------------------------------- what the substitute says about itself


@pytest.mark.parametrize(
    ("status", "words"),
    [
        ("NOT_INSTALLED", "is not installed on this computer"),
        ("NEEDS_DOWNLOAD", "has not been downloaded yet"),
    ],
)
def test_the_substitute_says_why_the_model_is_not_in_use(
    monkeypatch: pytest.MonkeyPatch, status: str, words: str
) -> None:
    monkeypatch.setattr(
        embedding_gemma, "real_model_status", lambda name=DEFAULT_MODEL_NAME, model_dir=None: status
    )
    monkeypatch.delenv("QUANTOS_SYNTHETIC_MODE", raising=False)
    with patch("httpx.get", side_effect=OSError("no Ollama here")):
        provider = EmbeddingGemmaProvider(mode="auto")
    assert provider.active_backend == "synthetic"
    assert provider.label == f"Built-in keyword matching (EmbeddingGemma 2 {words})"
    assert provider.uses_real_model is False


def test_a_switched_off_provider_says_it_is_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    assert EmbeddingGemmaProvider(mode="synthetic").label.endswith("is switched off)")
    monkeypatch.setenv("QUANTOS_SYNTHETIC_MODE", "1")
    assert EmbeddingGemmaProvider(mode="auto").label.endswith("is switched off)")


def test_auto_mode_uses_the_real_model_only_when_it_is_already_on_this_computer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUANTOS_SYNTHETIC_MODE", raising=False)
    monkeypatch.setattr(
        embedding_gemma,
        "real_model_status",
        lambda name=DEFAULT_MODEL_NAME, model_dir=None: "READY",
    )
    assert EmbeddingGemmaProvider(mode="auto").active_backend == "transformers"
    # packages without the weights must not start a 1.5 GB download behind the user's back
    monkeypatch.setattr(
        embedding_gemma,
        "real_model_status",
        lambda name=DEFAULT_MODEL_NAME, model_dir=None: "NEEDS_DOWNLOAD",
    )
    with patch("httpx.get", side_effect=OSError("no Ollama here")):
        assert EmbeddingGemmaProvider(mode="auto").active_backend == "synthetic"


@pytest.mark.parametrize("missing", ["sentence_transformers", "torch", "torchvision", "PIL"])
def test_the_model_is_not_ready_when_any_library_it_needs_is_missing(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    # A real run found that the model's processor imports the image libraries even for text, so READY must name them too.
    monkeypatch.setattr(embedding_gemma, "_weights_cached", lambda name=DEFAULT_MODEL_NAME: True)
    with monkeypatch.context() as patched:
        patched.setattr(
            embedding_gemma.importlib.util,
            "find_spec",
            lambda name, *args: None if name == missing else object(),
        )
        assert embedding_gemma.torch_route_status() == "NOT_INSTALLED"


def test_the_model_is_ready_only_with_every_library_and_the_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as patched:
        patched.setattr(embedding_gemma.importlib.util, "find_spec", lambda name, *args: object())
        patched.setattr(embedding_gemma, "_weights_cached", lambda name=DEFAULT_MODEL_NAME: True)
        assert embedding_gemma.torch_route_status() == "READY"
        patched.setattr(embedding_gemma, "_weights_cached", lambda name=DEFAULT_MODEL_NAME: False)
        assert embedding_gemma.torch_route_status() == "NEEDS_DOWNLOAD"


def test_the_status_check_reads_the_cache_without_importing_or_downloading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    assert embedding_gemma._weights_cached() is False
    snapshot = tmp_path / "models--google--embeddinggemma-2" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    assert embedding_gemma._weights_cached() is False  # a folder is not the weights
    (snapshot / "model.safetensors").write_bytes(b"x")
    assert embedding_gemma._weights_cached() is True


# ----------------------------------------------------------------------------- paper search never mixes two backends


def test_paper_search_rebuilds_its_vectors_when_the_backend_changes_underneath_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake(
        monkeypatch, fail_on_encode_call=2
    )  # the library is indexed (call 1); the question fails (call 2)
    provider = EmbeddingGemmaProvider(dimensions=256, mode="transformers")
    rag = QuantPaperRAG(embedding_provider=provider)
    assert provider.uses_real_model is True

    result = rag.query("How do I avoid backtest overfitting?", top_k=2)

    assert provider.active_backend == "synthetic"
    assert result.metadata["embedding_is_real_model"] is False
    assert "Built-in keyword matching" in result.metadata["embedding_label"]
    assert result.metadata["embedding_model"] == "built-in keyword matching"
    assert rag._dense_generation == provider.generation
    # every paper is now a substitute vector, so they can be compared with the question's
    expected = provider.embed_texts([rag._paper_text(p) for p in rag.papers])
    assert rag.dense_vectors == expected
    assert result.top_papers


def test_paper_search_metadata_tells_the_truth_for_the_substitute() -> None:
    rag = QuantPaperRAG(embedding_provider=EmbeddingGemmaProvider(mode="synthetic"))
    metadata = rag.query("limit order book spread", top_k=1).metadata
    assert metadata["embedding_is_real_model"] is False
    assert metadata["embedding_model"] == "built-in keyword matching"
    assert metadata["backend"] == "synthetic"


# ----------------------------------------------------------------------------- the screens


@pytest.mark.parametrize(
    ("found", "status", "words"),
    [
        ("READY", "READY", "It runs on this computer."),
        ("NEEDS_DOWNLOAD", "NOT DOWNLOADED", "Open Research and choose Turn on smarter search"),
        ("NOT_INSTALLED", "NOT INSTALLED", "not installed on this computer"),
    ],
)
def test_the_hardware_card_says_whether_the_model_can_really_run(
    monkeypatch: pytest.MonkeyPatch, found: str, status: str, words: str
) -> None:
    monkeypatch.setattr(hardware, "real_model_status", lambda: found)
    card = next(m for m in hardware._catalog_local_models("cpu") if m.id == "embeddinggemma-2")
    assert card.status == status
    assert words in card.description
    assert card.name == "EmbeddingGemma 2 (text, about 270M)"
    assert card.size == "~330 MB download"
    # the product promises halal results never come from an AI model
    assert "Halal results never use it" in card.description
    assert "AAOIFI" not in card.description


def test_the_quant_slm_status_does_not_claim_a_model_it_does_not_run() -> None:
    pillars = quant_slm_status()["pillars"]
    assert not any("EmbeddingGemma" in line for line in pillars)
    assert any("the same for every stock" in line for line in pillars)


# ----------------------------------------------------------------------------- the downloadable (ONNX) route


class FakeOnnxEmbedder:
    """Stands in for embedding_onnx.OnnxEmbedder and records what it was asked."""

    built: list[FakeOnnxEmbedder] = []
    fail = False

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self.calls: list[list[str]] = []
        FakeOnnxEmbedder.built.append(self)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if FakeOnnxEmbedder.fail:
            raise RuntimeError("the model file is damaged")
        return [[float((sum(map(ord, t)) + i * 31) % 17 + 1) for i in range(768)] for t in texts]


@pytest.fixture
def fake_onnx(monkeypatch: pytest.MonkeyPatch) -> type[FakeOnnxEmbedder]:
    FakeOnnxEmbedder.built = []
    FakeOnnxEmbedder.fail = False
    monkeypatch.setattr(embedding_gemma.embedding_onnx, "OnnxEmbedder", FakeOnnxEmbedder)
    return FakeOnnxEmbedder


def test_the_downloaded_model_is_used_with_the_card_prefixes(
    fake_onnx: type[FakeOnnxEmbedder], tmp_path: Path
) -> None:
    provider = EmbeddingGemmaProvider(dimensions=256, mode="onnx", model_dir=tmp_path)
    assert provider.uses_real_model is False and "loads the first time" in provider.label
    doc = provider.embed_texts(["Deflated Sharpe ratio"], kind="document")[0]
    query = provider.embed_text("avoid overfitting", kind="query")

    assert (
        len(fake_onnx.built) == 1 and fake_onnx.built[0].model_dir == tmp_path
    )  # loaded once, from the app's folder
    assert fake_onnx.built[0].calls == [
        [DOCUMENT_PREFIX + "Deflated Sharpe ratio"],
        [QUERY_PREFIX + "avoid overfitting"],
    ]
    assert len(doc) == len(query) == 256 and pytest.approx(norm(doc), rel=1e-3) == 1.0
    assert provider.uses_real_model is True and provider.active_backend == "onnx"
    assert provider.label == "EmbeddingGemma 2 (running on this computer)"
    assert provider.served_model == "google/embeddinggemma-2 (8-bit)"
    assert provider.get_stats().is_real_model is True


def test_a_damaged_download_falls_back_and_says_so(
    fake_onnx: type[FakeOnnxEmbedder], tmp_path: Path
) -> None:
    fake_onnx.fail = True
    provider = EmbeddingGemmaProvider(dimensions=128, mode="onnx", model_dir=tmp_path)
    vec = provider.embed_text("Shariah screening")
    assert len(vec) == 128 and pytest.approx(norm(vec), rel=1e-3) == 1.0
    assert provider.active_backend == "synthetic" and provider.uses_real_model is False
    assert provider.generation == 1
    assert "damaged" in (provider.get_stats().fallback_reason or "")
    assert provider.label == "Built-in keyword matching (EmbeddingGemma 2 could not run here)"


def test_auto_mode_prefers_the_downloaded_model_over_the_developer_route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("QUANTOS_SYNTHETIC_MODE", raising=False)
    monkeypatch.setattr(
        embedding_gemma.embedding_onnx, "onnx_status", lambda model_dir=None: "READY"
    )
    monkeypatch.setattr(
        embedding_gemma, "torch_route_status", lambda name=DEFAULT_MODEL_NAME: "READY"
    )
    assert EmbeddingGemmaProvider(mode="auto", model_dir=tmp_path).active_backend == "onnx"
    monkeypatch.setattr(
        embedding_gemma.embedding_onnx, "onnx_status", lambda model_dir=None: "NEEDS_DOWNLOAD"
    )
    assert EmbeddingGemmaProvider(mode="auto", model_dir=tmp_path).active_backend == "transformers"


@pytest.mark.parametrize(
    ("onnx", "torch", "expected"),
    [
        ("READY", "NOT_INSTALLED", "READY"),
        ("NEEDS_DOWNLOAD", "READY", "READY"),
        ("NEEDS_DOWNLOAD", "NOT_INSTALLED", "NEEDS_DOWNLOAD"),
        ("NOT_INSTALLED", "NEEDS_DOWNLOAD", "NEEDS_DOWNLOAD"),
        ("NOT_INSTALLED", "NOT_INSTALLED", "NOT_INSTALLED"),
    ],
)
def test_the_overall_status_combines_both_routes(
    monkeypatch: pytest.MonkeyPatch, onnx: str, torch: str, expected: str
) -> None:
    monkeypatch.setattr(embedding_gemma.embedding_onnx, "onnx_status", lambda model_dir=None: onnx)
    monkeypatch.setattr(
        embedding_gemma, "torch_route_status", lambda name=DEFAULT_MODEL_NAME: torch
    )
    assert embedding_gemma.real_model_status() == expected
