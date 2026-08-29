"""QuantOS Live Terminal P&L and Trading Detail Viewer.

Displays a rich, formatted terminal snapshot of the active paper trading session,
positions, profit & loss, statutory fees, and Mīzān alpha model predictions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATUS_FILE = PROJECT_ROOT / "logs" / "paper_runs" / "live_paper_status.json"


def print_pnl_report() -> None:
    if not STATUS_FILE.exists():
        print(f"[WARN] No active live trading status found at {STATUS_FILE}")
        return

    try:
        with open(STATUS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as err:
        print(f"[ERROR] Could not load status file: {err}")
        return

    net_pnl = float(data.get("net_pnl", 0))
    pnl_sign = "+" if net_pnl >= 0 else ""

    print("=" * 80)
    print(f" QuantOS Live Trading & P&L Report -- {data.get('session_id', 'UNKNOWN')}")
    print(
        f" Time: {data.get('timestamp_ist', 'N/A')} | Market Close: {data.get('market_close_ist', '15:30:00 IST')}"
    )
    print("=" * 80)
    print(" 1. PORTFOLIO & P&L SUMMARY")
    print("-" * 80)
    print(f"  Total Portfolio Equity : Rs {data.get('total_equity', '0.00'):>12}")
    print(f"  Available Cash         : Rs {data.get('cash', '0.00'):>12}")
    print(f"  Initial Capital        : Rs {data.get('initial_cash', '1000000.00'):>12}")
    print(f"  Realized P&L           : Rs {data.get('realized_pnl', '0.00'):>12}")
    print(f"  Unrealized (MtM) P&L   : Rs {data.get('unrealized_pnl', '0.00'):>12}")
    print(
        f"  TOTAL NET P&L          : Rs {pnl_sign}{data.get('net_pnl', '0.00'):>12} ({pnl_sign}{data.get('net_pnl_pct', 0):.2f}%)"
    )
    print(f"  Statutory NSE Fees Paid: Rs {data.get('total_fees_paid', '0.00'):>12}")
    print("-" * 80)

    positions = data.get("positions_detail", [])
    print(f"\n 2. OPEN POSITIONS MATRIX ({len(positions)} Held Assets)")
    print("-" * 80)
    if not positions:
        print("  *(No open positions / 100% Cash buffer)*")
    else:
        print(
            f"  {'Symbol':<10} {'Qty':>6} {'Entry Price':>14} {'Current Price':>14} {'Market Value':>14} {'MtM P&L':>14} {'Alloc %':>8}"
        )
        print("  " + "-" * 76)
        for pos in positions:
            u_pnl = float(pos.get("unrealized_pnl", 0))
            u_sign = "+" if u_pnl >= 0 else ""
            print(
                f"  {pos['symbol']:<10} {pos['quantity']:>6} Rs {pos['entry_price']:>11} Rs {pos['current_price']:>11} Rs {pos['market_value']:>11} {u_sign}Rs {pos['unrealized_pnl']:>8} ({pos['allocation_pct']}%)"
            )

    signals = data.get("alpha_signals", [])
    print(f"\n 3. MIZAN ALPHA SCORES & TOP PICKS ({len(signals)} Indian Equities Evaluated)")
    print("-" * 80)
    for sig in signals[:10]:
        top_tag = " [TOP PICK]" if sig.get("is_top_pick") else ""
        print(
            f"  Rank #{sig['rank']:<2} {sig['symbol']:<12} | Alpha Score: +{sig['score']:.4f}{top_tag}"
        )
    if len(signals) > 10:
        print(
            f"  ... and {len(signals) - 10} more constituent stocks ranked across the active universe."
        )

    fills = data.get("recent_fills", [])
    print(f"\n 4. RECENT EXECUTIONS & FILLS ({data.get('fills_count', len(fills))} Total)")
    print("-" * 80)
    if not fills:
        print("  *(No fills executed yet)*")
    else:
        print(
            f"  {'Time (IST)':<12} {'Symbol':<10} {'Side':<6} {'Qty':>6} {'Price':>12} {'Statutory Fee':>14}"
        )
        print("  " + "-" * 64)
        for f in fills[-6:]:
            print(
                f"  {f['timestamp_ist']:<12} {f['symbol']:<10} {f['side']:<6} {f['quantity']:>6} Rs {f['price']:>9} Rs {f['fee']:>11}"
            )

    risk = data.get("risk_governor", {})
    print("\n 5. PRE-TRADE RISK & RECONCILIATION")
    print("-" * 80)
    print(
        f"  Kill Switch: {'ACTIVE (HALTED)' if risk.get('kill_switch_active') else 'NORMAL (SAFE)'} | Max Pos Weight: {risk.get('max_position_weight', '30%')} | Min Cash: {risk.get('min_cash_buffer', '5%')}"
    )
    print(f"  Penny-Exact Discrepancy: Rs {risk.get('discrepancy_paisa', '0.00')} (PASS)")

    gainers = data.get("top_gainers", [])
    if gainers:
        print("\n 6. TOP NSE GAINERS TODAY (Real-Time % Momentum)")
        print("-" * 80)
        print(
            f"  {'Rank':<6} {'Symbol':<12} {'LTP (Rs)':>12} {'Day Change':>14} {'Alpha Score':>14}"
        )
        print("  " + "-" * 62)
        for g in gainers[:5]:
            chg_sign = "+" if g["change_pct"] >= 0 else ""
            alpha_sign = "+" if g.get("alpha_score", 0) >= 0 else ""
            print(
                f"  #{g['rank']:<5} {g['symbol']:<12} Rs {g['price']:>9} {chg_sign}{g['change_pct']:>11.2f}% {alpha_sign}{g.get('alpha_score', 0):>13.4f}"
            )
    print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="QuantOS Live Terminal P&L and Trading Detail Viewer"
    )
    parser.add_argument(
        "--watch", action="store_true", help="Watch live P&L updating every 2 seconds"
    )
    parser.add_argument(
        "--interval", type=float, default=2.0, help="Seconds between refresh in watch mode"
    )
    args = parser.parse_args()

    if not args.watch:
        print_pnl_report()
        return 0

    try:
        while True:
            # Clear screen (ANSI escape code)
            print("\033[2J\033[H", end="")
            print_pnl_report()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nViewer stopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
