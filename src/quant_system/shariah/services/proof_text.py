"""The sentences of a proof that need the whole picture: the headline, the disagreement, what would change it."""

from __future__ import annotations

from typing import Any

from quant_system.shariah.services.activity_check import ActivityStatus
from quant_system.shariah.services.proof_measures import Measures
from quant_system.shariah.services.proof_types import ProofInputs
from quant_system.shariah.services.proof_words import NUMERATOR, crore_text

__all__ = ["changes_that_matter", "divergence_of", "headline_for", "sample_comparison"]

_WHERE = {"AAOIFI": "its 36-month average market value", "TASIS": "its total assets"}
_WHAT_STANDARD = {"AAOIFI": "the market-value standard", "TASIS": "the total-assets standard"}
_MAX_CHANGES = 3
_MIN_DIFFERENCE_CR = 100.0
_MIN_DIFFERENCE_SHARE = 0.15


def _tests_by_key(standard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["key"]: t for t in standard["tests"]}


def _first(standards: list[dict[str, Any]], result: str) -> dict[str, Any] | None:
    found: list[dict[str, Any]] = [
        test for standard in standards for test in standard["tests"] if test["result"] == result
    ]
    return found[0] if found else None


_RANK = {"PASS": 0, "BORDERLINE": 1, "DEPENDS": 2, "FAIL": 3}
_STATUS_WORDS = {
    "COMPLIANT": "compliant",
    "NON_COMPLIANT": "not compliant",
    "QUESTIONABLE": "questionable",
}


def _parting_test(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any] | None:
    """The test on which the two standards are furthest apart, as the stricter standard saw it."""
    one, other = _tests_by_key(first), _tests_by_key(second)
    gaps = {k: abs(_RANK[one[k]["result"]] - _RANK[other[k]["result"]]) for k in one}
    key = max(gaps, key=lambda k: gaps[k])
    if gaps[key] == 0:
        return None
    return one[key] if _RANK[one[key]["result"]] > _RANK[other[key]["result"]] else other[key]


def divergence_of(standards: list[dict[str, Any]]) -> dict[str, Any]:
    """Whether the two standards reached different results, and the test where they part."""
    first, second = standards
    both = "NOT_COMPUTED" not in (first["status"], second["status"])
    if not both or first["status"] == second["status"]:
        return {"noted": False, "explanation": None}
    parting = _parting_test(first, second)
    detail = (
        f" The difference is in the {parting['title'].lower()} test: {parting['plain']}"
        if parting
        else ""
    )
    text = (
        f"The two standards disagree. {_WHAT_STANDARD['AAOIFI'].capitalize()} says "
        f"{_STATUS_WORDS[first['status']]}; {_WHAT_STANDARD['TASIS']} says {_STATUS_WORDS[second['status']]}. "
        f"The first measures against market value and the second against total assets.{detail}"
    )
    return {"noted": True, "explanation": text}


def _period(inputs: ProofInputs) -> str:
    if inputs.filing is None:
        return "the hand-entered sample figures"
    kind = "consolidated" if inputs.filing.consolidated else "standalone"
    return f"its {inputs.filing.period_label} filing ({kind})"


def _questionable(
    inputs: ProofInputs, standards: list[dict[str, Any]], divergence: dict[str, Any]
) -> str:
    name = inputs.company_name or inputs.symbol
    if inputs.activity.status is ActivityStatus.NOT_CONFIRMED:
        return (
            f"{name} is questionable: its business could not be confirmed. {inputs.activity.plain}"
        )
    if any(s["status"] == "NOT_COMPUTED" for s in standards):
        return (
            f"{name} is questionable: the market-value standard could not be worked out because QuantOS has no "
            "price history for it."
        )
    if divergence["noted"]:
        return f"{name} is questionable. {divergence['explanation']}"
    test = _first(standards, "DEPENDS") or _first(standards, "BORDERLINE")
    return f"{name} is questionable: {test['plain'] if test else 'it is close to a limit.'}"


