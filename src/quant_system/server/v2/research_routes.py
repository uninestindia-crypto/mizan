"""``/api/v2/research``: find finance research papers by meaning, and turn on EmbeddingGemma 2 from inside the app.

Nothing here asks a person to open a terminal, edit a file or set anything. Turning on smarter search is one button that downloads the
model once into the app's own folder; searching works before and after, and the answer always says which kind of matching was used.

Like ``broker_routes.py`` this module imports nothing from ``router.py`` at the top of the file, so ``router.py`` can wire it in
without a cycle: ``V2Error`` is fetched inside the function that needs it.
"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from quant_system.research.research_service import ResearchError, ResearchService
from quant_system.server.v2 import paths

router = APIRouter(prefix="/research", tags=["Research"])

_service: ResearchService | None = None
_service_lock = threading.Lock()


class SearchBody(BaseModel):
    question: str
    top_k: int = 5
    online: bool = False


def service() -> ResearchService:
    """The one research service for this running app, made the first time it is needed."""
    global _service
    with _service_lock:
        if _service is None:
            base = paths.state_dir()
            _service = ResearchService(
                model_dir=base / "models" / "embeddinggemma-2",
                library_file=base / "research" / "papers.json",
            )
        return _service


def set_service(value: ResearchService | None) -> None:
    """Replaces the service. Used by tests and never by the app."""
    global _service
    with _service_lock:
        _service = value


def _plain(err: ResearchError) -> Exception:
    from quant_system.server.v2.router import V2Error

    return V2Error(err.status, err.code, err.message)


@router.get("/status")
def research_status() -> dict[str, Any]:
    """Which kind of matching is on, how many papers are in the library, and how the one-time set-up is going."""
    return service().status()


@router.post("/search")
def research_search(body: SearchBody) -> dict[str, Any]:
    """The papers closest in meaning to a question. ``online`` also looks for new papers on arXiv first."""
    try:
        return service().search(body.question, top_k=body.top_k, online=body.online)
    except ResearchError as err:
        raise _plain(err) from err


@router.post("/setup")
def research_setup() -> dict[str, Any]:
    """Starts the one-time download of EmbeddingGemma 2. Asking again while it runs changes nothing."""
    try:
        return service().start_setup()
    except ResearchError as err:
        raise _plain(err) from err


@router.post("/setup/cancel")
def research_setup_cancel() -> dict[str, Any]:
    """Stops the download. What was already downloaded is kept, so starting again carries on."""
    return service().cancel_setup()
