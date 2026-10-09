"""Preferring a company's own filing over the hand-entered sample in the older screener screens.

The older screens (the list, search, a stock's detail, its screening and its audit trail) were built on the sample
rows. Where a filing exists, they now show the filing's result, and they always say where their verdict came from
(`verdict_source`), how well backed it is (`data_status`) and the date of the figures (`as_of`). Old fields stay. A
ratio that is a range in the proof (the filing does not break a figure down) is shown at its upper reading, the
cautious one; the status always comes from the proof, which also says when the two readings fall either side of a limit.
"""

from __future__ import annotations

from typing import Any

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from quant_system.shariah.schemas.company import ComplianceStatus, DataStatus, ScreeningStandard
from quant_system.shariah.schemas.screening import (
    AuditEvidenceLine,
    RatioMeter,
    SectorRuleResult,
    StandardEvaluation,
)
from quant_system.shariah.services.proof_runtime import filing_proof
from quant_system.shariah.services.proof_words import NUMERATOR

__all__ = [
    "evaluations_from",
    "evidence_lines",
    "prefer_filing",
    "proofs_for",
    "transparency_overrides",
]

_RATIO_NAMES = {"debt": "debt", "cash": "cash", "receivables": "rec", "impermissible": "imp"}
_AGAINST = {"AAOIFI": "36-Month Average Market Value", "TASIS": "Book Value of Total Assets"}
_INCOME = "Total Income (Operations + Other)"
_NEEDS_PRICES = "Needs price history"
_DERIVED_SCHEDULE = "Worked out by QuantOS from its own daily prices and the filed share count"


async def proofs_for(symbols: list[str]) -> dict[str, dict[str, Any] | None]:
    """The filing proof of each stock that has one, looked up off the request's event loop."""

    def look() -> dict[str, dict[str, Any] | None]:
        return {symbol: filing_proof(symbol) for symbol in symbols}

    return await run_in_threadpool(look)


def _standard(proof: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in proof["standards"] if s["standard"] == name)


def _sector_fails(proof: dict[str, Any]) -> bool:
    return bool((proof.get("sector") or {}).get("status") == "FAIL")


def standard_status(proof: dict[str, Any], name: str) -> ComplianceStatus:
    """One standard's status in the older three-value form.

    A business that fails fails both standards; a standard that could not be worked out is questionable.
    """
    if _sector_fails(proof):
        return ComplianceStatus.NON_COMPLIANT
    status = _standard(proof, name)["status"]
    return ComplianceStatus(status) if status != "NOT_COMPUTED" else ComplianceStatus.QUESTIONABLE


def _ratio(proof: dict[str, Any], name: str, key: str) -> float | None:
    test = next(t for t in _standard(proof, name)["tests"] if t["key"] == key)
    return None if test["high"] is None else round(test["high"]["pct"] / 100.0, 6)


def _period_end(proof: dict[str, Any]) -> str | None:
    return (proof.get("filing") or {}).get("period_end")


def filing_fields(proof: dict[str, Any]) -> dict[str, Any]:
    """The fields a row of the older screens takes from a filing's proof."""
    fields: dict[str, Any] = {
        "aaoifi_status": standard_status(proof, "AAOIFI"),
        "tasis_status": standard_status(proof, "TASIS"),
        "data_status": DataStatus(proof["data_status"]),
        "verdict_source": "filing",
        "as_of": _period_end(proof),
    }
    for name in ("AAOIFI", "TASIS"):
        for key, short in _RATIO_NAMES.items():
            fields[f"{name.lower()}_{short}_ratio"] = _ratio(proof, name, key)
    sector = proof.get("sector") or {}
    if sector.get("status") in ("PASS", "FAIL"):
        fields["sector_compliant"] = sector["status"] == "PASS"
        fields["sector_failure_reason"] = sector.get("reason")
    return fields


def prefer_filing[M: BaseModel](model: M, proof: dict[str, Any] | None) -> M:
    """The row with the filing's result in place of the sample's. Unchanged (but for its source) when there is none."""
    if proof is None:
        return model
    wanted = filing_fields(proof)
    return model.model_copy(
        update={k: v for k, v in wanted.items() if k in type(model).model_fields}
    )


# ------------------------------------------------------------------------------------- evaluations


def _numerator_tags(test: dict[str, Any]) -> str | None:
    tags = [i["xbrl_tag"] for i in test["inputs"] if i["role"] == "numerator" and i["xbrl_tag"]]
    return ", ".join(dict.fromkeys(tags)) or None


