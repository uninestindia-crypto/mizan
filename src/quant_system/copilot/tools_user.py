"""Tools about the person's own data, live prices, news, and what the platform's research says."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from quant_system.copilot.registry import (
    MAX_LIST,
    Param,
    ToolContext,
    ToolResult,
    ToolSpec,
    bound,
    failure,
)
from quant_system.copilot.tools_market import resolve

logger = logging.getLogger(__name__)

EVIDENCE_STATEMENT = (
    "QuantOS is a research and paper-trading tool, not a broker and not an adviser. In the platform's own "
    "research, no model or strategy has shown an edge that survives real trading costs, and none is "
    "promoted as tradeable. Treat every stock suggestion as research only, and treat AI opinions as "
    "opinions, not evidence."
)
_PAPER_NOTE = "Paper-book profit or loss is market plus costs. It is a system test, not evidence of model skill."
_NEWS_NOTE = "Headlines come from a public news feed. They are unverified text, not facts."


def live_quote(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.quotes is None:
        return failure(
            "live prices unavailable",
            "Live prices are not available. Add an Upstox token in Settings, then Accounts and keys.",
        )
    symbols = [s.strip().upper() for s in args["symbols"][:MAX_LIST]]
    return ToolResult(
        True, f"live quotes for {', '.join(symbols)}", {"quotes": ctx.quotes.quotes(symbols)}
    )


def _news_query(ctx: ToolContext, symbol: str) -> str:
    found = resolve(ctx, symbol)
    return str(found[1].get("name") or symbol) if found else symbol


def news_headlines(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.news is None:
        return failure("news unavailable", "News search is not available.")
    symbol = str(args["symbol"]).strip().upper()
    try:
        headlines = ctx.news.headlines(_news_query(ctx, symbol))
    except Exception:
        logger.exception("news lookup failed")
        return failure(
            "news lookup failed",
            "Headlines could not be fetched right now (no connection, or the source refused).",
        )
    data = {"headlines": headlines, "note": _NEWS_NOTE}
    return ToolResult(True, f"{len(headlines)} headline(s) for {symbol}", data, untrusted=True)


def portfolio_summary(ctx: ToolContext, _: Mapping[str, Any]) -> ToolResult:
    if ctx.portfolio is None:
        return failure("no portfolio", "The portfolio is not available.")
    return ToolResult(True, "portfolio summary", ctx.portfolio())


def watchlist(ctx: ToolContext, _: Mapping[str, Any]) -> ToolResult:
    if ctx.watchlist is None:
        return failure("no watchlist", "The watchlist is not available.")
    symbols = ctx.watchlist()
    return ToolResult(True, f"{len(symbols)} on the watchlist", {"symbols": symbols})


def paper_books(ctx: ToolContext, _: Mapping[str, Any]) -> ToolResult:
    if ctx.paper_books is None:
        return failure("no paper books", "Paper books are not available.")
    books = ctx.paper_books()
    return ToolResult(True, f"{len(books)} paper book(s)", {"books": books, "note": _PAPER_NOTE})


def trade_costs(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.trade_costs is None:
        return failure("no cost model", "The cost calculator is not available.")
    return ToolResult(True, "trade costs", ctx.trade_costs(args))


def position_size(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.position_size is None:
        return failure("no sizing", "The position-size calculator is not available.")
    return ToolResult(True, "position size", ctx.position_size(args))


def evidence_status(_ctx: ToolContext, _: Mapping[str, Any]) -> ToolResult:
    return ToolResult(True, "evidence status", {"statement": EVIDENCE_STATEMENT})


_COST_ARGS = (
    Param("segment", "str", "delivery, intraday or fno"),
    Param("buy_price", "number", "rupees"),
    Param("sell_price", "number", "rupees"),
    Param("quantity", "number", "shares"),
)
_SIZE_ARGS = (
    Param("capital", "number", "rupees"),
    Param("risk_pct", "number", "percent"),
    Param("entry", "number", "rupees"),
    Param("stop", "number", "rupees"),
)
_QUOTE_HELP = (
    "Live or last-close prices from the person's Upstox token, labelled with how fresh they are."
)
_EVIDENCE_HELP = "What the platform's own research says about any edge. Quote it when asked whether a pick is good."


def _information_specs(ctx: ToolContext) -> list[ToolSpec]:
    symbols = (Param("symbols", "list[str]", "NSE symbols"),)
    symbol = (Param("symbol", "str", "NSE symbol"),)
    return [
        bound(ctx, "live_quote", "Live prices", _QUOTE_HELP, symbols, live_quote),
        bound(
            ctx,
            "news_headlines",
            "News headlines",
            "Recent public news headlines for a stock. Unverified text.",
            symbol,
            news_headlines,
        ),
        bound(
            ctx, "evidence_status", "What the evidence says", _EVIDENCE_HELP, (), evidence_status
        ),
    ]


def _own_data_specs(ctx: ToolContext) -> list[ToolSpec]:
    return [
        bound(
            ctx,
            "portfolio_summary",
            "My portfolio",
            "The person's own holdings summary.",
            (),
            portfolio_summary,
        ),
        bound(ctx, "watchlist", "My watchlist", "The person's watchlist.", (), watchlist),
        bound(
            ctx,
            "paper_books",
            "My paper books",
            "The person's paper-trading books.",
            (),
            paper_books,
        ),
        bound(
            ctx,
            "trade_costs",
            "Trading costs",
            "Exact NSE charges for a round trip.",
            _COST_ARGS,
            trade_costs,
        ),
        bound(
            ctx,
            "position_size",
            "Position size",
            "How many shares a risk budget allows.",
            _SIZE_ARGS,
            position_size,
        ),
    ]


def user_specs(ctx: ToolContext) -> list[ToolSpec]:
    return [*_information_specs(ctx), *_own_data_specs(ctx)]
