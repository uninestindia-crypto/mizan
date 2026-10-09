"""The exchange's trading holidays, so the top bar can say "Market open" only when it is allowed to.

Read-only. The list is the NSE authority file that ships with the app (``data/authorities/nse-trading-holidays.json``).
It names the years it covers, and a date in a year it does not cover can never be called a trading day: this route
reports the years along with the holidays so the screen can tell "no holiday today" from "no list for this year".

A missing, unreadable or inconsistent file is not an error. The answer is then an empty list with no years, which
the screen reads as "holidays unknown" and keeps saying "Market hours".
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/market", tags=["Market"])
__all__ = ["HOLIDAY_FILE", "holiday_list", "router"]

HOLIDAY_FILE = Path("authorities") / "nse-trading-holidays.json"
REPO_ROOT = Path(__file__).resolve().parents[4]


def _nothing_known() -> dict[str, Any]:
    return {"years": [], "holidays": [], "source": None, "fetched_at": None}


def _roots() -> list[Path]:
    """Folders that can hold a ``data`` folder, best first: an explicit app root, the built app, the checkout."""
    roots: list[Path] = []
    override = os.environ.get("QUANTOS_APP_ROOT")
    if override:
        roots.append(Path(override))
    if getattr(sys, "frozen", False):
        beside = Path(sys.executable).resolve().parent
        roots += [beside, beside / "_internal"]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(Path(bundle))
    roots.append(REPO_ROOT)
    return list(dict.fromkeys(roots))


def _display_name(text: str) -> str:
    """The holiday's name as a person reads it: the authority's trailing footnote mark is not part of the name."""
    return text.strip().rstrip("*").strip()


def _parse(raw: Any) -> dict[str, Any] | None:
    """The list in the shape the screen reads, or None when any part of the file cannot be trusted."""
    if not isinstance(raw, dict):
        return None
    years = sorted({int(year) for year in raw["covers_years"]})
    if not years or any(not 1900 <= year <= 2999 for year in years):
        return None
    seen: dict[str, str] = {}
    for entry in raw["holidays"]:
        day = date.fromisoformat(str(entry["date"]))
        name = _display_name(str(entry["description"]))
        if not name:
            return None
        seen[day.isoformat()] = name
    holidays = [{"date": day, "name": seen[day]} for day in sorted(seen)]
    source = raw.get("authority")
    fetched = raw.get("fetched_at_utc")
    return {
        "years": years,
        "holidays": holidays,
        "source": source if isinstance(source, str) else None,
        "fetched_at": fetched if isinstance(fetched, str) else None,
    }


def holiday_list() -> dict[str, Any]:
    """The readable, consistent holiday file that reaches the latest year, or an empty answer when none can be trusted.

    A copy left in a data folder years ago must not hide a newer one that ships with the app, so the copy that
    covers the latest year wins; when two reach the same year, the one found first (the app's own) wins.
    """
    best: dict[str, Any] | None = None
    for root in _roots():
        try:
            parsed = _parse(json.loads((root / "data" / HOLIDAY_FILE).read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if parsed is not None and (best is None or parsed["years"][-1] > best["years"][-1]):
            best = parsed
    return best if best is not None else _nothing_known()


@router.get("/holidays")
def market_holidays() -> dict[str, Any]:
    return holiday_list()
