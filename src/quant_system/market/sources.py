"""Discover and read committed daily-bar datasets from the evidence store, read-only.

Layout (``quantos.evidence_manifest`` v1)::

    <market-cache>/<cache-name>/store/datasets/<dataset_id>/{COMMITTED, manifest.json}
    <market-cache>/<cache-name>/store/blobs/sha256/..../<hash>.jsonl.gz

Two roles matter to the retail index:

* ``HISTORY`` caches (``all-market-*``): ten years of every listed symbol, acquired once.
* ``REFRESH`` caches (``nifty500-refresh-*``): rolling three-year windows re-acquired daily for the
  NIFTY 500. The newest vintage is the freshest data and is internally consistent, because the
  provider re-adjusts the whole window on every acquisition.

Nothing here writes to the store. Invalid rows are skipped and counted, never repaired.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Role = Literal["HISTORY", "REFRESH"]

_ROLE_PREFIXES: tuple[tuple[str, Role], ...] = (
    ("all-market-", "HISTORY"),
    ("nifty500-refresh-", "REFRESH"),
)


@dataclass(frozen=True, slots=True)
class CacheRef:
    name: str
    role: Role
    store: Path


@dataclass(frozen=True, slots=True)
class DatasetRef:
    cache: str
    role: Role
    dataset_id: str
    manifest_hash: str
    symbol: str
    instrument_key: str
    acquired_at: str
    range_start: str
    range_end: str
    row_count: int
    blob_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class RawBar:
    """One daily bar. Prices are the provider's decimal strings parsed to float for storage."""

    d: str
    o: float
    h: float
    low: float
    c: float
    v: int


@dataclass(slots=True)
class ReadStats:
    rows: int = 0
    invalid: int = 0
    duplicate_dates: int = 0


def discover_caches(market_cache_dir: Path) -> list[CacheRef]:
    """Return every cache under ``market_cache_dir`` whose name maps to a known role."""
    found: list[CacheRef] = []
    if not market_cache_dir.is_dir():
        return found
    for child in sorted(market_cache_dir.iterdir()):
        if not child.is_dir():
            continue
        role = next((r for prefix, r in _ROLE_PREFIXES if child.name.startswith(prefix)), None)
        store = child / "store"
        if role is None or not (store / "datasets").is_dir():
            continue
        found.append(CacheRef(name=child.name, role=role, store=store))
    return found


def scan_datasets(cache: CacheRef) -> list[DatasetRef]:
    """Read every committed manifest in one cache. Uncommitted or unreadable datasets are skipped."""
    refs: list[DatasetRef] = []
    for dataset_dir in sorted((cache.store / "datasets").iterdir()):
        if not (dataset_dir / "COMMITTED").is_file():
            continue
        manifest_path = dataset_dir / "manifest.json"
        try:
            manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ref = _dataset_ref(cache, dataset_dir.name, manifest)
        if ref is not None:
            refs.append(ref)
    return refs


def _dataset_ref(cache: CacheRef, dataset_id: str, manifest: dict[str, Any]) -> DatasetRef | None:
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        return None
    symbol = str(metadata.get("symbol") or "").strip().upper()
    if not symbol or str(metadata.get("interval")) != "1":
        return None
    received = metadata.get("received_range") or {}
    blobs = manifest.get("blobs") or []
    paths = tuple(
        cache.store / str(blob["relative_path"])
        for blob in blobs
        if isinstance(blob, dict) and blob.get("relative_path")
    )
    if not paths:
        return None
    return DatasetRef(
        cache=cache.name,
        role=cache.role,
        dataset_id=dataset_id,
        manifest_hash=str(manifest.get("manifest_hash") or ""),
        symbol=symbol,
        instrument_key=str(metadata.get("provider_instrument_id") or ""),
        acquired_at=str(metadata.get("acquired_at") or ""),
        range_start=str(received.get("start") or "")[:10],
        range_end=str(received.get("end") or "")[:10],
        row_count=int(metadata.get("row_count") or 0),
        blob_paths=paths,
    )


def newest_per_symbol(refs: Iterable[DatasetRef]) -> dict[str, DatasetRef]:
    """Keep the most recently acquired dataset per symbol; ties go to the larger dataset."""
    chosen: dict[str, DatasetRef] = {}
    for ref in refs:
        current = chosen.get(ref.symbol)
        if current is None or (ref.acquired_at, ref.row_count) > (
            current.acquired_at,
            current.row_count,
        ):
            chosen[ref.symbol] = ref
    return chosen


def read_bars(ref: DatasetRef, stats: ReadStats | None = None) -> list[RawBar]:
    """Parse a dataset's bars, oldest first. The first bar seen for a date wins."""
    tally = stats if stats is not None else ReadStats()
    by_date: dict[str, RawBar] = {}
    for record in _records(ref.blob_paths):
        bar = _parse(record)
        tally.rows += 1
        if bar is None:
            tally.invalid += 1
            continue
        if bar.d in by_date:
            tally.duplicate_dates += 1
            continue
        by_date[bar.d] = bar
    return [by_date[d] for d in sorted(by_date)]


def _records(paths: Iterable[Path]) -> Iterator[dict[str, Any]]:
    for path in paths:
        try:
            handle = gzip.open(path, "rt", encoding="utf-8")
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
                    yield {}
                    continue
                if isinstance(record, dict):
                    yield record


def _parse(record: dict[str, Any]) -> RawBar | None:
    try:
        d = str(record["exchange_date"])[:10]
        o = float(record["open"])
        h = float(record["high"])
        low = float(record["low"])
        c = float(record["close"])
    except (KeyError, TypeError, ValueError):
        return None
    if len(d) != 10 or min(o, h, low, c) <= 0.0 or h < low or not (low <= c <= h):
        return None
    try:
        v = max(int(record.get("volume") or 0), 0)
    except (TypeError, ValueError):
        v = 0
    return RawBar(d=d, o=o, h=h, low=low, c=c, v=v)


def store_fingerprint(caches: Iterable[CacheRef]) -> str:
    """Hash of every committed dataset id; changes whenever a dataset is added or removed."""
    digest = hashlib.sha256()
    for cache in sorted(caches, key=lambda c: c.name):
        for dataset_dir in sorted((cache.store / "datasets").iterdir()):
            if (dataset_dir / "COMMITTED").is_file():
                digest.update(f"{cache.name}/{dataset_dir.name}\n".encode())
    return digest.hexdigest()
