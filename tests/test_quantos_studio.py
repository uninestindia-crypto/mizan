"""Tests for QuantOS Desktop Studio Host and Zero-Console Launcher."""

from __future__ import annotations

import os
from pathlib import Path

from quantos_studio import (
    configure_drive_isolation,
    find_app_browser,
    find_free_port,
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
