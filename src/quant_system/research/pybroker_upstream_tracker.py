"""Upstream PyBroker release tracker and AI Agent hand-off briefing generator for Mizan.

Monitors upstream GitHub and PyPI releases for PyBroker (lib-pybroker).
When an upstream update is detected:
1. Surfaces an update alert through Mizan's server and status endpoints.
2. Automatically generates an AI Agent Hand-off Briefing in agent_context/handoffs/
   with an exact prompt for the owner to give to an AI agent (Antigravity/Claude Code/Cursor).
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PYBROKER_GITHUB_REPO = "edtechre/pybroker"
PYPI_URL = "https://pypi.org/pypi/lib-pybroker/json"
STATE_FILE_NAME = "pybroker_upstream_state.json"
CACHE_SECONDS = 6 * 3600  # 6 hours
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version_tuple(ver_str: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.match(ver_str.strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def is_version_newer(latest: str, current: str) -> bool:
    new_v = parse_version_tuple(latest)
    old_v = parse_version_tuple(current)
    return new_v is not None and old_v is not None and new_v > old_v


def get_installed_pybroker_version() -> str:
    """Reads current PyBroker version from local source or state."""
    try:
        import pybroker

        return str(getattr(pybroker, "__version__", "2.0.1"))
    except Exception:
        return "2.0.1"


def get_data_dir() -> Path:
    from quant_system.server.v2.paths import app_root

    return app_root() / "data"


def get_state_file_path() -> Path:
    return get_data_dir() / STATE_FILE_NAME


def fetch_from_pypi() -> dict[str, Any] | None:
    """Queries PyPI for the latest lib-pybroker release metadata."""
    req = urllib.request.Request(
        PYPI_URL,
        headers={"User-Agent": "Mizan-QuantOS-PyBrokerTracker/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            info = data.get("info", {})
            version = info.get("version")
            if version:
                return {
                    "version": version,
                    "url": info.get("project_url")
                    or f"https://pypi.org/project/lib-pybroker/{version}/",
                    "summary": info.get("summary") or "Algorithmic trading with machine learning",
                    "published_at": None,
                    "source": "pypi",
                }
    except Exception as e:
        logger.debug("PyPI fetch failed: %s", e)
    return None


def fetch_from_github() -> dict[str, Any] | None:
    """Queries GitHub API for the latest PyBroker release."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{PYBROKER_GITHUB_REPO}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Mizan-QuantOS-PyBrokerTracker/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tag = str(data.get("tag_name", "")).lstrip("v")
            if tag:
                return {
                    "version": tag,
                    "url": data.get("html_url")
                    or f"https://github.com/{PYBROKER_GITHUB_REPO}/releases/tag/v{tag}",
                    "summary": str(data.get("body", ""))[:1200],
                    "published_at": data.get("published_at"),
                    "source": "github",
                }
    except Exception as e:
        logger.debug("GitHub releases fetch failed: %s", e)
    return None


def generate_agent_handoff_prompt(
    latest_ver: str,
    current_ver: str,
    release_url: str,
    release_notes: str,
) -> str:
    """Generates the prompt for the owner to give to an AI agent."""
    return f"""A new upstream release of PyBroker (v{latest_ver}) has been published (current in Mizan: v{current_ver}).
Please perform the following update steps:

1. Review Release Notes & Diff:
   - URL: {release_url}
   - Highlights:
{release_notes}

2. Sync Engine Updates:
   - Run: `python scripts/sync_pybroker_update.py --version {latest_ver}`
   - Inspect changes to `src/pybroker/` and ensure `@njit(cache=True)` and zero-lookahead invariants hold.

3. Learn & Update Skills:
   - Review any new indicators, kernels, or multi-interval capabilities in PyBroker.
   - Update agent skills in `skills/` and `.agents/skills/` and `agent_context/skills/pybroker_engine_guide.md`.

4. Run Mizan Regression Gates:
   - Run: `pytest tests/test_pybroker_adapter.py -v`
   - Run: `pytest tests/test_pybroker_upstream_tracker.py -v`
   - Run: `pytest tests/test_updates.py -v`

5. Update Version Ledger:
   - Update `pyproject.toml` dependencies if requirements changed.
   - Save the new version in `data/{STATE_FILE_NAME}`.
"""


