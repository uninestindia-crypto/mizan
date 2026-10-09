"""A company's own results, read from its filings: figures, ratios and a scorecard of rules of thumb.

Read-only. Every figure carries the period it covers and the date the company filed it, and the answer says how old
the filings are. Rules of thumb are conventions and say so. Nothing here tells a person what to do with a stock.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quant_system.copilot.registry import (
    ToolContext,
    ToolResult,
    ToolSpec,
    ToolText,
    bound,
    failure,
)
from quant_system.copilot.tools_market import PERCENT_NOTE, SYMBOL, resolve

BAD_SYMBOL = "That is not a valid stock symbol. Use letters and numbers only, for example TCS."
# The figures worth putting in front of a model, in the order a person reads them.
BRIEF_KEYS = (
    "ttm_revenue",
    "ttm_net_profit",
    "ttm_eps",
    "net_margin",
    "operating_margin",
    "revenue_growth_ttm",
    "profit_growth_ttm",
    "profitable_quarters",
    "interest_cover",
    "debt_to_equity",
    "roe",
    "pe",
    "pb",
)
_TEXT = ToolText(
    "Company results from filings",
    "Shows a company's own reported results, ratios and plain rules of thumb, with the filing dates.",
    "Facts from one company's own quarterly results filings on NSE: sales, profit and earnings per share over the "
    "last four quarters, growth, margins, borrowings against the owners' money, return on equity, and price ratios "
    "from the platform's last close, plus a scorecard of rules of thumb. Each figure has the period it covers and "
    "the date it was filed; the answer also says how old the newest filing is and whether any are held at all. "
    "Quote the period and the filing date with every figure. Say that a rule of thumb is a convention. Never call "
    "a stock cheap, expensive, good or bad, never tell the person to buy or sell, and never promise a return. "
    + PERCENT_NOTE,
)


def _figure(metric: Mapping[str, Any]) -> dict[str, Any]:
    """One figure, brief. A percentage goes under a name ending in _pct so it is read as percent points."""
    name = "value_pct" if metric["unit"] == "percent" else "value"
    entry: dict[str, Any] = {
        "label": metric["label"],
        name: metric["value"],
        "as_of": metric["as_of"],
    }
    if metric["unit"] not in ("percent", "INR"):
        entry["unit"] = metric["unit"]
    if metric["approximate"]:
        entry["approximate"] = True
    return entry


def _unavailable(metric: Mapping[str, Any]) -> dict[str, Any]:
    return {"label": metric["label"], "not_available": metric["reason"]}


def _brief(view: Mapping[str, Any]) -> dict[str, Any]:
    """The company view cut down to what a model needs, with the proof of the filing it came from."""
    metrics = view["metrics"]
    latest = view["latest_quarter"]
    filing = (
        {
            "quarter_ended": latest["period_end"],
            "filed_on": latest["filed_on"],
            "link": latest["filing_url"],
            "fingerprint": latest["sha256"],
        }
        if latest
        else None
    )
    figures = {
        key: _figure(metrics[key]) if metrics[key]["available"] else _unavailable(metrics[key])
        for key in BRIEF_KEYS
    }
    facts = [
        {"status": f["status"], "sentence": f["sentence"], "rule": f["rule_of_thumb"]}
        for f in view["scorecard"]["facts"]
    ]
    return {
        "symbol": view["symbol"],
        "company_name": view["company_name"],
        "data_status": view["data_status"],
        "data_notice": view["data_notice"],
        "basis": view["basis"]["label"],
        "latest_filing": filing,
        "price": view["price"],
        "figures": figures,
        "scorecard": {"header": view["scorecard"]["header"], "facts": facts},
        "reminder": view["statement"],
    }


def _view(ctx: ToolContext, symbol: str) -> dict[str, Any]:
    if ctx.fundamentals is not None:
        return ctx.fundamentals(symbol)
    # Imported here: the filings engine reads files and should not be loaded just to list the tools.
    from quant_system.fundamentals.runtime import default_runtime
    from quant_system.fundamentals.service import price_for
    from quant_system.fundamentals.views import company_view

    return company_view(default_runtime().service.analyse(symbol, price_for(ctx.index, symbol)))


def filing_fundamentals(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    text = str(args["symbol"]).strip()
    if not (1 <= len(text) <= 15 and all(c.isalnum() or c in "&-" for c in text)):
        return failure("not a valid symbol", BAD_SYMBOL)
    found = resolve(ctx, text)
    symbol = found[0] if found else text.upper()
    data = _brief(_view(ctx, symbol))
    status = str(data["data_status"]).replace("_", " ").lower()
    return ToolResult(True, f"{symbol}: results from filings ({status})", data)


def fundamentals_specs(ctx: ToolContext) -> list[ToolSpec]:
    return [bound(ctx, "filing_fundamentals", _TEXT, (SYMBOL,), filing_fundamentals)]


__all__ = ["BRIEF_KEYS", "fundamentals_specs"]
