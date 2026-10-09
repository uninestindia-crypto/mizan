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
from quant_system.copilot.guard import is_advice
from quant_system.copilot.halal_text import FILING_SOURCES, render_proof_block, verdict_of
from quant_system.copilot.registry import Proposal, ToolRegistry, ToolResult, failure

__all__ = ["AnswerContext", "answer_without_ai", "render_halal", "verdict_word"]

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
    "To ask open-ended questions or get independent second opinions, set up an AI: open Settings, then AI assistants. "
    "You can use an AI app you are already signed in to, or add a key under Accounts and keys."
)
_ADD_KEY_BUTTON = Proposal("navigate", "Choose an AI", "/settings/ai")
_NOT_ALLOWED = "This assistant is not set up to look that up. Open Agents, edit it, and tick that item in its list."
_WHICH_STOCK = "Which stock do you mean? Write its symbol in capital letters, for example TCS."
_WHICH_FOR_OPINION = "Which stock should the AI models look at? Write its symbol in capital letters, for example TCS."
_NO_ADVICE = "I can't tell you whether to buy or sell."
_NO_ADVICE_WITH_FACTS = f"{_NO_ADVICE} Here are the facts to look at yourself:"
_MAX_SYMBOL_LOOKUPS = 12  # capital-letter words checked in one question
_MAX_WATCHLIST_LABELS = 30
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
    shariah_mode: bool = False  # every answer about a stock opens with the screener's verdict


@dataclass(slots=True)
class _Run:
    registry: ToolRegistry
    allowed: frozenset[str] | None = None
    symbol: str | None = None
    shariah_mode: bool = False
    steps: list[Step] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    looked_up: dict[str, bool] = field(default_factory=dict)  # word -> is it a stock symbol
    answered: bool = False  # a read-only lookup succeeded, so facts are being shown
    blocked: str | None = (
        None  # why no stock could be looked up at all (for example no market data yet)
    )

    def call(self, tool: str, args: dict[str, Any]) -> ToolResult:
        if self.allowed is not None and tool not in self.allowed:
            result = failure("Not allowed for this assistant.", _NOT_ALLOWED)
        else:
            result = self.registry.call(tool, args)
        self.steps.append(Step(tool, self.registry.label(tool), result.summary, result.ok))
        self.answered = self.answered or (result.ok and not tool.startswith("suggest_"))
        self.offer(*result.proposals)
        return result

    def offer(self, *proposals: Proposal) -> None:
        self.proposals.extend(p for p in proposals if p not in self.proposals)


def _words(text: str) -> set[str]:
    return {w.upper() for w in re.findall(r"[A-Za-z][A-Za-z']*", text)}


def _lookup_symbol(run: _Run, token: str) -> bool:
    found = run.registry.call("find_stock", {"query": token})
    if not found.ok:
        run.blocked = found.error
    matches = found.data.get("matches", []) if found.ok else []
    known = any(m["symbol"] == token for m in matches)
    if known:
        run.steps.append(Step("find_stock", run.registry.label("find_stock"), found.summary, True))
    return known


def _known_symbol(run: _Run, token: str) -> bool:
    """Whether the market data has a stock with exactly this symbol. Asked once per word, however often it recurs.

    This is the one lookup the built-in answers make on their own, to read a symbol out of the person's words, so it
    goes straight to the market data instead of through an assistant's list of allowed items.
    """
    if token not in run.looked_up:
        run.looked_up[token] = _lookup_symbol(run, token)
    return run.looked_up[token]


def _capital_words(text: str) -> list[str]:
    """Words written entirely in capitals, in order, once each. Only these can be a stock symbol.

    A word typed in lower case or as a Capitalised word is ordinary language ("idea", "Beta", "Total"), even when a
    listed company has that very symbol, so it is never looked up and never guessed at.
    """
    words = re.findall(r"[A-Za-z][A-Za-z0-9&-]{1,14}", text)
    return list(dict.fromkeys(w for w in words if w.isupper() and w not in _STOP))


def _named_symbols(run: _Run, text: str, page: str | None) -> list[str]:
    """The stocks the question is about: a workflow's stock, else those written in capitals, else the screen's."""
    if run.symbol:
        return [run.symbol]
    named = [w for w in _capital_words(text)[:_MAX_SYMBOL_LOOKUPS] if _known_symbol(run, w)]
    if named:
        return named
    on_screen = re.match(r"^/stock/([A-Za-z0-9&-]+)", page or "")
    return [str(on_screen.group(1)).upper()] if on_screen else []


def _which(run: _Run, named: list[str], none_named: str) -> str:
    """The plain question to ask when the words did not settle on exactly one stock.

    When no stock could be looked up at all (market data not connected), say that instead, because a symbol in
    capitals is not the problem and asking again would not help.
    """
    if not named:
        return run.blocked or none_named
    names = f"{', '.join(named[:-1])} or {named[-1]}" if len(named) > 1 else named[0]
    return f"Which stock do you mean: {names}?"


# ------------------------------------------------------------------------------------- renderers


