"""Tests for QuantOS Desktop Studio Host and Zero-Console Launcher."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import uvicorn

from quant_system.server.app import app
from quantos_studio import (
    NullStream,
    configure_drive_isolation,
    ensure_safe_std_streams,
    find_app_browser,
    find_free_port,
    setup_studio_logging,
    wait_for_server_ready,
)


def test_configure_drive_isolation_sets_local_tmp() -> None:
    """Verifies that drive isolation sets temp/cache dirs to the install drive."""
    root = configure_drive_isolation()
    assert root.exists()
    assert (root / "tmp").exists()
    assert (root / "logs").exists()
    assert (root / "data").exists()

    expected_tmp = str(root / "tmp")
    assert os.environ.get("TEMP") == expected_tmp
    assert os.environ.get("TMP") == expected_tmp


def test_find_free_port_returns_valid_port() -> None:
    """Verifies that find_free_port returns a usable integer port."""
    port = find_free_port(9000)
    assert isinstance(port, int)
    assert 9000 <= port < 9050


def test_wait_for_server_ready_timeout() -> None:
    """Verifies that wait_for_server_ready returns False when target port is unreachable."""
    # Port 59999 should not have a running QuantOS server
    ready = wait_for_server_ready("http://127.0.0.1:59999", timeout_sec=0.2)
    assert ready is False


def test_find_app_browser_safe_execution() -> None:
    """Verifies that find_app_browser executes safely and returns a valid path or None."""
    browser_exe = find_app_browser()
    if browser_exe is not None:
        assert isinstance(browser_exe, str)
        assert Path(browser_exe).is_file()


def test_desktop_launcher_artifacts_exist() -> None:
    """Verifies presence and non-emptiness of the studio launcher artifacts."""
    root = Path(__file__).parent.parent
    vbs = root / "QuantOS-Studio.vbs"
    bat = root / "launch-quantos-studio.bat"
    shortcut_ps1 = root / "scripts" / "create-desktop-shortcut.ps1"
    spec = root / "installer" / "quantos-studio.spec"

    assert vbs.is_file(), "QuantOS-Studio.vbs must exist"
    assert vbs.stat().st_size > 50, "QuantOS-Studio.vbs must not be empty"

    assert bat.is_file(), "launch-quantos-studio.bat must exist"
    assert bat.stat().st_size > 50, "launch-quantos-studio.bat must not be empty"

    assert shortcut_ps1.is_file(), "create-desktop-shortcut.ps1 must exist"
    assert shortcut_ps1.stat().st_size > 50, "create-desktop-shortcut.ps1 must not be empty"

    assert spec.is_file(), "quantos-studio.spec must exist"
    assert spec.stat().st_size > 50, "quantos-studio.spec must not be empty"


def test_null_stream_behavior() -> None:
    """Verifies that NullStream fulfills stream expectations safely."""
    stream = NullStream()
    assert stream.write("test message") == 12
    assert stream.isatty() is False
    assert stream.read() == ""
    assert stream.readline() == ""
    assert stream.encoding == "utf-8"
    stream.flush()


def test_ensure_safe_std_streams_replaces_none() -> None:
    """Verifies that ensure_safe_std_streams replaces None streams with safe fallbacks."""
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    try:
        sys.stdin = None
        sys.stdout = None
        sys.stderr = None

        ensure_safe_std_streams()

        assert sys.stdin is not None
        assert sys.stdout is not None
        assert sys.stderr is not None
        assert sys.stdout.isatty() is False
        assert sys.stderr.isatty() is False
        assert sys.stdout.write("hello") == 5
        assert sys.stderr.write("world") == 5
    finally:
        sys.stdin = orig_stdin
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr


def test_ensure_safe_std_streams_redirects_to_log(tmp_path: Path) -> None:
    """Verifies that providing app_root redirects stdout/stderr to studio_stdio.log."""
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    try:
        sys.stdin = None
        sys.stdout = None
        sys.stderr = None

        ensure_safe_std_streams(tmp_path)

        assert sys.stdout is not None
        assert sys.stderr is not None
        sys.stdout.write("stdout log test\n")
        sys.stderr.write("stderr log test\n")

        log_path = tmp_path / "logs" / "studio_stdio.log"
        assert log_path.is_file()
        content = log_path.read_text(encoding="utf-8")
        assert "stdout log test" in content
        assert "stderr log test" in content
    finally:
        sys.stdin = orig_stdin
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr


def test_uvicorn_config_with_none_streams_does_not_crash() -> None:
    """Verifies that uvicorn configuration does not crash with AttributeError when std streams are None."""
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    try:
        sys.stdin = None
        sys.stdout = None
        sys.stderr = None

        ensure_safe_std_streams()

        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=8080,
            log_level="warning",
            access_log=False,
            log_config=None,
            use_colors=False,
        )
        assert config is not None
    finally:
        sys.stdin = orig_stdin
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr


def test_setup_studio_logging_routes_uvicorn(tmp_path: Path) -> None:
    """Verifies that setup_studio_logging routes uvicorn error logging to studio.log."""
    try:
        logger = setup_studio_logging(tmp_path)
        assert logger.name == "quantos.studio"

        uv_logger = logging.getLogger("uvicorn.error")
        handlers = [h for h in uv_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(handlers) >= 1
        assert any("studio.log" in str(h.baseFilename) for h in handlers)
    finally:
        for name in ("quantos.studio", "uvicorn", "uvicorn.error", "uvicorn.access"):
            lg = logging.getLogger(name)
            for h in list(lg.handlers):
                if isinstance(h, logging.FileHandler):
                    h.close()
                    lg.removeHandler(h)
