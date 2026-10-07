"""The engine starts on a background thread, so the window can open while it loads, and a failed start is reported."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import quantos_studio
from quantos_studio import EngineBoot

LOG = logging.getLogger("test.boot")
ROOT = Path(__file__).resolve().parents[1]


class _FakeServer:
    """Runs until told to exit, like the real server, without polling."""

    def __init__(self) -> None:
        self._exit = threading.Event()
        self.ran = threading.Event()

    @property
    def should_exit(self) -> bool:
        return self._exit.is_set()

    @should_exit.setter
    def should_exit(self, value: bool) -> None:
        if value:
            self._exit.set()

    def run(self) -> None:
        self.ran.set()
        self._exit.wait(5)


def test_starting_the_engine_returns_at_once_even_when_loading_it_is_slow() -> None:
    release = threading.Event()

    def slow_build(_port: int) -> Any:
        release.wait(5)
        return _FakeServer()

    boot = EngineBoot(8080, LOG, make_server=slow_build)
    started = time.monotonic()
    boot.start()
    assert time.monotonic() - started < 0.5
    release.set()
    boot.stop()


def test_the_engine_is_reported_ready_when_the_address_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _FakeServer()
    boot = EngineBoot(8080, LOG, make_server=lambda _port: server)
    monkeypatch.setattr(quantos_studio, "wait_for_server_ready", lambda url, timeout_sec: True)
    boot.start()
    assert boot.wait_ready("http://127.0.0.1:8080", timeout_sec=2.0) is True
    assert server.ran.wait(2)
    boot.stop()
    assert server.should_exit is True


def test_a_start_that_fails_is_reported_at_once_not_after_the_whole_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_port: int) -> Any:
        raise RuntimeError("could not import")

    boot = EngineBoot(8080, LOG, make_server=broken)
    monkeypatch.setattr(quantos_studio, "wait_for_server_ready", lambda url, timeout_sec: False)
    boot.start()
    started = time.monotonic()
    assert boot.wait_ready("http://127.0.0.1:8080", timeout_sec=30.0) is False
    assert time.monotonic() - started < 5
    assert isinstance(boot.error, RuntimeError)


def test_an_engine_that_never_answers_gives_up_after_the_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _FakeServer()
    boot = EngineBoot(8080, LOG, make_server=lambda _port: server)
    monkeypatch.setattr(quantos_studio, "wait_for_server_ready", lambda url, timeout_sec: False)
    boot.start()
    assert boot.wait_ready("http://127.0.0.1:8080", timeout_sec=0.3) is False
    boot.stop()


def test_stopping_an_engine_that_never_started_is_harmless() -> None:
    boot = EngineBoot(8080, LOG, make_server=lambda _port: _FakeServer())
    boot.stop()
    assert boot.server is None and boot.error is None


def test_the_studio_starts_the_engine_before_it_opens_the_window() -> None:
    source = (ROOT / "quantos_studio.py").read_text(encoding="utf-8")
    body = source[source.index("def run_studio") :]
    assert body.index("boot.start()") < body.index("run_native_window(")
    assert "loading=" in body  # the window is given the loading screen


def test_the_studio_allows_a_slow_laptop_far_longer_than_twelve_seconds() -> None:
    source = (ROOT / "quantos_studio.py").read_text(encoding="utf-8")
    assert "READY_TIMEOUT_SECONDS" in source
    assert "timeout_sec=12.0" not in source  # a slow laptop needs more than twelve seconds


SPEC_FILES = ["quant_system.spec", "installer/quantos.spec", "installer/quantos-studio.spec"]


@pytest.mark.parametrize("name", SPEC_FILES)
def test_the_program_is_not_compressed_on_disk_because_that_slows_every_start(name: str) -> None:
    """UPX unpacks every file each time the program starts and is a common trigger for antivirus scans."""
    spec = (ROOT / name).read_text(encoding="utf-8")
    assert "upx=True" not in spec