def render_halal(data: dict[str, Any]) -> str:
    """The screener's own result as short paragraphs and flat lists, so it reads the same in every screen."""
    if not data.get("covered"):
        return str(data["message"])
    if data.get("verdict_source") in FILING_SOURCES:
        return render_proof_block(data)
    blocks = [f"**From QuantOS's halal screener: {data['symbol']} ({data.get('company')})**"]
    if not data.get("sector_compliant", True):
        blocks.append(f"**Business activity:** not allowed ({data.get('sector_failure_reason')})")
    for standard in data["standards"]:
        status = _STATUS.get(standard["status"], standard["status"])
        ratios = [
            f"- {r['name']}: {r['actual_pct']:.1f}% (limit {r['threshold_pct']:.0f}%)"
            for r in standard["ratios"]
        ]
        blocks.append("\n".join([f"**{standard['standard']}: {status}**", *ratios]))
    if data.get("standards_disagree"):
        blocks.append(f"The two standards disagree: {data.get('disagreement_reason')}")
    source = data["provenance"]
    blocks.append(
        f"Data: {source.get('reporting_period')}, filed {source.get('filing_date')}. This is an illustrative sample "
        "entered by hand: not audited and not live."
    )
    blocks.append(
        "This is a screening aid, not a religious ruling (fatwa). Please ask a qualified scholar before you decide."
    )
    return "\n\n".join(blocks)


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
    percent = f" ({float(change):+.1f}%)" if isinstance(change, (int, float)) else ""
    lines = [
        "**Your portfolio**",
        f"- Value: {_rupees(totals.get('value'))} (you paid {_rupees(totals.get('cost'))})",
        f"- Profit or loss so far: {_rupees(totals.get('pnl'))}{percent}",
    ]
    lines.extend(f"- {warning}" for warning in data.get("warnings") or [])
    lines.append(str(data.get("note") or ""))
    return "\n".join(line for line in lines if line)


# ------------------------------------------------------------------------------------- questions


def verdict_word(data: dict[str, Any]) -> str:
    """One plain word for a screener result: compliant, not compliant, questionable or not screened."""
    if not data.get("covered"):
        return "not screened"
    if data.get("verdict_source") in FILING_SOURCES:
        return verdict_of(data)
    statuses = {str(s["status"]) for s in data["standards"]}
    if not data.get("sector_compliant", True) or "NON_COMPLIANT" in statuses:
        return "not compliant"
    return "compliant" if statuses == {"COMPLIANT"} else "questionable"


def _screener_lead(run: _Run, symbol: str) -> str:
    """In Shariah mode, the screener's own block, to put before anything else said about a stock."""
    if not run.shariah_mode or (run.allowed is not None and "shariah_check" not in run.allowed):
        return ""
    result = run.call("shariah_check", {"symbol": symbol})
    return f"{render_halal(result.data) if result.ok else result.error}\n\n"


def _stock_question(
    run: _Run, text: str, page: str | None, tool: str, render: Callable[[dict[str, Any]], str]
) -> str:
    named = _named_symbols(run, text, page)
    if len(named) != 1:
        return _which(run, named, _WHICH_STOCK)
    symbol = named[0]
    lead = "" if tool == "shariah_check" else _screener_lead(run, symbol)
    key = "symbols" if tool == "live_quote" else "symbol"
    result = run.call(tool, {key: [symbol] if tool == "live_quote" else symbol})
    return lead + (render(result.data) if result.ok else str(result.error))


def _second_opinion(run: _Run, text: str, page: str | None, ai_available: bool) -> str:
    named = _named_symbols(run, text, page)
    if len(named) != 1:
        return _which(run, named, _WHICH_FOR_OPINION)
    symbol = named[0]
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
        symbols = list(result.data["symbols"])
        if run.shariah_mode and symbols and "shariah_check" in (run.allowed or {"shariah_check"}):
            return _labelled_watchlist(run, symbols)
        return "Your watchlist: " + (", ".join(symbols) or "it is empty.")
    if kind == "paper_books":
        names = [str(b.get("name", "Paper book")) for b in result.data["books"]]
        return (
            "Your paper books: "
            + (", ".join(names) or "none yet.")
            + "\n"
            + str(result.data["note"])
        )
    return _render_portfolio(result.data)


def _labelled_watchlist(run: _Run, symbols: list[str]) -> str:
    lines = []
    for symbol in symbols[:_MAX_WATCHLIST_LABELS]:
        screened = run.registry.call("shariah_check", {"symbol": symbol})
        lines.append(
            f"- {symbol}: {verdict_word(screened.data) if screened.ok else 'not screened'}"
        )
    run.steps.append(
        Step("shariah_check", run.registry.label("shariah_check"), f"{len(lines)} checked", True)
    )
    more = len(symbols) - len(lines)
    tail = [f"- and {more} more not checked here"] if more > 0 else []
    return "\n".join(["Your watchlist, with each stock's halal screening result:", *lines, *tail])


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
    if words & {"FACTS", "STATS", "DOING", "ABOUT", "SUMMARY"} or _named_symbols(run, text, None):
        return _stock_question(run, text, page, "stock_facts", _render_facts)
    return _MENU


def answer_without_ai(
    text: str, registry: ToolRegistry, context: AnswerContext | None = None
) -> AgentResult:
    context = context or AnswerContext()
    run = _Run(registry, context.allowed, context.symbol, context.shariah_mode)
    reply = _route(run, text, context.page, context.ai_available)
    # The menu already says it cannot tell anyone what to buy or sell; every other answer says so first.
    if reply != _MENU and is_advice(text):
        reply = f"{_NO_ADVICE_WITH_FACTS if run.answered else _NO_ADVICE}\n\n{reply}"
    if context.hint and not context.ai_available and "add an AI key" not in reply:
        reply = f"{reply}\n\n{_NEED_AI}"
        run.offer(_ADD_KEY_BUTTON)
    return AgentResult(reply, run.steps, run.proposals, model=None)
