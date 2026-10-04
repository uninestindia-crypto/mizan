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
from typing import Any

REPOSITORY = os.environ.get("QUANTOS_UPDATE_REPO", "uninestindia-crypto/quant-system")
CACHE_SECONDS = 6 * 3600
_NOTES_LIMIT = 1500
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

Fetcher = Callable[[], dict[str, Any] | None]


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
        }
