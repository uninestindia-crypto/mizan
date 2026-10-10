"""What the Research screen runs on: the paper library, the search, and the one-click set-up of EmbeddingGemma 2.

A person asks a question in plain words and gets the research papers closest to it. The matching uses EmbeddingGemma 2 once it has
been downloaded (one click, about 330 MB, kept inside the app's own folder) and says so; until then it uses the built-in keyword
matching and says that instead. Papers found on arXiv are saved on this computer so they are there next time.

Nothing here needs a terminal, a file edit or a setting. Every message a person can read is a plain sentence.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from quant_system.research import embedding_onnx
from quant_system.research.arxiv_client import ArxivClient, PaperMetadata
from quant_system.research.embedding_gemma import EmbeddingGemmaProvider, real_model_status
from quant_system.research.rag_engine import QuantPaperRAG

logger = logging.getLogger(__name__)

ARXIV_URL = "https://export.arxiv.org/api/query"
ARXIV_FIELDS = (
    "q-fin.CP",
    "q-fin.GN",
    "q-fin.MF",
    "q-fin.PM",
    "q-fin.PR",
    "q-fin.RM",
    "q-fin.ST",
    "q-fin.TR",
)
FIELD_NAMES = {
    "q-fin.CP": "Computational finance",
    "q-fin.EC": "Economics",
    "q-fin.GN": "General finance",
    "q-fin.MF": "Mathematical finance",
    "q-fin.PM": "Portfolio management",
    "q-fin.PR": "Pricing of securities",
    "q-fin.RM": "Risk management",
    "q-fin.ST": "Statistical finance",
    "q-fin.TR": "Trading and market structure",
}
MAX_SAVED_PAPERS = 300
MAX_AUTHORS_SHOWN = 6
QUESTION_LIMIT = 500


class ResearchError(Exception):
    """A problem with a sentence a person can read, and the status code the screen should get."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def build_arxiv_query(question: str) -> str | None:
    """Turns a plain question into an arXiv search limited to the finance sections, or None when it has no usable words."""
    terms: list[str] = []
    for word in QuantPaperRAG.tokenize(question):
        if word.isalpha() and len(word) > 2 and word not in terms:
            terms.append(word)
    if not terms:
        return None
    words = " OR ".join(f"all:{word}" for word in terms[:6])
    fields = " OR ".join(f"cat:{field}" for field in ARXIV_FIELDS)
    return f"({words}) AND ({fields})"


def fetch_arxiv(query: str, max_results: int = 5) -> list[PaperMetadata]:
    """Asks arXiv for papers. Unlike ``ArxivClient.search_papers`` it says when it could not reach the site."""
    client = ArxivClient()
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
    )
    request = urllib.request.Request(  # noqa: S310 - https address fixed above
        f"{ARXIV_URL}?{params}", headers={"User-Agent": "QuantOS-Research/1.0"}, method="GET"
    )
    client._enforce_rate_limit()  # arXiv asks for one request every three seconds
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return client.parse_atom_feed(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, TimeoutError) as err:
        raise ResearchError(
            503,
            "NO_INTERNET",
            "Could not reach arXiv. Check your internet connection. Your saved papers still work.",
        ) from err
    except Exception as err:  # a reply that is not a paper list
        raise ResearchError(
            502, "ARXIV_REPLY", "arXiv sent a reply QuantOS could not read. Try again later."
        ) from err


def _paper_to_dict(paper: PaperMetadata) -> dict[str, Any]:
    return {
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "summary": paper.summary,
        "authors": list(paper.authors),
        "published": paper.published.isoformat(),
        "pdf_url": paper.pdf_url,
        "primary_category": paper.primary_category,
        "doi": paper.doi,
    }