def headline_for(
    inputs: ProofInputs, verdict: str, standards: list[dict[str, Any]], divergence: dict[str, Any]
) -> str:
    """One plain sentence on why the stock is, or is not, compliant."""
    name = inputs.company_name or inputs.symbol
    if inputs.activity.status is ActivityStatus.FAIL:
        return f"{name} is not Shariah-compliant. {inputs.activity.plain}"
    if verdict == "NON_COMPLIANT":
        failing = _first(standards, "FAIL")
        return f"{name} is not Shariah-compliant. {failing['plain'] if failing else ''}".strip()
    if verdict == "COMPLIANT":
        return f"{name} passes the business test and both standards, on {_period(inputs)}."
    return _questionable(inputs, standards, divergence)


# ------------------------------------------------------------------------------------- what would change it


def _need(test: dict[str, Any]) -> float:
    """Crore the figure sits above its limit at the upper reading (negative when it is below)."""
    high = test["high"]
    return float(high["numerator_cr"] - test["limit_pct"] / 100 * high["denominator_cr"])


def _where(standard: str, key: str) -> str:
    return "its total income" if key == "impermissible" else _WHERE[standard]


def _over(standard: str, test: dict[str, Any]) -> str:
    name, limit = NUMERATOR[test["key"]], f"{test['limit_pct']:g}%"
    return (
        f"{name} would need to fall by about {crore_text(_need(test))} to get under the {limit} limit against "
        f"{_where(standard, test['key'])}, with nothing else changing."
    )


def _room(standard: str, test: dict[str, Any]) -> str:
    name, limit = NUMERATOR[test["key"]], f"{test['limit_pct']:g}%"
    return (
        f"{name} could rise by about {crore_text(-_need(test))} before reaching the {limit} limit against "
        f"{_where(standard, test['key'])}."
    )


def _tests_of(standards: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return [(s["standard"], test) for s in standards for test in s["tests"]]


def _tightest_room(standards: list[dict[str, Any]]) -> str | None:
    """The sentence for the passing test with the least room, measured against its own denominator."""
    passing = [
        (standard, test)
        for standard, test in _tests_of(standards)
        if test["result"] in ("PASS", "BORDERLINE") and test["high"]["denominator_cr"] > 0
    ]
    if not passing:
        return None
    standard, test = min(
        passing, key=lambda pair: -_need(pair[1]) / float(pair[1]["high"]["denominator_cr"])
    )
    return _room(standard, test)


def changes_that_matter(standards: list[dict[str, Any]]) -> list[str]:
    """Up to three sentences: the figures that would have to move to pass, then the tightest one that passes."""
    failing = [
        _over(standard, test)
        for standard, test in _tests_of(standards)
        if test["result"] in ("FAIL", "DEPENDS")
    ]
    unique = list(dict.fromkeys(failing))[: _MAX_CHANGES - 1]
    room = _tightest_room(standards)
    return [*unique, room] if room else unique


# ------------------------------------------------------------------------------------- sample comparison

_COMPARED = (
    ("total_debt", "debt", "borrowings"),
    ("total_assets", "total assets", "assets"),
    ("total_receivables", "receivables", "receivables"),
)


def _filing_value(measures: Measures, column: str) -> float:
    if column == "total_assets":
        return float(measures.assets_cr)
    key = {"total_debt": "debt", "total_receivables": "receivables"}[column]
    return float(measures.numerators[key].high_cr)


def _differs(sample: float, filed: float) -> bool:
    gap = abs(sample - filed)
    return gap > _MIN_DIFFERENCE_CR and gap > _MIN_DIFFERENCE_SHARE * max(abs(sample), abs(filed))


def sample_comparison(inputs: ProofInputs, measures: Measures) -> dict[str, Any]:
    """Where the older hand-entered sample and the filing disagree by a lot, said plainly. Only with a filing."""
    if inputs.sample is None or inputs.filing is None:
        return {"differs": False, "note": None}
    rows = []
    for column, label, _ in _COMPARED:
        sample, filed = float(inputs.sample.get(column) or 0.0), _filing_value(measures, column)
        if _differs(sample, filed):
            rows.append((label, crore_text(sample), crore_text(filed)))
    if not rows:
        return {"differs": False, "note": None}
    old = " and ".join(f"{label} of {sample}" for label, sample, _ in rows)
    new = " and ".join(f"{filed}" for _, _, filed in rows)
    note = (
        f"The older hand-entered sample for this stock showed {old}. The filing shows {new}. "
        "The figures from the filing are used."
    )
    return {"differs": True, "note": note}
