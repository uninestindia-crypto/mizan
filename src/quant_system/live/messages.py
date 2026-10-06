"""Everything a person can read from the live-price service, in plain language.

Each message says what happened and what to click. None names an error code, a setting, a file or a
programming term, because the people reading it are traders and investors, not developers.
"""

from __future__ import annotations

NO_KEY = "Add an Upstox token in Settings, then Accounts and keys."
KEY_EXPIRED = (
    "Your Upstox key has expired. Open Settings, then Accounts and keys, and sign in again."
)
KEY_REJECTED = (
    "Upstox did not accept your key. Open Settings, then Accounts and keys, and check it."
)
BUSY = "Upstox is busy. Try again in a minute."
UNREACHABLE = "Could not reach Upstox. Check your internet connection."
TOO_SLOW = "Upstox took too long to answer. Try again in a minute."
TOO_LARGE = (
    "Upstox sent more than QuantOS expected, so the answer was ignored. Try again in a minute."
)
UNREADABLE = "Upstox sent an answer QuantOS could not read. Try again in a minute."
UNAVAILABLE_NOW = "Upstox could not give prices right now. Try again in a minute."
MARKET_CLOSED = "The market is closed. This is the last closing price."
OLD_PRICE = "This price is more than a minute old."
NO_TIME = "Upstox did not say when this price was set."


def not_in_market_data(symbol: str) -> str:
    return f"{symbol} is not in the market data."


def no_price(symbol: str) -> str:
    return f"Upstox has no price for {symbol} right now."