def write_handoff_briefing_file(
    latest_ver: str,
    current_ver: str,
    release_url: str,
    release_notes: str,
) -> Path:
    """Writes the owner-to-agent briefing file in agent_context/handoffs/."""
    from quant_system.server.v2.paths import app_root

    handoff_dir = app_root() / "agent_context" / "handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    briefing_file = handoff_dir / "PYBROKER-UPDATE-BRIEFING.md"

    prompt_text = generate_agent_handoff_prompt(latest_ver, current_ver, release_url, release_notes)

    gen_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    content = (
        "# Mizan Upstream PyBroker Update Briefing\n\n"
        f"**Generated UTC**: {gen_time}\n"
        f"**Current Mizan PyBroker**: `v{current_ver}`\n"
        f"**New Upstream PyBroker**: `v{latest_ver}`\n"
        f"**Release URL**: [{release_url}]({release_url})\n\n"
        "---\n\n"
        "## 📋 Owner Action: Copy & Hand This Prompt to Your AI Agent\n\n"
        "Copy the prompt block below and paste it into your AI assistant (Antigravity, Claude Code, or Cursor):\n\n"
        f"```markdown\n{prompt_text}\n```\n\n"
        "---\n\n"
        "## 📝 Upstream Release Summary\n\n"
        f"{release_notes or 'No additional release notes provided.'}\n"
    )
    briefing_file.write_text(content, encoding="utf-8")
    return briefing_file


class PyBrokerUpstreamTracker:
    """Manages PyBroker upstream version tracking and notifications."""

    def __init__(self, current_version: str | None = None) -> None:
        self.current_version = current_version or get_installed_pybroker_version()
        self._lock = threading.Lock()
        self._cached: tuple[float, dict[str, Any]] | None = None

    def check(self, force: bool = False) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            if not force and self._cached and (now - self._cached[0] < CACHE_SECONDS):
                return self._cached[1]

            result = self._check_live()
            self._cached = (now, result)
            self._persist_state(result)
            return result

    def _check_live(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "current_version": self.current_version,
            "latest_version": self.current_version,
            "update_available": False,
            "release_url": f"https://github.com/{PYBROKER_GITHUB_REPO}",
            "notes": "",
            "checked": False,
            "briefing_path": None,
            "handoff_prompt": None,
        }

        # Check PyPI first, then GitHub
        release = fetch_from_pypi() or fetch_from_github()
        if not release:
            return {**base, "checked": False}

        latest_ver = str(release.get("version", self.current_version))
        update_avail = is_version_newer(latest_ver, self.current_version)
        url = str(release.get("url", base["release_url"]))
        notes = str(release.get("summary", ""))

        briefing_path = None
        handoff_prompt = None

        if update_avail:
            handoff_prompt = generate_agent_handoff_prompt(
                latest_ver=latest_ver,
                current_ver=self.current_version,
                release_url=url,
                release_notes=notes,
            )
            try:
                p = write_handoff_briefing_file(
                    latest_ver=latest_ver,
                    current_ver=self.current_version,
                    release_url=url,
                    release_notes=notes,
                )
                briefing_path = str(p)
            except Exception as e:
                logger.warning("Could not write handoff briefing file: %s", e)

        return {
            "current_version": self.current_version,
            "latest_version": latest_ver,
            "update_available": update_avail,
            "release_url": url,
            "notes": notes,
            "checked": True,
            "briefing_path": briefing_path,
            "handoff_prompt": handoff_prompt,
        }

    def _persist_state(self, state: dict[str, Any]) -> None:
        try:
            state_file = get_state_file_path()
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug("Failed to persist pybroker state: %s", e)


_default_tracker: PyBrokerUpstreamTracker | None = None


def get_pybroker_tracker() -> PyBrokerUpstreamTracker:
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = PyBrokerUpstreamTracker()
    return _default_tracker


if __name__ == "__main__":
    force_check = "--force" in sys.argv
    tracker = get_pybroker_tracker()
    status = tracker.check(force=force_check)
    print("=" * 60)
    print("MIZAN PYBROKER UPSTREAM STATUS")
    print("=" * 60)
    print(f"Current Installed Version : {status['current_version']}")
    print(f"Latest Upstream Version    : {status['latest_version']}")
    print(f"Update Available           : {status['update_available']}")
    if status["update_available"]:
        print(f"Release URL                : {status['release_url']}")
        print(f"Briefing File              : {status['briefing_path']}")
        print("\n=== AI AGENT HAND-OFF PROMPT ===")
        print(status["handoff_prompt"])
    else:
        print("PyBroker is fully up to date.")
    print("=" * 60)
