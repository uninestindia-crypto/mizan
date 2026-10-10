"""The one-line reason and the status row a badge needs, worked out from the finished proof and nothing else.

Because it only reads the proof, a badge can never disagree with the proof it links to.
"""

from __future__ import annotations

from typing import Any

__all__ = ["MAX_SHORT_CHARS", "short_reason", "status_row"]

MAX_SHORT_CHARS = 89
_SUBJECT = {
    "debt": "Debt is",
    "cash": "Cash and securities are",
    "receivables": "Receivables are",
    "impermissible": "Interest and similar income is",
}
_AGAINST = {"AAOIFI": "market value", "TASIS": "total assets"}
_BUSINESS = {
    "interest_based_finance": "interest-based finance",
    "alcohol": "alcohol",
    "tobacco": "tobacco",
    "gambling": "gambling",
    "cinema": "cinema",
}
_COMPLIANT = "Passes the business test and both standards."
_NOT_SCREENED = "Not screened yet."


def _fit(text: str) -> str:
    """The text cut at a word so that it is under 90 characters, with an ellipsis when something was cut."""
    if len(text) <= MAX_SHORT_CHARS:
        return text
    cut = text[: MAX_SHORT_CHARS - 1].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return f"{cut}…"


def _sentence(standard: str, test: dict[str, Any]) -> str:
    limit = f"{test['limit_pct']:g}%"
    if test["key"] == "impermissible":
        return f"{_SUBJECT['impermissible']} over the {limit} limit."
    return f"{_SUBJECT[test['key']]} over the {limit} limit against {_AGAINST[standard]}."


def _failing_test(proof: dict[str, Any]) -> str | None:
    failing = [
        (s["standard"], t) for s in proof["standards"] for t in s["tests"] if t["result"] == "FAIL"
    ]
    return _sentence(*failing[0]) if failing else None


def _not_compliant(proof: dict[str, Any]) -> str:
    sector = proof.get("sector") or {}
    if sector.get("status") == "FAIL":
        rule = str(sector.get("rule") or "")
        return f"Its business is ruled out: {_BUSINESS.get(rule, 'a prohibited line of business')}."
    return _failing_test(proof) or "It fails one of the screening tests."


def _questionable(proof: dict[str, Any]) -> str:
    standards = proof["standards"]
    results = {test["result"] for s in standards for test in s["tests"]}
    if (proof.get("sector") or {}).get("status") == "NOT_CONFIRMED":
        return "Its business could not be confirmed from the data QuantOS holds."
    if any(s["status"] == "NOT_COMPUTED" for s in standards):
        return "Needs price history to finish the market-value tests."
    if proof["divergence"]["noted"]:
        return "The two standards disagree on this company."
    if "DEPENDS" in results:
        return "The filing does not say which side of a limit it is on."
    return "Close to a limit on at least one test."


def short_reason(proof: dict[str, Any]) -> str:
    """A plain reason for the verdict, under 90 characters."""
    verdict = proof["verdict"]
    if verdict == "COMPLIANT":
        return _COMPLIANT
    if verdict == "NON_COMPLIANT":
        return _fit(_not_compliant(proof))
    if verdict == "QUESTIONABLE":
        return _fit(_questionable(proof))
    return _NOT_SCREENED


def status_row(proof: dict[str, Any]) -> dict[str, Any]:
    """What a badge shows: the verdict, how well backed it is, the reason, and the date of the figures."""
    filing = proof.get("filing") or {}
    return {
        "verdict": proof["verdict"],
        "data_status": proof["data_status"],
        "short": short_reason(proof),
        "as_of": filing.get("period_end"),
    }
