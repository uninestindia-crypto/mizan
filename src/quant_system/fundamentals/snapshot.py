"""The bundled snapshot: a versioned, gzip-compressed JSON document of real quarterly figures, read only at run time."""

from __future__ import annotations

import gzip
import json
import os
import re
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from quant_system.fundamentals.models import QuarterFigures

SNAPSHOT_FORMAT: Final = 1
SNAPSHOT_SOURCE: Final = "NSE corporate-financial-results XBRL"
INDUSTRY_SOURCE: Final = "NSE Nifty Total Market list"
MAX_SNAPSHOT_BYTES: Final = 256 * 1024 * 1024
SYMBOL_PATTERN: Final = re.compile(r"[A-Za-z0-9&-]{1,15}")


class FundamentalsStoreError(Exception):
    """Saving or building failed. The message is plain language."""


def normalize_symbol(symbol: str) -> str | None:
    """The upper-case NSE symbol, or None when it is not a plausible one."""
    text = symbol if isinstance(symbol, str) else ""
    return text.upper() if SYMBOL_PATTERN.fullmatch(text) else None


@dataclass(frozen=True)
class IndustrySnapshot:
    groups: Mapping[str, str]
    read_on: str


@dataclass(frozen=True)
class Snapshot:
    built_on: str | None
    companies: dict[str, Any]
    industry_groups: dict[str, str] = field(default_factory=dict)
    industry_read_on: str = ""


def check_row(symbol: str, item: QuarterFigures) -> None:
    """A snapshot row must be the named company's and must carry its proof."""
    if normalize_symbol(symbol) != symbol or item.symbol != symbol:
        raise FundamentalsStoreError(
            f"{symbol}: the figures belong to {item.symbol}, not {symbol}."
        )
    if not item.sha256:
        raise FundamentalsStoreError(
            f"{symbol}: the filing has no recorded sha256, so it was not written."
        )
    if not item.source_url:
        raise FundamentalsStoreError(
            f"{symbol}: the filing has no recorded source link, so it was not written."
        )


def write_snapshot(
    path: Path,
    companies: Mapping[str, Sequence[QuarterFigures]],
    built_on: str,
    industry: IndustrySnapshot | None,
) -> None:
    """Write the same bytes for the same input: sorted keys, no timestamps, no wall clock."""
    for symbol, rows in companies.items():
        for item in rows:
            check_row(symbol, item)
    document: dict[str, Any] = {
        "format": SNAPSHOT_FORMAT,
        "built_on": built_on,
        "source": SNAPSHOT_SOURCE,
        "companies": {
            symbol: [item.to_json_dict() for item in sorted(rows, key=_order)]
            for symbol, rows in companies.items()
        },
    }
    if industry is not None:
        document["industry_groups"] = dict(industry.groups)
        document["industry_source"] = INDUSTRY_SOURCE
        document["industry_read_on"] = industry.read_on
    text = json.dumps(document, sort_keys=True, separators=(",", ":"))
    packed = gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(packed)
    os.replace(partial, path)


def _order(item: QuarterFigures) -> tuple[str, bool]:
    return item.period_end.isoformat(), item.consolidated


def read_snapshot(path: Path) -> Snapshot | None:
    """The snapshot, or None when it is missing, damaged or from a newer format."""
    try:
        with gzip.open(path, "rb") as handle:
            raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
        document = json.loads(raw.decode("utf-8")) if len(raw) <= MAX_SNAPSHOT_BYTES else None
    except (OSError, EOFError, ValueError, zlib.error):
        return None
    if not isinstance(document, dict) or document.get("format") != SNAPSHOT_FORMAT:
        return None
    companies = document.get("companies")
    if not isinstance(companies, dict):
        return None
    groups = document.get("industry_groups")
    built = document.get("built_on")
    return Snapshot(
        built_on=built if isinstance(built, str) else None,
        companies=companies,
        industry_groups={k: v for k, v in groups.items() if isinstance(v, str)}
        if isinstance(groups, dict)
        else {},
        industry_read_on=str(document.get("industry_read_on") or ""),
    )
