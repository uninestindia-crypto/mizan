"""Reading company filings from NSE in the background, one job at a time, with progress a screen can follow.

A job is only ever started by a button in the app. It reads one company at a time and pauses between requests (the
NSE client does that), never retries a refusal, and stops after three refusals in a row. A person can stop it: it
stops before the next company's requests. A filing is saved to this computer only when it was read cleanly and
agrees with itself, and a stopped job saves nothing it was in the middle of. Jobs live in memory only.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from quant_system.shariah.filings.models import FilingFigures, ReadStatus, normalize_symbol
from quant_system.shariah.filings.nse_client import FilingsBlocked, FilingsError, InvalidSymbol
from quant_system.shariah.filings.selection import Selection
from quant_system.shariah.filings.snapshot import FilingsStoreError
from quant_system.shariah.filings.store import FilingsStore
from quant_system.shariah.services.filing_words import (
    BUSY,
    NOTHING_TO_REFRESH,
    SAVE_FAILED_PREFIX,
    STOPPED,
    TOO_MANY_BLOCKS,
    failure_reason,
    finished_message,
    reading_message,
    used_filing,
)

__all__ = ["BUSY", "FilingJobs", "FilingsSource", "TooBusy"]

logger = logging.getLogger(__name__)

MAX_BLOCKS_IN_A_ROW = 3
MAX_KEPT = 20
MAX_FAILURES = 200
_GENERIC = "Something went wrong while reading filings. Try again later."
_NOT_READ = "QuantOS could not read this company's filing."


class FilingsSource(Protocol):
    def read_company(self, symbol: str) -> Selection: ...


SourceFactory = Callable[[], FilingsSource]
Tracked = Callable[[], Sequence[str]]
Spawn = Callable[[Callable[[], None]], None]


def _in_thread(task: Callable[[], None]) -> None:
    threading.Thread(target=task, name="shariah-filings", daemon=True).start()


class TooBusy(Exception):
    """A job is already running."""


@dataclass(slots=True)
class _Job:
    symbols: list[str]
    status: str = "running"
    done: int = 0
    saved: int = 0
    message: str = ""
    failures: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Outcome:
    """What reading one company came to: a filing to keep, or the plain reason there is none."""

    figures: FilingFigures | None = None
    reason: str | None = None
    refused: bool = False


class FilingJobs:
    def __init__(
        self,
        store: FilingsStore,
        source: SourceFactory,
        tracked: Tracked,
        spawn: Spawn = _in_thread,
    ) -> None:
        self._store = store
        self._source = source
        self._tracked = tracked
        self._spawn = spawn
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}

    # -- starting, following and stopping --------------------------------------------------------
    def start_one(self, symbol: str) -> str:
        """Read one company's latest filing. Raises InvalidSymbol or TooBusy."""
        clean = normalize_symbol(symbol)
        if clean is None:
            raise InvalidSymbol
        return self._start([clean])

    def start_refresh(self) -> str:
        """Read the latest filing of every stock the app tracks and every stock already screened. Raises TooBusy."""
        return self._start(self._refresh_symbols())

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "status": job.status,
                "done": job.done,
                "total": len(job.symbols),
                "message": job.message,
                "failures": [dict(failure) for failure in job.failures],
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
    def _refresh_symbols(self) -> list[str]:
        tracked = [s for s in (normalize_symbol(raw) for raw in self._tracked()) if s]
        screened = [s for s in self._store.symbols() if self._read_cleanly(s)]
        return list(dict.fromkeys([*tracked, *screened]))

    def _read_cleanly(self, symbol: str) -> bool:
        figures = self._store.get(symbol)
        return figures is not None and figures.read_status is ReadStatus.READ_OK

    def _start(self, symbols: list[str]) -> str:
        with self._lock:
            if any(job.status == "running" for job in self._jobs.values()):
                raise TooBusy(BUSY)
            self._forget_old()
            job_id = uuid.uuid4().hex[:12]
            job = _Job(symbols)
            self._jobs[job_id] = job
            if not symbols:
                job.status, job.message = "done", NOTHING_TO_REFRESH
                return job_id
            job.message = reading_message(symbols[0], 0, len(symbols))
        self._spawn(lambda: self._run(job))
        return job_id

    def _forget_old(self) -> None:
        while len(self._jobs) >= MAX_KEPT:
            del self._jobs[next(iter(self._jobs))]

    def _run(self, job: _Job) -> None:
        try:
            self._work(job)
        except FilingsStoreError as error:
            self._finish(job, "failed", f"{SAVE_FAILED_PREFIX}{error}")
        except (
            Exception
        ):  # a job must always end in a plain sentence, never in a silent thread death
            logger.exception("reading company filings failed")
            self._finish(job, "failed", _GENERIC)

    def _work(self, job: _Job) -> None:
        source = self._source()
        refused_in_a_row = 0
        for symbol in job.symbols:
            if self._stopped(job):
                return
            self._announce(job, symbol)
            refused = self._step(job, source, symbol)
            refused_in_a_row = refused_in_a_row + 1 if refused else 0
            if refused_in_a_row >= MAX_BLOCKS_IN_A_ROW:
                self._finish(job, "failed", TOO_MANY_BLOCKS)
                return
        failed = job.saved == 0 and bool(job.failures)
        message = finished_message(job.symbols, job.saved, job.failures)
        self._finish(job, "failed" if failed else "done", message)

    def _step(self, job: _Job, source: FilingsSource, symbol: str) -> bool:
        """Read and keep one company's filing. True when NSE refused the request."""
        outcome = self._read(source, symbol)
        with self._lock:
            if job.status != "running":
                return False  # stopped meanwhile: whatever was just read is ignored
            if outcome.figures is not None:
                self._store.put(outcome.figures)
            job.done += 1
            job.saved += outcome.figures is not None
            if outcome.reason and len(job.failures) < MAX_FAILURES:
                job.failures.append({"symbol": symbol, "reason": outcome.reason})
        return outcome.refused

    def _read(self, source: FilingsSource, symbol: str) -> _Outcome:
        try:
            selection = source.read_company(symbol)
        except FilingsError as error:
            return _Outcome(reason=error.message, refused=isinstance(error, FilingsBlocked))
        except Exception:  # one company's failure must not stop the others
            logger.exception("could not read the filing for %s", symbol)
            return _Outcome(reason=_NOT_READ)
        figures = selection.figures
        if figures is None or not used_filing(figures):
            return _Outcome(reason=failure_reason(selection))
        return _Outcome(figures=figures)

    def _announce(self, job: _Job, symbol: str) -> None:
        with self._lock:
            if job.status == "running":
                job.message = reading_message(symbol, job.done, len(job.symbols))

    def _stopped(self, job: _Job) -> bool:
        with self._lock:
            return job.status != "running"

    def _finish(self, job: _Job, status: str, message: str) -> None:
        with self._lock:
            if job.status == "running":  # a stopped job stays stopped
                job.status, job.message = status, message
