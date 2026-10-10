"""Reading one company's results from NSE in the background, with progress a screen can follow.

A job is only ever started by a button in the app. It reads one filing at a time with a pause between requests (the
NSE client does that), never retries a refusal, and can be stopped between filings. Filings are saved the moment
they are read, so a stop or a refusal half way keeps what was already read. Jobs live in memory only; one runs at a
time. The shape matches the Shariah filings jobs: status running, done, failed or cancelled; done and total; a
plain message; and a list of failures.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final

from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.reader import Clock, Hooks, ResultsSource, read_company
from quant_system.fundamentals.snapshot import FundamentalsStoreError, normalize_symbol
from quant_system.fundamentals.store import FundamentalsStore
from quant_system.shariah.filings.nse_client import FilingsBlocked, FilingsError, InvalidSymbol

__all__ = ["BUSY", "FundamentalsJobs", "InvalidSymbol", "TooBusy"]

logger = logging.getLogger(__name__)

MAX_KEPT: Final = 20
QUARTERS_TO_READ: Final = 16
BUSY: Final = (
    "QuantOS is already reading a company's results. Wait for it to finish, then try again."
)
STOPPED: Final = "Stopped. Filings already read are kept."
GENERIC: Final = "Something went wrong while reading this company's results. Try again later."
NOTHING_LISTED: Final = (
    "NSE lists no quarterly results filing for this company that QuantOS can read."
)
Spawn = Callable[[Callable[[], None]], None]
SourceFactory = Callable[[], ResultsSource]


def _in_thread(task: Callable[[], None]) -> None:
    threading.Thread(target=task, name="fundamentals-filings", daemon=True).start()


class TooBusy(Exception):
    """A job is already running."""


@dataclass
class _Job:
    symbol: str
    status: str = "running"
    done: int = 0
    total: int = 0
    saved: int = 0
    message: str = ""
    failures: list[dict[str, str]] = field(default_factory=list)


class FundamentalsJobs:
    def __init__(
        self, store: FundamentalsStore, source: SourceFactory, now: Clock, spawn: Spawn = _in_thread
    ) -> None:
        self._store = store
        self._source = source
        self._now = now
        self._spawn = spawn
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}

    # -- starting, following and stopping --------------------------------------------------------
    def start(self, symbol: str) -> str:
        """Start reading one company. Raises InvalidSymbol or TooBusy."""
        clean = normalize_symbol(symbol)
        if clean is None:
            raise InvalidSymbol
        with self._lock:
            if any(job.status == "running" for job in self._jobs.values()):
                raise TooBusy(BUSY)
            while len(self._jobs) >= MAX_KEPT:
                del self._jobs[next(iter(self._jobs))]
            job_id = uuid.uuid4().hex[:12]
            job = _Job(clean, message=f"Asking NSE what {clean} has filed.")
            self._jobs[job_id] = job
        self._spawn(lambda: self._run(job))
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "status": job.status,
                "symbol": job.symbol,
                "done": job.done,
                "total": job.total,
                "saved": job.saved,
                "message": job.message,
                "failures": [dict(item) for item in job.failures],
            }

    def cancel(self, job_id: str) -> bool:
        """Stop a job. False only when there is no such job. Asking twice, or after it ended, changes nothing."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status == "running":
                job.status, job.message = "cancelled", STOPPED
            return True

    # -- internals -------------------------------------------------------------------------------
    def _run(self, job: _Job) -> None:
        try:
            self._work(job)
        except FilingsError as error:
            self._fail(job, error.message, refused=isinstance(error, FilingsBlocked))
        except FundamentalsStoreError as error:
            self._fail(job, str(error))
        except (
            Exception
        ):  # a job must always end in a plain sentence, never in a silent thread death
            logger.exception("reading results for %s failed", job.symbol)
            self._fail(job, GENERIC)

    def _work(self, job: _Job) -> None:
        hooks = Hooks(
            progress=lambda done, total: self._progress(job, done, total),
            stop=lambda: self._stopped(job),
            keep=lambda item: self._keep(job, item),
        )
        result = read_company(self._source(), job.symbol, QUARTERS_TO_READ, self._now, hooks)
        if not result.planned:
            self._fail(job, NOTHING_LISTED)
            return
        message = f"Read {job.saved} of {result.planned} filings for {job.symbol}."
        if result.skipped:
            message += f" NSE no longer had {result.skipped} of them."
        self._finish(job, "done", message)

    def _keep(self, job: _Job, item: QuarterFigures) -> None:
        with self._lock:
            if job.status != "running":
                return  # stopped meanwhile: whatever was just read is ignored
        job.saved += self._store.put([item])

    def _progress(self, job: _Job, done: int, total: int) -> None:
        with self._lock:
            if job.status == "running":
                job.done, job.total = done, total
                job.message = f"Reading {job.symbol}: filing {done} of {total}."

    def _stopped(self, job: _Job) -> bool:
        with self._lock:
            return job.status != "running"

    def _fail(self, job: _Job, reason: str, refused: bool = False) -> None:
        with self._lock:
            if job.status != "running":
                return
            job.failures.append({"symbol": job.symbol, "reason": reason})
            job.status, job.message = "failed", reason
        if refused:
            logger.info("NSE refused a request while reading %s", job.symbol)

    def _finish(self, job: _Job, status: str, message: str) -> None:
        with self._lock:
            if job.status == "running":  # a stopped job stays stopped
                job.status, job.message = status, message
