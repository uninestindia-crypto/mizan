"""Second opinions take a while, so they run in the background and the screen checks in for progress.

Jobs are kept in memory only: they hold an answer for a screen that is still open, nothing more. A few run at once,
the oldest are dropped, and a job that fails reports a plain sentence rather than a stack trace.

A job that is still running after its deadline is marked failed and stops counting toward the limit. A thread cannot
be stopped from outside, so the work is only left behind: whatever it finally returns is ignored.

A person can stop a job (:meth:`VerifyJobs.cancel`). It reads ``cancelled`` at once and stops counting toward the
limit. The work is told through the ``cancelled`` check it is handed, and must stop starting new AI calls. A call
that is already in flight cannot be recalled: it finishes in the background and its answer is ignored.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from quant_system.copilot.messages import CANCELLED_TEXT
from quant_system.copilot.verify_opinion import Opinion
from quant_system.copilot.verify_summary import VerificationResult

__all__ = ["CANCELLED_TEXT", "TooBusyError", "VerifyJobs"]

logger = logging.getLogger(__name__)

MAX_RUNNING = 3
MAX_KEPT = 20
KEEP_SECONDS = 1800.0
MAX_SECONDS = 600.0
FAILED_TEXT = (
    "The second opinion could not be finished. "
    "Check your AI keys in Settings, then Accounts and keys, and try again."
)
# The work is handed a way to report each answer and a check it must make before it starts any new AI call.
Work = Callable[[Callable[[Opinion], None], Callable[[], bool]], VerificationResult]
Spawn = Callable[[Callable[[], None]], None]


def _in_thread(task: Callable[[], None]) -> None:
    threading.Thread(target=task, daemon=True).start()


class TooBusyError(Exception):
    """Too many second opinions are already running."""


@dataclass(slots=True)
class _Job:
    total: int
    created: float
    done: int = 0
    status: str = "running"
    result: dict[str, Any] | None = None
    error: str | None = None


class VerifyJobs:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        spawn: Spawn = _in_thread,
        deadline: float = MAX_SECONDS,
    ) -> None:
        self._clock = clock
        self._spawn = spawn
        self._deadline = deadline
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}

    def start(self, work: Work, total: int) -> str:
        with self._lock:
            self._expire()
            self._forget_old()
            if sum(job.status == "running" for job in self._jobs.values()) >= MAX_RUNNING:
                raise TooBusyError
            job_id = uuid.uuid4().hex[:12]
            job = _Job(total, self._clock())
            self._jobs[job_id] = job
        self._spawn(lambda: self._run(job, work))
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._expire()
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "status": job.status,
                "progress": {"done": job.done, "total": job.total},
                "result": job.result,
                "error": job.error,
            }

    def cancel(self, job_id: str) -> bool:
        """Stop a job the person no longer wants. False only when there is no such job.

        Asking twice changes nothing, and a job that has already finished keeps its result.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status == "running":
                job.status, job.error = "cancelled", CANCELLED_TEXT
            return True

    # ------------------------------------------------------------------------------------------

    def _run(self, job: _Job, work: Work) -> None:
        if self._stopped(job):
            return  # stopped before it even started: nothing to ask
        try:
            result = work(lambda _opinion: self._count(job), lambda: self._stopped(job))
        except Exception:
            logger.exception("second opinion job failed")
            self._finish(job, "failed", None, FAILED_TEXT)
        else:
            self._finish(job, "done", result.as_dict(), None)

    def _stopped(self, job: _Job) -> bool:
        """True once the job is no longer running: stopped by the person, or given up on at its deadline."""
        with self._lock:
            self._expire()
            return job.status != "running"

    def _count(self, job: _Job) -> None:
        with self._lock:
            if job.status == "running":
                job.done += 1

    def _finish(
        self, job: _Job, status: str, result: dict[str, Any] | None, error: str | None
    ) -> None:
        with self._lock:
            # A job stopped by the person or given up on at its deadline stays so: whatever the work finally returns
            # is ignored.
            if job.status != "running":
                return
            job.status, job.result, job.error = status, result, error
            job.done = job.total if status == "done" else job.done

    def _expire(self) -> None:
        """Give up on a job that is still running past its deadline. Called with the lock held."""
        now = self._clock()
        for job in self._jobs.values():
            if job.status == "running" and now - job.created > self._deadline:
                job.status, job.error = "failed", FAILED_TEXT

    def _forget_old(self) -> None:
        now = self._clock()
        for job_id in [
            i
            for i, j in self._jobs.items()
            if j.status != "running" and now - j.created > KEEP_SECONDS
        ]:
            del self._jobs[job_id]
        while len(self._jobs) >= MAX_KEPT:
            finished = [i for i, j in self._jobs.items() if j.status != "running"]
            if not finished:
                break
            del self._jobs[finished[0]]
