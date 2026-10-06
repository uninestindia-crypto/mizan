"""Everything a person can read from the live-price service, in plain language.

Each message says what happened and what to click. None names an error code, a setting, a file or a
programming term, because the people reading it are traders and investors, not developers.
"""

from __future__ import annotations

from datetime import date, datetime

NO_KEY = "Add your Upstox key in Settings, then Accounts and keys."
KEY_EXPIRED = (
    "Your Upstox key has expired. Open Settings, then Accounts and keys, and sign in again."
)
KEY_REJECTED = (
    "Upstox did not accept your key. Open Settings, then Accounts and keys, and check it."
)
BUSY = "Upstox is busy. Try again in a minute."
BUSY_LONGER = "Upstox is busy. Try again in a few minutes."
UNREACHABLE = "Could not reach Upstox. Check your internet connection."
TOO_SLOW = "Upstox took too long to answer. Try again in a minute."
TOO_LARGE = (
    "Upstox sent more than QuantOS expected, so the answer was ignored. Try again in a minute."
)
UNREADABLE = "Upstox sent an answer QuantOS could not read. Try again in a minute."
UNAVAILABLE_NOW = "Upstox could not give prices right now. Try again in a minute."
UNAVAILABLE_LONGER = "Upstox could not give prices right now. Try again in a few minutes."
MARKET_CLOSED = "The market is closed. This is the last closing price."
OLD_PRICE = "This price is more than a minute old."
NO_TIME = "Upstox did not say when this price was set."
CLOCK_MISMATCH = "The time on this price does not match your computer's clock."

_month_names = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _day(day: date) -> str:
    return f"{day.day:02d} {_month_names[day.month - 1]}"


def older_than_last_session(day: date) -> str:
    return f"This price is from {_day(day)}, older than the last trading day."


def not_from_last_session(day: date) -> str:
    return f"This price is dated {_day(day)}, which does not match the last trading day."


def last_traded(when: datetime, feed_time: datetime) -> str:
    """When this share last changed hands, in India time. The day is named only when it is not the feed's day."""
    clock = f"{when:%H:%M}"
    if when.date() == feed_time.date():
        return f"This share last traded at {clock}."
    return f"This share last traded on {_day(when.date())} at {clock}."


def not_in_market_data(symbol: str) -> str:
    return f"{symbol} is not in the market data."


def no_price(symbol: str) -> str:
    return f"Upstox has no price for {symbol} right now."
