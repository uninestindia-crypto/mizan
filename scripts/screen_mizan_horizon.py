"""Characterize gross return against cost across holding periods.

This is a property of the execution contract, not a strategy search: it measures the unconditional
average return of holding every name for N sessions, against the one-off round-trip cost of doing
so. No model chooses anything, no evidence store is written, and no multiplicity ordinal is spent.

The 2-session governed contract charges ~0.2225% to capture ~0.0776% of average gross drift. The
question this answers is at what horizon, if any, the average gross drift exceeds the cost.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

ROUND_TRIP_COST = 0.002225
"""Measured mean round-trip cost per governed label row (scripts/diagnose_mizan_loss.py)."""

HORIZONS = (1, 2, 3, 4, 5, 10, 21, 42, 63, 126, 252)


def run(args: argparse.Namespace) -> int:
    store = EvidenceStore(EvidenceStoreConfig(root=args.market_cache))
    series: dict[str, list[float]] = {}
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        acquisition = historical_acquisition_from_verified(verified)
        symbol = acquisition.manifest.symbol
        opens = [float(record.open) for record in acquisition.records]
        if len(opens) > len(series.get(symbol, [])):
            series[symbol] = opens
    print(f"symbols: {len(series)}")
    print()
    print(
        f"{'HOLD':>5s} {'MEAN GROSS':>12s} {'COST':>10s} {'NET':>12s} "
        f"{'GROSS/COST':>11s} {'WIN RATE':>9s} {'ANNUAL NET':>11s}"
    )
    print("-" * 76)

    for horizon in HORIZONS:
        returns: list[float] = []
        for opens in series.values():
            # Non-overlapping windows: overlapping ones would inflate the sample and understate
            # the standard error, which is the bookkeeping error this repository already made once.
            for i in range(0, len(opens) - horizon, horizon):
                if opens[i] > 0:
                    returns.append(opens[i + horizon] / opens[i] - 1.0)
        if not returns:
            continue
        gross = statistics.fmean(returns)
        net = gross - ROUND_TRIP_COST
        wins = sum(1 for r in returns if r > ROUND_TRIP_COST) / len(returns)
        periods_per_year = 252.0 / horizon
        annual = (1.0 + net) ** periods_per_year - 1.0 if net > -1 else float("nan")
        print(
            f"{horizon:>5d} {gross:>+12.6f} {ROUND_TRIP_COST:>10.6f} {net:>+12.6f} "
            f"{gross / ROUND_TRIP_COST:>10.2f}x {wins:>8.1%} {annual:>+10.1%}"
        )

    print()
    print("MEAN GROSS is the unconditional average of holding every name for that many sessions.")
    print("COST is charged once per round trip regardless of horizon, so it amortizes as the hold")
    print("lengthens. NET is what is left for a model to work with before it selects anything.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--market-cache",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
