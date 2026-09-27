"""QuantOS Automated Prerequisite Detection & Silent Installer Reference Implementation.

Contains logic for:
1. Detecting Microsoft Visual C++ 2015-2022 x64 Redistributable via registry.
2. Detecting Microsoft Edge WebView2 Evergreen Runtime via registry.
3. Official Microsoft URL endpoints.
4. Silent command-line flags and exit code interpretation.
5. Network connectivity pre-flight check (official Microsoft domains only).
6. Graceful offline fallback and local candidate discovery.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Authoritative official Microsoft URLs
VC_REDIST_X64_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
WEBVIEW2_BOOTSTRAPPER_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
WEBVIEW2_STANDALONE_X64_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124701"

# Allowed Microsoft domains for network requests (fail-closed security)
OFFICIAL_MICROSOFT_DOMAINS = (
    "aka.ms",
    "go.microsoft.com",
    "download.visualstudio.microsoft.com",
    "msedge.sf.dl.delivery.mp.microsoft.com",
)

# Registry Keys
VC_REG_PATHS = [
    r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64",
    r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64",
]

WEBVIEW2_REG_PATHS = [
    # (hive_name, subkey)
    ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    ("HKLM", r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    ("HKCU", r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
]


@dataclass
class PrerequisiteStatus:
    name: str
    installed: bool
    version: str | None
    registry_path: str | None
    details: dict[str, Any]


def check_vc_redist_installed() -> PrerequisiteStatus:
    """Checks whether Microsoft Visual C++ 2015-2022 x64 is installed."""
    if sys.platform != "win32":
        return PrerequisiteStatus(
            name="VC++ 2015-2022 x64",
            installed=True,
            version="mock-non-windows",
            registry_path=None,
            details={"mock": True},
        )

    import winreg

    for subkey in VC_REG_PATHS:
        for flags in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey, 0, flags) as key:
                    installed_val, _ = winreg.QueryValueEx(key, "Installed")
                    if installed_val == 1:
                        try:
                            version_val, _ = winreg.QueryValueEx(key, "Version")
                        except OSError:
                            version_val = "14.x"
                        try:
                            major_val, _ = winreg.QueryValueEx(key, "Major")
                        except OSError:
                            major_val = 14
                        try:
                            minor_val, _ = winreg.QueryValueEx(key, "Minor")
                        except OSError:
                            minor_val = 0

                        return PrerequisiteStatus(
                            name="VC++ 2015-2022 x64",
                            installed=True,
                            version=str(version_val),
                            registry_path=f"HKLM\\{subkey}",
                            details={"major": major_val, "minor": minor_val},
                        )
            except OSError:
                continue

    return PrerequisiteStatus(
        name="VC++ 2015-2022 x64",
        installed=False,
        version=None,
        registry_path=None,
        details={},
    )


def check_webview2_installed() -> PrerequisiteStatus:
    """Checks whether Microsoft Edge WebView2 Evergreen Runtime is installed."""
    if sys.platform != "win32":
        return PrerequisiteStatus(
            name="Edge WebView2",
            installed=True,
            version="mock-non-windows",
            registry_path=None,
            details={"mock": True},
        )

    import winreg

    for hive_name, subkey in WEBVIEW2_REG_PATHS:
        root_hive = winreg.HKEY_LOCAL_MACHINE if hive_name == "HKLM" else winreg.HKEY_CURRENT_USER
        for flags in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(root_hive, subkey, 0, flags) as key:
                    pv_val, _ = winreg.QueryValueEx(key, "pv")
                    if pv_val and str(pv_val).strip() not in ("", "0.0.0.0"):
                        try:
                            location_val, _ = winreg.QueryValueEx(key, "location")
                        except OSError:
                            location_val = None

                        return PrerequisiteStatus(
                            name="Edge WebView2",
                            installed=True,
                            version=str(pv_val).strip(),
                            registry_path=f"{hive_name}\\{subkey}",
                            details={"location": location_val},
                        )
            except OSError:
                continue

    return PrerequisiteStatus(
        name="Edge WebView2",
        installed=False,
        version=None,
        registry_path=None,
        details={},
    )


def verify_microsoft_connectivity(timeout_seconds: float = 5.0) -> tuple[bool, str]:
    """Tests connectivity to verified official Microsoft endpoints only."""
    url = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            if resp.status in (200, 301, 302):
                return True, f"Connected (HTTP {resp.status})"
            return False, f"Unexpected HTTP status: {resp.status}"
    except urllib.error.URLError as exc:
        return False, f"Network unreachable: {exc.reason}"
    except Exception as exc:
        return False, f"Connection error: {exc}"


def find_offline_prerequisite(filename: str, search_roots: list[Path]) -> Path | None:
    """Searches given roots for offline prerequisite installer files."""
    for root in search_roots:
        candidate = root / filename
        if candidate.is_file():
            return candidate
        prereqs_dir = root / "prerequisites" / filename
        if prereqs_dir.is_file():
            return prereqs_dir
    return None


def interpret_vcredist_exit_code(code: int) -> tuple[bool, bool, str]:
    """Interprets VC++ redistributable installer exit codes.

    Returns:
        (success: bool, reboot_required: bool, message: str)
    """
    if code == 0:
        return True, False, "Success (Exit code 0)"
    if code == 3010:
        return True, True, "Success, Reboot Required (Exit code 3010)"
    if code == 1638:
        return True, False, "Success, Newer version already installed (Exit code 1638)"
    if code == 1618:
        return False, False, "Failure: Another installation is already in progress (Exit code 1618)"
    if code == 1602:
        return False, False, "Failure: User cancelled installation (Exit code 1602)"
    if code == 1603:
        return False, False, "Failure: Fatal error during installation (Exit code 1603)"
    return False, False, f"Failure: Unrecognized error code {code}"


def interpret_webview2_exit_code(code: int) -> tuple[bool, bool, str]:
    """Interprets Edge WebView2 installer exit codes.

    Returns:
        (success: bool, reboot_required: bool, message: str)
    """
    if code == 0:
        return True, False, "Success (Exit code 0)"
    return False, False, f"Failure: Exit code {code}"
