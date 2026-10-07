"""The installer carries what a factory-new laptop is missing, and checks it came from Microsoft."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISS = (ROOT / "installer" / "quant_os_setup.iss").read_text(encoding="utf-8")
BUILD = (ROOT / "scripts" / "build-windows-installer.ps1").read_text(encoding="utf-8")
WEBVIEW2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def test_the_installer_installs_the_window_component_only_when_it_is_missing() -> None:
    assert "#ifdef WebView2Setup" in ISS  # a development build without it still compiles
    assert "function WebView2Missing" in ISS
    assert ISS.count("Check: WebView2Missing") >= 2  # both the copy and the run are conditional
    assert "/silent /install" in ISS


def test_the_installer_looks_for_the_component_where_microsoft_says_it_registers() -> None:
    assert WEBVIEW2_GUID in ISS
    assert "HKLM32" in ISS and "HKCU" in ISS
    assert "'pv'" in ISS


def _component_run_line() -> str:
    lines = [line for line in ISS.splitlines() if "MicrosoftEdgeWebview2Setup.exe" in line]
    return "\n".join(line for line in lines if "Parameters" in line)


def test_a_failed_component_install_does_not_stop_quantos_installing() -> None:
    """With no internet the app still opens, in an Edge window, so the install must carry on."""
    line = _component_run_line()
    assert "waituntilterminated" in line and "runhidden" in line


def test_the_build_fetches_the_component_from_microsoft_and_checks_its_signature() -> None:
    assert "https://go.microsoft.com/fwlink/p/?LinkId=2124703" in BUILD
    assert "Get-AuthenticodeSignature" in BUILD and "Microsoft Corporation" in BUILD
    assert "/DWebView2Setup=" in BUILD


def test_a_release_cannot_quietly_skip_the_component() -> None:
    assert "-SkipWebView2" in BUILD  # the only way to build without it is to say so
    assert "throw" in BUILD[BUILD.index("WebView2") :]


def test_the_installer_points_support_and_updates_at_the_real_repository() -> None:
    assert "https://github.com/uninestindia-crypto/mizan" in ISS
    assert "quant-system/quantos" not in ISS