def _meter(standard: str, test: dict[str, Any]) -> RatioMeter:
    key, limit = test["key"], float(test["limit_pct"])
    if test["result"] == "NOT_COMPUTED":
        return RatioMeter(
            metric_name=test["title"],
            actual_value=0.0,
            actual_pct=0.0,
            threshold_pct=limit,
            is_compliant=False,
            numerator_label=_NEEDS_PRICES,
            numerator_value_inr_cr=0.0,
            denominator_label=_NEEDS_PRICES,
            denominator_value_inr_cr=0.0,
            note_reference=test["plain"],
        )
    high = test["high"]
    return RatioMeter(
        metric_name=test["title"],
        actual_value=round(high["pct"] / 100.0, 6),
        actual_pct=round(high["pct"], 4),
        threshold_pct=limit,
        is_compliant=test["result"] in ("PASS", "BORDERLINE"),
        is_warning=test["result"] == "BORDERLINE",
        numerator_label=NUMERATOR[key],
        numerator_value_inr_cr=round(high["numerator_cr"], 2),
        denominator_label=_INCOME if key == "impermissible" else _AGAINST[standard],
        denominator_value_inr_cr=round(high["denominator_cr"], 2),
        note_reference=_numerator_tags(test),
    )


def _summary(proof: dict[str, Any], name: str) -> str:
    if _sector_fails(proof):
        return f"Disqualified: Sector failure ({proof['sector'].get('reason')})"
    return str(_standard(proof, name)["summary"])


def _evaluation(proof: dict[str, Any], name: str) -> StandardEvaluation:
    meters = {t["key"]: _meter(name, t) for t in _standard(proof, name)["tests"]}
    status = standard_status(proof, name)
    return StandardEvaluation(
        standard=ScreeningStandard(name),
        status=status,
        is_compliant=status == ComplianceStatus.COMPLIANT,
        debt_ratio=meters["debt"],
        cash_ratio=meters["cash"],
        receivables_ratio=meters["receivables"],
        impermissible_income_ratio=meters["impermissible"],
        summary=_summary(proof, name),
    )


def evaluations_from(
    proof: dict[str, Any],
) -> tuple[StandardEvaluation, StandardEvaluation, bool, str | None]:
    """Both standards, whether they disagree and why, built from a filing's proof (cautious upper readings)."""
    divergence = proof["divergence"]
    return (
        _evaluation(proof, "AAOIFI"),
        _evaluation(proof, "TASIS"),
        bool(divergence["noted"]),
        divergence["explanation"],
    )


def transparency_overrides(proof: dict[str, Any]) -> dict[str, Any]:
    """What a screening says about itself, taken from the filing's proof instead of the sample's defaults."""
    sector = proof.get("sector") or {}
    return {
        "data_status": DataStatus(proof["data_status"]),
        "data_notice": proof["data_notice"],
        "methodology_version": proof["methodology_version"],
        "screened_at": proof["screened_at"],
        "sector_rule": SectorRuleResult(
            compliant=sector.get("status") != "FAIL",
            rule=sector.get("rule"),
            matched_keyword=sector.get("matched_keyword"),
            reason=sector.get("reason"),
        ),
        "not_covered": list(proof["not_covered"]),
        "verdict_source": "filing",
        "as_of": _period_end(proof),
    }


# ------------------------------------------------------------------------------------- audit trail


def _line(item: dict[str, Any], proof: dict[str, Any]) -> AuditEvidenceLine:
    label = (proof.get("filing") or {}).get("period_label")
    return AuditEvidenceLine(
        line_item=item["label"],
        value_inr_cr=float(item["value_cr"]),
        note_ref=item["xbrl_tag"],
        filing_schedule=label if item["xbrl_tag"] else _DERIVED_SCHEDULE,
        verification_status=proof["data_status"],
    )


def evidence_lines(
    proof: dict[str, Any],
) -> tuple[list[AuditEvidenceLine], list[AuditEvidenceLine]]:
    """Every figure the result rests on: balance-sheet lines, then income lines, each with its filed field name."""
    balance: dict[str, AuditEvidenceLine] = {}
    income: dict[str, AuditEvidenceLine] = {}
    for standard in proof["standards"]:
        for test in standard["tests"]:
            bucket = income if test["key"] == "impermissible" else balance
            bucket.update({i["label"]: _line(i, proof) for i in test["inputs"]})
    return list(balance.values()), list(income.values())
