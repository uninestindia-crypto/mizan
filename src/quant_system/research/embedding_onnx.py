"""EmbeddingGemma 2 as a small downloadable model, so a person can turn it on from inside the app.

The torch route needs 1.5 GB of weights and 1.1 GB of libraries, which a factory-new laptop does not have. This route needs
``onnxruntime`` and ``tokenizers`` (both ship with the app) and one download of about 330 MB:

- ``onnx-community/embeddinggemma-2-ONNX`` at one pinned revision (Apache 2.0, no sign-in), the 8-bit text model and its tokenizer.
- Every file's size and SHA-256 is pinned below, copied from Hugging Face's own record and checked against the bytes measured on
  2026-10-10. A download that does not match is deleted, never used.
- Measured against the PyTorch float32 reference on 2026-10-10: cosine 0.99992 or better on documents, a query and a 1,300-token
  text, the same ranking (also at 256 dimensions), about 680 MB peak memory, about 0.2 to 0.3 s per short text on an 8-core ARM64 CPU.

The graph already does the pooling and the 512 to 768 projection and returns unit-length ``sentence_embedding`` rows. It also has
image, video and audio inputs, which a text-only caller feeds as empty arrays.
"""

from __future__ import annotations

import functools
import hashlib
import importlib
import importlib.util
import logging
import os
import shutil
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPOSITORY = "onnx-community/embeddinggemma-2-ONNX"
REVISION = "daa72c51243991dfcaf9f9137d2c573d8f7790c0"  # pragma: allowlist secret
BASE_URL = f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/"
GRAPH_FILE = "onnx/model_quantized.onnx"
MARKER_FILE = ".verified"
MAX_TOKENS = 8192
# Tokens in one batch (padded length times rows): bounds memory when several long texts arrive together.
TOKEN_BUDGET = 4096
CHUNK_BYTES = 1024 * 1024
SPACE_MARGIN_BYTES = 200 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ModelFile:
    path: str
    size: int
    sha256: str


MODEL_FILES: tuple[ModelFile, ...] = (
    ModelFile(
        "onnx/model_quantized.onnx",
        495_165,
        "d06edd601f851c633a2519304cbeb8dc6170d7ceb61b436625c17fb9b6e74953",  # pragma: allowlist secret
    ),
    ModelFile(
        "onnx/model_quantized.onnx_data",
        313_724_928,
        "278a7ff1248c3618e4bd11a607fc54f7bdc7778854230f3956d3f86bd9db4f3b",  # pragma: allowlist secret
    ),
    ModelFile(
        "tokenizer.json",
        32_170_510,
        "4d777ef5bdc1aa36227abdfb77c3e49e7b9c892d16e1b6bda41c393504828be4",  # pragma: allowlist secret
    ),
)
TOTAL_BYTES = sum(item.size for item in MODEL_FILES)


class ModelSetupError(Exception):
    """A download problem, with a sentence a person can read."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def default_model_dir() -> Path:
    """Where the model lives: inside the app's own data folder, so nothing is written elsewhere on the drive."""
    override = os.environ.get("QUANTOS_MODEL_DIR")
    if override:
        return Path(override)
    root = os.environ.get("QUANTOS_APP_ROOT")
    if root:
        base = Path(root)
    elif getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[3]
    return base / "data" / "quantos2" / "models" / "embeddinggemma-2"


@functools.lru_cache(maxsize=1)
def _runtime_importable() -> bool:
    try:
        importlib.import_module("onnxruntime")
        importlib.import_module("tokenizers")
    except (
        Exception
    ):  # a missing file, or a Windows runtime file the computer lacks, both mean "cannot run here"
        logger.warning("onnxruntime or tokenizers could not be loaded", exc_info=True)
        return False
    return True


def runtime_available() -> bool:
    """True when onnxruntime and tokenizers really load on this computer, so a download is never offered for a model that cannot start."""
    return _runtime_importable()


