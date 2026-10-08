"""Sync upstream PyBroker releases into Mizan.

Used by AI agents (Antigravity, Claude Code) when handed an update task.
"""

from __future__ import annotations

import argparse
import logging
import sys

from quant_system.research.pybroker_upstream_tracker import (
    get_installed_pybroker_version,
    get_pybroker_tracker,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("sync_pybroker_update")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync PyBroker upstream update into Mizan")
    parser.add_argument("--version", help="Target PyBroker version to sync")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without modifying")
    args = parser.parse_args()

    tracker = get_pybroker_tracker()
    status = tracker.check(force=True)

    current_ver = get_installed_pybroker_version()
    latest_ver = args.version or status.get("latest_version")

    logger.info("Current Mizan PyBroker version: %s", current_ver)
    logger.info("Target Upstream PyBroker version: %s", latest_ver)

    if not status.get("update_available") and not args.version:
        logger.info("PyBroker is already up-to-date (v%s). No action required.", current_ver)
        return 0

    if args.dry_run:
        logger.info("[Dry Run] Update available: %s -> %s", current_ver, latest_ver)
        logger.info("[Dry Run] Release URL: %s", status.get("release_url"))
        return 0

    logger.info("Upstream PyBroker briefing ready at: %s", status.get("briefing_path"))
    logger.info(
        "To test Mizan's PyBroker integration, run: pytest tests/test_pybroker_adapter.py -v"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
