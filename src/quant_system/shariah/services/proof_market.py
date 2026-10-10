"""The 36-month average market value: QuantOS's own daily closing prices times the shares in the filing.

The market-value standard needs a price history and a share count. When either is missing, too short or too old,
the result says why in a plain sentence and the market-value tests are left undecided. Nothing is estimated.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from quant_system.shariah.services.proof_types import MarketValueIn
from quant_system.shariah.services.proof_words import indian_grouping

__all__ = [
    "MAX_LEADING_GAP_DAYS",
    "MAX_PRICE_AGE_DAYS",
    "WINDOW_MONTHS",
    "BarsSource",
    "MarketValueResult",
    "PriceHistory",
    "average_market_value",
]

WINDOW_MONTHS = 36
#: The first price may be this many days after the window opens, so a stock needs about 34 months of history.
MAX_LEADING_GAP_DAYS = 45
#: The newest price may be this many days old. An older price file says nothing about today's market value.
MAX_PRICE_AGE_DAYS = 366
CRORE = Decimal(10_000_000)
Rows = list[tuple[date, Decimal]]


class PriceHistory(Protocol):
    """Daily prices for one stock, oldest first. The market index's bar series fits."""

    @property
    def dates(self) -> Sequence[str]: ...

    @property
    def close(self) -> Any: ...


class BarsSource(Protocol):
    def bars(self, symbol: str, start: str | None = None, end: str | None = None) -> PriceHistory:
        """Daily bars between two dates. Raises when the stock is unknown or no prices are loaded."""


@dataclass(frozen=True, slots=True)
class MarketValueResult:
    """The market value, or None with the plain reason it could not be worked out."""

    value: MarketValueIn | None
    reason: str | None = None


def months_before(day: date, months: int) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def _day(text: str) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def _usable(close: Any) -> Decimal | None:
    """One closing price as an exact decimal, or None when it is not a positive number."""
    try:
        price = Decimal(repr(float(close)))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return price if price.is_finite() and price > 0 else None


def _in_window(history: PriceHistory, start: date, end: date) -> Rows:
    rows = []
    for text, close in zip(history.dates, history.close, strict=False):
        day, price = _day(text), _usable(close)
        if day is not None and price is not None and start <= day <= end:
            rows.append((day, price))
    return rows


def _nice(day: date) -> str:
    return f"{day.day} {day.strftime('%b %Y')}"


def _why_not(symbol: str, rows: Rows, start: date, today: date) -> str | None:
    if not rows:
        return (
            f"QuantOS holds no daily prices for {symbol} in the last 36 months, so the market-value standard "
            "could not be worked out."
        )
    if rows[0][0] > start + timedelta(days=MAX_LEADING_GAP_DAYS):
        return (
            f"QuantOS holds prices for {symbol} only from {_nice(rows[0][0])}, which is shorter than the "
            "36 months the market-value standard averages over."
        )
    if today - rows[-1][0] > timedelta(days=MAX_PRICE_AGE_DAYS):
        return (
            f"QuantOS's newest price for {symbol} is from {_nice(rows[-1][0])}, which is too old to work out "
            "today's market value."
        )
    return None


def _rupees(amount: Decimal) -> str:
    whole, paise = divmod(int(amount * 100), 100)
    return f"₹{indian_grouping(whole)}.{paise:02d}"


def _label(rows: Rows, average: Decimal, shares: int) -> str:
    return (
        f"Average close of {_rupees(average)} from {_nice(rows[0][0])} to {_nice(rows[-1][0])} "
        f"({len(rows)} trading days), times {indian_grouping(shares)} shares"
    )


def average_market_value(
    symbol: str, history: PriceHistory | None, shares: int | None, today: date
) -> MarketValueResult:
    """Average daily close over the 36 months ending at the newest price, times the filed share count, in crore."""
    if shares is None or shares <= 0:
        return MarketValueResult(
            None,
            "The filing does not give a share count QuantOS can use, so the market-value standard could "
            "not be worked out.",
        )
    if history is None:
        return MarketValueResult(
            None,
            f"QuantOS holds no price history for {symbol}, so the market-value standard could not be worked out.",
        )
    newest = max(
        (d for d in map(_day, history.dates) if d is not None and d <= today), default=None
    )
    if newest is None:
        return _no_prices(symbol)
    start = months_before(newest, WINDOW_MONTHS)
    rows = _in_window(history, start, newest)
    why = _why_not(symbol, rows, start, today)
    if why is not None:
        return MarketValueResult(None, why)
    average = sum((price for _, price in rows), Decimal(0)) / len(rows)
    value = MarketValueIn(average * shares / CRORE, shares, _label(rows, average, shares))
    return MarketValueResult(value)


def _no_prices(symbol: str) -> MarketValueResult:
    return MarketValueResult(
        None,
        f"QuantOS holds no daily prices for {symbol}, so the market-value standard could not be worked out.",
    )
