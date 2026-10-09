"""Connects the Shariah proof service to the app's own files and data.

It decides where this computer keeps the filings it fetched, finds the filings bundled with the program, hands the
service the market data already loaded in the app, and says which stocks the person follows. Nothing here reads the
network; the live NSE reader is built only when a person starts a fetch.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_system.server.v2 import paths
from quant_system.shariah.filings.nse_client import NseFilingsClient
from quant_system.shariah.filings.service import LiveSource
from quant_system.shariah.filings.store import FilingsStore
from quant_system.shariah.services.filing_jobs import FilingJobs, FilingsSource
from quant_system.shariah.services.proof_market import PriceHistory
from quant_system.shariah.services.proof_paths import bundled_snapshot_path
from quant_system.shariah.services.proof_runtime import ProofRuntime
from quant_system.shariah.services.proof_samples import SampleRows
from quant_system.shariah.services.proof_service import ProofService

__all__ = ["proof_runtime", "reset_proof_runtime", "tracked_symbols"]

USER_FILINGS_FILE = "shariah_filings.sqlite"
_lock = threading.Lock()
_runtime: ProofRuntime | None = None
_client: NseFilingsClient | None = None


class _AppBars:
    """The market index the app has loaded, looked up at the moment a price is needed."""

    def bars(self, symbol: str, start: str | None = None, end: str | None = None) -> PriceHistory:
        from quant_system.server.v2.router import services

        return services().index.bars(symbol, start, end)

    def version(self) -> str:
        """Names the price data now loaded, so a proof worked out before a download is worked out again after it."""
        from quant_system.server.v2.router import services

        current = services().index.current_path()
        try:
            seen = current.stat() if current else None
        except OSError:
            return "none"
        # The size joins the time: Windows can give two writes in quick succession the same time stamp.
        return f"{current.name}:{seen.st_mtime_ns}:{seen.st_size}" if current and seen else "none"


def _sample_path() -> Path:
    from quant_system.shariah.core.config import settings

    return Path(settings.SQLITE_DB_PATH)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _live_source() -> FilingsSource:
    """The reader of NSE's filings. One client is kept, so its pause between requests holds across jobs."""
    global _client
    if _client is None:
        _client = NseFilingsClient()
    return LiveSource(_client)


def _paper_symbols(books: list[dict[str, Any]]) -> Iterator[str]:
    for book in books:
        listed = book["spec"].get("symbols")
        yield from (str(s) for s in listed) if isinstance(listed, list) else ()


def tracked_symbols() -> list[str]:
    """The stocks the person follows: the watchlist, the holdings and the stocks named in paper books."""
    from quant_system.server.v2.router import services

    state = services().state
    held = (holding.symbol for holding in state.holdings())
    every = [*state.watchlist(), *held, *_paper_symbols(state.paper_books())]
    return list(dict.fromkeys(symbol.strip().upper() for symbol in every if symbol.strip()))


def _build() -> ProofRuntime:
    store = FilingsStore(bundled_snapshot_path(), paths.state_dir() / USER_FILINGS_FILE)
    service = ProofService(store, SampleRows(_sample_path), _AppBars(), _utc_now)
    return ProofRuntime(service, FilingJobs(store, _live_source, tracked_symbols))


def proof_runtime() -> ProofRuntime:
    global _runtime
    with _lock:
        if _runtime is None:
            _runtime = _build()
        return _runtime


def reset_proof_runtime() -> None:
    """Forget the built runtime so the next call builds it again. For tests and for a changed app folder."""
    global _runtime
    with _lock:
        _runtime = None
