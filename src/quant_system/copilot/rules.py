"""Answers that need no AI: the common questions, built straight from the read-only tools.

The Copilot is useful before anyone adds an AI key (goal G4: it runs with no credentials). A question that matches
a known kind is answered from the tool that owns the facts and says where they come from and how old they are.
Anything else gets the menu of what it can do, never an invented answer.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from quant_system.copilot.agent import AgentResult, Step
from quant_system.copilot.registry import Proposal, ToolRegistry, ToolResult, failure

__all__ = ["AnswerContext", "answer_without_ai", "render_halal"]

_STOP = frozenset(
    "A AN AND ARE AS AT BE BUY BY CAN CHECK DO DOES DOING FACTS FOR GET HALAL HARAM HI HELLO HELP HOW IF IS IT ITS "
    "ME MY NEWS OF ON OR PRICE QUOTE SELL SHARE SHARIAH STOCK THE THIS TO VERIFY WHAT WHERE WHICH WHO WITH SECOND "
    "OPINION LIVE COMPLIANT PLEASE TELL SHOW ABOUT ANY NOW TODAY".split()
)
_STATUS = {
    "COMPLIANT": "Compliant",
    "NON_COMPLIANT": "Not compliant",
    "QUESTIONABLE": "Questionable (close to a limit)",
}
_NEED_AI = (
    "To ask open-ended questions or get independent second opinions, add an AI key: "
    "open Settings, then Accounts and keys."
)
_ADD_KEY_BUTTON = Proposal("navigate", "Add an AI key", "/settings/accounts")
_NOT_ALLOWED = "This assistant is not set up to look that up. Open Agents, edit it, and tick that item in its list."
_MENU = """I can answer from what is inside QuantOS:
- **Halal screening** for a stock ("is TCS halal?"), with every ratio and where the data comes from
- **Price facts** ("how is INFY doing?")
- **News headlines** ("news on RELIANCE")
- **Live prices** ("price of TCS")
- **Trading costs** and **position size** (the Tools screen)
- **Your portfolio, watchlist and paper books**
- **Independent second opinions** from several AI models on a stock

