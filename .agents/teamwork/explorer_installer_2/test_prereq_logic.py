"""Unit tests for prerequisites reference implementation."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from prerequisites import (
    OFFICIAL_MICROSOFT_DOMAINS,
    VC_REDIST_X64_URL,
    WEBVIEW2_BOOTSTRAPPER_URL,
    WEBVIEW2_STANDALONE_X64_URL,
    check_vc_redist_installed,
    check_webview2_installed,
    find_offline_prerequisite,
    interpret_vcredist_exit_code,
    interpret_webview2_exit_code,
    verify_microsoft_connectivity,
)


def test_urls_and_domains():
    assert VC_REDIST_X64_URL.startswith("https://aka.ms")
    assert WEBVIEW2_BOOTSTRAPPER_URL.startswith("https://go.microsoft.com")
    assert WEBVIEW2_STANDALONE_X64_URL.startswith("https://go.microsoft.com")
    assert all("microsoft.com" in d or d == "aka.ms" for d in OFFICIAL_MICROSOFT_DOMAINS)


def test_interpret_vcredist_exit_codes():
    ok, reboot, msg = interpret_vcredist_exit_code(0)
    assert ok is True and reboot is False

    ok, reboot, msg = interpret_vcredist_exit_code(3010)
    assert ok is True and reboot is True

    ok, reboot, msg = interpret_vcredist_exit_code(1638)
    assert ok is True and reboot is False
    assert "Newer version" in msg

    ok, reboot, msg = interpret_vcredist_exit_code(1603)
    assert ok is False and reboot is False


def test_interpret_webview2_exit_codes():
    ok, reboot, msg = interpret_webview2_exit_code(0)
    assert ok is True and reboot is False

    ok, reboot, msg = interpret_webview2_exit_code(1)
    assert ok is False and reboot is False


def test_find_offline_prerequisite(tmp_path: Path):
    assert find_offline_prerequisite("vc_redist.x64.exe", [tmp_path]) is None

    # Test in root
    f1 = tmp_path / "vc_redist.x64.exe"
    f1.write_text("mock")
    assert find_offline_prerequisite("vc_redist.x64.exe", [tmp_path]) == f1

    # Test in prerequisites subfolder
    f1.unlink()
    sub = tmp_path / "prerequisites"
    sub.mkdir()
    f2 = sub / "vc_redist.x64.exe"
    f2.write_text("mock")
    assert find_offline_prerequisite("vc_redist.x64.exe", [tmp_path]) == f2


def test_live_detection_on_host():
    vc_status = check_vc_redist_installed()
    print(f"VC++ Status: {vc_status}")
    assert vc_status.installed is True
    assert vc_status.version is not None

    wv_status = check_webview2_installed()
    print(f"WebView2 Status: {wv_status}")
    assert wv_status.installed is True
    assert wv_status.version is not None


if __name__ == "__main__":
    test_urls_and_domains()
    test_interpret_vcredist_exit_codes()
    test_interpret_webview2_exit_codes()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_find_offline_prerequisite(Path(td))
    test_live_detection_on_host()
    print("ALL TESTS PASSED SUCCESSFULLY!")
