"""Decompose Mizan's loss into signal and cost, on the exact rows it was evaluated on.

Asserting "costs dominate" is not evidence. This measures it: for every governed label row, the
contract records both a gross return (next open to the open after it) and a net return after real
NSE statutory costs. If gross is positive and net is negative, the loss is the cost model. If gross
is also negative, the model is picking badly and cost is not the story.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

import train_mizan  # noqa: E402


def summarize(values: list[float]) -> str:
    if not values:
        return "n=0"
    mean = statistics.fmean(values)
    return f"n={len(values):,} mean={mean:+.6f} median={statistics.median(values):+.6f}"


def run(args: argparse.Namespace) -> int:
    features_by_symbol = train_mizan.load_feature_store(args.feature_store)
    acquisitions = train_mizan.governed_acquisitions(args.market_cache)
    usable = sorted(set(acquisitions) & set(features_by_symbol))

    gross: list[float] = []
    net: list[float] = []
    costs: list[float] = []
    per_symbol: list[tuple[str, float, float]] = []

    for symbol in usable:
        try:
            _, labels, _ = train_mizan._constituent(
                symbol,
                acquisitions[symbol],
                features_by_symbol[symbol],
                args.calendar_version,
                args.quantity,
                args.horizon_sessions,
            )
        except Exception:  # noqa: BLE001 - a constituent that cannot label is reported by the trainer
            continue
        g = [float(Decimal(row.gross_return)) for row in labels.rows]
        n = [float(Decimal(row.net_return)) for row in labels.rows]
        gross.extend(g)
        net.extend(n)
        costs.extend(gi - ni for gi, ni in zip(g, n, strict=True))
        per_symbol.append((symbol, statistics.fmean(g), statistics.fmean(n)))

    print("=== MIZAN LOSS DECOMPOSITION (all governed label rows) ===")
    print(f"gross return  : {summarize(gross)}")
    print(f"net return    : {summarize(net)}")
    print(f"cost per trade: {summarize(costs)}")
    print()

    mean_gross = statistics.fmean(gross)
    mean_cost = statistics.fmean(costs)
    print(f"mean gross per 2-session hold : {mean_gross:+.6f}  ({mean_gross * 100:+.4f}%)")
    print(f"mean cost  per 2-session hold : {mean_cost:+.6f}  ({mean_cost * 100:+.4f}%)")
    print(f"gross as a multiple of cost   : {mean_gross / mean_cost:.3f}x")
    print()
    print(
        f"symbols whose GROSS mean is positive: "
        f"{sum(1 for _, g, _ in per_symbol if g > 0)}/{len(per_symbol)}"
    )
    print(
        f"symbols whose NET   mean is positive: "
        f"{sum(1 for _, _, n in per_symbol if n > 0)}/{len(per_symbol)}"
    )
    print()
    print("The label contract is long-only and unconditional: these are the returns of holding")
    print("every name for every 2-session window, before any model chooses anything. A model can")
    print("only select among these rows -- it cannot create return that is not in them.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feature-store",
        type=Path,
        default=ROOT_DIR / "data/evidence/feature-store/mizan/mizan_feature_store.csv.gz",
    )
    parser.add_argument(
        "--market-cache",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
    )
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--horizon-sessions", type=int, default=2)
    parser.add_argument("--calendar-version", default="provider-derived-v1")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
