"""The halal screener's result, written out for a person, when it comes from a company's own filing.

The older sample-based result is written by `rules.render_halal`; this writes the same block for a result that
rests on the company's results filing (or on its business alone), in the same plain layout.
"""

from __future__ import annotations

from typing import Any

from quant_system.copilot.screening_proof import VERDICT_WORDS

__all__ = ["FILING_SOURCES", "STATUS_WORDS", "render_proof_block", "verdict_of"]

FILING_SOURCES = ("filing", "business")
STATUS_WORDS = {
    "COMPLIANT": "Compliant",
    "NON_COMPLIANT": "Not compliant",
    "QUESTIONABLE": "Questionable (close to a limit)",
    "NOT_COMPUTED": "Not worked out (it needs the stock's price history)",
}
_DISCLAIMER = (
    "This is a screening aid, not a religious ruling (fatwa). "
    "Please ask a qualified scholar before you decide."
)
_GENERIC_GAPS = ("scholar", "fatwa")
_MAX_GAPS = 4


def verdict_of(data: dict[str, Any]) -> str:
    """One plain word for a result that carries the Shariah engine's verdict."""
    return VERDICT_WORDS.get(str(data.get("verdict")), "not screened")


def _ratio_line(ratio: dict[str, Any]) -> str:
    low, high, limit = ratio["lower_pct"], ratio["actual_pct"], ratio["threshold_pct"]
    figure = f"{high:.1f}%" if abs(high - low) < 0.05 else f"between {low:.1f}% and {high:.1f}%"
    return f"- {ratio['name']}: {figure} (limit {limit:.0f}%)"


def _standard_block(standard: dict[str, Any]) -> str:
    status = STATUS_WORDS.get(standard["status"], standard["status"])
    return "\n".join(
        [f"**{standard['standard']}: {status}**", *(_ratio_line(r) for r in standard["ratios"])]
    )


def _source_block(data: dict[str, Any]) -> str:
    notice = str(data.get("data_notice") or "")
    line = data.get("source_line")
    filing = data.get("filing") or {}
    link = (
        f" Open the filing to check it: {filing['source_url']}" if filing.get("source_url") else ""
    )
    return f"{line}. {notice}{link}".strip() if line else notice


def _gaps(data: dict[str, Any]) -> str | None:
    gaps = [
        g for g in data.get("not_covered") or [] if not any(w in g.lower() for w in _GENERIC_GAPS)
    ]
    if not gaps:
        return None
    return "\n".join(["What this does not cover:", *(f"- {gap}" for gap in gaps[:_MAX_GAPS])])


def render_proof_block(data: dict[str, Any]) -> str:
    """The result as short paragraphs and flat lists, starting with the verdict and why."""
    word = verdict_of(data).capitalize()
    blocks = [
        f"**From QuantOS's halal screener: {data['symbol']} ({data.get('company')})**",
        f"**Result: {word}.** {data.get('headline')}",
    ]
    if not data.get("sector_compliant", True):
        blocks.append(f"**Business activity:** not allowed ({data.get('sector_failure_reason')})")
    blocks.extend(_standard_block(s) for s in data["standards"])
    if data.get("standards_disagree"):
        blocks.append(f"The two standards disagree: {data.get('disagreement_reason')}")
    blocks.append(_source_block(data))
    blocks.extend(block for block in (_gaps(data), _DISCLAIMER) if block)
    return "\n\n".join(blocks)
