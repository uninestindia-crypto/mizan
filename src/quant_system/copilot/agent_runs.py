"""Runs of the Copilot in agent mode: the steps it takes, the changes it asks for, and what the person decides.

A run lives in memory for as long as its screen is open. The screen asks for what happened since the last time, and a
change the Copilot asks for waits here until the person answers. The rules that matter:

* the model thread only ever *waits* for an answer. The change is carried out by the request that carries the person's
  approval (:meth:`AgentRuns.decide`), never by the thread the model runs in;
* a request is checked and put into plain words before it is shown, and a request that does not pass is refused to the
  model, never to the person;
* each kind of change has a limit per run, and a change nobody answers in time is not done.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from quant_system.copilot.actions import ActionRegistry, ActionSpec
from quant_system.copilot.agent import ActionOutcome
from quant_system.copilot.guard import scrub_prose
from quant_system.copilot.messages import CANCELLED_TEXT
from quant_system.copilot.registry import Proposal, UserFacingError

__all__ = ["AgentRuns", "RunHandle", "TooBusyError"]

logger = logging.getLogger(__name__)

MAX_RUNNING = 3
MAX_KEPT = 20
KEEP_SECONDS = 1800.0
MAX_SECONDS = 1800.0
WAIT_FOR_ANSWER_SECONDS = 600.0
MAX_EVENTS = 200
EVENT_CHARS = 400
FAILED_TEXT = "The Copilot could not finish this. Check your AI in Settings, then AI assistants, and try again."
TOO_SLOW_TEXT = "This took too long, so it was stopped."
_NOT_DONE = {
    "declined": "The person declined this, so it was not done. Carry on without it.",
    "expired": "The person did not answer in time, so it was not done.",
    "stopped": "The person stopped the run, so it was not done.",
}


class TooBusyError(Exception):
    """Too many runs are already going."""


def _in_thread(task: Callable[[], None]) -> None:
    threading.Thread(target=task, daemon=True).start()


def _plain(text: str) -> str:
    """Words the Copilot wrote, as one short line the person sees: advice phrasing is taken out, the rest is kept."""
    checked = scrub_prose(
        " ".join(str(text).split())[:EVENT_CHARS], halal_allowed=False, allowed_links=()
    )
    return (
        " ".join(checked.text.split())
        if checked.removed
        else " ".join(str(text).split())[:EVENT_CHARS]
    )


@dataclass(slots=True)
class Pending:
    """One change the Copilot has asked for and the person has not yet answered."""

    id: str
    name: str
    args: dict[str, Any]
    title: str
    detail: str | None
    note: str | None
    why: str
    # waiting -> approving (an approval is being carried out) -> done | failed; or waiting -> declined | expired | stopped
    status: str = "waiting"
    text: str = ""
    proposals: tuple[Proposal, ...] = ()
    answered: threading.Event = field(default_factory=threading.Event)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "detail": self.detail,
            "note": self.note,
            "why": self.why,
        }


@dataclass(slots=True)
class _Run:
    id: str
    created: float
    status: str = "running"  # running | waiting | done | failed | cancelled
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_EVENTS))
    pending: dict[str, Pending] = field(default_factory=dict)
    asked: dict[str, int] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    counter: int = 0
    stopped: threading.Event = field(default_factory=threading.Event)


class RunHandle:
    """What the work of one run is given: a way to report a step, to learn it was stopped, and to ask for changes."""

    def __init__(self, runs: AgentRuns, run: _Run) -> None:
        self._runs = runs
        self._run = run

    def emit(self, kind: str, text: str, ok: bool = True, **data: Any) -> None:
        self._runs._add_event(self._run, kind, text, ok, data)

    def cancelled(self) -> bool:
        return self._run.stopped.is_set() or self._run.status in ("cancelled", "failed")

    def broker(
        self, actions: ActionRegistry, wait_seconds: float = WAIT_FOR_ANSWER_SECONDS
    ) -> RunBroker:
        return RunBroker(self, self._runs, self._run, actions, wait_seconds)


class RunBroker:
    """The Copilot's side of asking: it proposes a change and waits. It cannot carry the change out."""

    def __init__(
        self,
        handle: RunHandle,
        runs: AgentRuns,
        run: _Run,
        actions: ActionRegistry,
        wait_seconds: float,
    ) -> None:
        self._handle = handle
        self._runs = runs
        self._run = run
        self._actions = actions
        self._wait_seconds = wait_seconds

    def describe(self) -> str:
        return self._actions.describe()

    def propose(self, name: str, args: Mapping[str, Any], why: str) -> Pending | str:
        """A pending change to wait on, or a plain reason the request cannot be asked for."""
        spec = self._actions.get(name)
        problem = self._actions.check(name, args)
        if spec is None or problem:
            return problem or f"There is no action called {name}."
        with self._runs._lock:
            if self._run.asked.get(name, 0) >= spec.limit:
                return f"You have already asked for this {spec.limit} time(s) in this run, which is the most allowed."
        try:
            text = spec.describe(args)
        except UserFacingError as error:
            return str(error)
        pending = Pending(
            id=uuid.uuid4().hex[:10],
            name=name,
            args=dict(args),
            title=text.title,
            detail=text.detail,
            note=text.note,
            why=_plain(why),
        )
        with self._runs._lock:
            self._run.asked[name] = self._run.asked.get(name, 0) + 1
            self._run.pending[pending.id] = pending
            self._run.status = "waiting"
        self._handle.emit("action_request", text.title, action_id=pending.id)
        return pending

    def wait(self, pending: Pending) -> ActionOutcome:
        """Blocks until the person answers, the run is stopped, or the time is up. Never carries the change out."""
        deadline = time.monotonic() + self._wait_seconds
        while not pending.answered.wait(0.2):
            if self._handle.cancelled():
                self._runs._settle(self._run, pending, "stopped", "")
                break
            if time.monotonic() > deadline:
                self._runs._settle(self._run, pending, "expired", "")
                break
        with self._runs._lock:
            if (
                not any(p.status == "waiting" for p in self._run.pending.values())
                and self._run.status == "waiting"
            ):
                self._run.status = "running"
        text = pending.text or _NOT_DONE.get(pending.status, "It was not done.")
        return ActionOutcome(pending.status, text, pending.proposals)


