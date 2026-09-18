"""The scheduled session must ask Windows not to idle-sleep the machine while it runs.

The flagship paper book went 18 days without rebalancing for this reason, and nothing in the book
was wrong. The 09:00 task woke the machine and started the run; the machine then idled back to
sleep 7m13s later -- the same figure on two consecutive days -- suspending the process mid-run:

    2026-09-16 09:07:32  Kernel-Power 42  "The system is entering sleep. Sleep Reason: System Idle"
    2026-09-17 09:07:14  Kernel-Power 42  "Sleep Reason: System Idle"

It resumed only when a human opened the lid, hours after the 15:30 IST close, so the session reached
its trading window with no window left, submitted zero orders, and the rebalance was correctly
refused for want of coverage. The hold clock never reset, and the next day repeated it.

What is tested here is the contract, not the outcome: the request is taken for the run and released
afterwards even when the run raises, and a machine that refuses the request still trades. Only a
real 09:00 run with the lid shut on battery can prove the outcome.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "scripts" / "run_scheduled_paper_session.py"


@pytest.fixture(scope="module")
def wrapper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_scheduled_paper_session", WRAPPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Recorder:
    """Stands in for `SetThreadExecutionState`, recording the flags it is handed."""

    def __init__(self, result: int = 0x80000000) -> None:
        self.calls: list[int] = []
        self.result = result

    def __call__(self, flags: int) -> int:
        self.calls.append(flags)
        return self.result


def test_the_run_holds_a_system_power_request(wrapper: ModuleType) -> None:
    """The defect: nothing asked Windows to stay awake, so it idled the run out from under itself."""
    recorder = _Recorder()

    with wrapper.keep_system_awake(_set_state=recorder):
        pass

    assert recorder.calls, "no power request was made; the machine may idle-sleep mid-session"
    requested = recorder.calls[0]
    assert requested & wrapper.ES_CONTINUOUS, "the request must persist for the run, not one moment"
    assert requested & wrapper.ES_SYSTEM_REQUIRED, "the request must keep the *system* awake"


def test_the_request_is_released_when_the_run_finishes(wrapper: ModuleType) -> None:
    """A request that outlives the run would keep the laptop awake indefinitely."""
    recorder = _Recorder()

    with wrapper.keep_system_awake(_set_state=recorder):
        pass

    assert len(recorder.calls) == 2, f"expected take and release, got {recorder.calls}"
    released = recorder.calls[-1]
    assert released == wrapper.ES_CONTINUOUS, "release must clear SYSTEM_REQUIRED and keep nothing"


def test_the_request_is_released_even_when_the_session_raises(wrapper: ModuleType) -> None:
    """The session runs for hours and can fail at any point; the laptop must not stay pinned awake."""
    recorder = _Recorder()

    with pytest.raises(RuntimeError, match="session blew up"):
        with wrapper.keep_system_awake(_set_state=recorder):
            raise RuntimeError("session blew up")

    assert recorder.calls[-1] == wrapper.ES_CONTINUOUS, "the release must run on the exception path"


def test_a_refused_request_does_not_stop_the_session(wrapper: ModuleType) -> None:
    """Fail soft. A run that refused to trade because Windows declined a hint would be worse.

    `SetThreadExecutionState` returns 0 on failure. The session must proceed regardless.
    """
    recorder = _Recorder(result=0)
    reached = False

    with wrapper.keep_system_awake(_set_state=recorder):
        reached = True

    assert reached, "a refused power request must not prevent the session from running"


def test_an_unavailable_api_does_not_stop_the_session(wrapper: ModuleType) -> None:
    """On POSIX, and on any Windows where the call cannot be bound, there is simply no request."""

    def explode(_flags: int) -> int:
        raise OSError("SetThreadExecutionState is unavailable")

    reached = False
    with wrapper.keep_system_awake(_set_state=explode):
        reached = True

    assert reached, "an unavailable power API must not prevent the session from running"


def test_the_wrapper_actually_uses_it(wrapper: ModuleType) -> None:
    """Guards against the helper existing and `main` never calling it -- the whole defect returning.

    Read from the source rather than by driving `main`, which would need a trading day, a provider
    token, a refreshed cache and six hours.
    """
    source = WRAPPER.read_text(encoding="utf-8")
    body = source.split("def main(", 1)[1]
    assert "keep_system_awake(" in body, (
        "main() does not hold a power request; the session can be idled out from under itself again"
    )


def _unused(value: Any) -> Any:  # pragma: no cover - keeps the type checker honest about fixtures
    return value
