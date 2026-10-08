#!/usr/bin/env python3
"""Automated Market-Hours Scheduler for Mizan Quant-SLM.

Enforces Indian National Stock Exchange (NSE) cash market trading hours:
09:15 to 15:30 IST (UTC+05:30), Monday through Friday.

Features:
- Live session check via `quant_system.live.market_hours.is_session_open`.
- Automatic paper execution on live Upstox API quote feeds.
- Continuous daemon mode (`--daemon`) with configurable polling interval.
- Seamless offline simulation fallback if forced (`--force`).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quant_system.live.market_hours import IST, is_session_open  # noqa: E402
from quant_system.research.qlib import run_live_slm_pipeline  # noqa: E402


def run_scheduled_iteration(universe: list[str], epochs: int, force: bool = False) -> bool:
    now_utc = datetime.now(UTC)
    now_ist = now_utc.astimezone(IST)
    is_open = is_session_open(now_utc)

    print("-" * 75)
    print(f"[*] Mizan Quant-SLM Market Hours Checker: {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"    Session State: {'OPEN (09:15 - 15:30 IST)' if is_open else 'CLOSED'}")

    if not is_open and not force:
        print("[-] Cash market session is closed. Skipping live execution until next session.")
        print("    (Pass --force to run execution anyway in offline simulation mode.)")
        return False

    if not is_open and force:
        print("[!] Session is closed but --force was specified. Proceeding with execution...")

    print("[+] Launching Mizan Quant-SLM execution iteration...")
    t0 = time.time()
    result = run_live_slm_pipeline(
        universe=universe,
        epochs=epochs,
        use_cache=True,
        sample_step=15,
    )
    elapsed = time.time() - t0
    print(f"[+] Iteration completed in {elapsed:.2f}s! Orders generated: {result.get('orders_count', 0)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Mizan Quant-SLM Market-Hours Automated Runner.")
    parser.add_argument(
        "--universe",
        nargs="+",
        default=["NIFTY50"],
        help="Universe symbols (default: NIFTY50).",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=15,
        help="Model training epochs per run.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Polling interval in seconds for daemon mode (default: 300s = 5m).",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously in daemon mode during market hours.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution even if cash market session is closed.",
    )
    args = parser.parse_args()

    print("=" * 75)
    print("[*] MIZAN QUANT OS: AUTOMATED MARKET-HOURS QUANT-SLM SCHEDULER")
    print("=" * 75)

    if not args.daemon:
        run_scheduled_iteration(universe=args.universe, epochs=args.epochs, force=args.force)
        return 0

    print(f"[+] Daemon mode active. Polling every {args.interval} seconds (Press Ctrl+C to stop).")
    try:
        while True:
            run_scheduled_iteration(universe=args.universe, epochs=args.epochs, force=args.force)
            print(f"[*] Sleeping for {args.interval}s until next check...")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[+] Daemon stopped cleanly by user.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
