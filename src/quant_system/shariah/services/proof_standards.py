"""One standard's four tests, each read at its lower and upper figure, with a sentence and every input."""

from __future__ import annotations

from typing import Any

from quant_system.shariah.core.config import settings
from quant_system.shariah.schemas.screening import RatioMeter, StandardEvaluation
from quant_system.shariah.services.proof_measures import Measures
from quant_system.shariah.services.proof_words import TITLES, describe_test

__all__ = ["KEYS", "build_standard", "classify"]

KEYS = ("debt", "cash", "receivables", "impermissible")
_METER = {
    "debt": "debt_ratio",
    "cash": "cash_ratio",
    "receivables": "receivables_ratio",
    "impermissible": "impermissible_income_ratio",
}
_LIMIT = {
    "debt": settings.MAX_DEBT_RATIO,
    "cash": settings.MAX_CASH_RATIO,
    "receivables": settings.MAX_RECEIVABLES_RATIO,
    "impermissible": settings.MAX_IMPERMISSIBLE_REVENUE_RATIO,
}
_WARN = {
    "debt": settings.WARN_DEBT_RATIO,
    "cash": settings.WARN_CASH_RATIO,
    "receivables": settings.WARN_RECEIVABLES_RATIO,
    "impermissible": settings.WARN_IMPERMISSIBLE_REVENUE_RATIO,
}
_NEEDS_PRICES = (
    "Needs price history: QuantOS does not hold enough daily prices for this stock to work out its 36-month "
    "average market value."
)


def classify(low: RatioMeter, high: RatioMeter) -> str:
    """PASS, BORDERLINE (inside the warning band), DEPENDS (the two readings fall either side) or FAIL."""
    if not low.is_compliant:
        return "FAIL"
    if not high.is_compliant:
        return "DEPENDS"
    return "BORDERLINE" if low.is_warning or high.is_warning else "PASS"


def _side(meter: RatioMeter) -> dict[str, float]:
    return {
        "pct": meter.actual_pct,
        "numerator_cr": meter.numerator_value_inr_cr,
        "denominator_cr": meter.denominator_value_inr_cr,
    }


def _denominator_lines(standard: str, key: str, measures: Measures) -> list[dict[str, Any]]:
    if key == "impermissible":
        parts = measures.revenue
    elif standard == "TASIS":
        parts = measures.assets
    else:
        parts = (measures.market_value,) if measures.market_value else ()
    return [part.as_dict("both") for part in parts]


def _computed(
    key: str, standard: str, pair: tuple[RatioMeter, RatioMeter], measures: Measures
) -> dict[str, Any]:
    low, high = pair
    test: dict[str, Any] = {
        "key": key,
        "title": TITLES[(standard, key)],
        "limit_pct": high.threshold_pct,
        "warning_pct": round(_WARN[key] * 100, 2),
        "result": classify(low, high),
        "low": _side(low),
        "high": _side(high),
        "inputs": [*measures.numerators[key].lines(), *_denominator_lines(standard, key, measures)],
    }
    test["plain"] = describe_test(test, standard)
    return test


def _not_computed(key: str, standard: str) -> dict[str, Any]:
    return {
        "key": key,
        "title": TITLES[(standard, key)],
        "limit_pct": round(_LIMIT[key] * 100, 2),
        "warning_pct": round(_WARN[key] * 100, 2),
        "result": "NOT_COMPUTED",
        "low": None,
        "high": None,
        "inputs": [],
        "plain": _NEEDS_PRICES,
    }


def _status(tests: list[dict[str, Any]]) -> str:
    results = {t["result"] for t in tests}
    if "FAIL" in results:
        return "NON_COMPLIANT"
    if "NOT_COMPUTED" in results:
        return "NOT_COMPUTED"
    return "QUESTIONABLE" if results & {"DEPENDS", "BORDERLINE"} else "COMPLIANT"


def _titles(tests: list[dict[str, Any]], result: str) -> list[str]:
    return [t["title"].lower() for t in tests if t["result"] == result]


def _summary(status: str, tests: list[dict[str, Any]]) -> str:
    named = {r: _titles(tests, r) for r in ("FAIL", "DEPENDS", "BORDERLINE")}
    if status == "COMPLIANT":
        return "Passes all four tests."
    if status == "NON_COMPLIANT":
        return "Fails: " + "; ".join(named["FAIL"]) + "."
    if status == "NOT_COMPUTED":
        return "Could not be worked out in full: it needs the stock's price history."
    close = [*named["DEPENDS"], *named["BORDERLINE"]]
    return "Undecided or close to a limit on: " + "; ".join(close) + "."


def build_standard(
    name: str,
    evaluations: tuple[StandardEvaluation, StandardEvaluation],
    measures: Measures,
    has_market_value: bool,
) -> dict[str, Any]:
    """The block for one standard, from the engine's evaluation at the lower and at the upper reading."""
    low_eval, high_eval = evaluations
    tests: list[dict[str, Any]] = []
    for key in KEYS:
        if name == "AAOIFI" and not has_market_value and key != "impermissible":
            tests.append(_not_computed(key, name))
            continue
        pair = (getattr(low_eval, _METER[key]), getattr(high_eval, _METER[key]))
        tests.append(_computed(key, name, pair, measures))
    status = _status(tests)
    return {"standard": name, "status": status, "summary": _summary(status, tests), "tests": tests}
