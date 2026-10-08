#!/usr/bin/env python3
"""CLI script to monitor upstream Microsoft Qlib releases and notify Mizan.

Usage:
    python scripts/watch_upstream_qlib.py
    python scripts/watch_upstream_qlib.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to pythonpath
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quant_system.research.qlib.upstream_watcher import QlibUpstreamWatcher  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor Microsoft Qlib for upstream updates and generate AI agent work tickets."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force ticket generation and notification even if the tag matches last seen.",
    )
    parser.add_argument(
        "--repo",
        default="microsoft/qlib",
        help="Target GitHub repository (default: microsoft/qlib).",
    )
    args = parser.parse_args()

    print(f"[*] Checking upstream repository: {args.repo} ...")
    watcher = QlibUpstreamWatcher(repository=args.repo)
    result = watcher.check(force_notify=args.force)

    if not result.get("checked"):
        print(f"[!] Check failed: {result.get('error', 'unknown error')}")
        return 1

    tag = result.get("tag")
    update_available = result.get("update_available")
    ticket_file = result.get("ticket_file")

    print(f"[+] Latest upstream tag: {tag}")
    if update_available:
        print("[!] NEW UPDATE DETECTED!")
        print(f"    Release URL: {result['release'].get('html_url')}")
        print(f"    AI Agent Handoff Ticket generated at: {ticket_file}")
        print("\n[>>] Owner Action: Assign this ticket file to your AI agent (Antigravity/Claude) to learn and adapt.")
    else:
        print(f"[-] Upstream is up to date (last seen: {result.get('last_seen_tag')}). No new ticket needed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
