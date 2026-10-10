"""The bundled snapshot: a versioned, gzip-compressed JSON document of real filing figures."""

from __future__ import annotations

import gzip
import json
import os
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from quant_system.shariah.filings.models import FilingFigures, normalize_symbol

SNAPSHOT_FORMAT: Final = 1
SNAPSHOT_SOURCE: Final = "NSE corporate-financial-results XBRL"
INDUSTRY_SOURCE: Final = "NSE Nifty Total Market list"
MAX_SNAPSHOT_BYTES: Final = 256 * 1024 * 1024


class FilingsStoreError(Exception):
    """Saving or building failed. The message is plain language."""


@dataclass(frozen=True)
class IndustrySnapshot:
    groups: Mapping[str, str]
    read_on: str


@dataclass(frozen=True)
class Snapshot:
    built_on: str | None
    filings: dict[str, Any]
    industry_groups: dict[str, str] = field(default_factory=dict)
    industry_read_on: str = ""


def check_row(symbol: str, figures: FilingFigures) -> None:
    """A snapshot row must be the named company's and must carry its proof."""
    if normalize_symbol(symbol) != symbol or figures.symbol != symbol:
        raise FilingsStoreError(f"{symbol}: the figures belong to {figures.symbol}, not {symbol}.")
    if not figures.proof.sha256:
        raise FilingsStoreError(
            f"{symbol}: the filing has no recorded sha256, so it was not written."
        )
    if not figures.proof.source_url:
        raise FilingsStoreError(
            f"{symbol}: the filing has no recorded source_url, so it was not written."
        )


def write_snapshot(
    path: Path,
    filings: Mapping[str, FilingFigures],
    built_on: str,
    industry: IndustrySnapshot | None = None,
) -> None:
    """Write the same bytes for the same input: sorted keys, no timestamps, no wall clock."""
    for symbol, figures in filings.items():
        check_row(symbol, figures)
    document: dict[str, Any] = {
        "format": SNAPSHOT_FORMAT,
        "built_on": built_on,
        "source": SNAPSHOT_SOURCE,
        "filings": {symbol: figures.to_json_dict() for symbol, figures in filings.items()},
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
    filings = document.get("filings")
    if not isinstance(filings, dict):
        return None
    groups = document.get("industry_groups")
    built = document.get("built_on")
    return Snapshot(
        built_on=built if isinstance(built, str) else None,
        filings=filings,
        industry_groups={k: v for k, v in groups.items() if isinstance(v, str)}
        if isinstance(groups, dict)
        else {},
        industry_read_on=str(document.get("industry_read_on") or ""),
    )
