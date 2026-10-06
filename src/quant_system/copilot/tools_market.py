"""Tools about the market: finding a stock, its price facts, and proposing a screen or a second opinion."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quant_system.copilot.registry import (
    MAX_TEXT,
    Param,
    Proposal,
    ToolContext,
    ToolResult,
    ToolSpec,
    ToolText,
    bound,
    failure,
)

# Screens the Copilot may suggest. The path is fixed here; the model only picks a key.
SCREENS: dict[str, str] = {
    "home": "/",
    "markets": "/markets",
    "lab": "/lab",
    "portfolio": "/portfolio",
    "paper": "/paper",
    "tools": "/tools/costs",
    "shariah": "/shariah",
    "settings_keys": "/settings/accounts",
    "settings_data": "/settings/data",
}

# What each screen is called in the app, so a button reads like the menu it opens. The Settings screens are named
# as the tabs on the Settings screen name them.
SCREEN_NAMES: dict[str, str] = {
    "home": "Home",
    "markets": "Markets",
    "lab": "Strategy Lab",
    "portfolio": "Portfolio",
    "paper": "Paper trading",
    "tools": "Tools",
    "shariah": "Mizan Shariah",
    "settings_keys": "Accounts and keys",
    "settings_data": "Market data",
}

NO_MARKET_DATA = "Market data is not connected yet. Open Settings, then Market data."
SYMBOL = Param("symbol", "str", "NSE symbol, e.g. TCS")
# For the model, appended to the description of every tool whose result carries a percentage.
PERCENT_NOTE = "Every field ending in _pct is in percent points: 5.2 means 5.2%, never 0.052."


def counted(number: int, noun: str) -> str:
    """ "1 stock", "2 stocks": a count a person can read, never "stock(s)"."""
    return f"{number} {noun}{'' if number == 1 else 's'}"


def pct(value: Any) -> float | None:
    return None if value is None else round(float(value) * 100.0, 2)


def resolve(ctx: ToolContext, symbol: str) -> tuple[str, dict[str, Any]] | None:
    """The canonical symbol and its info, or None when the stock is not in the market data."""
    if ctx.index is None:
        return None
    try:
        info = ctx.index.symbol_info(ctx.index.resolve(symbol))
    except LookupError:
        return None
    return str(info["symbol"]), info


def _no_data() -> ToolResult:
    return failure("market data not connected", NO_MARKET_DATA)


def _unknown(symbol: object) -> ToolResult:
    return failure(f"{symbol}: not found", f"{str(symbol).upper()} is not in the market data.")


def find_stock(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.index is None:
        return _no_data()
    rows = ctx.index.search(str(args["query"])[:MAX_TEXT], limit=5)
    matches = [{"symbol": r["symbol"], "name": r["name"]} for r in rows]
    found = f"Found {counted(len(matches), 'stock')} for {args['query']}"
    return ToolResult(True, found, {"matches": matches})


def stock_facts(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.index is None:
        return _no_data()
    found = resolve(ctx, str(args["symbol"]))
    if found is None:
        return _unknown(args["symbol"])
    symbol, info = found
    stats = ctx.index.stock_stats(symbol)
    series = ctx.index.bars(symbol)
    last_session = str(series.dates[-1])
    snapshot = info.get("snapshot") or {}
    data = {
        "symbol": symbol,
        "name": info.get("name"),
        "last_session": last_session,
        "last_close": float(series.close[-1]),
        "return_1m_pct": pct(stats.get("ret_1m")),
        "return_6m_pct": pct(stats.get("ret_6m")),
        "return_1y_pct": pct(stats.get("ret_1y")),
        "volatility_1y_pct": pct(stats.get("vol_1y")),
        "max_drawdown_1y_pct": pct(stats.get("max_drawdown_1y")),
        "beta_1y": stats.get("beta_1y"),
        "average_daily_turnover_cr": snapshot.get("turnover_cr"),
        "from_52w_high_pct": pct(snapshot.get("from_52w_high")),
        "provenance": f"Local end-of-day price data, last session {last_session}. Not live.",
    }
    return ToolResult(True, f"{symbol}: facts as of {last_session}", data)


def suggest_screen(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    screen = str(args["screen"])
    if screen == "stock":
        return _suggest_stock(ctx, str(args.get("symbol", "")))
    path = SCREENS.get(screen)
    if path is None:
        return failure("unknown screen", f"Screens I can suggest: stock, {', '.join(SCREENS)}.")
    name = SCREEN_NAMES[screen]
    proposal = Proposal("navigate", f"Open {name}", path)
    return ToolResult(True, f"Suggested opening {name}", {"screen": screen}, proposals=[proposal])


def _suggest_stock(ctx: ToolContext, symbol: str) -> ToolResult:
    if ctx.index is None:
        return _no_data()
    found = resolve(ctx, symbol)
    if found is None:
        return failure("unknown stock", "That stock is not in the market data.")
    name = found[0]
    proposal = Proposal("navigate", f"Open {name}", f"/stock/{name}", name)
    return ToolResult(
        True, f"Suggested opening {name}", {"screen": "stock", "symbol": name}, proposals=[proposal]
    )


def suggest_second_opinion(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.index is None:
        return _no_data()
    found = resolve(ctx, str(args["symbol"]))
    if found is None:
        return failure("unknown stock", "That stock is not in the market data.")
    name = found[0]
    proposal = Proposal("second_opinion", f"Get independent second opinions on {name}", None, name)
    return ToolResult(
        True, f"Suggested a second opinion on {name}", {"symbol": name}, proposals=[proposal]
    )


_SCREEN_KEYS = "stock, " + ", ".join(SCREENS)
_TEXT = {
    "find_stock": ToolText(
        "Find a stock",
        "Looks up a stock by its name or symbol.",
        "Find stocks by name or symbol.",
    ),
    "stock_facts": ToolText(
        "Price facts",
        "Shows how a stock has moved over the last month, six months and year.",
        "Price statistics for one stock from local end-of-day data, with their age. "
        + PERCENT_NOTE,
    ),
    "suggest_screen": ToolText(
        "Suggest a screen to open",
        "Offers a button that takes you to the right screen in QuantOS.",
        f"Propose a screen for the person to open. screen is one of: {_SCREEN_KEYS}.",
    ),
    "suggest_second_opinion": ToolText(
        "Offer second opinions",
        "Offers a button that asks several AI models for their own independent readings of a stock.",
        "Propose running independent multi-model second opinions on a stock. "
        "The person decides; it uses their AI keys.",
    ),
}
_SCREEN_ARGS = (
    Param("screen", "str", "screen key"),
    Param("symbol", "str", "needed when screen is stock", required=False),
)


def market_specs(ctx: ToolContext) -> list[ToolSpec]:
    return [
        bound(
            ctx,
            "find_stock",
            _TEXT["find_stock"],
            (Param("query", "str", "name or symbol"),),
            find_stock,
        ),
        bound(ctx, "stock_facts", _TEXT["stock_facts"], (SYMBOL,), stock_facts),
        bound(ctx, "suggest_screen", _TEXT["suggest_screen"], _SCREEN_ARGS, suggest_screen),
        bound(
            ctx,
            "suggest_second_opinion",
            _TEXT["suggest_second_opinion"],
            (SYMBOL,),
            suggest_second_opinion,
        ),
    ]
