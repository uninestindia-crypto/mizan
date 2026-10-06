"""What the live-price service says about one share, and how a price earns its label.

A label is a promise about the price, so it is decided when the answer is given, from the clock then
and the age of the price: a price that was live when it was fetched is not live ten seconds on, and a
price is called the last close only when it is dated the last trading day.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from quant_system.live import messages
from quant_system.live.market_hours import IST, is_session_open, last_trading_date

SOURCE = "Upstox"
FRESH_SECONDS = 60
# How far ahead of this computer's clock a price may be stamped before its time is not trusted.
CLOCK_SKEW_SECONDS = 5
# A feed time this far past the last trade means the share has been quiet.
QUIET_AFTER = timedelta(minutes=5)


class Label(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    LAST_CLOSE = "LAST_CLOSE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class RawQuote:
    """A price as Upstox gave it, before it is labelled.

    `quoted_at` is the feed's own time and is None when it did not say. `last_traded_at` is when the share
    last changed hands, which can be long before the feed's time for a quiet share.
    """

    last_price: float
    change_pct: float | None
    quoted_at: datetime | None
    last_traded_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class QuoteEntry:
    label: Label
    last_price: float | None = None
    change_pct: float | None = None
    as_of: str | None = None
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "last_price": self.last_price,
            "change_pct": self.change_pct,
            "label": self.label.value,
            "as_of": self.as_of,
            "source": SOURCE,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class QuoteBatch:
    """The answer to one request: whether Upstox is usable, what to tell the person, and each share."""

    connected: bool
    message: str | None
    quotes: dict[str, QuoteEntry]

    def as_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "message": self.message,
            "quotes": {symbol: entry.as_dict() for symbol, entry in self.quotes.items()},
        }


def unavailable(message: str) -> QuoteEntry:
    return QuoteEntry(Label.UNAVAILABLE, message=message)


def refused_batch(symbols: Sequence[str], message: str) -> QuoteBatch:
    """Nothing could be asked: every share is unavailable, for the same reason."""
    return QuoteBatch(False, message, {symbol: unavailable(message) for symbol in symbols})


def entry_from_quote(raw: RawQuote, now: datetime) -> QuoteEntry:
    label, message = _label_for(raw.quoted_at, now)
    shown_at, traded = raw.quoted_at, raw.last_traded_at
    if shown_at is not None and traded is not None and shown_at - traded > QUIET_AFTER:
        # The label rests on the feed's time, but a quiet share is not presented as freshly traded.
        told = messages.last_traded(traded.astimezone(IST), shown_at.astimezone(IST))
        message = f"{message} {told}" if message else told
        shown_at = traded
    as_of = shown_at.astimezone(IST).isoformat(timespec="seconds") if shown_at else None
    return QuoteEntry(label, raw.last_price, raw.change_pct, as_of, message)


def _label_for(quoted_at: datetime | None, now: datetime) -> tuple[Label, str | None]:
    """Live only while the session is open and the price is under a minute old; the last close only when the price
    is dated the last trading day. A price stamped ahead of the clock, or from an earlier day, is delayed.

    Exchange holidays are unknown here, so a weekday that is really a holiday has a price from the day before and
    is called delayed, never live and never the last close.
    """
    if quoted_at is None:
        return Label.DELAYED, messages.NO_TIME
    if (quoted_at - now).total_seconds() > CLOCK_SKEW_SECONDS:
        return Label.DELAYED, messages.CLOCK_MISMATCH
    if not is_session_open(now):
        return _closed_label(quoted_at, now)
    if (now - quoted_at).total_seconds() < FRESH_SECONDS:
        return Label.LIVE, None
    return Label.DELAYED, messages.OLD_PRICE


def _closed_label(quoted_at: datetime, now: datetime) -> tuple[Label, str | None]:
    quoted_on, last_session = quoted_at.astimezone(IST).date(), last_trading_date(now)
    if quoted_on == last_session:
        return Label.LAST_CLOSE, messages.MARKET_CLOSED
    if quoted_on < last_session:
        return Label.DELAYED, messages.older_than_last_session(quoted_on)
    return Label.DELAYED, messages.not_from_last_session(quoted_on)
