"""The window opens at once with a loading screen, and shows the app only when the engine is ready."""

from __future__ import annotations

import re
import sys
import types
from typing import Any

import pytest

from quant_system.shell import native_window
from quant_system.shell.native_window import LoadingPage, run_native_window
from quant_system.shell.splash import failure_html, splash_html

# ------------------------------------------------------------------------------------- the pages


def _visible_text(page: str) -> str:
    """What a person reads on the page: no style block, no tags."""
    without_style = re.sub(r"<style.*?</style>", " ", page, flags=re.DOTALL)
    return " ".join(re.sub(r"<[^>]+>", " ", without_style).split()).lower()


CODE_WORDS = ("port", "server", "localhost", "exception", "traceback", "error code", "log file")


@pytest.mark.parametrize("dark", [False, True])
def test_the_loading_screen_is_self_contained_and_says_what_is_happening(dark: bool) -> None:
    page = splash_html(dark=dark, version="2.5.0")
    assert "QuantOS" in page and "Starting" in page and "2.5.0" in page
    assert "http://" not in page and "https://" not in page  # nothing is fetched to show it
    assert "<script" not in page  # it shows even where scripts are off


def test_the_loading_screen_matches_the_window_colour_so_nothing_flashes() -> None:
    assert native_window.DARK_BACKGROUND in splash_html(dark=True, version="1")
    assert native_window.LIGHT_BACKGROUND in splash_html(dark=False, version="1")


def test_the_loading_screen_reassures_a_slow_start_without_code_terms() -> None:
    text = _visible_text(splash_html(dark=False, version="1"))
    assert "still starting" in text
    assert [w for w in CODE_WORDS if w in text] == []


def test_a_version_cannot_inject_markup() -> None:
    assert "<img" not in splash_html(dark=False, version='<img src=x onerror="1">')


def test_the_failure_page_says_what_to_do_in_plain_words() -> None:
    text = _visible_text(failure_html(dark=False))
    assert "could not start" in text and "open quantos again" in text
    assert [w for w in CODE_WORDS if w in text] == []


# ------------------------------------------------------------------------------------- the window


class _FakeWindow:
    def __init__(self) -> None:
        self.loaded: list[tuple[str, str]] = []

    def load_url(self, url: str) -> None:
        self.loaded.append(("url", url))

    def load_html(self, html: str) -> None:
        self.loaded.append(("html", html))


def _fake_webview(calls: dict[str, Any], window: _FakeWindow) -> types.SimpleNamespace:
    def create_window(**kwargs: Any) -> _FakeWindow:
        calls["window"] = kwargs
        return window

    def start(**kwargs: Any) -> None:
        calls["start"] = kwargs
        func = kwargs.get("func")
        if func is not None:
            func(*kwargs.get("args", ()))

    return types.SimpleNamespace(
        create_window=create_window,
        start=start,
        screens=[types.SimpleNamespace(width=1280, height=800)],
    )


@pytest.fixture()
def runtime_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_window, "webview2_runtime_version", lambda: "154.0.4258.37")
    monkeypatch.setattr(native_window, "system_prefers_dark", lambda: False)


def _run(monkeypatch: pytest.MonkeyPatch, ready: Any) -> tuple[dict[str, Any], _FakeWindow, bool]:
    calls: dict[str, Any] = {}
    window = _FakeWindow()
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(calls, window))
    loading = LoadingPage(html="<p>loading</p>", ready=ready, failure_html="<p>failed</p>")
    shown = run_native_window("http://127.0.0.1:8080", loading=loading)
    return calls, window, shown


def test_the_window_opens_on_the_loading_screen_not_on_the_address(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    calls, _, shown = _run(monkeypatch, lambda: True)
    assert shown is True
    assert calls["window"]["html"] == "<p>loading</p>" and "url" not in calls["window"]


def test_when_the_engine_is_ready_the_window_goes_to_the_app(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    _, window, _ = _run(monkeypatch, lambda: True)
    assert window.loaded == [("url", "http://127.0.0.1:8080")]


def test_when_the_engine_cannot_start_the_window_says_so_in_plain_words(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    _, window, _ = _run(monkeypatch, lambda: False)
    assert window.loaded == [("html", "<p>failed</p>")]


def test_a_readiness_check_that_raises_is_a_failed_start_never_a_crash(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    def broken() -> bool:
        raise RuntimeError("boom")

    _, window, shown = _run(monkeypatch, broken)
    assert shown is True and window.loaded == [("html", "<p>failed</p>")]


def test_the_wait_happens_after_the_window_exists(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    seen: dict[str, bool] = {}
    calls: dict[str, Any] = {}

    def ready() -> bool:
        seen["window_existed"] = "window" in calls
        return True

    window = _FakeWindow()
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(calls, window))
    loading = LoadingPage(html="x", ready=ready, failure_html="y")
    run_native_window("http://127.0.0.1:8080", loading=loading)
    assert seen == {"window_existed": True}


def test_without_a_loading_screen_the_window_still_opens_straight_on_the_address(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    calls: dict[str, Any] = {}
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(calls, _FakeWindow()))
    assert run_native_window("http://127.0.0.1:8080") is True
    assert calls["window"]["url"] == "http://127.0.0.1:8080"
    assert "func" not in calls["start"]
