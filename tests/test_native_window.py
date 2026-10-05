"""The native desktop window: sizing, theme, single instance, and graceful fallback."""

from __future__ import annotations

import sys
import types
import uuid
from typing import Any

import pytest

from quant_system.shell import native_window
from quant_system.shell.native_window import (
    DARK_BACKGROUND,
    LIGHT_BACKGROUND,
    acquire_single_instance,
    diagnostics_port,
    fit_to_screen,
    run_native_window,
    system_prefers_dark,
    webview2_runtime_version,
)

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows registry and mutexes")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("9222", 9222),
        (" 8080 ", 8080),
        ("", None),
        ("abc", None),
        ("80", None),
        ("70000", None),
        ("-1", None),
    ],
)
def test_diagnostics_port_is_opt_in_and_validated(value: str, expected: int | None) -> None:
    assert diagnostics_port({"QUANTOS_DEBUG_PORT": value}) == expected
    assert diagnostics_port({}) is None


def test_diagnostics_port_is_passed_to_the_engine_only_when_requested(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    calls: dict[str, Any] = {}
    fake = _fake_webview(calls)
    fake.settings = {}
    monkeypatch.setitem(sys.modules, "webview", fake)
    monkeypatch.delenv("QUANTOS_DEBUG_PORT", raising=False)
    run_native_window("http://127.0.0.1:1")
    assert fake.settings == {}
    monkeypatch.setenv("QUANTOS_DEBUG_PORT", "9333")
    run_native_window("http://127.0.0.1:1")
    assert fake.settings == {"REMOTE_DEBUGGING_PORT": 9333}


# ------------------------------------------------------------------------------- sizing


def test_window_keeps_its_desired_size_on_a_large_screen() -> None:
    assert fit_to_screen((2560, 1440)) == ((1440, 900), (1024, 700))


def test_window_shrinks_to_fit_a_150_percent_laptop() -> None:
    (width, height), (min_width, min_height) = fit_to_screen((1280, 800))
    assert (width, height) == (1177, 720)
    assert width <= 1280 and height <= 800
    assert (min_width, min_height) == (1024, 700)


def test_minimum_size_never_exceeds_the_window() -> None:
    (width, height), (min_width, min_height) = fit_to_screen((800, 600))
    assert min_width <= width and min_height <= height


def test_unknown_screen_keeps_defaults() -> None:
    assert fit_to_screen(None, (1200, 800), (900, 600)) == ((1200, 800), (900, 600))


# ---------------------------------------------------------------------------- registry


class _FakeKey:
    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def _fake_registry(values: dict[str, Any]) -> types.SimpleNamespace:
    def open_key(_hive: object, path: str) -> _FakeKey:
        if not any(marker in path for marker in values):
            raise OSError(path)
        return _FakeKey()

    def query(_key: object, name: str) -> tuple[Any, int]:
        for marker, value in values.items():
            if marker in name or name == "pv" and marker == "EdgeUpdate":
                return value, 1
        raise OSError(name)

    return types.SimpleNamespace(
        HKEY_CURRENT_USER=1, HKEY_LOCAL_MACHINE=2, OpenKey=open_key, QueryValueEx=query
    )


@windows_only
@pytest.mark.parametrize(("apps_use_light", "dark"), [(0, True), (1, False)])
def test_dark_mode_follows_windows(
    monkeypatch: pytest.MonkeyPatch, apps_use_light: int, dark: bool
) -> None:
    monkeypatch.setitem(sys.modules, "winreg", _fake_registry({"Personalize": 0}))
    fake = sys.modules["winreg"]
    fake.QueryValueEx = lambda _key, _name: (apps_use_light, 4)  # type: ignore[attr-defined]
    assert system_prefers_dark() is dark


@windows_only
def test_dark_mode_defaults_to_light_when_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*_args: object) -> None:
        raise OSError

    fake = types.SimpleNamespace(HKEY_CURRENT_USER=1, OpenKey=deny, QueryValueEx=deny)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    assert system_prefers_dark() is False


@windows_only
def test_webview2_runtime_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.SimpleNamespace(
        HKEY_CURRENT_USER=1,
        HKEY_LOCAL_MACHINE=2,
        OpenKey=lambda _hive, _path: _FakeKey(),
        QueryValueEx=lambda _key, _name: ("154.0.4258.37", 1),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake)
    assert webview2_runtime_version() == "154.0.4258.37"
    fake.QueryValueEx = lambda _key, _name: ("0.0.0.0", 1)
    assert webview2_runtime_version() is None


