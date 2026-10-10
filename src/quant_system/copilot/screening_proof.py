"""A stock's Shariah proof, shaped as the halal screening tool's answer.

The proof is worked out by the Shariah engine from the company's own results filing. Nothing here decides anything:
it only picks the parts a person or a model needs (the verdict, the ratios against their limits, the filing and its
link, what the result leaves out) and keeps the engine's own words. The shape matches the older sample-based answer
so the renderers and the guard that checks a reply against the screener keep working.
"""

from __future__ import annotations

from typing import Any

from quant_system.copilot.registry import ToolResult

__all__ = ["VERDICT_WORDS", "proof_result", "source_line"]

VERDICT_WORDS = {
    "COMPLIANT": "compliant",
    "NON_COMPLIANT": "not compliant",
    "QUESTIONABLE": "questionable",
    "NOT_SCREENED": "not screened",
}
_PASSING = ("PASS", "BORDERLINE")


def source_line(filing: dict[str, Any]) -> str:
    """The sentence that says the result is from the company's own filing, with the date it was filed."""
    filed = filing.get("filed_on")
    when = f"filed {filed}" if filed else f"for {filing.get('period_label') or 'its latest period'}"
    return f"Screened from the company's own filing, {when}"


def _ratio(test: dict[str, Any]) -> dict[str, Any]:
    high, low, limit = test["high"], test["low"], float(test["limit_pct"])
    return {
        "name": test["title"],
        "actual_pct": high["pct"],
        "lower_pct": low["pct"],
        "threshold_pct": limit,
        "headroom_pct": round(limit - high["pct"], 4),
        "within_limit": test["result"] in _PASSING,
        "in_warning_band": test["result"] == "BORDERLINE",
        "result": test["result"],
    }


def _standard(block: dict[str, Any]) -> dict[str, Any]:
    """One standard: its status, its sentence, and every test that could be worked out against its limit."""
    return {
        "standard": block["standard"],
        "status": block["status"],
        "summary": block["summary"],
        "ratios": [_ratio(t) for t in block["tests"] if t["result"] != "NOT_COMPUTED"],
    }


def _filing(filing: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "source_url",
        "detail_url",
        "period_end",
        "period_label",
        "filed_on",
        "consolidated",
        "audited",
    )
    return {
        **{k: filing.get(k) for k in keys},
        "figures_agree_with_themselves": filing["tie_out"]["ok"],
    }


def _business(proof: dict[str, Any]) -> dict[str, Any]:
    sector = proof["sector"]
    failed = sector["status"] == "FAIL"
    return {
        "sector_compliant": not failed,
        "sector_failure_reason": sector.get("reason") if failed else None,
        "business_test": sector.get("plain"),
    }


def _answer(symbol: str, proof: dict[str, Any]) -> dict[str, Any]:
    filing = proof["filing"]
    answer: dict[str, Any] = {
        "covered": True,
        "symbol": symbol,
        "company": proof["company_name"],
        "verdict": proof["verdict"],
        "headline": proof["headline"],
        **_business(proof),
        "standards": [_standard(s) for s in proof["standards"]],
        "standards_disagree": bool(proof["divergence"]["noted"]),
        "disagreement_reason": proof["divergence"]["explanation"],
        "purification_ratio_pct": None,
        "data_status": proof["data_status"],
        "data_notice": proof["data_notice"],
        "verdict_source": "filing" if filing else "business",
        "what_would_change_it": list(proof["what_would_change_it"]),
        "not_covered": list(proof["not_covered"]),
    }
    if filing:
        answer["filing"] = _filing(filing)
        answer["source_line"] = source_line(filing)
        answer["provenance"] = {
            "reporting_period": filing["period_label"],
            "filing_date": filing["filed_on"],
            "source_document": filing["source_url"],
        }
    else:
        answer["provenance"] = {
            "reporting_period": None,
            "filing_date": None,
            "source_document": None,
        }
    return answer


def _summary(symbol: str, proof: dict[str, Any]) -> str:
    word = VERDICT_WORDS.get(proof["verdict"], "not screened")
    filing = proof["filing"]
    if filing:
        return f"{symbol}: {word}. {source_line(filing)}."
    return f"{symbol}: {word}. Decided on the company's business alone: its balance sheet was not read."


def proof_result(symbol: str, proof: dict[str, Any]) -> ToolResult:
    """The tool's answer for a proof that is not the old sample: from a filing, or a business that fails on its own."""
    if proof["verdict"] == "NOT_SCREENED":
        data = {
            "covered": False,
            "symbol": symbol,
            "message": proof["headline"],
            "verdict": "NOT_SCREENED",
            "data_status": "NOT_SCREENED",
            "data_notice": proof["data_notice"],
            "not_covered": list(proof["not_covered"]),
        }
        return ToolResult(True, f"{symbol}: not screened yet", data)
    return ToolResult(True, _summary(symbol, proof), _answer(symbol, proof))
