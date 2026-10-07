"""The facts a second opinion is built from: one read-only look at a stock, gathered once and shown to every model.

Every model on the panel reads the *same* facts, so any difference between them is a difference in judgement and not
in what each was shown. Outside text (news) stays fenced as untrusted data. The halal section is carried verbatim from
the deterministic screener so the screen can show it; no model gets to rule on it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from quant_system.copilot.guard import fence
from quant_system.copilot.registry import ToolRegistry, ToolResult

__all__ = ["FactPack", "FactSection", "build_fact_pack"]

SECTION_CHARS = 3500


@dataclass(frozen=True, slots=True)
class FactSection:
    tool: str
    title: str
    text: str  # what the models are shown: JSON, fenced when it came from outside the app
    summary: str  # plain words for the person: what this section is
    untrusted: bool


@dataclass(frozen=True, slots=True)
class FactPack:
    symbol: str
    sections: tuple[FactSection, ...]
    unavailable: tuple[str, ...]  # titles of facts that could not be fetched, in plain words
    halal: dict[str, Any] | None  # the screener's own answer, untouched

    @property
    def usable(self) -> bool:
        """Without price history there is nothing meaningful to ask a model about."""
        return any(section.tool == "stock_facts" for section in self.sections)

    @property
    def reorderable(self) -> bool:
        """False when showing the facts the other way round changes nothing, so a recheck would not be a reorder."""
        return self.render() != self.render(reverse=True)

    def render(self, *, reverse: bool = False) -> str:
        """The facts as text. ``reverse`` shows the sections in the opposite order, for the stability recheck."""
        ordered = list(reversed(self.sections)) if reverse else list(self.sections)
        blocks = [f"## {section.title}\n{section.text}" for section in ordered]
        if self.unavailable:
            blocks.append("## Not available right now\n" + ", ".join(self.unavailable))
        return "\n\n".join(blocks)

    def as_dict(self) -> dict[str, Any]:
        """What the screen shows under 'What the models were shown'."""
        return {
            "symbol": self.symbol,
            "sections": [
                {"title": s.title, "summary": s.summary, "from_outside": s.untrusted}
                for s in self.sections
            ],
            "unavailable": list(self.unavailable),
        }


def _always(_data: dict[str, Any]) -> bool:
    return True


def _has_price(data: dict[str, Any]) -> bool:
    """A live quote lookup can succeed and still carry no price (no broker key, or a share it could not price)."""
    quotes = data.get("quotes")
    entries = quotes.values() if isinstance(quotes, dict) else ()
    return any(
        isinstance(entry, dict)
        and entry.get("last_price") is not None
        and entry.get("label") != "UNAVAILABLE"
        for entry in entries
    )


def _has_headlines(data: dict[str, Any]) -> bool:
    return bool(data.get("headlines"))


@dataclass(frozen=True, slots=True)
class _Source:
    tool: str
    title: str
    summary: str
    args: Callable[[str], dict[str, Any]]
    # False when the tool answered but gave the models nothing to read; the source then counts as unavailable.
    has_content: Callable[[dict[str, Any]], bool] = _always


_SOURCES = (
    _Source(
        "stock_facts",
        "Price history facts",
        "Returns, volatility and worst fall from end-of-day prices",
        lambda s: {"symbol": s},
    ),
    _Source(
        "fundamentals",
        "Fundamentals",
        "Valuation and balance-sheet figures (a hand-entered sample)",
        lambda s: {"symbol": s},
    ),
    _Source(
        "shariah_check",
        "Halal screening result",
        "The platform's screener, both standards, with its data status",
        lambda s: {"symbol": s},
    ),
    _Source(
        "news_headlines",
        "Recent headlines",
        "Public news headlines: unverified text from outside the app",
        lambda s: {"symbol": s},
        _has_headlines,
    ),
    _Source(
        "live_quote",
        "Live price",
        "The latest price from your broker connection, with its freshness",
        lambda s: {"symbols": [s]},
        _has_price,
    ),
)


def _section(source: _Source, result: ToolResult) -> FactSection:
    """Outside text arrives already fenced by ``for_prompt``. The rest still carries names and notes that came from
    data files, so it is made unable to forge a fence tag too: every angle bracket in it is written as an escape."""
    text = result.for_prompt(SECTION_CHARS)
    return FactSection(
        source.tool,
        source.title,
        text if result.untrusted else fence(text),
        source.summary,
        result.untrusted,
    )


def build_fact_pack(registry: ToolRegistry, symbol: str) -> FactPack:
    """Gather every fact the panel can use. A source that fails, or answers with nothing in it, is named, never
    papered over: the screen lists as 'shown to the models' only what they were really given."""
    symbol = symbol.strip().upper()
    sections: list[FactSection] = []
    unavailable: list[str] = []
    halal: dict[str, Any] | None = None
    for source in _SOURCES:
        result = registry.call(source.tool, source.args(symbol))
        if not result.ok or not source.has_content(result.data):
            unavailable.append(source.title)
            continue
        sections.append(_section(source, result))
        if source.tool == "shariah_check":
            halal = result.data
    return FactPack(symbol, tuple(sections), tuple(unavailable), halal)
