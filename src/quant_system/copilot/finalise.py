"""The last deterministic check on what a model wrote, before a person reads it.

A prompt asks a model to stay within the honesty rules; this is the control that does not depend on the model
listening. It removes trading advice, halal rulings the screener did not make and web addresses no lookup returned
(:func:`quant_system.copilot.guard.scrub_prose`), and it makes sure the halal screener's own result and its
not-a-fatwa notice are always on the page whenever the screener ran, whatever the model chose to say about it.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from typing import Any, Final

from quant_system.copilot.guard import scrub_prose

__all__ = ["add_halal_blocks", "finalise_reply", "links_in"]

_LINK_DEPTH: Final = 6
_NOTHING_LEFT = "I could not write an answer I am allowed to show. Try asking in a different way."
_BLOCK_FAILED = (
    "The halal screening details could not be shown just now. Please try again in a minute."
)


def _is_link(text: str) -> bool:
    return text.startswith(("https://", "http://")) and not any(ch.isspace() for ch in text)


def _children(data: Any) -> Iterable[Any]:
    if isinstance(data, Mapping):
        return data.values()
    return data if isinstance(data, (list, tuple, set, frozenset)) else ()


def links_in(data: Any, depth: int = 0) -> set[str]:
    """Every web address that is a value somewhere in a tool result: the only ones a reply may repeat."""
    if isinstance(data, str):
        return {data} if _is_link(data) else set()
    found: set[str] = set()
    for child in _children(data) if depth < _LINK_DEPTH else ():
        found |= links_in(child, depth + 1)
    return found


def add_halal_blocks(text: str, screened: Sequence[Mapping[str, Any]]) -> str:
    """The text followed by the screener's own block for every stock it screened in this run."""
    if not screened:
        return text
    # Imported here: the built-in answers import the agent, which imports this module.
    from quant_system.copilot.rules import render_halal

    return "\n\n".join([text, *(_block(render_halal, one) for one in screened)])


def _block(render: Any, data: Mapping[str, Any]) -> str:
    try:
        return str(render(dict(data)))
    except Exception:
        # A result the renderer cannot read is still never replaced by the model's words.
        return _BLOCK_FAILED


def finalise_reply(
    text: str, *, screened: Sequence[Mapping[str, Any]], links: Collection[str]
) -> str:
    """A model's final text, checked, with the screener's block after it when the screener ran.

    ``screened`` is every halal screener result from this run; a halal statement may stay only when one of them
    actually covered a stock. Text that needed nothing removed comes back exactly as the model wrote it.
    """
    covered = any(result.get("covered") for result in screened)
    checked = scrub_prose(text, halal_allowed=covered, allowed_links=links)
    shown = checked.text if checked.removed else text.strip()
    return add_halal_blocks(shown or _NOTHING_LEFT, screened)
