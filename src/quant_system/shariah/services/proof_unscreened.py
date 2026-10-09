"""The proof for a stock QuantOS cannot screen from figures: a business that fails on its own, or no usable figures.

A company whose business fails the sector rule is not compliant whatever its balance sheet says, so it needs no
balance sheet to be told so. Banks and other lenders are the common case: they file in a layout QuantOS does not
read, and their business already fails. Every other stock without a usable filing and without a sample row is
simply "not screened yet": never guessed, never called compliant.
"""

from __future__ import annotations

from typing import Any

from quant_system.shariah.filings.models import FilingFigures
from quant_system.shariah.services.activity_check import ActivityResult, ActivityStatus
from quant_system.shariah.services.proof_words import data_notice, not_covered_for

__all__ = ["filing_note", "finish_unscreened"]

_CLOSING_GAPS = not_covered_for("UNVERIFIED_SAMPLE")
_BEFORE = _CLOSING_GAPS[0]
_AFTER = _CLOSING_GAPS[-1]
_RESTS_ON_NAME = (
    "This result rests on the company's name and its NSE industry group. QuantOS did not read this company's "
    "balance sheet, so none of the financial tests were run."
)
_BUSINESS_GAP = (
    "Business activity is judged from the company's name and its NSE industry group, not from a full "
    "description of what it sells."
)
_NO_TESTS_GAP = "The four financial tests were not run: no balance sheet was read for this company."
_NOTHING_GAP = "QuantOS holds no usable company filing or sample figures for this stock, so no financial test was run."


def filing_note(figures: FilingFigures | None) -> str | None:
    """What was found on NSE but could not be used, in a plain sentence. None when no filing is held."""
    if figures is None:
        return None
    found = f"QuantOS found this company's results on NSE ({figures.proof.period_label}) but could not use them."
    return f"{found} {figures.read_note}".strip() if figures.read_note else found


def _not_compliant(
    proof: dict[str, Any], name: str, activity: ActivityResult, note: str | None
) -> dict[str, Any]:
    return {
        **proof,
        "verdict": "NON_COMPLIANT",
        "headline": f"{name} is not Shariah-compliant. {activity.plain}",
        "data_notice": f"{_RESTS_ON_NAME} {note}" if note else _RESTS_ON_NAME,
        "not_covered": [_BEFORE, _NO_TESTS_GAP, _BUSINESS_GAP, _AFTER],
    }


def _not_screened(proof: dict[str, Any], name: str, note: str | None) -> dict[str, Any]:
    gaps = [_BEFORE, _NOTHING_GAP, _AFTER]
    if note is None:
        return {**proof, "data_notice": data_notice("NOT_SCREENED"), "not_covered": gaps}
    return {
        **proof,
        "headline": f"{name} is not screened yet. {note}",
        "data_notice": note,
        "not_covered": gaps,
    }


def finish_unscreened(
    proof: dict[str, Any], activity: ActivityResult, figures: FilingFigures | None, name: str
) -> dict[str, Any]:
    """Turn the builder's "not screened" proof into the right one for a stock with no usable figures."""
    note = filing_note(figures)
    shown = name or str(proof["symbol"])
    if activity.status is ActivityStatus.FAIL:
        return _not_compliant(proof, shown, activity, note)
    return _not_screened(proof, shown, note)
