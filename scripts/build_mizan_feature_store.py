"""Build the Mizan pooled cross-sectional feature store from the all-market cache.

This does not consume ``data/evidence/feature-store/multidim_feature_store.csv``. That artifact
double-counts: the all-market store holds two DATASET resources for 55 symbols, and the builder
appended rows once per dataset, so 111,941 of its 246,554 (date, symbol) pairs appear twice. Rows
here are deduplicated by symbol before any feature is computed.

Every feature uses trailing or same-bar-close information only. Forward columns are not computed at
all -- labels come from the governed cost-aware path, not from a forward close.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
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

WARMUP_BARS = 50
"""Longest trailing window any feature needs (the 50-session moving average)."""


def wilder_rsi(closes: list[float], period: int = 14) -> list[float]:
    """Wilder RSI. Index i is a function of closes[: i + 1] and nothing later."""
    out = [50.0] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period, len(closes)):
        if i > period:
            change = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        if avg_loss == 0.0:
            out[i] = 100.0 if avg_gain > 0.0 else 50.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def read_universe(path: Path) -> dict[str, str]:
    """Symbol to instrument key, from the declared research universe authority."""
    universe: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("Symbol") or not line.strip():
            continue
        parts = line.split(",")
        if len(parts) >= 3:
            universe[parts[0].strip()] = parts[2].strip()
    return universe


def load_macro(macro_dir: Path, name: str) -> dict[str, float]:
    path = macro_dir / f"macro_{name}.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {candle[0][:10]: float(candle[4]) for candle in payload.get("candles", [])}


def deduplicate_by_symbol(store: EvidenceStore) -> dict[str, Any]:
    """One acquisition per symbol: longest history, ties broken by instrument id.

    55 symbols in the all-market cache carry two DATASET resources. Keeping both is exactly what
    double-counted the previous feature store.
    """
    best: dict[str, Any] = {}
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        acquisition = historical_acquisition_from_verified(verified)
        symbol = acquisition.manifest.symbol
        incumbent = best.get(symbol)
        if incumbent is None or (
            len(acquisition.records),
            acquisition.manifest.provider_instrument_id,
        ) > (len(incumbent.records), incumbent.manifest.provider_instrument_id):
            best[symbol] = acquisition
    return best


def _instrument_rows(
    symbol: str,
    acquisition: Any,
    vix_by_date: dict[str, float],
    nifty_by_date: dict[str, float],
) -> list[tuple[str, str, list[float]]]:
    """Causal feature rows for one instrument, before cross-sectional ranking."""
    records = acquisition.records
    dates = [record.exchange_date.isoformat() for record in records]
    opens = [float(record.open) for record in records]
    highs = [float(record.high) for record in records]
    lows = [float(record.low) for record in records]
    closes = [float(record.close) for record in records]
    volumes = [float(record.volume) for record in records]
    rsi = wilder_rsi(closes)

    rows: list[tuple[str, str, list[float]]] = []
    for i in range(WARMUP_BARS, len(records)):
        close, open_, high, low = closes[i], opens[i], highs[i], lows[i]
        if close <= 0 or open_ <= 0 or high <= 0 or low <= 0:
            continue
        date = dates[i]
        vix = vix_by_date.get(date)
        vix_past = vix_by_date.get(dates[i - 5])
        nifty = nifty_by_date.get(date)
        nifty_past = nifty_by_date.get(dates[i - 5])
        if vix is None or vix_past is None or nifty is None or nifty_past is None:
            continue

        log_hl = math.log(high / low)
        log_co = math.log(close / open_)
        sma_20 = sum(closes[i - 20 : i]) / 20.0
        sma_50 = sum(closes[i - 50 : i]) / 50.0
        window = volumes[i - 20 : i]
        mean_volume = sum(window) / 20.0
        std_volume = math.sqrt(sum((v - mean_volume) ** 2 for v in window) / 20.0)
        hl_range = high - low

        rows.append(
            (
                date,
                symbol,
                [
                    close / closes[i - 1] - 1.0 if closes[i - 1] > 0 else 0.0,
                    close / closes[i - 5] - 1.0 if closes[i - 5] > 0 else 0.0,
                    close / closes[i - 21] - 1.0 if closes[i - 21] > 0 else 0.0,
                    math.sqrt(max(0.0, 0.5 * log_hl**2 - (2.0 * math.log(2.0) - 1.0) * log_co**2)),
                    log_hl / math.sqrt(4.0 * math.log(2.0)),
                    rsi[i] / 100.0 - 0.5,
                    close / sma_20 - 1.0 if sma_20 > 0 else 0.0,
                    close / sma_50 - 1.0 if sma_50 > 0 else 0.0,
                    (volumes[i] - mean_volume) / max(1.0, std_volume),
                    ((close - low) - (high - close)) / hl_range if hl_range > 1e-9 else 0.0,
                    vix / 100.0,
                    vix / vix_past - 1.0 if vix_past > 0 else 0.0,
                    nifty / nifty_past - 1.0 if nifty_past > 0 else 0.0,
                    0.0,  # cs_rank_momentum_5, filled once the cross-section is complete
                    0.0,  # cs_rank_volume_surprise, likewise
                ],
            )
        )
    return rows


def _apply_cross_sectional_ranks(by_date: dict[str, list[tuple[str, list[float]]]]) -> None:
    """Rank each instrument against that date's cross-section, centred on zero.

    Uses only contemporaneous information: every row being ranked shares one decision date.
    """
    momentum = FEATURE_NAMES_V3.index("return_5")
    volume = FEATURE_NAMES_V3.index("volume_zscore")
    rank_momentum = FEATURE_NAMES_V3.index("cs_rank_momentum_5")
    rank_volume = FEATURE_NAMES_V3.index("cs_rank_volume_surprise")
    for rows in by_date.values():
        count = len(rows)
        for source, target in ((momentum, rank_momentum), (volume, rank_volume)):
            order = sorted(range(count), key=lambda k: rows[k][1][source])
            for rank, position in enumerate(order):
                rows[position][1][target] = (rank + 1) / count - 0.5


def build(store_root: Path, macro_dir: Path, universe_path: Path, out_dir: Path) -> None:
    universe = read_universe(universe_path)
    vix_by_date = load_macro(macro_dir, "INDIAVIX")
    nifty_by_date = load_macro(macro_dir, "NIFTY50")
    print(f"universe        : {len(universe)} names", flush=True)
    print(f"macro           : VIX {len(vix_by_date)}d, NIFTY {len(nifty_by_date)}d", flush=True)

    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    acquisitions = deduplicate_by_symbol(store)
    print(f"deduplicated    : {len(acquisitions)} symbols", flush=True)

    selected = {s: a for s, a in acquisitions.items() if s in universe}
    print(f"in universe     : {len(selected)} symbols", flush=True)

    by_date: dict[str, list[tuple[str, list[float]]]] = defaultdict(list)
    skipped = 0
    for symbol, acquisition in sorted(selected.items()):
        if len(acquisition.records) < WARMUP_BARS + 30:
            skipped += 1
            continue
        for date, name, values in _instrument_rows(symbol, acquisition, vix_by_date, nifty_by_date):
            by_date[date].append((name, values))
    print(f"skipped (short) : {skipped}", flush=True)

    _apply_cross_sectional_ranks(by_date)

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "mizan_feature_store.csv.gz"
    total = 0
    symbols: set[str] = set()
    with gzip.open(csv_path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "symbol", *FEATURE_NAMES_V3])
        for date in sorted(by_date):
            for symbol, values in sorted(by_date[date]):
                writer.writerow([date, symbol, *(f"{value:.10f}" for value in values)])
                symbols.add(symbol)
                total += 1

    metadata = {
        "cross_sectional_dates": len(by_date),
        "deduplicated_symbols": len(acquisitions),
        "feature_names": list(FEATURE_NAMES_V3),
        "feature_schema_id": "quantos.mizan_crosssectional_fifteen",
        "feature_schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "symbols": len(symbols),
        "total_rows": total,
        "universe_authority": universe_path.as_posix(),
        "warmup_bars": WARMUP_BARS,
    }
    (out_dir / "mizan_feature_store_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"rows            : {total:,}", flush=True)
    print(f"symbols         : {len(symbols)}", flush=True)
    print(f"dates           : {len(by_date):,}", flush=True)
    print(f"written         : {csv_path}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store-root",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/all-market-20160822-20260821/store",
    )
    parser.add_argument(
        "--macro-dir",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/macro-regimes-20160822-20260821",
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-research-universe-liquid-10y.csv",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=ROOT_DIR / "data/evidence/feature-store/mizan"
    )
    args = parser.parse_args()
    build(args.store_root, args.macro_dir, args.universe, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
