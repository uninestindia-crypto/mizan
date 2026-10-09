"""Connects the Copilot's read-only tools to the app's own data: market index, halal sample, portfolio, news.

Nothing here writes anything. Every callable reads what the app already holds and shapes it into the small, honest
summaries the tools hand to a model or show to a person.
"""

from __future__ import annotations

import math
import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

from quant_system.copilot.news import GoogleNewsSource
from quant_system.copilot.registry import ToolContext, UserFacingError
from quant_system.copilot.sources import SqliteShariahSource
from quant_system.server.v2.credentials import AI_KEY_NAMES
from quant_system.server.v2.portfolio import portfolio_summary
from quant_system.server.v2.tools import SEGMENTS, ToolError, position_size, trade_costs

__all__ = ["key_lookup", "live_prices_status", "news_source", "tool_context"]

_NEWS = GoogleNewsSource()
_NO_DATA = "Market data is not connected yet. Open Settings, then Market data."
_BAD_NUMBERS = "Those numbers could not be used. Check the prices and the quantity and try again."
_WHOLE_SHARES = "The quantity must be a whole number of shares, for example 10."
_HOLDING_KEYS = ("symbol", "quantity", "avg_price", "close", "value", "pnl")
_BOOK_KEYS = ("name", "status", "last_session", "sessions")
# The app's own calculators hand back ratios (0.05 for 5%). Everything the Copilot reports in a field named
# "..._pct" is in percent points (5.0), the same as the price facts, so a model that quotes it is never 100 times off.
_COST_RATIOS = ("charges_pct_of_turnover", "breakeven_move_pct")
_SIZE_RATIOS = ("stop_distance_pct", "capital_used_pct")


def news_source() -> GoogleNewsSource:
    return _NEWS


def _percent_points(ratio: Any, digits: int = 2) -> float | None:
    """A ratio such as 0.0031 as percent points (0.31). Missing or unusable stays missing."""
    try:
        points = float(ratio) * 100.0
    except (TypeError, ValueError):
        return None
    return round(points, digits) if math.isfinite(points) else None


def _in_percent_points(result: dict[str, Any], *names: str) -> dict[str, Any]:
    return {**result, **{name: _percent_points(result[name], 3) for name in names}}


def key_lookup(provider: str) -> str | None:
    """A saved AI key for the provider: the app's saved keys are copied into the environment at start-up."""
    from quant_system.server.v2.router import services

    name = AI_KEY_NAMES.get(provider)
    if name is None:
        return None
    return os.environ.get(name) or services().credentials.get(name)


def live_prices_status() -> dict[str, Any]:
    """Whether live prices can be asked for right now: a broker key is saved and has not expired."""
    from quant_system.server.v2.live_routes import key_readiness
    from quant_system.server.v2.router import services

    return key_readiness(services().credentials)


def _quotes() -> Any:
    from quant_system.server.v2.live_routes import quote_service

    return quote_service()


def _shariah_path() -> Path:
    """Where the halal sample lives: the Shariah package's own path setting (the same file its screens read)."""
    from quant_system.shariah.core.config import settings

    return Path(settings.SQLITE_DB_PATH)


def _open_read_only(path: Path) -> sqlite3.Connection:
    """The halal database opened so that nothing can be written, no file is created and no journal mode is set.

    The Shariah package's own connection sets a journal mode on open, which rewrites the bundled sample file and
    creates an empty database when the file is missing. The Copilot only ever reads, so it opens the file read-only.
    The address is built from the path (not pasted into the text) so a folder with a space or a ``#`` still opens.
    """
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _shariah() -> SqliteShariahSource:
    return SqliteShariahSource(lambda: _open_read_only(_shariah_path()))


def _portfolio() -> dict[str, Any]:
    from quant_system.server.v2.router import _broker, _today, services

    svc = services()
    holdings = svc.state.holdings()
    if not holdings:
        return {
            "holdings": [],
            "totals": None,
            "note": "No holdings added yet. Add them on the Portfolio screen.",
        }
    if not svc.index.is_ready():
        raise UserFacingError(_NO_DATA)
    full = portfolio_summary(svc.index, holdings, _broker(svc.state.settings()), _today())
    return {
        "totals": {**full["totals"], "pnl_pct": _percent_points(full["totals"].get("pnl_pct"))},
        "warnings": full["warnings"],
        "holdings": [_holding(row) for row in full["holdings"]][:30],
        "note": "Values use each stock's last end-of-day close, not live prices.",
    }


