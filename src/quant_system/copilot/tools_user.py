"""Tools about the person's own data, live prices, news, and what the platform's research says."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from quant_system.copilot.registry import (
    MAX_LIST,
    Param,
    ToolContext,
    ToolResult,
    ToolSpec,
    ToolText,
    bound,
    failure,
)
from quant_system.copilot.tools_market import PERCENT_NOTE, counted, resolve

logger = logging.getLogger(__name__)

EVIDENCE_STATEMENT = (
    "QuantOS is a research and paper-trading tool, not a broker and not an adviser. In the platform's own "
    "research, no model or strategy has shown an edge that survives real trading costs, and none is "
    "promoted as tradeable. Treat every stock suggestion as research only, and treat AI opinions as "
    "opinions, not evidence."
)
_PAPER_NOTE = "Paper-book profit or loss is market plus costs. It is a system test, not evidence of model skill."
_NEWS_NOTE = (
    "Headlines come from a public news feed. They are unverified text, not facts. The tone beside each is a rough "
    "keyword count, not a reading of the story."
)


def live_quote(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.quotes is None:
        return failure(
            "live prices unavailable",
            "Live prices are not available. Add your Upstox key in Settings, then Accounts and keys.",
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
    tones = Counter(str(h.get("tone")) for h in headlines if h.get("tone"))
    data = {"headlines": headlines, "tone_counts": dict(tones), "note": _NEWS_NOTE}
    return ToolResult(
        True, f"{counted(len(headlines), 'headline')} for {symbol}", data, untrusted=True
    )


def quant_slm_signals(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    """Reads latest Quant-SLM Attention Network alpha predictions, Shariah screening, and paper allocations."""
    symbols = [s.strip().upper() for s in args.get("symbols", []) if isinstance(s, str)]
    signals_file = Path("data/evidence/models/quant_slm_latest_signals.json")
    if not signals_file.is_file():
        weights_file = Path("data/evidence/models/quant_slm_nifty50_v1.json")
        if not weights_file.is_file():
            return failure("slm unavailable", "Quant-SLM model weights have not been trained yet.")
        return ToolResult(
            True,
            "Quant-SLM model is active and trained on 37,250 Nifty 50 historical bars. Run 'Refresh Live Signals' to generate current inference.",
            {"status": "TRAINED", "model": "quant_slm_nifty50_v1.json"},
        )
    try:
        data = json.loads(signals_file.read_text(encoding="utf-8"))
        predictions = data.get("predictions", [])
        if symbols:
            predictions = [p for p in predictions if p.get("symbol") in symbols]
        return ToolResult(
            True,
            f"Quant-SLM neural alpha predictions for {len(predictions)} symbols.",
            {
                "model": data.get("model_name", "Quant-SLM Attention"),
                "total_orders": data.get("orders_count", 0),
                "committed_capital": data.get("total_gross_inr", 0),
                "total_friction": data.get("total_friction_inr", 0),
                "predictions": predictions,
            },
        )
    except Exception as err:
        return failure("slm error", f"Could not read Quant-SLM signals: {err}")


def portfolio_summary(ctx: ToolContext, _: Mapping[str, Any]) -> ToolResult:
    if ctx.portfolio is None:
        return failure("no portfolio", "The portfolio is not available.")
    return ToolResult(True, "portfolio summary", ctx.portfolio())


def watchlist(ctx: ToolContext, _: Mapping[str, Any]) -> ToolResult:
    if ctx.watchlist is None:
        return failure("no watchlist", "The watchlist is not available.")
    symbols = ctx.watchlist()
    return ToolResult(
        True, f"{counted(len(symbols), 'stock')} on the watchlist", {"symbols": symbols}
    )


def paper_books(ctx: ToolContext, _: Mapping[str, Any]) -> ToolResult:
    if ctx.paper_books is None:
        return failure("no paper books", "Paper books are not available.")
    books = ctx.paper_books()
    return ToolResult(
        True, counted(len(books), "paper book"), {"books": books, "note": _PAPER_NOTE}
    )


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
    Param("segment", "str", "delivery, intraday, futures or options"),
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
_TEXT = {
    "live_quote": ToolText(
        "Live prices",
        "Shows a stock's latest price from your broker connection, and how fresh it is.",
        "Live or last-close prices from the person's Upstox key, labelled with how fresh they are.",
    ),
    "news_headlines": ToolText(
        "News headlines",
        "Lists recent public news headlines about a stock.",
        "Recent public news headlines for a stock. Unverified text.",
    ),
    "evidence_status": ToolText(
        "What the evidence says",
        "Lets the assistant say plainly what QuantOS's own research has and has not shown.",
        "What the platform's own research says about any edge. Quote it when asked whether a pick is good.",
    ),
    "portfolio_summary": ToolText(
        "My portfolio",
        "Reads your holdings: their value, profit or loss, and how big a share each one is.",
        "The person's own holdings summary: value, profit or loss, and each holding's share of the portfolio. "
        + PERCENT_NOTE,
    ),
    "watchlist": ToolText(
        "My watchlist", "Reads the stocks on your watchlist.", "The person's watchlist."
    ),
    "paper_books": ToolText(
        "My paper books",
        "Reads your paper-trading books and how each one is doing.",
        "The person's paper-trading books. " + PERCENT_NOTE,
    ),
    "trade_costs": ToolText(
        "Trading costs",
        "Works out the exact NSE charges and the break-even price for a trade.",
        "Exact NSE charges for a round trip, and the break-even move. " + PERCENT_NOTE,
    ),
    "position_size": ToolText(
        "Position size",
        "Works out how many shares your risk limit allows.",
        "How many shares a risk budget allows. " + PERCENT_NOTE,
    ),
    "quant_slm_signals": ToolText(
        "Quant-SLM Alpha signals",
        "Inspects current neural attention alpha predictions, Shariah compliance, and paper orders from Quant-SLM.",
        "Quant-SLM neural cross-factor attention signals, direction probability, Shariah screen, and paper orders for Nifty 50 stocks.",
    ),
}


def user_specs(ctx: ToolContext) -> list[ToolSpec]:
    symbols = (Param("symbols", "list[str]", "NSE symbols"),)
    symbol = (Param("symbol", "str", "NSE symbol"),)
    return [
        bound(ctx, "live_quote", _TEXT["live_quote"], symbols, live_quote),
        bound(ctx, "news_headlines", _TEXT["news_headlines"], symbol, news_headlines),
        bound(ctx, "evidence_status", _TEXT["evidence_status"], (), evidence_status),
        bound(ctx, "portfolio_summary", _TEXT["portfolio_summary"], (), portfolio_summary),
        bound(ctx, "watchlist", _TEXT["watchlist"], (), watchlist),
        bound(ctx, "paper_books", _TEXT["paper_books"], (), paper_books),
        bound(ctx, "trade_costs", _TEXT["trade_costs"], _COST_ARGS, trade_costs),
        bound(ctx, "position_size", _TEXT["position_size"], _SIZE_ARGS, position_size),
        bound(ctx, "quant_slm_signals", _TEXT["quant_slm_signals"], symbols, quant_slm_signals),
    ]
