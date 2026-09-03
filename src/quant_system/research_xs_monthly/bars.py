"""Isolated bar loader for the XS-monthly research screen (new stack).

Reads point-in-time daily bars from a market-cache store directory
(``store/datasets/*/manifest.json`` + ``store/blobs/...jsonl.gz``).

READ-ONLY against the cache: never writes, never mutates, never imports the
governed dataset/label/fold/evidence paths. Stdlib only.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class Bar:
    symbol: str
    exchange_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def _pos_decimal(value: object) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if d <= 0:
        return None
    return d


def _parse_bar(record: dict, fallback_symbol: str | None = None) -> Bar | None:
    try:
        symbol = str(record.get("symbol") or fallback_symbol or "").strip()
        ex_date = date.fromisoformat(str(record.get("exchange_date")))
        o = _pos_decimal(record.get("open"))
        h = _pos_decimal(record.get("high"))
        lo = _pos_decimal(record.get("low"))
        c = _pos_decimal(record.get("close"))
        if not symbol or o is None or h is None or lo is None or c is None:
            return None
        try:
            vol = int(record.get("volume") or 0)
        except (ValueError, TypeError):
            vol = 0
        return Bar(
            symbol=symbol,
            exchange_date=ex_date,
            open=o,
            high=h,
            low=lo,
            close=c,
            volume=max(vol, 0),
        )
    except (ValueError, TypeError):
        return None


def load_cache_bars(
    cache_store: Path,
    symbols: set[str] | None = None,
    max_datasets: int | None = None,
) -> tuple[dict[str, list[Bar]], dict[str, int]]:
    """Scan ``store/datasets/*/manifest.json`` and load bars.

    Returns ``({symbol: [Bar... ascending by date]}, stats)``. Duplicate dates
    keep the first bar seen. Invalid bars/datasets are skipped and counted —
    never imputed, never forward-filled.
    """
    datasets = sorted((Path(cache_store) / "datasets").glob("dset_*"))
    if max_datasets is not None:
        datasets = datasets[:max_datasets]
    by_symbol: dict[str, dict[date, Bar]] = {}
    stats = {
        "datasets_scanned": 0,
        "datasets_loaded": 0,
        "datasets_skipped": 0,
        "bars_loaded": 0,
        "bars_invalid": 0,
        "bars_duplicate_date": 0,
    }
    for dset in datasets:
        manifest_path = dset / "manifest.json"
        if not manifest_path.is_file():
            stats["datasets_skipped"] += 1
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            stats["datasets_skipped"] += 1
            continue
        stats["datasets_scanned"] += 1
        blobs = manifest.get("blobs") or []
        if not blobs:
            stats["datasets_skipped"] += 1
            continue
        loaded_any = False
        for blob in blobs:
            rel = blob.get("relative_path")
            if not rel:
                continue
            blob_path = Path(cache_store) / rel
            if not blob_path.is_file():
                continue
            try:
                handle = gzip.open(blob_path, "rt", encoding="utf-8")
            except OSError:
                continue
            with handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        stats["bars_invalid"] += 1
                        continue
                    bar = _parse_bar(record)
                    if bar is None:
                        stats["bars_invalid"] += 1
                        continue
                    if symbols is not None and bar.symbol not in symbols:
                        continue
                    slot = by_symbol.setdefault(bar.symbol, {})
                    if bar.exchange_date in slot:
                        stats["bars_duplicate_date"] += 1
                        continue
                    slot[bar.exchange_date] = bar
                    stats["bars_loaded"] += 1
                    loaded_any = True
        if loaded_any:
            stats["datasets_loaded"] += 1
        else:
            stats["datasets_skipped"] += 1
    ordered = {
        symbol: [slot[d] for d in sorted(slot)] for symbol, slot in sorted(by_symbol.items())
    }
    return ordered, stats


def read_universe_symbols(universe_csv: Path) -> list[str]:
    """Read the ``Symbol`` column, ignoring ``#`` comment lines. Sorts + dedupes."""
    names: list[str] = []
    with open(universe_csv, encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            names.append(line)
            break
    # First non-comment line is the header; remaining lines are data.
    symbols: list[str] = []
    import csv as _csv

    with open(universe_csv, encoding="utf-8-sig") as handle:
        rows = [ln for ln in handle if not ln.lstrip().startswith("#")]
    reader = _csv.DictReader(rows)
    for row in reader:
        symbol = (row.get("Symbol") or "").strip()
        if symbol:
            symbols.append(symbol)
    return sorted(set(symbols))
