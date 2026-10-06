"""What the live-price service says about one share, and how a price earns its label.

A label is a promise about the price, so it is decided when the answer is given, from the clock then
and the age of the price: a price that was live when it was fetched is not live ten seconds on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from quant_system.live import messages
from quant_system.live.market_hours import IST, is_session_open

SOURCE = "Upstox"
FRESH_SECONDS = 60


class Label(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    LAST_CLOSE = "LAST_CLOSE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class RawQuote:
    """A price as Upstox gave it, before it is labelled. `quoted_at` is None when it did not say."""

    last_price: float
    change_pct: float | None
    quoted_at: datetime | None


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
    as_of = raw.quoted_at.astimezone(IST).isoformat(timespec="seconds") if raw.quoted_at else None
    return QuoteEntry(label, raw.last_price, raw.change_pct, as_of, message)


def _label_for(quoted_at: datetime | None, now: datetime) -> tuple[Label, str | None]:
    """Closed is the last close. Open is live only when the price is under a minute old.

    Exchange holidays are unknown here, so a weekday that is really a holiday reaches the last
    branch with a price from the day before, and is called delayed, never live.
    """
    if not is_session_open(now):
        return Label.LAST_CLOSE, messages.MARKET_CLOSED
    if quoted_at is None:
        return Label.DELAYED, messages.NO_TIME
    if abs((now - quoted_at).total_seconds()) < FRESH_SECONDS:
        return Label.LIVE, None
    return Label.DELAYED, messages.OLD_PRICE
