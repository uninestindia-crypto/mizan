"""When the NSE cash session is open, in India time.

The session runs 09:15 to 15:30 India time, Monday to Friday. Exchange holidays are not known here,
so a holiday weekday looks open: the price's own age is what keeps such a day from being called live.
India has no daylight saving, so a fixed offset is exact and needs no timezone database (a fresh
Windows laptop has none).
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta, timezone

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