# ------------------------------------------------------------------------ single instance


@windows_only
def test_second_instance_is_refused_until_the_first_is_gone() -> None:
    name = f"Local\\QuantOS.Test.{uuid.uuid4().hex}"
    assert acquire_single_instance(name) is True
    assert acquire_single_instance(name) is False
    assert acquire_single_instance(f"Local\\QuantOS.Test.{uuid.uuid4().hex}") is True


# ---------------------------------------------------------------------- native window run


def _fake_webview(
    calls: dict[str, Any], *, fail_start: bool = False, screens: list[Any] | None = None
) -> types.SimpleNamespace:
    def create_window(**kwargs: Any) -> None:
        calls["window"] = kwargs

    def start(**kwargs: Any) -> None:
        calls["start"] = kwargs
        if fail_start:
            raise RuntimeError("WebView2 could not start")

    listed = screens if screens is not None else [types.SimpleNamespace(width=1280, height=800)]
    return types.SimpleNamespace(create_window=create_window, start=start, screens=listed)


@pytest.fixture()
def runtime_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(native_window, "webview2_runtime_version", lambda: "154.0.4258.37")
    monkeypatch.setattr(native_window, "system_prefers_dark", lambda: False)


def test_opens_a_fitted_window_on_the_chromium_engine_only(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    calls: dict[str, Any] = {}
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(calls))
    assert run_native_window("http://127.0.0.1:8080", storage_path="C:/app/tmp/wv") is True
    window, start = calls["window"], calls["start"]
    assert window["title"] == "QuantOS" and window["url"] == "http://127.0.0.1:8080"
    assert (window["width"], window["height"]) == (1177, 720)
    assert window["background_color"] == LIGHT_BACKGROUND
    assert start["gui"] == "edgechromium"  # never the legacy Internet Explorer engine
    assert start["storage_path"] == "C:/app/tmp/wv" and start["debug"] is False


def test_dark_windows_gets_a_dark_first_paint(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    calls: dict[str, Any] = {}
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(calls))
    monkeypatch.setattr(native_window, "system_prefers_dark", lambda: True)
    assert run_native_window("http://127.0.0.1:1") is True
    assert calls["window"]["background_color"] == DARK_BACKGROUND


def test_unknown_screen_size_still_opens(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    calls: dict[str, Any] = {}
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(calls, screens=[]))
    assert run_native_window("http://127.0.0.1:1") is True
    assert (calls["window"]["width"], calls["window"]["height"]) == (1440, 900)


def test_falls_back_when_pywebview_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "webview", None)  # makes "import webview" raise ImportError
    assert run_native_window("http://127.0.0.1:1") is False


def test_falls_back_when_webview2_is_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(calls))
    monkeypatch.setattr(native_window, "webview2_runtime_version", lambda: None)
    assert run_native_window("http://127.0.0.1:1") is False
    assert calls == {}  # no window was created


def test_falls_back_when_the_engine_fails_to_start(
    monkeypatch: pytest.MonkeyPatch, runtime_installed: None
) -> None:
    calls: dict[str, Any] = {}
    monkeypatch.setitem(sys.modules, "webview", _fake_webview(calls, fail_start=True))
    assert run_native_window("http://127.0.0.1:1") is False


def test_studio_tries_the_native_window_before_any_browser() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "quantos_studio.py").read_text(
        encoding="utf-8"
    )
    assert "acquire_single_instance()" in source
    assert source.index("run_native_window(") < source.index(
        "find_app_browser()", source.index("def run_studio")
    )


def test_cleanup_zombie_instances_safe() -> None:
    from quant_system.shell.native_window import cleanup_zombie_instances

    # Safe execution across platforms, handles nonexistent processes safely
    cleaned = cleanup_zombie_instances(("nonexistent_process_12345.exe",))
    assert isinstance(cleaned, int)
    assert cleaned >= 0


def test_studio_contains_hard_exit_and_zombie_cleanup() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "quantos_studio.py").read_text(
        encoding="utf-8"
    )
    assert "cleanup_zombie_instances" in source
    assert "os._exit(0)" in source