class AgentRuns:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        spawn: Callable[[Callable[[], None]], None] = _in_thread,
        deadline: float = MAX_SECONDS,
    ) -> None:
        self._clock = clock
        self._spawn = spawn
        self._deadline = deadline
        self._lock = threading.RLock()
        self._runs: dict[str, _Run] = {}
        self._actions: dict[str, ActionRegistry] = {}

    # ------------------------------------------------------------------------------------------ start

    def start(self, work: Callable[[RunHandle], dict[str, Any]], actions: ActionRegistry) -> str:
        with self._lock:
            self._expire()
            self._forget_old()
            if sum(r.status in ("running", "waiting") for r in self._runs.values()) >= MAX_RUNNING:
                raise TooBusyError
            run = _Run(id=uuid.uuid4().hex[:12], created=self._clock())
            self._runs[run.id] = run
            self._actions[run.id] = actions
        handle = RunHandle(self, run)
        self._spawn(lambda: self._run(run, handle, work))
        return run.id

    def _run(
        self, run: _Run, handle: RunHandle, work: Callable[[RunHandle], dict[str, Any]]
    ) -> None:
        if handle.cancelled():
            return
        try:
            result = work(handle)
        except Exception:
            logger.exception("agent run failed")
            self._finish(run, "failed", None, FAILED_TEXT)
        else:
            self._finish(run, "done", result, None)

    # ----------------------------------------------------------------------------------------- reading

    def get(self, run_id: str, after: int = 0) -> dict[str, Any] | None:
        with self._lock:
            self._expire()
            run = self._runs.get(run_id)
            if run is None:
                return None
            return {
                "status": run.status,
                "events": [e for e in run.events if e["n"] > after],
                "next": run.counter,
                "pending": [p.as_dict() for p in run.pending.values() if p.status == "waiting"],
                "result": run.result,
                "error": run.error,
            }

    def cancel(self, run_id: str) -> bool:
        """Stop a run the person no longer wants. Changes still waiting for an answer are not done."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return False
            if run.status in ("running", "waiting"):
                run.status, run.error = "cancelled", CANCELLED_TEXT
                run.stopped.set()
                for pending in run.pending.values():
                    if pending.status == "waiting":
                        self._settle(run, pending, "stopped", "")
            return True

    # ---------------------------------------------------------------------------------------- deciding

    def decide(self, run_id: str, action_id: str, approve: bool) -> str | None:
        """Carry out the person's answer. ``None`` when there is nothing waiting to answer; else the sentence to show."""
        with self._lock:
            run = self._runs.get(run_id)
            pending = run.pending.get(action_id) if run else None
            registry = self._actions.get(run_id)
            if run is None or pending is None or registry is None or pending.status != "waiting":
                return None
            spec = registry.get(pending.name)
            if not approve or spec is None:
                self._settle(run, pending, "declined", "")
                self._add_event(
                    run,
                    "action_result",
                    f"Skipped: {pending.title}",
                    True,
                    {"action_id": action_id},
                )
                return "Skipped."
            # Claimed under the lock, so a second press of Approve finds nothing waiting and cannot run it twice.
            pending.status = "approving"
        return self._carry_out(run, pending, spec)

    def _carry_out(self, run: _Run, pending: Pending, spec: ActionSpec) -> str:
        """Runs an approved change in the request that approved it, never in the model's thread."""
        try:
            done = spec.run(pending.args)
        except UserFacingError as error:
            status, text, ok = "failed", f"It could not be done: {error}", False
            proposals: tuple[Proposal, ...] = ()
        except Exception:
            logger.exception("approved action %s failed", pending.name)
            status, text, ok = "failed", "It could not be done just now.", False
            proposals = ()
        else:
            status, text, ok, proposals = "done", done.text, True, done.proposals
        with self._lock:
            pending.proposals = proposals
            self._settle(run, pending, status, text, expect="approving")
            self._add_event(run, "action_result", text, ok, {"action_id": pending.id})
        return text

    def _settle(
        self, run: _Run, pending: Pending, status: str, text: str, expect: str = "waiting"
    ) -> None:
        """Records the answer once. A change being carried out cannot be timed out or stopped from under it."""
        with self._lock:
            if pending.status != expect:
                return
            pending.status, pending.text = status, text
            pending.answered.set()
            if (
                not any(p.status == "waiting" for p in run.pending.values())
                and run.status == "waiting"
            ):
                run.status = "running"

    # --------------------------------------------------------------------------------------- bookkeeping

    def _add_event(self, run: _Run, kind: str, text: str, ok: bool, data: dict[str, Any]) -> None:
        with self._lock:
            run.counter += 1
            run.events.append(
                {"n": run.counter, "kind": kind, "text": _plain(text), "ok": ok, **data}
            )

    def _finish(
        self, run: _Run, status: str, result: dict[str, Any] | None, error: str | None
    ) -> None:
        with self._lock:
            if run.status in ("cancelled", "failed"):
                if run.status == "cancelled" and result is not None:
                    run.result = result  # what was found before it was stopped
                return
            run.status, run.result, run.error = status, result, error

    def _expire(self) -> None:
        now = self._clock()
        for run in self._runs.values():
            if run.status in ("running", "waiting") and now - run.created > self._deadline:
                run.status, run.error = "failed", TOO_SLOW_TEXT
                run.stopped.set()

    def _forget_old(self) -> None:
        now = self._clock()
        for run_id in [
            i
            for i, r in self._runs.items()
            if r.status not in ("running", "waiting") and now - r.created > KEEP_SECONDS
        ]:
            del self._runs[run_id]
            self._actions.pop(run_id, None)
        while len(self._runs) >= MAX_KEPT:
            finished = [i for i, r in self._runs.items() if r.status not in ("running", "waiting")]
            if not finished:
                break
            del self._runs[finished[0]]
            self._actions.pop(finished[0], None)
