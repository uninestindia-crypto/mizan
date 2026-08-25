"""Does any Mizan feature predict anything at all?

Mizan measured 49.2% accuracy against 50.3% for buy-and-hold, so the fitted linear model has no
skill. That leaves two very different diagnoses, and they imply opposite next steps:

  * the features carry signal and the LINEAR model fails to extract it -> try another model class;
  * the features carry no signal -> no model class helps, and prediction is the wrong product.

This separates them. For each feature it computes the cross-sectional information coefficient --
the rank correlation, within a single date, between the feature and the forward net return every
name actually went on to deliver. Averaged across dates, with a t-statistic over the per-date series.

All fifteen features are reported. Reporting only the best would be selecting on the same data the
statistic is computed from, which is the exact error the deflated Sharpe exists to punish. No
evidence store is written and no multiplicity ordinal is spent.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import math
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling.rows import FEATURE_NAMES_V3  # noqa: E402

ROUND_TRIP_COST = 0.002225
MIN_CROSS_SECTION = 20
"""A rank correlation over fewer names than this is noise, not a cross-section."""


def _ranks(values: list[float]) -> list[float]:
    """Average ranks, so ties do not manufacture spurious correlation."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0 or n < 3:
        return None
    return sxy / math.sqrt(sxx * syy)


def forward_returns(store_root: Path, horizon: int) -> dict[str, dict[date, float]]:
    """Net return from the next open to the open `horizon` sessions later, per symbol and date."""
    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    best: dict[str, Any] = {}
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        acquisition = historical_acquisition_from_verified(verified)
        if acquisition.manifest.historical_universe_authority is None:
            continue
        symbol = acquisition.manifest.symbol
        if symbol not in best or len(acquisition.records) > len(best[symbol].records):
            best[symbol] = acquisition

    out: dict[str, dict[date, float]] = {}
    for symbol, acquisition in best.items():
        records = acquisition.records
        opens = [float(record.open) for record in records]
        dates = [record.exchange_date for record in records]
        series: dict[date, float] = {}
        for i in range(len(records) - horizon - 1):
            entry = opens[i + 1]
            exit_ = opens[i + 1 + horizon]
            if entry > 0:
                series[dates[i]] = exit_ / entry - 1.0 - ROUND_TRIP_COST
        out[symbol] = series
    return out


def run(args: argparse.Namespace) -> int:
    forward = forward_returns(args.market_cache, args.horizon)
    print(f"symbols with forward returns : {len(forward)}")

    by_date: dict[date, list[tuple[str, list[float]]]] = defaultdict(list)
    with gzip.open(args.feature_store, "rt", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            symbol = row["symbol"]
            if symbol not in forward:
                continue
            day = date.fromisoformat(row["date"])
            if day not in forward[symbol]:
                continue
            by_date[day].append((symbol, [float(row[name]) for name in FEATURE_NAMES_V3]))

    usable = {d: rows for d, rows in by_date.items() if len(rows) >= MIN_CROSS_SECTION}
    print(f"dates with a usable cross-section: {len(usable):,}")
    print(f"horizon: {args.horizon} sessions held, net of {ROUND_TRIP_COST:.4%} round trip")
    print()
    print(f"{'FEATURE':28s} {'MEAN IC':>9s} {'STDEV':>8s} {'T-STAT':>8s} {'|t|>2':>6s}")
    print("-" * 64)

    ordered = sorted(usable)
    results = []
    for index, name in enumerate(FEATURE_NAMES_V3):
        per_date: list[float] = []
        for day in ordered:
            rows = usable[day]
            xs = _ranks([values[index] for _, values in rows])
            ys = _ranks([forward[symbol][day] for symbol, _ in rows])
            correlation = _correlation(xs, ys)
            if correlation is not None:
                per_date.append(correlation)
        if len(per_date) < 3:
            continue
        mean = statistics.fmean(per_date)
        stdev = statistics.stdev(per_date)
        t = mean / (stdev / math.sqrt(len(per_date))) if stdev > 0 else 0.0
        results.append((name, mean, stdev, t))
        print(
            f"{name:28s} {mean:>+9.5f} {stdev:>8.5f} {t:>+8.2f} {'YES' if abs(t) > 2 else '':>6s}"
        )

    print()
    significant = [r for r in results if abs(r[3]) > 2]
    print(f"features with |t| > 2 : {len(significant)} of {len(results)}")
    print()
    print("Per-date ICs overlap when the horizon exceeds one session, so these t-statistics are")
    print("optimistic. Read a |t| below 2 as 'no detectable signal'; read one above 2 as 'worth a")
    print("pre-declared governed test', never as a result on its own.")
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
    parser.add_argument("--horizon", type=int, default=10)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
