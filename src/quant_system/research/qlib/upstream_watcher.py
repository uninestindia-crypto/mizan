"""Monitors Microsoft Qlib upstream releases and prepares AI agent handoff work tickets.

When a new release or update is published on microsoft/qlib:
1. Detects the new release tag, notes, and published timestamp.
2. Updates local state in ``data/upstream/qlib_state.json``.
3. Generates an AI Agent Handoff Ticket in ``agent_context/work/inbox/`` so the owner
   can immediately assign it to an AI agent (Antigravity, Claude, Codex) to learn and adapt.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_QLIB_REPO = "microsoft/qlib"
DEFAULT_STATE_PATH = Path("data/upstream/qlib_state.json")
DEFAULT_INBOX_DIR = Path("agent_context/work/inbox")
DEFAULT_NOTIFICATIONS_PATH = Path("data/upstream/notifications.jsonl")


@dataclass(frozen=True, slots=True)
class QlibUpstreamRelease:
    tag_name: str
    published_at: str
    html_url: str
    body: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag_name": self.tag_name,
            "published_at": self.published_at,
            "html_url": self.html_url,
            "body": self.body,
            "name": self.name,
        }


Fetcher = Callable[[str], dict[str, Any] | None]


def _default_fetch(repo: str) -> dict[str, Any] | None:
    # 1. Try public GitHub API
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Mizan-Qlib-Watcher"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, ValueError, urllib.error.HTTPError):
        pass

    # 2. Fallback to `gh` CLI if installed
    gh = shutil.which("gh")
    if gh:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            res = subprocess.run(
                [gh, "api", f"repos/{repo}/releases/latest"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                creationflags=flags,
                check=False,
            )
            if res.returncode == 0:
                parsed = json.loads(res.stdout)
                if isinstance(parsed, dict):
                    return parsed
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass

    return None


class QlibUpstreamWatcher:
    """Watches Microsoft Qlib for updates and generates AI agent action tickets."""

    def __init__(
        self,
        repository: str = DEFAULT_QLIB_REPO,
        state_file: Path = DEFAULT_STATE_PATH,
        inbox_dir: Path = DEFAULT_INBOX_DIR,
        notifications_file: Path = DEFAULT_NOTIFICATIONS_PATH,
        fetcher: Fetcher | None = None,
    ) -> None:
        self.repository = repository
        self.state_file = state_file
        self.inbox_dir = inbox_dir
        self.notifications_file = notifications_file
        self._fetch = fetcher or _default_fetch

    def load_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {"last_seen_tag": None, "last_checked_utc": None}
        try:
            with self.state_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {"last_seen_tag": None, "last_checked_utc": None}

    def save_state(self, tag: str) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_seen_tag": tag,
            "last_checked_utc": datetime.now(UTC).isoformat(),
            "repository": self.repository,
        }
        with self.state_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def log_notification(self, release: QlibUpstreamRelease) -> None:
        self.notifications_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "microsoft/qlib",
            "tag": release.tag_name,
            "url": release.html_url,
            "summary": release.name or release.tag_name,
        }
        with self.notifications_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def generate_agent_handoff_ticket(self, release: QlibUpstreamRelease) -> Path:
        """Create an AI agent work ticket in the inbox for owner delegation."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        clean_tag = re.sub(r"[^a-zA-Z0-9.-]", "_", release.tag_name)
        now_date = datetime.now(UTC).strftime("%Y%m%d")
        ticket_file = self.inbox_dir / f"{now_date}-upstream-qlib-{clean_tag}.md"

        content = (
            f"# Upstream Work Ticket: Microsoft Qlib Update ({release.tag_name})\n\n"
            "STATUS: INBOX (Ready for AI Agent Assignment)\n"
            f"SOURCE: {self.repository}\n"
            f"RELEASE_TAG: {release.tag_name}\n"
            f"RELEASE_URL: {release.html_url}\n"
            f"DETECTED_UTC: {datetime.now(UTC).isoformat()}\n\n"
            "---\n\n"
            "## Upstream Announcement\n"
            f"**Title:** {release.name or release.tag_name}\n"
            f"**Published:** {release.published_at}\n\n"
            "### Release Notes\n"
            f"{release.body or 'No release notes provided.'}\n\n"
            "---\n\n"
            "## Instructions for the Assigned AI Agent (Antigravity / Claude / Codex)\n\n"
            "The owner has handed this upstream update to you. Please execute the following protocol:\n\n"
            "1. **Active Record**:\n"
            f"   - Move or copy this ticket into `agent_context/work/active/YYYYMMDD-agent-qlib-update-{clean_tag}.md`.\n"
            "   - Set `STATUS: ACTIVE` and declare owned paths.\n\n"
            "2. **Inspect Upstream Changes**:\n"
            f"   - Examine new models, factors, or performance fixes introduced in `{release.tag_name}`.\n"
            f"   - Reference local repo at `d:/Quant OS Project/qlib-main` or GitHub compare: `{release.html_url}`.\n\n"
            "3. **Incorporate into Mizan**:\n"
            "   - Check if new mathematical alpha factors belong in `src/quant_system/research/qlib/alpha158.py`.\n"
            "   - Check if new modeling architectures belong in `src/quant_system/research/qlib/adapter.py`.\n"
            "   - Maintain Mizan's strict invariants: zero lookahead bias, point-in-time causality, and strict typing.\n\n"
            "4. **Verify Quality Gates**:\n"
            "   - Run `pytest tests/test_qlib_bridge.py -v`.\n"
            "   - Verify `scripts/run-gates.ps1` (or relevant slice tests).\n\n"
            "5. **Complete Work Record**:\n"
            "   - Move active record to `agent_context/work/completed/`.\n"
        )
        with ticket_file.open("w", encoding="utf-8") as f:
            f.write(content)
        return ticket_file

    def check(self, force_notify: bool = False) -> dict[str, Any]:
        """Check upstream repository for new release."""
        raw = self._fetch(self.repository)
        if not raw:
            return {"checked": False, "update_available": False, "error": "Fetch failed"}

        tag = str(raw.get("tag_name") or "")
        if not tag:
            return {"checked": True, "update_available": False, "note": "No tag found"}

        release = QlibUpstreamRelease(
            tag_name=tag,
            published_at=str(raw.get("published_at") or ""),
            html_url=str(raw.get("html_url") or ""),
            body=str(raw.get("body") or ""),
            name=str(raw.get("name") or ""),
        )

        state = self.load_state()
        last_seen = state.get("last_seen_tag")
        is_new = (last_seen != tag) or force_notify

        ticket_path: Path | None = None
        if is_new:
            self.save_state(tag)
            self.log_notification(release)
            ticket_path = self.generate_agent_handoff_ticket(release)

        return {
            "checked": True,
            "update_available": is_new,
            "tag": tag,
            "last_seen_tag": last_seen,
            "ticket_file": str(ticket_path) if ticket_path else None,
            "release": release.to_dict(),
        }


def check_qlib_upstream(force_notify: bool = False) -> dict[str, Any]:
    """Convenience helper."""
    return QlibUpstreamWatcher().check(force_notify=force_notify)