def _holding(row: dict[str, Any]) -> dict[str, Any]:
    kept = {key: row.get(key) for key in _HOLDING_KEYS}
    return {
        **kept,
        "pnl_pct": _percent_points(row.get("pnl_pct")),
        "weight_pct": _percent_points(row.get("weight")),
    }


def _broker_account() -> dict[str, Any]:
    """A short, view-only summary of the person's broker account, if they have allowed the assistant to see it."""
    from quant_system.broker_view import BrokerViewError
    from quant_system.server.v2.broker_routes import broker_view_service

    try:
        return broker_view_service().assistant_summary()
    except BrokerViewError as error:
        raise UserFacingError(error.message) from error


def _paper_books() -> list[dict[str, Any]]:
    from quant_system.server.v2.router import services

    svc = services()
    if not svc.index.is_ready():
        raise UserFacingError(_NO_DATA)
    return [_book(book) for book in svc.paper.summaries(svc.index)]


def _book(book: dict[str, Any]) -> dict[str, Any]:
    kept = {key: book.get(key) for key in _BOOK_KEYS}
    return {
        **kept,
        "return_pct": _percent_points(book.get("return")),
        "benchmark_return_pct": _percent_points(book.get("benchmark_return")),
        "excess_pct": _percent_points(book.get("excess")),
    }


def _whole_shares(value: Any) -> int:
    """A share count that really is a whole number. 10.7 is refused, never quietly cut to 10."""
    try:
        number = float(value)
    except (OverflowError, ValueError) as error:
        raise UserFacingError(_WHOLE_SHARES) from error
    if not number.is_integer():  # also false for NaN and infinity
        raise UserFacingError(_WHOLE_SHARES)
    return int(number)


def _decimals(args: Any, names: tuple[str, ...]) -> list[Decimal]:
    """The named numbers as exact decimals. NaN and infinity are not numbers a calculator can use."""
    numbers = [Decimal(str(args[name])) for name in names]
    if not all(number.is_finite() for number in numbers):
        raise ValueError("not a finite number")
    return numbers


def _costs(args: Any) -> dict[str, Any]:
    from quant_system.server.v2.router import _broker, _today, services

    segment = str(args["segment"]).lower()
    if segment not in SEGMENTS:
        raise UserFacingError("The segment must be delivery, intraday, futures or options.")
    broker = _broker(services().state.settings())
    quantity = _whole_shares(args["quantity"])
    try:
        buy, sell = _decimals(args, ("buy_price", "sell_price"))
        result = trade_costs(segment, buy, sell, quantity, _today(), broker)  # type: ignore[arg-type]
    except ToolError as error:
        raise UserFacingError(str(error)) from error
    except (ArithmeticError, ValueError) as error:
        raise UserFacingError(_BAD_NUMBERS) from error
    return _in_percent_points(result, *_COST_RATIOS)


def _size(args: Any) -> dict[str, Any]:
    try:
        capital, risk, entry, stop = _decimals(args, ("capital", "risk_pct", "entry", "stop"))
        result = position_size(capital, risk, entry, stop)
    except ToolError as error:
        raise UserFacingError(str(error)) from error
    except (ArithmeticError, ValueError) as error:
        raise UserFacingError(_BAD_NUMBERS) from error
    return _in_percent_points(result, *_SIZE_RATIOS)


def tool_context() -> ToolContext:
    from quant_system.server.v2.router import services

    svc = services()
    return ToolContext(
        index=svc.index if svc.index.is_ready() else None,
        shariah=_shariah(),
        news=news_source(),
        quotes=_quotes(),
        portfolio=_portfolio,
        watchlist=svc.state.watchlist,
        paper_books=_paper_books,
        trade_costs=_costs,
        position_size=_size,
        broker=_broker_account,
    )
