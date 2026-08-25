"""Select a defensible research universe from the all-market profile data.

The all-market cache holds 3,267 currently-listed NSE symbols. Using it as delivered would
manufacture results: 437 are SME-platform names whose liquidity does not support the 0.224%
statutory cost model, 19 are under surveillance (PCA), 22% of the market has more than 5% of days
circuit-locked at a price you cannot transact at, and only 1,289 have a full ten-year history.

This selects the subset where the rest of the governed stack's assumptions are arguable rather than
fictional, and records the exclusions so a reader can see what was dropped and why.

**The survivorship bias is documented, not removed.** The source universe is "all *active* NSE listed
equities", so companies that delisted or failed inside the window are absent. That cannot be fixed
from this cache. Its consequence for interpretation is asymmetric and is written into the output
header: a positive result here is weak evidence because the bias pushes that way, while a negative
result is strong because the bias was working in the strategy's favour and it still failed.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

MIN_YEARS = 9.5
MIN_MEDIAN_TURNOVER_INR = 5_00_00_000  # Rs 5 crore; see the work record for why this floor
EXCLUDED_SEGMENTS = frozenset({"SME", "PCA"})


def _num(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except ValueError:
        return 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("data/evidence/market-analysis/nse_all_market_profiles.csv"),
    )
    parser.add_argument(
        "--out", type=Path, default=Path("data/authorities/nse-research-universe-liquid-10y.csv")
    )
    args = parser.parse_args(argv)

    if not args.profiles.is_file():
        print(f"profiles not found: {args.profiles}", flush=True)
        return 2

    rows = list(csv.DictReader(args.profiles.read_text(encoding="utf-8-sig").splitlines()))
    dropped: dict[str, int] = {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    kept = []
    for row in rows:
        segment = (row.get("security_type") or row.get("instrument_type") or "").upper()
        if segment in EXCLUDED_SEGMENTS:
            drop(f"segment {segment}")
            continue
        if _num(row, "years_active") < MIN_YEARS:
            drop("history < 9.5y")
            continue
        if _num(row, "median_daily_turnover_inr") < MIN_MEDIAN_TURNOVER_INR:
            drop("turnover < Rs 5cr")
            continue
        isin = (row.get("isin") or "").strip()
        symbol = (row.get("symbol") or "").strip()
        if not isin or not symbol:
            drop("missing symbol or isin")
            continue
        kept.append((symbol, isin, row))

    kept.sort(key=lambda entry: entry[0])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        handle.write(
            "# QuantOS research universe: currently-listed NSE equities with >=9.5y history and\n"
            f"# median daily turnover >= Rs {MIN_MEDIAN_TURNOVER_INR / 1e7:.0f} crore. SME and PCA excluded.\n"
            "# SURVIVORSHIP BIAS: the source universe is ACTIVE listings only, so companies that\n"
            "# delisted or failed inside the window are absent. This cannot be corrected from this\n"
            "# cache. Read results asymmetrically: a positive result is weak evidence because the\n"
            "# bias pushes that way; a negative result is strong because the bias favoured the\n"
            "# strategy and it still failed.\n"
        )
        writer = csv.writer(handle)
        writer.writerow(
            ["Symbol", "ISIN Code", "InstrumentKey", "YearsActive", "MedianDailyTurnoverINR"]
        )
        for symbol, isin, row in kept:
            writer.writerow(
                [
                    symbol,
                    isin,
                    f"NSE_EQ|{isin}",
                    f"{_num(row, 'years_active'):.2f}",
                    f"{_num(row, 'median_daily_turnover_inr'):.0f}",
                ]
            )

    print(f"profiled symbols : {len(rows)}")
    for reason, count in sorted(dropped.items(), key=lambda kv: -kv[1]):
        print(f"  dropped {reason:<22}: {count}")
    print(f"selected         : {len(kept)}")
    print(f"written          : {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
