"""The proof for one stock: the verdict, the tests behind it, the figures and the filing they came from.

The ratio engine (`screener_service.evaluate_company_shariah`) does every division and every comparison with a limit.
This module only chooses which figures to hand it (a lower and an upper reading where a filing does not say), puts the
results in the order a person reads them, and says in plain words what each one means. Nothing here is an opinion.
"""

from __future__ import annotations

from typing import Any

from quant_system.shariah.services.activity_check import ActivityStatus
from quant_system.shariah.services.proof_measures import Measures, company_dict, measures_for
from quant_system.shariah.services.proof_standards import build_standard
from quant_system.shariah.services.proof_text import (
    changes_that_matter,
    divergence_of,
    headline_for,
    sample_comparison,
)
from quant_system.shariah.services.proof_types import FilingIn, ProofInputs
from quant_system.shariah.services.proof_words import data_notice, not_covered_for
from quant_system.shariah.services.screener_service import evaluate_company_shariah

__all__ = ["METHODOLOGY_VERSION", "build_stock_proof"]

METHODOLOGY_VERSION = "shariah-screen-v2"


def _filing_block(filing: FilingIn | None) -> dict[str, Any] | None:
    if filing is None:
        return None
    return {
        "source_url": filing.source_url,
        "detail_url": filing.detail_url,
        "period_end": filing.period_end,
        "period_label": filing.period_label,
        "filed_on": filing.filed_on,
        "consolidated": filing.consolidated,
        "audited": filing.audited,
        "sha256": filing.sha256,
        "tie_out": {"ok": filing.tie_out_ok, "checks": list(filing.tie_out)},
    }


def _standards(measures: Measures) -> list[dict[str, Any]]:
    low = evaluate_company_shariah(company_dict(measures, "low"))
    high = evaluate_company_shariah(company_dict(measures, "high"))
    has_market = measures.market_value is not None and measures.market_value.value_cr > 0
    return [
        build_standard("AAOIFI", (low[0], high[0]), measures, has_market),
        build_standard("TASIS", (low[1], high[1]), measures, has_market),
    ]


def _verdict(activity: ActivityStatus, standards: list[dict[str, Any]]) -> str:
    """COMPLIANT only when the business passes and both standards were worked out and passed."""
    if activity is ActivityStatus.FAIL:
        return "NON_COMPLIANT"
    computed = [s["status"] for s in standards if s["status"] != "NOT_COMPUTED"]
    if computed and all(status == "NON_COMPLIANT" for status in computed):
        return "NON_COMPLIANT"
    if activity is ActivityStatus.NOT_CONFIRMED or len(computed) < len(standards):
        return "QUESTIONABLE"
    return "COMPLIANT" if set(computed) == {"COMPLIANT"} else "QUESTIONABLE"


def _header(inputs: ProofInputs) -> dict[str, Any]:
    return {
        "symbol": inputs.symbol,
        "company_name": inputs.company_name,
        "isin": inputs.isin,
        "data_status": inputs.data_status,
        "data_notice": data_notice(inputs.data_status),
        "methodology_version": METHODOLOGY_VERSION,
        "screened_at": inputs.screened_at,
        "sector": inputs.activity.as_dict(),
        "filing": _filing_block(inputs.filing),
    }


def _not_screened(inputs: ProofInputs) -> dict[str, Any]:
    name = inputs.company_name or inputs.symbol
    return {
        **_header(inputs),
        "data_status": "NOT_SCREENED",
        "data_notice": data_notice("NOT_SCREENED"),
        "verdict": "NOT_SCREENED",
        "headline": (
            f"{name} is not screened yet. QuantOS holds no company filing or sample figures for it, so there is "
            "no result to show."
        ),
        "standards": [],
        "divergence": {"noted": False, "explanation": None},
        "what_would_change_it": [],
        "not_covered": not_covered_for("NOT_SCREENED"),
        "sample_comparison": {"differs": False, "note": None},
    }


def build_stock_proof(inputs: ProofInputs) -> dict[str, Any]:
    """Everything the proof screen shows for one stock, as plain data."""
    measures = measures_for(inputs)
    if measures is None:
        return _not_screened(inputs)
    standards = _standards(measures)
    verdict = _verdict(inputs.activity.status, standards)
    divergence = divergence_of(standards)
    return {
        **_header(inputs),
        "verdict": verdict,
        "headline": headline_for(inputs, verdict, standards, divergence),
        "standards": standards,
        "divergence": divergence,
        "what_would_change_it": changes_that_matter(standards),
        "not_covered": not_covered_for(inputs.data_status),
        "sample_comparison": sample_comparison(inputs, measures),
    }
