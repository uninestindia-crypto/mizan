"""Reference data read from a QuantOS data folder: listings, universes and corporate actions.

All inputs are the repository's own authority files. Nothing is fetched from the network here.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from quant_system.data.corporate_actions import parse_subject_factor

LISTINGS_FILE = "nse-all-listed-equities.csv"
LIQUID_UNIVERSE_FILE = "nse-research-universe-liquid-10y.csv"

# Structural actions whose price effect QuantOS cannot size from public data. Returns computed
# across one are not comparable, so screens and the lab must refuse them (fail closed). Splits and
# bonuses are not listed: the provider already back-adjusts them (212 of 212 measured).
BREAKING_COMPONENTS = frozenset({"demerger", "rights"})

_KIND_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("demerger", re.compile(r"de-?merger", re.IGNORECASE)),
    ("rights", re.compile(r"\brights?\b", re.IGNORECASE)),
    ("bonus", re.compile(r"\bbonus\b", re.IGNORECASE)),
    ("split", re.compile(r"split|sub-?division|consolidation", re.IGNORECASE)),
    ("buyback", re.compile(r"buy\s*-?\s*back", re.IGNORECASE)),
    ("dividend", re.compile(r"dividend|distribution", re.IGNORECASE)),
    ("meeting", re.compile(r"general meeting|\bagm\b|\begm\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class Listing:
    symbol: str
    name: str
    isin: str
    instrument_key: str
    series: str
    security_type: str

    @property
    def is_etf(self) -> bool:
        return self.isin.startswith("INF")


@dataclass(frozen=True, slots=True)
class CorporateAction:
    symbol: str
    ex_date: str
    subject: str
    kinds: tuple[str, ...]
    breaks_history: bool


def authorities_dir(data_folder: Path) -> Path:
    return data_folder / "authorities"


def load_listings(data_folder: Path) -> dict[str, Listing]:
    path = authorities_dir(data_folder) / LISTINGS_FILE
    listings: dict[str, Listing] = {}
    if not path.is_file():
        return listings
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            symbol = (row.get("Symbol") or "").strip().upper()
            if not symbol:
                continue
            listings[symbol] = Listing(
                symbol=symbol,
                name=(row.get("Company Name") or "").strip(),
                isin=(row.get("ISIN Code") or "").strip(),
                instrument_key=(row.get("Instrument Key") or "").strip(),
                series=(row.get("Instrument Type") or "").strip(),
                security_type=(row.get("Security Type") or "").strip(),
            )
    return listings


def load_liquid_universe(data_folder: Path) -> list[str]:
    """Symbols of the 423-name research universe (>= 9.5y history, median turnover >= ₹5 crore)."""
    path = authorities_dir(data_folder) / LIQUID_UNIVERSE_FILE
    if not path.is_file():
        return []
    rows = [
        line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")
    ]
    symbols: list[str] = []
    for row in csv.DictReader(rows):
        symbol = (row.get("Symbol") or "").strip().upper()
        if symbol:
            symbols.append(symbol)
    return symbols


def corporate_action_file(data_folder: Path, symbol: str, cache_names: list[str]) -> Path | None:
    """Newest authority file for a symbol: market-cache refreshes first, then the tracked copies."""
    file_name = f"nse-corporate-actions-{symbol}.json"
    for cache_name in sorted(cache_names, reverse=True):
        candidate = (
            data_folder / "evidence" / "market-cache" / cache_name / "corporate-actions" / file_name
        )
        if candidate.is_file():
            return candidate
    fallback = authorities_dir(data_folder) / file_name
    return fallback if fallback.is_file() else None


def load_corporate_actions(path: Path, symbol: str) -> list[CorporateAction]:
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(records, list):
        return []
    actions: list[CorporateAction] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        ex_date = _parse_nse_date(str(record.get("exDate") or ""))
        subject = " ".join(str(record.get("subject") or "").split())
        if ex_date is None or not subject:
            continue
        actions.append(classify_action(symbol, ex_date, subject))
    actions.sort(key=lambda a: a.ex_date)
    return actions


def classify_action(symbol: str, ex_date: str, subject: str) -> CorporateAction:
    kinds = tuple(kind for kind, pattern in _KIND_PATTERNS if pattern.search(subject))
    unsized = set(parse_subject_factor(subject, total_return=False).unsized)
    return CorporateAction(
        symbol=symbol,
        ex_date=ex_date,
        subject=subject,
        kinds=kinds or ("other",),
        breaks_history=bool(unsized & BREAKING_COMPONENTS),
    )


def _parse_nse_date(text: str) -> str | None:
    text = text.strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None
