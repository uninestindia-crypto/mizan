"""Liveness and readiness for the app, in the shape monitoring tools expect.

``live`` answers "is the process up". ``ready`` answers "can it do its job right now" and says which
part cannot. A desktop app that merely has no market data yet is *degraded*, not down, so readiness
only fails (HTTP 503) when the app's own state store cannot be read. Every check names what is wrong
in words, so an operator does not need the source to act on it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from quant_system import __version__

Status = Literal["ok", "degraded", "fail"]

#: Data older than this many calendar days is "stale" (a long weekend plus a holiday still passes).
STALE_AFTER_DAYS = 5
#: Warn this many days before the last covered year of the NSE holiday list ends.
CALENDAR_WARN_DAYS = 90
HOLIDAY_FILE = Path("authorities") / "nse-trading-holidays.json"


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def liveness(now: datetime | None = None) -> dict[str, Any]:
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    return {"status": "ok", "version": __version__, "time_utc": stamp}


def holiday_calendar_check(data_folder: Path | None, today: date) -> Check:
    """Whether the NSE holiday list still covers the days ahead.

    The scheduled runner refuses a date outside the covered years instead of assuming it is a trading
    day, so an expired list stops unattended sessions. This says so ahead of time.
    """
    if data_folder is None:
        return Check(
            "holiday_calendar",
            "degraded",
            "No market data is connected, so there is no holiday list.",
        )
    try:
        raw = json.loads((data_folder / HOLIDAY_FILE).read_text(encoding="utf-8"))
        years = sorted(int(y) for y in raw["covers_years"])
    except (OSError, ValueError, KeyError, TypeError):
        return Check(
            "holiday_calendar",
            "degraded",
            "The NSE holiday list is missing or unreadable, so market holidays look like missing sessions.",
        )
    if not years or today.year not in years:
        return Check(
            "holiday_calendar",
            "fail",
            f"The NSE holiday list does not cover {today.year} (it covers {', '.join(map(str, years)) or 'nothing'}).",
        )
    last = date(years[-1], 12, 31)
    left = (last - today).days
    if left <= CALENDAR_WARN_DAYS:
        return Check(
            "holiday_calendar",
            "degraded",
            f"The NSE holiday list covers only to {last:%d %b %Y} ({left} days). Fetch the next "
            f"year's list before then or unattended paper sessions will refuse to run.",
        )
    return Check("holiday_calendar", "ok", f"Covers {years[0]} to {years[-1]}; {left} days remain.")


def market_data_check(latest_session: str | None, today: date) -> Check:
    if latest_session is None:
        return Check("market_data", "degraded", "No market data is connected yet.")
    age = (today - date.fromisoformat(latest_session[:10])).days
    if age > STALE_AFTER_DAYS:
        return Check(
            "market_data",
            "degraded",
            f"Prices run to {latest_session[:10]}, {age} days ago. Paper books will say their orders are out of date.",
        )
    return Check("market_data", "ok", f"Prices run to {latest_session[:10]} ({age} days ago).")


def rollup(checks: list[Check]) -> Status:
    if any(c.status == "fail" for c in checks):
        return "fail"
    if any(c.status == "degraded" for c in checks):
        return "degraded"
    return "ok"
