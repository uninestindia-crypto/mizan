"""Connects the Copilot's read-only tools to the app's own data: market index, halal sample, portfolio, news.

Nothing here writes anything. Every callable reads what the app already holds and shapes it into the small, honest
summaries the tools hand to a model or show to a person.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

from quant_system.copilot.news import GoogleNewsSource
from quant_system.copilot.registry import ToolContext, UserFacingError
from quant_system.copilot.sources import SqliteShariahSource
from quant_system.server.v2.credentials import AI_KEY_NAMES
from quant_system.server.v2.portfolio import portfolio_summary
from quant_system.server.v2.tools import SEGMENTS, ToolError, position_size, trade_costs

__all__ = ["key_lookup", "news_source", "tool_context"]

_NEWS = GoogleNewsSource()
_NO_DATA = "Market data is not connected yet. Open Settings, then Data."
_BAD_NUMBERS = "Those numbers could not be used. Check the prices and the quantity and try again."
_HOLDING_KEYS = ("symbol", "quantity", "avg_price", "close", "value", "pnl", "pnl_pct", "weight")
_BOOK_KEYS = ("name", "status", "return", "benchmark_return", "excess", "last_session", "sessions")


def news_source() -> GoogleNewsSource:
    return _NEWS


def key_lookup(provider: str) -> str | None:
    """A saved AI key for the provider: the app's saved keys are copied into the environment at start-up."""
    from quant_system.server.v2.router import services

    name = AI_KEY_NAMES.get(provider)
    if name is None:
        return None
    return os.environ.get(name) or services().credentials.get(name)


def _shariah() -> SqliteShariahSource:
    from quant_system.shariah.db.session import get_db_connection

    return SqliteShariahSource(get_db_connection)


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
        "totals": full["totals"],
        "warnings": full["warnings"],
        "holdings": [{key: row.get(key) for key in _HOLDING_KEYS} for row in full["holdings"]][:30],
        "note": "Values use each stock's last end-of-day close, not live prices.",
    }


def _paper_books() -> list[dict[str, Any]]:
    from quant_system.server.v2.router import services

    svc = services()
    if not svc.index.is_ready():
        raise UserFacingError(_NO_DATA)
    return [{key: book.get(key) for key in _BOOK_KEYS} for book in svc.paper.summaries(svc.index)]


def _costs(args: Any) -> dict[str, Any]:
    from quant_system.server.v2.router import _broker, _today, services

    segment = str(args["segment"]).lower()
    if segment not in SEGMENTS:
        raise UserFacingError("The segment must be delivery, intraday, futures or options.")
    broker = _broker(services().state.settings())
    try:
        buy, sell = Decimal(str(args["buy_price"])), Decimal(str(args["sell_price"]))
        return trade_costs(segment, buy, sell, int(args["quantity"]), _today(), broker)  # type: ignore[arg-type]
    except ToolError as error:
        raise UserFacingError(str(error)) from error
    except (ArithmeticError, ValueError) as error:
        raise UserFacingError(_BAD_NUMBERS) from error


def _size(args: Any) -> dict[str, Any]:
    try:
        numbers = [Decimal(str(args[name])) for name in ("capital", "risk_pct", "entry", "stop")]
        return position_size(numbers[0], numbers[1], numbers[2], numbers[3])
    except ToolError as error:
        raise UserFacingError(str(error)) from error
    except (ArithmeticError, ValueError) as error:
        raise UserFacingError(_BAD_NUMBERS) from error


def tool_context() -> ToolContext:
    from quant_system.server.v2.router import services

    svc = services()
    return ToolContext(
        index=svc.index if svc.index.is_ready() else None,
        shariah=_shariah(),
        news=news_source(),
        portfolio=_portfolio,
        watchlist=svc.state.watchlist,
        paper_books=_paper_books,
        trade_costs=_costs,
        position_size=_size,
    )
