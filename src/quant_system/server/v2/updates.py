"""Is a newer QuantOS release available? Read from GitHub releases, cached, never in the way.

The check asks GitHub for the latest release of the repository. It tries the public API first (works
when the repository is public) and, if GitHub answers 404 or 403 (a private repository or a rate
limit), the signed-in GitHub command line (``gh``) on this computer, which is how the repository's
owner is already signed in. If neither answers, the app simply shows nothing: an update check must
never produce an error a person has to deal with.

Nothing is downloaded or installed here. The notice links to the release page; installing is the
person's decision.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

REPOSITORY = os.environ.get("QUANTOS_UPDATE_REPO", "uninestindia-crypto/mizan")
CACHE_SECONDS = 6 * 3600
_NOTES_LIMIT = 1500
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

Fetcher = Callable[[], dict[str, Any] | None]


@dataclass(frozen=True, slots=True)
class ReleaseAssets:
    """The files a one-click update needs from the newest release."""

    version: str
    installer_name: str
    installer_url: str
    checksums_url: str | None


def _asset_url(assets: list[Any], matches: Callable[[str], bool]) -> tuple[str, str] | None:
    """``(name, download address)`` of the first release file whose name matches, or None."""
    for asset in assets:
        name = str(asset.get("name", "")) if isinstance(asset, dict) else ""
        url = str(asset.get("browser_download_url") or "") if isinstance(asset, dict) else ""
        if name and url and matches(name):
            return name, url
    return None


def parse_version(text: str) -> tuple[int, int, int] | None:
    """``v2.1.0`` or ``2.1.0`` as a comparable tuple; anything else (a pre-release tag) is None."""
    match = _VERSION.match(text.strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def is_newer(latest: str, current: str) -> bool:
    new, old = parse_version(latest), parse_version(current)
    return new is not None and old is not None and new > old


def _public_api(repository: str) -> dict[str, Any] | None:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "QuantOS-update-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.HTTPError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _github_cli(repository: str) -> dict[str, Any] | None:
    gh = shutil.which("gh")
    if gh is None:
        return None
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        completed = subprocess.run(
            [gh, "api", f"repos/{repository}/releases/latest"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
            creationflags=flags,
            stdin=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            return None
        parsed = json.loads(completed.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return parsed if isinstance(parsed, dict) else None


def fetch_latest_release(repository: str = REPOSITORY) -> dict[str, Any] | None:
    return _public_api(repository) or _github_cli(repository)


class UpdateChecker:
    def __init__(self, current: str, fetch: Fetcher | None = None) -> None:
        self._current = current
        self._fetch: Fetcher = fetch or fetch_latest_release
        self._lock = threading.Lock()
        self._cached: tuple[float, dict[str, Any]] | None = None
        self._release: dict[str, Any] | None = None

    def install_assets(self) -> ReleaseAssets | None:
        """The installer and fingerprint file of the newest release, when it is newer than this one."""
        with self._lock:
            release, cached = self._release, self._cached
        if release is None or cached is None or not cached[1]["update_available"]:
            return None
        files = [a for a in release.get("assets") or [] if isinstance(a, dict)]
        installer = _asset_url(files, lambda name: name.endswith("_Setup.exe"))
        sums = _asset_url(files, lambda name: name.upper().startswith("SHA256SUMS"))
        if installer is None:
            return None
        return ReleaseAssets(
            str(cached[1]["latest"]), installer[0], installer[1], sums[1] if sums else None
        )

    def check(self, force: bool = False) -> dict[str, Any]:
        with self._lock:
            if not force and self._cached and time.monotonic() - self._cached[0] < CACHE_SECONDS:
                return self._cached[1]
            result = self._read()
            # A failed check is retried soon (a minute), a good one stays for hours.
            age = 0.0 if result["checked"] else CACHE_SECONDS - 60.0
            self._cached = (time.monotonic() - age, result)
            return result

    def _read(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "current": self._current,
            "latest": None,
            "update_available": False,
            "url": None,
            "notes": "",
            "published_at": None,
            "installer": None,
            "checked": False,
        }
        try:
            release = self._fetch()
        except Exception:  # an update check must never raise into the app
            release = None
        self._release = release or None
        if not release:
            return base
        tag = str(release.get("tag_name") or "")
        latest = tag.lstrip("v") if parse_version(tag) else None
        if latest is None or release.get("draft") or release.get("prerelease"):
            return {**base, "checked": True}
        assets = [
            str(a.get("name", "")) for a in release.get("assets") or [] if isinstance(a, dict)
        ]
        return {
            **base,
            "latest": latest,
            "update_available": is_newer(latest, self._current),
            "url": str(release.get("html_url") or "") or None,
            "notes": str(release.get("body") or "")[:_NOTES_LIMIT],
            "published_at": release.get("published_at"),
            "installer": next((a for a in assets if a.endswith("_Setup.exe")), None),
            "checked": True,
            "pybroker_update": self.check_pybroker(force=False),
        }

    def check_pybroker(self, force: bool = False) -> dict[str, Any]:
        """Checks upstream PyBroker release status and AI agent hand-off prompt."""
        try:
            from quant_system.research.pybroker_upstream_tracker import get_pybroker_tracker

            return get_pybroker_tracker().check(force=force)
        except Exception as e:
            return {
                "current_version": "2.0.1",
                "latest_version": "2.0.1",
                "update_available": False,
                "error": str(e),
                "checked": False,
            }

    def changelog(self) -> list[dict[str, Any]]:
        curr_ver = self._current.lstrip("v")
        results: list[dict[str, Any]] = []
        found_current = False
        for item in OFFLINE_CHANGELOG:
            entry = dict(item)
            is_cur = entry["version"] == curr_ver
            if is_cur:
                found_current = True
            entry["is_current"] = is_cur
            results.append(entry)
        if results and not found_current:
            results[0]["is_current"] = True
        return results


OFFLINE_CHANGELOG: list[dict[str, Any]] = [
    {
        "version": "3.0.0",
        "date": "2026-10-08",
        "title": "Mizan Quant OS: Quant SLM Engine, Microsoft Qlib Multi-Factor Architecture & Factory-New Installer",
        "whats_new": [
            "Mizan Quant OS brand unification: combined institutional quantitative trading, factor research, and Mizan Shariah wealth compliance in one unified operating system",
            "Quant SLM: local Small Language Model for ultra-fast, accurate market intelligence, combining deep multi-factor alpha signals, technical indicators, and embedding-gemma-2 / XRIV features",
            "Microsoft Qlib integration: high-performance quantitative alpha factor library, multi-factor models, and automated upstream synchronization pipeline",
            "Factory-new laptop installer: standalone, drive-isolated Inno Setup distribution (MizanQuantOS_v3.0.0_Setup.exe) with bundled runtime and zero C-drive leakage",
            "Upstox live market feeds: low-latency price feeds, quote streams, and portfolio synchronization",
        ],
        "fixes": [
            "Enforced strict drive-isolated local execution with zero C: drive path leakage",
            "Corporate actions provider caching with automatic historical symbol alias mapping",
            "Fixed walk-forward validation matrix bounds and purged look-ahead data leakage",
        ],
        "improvements": [
            "Institutional multi-factor backtesting performance and real-time risk governor checks",
            "Comprehensive packaging with cryptographic Software Bill of Materials (SBOM) and SHA-256 verification manifests",
        ],
        "unchanged_protections": [
            "Keys stay strictly encrypted in local Windows Credential Manager and are never sent to external servers",
            "Zero unauthorized live-broker order execution — all autonomous decisions strictly sandboxed and verified",
            "Halal screening rules remain determined by deterministic algorithmic criteria (DJIM/AAOIFI), never unverified AI hallucination",
            "Decimal-exact financial accounting and statutory NSE transaction cost schedules preserved",
        ],
    },
    {
        "version": "2.5.0",
        "date": "2026-10-07",
        "title": "Copilot Assistant, Independent Second Opinions, Your Own Agents & Live Prices",
        "whats_new": [
            "Copilot: ask a question from any screen with the Copilot button at the top (or Ctrl+J). It works with no AI key, answering from QuantOS's own data, and takes open-ended questions once you add an AI key in Settings. It can suggest a screen to open and can never place an order",
            "Second opinions: have several AI models read the same facts about a stock, each on its own, and see where they agree, where they differ and why. Agreement between AI models is not evidence that a stock will do well",
            "Agents: create, edit, run and delete your own saved agents on the new Agents screen, with four ready-made ones that need no AI key",
            "Live prices from your Upstox key, read-only: every price says whether it is Live, Delayed, Last close or Not available",
            "News headlines for a stock, with a rough keyword tone that is clearly labelled as rough",
        ],
        "fixes": [
            "A key pasted with a space or a line break is refused with a plain message instead of failing later",
            "The Copilot button and panel fit every window width, from a phone-sized window to a wide monitor",
            "Pop-up windows return you to where you were when they close, and form fields are read out with their hints",
        ],
        "improvements": [
            "Home shows an End of day label on prices when the market is closed",
            "Danger buttons are easier to read in dark mode",
        ],
        "unchanged_protections": [
            "Keys stay in Windows Credential Manager and are sent only to the provider they belong to",
            "QuantOS still never places orders with any broker, and neither can the Copilot",
            "Halal results come only from the QuantOS screener, never from an AI model",
            "Nothing in QuantOS has shown an edge that survives real trading costs, and AI opinions do not change that",
        ],
    },
    {
        "version": "2.4.0",
        "date": "2026-10-05",
        "title": "Import All Your Keys From a .env File, Paper-Book Order Inbox & Health Checks",
        "whats_new": [
            "Import all your keys at once: choose your .env or .env.local files in Settings, review what was found, and save them in one step",
            "Paper books say when their orders are out of date and offer a copy-ready order ticket",
            "Record what you did with each paper-book order, see what is waiting, and compare your fills",
            "Optional Slack, Discord or ntfy message when a paper book has orders to place; it never carries a stock, quantity or price",
            "Liveness and readiness checks, with an early warning before the NSE holiday list runs out",
        ],
        "fixes": [
            "The live trading dashboard now runs inside the desktop app",
            "Honest log times and audit labels in paper-pilot sessions",
            "Fits phone-sized screens and passes colour-contrast checks; Mizan Shariah sample data is labelled honestly",
            "Desktop launch, single-instance lock and shortcut logo fixes",
        ],
        "improvements": [
            "Mizan Shariah screens follow the QuantOS design system",
        ],
        "unchanged_protections": [
            "Keys stay in Windows Credential Manager and are sent only to the provider they belong to",
            "QuantOS still never places orders with any broker",
            "Existing paper books, portfolios and evidence are kept when you update over an older install",
            "Decimal-exact accounting and statutory NSE cost schedules are unchanged",
        ],
    },
    {
        "version": "2.3.0",
        "date": "2026-10-05",
        "title": "Unified Desktop Studio & Mizan Shariah Wealth Engine",
        "whats_new": [
            "Unified desktop studio with instant 1-click mode switch between Institutional Quant and Mizan Shariah Wealth Engine",
            "Mizan Shariah screening engine with customizable screening rules (DJIM, AAOIFI)",
            "Automated purification calculation and charity zakat ledger for Islamic wealth compliance",
            "Download and cache official NSE symbol changes with historical alias merging (e.g. HEG → HEGAM)",
            "Portfolio purifier and halal wealth intelligence tools",
        ],
        "fixes": [
            "Setup onboarding wizard remembers current step across reloads",
            "Never overwrite saved corporate action authorities with empty results on network timeouts",
        ],
        "improvements": [
            "Harmonized Mizan Shariah frontend with Apple-grade QuantOS design system",
            "High-contrast accessible theme toggles and responsive layout refinements",
        ],
        "unchanged_protections": [
            "Zero live-broker order routing — all executions strictly paper/shadow simulated",
            "Decimal-exact financial accounting and statutory NSE transaction cost schedules preserved",
            "Full offline self-contained operation without external cloud dependencies or telemetry",
            "Immutable content-addressed evidence store remains write-protected",
        ],
    },
    {
        "version": "2.2.0",
        "date": "2026-10-04",
        "title": "Automated Paper Books & Lightning AI Provider",
        "whats_new": [
            "Paper books keep themselves up to date automatically after each NSE market close",
            "Native Lightning AI provider support for ultra-low latency model calls",
            "Upstox analytics token integration and Moonshot model architecture",
        ],
        "fixes": [
            "Hardened corporate actions provider fallback on connectivity blips",
            "Persistent paper engine state synchronization across app restarts",
        ],
        "improvements": [
            "Background auto-updater runs with zero CPU overhead and bounded sleep",
        ],
        "unchanged_protections": [
            "Existing paper trading portfolios and historical ledgers preserved without loss",
            "Strict point-in-time bar history constraints maintained",
        ],
    },
    {
        "version": "2.1.0",
        "date": "2026-10-04",
        "title": "In-App Update Checker, Native Paper Trading & AI Hub",
        "whats_new": [
            "In-app update notifications when new releases are published on GitHub",
            "Quick 'Update market data' keeping full ten-year bar history",
            "Start and follow live paper trading books directly within the desktop UI",
            "Built-in market data downloader for factory-new laptops without pre-existing data",
            "Direct support for Google Gemini, DeepSeek, and Mistral API keys in AI Assistant",
            "Auto-discovery of local market data and browser-based CLI authentication",
        ],
        "fixes": [
            "Repaired statutory transaction cost display across order sizes",
            "Chat requests no longer force strict JSON mode and retry safely without refused temperature",
            "Stopped copying saved API keys into plaintext .env file",
        ],
        "improvements": [
            "Sub-second market data search and symbol lookup across 3,000+ NSE tickers",
        ],
        "unchanged_protections": [
            "Strict local loopback trust boundary — zero remote access and no external telemetry",
            "Purged and embargoed walk-forward validation prevents look-ahead leakage",
        ],
    },
    {
        "version": "2.0.1",
        "date": "2026-10-03",
        "title": "Windows Shell Integration & Multi-Agent Bridge",
        "whats_new": [
            "Fixed taskbar icon identity and tray integration on Windows x64",
            "Multi-agent CLI bridge and 1-click credential hub",
        ],
        "fixes": [
            "Clean exit handling on Windows process shutdowns",
        ],
        "improvements": [
            "Optimized asset preloading in WebView2 container",
        ],
        "unchanged_protections": [
            "100% backward compatibility with QuantOS v1 evidence store and historical runs",
        ],
    },
    {
        "version": "2.0.0",
        "date": "2026-10-03",
        "title": "QuantOS 2.0 Retail Platform & Native Window Runner",
        "whats_new": [
            "Complete consumer-grade retail interface (QuantOS 2.0) with Strategy Lab and Market Index",
            "Native Windows desktop runner powered by WebView2 without black terminal popups",
            "Versioned operation API v2 with local trust boundary",
        ],
        "fixes": [
            "Fixed journey script execution inside native desktop window container",
        ],
        "improvements": [
            "Instant UI responsiveness and clean semantic navigation",
        ],
        "unchanged_protections": [
            "Core risk governor, immutable content-addressed evidence store, and Decimal ledger invariants untouched",
        ],
    },
]