def files_present(model_dir: Path, files: Sequence[ModelFile] | None = None) -> bool:
    """Every model file exists at its pinned size and was verified when it was downloaded."""
    wanted = MODEL_FILES if files is None else tuple(files)
    marker = model_dir / MARKER_FILE
    try:
        if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != REVISION:
            return False
        return all(
            (model_dir / item.path).is_file()
            and (model_dir / item.path).stat().st_size == item.size
            for item in wanted
        )
    except OSError:
        return False


def onnx_status(model_dir: Path | None = None) -> str:
    """``READY``, ``NEEDS_DOWNLOAD`` (the runtime is here, the model is not) or ``NOT_INSTALLED`` (no runtime)."""
    if not runtime_available():
        return "NOT_INSTALLED"
    return "READY" if files_present(model_dir or default_model_dir()) else "NEEDS_DOWNLOAD"


# ----------------------------------------------------------------------------- download


def _open(url: str, headers: dict[str, str], timeout: float) -> Any:
    """Opens one address. A single seam so tests can stand in for the network."""
    request = urllib.request.Request(url, headers=headers)  # noqa: S310 - https only, checked by the caller
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _megabytes(count: int) -> int:
    return max(1, round(count / 1024 / 1024))


def download_model(
    model_dir: Path,
    *,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    files: Sequence[ModelFile] | None = None,
    base_url: str = BASE_URL,
    revision: str = REVISION,
) -> None:
    """Downloads and verifies the model into ``model_dir``. Safe to run again: finished files are kept, partial ones resume."""
    wanted = MODEL_FILES if files is None else tuple(files)
    total = sum(item.size for item in wanted)
    try:
        model_dir.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(model_dir).free
    except OSError as err:
        raise ModelSetupError(
            "CANNOT_WRITE",
            "QuantOS cannot save files in its data folder. Check that the drive is available.",
        ) from err
    already = sum(
        item_path.stat().st_size
        for item in wanted
        if (item_path := model_dir / item.path).is_file() and item_path.stat().st_size <= item.size
    )
    if free < max(0, total - already) + SPACE_MARGIN_BYTES:
        raise ModelSetupError(
            "NOT_ENOUGH_SPACE",
            f"There is not enough free disk space. The research engine needs about {_megabytes(total + SPACE_MARGIN_BYTES)} MB.",
        )
    marker = model_dir / MARKER_FILE
    marker.unlink(missing_ok=True)  # not ready again until every file has been verified

    done = 0
    for item in wanted:
        target = model_dir / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        if (
            target.is_file()
            and target.stat().st_size == item.size
            and _sha256_of(target) == item.sha256
        ):
            done += item.size
            if progress:
                progress(done, total)
            continue
        target.unlink(missing_ok=True)
        _fetch_one(item, target, base_url, done, total, progress, cancelled)
        done += item.size
    marker.write_text(revision, encoding="utf-8")


def _fetch_one(
    item: ModelFile,
    target: Path,
    base_url: str,
    done_before: int,
    total: int,
    progress: Callable[[int, int], None] | None,
    cancelled: Callable[[], bool] | None,
) -> None:
    part = target.with_name(target.name + ".part")
    url = base_url + item.path
    if not url.startswith("https://"):
        raise ModelSetupError(
            "DOWNLOAD_REFUSED", "The download address is not secure, so QuantOS will not use it."
        )
    start = part.stat().st_size if part.is_file() else 0
    if start > item.size:
        part.unlink()
        start = 0
    headers = {"User-Agent": "QuantOS"}
    if start:
        headers["Range"] = f"bytes={start}-"
    try:
        response = _open(url, headers, 30.0)
    except urllib.error.HTTPError as err:
        if err.code == 416:  # the partial file is already complete or stale: start again
            part.unlink(missing_ok=True)
            raise ModelSetupError(
                "DOWNLOAD_FAILED", "The download was interrupted. Try again."
            ) from err
        raise ModelSetupError(
            "DOWNLOAD_REFUSED",
            f"The download site refused the request (code {err.code}). Try again later.",
        ) from err
    except (TimeoutError, urllib.error.URLError, OSError) as err:
        raise ModelSetupError(
            "NO_INTERNET",
            "Could not reach the download site. Check your internet connection and try again.",
        ) from err
    try:
        with response:
            if not str(response.geturl()).startswith("https://"):
                raise ModelSetupError(
                    "DOWNLOAD_REFUSED",
                    "The download moved to an address that is not secure, so QuantOS stopped.",
                )
            if start and getattr(response, "status", 200) != 206:
                start = 0  # the server ignored the range: take the whole file again
            mode = "ab" if start else "wb"
            received = start
            with part.open(mode) as out:
                while True:
                    if cancelled and cancelled():
                        raise ModelSetupError(
                            "CANCELLED", "The download was cancelled. You can start it again later."
                        )
                    block = response.read(CHUNK_BYTES)
                    if not block:
                        break
                    out.write(block)
                    received += len(block)
                    if progress:
                        progress(done_before + min(received, item.size), total)
    except ModelSetupError:
        raise
    except (TimeoutError, urllib.error.URLError, OSError) as err:
        raise ModelSetupError(
            "NO_INTERNET",
            "The connection was lost during the download. Check your internet and try again.",
        ) from err
    if part.stat().st_size != item.size or _sha256_of(part) != item.sha256:
        part.unlink(missing_ok=True)
        raise ModelSetupError(
            "CHECKSUM_MISMATCH", "The download was damaged and has been deleted. Please try again."
        )
    part.replace(target)


