"""The downloadable EmbeddingGemma 2: pinned files, a download that verifies what it gets, and the ONNX embedder.

Nothing here touches the internet. A pretend network serves small stand-in files. One test runs the real model when its files are
on this computer (set ``QUANTOS_TEST_MODEL_DIR`` to a folder that holds them) and is skipped otherwise.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import math
import os
import re
import shutil
import urllib.error
from collections import namedtuple
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from quant_system.research import embedding_onnx
from quant_system.research.embedding_onnx import (
    MODEL_FILES,
    ModelFile,
    ModelSetupError,
    OnnxEmbedder,
    download_model,
    files_present,
    onnx_status,
)

BASE = "https://example.test/repo/resolve/abc/"


def make_files() -> tuple[dict[str, bytes], tuple[ModelFile, ...]]:
    blobs = {
        "onnx/model_quantized.onnx": b"graph-bytes" * 20,
        "onnx/model_quantized.onnx_data": bytes(range(256)) * 40,
        "tokenizer.json": b'{"tokenizer": true}' * 10,
    }
    files = tuple(
        ModelFile(path, len(data), hashlib.sha256(data).hexdigest()) for path, data in blobs.items()
    )
    return blobs, files


class FakeResponse:
    def __init__(self, data: bytes, status: int = 200, url: str = BASE + "x") -> None:
        self._buf = io.BytesIO(data)
        self.status = status
        self._url = url

    def read(self, count: int = -1) -> bytes:
        return self._buf.read(count)

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> bool:
        self._buf.close()
        return False


def serve(
    monkeypatch: pytest.MonkeyPatch,
    blobs: dict[str, bytes],
    *,
    honour_range: bool = True,
    corrupt: str | None = None,
    fail: Exception | None = None,
) -> list[tuple[str, dict[str, str]]]:
    """A pretend download site. Returns the list of requests it received."""
    seen: list[tuple[str, dict[str, str]]] = []

    def fake_open(url: str, headers: dict[str, str], timeout: float) -> FakeResponse:
        seen.append((url, dict(headers)))
        if fail is not None:
            raise fail
        path = url.removeprefix(BASE)
        data = blobs[path]
        if path == corrupt:
            data = b"X" + data[1:]
        range_header = headers.get("Range")
        if range_header and honour_range:
            start = int(re.match(r"bytes=(\d+)-", range_header).group(1))  # type: ignore[union-attr]
            return FakeResponse(data[start:], status=206, url=url)
        return FakeResponse(data, status=200, url=url)

    monkeypatch.setattr(embedding_onnx, "_open", fake_open)
    return seen


# ----------------------------------------------------------------------------- the pins


def test_the_pinned_files_are_the_ones_checked_against_hugging_face() -> None:
    assert embedding_onnx.REPOSITORY == "onnx-community/embeddinggemma-2-ONNX"
    assert re.fullmatch(
        r"[0-9a-f]{40}", embedding_onnx.REVISION
    )  # one exact revision, never "main"
    assert embedding_onnx.REVISION in embedding_onnx.BASE_URL
    assert embedding_onnx.BASE_URL.startswith("https://huggingface.co/")
    assert [f.path for f in MODEL_FILES] == [
        "onnx/model_quantized.onnx",
        "onnx/model_quantized.onnx_data",
        "tokenizer.json",
    ]
    assert all(re.fullmatch(r"[0-9a-f]{64}", f.sha256) for f in MODEL_FILES)
    assert embedding_onnx.TOTAL_BYTES == 495_165 + 313_724_928 + 32_170_510  # about 330 MB


def test_the_default_model_folder_is_inside_the_apps_own_data_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from quant_system.server.v2 import paths

    monkeypatch.delenv("QUANTOS_MODEL_DIR", raising=False)
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path))
    assert (
        embedding_onnx.default_model_dir()
        == tmp_path / "data" / "quantos2" / "models" / "embeddinggemma-2"
    )
    # the screens keep their files in paths.state_dir(); the two must agree or the model would be saved twice
    assert embedding_onnx.default_model_dir() == paths.state_dir() / "models" / "embeddinggemma-2"
    monkeypatch.setenv("QUANTOS_MODEL_DIR", str(tmp_path / "elsewhere"))
    assert embedding_onnx.default_model_dir() == tmp_path / "elsewhere"


# ----------------------------------------------------------------------------- status


def test_status_needs_the_runtime_then_the_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    monkeypatch.setattr(embedding_onnx, "MODEL_FILES", files)
    assert onnx_status(tmp_path) == "NEEDS_DOWNLOAD"
    serve(monkeypatch, blobs)
    download_model(tmp_path, files=files, base_url=BASE, revision=embedding_onnx.REVISION)
    assert onnx_status(tmp_path) == "READY"
    with monkeypatch.context() as patched:
        patched.setattr(embedding_onnx.importlib.util, "find_spec", lambda name, *a: None)
        assert onnx_status(tmp_path) == "NOT_INSTALLED"


def test_a_folder_without_the_verified_marker_or_with_a_wrong_size_is_not_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    serve(monkeypatch, blobs)
    download_model(tmp_path, files=files, base_url=BASE)
    assert files_present(tmp_path, files)
    (tmp_path / ".verified").unlink()
    assert not files_present(tmp_path, files)
    (tmp_path / ".verified").write_text(embedding_onnx.REVISION, encoding="utf-8")
    assert files_present(tmp_path, files)
    (tmp_path / "tokenizer.json").write_bytes(b"short")
    assert not files_present(tmp_path, files)


# ----------------------------------------------------------------------------- the download


def test_a_download_saves_verifies_and_reports_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    seen = serve(monkeypatch, blobs)
    steps: list[tuple[int, int]] = []
    download_model(
        tmp_path,
        files=files,
        base_url=BASE,
        progress=lambda done, total: steps.append((done, total)),
    )

    for path, data in blobs.items():
        assert (tmp_path / path).read_bytes() == data
    assert (tmp_path / ".verified").read_text(encoding="utf-8") == embedding_onnx.REVISION
    total = sum(len(d) for d in blobs.values())
    assert steps and steps[-1] == (total, total)
    assert [done for done, _ in steps] == sorted(done for done, _ in steps)  # never goes backwards
    assert {url for url, _ in seen} == {BASE + path for path in blobs}
    assert not list(tmp_path.rglob("*.part"))


def test_files_already_on_the_computer_are_not_downloaded_again(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    serve(monkeypatch, blobs)
    download_model(tmp_path, files=files, base_url=BASE)
    seen = serve(monkeypatch, blobs)
    download_model(tmp_path, files=files, base_url=BASE)
    assert seen == []


def test_an_interrupted_download_resumes_where_it_stopped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    big = "onnx/model_quantized.onnx_data"
    part = tmp_path / (big + ".part")
    part.parent.mkdir(parents=True)
    part.write_bytes(blobs[big][:3000])
    seen = serve(monkeypatch, blobs)
    download_model(tmp_path, files=files, base_url=BASE)
    big_request = next(headers for url, headers in seen if url.endswith(big))
    assert big_request["Range"] == "bytes=3000-"
    assert (tmp_path / big).read_bytes() == blobs[big]


def test_a_server_that_ignores_the_resume_request_still_gives_a_correct_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    big = "onnx/model_quantized.onnx_data"
    part = tmp_path / (big + ".part")
    part.parent.mkdir(parents=True)
    part.write_bytes(blobs[big][:3000])
    serve(monkeypatch, blobs, honour_range=False)
    download_model(tmp_path, files=files, base_url=BASE)
    assert (tmp_path / big).read_bytes() == blobs[big]


def test_a_damaged_download_is_deleted_and_never_marked_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    serve(monkeypatch, blobs, corrupt="tokenizer.json")
    with pytest.raises(ModelSetupError) as caught:
        download_model(tmp_path, files=files, base_url=BASE)
    assert caught.value.code == "CHECKSUM_MISMATCH"
    assert "damaged" in caught.value.message
    assert not (tmp_path / "tokenizer.json").exists()
    assert not list(tmp_path.rglob("*.part"))
    assert not (tmp_path / ".verified").exists()
    assert not files_present(tmp_path, files)


def test_no_internet_says_so_in_plain_words(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    serve(monkeypatch, blobs, fail=urllib.error.URLError("offline"))
    with pytest.raises(ModelSetupError) as caught:
        download_model(tmp_path, files=files, base_url=BASE)
    assert caught.value.code == "NO_INTERNET"
    assert "internet connection" in caught.value.message


def test_a_refusal_from_the_download_site_names_the_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    error = urllib.error.HTTPError(BASE, 403, "Forbidden", {}, None)  # type: ignore[arg-type]
    serve(monkeypatch, blobs, fail=error)
    with pytest.raises(ModelSetupError) as caught:
        download_model(tmp_path, files=files, base_url=BASE)
    assert caught.value.code == "DOWNLOAD_REFUSED" and "403" in caught.value.message


def test_cancelling_stops_the_download_and_keeps_the_part_to_resume(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    monkeypatch.setattr(embedding_onnx, "CHUNK_BYTES", 1000)
    serve(monkeypatch, blobs)
    calls = {"n": 0}

    def cancelled() -> bool:
        calls["n"] += 1
        return calls["n"] > 4

    with pytest.raises(ModelSetupError) as caught:
        download_model(tmp_path, files=files, base_url=BASE, cancelled=cancelled)
    assert caught.value.code == "CANCELLED"
    assert not (tmp_path / ".verified").exists()
    # starting again finishes the job from what is there
    serve(monkeypatch, blobs)
    download_model(tmp_path, files=files, base_url=BASE)
    assert files_present(tmp_path, files)


def test_not_enough_disk_space_stops_before_anything_is_downloaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    seen = serve(monkeypatch, blobs)
    usage = namedtuple("usage", "total used free")  # noqa: PYI024
    monkeypatch.setattr(shutil, "disk_usage", lambda path: usage(10, 10, 0))
    with pytest.raises(ModelSetupError) as caught:
        download_model(tmp_path, files=files, base_url=BASE)
    assert caught.value.code == "NOT_ENOUGH_SPACE" and "free disk space" in caught.value.message
    assert seen == []


def test_an_address_that_is_not_secure_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    seen = serve(monkeypatch, blobs)
    with pytest.raises(ModelSetupError) as caught:
        download_model(tmp_path, files=files, base_url="http://example.test/")
    assert caught.value.code == "DOWNLOAD_REFUSED" and seen == []


def test_a_redirect_to_an_insecure_address_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blobs, files = make_files()
    monkeypatch.setattr(
        embedding_onnx,
        "_open",
        lambda url, headers, timeout: FakeResponse(b"x", url="http://evil.test/x"),
    )
    with pytest.raises(ModelSetupError) as caught:
        download_model(tmp_path, files=files, base_url=BASE)
    assert caught.value.code == "DOWNLOAD_REFUSED"


def test_the_messages_a_person_reads_have_no_developer_words() -> None:
    codes = (
        "NO_INTERNET",
        "DOWNLOAD_REFUSED",
        "CHECKSUM_MISMATCH",
        "NOT_ENOUGH_SPACE",
        "CANCELLED",
        "CANNOT_WRITE",
    )
    source = Path(embedding_onnx.__file__).read_text(encoding="utf-8")
    for code in codes:
        assert code in source
    messages = re.findall(r'"((?:[A-Z][^"\n]{20,}))"', source)
    people_text = [
        m for m in messages if " " in m and not m.startswith(("Opens", "Every", "Where"))
    ]
    for text in people_text:
        assert not re.search(
            r"\b(API|JSON|ONNX|SHA|checksum|endpoint|schema|CLI|terminal)\b", text, re.I
        ), text


# ----------------------------------------------------------------------------- the embedder (pretend runtime)


class FakeTokens:
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids


def install_fake_runtime(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Pretend onnxruntime and tokenizers. The returned list collects every batch the model was run on."""
    batches: list[dict[str, Any]] = []

    class FakeInput:
        def __init__(self, name: str, shape: list[Any]) -> None:
            self.name = name
            self.shape = shape

    class FakeSession:
        def __init__(self, path: str, options: Any, providers: list[str]) -> None:
            self.path, self.providers = path, providers

        def get_inputs(self) -> list[FakeInput]:
            return [
                FakeInput("input_ids", ["batch", "seq"]),
                FakeInput("attention_mask", ["batch", "seq"]),
                FakeInput("image_features", ["n", 512]),
                FakeInput("video_features", ["n", 512]),
                FakeInput("audio_features", ["n", 512]),
            ]

        def run(self, outputs: list[str], feeds: dict[str, Any]) -> list[Any]:
            batches.append(feeds)
            ids, mask = feeds["input_ids"], feeds["attention_mask"]
            rows = []
            for row_ids, row_mask in zip(ids, mask, strict=True):
                total = float(sum(int(i) for i, m in zip(row_ids, row_mask, strict=True) if m))
                vec = np.array(
                    [total % 7 + 1.0, len(row_ids[row_mask == 1]) + 0.5] + [1.0] * 766,
                    dtype=np.float32,
                )
                rows.append(vec / np.linalg.norm(vec))
            return [np.stack(rows)]

    class FakeTokenizer:
        truncation: int | None = None

        @classmethod
        def from_file(cls, path: str) -> FakeTokenizer:
            return cls()

        def enable_truncation(self, max_length: int) -> None:
            self.truncation = max_length

        def token_to_id(self, token: str) -> int | None:
            return 0 if token == "<pad>" else None

        def encode(self, text: str) -> FakeTokens:
            return FakeTokens([ord(c) % 50 + 1 for c in text][: self.truncation or 10**9])

    fake_ort = type(
        "ort",
        (),
        {
            "SessionOptions": type("Opt", (), {"intra_op_num_threads": 0}),
            "InferenceSession": FakeSession,
        },
    )
    fake_tokenizers = type("tk", (), {"Tokenizer": FakeTokenizer})
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None) -> Any:
        if name == "onnxruntime":
            return fake_ort
        if name == "tokenizers":
            return fake_tokenizers
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    return batches