I cannot predict the market or tell you what to buy or sell."""


@dataclass(frozen=True, slots=True)
class AnswerContext:
    """What the answer may depend on: the screen, whether an AI key exists, which tools may be used, the hint."""

    page: str | None = None
    ai_available: bool = False
    allowed: frozenset[str] | None = None  # None means every tool; an agent's own list narrows it
    hint: bool = True  # add the "add an AI key" line; a workflow adds it once, not after every step
    symbol: str | None = (
        None  # a stock already chosen (a workflow run); it wins over words in the text
    )


@dataclass(slots=True)
class _Run:
    registry: ToolRegistry
    allowed: frozenset[str] | None = None
    symbol: str | None = None
    steps: list[Step] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)

    def call(self, tool: str, args: dict[str, Any]) -> ToolResult:
        if self.allowed is not None and tool not in self.allowed:
            result = failure(f"{tool}: not allowed", _NOT_ALLOWED)
        else:
            result = self.registry.call(tool, args)
        self.steps.append(Step(tool, self.registry.label(tool), result.summary, result.ok))
        self.offer(*result.proposals)
        return result

    def offer(self, *proposals: Proposal) -> None:
        self.proposals.extend(p for p in proposals if p not in self.proposals)


def _words(text: str) -> set[str]:
    return {w.upper() for w in re.findall(r"[A-Za-z][A-Za-z']*", text)}


def _known_symbol(run: _Run, token: str) -> bool:
    found = run.registry.call("find_stock", {"query": token})
    matches = found.data.get("matches", []) if found.ok else []
    if not any(m["symbol"] == token for m in matches):
        return False
    run.steps.append(Step("find_stock", run.registry.label("find_stock"), found.summary, True))
    return True


def _find_symbol(run: _Run, text: str, page: str | None) -> str | None:
    if run.symbol:
        return run.symbol
    tokens = [str(t).upper() for t in re.findall(r"[A-Za-z][A-Za-z0-9&-]{1,14}", text)]
    for token in tokens:
        if token not in _STOP and _known_symbol(run, token):
            return token
    on_screen = re.match(r"^/stock/([A-Za-z0-9&-]+)", page or "")
    return str(on_screen.group(1)).upper() if on_screen else None


# ------------------------------------------------------------------------------------- renderers


def render_halal(data: dict[str, Any]) -> str:
    if not data.get("covered"):
        return str(data["message"])
    lines = [f"**{data['symbol']} ({data.get('company')})**: halal screening"]
    if not data.get("sector_compliant", True):
        lines.append(f"- Business activity: not allowed ({data.get('sector_failure_reason')})")
    for standard in data["standards"]:
        lines.append(
            f"- **{standard['standard']}:** {_STATUS.get(standard['status'], standard['status'])}"
        )
        lines.extend(
            f"  - {r['name']}: {r['actual_pct']:.1f}% (limit {r['threshold_pct']:.0f}%)"
            for r in standard["ratios"]
        )
    if data.get("standards_disagree"):
        lines.append(f"- The two standards disagree: {data.get('disagreement_reason')}")
    source = data["provenance"]
    lines.append(
        f"\nData: {source.get('reporting_period')}, filed {source.get('filing_date')}. This is an illustrative sample "
        "entered by hand: not audited and not live."
    )
    lines.append(
        "This is a screening aid, not a religious ruling (fatwa). Please ask a qualified scholar before you decide."
    )
    return "\n".join(lines)


def _render_facts(data: dict[str, Any]) -> str:
    def row(label: str, key: str) -> str:
        value = data.get(key)
        return f"- {label}: {value:+.1f}%" if value is not None else f"- {label}: not available"

    return "\n".join(
        [
            f"**{data['symbol']} ({data.get('name')})**",
            f"Last close ₹{data['last_close']:,.2f} on {data['last_session']}. This is end-of-day data and not live.",
            row("Over 1 month", "return_1m_pct"),
            row("Over 6 months", "return_6m_pct"),
            row("Over 1 year", "return_1y_pct"),
            f"- Yearly ups and downs (volatility): {data.get('volatility_1y_pct')}%",
            f"- Worst fall in the last year: {data.get('max_drawdown_1y_pct')}%",
        ]
    )


def _headline_line(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").replace("[", "(").replace("]", ")")
    link = item.get("link")
    text = f"[{title}]({link})" if isinstance(link, str) and link.startswith("https://") else title
    tone = str(item.get("tone") or "").lower()
    return f"- {text} ({item.get('source') or 'unknown source'}{', ' + tone if tone else ''})"


def _render_headlines(data: dict[str, Any]) -> str:
    items = data.get("headlines") or []
    if not items:
        return "I found no recent headlines."
    counts = data.get("tone_counts") or {}
    tone = ", ".join(f"{n} {name.lower()}" for name, n in counts.items())
    lines = [_headline_line(h) for h in items[:8]]
    note = f"\nRough tone by keyword count, not a reading of the stories: {tone}." if tone else ""
    return (
        "Recent headlines (unverified text from a public news feed, not facts):\n"
        + "\n".join(lines)
        + note
    )


def _render_quotes(data: dict[str, Any]) -> str:
    lines = []
    for symbol, quote in data.get("quotes", {}).items():
        price = quote.get("last_price")
        note = quote.get("message") or str(quote.get("label", "")).replace("_", " ").lower()
        lines.append(
            f"- **{symbol}**: ₹{price} ({note})"
            if price is not None
            else f"- **{symbol}**: {note or 'no price'}"
        )
    return "\n".join(lines) or "No prices came back."


def _rupees(value: Any) -> str:
    return f"₹{float(value):,.0f}" if isinstance(value, (int, float)) else "not available"


def _render_portfolio(data: dict[str, Any]) -> str:
    totals = data.get("totals")
    if not isinstance(totals, dict):
        return str(
            data.get("note") or "You have not added any holdings yet. Open Portfolio to add them."
        )
    change = totals.get("pnl_pct")
    percent = f" ({float(change) * 100:+.1f}%)" if isinstance(change, (int, float)) else ""
    lines = [
        "**Your portfolio**",
        f"- Value: {_rupees(totals.get('value'))} (you paid {_rupees(totals.get('cost'))})",
        f"- Profit or loss so far: {_rupees(totals.get('pnl'))}{percent}",
    ]
    lines.extend(f"- {warning}" for warning in data.get("warnings") or [])
    lines.append(str(data.get("note") or ""))
    return "\n".join(line for line in lines if line)


# ------------------------------------------------------------------------------------- questions


def _stock_question(
    run: _Run, text: str, page: str | None, tool: str, render: Callable[[dict[str, Any]], str]
) -> str:
    symbol = _find_symbol(run, text, page)
    if symbol is None:
        return "Which stock do you mean? Tell me its name or symbol, for example TCS."
    key = "symbols" if tool == "live_quote" else "symbol"
    result = run.call(tool, {key: [symbol] if tool == "live_quote" else symbol})
    return render(result.data) if result.ok else str(result.error)


def _second_opinion(run: _Run, text: str, page: str | None, ai_available: bool) -> str:
    symbol = _find_symbol(run, text, page)
    if symbol is None:
        return "Which stock should the AI models look at? Tell me its name or symbol."
    run.call("suggest_second_opinion", {"symbol": symbol})
    if ai_available:
        return (
            f"I can ask several AI models to look at {symbol} independently. Use the button below."
        )
    run.offer(_ADD_KEY_BUTTON)
    return f"Independent second opinions on {symbol} ask several AI models, so they need AI keys. {_NEED_AI}"


def _portfolio(run: _Run, kind: str) -> str:
    result = run.call(kind, {})
    if not result.ok:
        return str(result.error)
    if kind == "watchlist":
        return "Your watchlist: " + (", ".join(result.data["symbols"]) or "it is empty.")
    if kind == "paper_books":
        names = [str(b.get("name", "Paper book")) for b in result.data["books"]]
        return (
            "Your paper books: "
            + (", ".join(names) or "none yet.")
            + "\n"
            + str(result.data["note"])
        )
    return _render_portfolio(result.data)


def _costs(run: _Run) -> str:
    run.call("suggest_screen", {"screen": "tools"})
    return "The Costs tool shows the exact NSE charges for a trade, including brokerage and taxes. Open it below."


def _route(run: _Run, text: str, page: str | None, ai_available: bool) -> str:
    words = _words(text)
    if words & {"HALAL", "HARAM", "SHARIAH", "COMPLIANT"}:
        return _stock_question(run, text, page, "shariah_check", render_halal)
    if words & {"SECOND", "OPINION", "VERIFY", "CONFIRM", "RECHECK"}:
        return _second_opinion(run, text, page, ai_available)
    if words & {"NEWS", "HEADLINES", "SENTIMENT"}:
        return _stock_question(run, text, page, "news_headlines", _render_headlines)
    if words & {"PRICE", "QUOTE", "LIVE"}:
        return _stock_question(run, text, page, "live_quote", _render_quotes)
    if words & {"BROKERAGE", "CHARGES", "COSTS", "COST", "FEES", "TAX", "TAXES"}:
        return _costs(run)
    for kind, trigger in (
        ("portfolio_summary", {"PORTFOLIO", "HOLDINGS"}),
        ("watchlist", {"WATCHLIST"}),
        ("paper_books", {"PAPER"}),
    ):
        if words & trigger:
            return _portfolio(run, kind)
    if words & {"FACTS", "STATS", "DOING", "ABOUT", "SUMMARY"} or _find_symbol(run, text, None):
        return _stock_question(run, text, page, "stock_facts", _render_facts)
    return _MENU


def answer_without_ai(
    text: str, registry: ToolRegistry, context: AnswerContext | None = None
) -> AgentResult:
    context = context or AnswerContext()
    run = _Run(registry, context.allowed, context.symbol)
    reply = _route(run, text, context.page, context.ai_available)
    if context.hint and not context.ai_available and "add an AI key" not in reply:
        reply = f"{reply}\n\n{_NEED_AI}"
        run.offer(_ADD_KEY_BUTTON)
    return AgentResult(reply, run.steps, run.proposals, model=None)
