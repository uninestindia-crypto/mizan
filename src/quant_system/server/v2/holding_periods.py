"""How long each buy lot has been held, as facts. No tax rates and no tax amounts: rates change.

The 12-month date of a lot is the same day of the month twelve months later; a lot bought on 29 February has no such
day the next year, so its 12-month date is 28 February. A lot is shown as held longer than 12 months only once today
is after its 12-month date (the common test is "more than 12 months", so the date itself is not yet counted).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

__all__ = ["HOLDING_PERIOD_NOTE", "holding_period", "twelve_months_after"]

HOLDING_PERIOD_NOTE: Final = (
    "Holding periods are shown as facts. Check current tax rules or ask an adviser."
)


def twelve_months_after(day: date) -> date:
    """The same date a year on, or 28 February for a 29 February start."""
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return date(day.year + 1, 2, 28)


def holding_period(buy_date: str, today: date) -> dict[str, Any] | None:
    """The facts about one buy lot, or None when its date cannot be read."""
    try:
        bought = date.fromisoformat(buy_date[:10])
    except ValueError:
        return None
    long_term_on = twelve_months_after(bought)
    return {
        "buy_date": bought.isoformat(),
        "days_held": max(0, (today - bought).days),
        "long_term_on": long_term_on.isoformat(),
        "is_long_term": today > long_term_on,
    }