def test_the_embedder_returns_one_unit_vector_per_text_in_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    batches = install_fake_runtime(monkeypatch)
    embedder = OnnxEmbedder(tmp_path)
    texts = ["a much longer sentence about the market", "short", "medium length text", ""]
    vectors = embedder.embed(texts)
    assert len(vectors) == 4 and all(len(v) == 768 for v in vectors)
    assert all(math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-4) for v in vectors)
    # the same text on its own gives the same vector as inside a batch, so ordering and padding do not change answers
    alone = embedder.embed(["short"])[0]
    assert alone == pytest.approx(vectors[1], abs=1e-6)
    assert embedder.embed([]) == []
    assert batches


def test_the_image_video_and_audio_inputs_are_fed_as_empty_arrays(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    batches = install_fake_runtime(monkeypatch)
    OnnxEmbedder(tmp_path).embed(["hello"])
    feeds = batches[0]
    for name in ("image_features", "video_features", "audio_features"):
        assert feeds[name].shape == (0, 512) and feeds[name].dtype == np.float32
    assert feeds["input_ids"].dtype == np.int64 and feeds["attention_mask"].dtype == np.int64


def test_long_texts_are_batched_apart_so_memory_stays_bounded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    batches = install_fake_runtime(monkeypatch)
    monkeypatch.setattr(embedding_onnx, "TOKEN_BUDGET", 100)
    OnnxEmbedder(tmp_path).embed(["x" * 60, "y" * 60, "z" * 5, "w" * 5])
    shapes = sorted(b["input_ids"].shape for b in batches)
    assert all(rows * width <= 100 or rows == 1 for rows, width in shapes)
    assert sum(rows for rows, _ in shapes) == 4


def test_input_longer_than_the_models_limit_is_cut_not_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    batches = install_fake_runtime(monkeypatch)
    OnnxEmbedder(tmp_path).embed(["q" * 20_000])
    assert batches[0]["input_ids"].shape[1] == embedding_onnx.MAX_TOKENS


# ----------------------------------------------------------------------------- the real model, when it is here


@pytest.mark.skipif(
    not os.environ.get("QUANTOS_TEST_MODEL_DIR"),
    reason="set QUANTOS_TEST_MODEL_DIR to a folder holding the downloaded model to run this against the real thing",
)
def test_the_real_model_gives_meaningful_unit_vectors() -> None:
    embedder = OnnxEmbedder(Path(os.environ["QUANTOS_TEST_MODEL_DIR"]))
    docs = [
        "title: none | text: Deflated Sharpe ratio corrects for multiple testing and backtest overfitting.",
        "title: none | text: Zakat is calculated at 2.5 percent of eligible wealth held for a lunar year.",
        "title: none | text: Limit order book depth and the bid-ask spread determine market impact.",
    ]
    query = "task: search result | query: How do I avoid overfitting a backtest when I try many strategies?"
    vectors = embedder.embed([query, *docs])
    assert all(len(v) == 768 for v in vectors)
    assert all(math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-3) for v in vectors)
    scores = [sum(a * b for a, b in zip(vectors[0], d, strict=True)) for d in vectors[1:]]
    assert scores.index(max(scores)) == 0 and max(scores) > 0.7
    batch_vs_single = embedder.embed([docs[1]])[0]
    assert sum(a * b for a, b in zip(batch_vs_single, vectors[2], strict=True)) > 0.999