def _paper_from_dict(item: Any) -> PaperMetadata | None:
    try:
        return PaperMetadata(
            arxiv_id=str(item["arxiv_id"]),
            title=str(item["title"]),
            summary=str(item["summary"]),
            authors=[str(a) for a in item.get("authors", [])],
            published=datetime.fromisoformat(str(item["published"])),
            pdf_url=str(item.get("pdf_url", "")),
            primary_category=str(item.get("primary_category", "q-fin.ST")),
            doi=item.get("doi"),
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def paper_view(paper: PaperMetadata, score: float) -> dict[str, Any]:
    """One paper as the screen shows it."""
    shown = list(paper.authors[:MAX_AUTHORS_SHOWN])
    return {
        "id": paper.arxiv_id,
        "title": paper.title,
        "authors": shown,
        "more_authors": max(0, len(paper.authors) - len(shown)),
        "year": paper.published.year,
        "field": FIELD_NAMES.get(paper.primary_category, "Finance research"),
        "summary": paper.summary,
        "link": paper.pdf_url,
        "match_percent": max(0, min(100, round(score * 100))),
    }


class ResearchService:
    """One per running app. Safe to call from several requests at once."""

    def __init__(
        self,
        model_dir: Path,
        library_file: Path,
        *,
        downloader: Callable[..., None] = embedding_onnx.download_model,
        fetcher: Callable[[str, int], list[PaperMetadata]] = fetch_arxiv,
        provider_factory: Callable[[Path], EmbeddingGemmaProvider] | None = None,
    ) -> None:
        self.model_dir = model_dir
        self.library_file = library_file
        self._downloader = downloader
        self._fetcher = fetcher
        self._provider_factory = provider_factory or (
            lambda directory: EmbeddingGemmaProvider(mode="auto", model_dir=directory)
        )
        self._lock = threading.RLock()
        self._rag: QuantPaperRAG | None = None
        self._provider: EmbeddingGemmaProvider | None = None
        self._state_lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._setup: dict[str, Any] = self._idle()

    # ------------------------------------------------------------------ the library

    def _load_saved(self) -> list[PaperMetadata]:
        try:
            raw = json.loads(self.library_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        papers = [_paper_from_dict(item) for item in raw] if isinstance(raw, list) else []
        return [paper for paper in papers if paper is not None]

    def _save(self, papers: list[PaperMetadata]) -> None:
        try:
            self.library_file.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps([_paper_to_dict(p) for p in papers[-MAX_SAVED_PAPERS:]], indent=1)
            temporary = self.library_file.with_suffix(".tmp")
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(self.library_file)
        except OSError:
            logger.warning("Could not save the research library", exc_info=True)

    def _engine(self) -> QuantPaperRAG:
        with self._lock:
            if self._rag is None:
                provider = self._provider_factory(self.model_dir)
                rag = QuantPaperRAG(embedding_provider=provider)
                saved = self._load_saved()
                if saved:
                    rag.index_papers(saved)
                self._provider, self._rag = provider, rag
            return self._rag

    def _reset_engine(self) -> None:
        with self._lock:
            self._rag = None
            self._provider = None

    # ------------------------------------------------------------------ status

    def status(self) -> dict[str, Any]:
        state = real_model_status(model_dir=self.model_dir)
        with self._lock:
            provider, rag = self._provider, self._rag
            if provider is not None:
                label, by_meaning = (
                    provider.label,
                    provider.uses_real_model or provider.active_backend in ("onnx", "transformers"),
                )
            else:
                by_meaning = state == "READY"
                label = (
                    "EmbeddingGemma 2 (ready to use)"
                    if by_meaning
                    else "Built-in keyword matching (EmbeddingGemma 2 "
                    + (
                        "has not been downloaded yet)"
                        if state == "NEEDS_DOWNLOAD"
                        else "is not installed on this computer)"
                    )
                )
            papers = (
                len(rag.papers)
                if rag is not None
                else len(ArxivClient.get_curated_institutional_library()) + len(self._load_saved())
            )
        return {
            "engine": {
                "state": state,
                "by_meaning": by_meaning,
                "label": label,
                "download_mb": round(embedding_onnx.TOTAL_BYTES / 1024 / 1024),
            },
            "library": {"papers": papers},
            "setup": self.setup_snapshot(),
        }

    # ------------------------------------------------------------------ search

    def search(self, question: str, top_k: int = 5, online: bool = False) -> dict[str, Any]:
        text = question.strip()
        if not text:
            raise ResearchError(
                422,
                "EMPTY_QUESTION",
                "Type a question first, for example: how do I avoid overfitting a backtest?",
            )
        if len(text) > QUESTION_LIMIT:
            raise ResearchError(
                422,
                "QUESTION_TOO_LONG",
                f"Shorten the question to {QUESTION_LIMIT} letters or fewer.",
            )
        notes: list[str] = []
        with self._lock:
            rag = self._engine()
            if online:
                notes.append(self._add_from_arxiv(rag, text))
            result = rag.query(text, top_k=max(1, min(10, top_k)))
            provider = self._provider
            by_meaning = bool(provider and provider.uses_real_model)
            label = provider.label if provider else ""
            papers = len(rag.papers)
        return {
            "question": text,
            "results": [paper_view(paper, score) for paper, score in result.top_papers],
            "engine": {"by_meaning": by_meaning, "label": label},
            "library": {"papers": papers},
            "notes": [note for note in notes if note],
        }

    def _add_from_arxiv(self, rag: QuantPaperRAG, question: str) -> str:
        query = build_arxiv_query(question)
        if query is None:
            return "Add a few more words to look for new papers online."
        try:
            found = self._fetcher(query, 5)
        except ResearchError as err:
            return err.message
        have = {paper.arxiv_id for paper in rag.papers}
        new = [paper for paper in found if paper.arxiv_id not in have]
        if not new:
            return "arXiv had no new papers for this question."
        rag.index_papers(new)
        saved = self._load_saved()
        known = {paper.arxiv_id for paper in saved}
        self._save(saved + [paper for paper in new if paper.arxiv_id not in known])
        count = len(new)
        return f"Added {count} new paper{'s' if count != 1 else ''} from arXiv to your library."

    # ------------------------------------------------------------------ set-up

    @staticmethod
    def _idle() -> dict[str, Any]:
        return {
            "state": "IDLE",
            "percent": 0,
            "mb_done": 0.0,
            "mb_total": round(embedding_onnx.TOTAL_BYTES / 1048576, 1),
            "message": "",
            "error": None,
        }

    def setup_snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                **self._setup,
                "error": dict(self._setup["error"]) if self._setup["error"] else None,
            }

    def _set(self, **changes: Any) -> None:
        with self._state_lock:
            self._setup.update(changes)

    def _on_progress(self, done: int, total: int) -> None:
        self._set(
            state="DOWNLOADING",
            percent=int(done * 100 / total) if total else 0,
            mb_done=round(done / 1048576, 1),
            mb_total=round(total / 1048576, 1),
            message=f"Downloading EmbeddingGemma 2: {round(done / 1048576)} of {round(total / 1048576)} MB",
        )

    def start_setup(self) -> dict[str, Any]:
        """Starts the one-time download in the background. Asking again while it runs changes nothing."""
        with self._state_lock:
            running = self._thread is not None and self._thread.is_alive()
        if running:
            return self.setup_snapshot()
        if real_model_status(model_dir=self.model_dir) == "READY":
            self._set(
                **{
                    **self._idle(),
                    "state": "DONE",
                    "percent": 100,
                    "message": "EmbeddingGemma 2 is ready.",
                }
            )
            return self.setup_snapshot()
        if not embedding_onnx.runtime_available():
            raise ResearchError(
                409,
                "NOT_AVAILABLE",
                "Smarter search is not available in this copy of QuantOS. Search keeps working with the built-in keyword matching.",
            )
        self._cancel.clear()
        self._set(**{**self._idle(), "state": "DOWNLOADING", "message": "Starting the download..."})
        thread = threading.Thread(target=self._run_setup, name="research-setup", daemon=True)
        with self._state_lock:
            self._thread = thread
        started = (
            self.setup_snapshot()
        )  # the state at the moment of starting; the screen then follows it through status
        thread.start()
        return started

    def cancel_setup(self) -> dict[str, Any]:
        self._cancel.set()
        return self.setup_snapshot()

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def _run_setup(self) -> None:
        try:
            self._downloader(
                self.model_dir, progress=self._on_progress, cancelled=self._cancel.is_set
            )
            self._set(
                state="PREPARING", percent=100, message="Getting the research library ready..."
            )
            self._reset_engine()
            self._engine()  # reads the model and the papers once now, so the first search is quick
            provider = self._provider
            if provider is None or not provider.uses_real_model:
                # Downloaded but could not start (damaged file, not enough memory...): never announce "ready" for that.
                logger.warning(
                    "Downloaded model did not start: %s",
                    provider and provider.get_stats().fallback_reason,
                )
                message = (
                    "EmbeddingGemma 2 was downloaded but could not start on this computer. "
                    "Search keeps working with the built-in keyword matching."
                )
                self._set(
                    state="FAILED",
                    message=message,
                    error={"code": "ENGINE_START_FAILED", "message": message},
                )
                return
            self._set(
                state="DONE",
                percent=100,
                message="EmbeddingGemma 2 is ready. Search now matches by meaning.",
            )
        except embedding_onnx.ModelSetupError as err:
            if err.code == "CANCELLED":
                self._set(state="CANCELLED", message=err.message, error=None)
            else:
                self._set(
                    state="FAILED",
                    message=err.message,
                    error={"code": err.code, "message": err.message},
                )
        except Exception:
            logger.exception("Research set-up failed")
            message = "Something went wrong while turning on smarter search. Search still works with keyword matching. Try again."
            self._set(
                state="FAILED", message=message, error={"code": "SETUP_FAILED", "message": message}
            )
