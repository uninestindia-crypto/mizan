"""One company at a time: its series, metrics, scorecard and how far its data can be trusted.

The clock is injected; nothing here reads the real time. `data_status` is earned: VERIFIED_FILING only for figures
read from a filing that passed its own checks and is not older than 18 months, STALE for older ones, and
NOT_AVAILABLE when no filing could be used (and the reason is stated).
"""

from __future__ import annotations

import calendar
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final, Protocol

from quant_system.fundamentals import fmt
from quant_system.fundamentals.metric_types import Metrics, PriceQuote
from quant_system.fundamentals.metrics import compute_metrics
from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.scorecard import Scorecard, build_scorecard
from quant_system.fundamentals.series import Series, build_series
from quant_system.fundamentals.store import FundamentalsStore

STALE_AFTER_MONTHS: Final = 18
VERIFIED: Final = "VERIFIED_FILING"
STALE: Final = "STALE"
UNAVAILABLE: Final = "NOT_AVAILABLE"
NO_FILINGS: Final = (
    "No filings held for this company yet. You can ask QuantOS to read its latest results from NSE."
)
VERIFIED_NOTICE: Final = (
    "These figures are read from the company's own quarterly results filings on NSE. "
    "Each one links to its filing, with the filing's date and fingerprint."
)
NONE_USABLE: Final = "QuantOS holds filings for this company, but none passed its own checks, so no figures are shown."


class PriceReader(Protocol):
    def symbol_info(self, symbol: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class CompanyAnalysis:
    symbol: str
    company_name: str
    industry: str | None
    series: Series
    metrics: Metrics
    scorecard: Scorecard
    data_status: str
    data_notice: str
    read_status: str
    price: PriceQuote | None
    today: date


def months_before(today: date, months: int) -> date:
    year, month = divmod(today.year * 12 + today.month - 1 - months, 12)
    return date(year, month + 1, min(today.day, calendar.monthrange(year, month + 1)[1]))


def quote_of(close: object, as_of: object) -> PriceQuote | None:
    """A price quote from a close and a session date, or None when either is missing or unusable."""
    try:
        if not close or not as_of or Decimal(str(close)) <= 0:
            return None
        return PriceQuote(Decimal(str(close)), date.fromisoformat(str(as_of)[:10]))
    except (ValueError, ArithmeticError):
        return None


def price_for(index: PriceReader | None, symbol: str) -> PriceQuote | None:
    """The platform's own last close for a stock, or None when market data is missing for it."""
    if index is None:
        return None
    try:
        snapshot = index.symbol_info(symbol).get("snapshot") or {}
    except LookupError:
        return None
    return quote_of(snapshot.get("close"), snapshot.get("asof"))


def _held_status(ended: date, today: date) -> tuple[str, str, str]:
    if ended >= months_before(today, STALE_AFTER_MONTHS):
        return VERIFIED, VERIFIED_NOTICE, "READ_OK"
    notice = (
        f"The newest filing held is for the quarter ended {fmt.day(ended)}, more than "
        f"{STALE_AFTER_MONTHS} months ago. Treat these figures as old."
    )
    return STALE, notice, "READ_OK"


def _status(series: Series, today: date) -> tuple[str, str, str]:
    """(data_status, notice, read_status)."""
    if series.latest is not None:
        return _held_status(series.latest.period_end, today)
    if series.unread is not None and series.unread.status.value == "FORMAT_NOT_READ":
        return UNAVAILABLE, series.unread.note, "FORMAT_NOT_READ"
    if series.excluded or series.unread is not None:
        return UNAVAILABLE, NONE_USABLE, "NONE_USABLE"
    return UNAVAILABLE, NO_FILINGS, "NO_FILINGS"


class FundamentalsService:
    def __init__(self, store: FundamentalsStore, today: Callable[[], date]) -> None:
        self._store = store
        self._today = today

    @property
    def store(self) -> FundamentalsStore:
        return self._store

    def today(self) -> date:
        return self._today()

    def analyse(self, symbol: str, price: PriceQuote | None) -> CompanyAnalysis:
        return self._analyse(symbol.upper(), self._store.quarters(symbol), price)

    def analyse_all(self, prices: Callable[[str], PriceQuote | None]) -> list[CompanyAnalysis]:
        """Every company held, each with its own price (if any). Reads the stores once."""
        held = self._store.all_quarters()
        return [self._analyse(symbol, rows, prices(symbol)) for symbol, rows in held.items()]

    def _analyse(
        self, symbol: str, rows: list[QuarterFigures], price: PriceQuote | None
    ) -> CompanyAnalysis:
        today = self._today()
        series = build_series(rows)
        status, notice, read_status = _status(series, today)
        usable_price = price if series.latest is not None else None
        metrics = compute_metrics(series, usable_price)
        card = build_scorecard(metrics, series, status == STALE)
        name = series.company_name or (rows[0].company_name if rows else "")
        return CompanyAnalysis(
            symbol=symbol,
            company_name=name,
            industry=self._store.industry(symbol),
            series=series,
            metrics=metrics,
            scorecard=card,
            data_status=status,
            data_notice=notice,
            read_status=read_status,
            price=usable_price,
            today=today,
        )


def price_book(index: Any) -> Callable[[str], PriceQuote | None]:
    """A fast price lookup for many stocks: the index's snapshot read once, or one stock at a time as a fallback."""
    try:
        rows = index.snapshot("all")
    except (AttributeError, LookupError, RuntimeError):
        return lambda symbol: price_for(index, symbol)
    quotes = {str(row["symbol"]): quote_of(row.get("close"), row.get("asof")) for row in rows}
    prices = {symbol: quote for symbol, quote in quotes.items() if quote is not None}
    return prices.get
