"""The paper runner's log lines say IST, so they must be in IST on every machine.

The format string prints the word IST, but the default converter reports the host's local time. In
a cloud container the log read ``16:53:50 IST`` at 22:23 in India. Nothing in the file would ever have
said so, and these logs are the audit trail for an unattended trading session.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
import time
from pathlib import Path
from types import ModuleType
from unittest import mock

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_paper_pilot_session.py"


def _load_runner(*, logging_already_configured: bool) -> tuple[ModuleType, list[logging.Handler]]:
    """Execute the script as a module, leaving the root logger as it was found."""
    spec = importlib.util.spec_from_file_location("_rps_clock", SCRIPT)
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    root = logging.getLogger()
    saved = list(root.handlers)
    if not logging_already_configured:
        root.handlers = []
    try:
        with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
            sys.modules[spec.name] = runner
            try:
                spec.loader.exec_module(runner)
            finally:
                sys.modules.pop(spec.name, None)
        created = [h for h in root.handlers if h not in saved]
    finally:
        root.handlers = saved
    return runner, created


def test_ist_time_is_indian_time_whatever_the_process_timezone() -> None:
    runner, _ = _load_runner(logging_already_configured=True)
    stamp = runner.ist_time(0.0)  # 1970-01-01 00:00:00 UTC
    assert tuple(stamp)[:6] == (1970, 1, 1, 5, 30, 0)


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="needs POSIX tzset to change the host zone")
def test_the_converter_ignores_the_hosts_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    runner, _ = _load_runner(logging_already_configured=True)
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    time.tzset()
    try:
        assert tuple(runner.ist_time(0.0))[:6] == (1970, 1, 1, 5, 30, 0)
        assert tuple(time.localtime(0.0))[3] != 5  # the host clock really is elsewhere
    finally:
        monkeypatch.undo()
        time.tzset()


def test_a_log_line_the_runner_formats_carries_indian_time() -> None:
    _, created = _load_runner(logging_already_configured=False)
    assert len(created) == 1
    record = logging.LogRecord(
        "quant_system.paper_runner", logging.INFO, "f", 1, "hello", None, None
    )
    record.created = 0.0  # 05:30:00 in India
    line = created[0].format(record)
    assert line.startswith("1970-01-01 05:30:00 IST [INFO]")


def test_a_logging_setup_that_was_already_there_is_left_alone() -> None:
    runner, created = _load_runner(logging_already_configured=True)
    assert created == []
    assert runner.ist_time is not None
