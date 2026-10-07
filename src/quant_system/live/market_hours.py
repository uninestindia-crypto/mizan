"""When the NSE cash session is open, in India time.

The session runs 09:15 to 15:30 India time, Monday to Friday. Exchange holidays are not known here,
so a holiday weekday looks open: the price's own age is what keeps such a day from being called live.
India has no daylight saving, so a fixed offset is exact and needs no timezone database (a fresh
Windows laptop has none).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), "IST")
SESSION_OPENS = time(9, 15)
SESSION_CLOSES = time(15, 30)
_SATURDAY = 5


def as_aware(moment: datetime) -> datetime:
    """A moment with a zone. A clock that forgot to say which zone is read as UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def is_session_open(moment: datetime) -> bool:
    """Is it a weekday between 09:15 (inclusive) and 15:30 (exclusive) in India?"""
    local = as_aware(moment).astimezone(IST)
    if local.weekday() >= _SATURDAY:
        return False
    return SESSION_OPENS <= local.time() < SESSION_CLOSES


def last_trading_date(moment: datetime) -> date:
    """The most recent weekday whose session has begun, in India. Before 09:15 that is the day before, and a weekend
    goes back to Friday. Exchange holidays are unknown, so a holiday can be named as a trading day: a price from
    an earlier day is then never mistaken for the last close, which is the safe way to be wrong."""
    local = as_aware(moment).astimezone(IST)
    day = local.date()
    if local.time() < SESSION_OPENS:
        day -= timedelta(days=1)
    while day.weekday() >= _SATURDAY:
        day -= timedelta(days=1)
    return day