# ----------------------------------------------------------------------------- running the model


class OnnxEmbedder:
    """Turns texts into 768 unit-length numbers with the downloaded 8-bit EmbeddingGemma 2."""

    def __init__(self, model_dir: Path, *, threads: int | None = None) -> None:
        self.model_dir = model_dir
        self._threads = threads or os.cpu_count() or 4
        self._session: Any = None
        self._tokenizer: Any = None
        self._pad_id = 0
        self._lock = threading.Lock()

    def _load(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            ort = importlib.import_module("onnxruntime")
            tokenizers = importlib.import_module("tokenizers")
            options = ort.SessionOptions()
            options.intra_op_num_threads = self._threads
            session = ort.InferenceSession(
                str(self.model_dir / GRAPH_FILE), options, providers=["CPUExecutionProvider"]
            )
            tokenizer = tokenizers.Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
            tokenizer.enable_truncation(max_length=MAX_TOKENS)
            pad = tokenizer.token_to_id("<pad>")
            self._pad_id = int(pad) if pad is not None else 0
            self._tokenizer = tokenizer
            self._session = session

    def _extra_inputs(self) -> dict[str, Any]:
        """Empty arrays for the image, video and audio inputs the text-only caller does not use."""
        numpy = importlib.import_module("numpy")
        extra: dict[str, Any] = {}
        for item in self._session.get_inputs():
            if item.name in ("input_ids", "attention_mask"):
                continue
            width = item.shape[-1] if isinstance(item.shape[-1], int) else 512
            extra[item.name] = numpy.zeros((0, width), dtype=numpy.float32)
        return extra

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One unit-length vector per text, in the order given."""
        if not texts:
            return []
        self._load()
        numpy = importlib.import_module("numpy")
        encodings = [self._tokenizer.encode(text) for text in texts]
        order = sorted(range(len(encodings)), key=lambda index: len(encodings[index].ids))
        extra = self._extra_inputs()
        results: list[list[float]] = [[] for _ in texts]
        batch: list[int] = []
        longest = 0

        def run(indices: list[int], width: int) -> None:
            ids = numpy.full((len(indices), width), self._pad_id, dtype=numpy.int64)
            mask = numpy.zeros((len(indices), width), dtype=numpy.int64)
            for row, index in enumerate(indices):
                tokens = encodings[index].ids
                ids[row, : len(tokens)] = tokens
                mask[row, : len(tokens)] = 1
            feeds = {"input_ids": ids, "attention_mask": mask, **extra}
            rows = self._session.run(["sentence_embedding"], feeds)[0]
            for row, index in enumerate(indices):
                results[index] = [float(value) for value in rows[row]]

        for index in order:
            size = len(encodings[index].ids)
            if batch and (len(batch) + 1) * max(longest, size) > TOKEN_BUDGET:
                run(batch, longest)
                batch, longest = [], 0
            batch.append(index)
            longest = max(longest, size)
        if batch:
            run(batch, longest)
        return results
