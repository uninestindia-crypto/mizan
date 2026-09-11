"""Fit the corrected Mizan specification on the 43 governed names; test it on the other 380.

The mean-reversion hypothesis was discovered on the universe-bound names only, so those 380 liquid
names never touched it. Training on the 43 and testing on the 380 is therefore a genuine
instrument-level out-of-sample test of a hypothesis this data did not generate.

Three corrections to the v3 specification, all declared before the run:

  1. Drop `india_vix_level`, `india_vix_change_5`, `nifty_return_5`. They are market-wide values,
     identical for every name on a date, so they carry no cross-sectional information at all and
     only add collinearity.
  2. Drop `cs_rank_momentum_5` and `cs_rank_volume_surprise`. They are monotone transforms of
     `return_5` and `volume_zscore`, so keeping both makes near-duplicate columns and that is what
     let ridge flip signs.
  3. Rank every remaining feature within its own date. The model ranks names against each other, so
     ranked inputs are the natural scale and they remove market-wide moves automatically.

No evidence store is written and no multiplicity ordinal is spent. This is a screen whose only job
is to decide whether a governed trial is warranted.
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

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

from build_mizan_feature_store import (  # noqa: E402
    adjusted_bar_points,
    load_corporate_actions,
    load_validated_demerger_factors,
)
from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

ROUND_TRIP_COST = 0.002225
HOLD_SESSIONS = 10
SELECTION_FRACTION = 0.20
MIN_CROSS_SECTION = 20

CORRECTED_FEATURES = (
    "return_1",
    "return_5",
    "return_21",
    "rsi_14_centered",
    "sma_20_distance",
    "sma_50_distance",
    "volume_zscore",
    "money_flow_multiplier",
)


def _ranks(values: list[float]) -> list[float]:
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
    return [r / len(values) - 0.5 for r in ranks]


def forward_returns(
    store_root: Path,
    symbols: set[str],
    *,
    corporate_actions_dir: Path | None = None,
    total_return: bool = True,
    validated_factors_path: Path | None = None,
) -> dict[str, dict[date, float]]:
    """Net return from next open to the open HOLD_SESSIONS later.

    Adjusting the **label** matters at least as much as adjusting the feature: a screen that fixes
    one and not the other is measuring a mismatch rather than a model. The features here come from
    the adjusted feature store, so the targets must sit on the same basis.

    A window spanning a corporate action of **unknown size** produces no observation at all. Nothing
    sized it, so the adjusted series cannot correct it, and the raw ratio across it is a fabricated
    return -- on this corpus that would mean reading NIITLTD's -77.3% demerger gap as a real target.
    The window is dropped, matching what ``modeling.labels.build_label_dataset`` does with the
    governed labels, so the screen and the governed path agree about which observations exist.
    """
    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    best: dict[str, Any] = {}
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        acquisition = historical_acquisition_from_verified(verified)
        symbol = acquisition.manifest.symbol
        if symbol not in symbols:
            continue
        if symbol not in best or len(acquisition.records) > len(best[symbol].records):
            best[symbol] = acquisition
    validated = load_validated_demerger_factors(
        validated_factors_path if corporate_actions_dir is not None else None
    )
    out: dict[str, dict[date, float]] = {}
    refused = 0
    for symbol, acquisition in best.items():
        actions = (
            load_corporate_actions(corporate_actions_dir, symbol)
            if corporate_actions_dir is not None
            else []
        )
        bars, plan = adjusted_bar_points(
            acquisition,
            actions,
            total_return=total_return,
            validated_factors=validated.get(symbol),
        )
        unresolved = sorted(item.ex_date for item in plan.unresolved)
        opens = [float(bar.open) for bar in bars]
        dates = [bar.on for bar in bars]
        series: dict[date, float] = {}
        for i in range(len(opens) - HOLD_SESSIONS - 1):
            if opens[i + 1] <= 0:
                continue
            entry_on, exit_on = dates[i + 1], dates[i + 1 + HOLD_SESSIONS]
            # (entry, exit] -- an action on the entry date is already in the entry price.
            if any(entry_on < ex_date <= exit_on for ex_date in unresolved):
                refused += 1
                continue
            series[dates[i]] = opens[i + 1 + HOLD_SESSIONS] / opens[i + 1] - 1.0 - ROUND_TRIP_COST
        out[symbol] = series
    if refused:
        print(f"  refused {refused} windows spanning an unsized corporate action", flush=True)
    return out


def governed_symbols(store_root: Path) -> set[str]:
    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    found: set[str] = set()
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        acquisition = historical_acquisition_from_verified(verified)
        if acquisition.manifest.historical_universe_authority is not None:
            found.add(acquisition.manifest.symbol)
    return found


def _report(label: str, per_period: list[float], benchmark: list[float]) -> None:
    if len(per_period) < 3:
        print(f"{label}: too few periods")
        return
    mean = statistics.fmean(per_period)
    stdev = statistics.stdev(per_period)
    t = mean / (stdev / math.sqrt(len(per_period))) if stdev > 0 else 0.0
    sharpe = (mean / stdev) * math.sqrt(252.0 / HOLD_SESSIONS) if stdev > 0 else 0.0
    bench = statistics.fmean(benchmark) if benchmark else 0.0
    print(
        f"{label:34s} n={len(per_period):>4} mean={mean:>+9.6f} t={t:>+6.2f} "
        f"sharpe={sharpe:>+6.2f}  vs equal-weight {bench:>+9.6f}"
    )


def run(args: argparse.Namespace) -> int:
    print("=== MIZAN corrected specification: train on 43, test on the other 380 ===")
    print(f"features: {len(CORRECTED_FEATURES)} cross-sectionally ranked")
    print(
        f"hold {HOLD_SESSIONS} sessions, net of {ROUND_TRIP_COST:.4%}, long top "
        f"{SELECTION_FRACTION:.0%}\n"
    )

    by_date: dict[date, list[tuple[str, list[float]]]] = defaultdict(list)
    with gzip.open(args.feature_store, "rt", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_date[date.fromisoformat(row["date"])].append(
                (row["symbol"], [float(row[name]) for name in CORRECTED_FEATURES])
            )
    all_symbols = {s for rows in by_date.values() for s, _ in rows}
    train_symbols = governed_symbols(args.governed_cache) & all_symbols
    test_symbols = all_symbols - train_symbols
    print(f"train symbols (governed) : {len(train_symbols)}")
    print(f"test  symbols (untouched): {len(test_symbols)}")

    forward = forward_returns(
        args.market_cache,
        all_symbols,
        corporate_actions_dir=None if args.no_adjust else args.corporate_actions_dir,
        total_return=not args.price_return,
        validated_factors_path=None if args.no_adjust else args.validated_factors,
    )
    print(
        f"labels          : {'RAW (unadjusted)' if args.no_adjust else 'corporate-action adjusted'}",
        flush=True,
    )
    print(f"symbols with forward returns: {len(forward)}\n")

    # Rank within each date across the whole cross-section, then split by instrument.
    train_x: list[list[float]] = []
    train_y: list[float] = []
    test_rows: dict[date, list[tuple[str, list[float], float]]] = defaultdict(list)
    for day, rows in by_date.items():
        if len(rows) < MIN_CROSS_SECTION:
            continue
        ranked = [_ranks([values[i] for _, values in rows]) for i in range(len(CORRECTED_FEATURES))]
        for position, (symbol, _) in enumerate(rows):
            target = forward.get(symbol, {}).get(day)
            if target is None:
                continue
            vector = [ranked[i][position] for i in range(len(CORRECTED_FEATURES))]
            if symbol in train_symbols:
                train_x.append(vector)
                train_y.append(target)
            else:
                test_rows[day].append((symbol, vector, target))

    print(f"training rows (43 names) : {len(train_x):,}")
    print(f"test rows (380 names)    : {sum(len(v) for v in test_rows.values()):,}\n")
    if len(train_x) < 100:
        print("REFUSED: not enough training rows")
        return 2

    # Ridge on the raw forward return, not a sign: magnitude is information the classifier threw away.
    matrix = np.array(train_x, dtype=np.float64)
    targets = np.array(train_y, dtype=np.float64)
    design = np.hstack([np.ones((matrix.shape[0], 1)), matrix])
    regularizer = np.eye(design.shape[1]) * 1.0
    regularizer[0, 0] = 0.0
    beta = np.linalg.solve(design.T @ design + regularizer, design.T @ targets)
    print("fitted coefficients (trained on the 43 only):")
    for name, coefficient in zip(CORRECTED_FEATURES, beta[1:], strict=True):
        print(f"   {name:26s} {coefficient:>+12.6f}")
    print()

    selected: list[float] = []
    equal_weight: list[float] = []
    for day in sorted(test_rows):
        day_rows = test_rows[day]
        if len(day_rows) < MIN_CROSS_SECTION:
            continue
        scores = [
            (float(beta[0] + np.dot(beta[1:], vector)), target) for _, vector, target in day_rows
        ]
        scores.sort(key=lambda item: -item[0])
        take = max(1, int(len(scores) * SELECTION_FRACTION))
        selected.append(statistics.fmean([target for _, target in scores[:take]]))
        equal_weight.append(statistics.fmean([target for _, target in scores]))

    print("OUT-OF-SAMPLE on the 380 names that never produced the hypothesis:")
    _report("long top 20% by Mizan score", selected, equal_weight)
    _report("equal-weight all names (bench)", equal_weight, equal_weight)
    print()
    edge = [s - b for s, b in zip(selected, equal_weight, strict=True)]
    _report("selection edge over benchmark", edge, [])
    print()
    print("Rebalances overlap at a 10-session hold, so these t-statistics are optimistic.")
    print("The benchmark is the honest comparator: beating zero is not the test, beating")
    print("equal-weight is, because equal-weight requires no model at all.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feature-store",
        type=Path,
        default=ROOT_DIR / "data/evidence/feature-store/mizan/mizan_feature_store.csv.gz",
    )
    parser.add_argument(
        "--governed-cache",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
    )
    parser.add_argument(
        "--market-cache",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/all-market-20160822-20260821/store",
    )
    parser.add_argument(
        "--corporate-actions-dir",
        type=Path,
        default=ROOT_DIR
        / "data/evidence/market-cache/all-market-20160822-20260821/corporate-actions",
        help="Authority used to back-adjust the label's next-open prices.",
    )
    parser.add_argument(
        "--no-adjust",
        action="store_true",
        help="Compute labels from RAW opens, as this screen did before adjustment existed. "
        "Use with a RAW feature store to reproduce the -0.000022 baseline.",
    )
    parser.add_argument(
        "--validated-factors",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-validated-demerger-factors.json",
        help="Independently validated demerger factors. A ratio-less action absent from this file "
        "stays unresolved and every window spanning it is dropped rather than measured.",
    )
    parser.add_argument("--price-return", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
