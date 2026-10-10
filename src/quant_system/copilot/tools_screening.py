"""Shariah screening and fundamentals. The deterministic screener decides; nothing here lets a model overrule it.

Every result says what the data is. The bundled screening data is an illustrative hand-entered sample, so each
verdict carries ``UNVERIFIED_SAMPLE`` and the sample's notice, and a stock outside the sample is reported as
something QuantOS cannot screen, never guessed at.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from typing import Any

from quant_system.copilot.registry import (
    Param,
    ToolContext,
    ToolResult,
    ToolSpec,
    ToolText,
    bound,
    failure,
)
from quant_system.copilot.screening_proof import proof_result
from quant_system.copilot.tools_market import PERCENT_NOTE, SYMBOL, pct
from quant_system.shariah.schemas.screening import SAMPLE_DATA_NOTICE, UNVERIFIED_SAMPLE

logger = logging.getLogger(__name__)

SCREENING_DISCLAIMER = (
    "A screening aid built on published thresholds, not a religious ruling (fatwa). It does not replace a "
    "qualified scholar's judgement."
)
_FUNDAMENTAL_KEYS = (
    "pe_ratio",
    "pb_ratio",
    "market_cap",
    "total_assets",
    "total_debt",
    "total_cash_and_investments",
    "total_revenue",
)
# The figures a halal verdict is computed from. If any one cannot be read as a finite number, there is no verdict.
_SCREEN_INPUTS = (
    "total_debt",
    "total_cash_and_investments",
    "total_receivables",
    "total_assets",
    "avg_36m_market_cap",
    "total_impermissible_income",
    "total_revenue",
)
UNREADABLE = "The screening data for this stock could not be read."


def _number(value: Any) -> float | None:
    """The value as a finite number, or None when it is missing, text that is not a number, NaN or infinite."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


_STATUS_WORDS = {
    "COMPLIANT": "compliant",
    "NON_COMPLIANT": "not compliant",
    "QUESTIONABLE": "questionable",
}


def _ratio(meter: Any) -> dict[str, Any]:
    return {
        "name": meter.metric_name,
        "actual_pct": meter.actual_pct,
        "threshold_pct": meter.threshold_pct,
        "headroom_pct": round(meter.threshold_pct - meter.actual_pct, 4),
        "within_limit": meter.is_compliant,
        "in_warning_band": meter.is_warning,
    }


def _standard(evaluation: Any) -> dict[str, Any]:
    meters = (
        evaluation.debt_ratio,
        evaluation.cash_ratio,
        evaluation.receivables_ratio,
        evaluation.impermissible_income_ratio,
    )
    return {
        "standard": evaluation.standard.value,
        "status": evaluation.status.value,
        "summary": evaluation.summary,
        "ratios": [_ratio(meter) for meter in meters],
    }


def _not_covered(symbol: str, count: int) -> ToolResult:
    noun = "company" if count == 1 else "companies"
    message = (
        f"QuantOS cannot screen {symbol}: its screening data is an illustrative sample of {count} {noun} "
        f"and {symbol} is not one of them."
    )
    data = {
        "covered": False,
        "symbol": symbol,
        "message": message,
        "data_status": UNVERIFIED_SAMPLE,
        "disclaimer": SCREENING_DISCLAIMER,
    }
    return ToolResult(True, f"{symbol}: not in the screening sample", data)


def _covered(symbol: str, row: Mapping[str, Any]) -> ToolResult:
    # Imported here: the screener pulls in the Shariah package, which a tool test should not need.
    from quant_system.shariah.services.screener_service import evaluate_company_shariah

    if any(_number(row.get(key)) is None for key in _SCREEN_INPUTS):
        return failure(f"{symbol}: screening data could not be read", UNREADABLE)
    aaoifi, tasis, divergence, reason = evaluate_company_shariah(dict(row))
    standards = [_standard(aaoifi), _standard(tasis)]
    if not all(_number(r["actual_pct"]) is not None for s in standards for r in s["ratios"]):
        return failure(f"{symbol}: screening data could not be read", UNREADABLE)
    data = {
        "covered": True,
        "symbol": symbol,
        "company": row.get("company_name"),
        "sector": row.get("sector"),
        "sector_compliant": bool(row.get("sector_compliant", True)),
        "sector_failure_reason": row.get("sector_failure_reason"),
        "standards": standards,
        "standards_disagree": bool(divergence),
        "disagreement_reason": reason,
        "purification_ratio_pct": pct(_number(row.get("purification_ratio"))),
        "provenance": {
            "reporting_period": row.get("reporting_period"),
            "filing_date": row.get("filing_date"),
            "source_document": row.get("source_document"),
        },
        "data_status": UNVERIFIED_SAMPLE,
        "data_notice": SAMPLE_DATA_NOTICE,
        "disclaimer": SCREENING_DISCLAIMER,
    }
    verdicts = ", ".join(
        f"{s['standard']} {_STATUS_WORDS.get(s['status'], s['status'])}" for s in standards
    )
    return ToolResult(True, f"{symbol}: {verdicts} (sample data)", data)


def _proof_of(source: Any, symbol: str) -> dict[str, Any] | None:
    """The Shariah engine's proof for a stock, when the screening data can give one. Otherwise the sample decides."""
    fetch = getattr(source, "proof", None)
    if not callable(fetch):
        return None
    try:
        proof = fetch(symbol)
    except Exception:  # a proof that cannot be had must never stop the sample from answering
        logger.warning("the Shariah proof for %s could not be had", symbol, exc_info=True)
        return None
    return proof if isinstance(proof, dict) else None


def _decisive(proof: dict[str, Any] | None) -> bool:
    """A proof that decides on its own: from a company's filing, or from its business alone. Not the old sample."""
    return (
        proof is not None
        and proof.get("data_status") != UNVERIFIED_SAMPLE
        and proof.get("verdict") != "NOT_SCREENED"
    )


def _with_disclaimer(result: ToolResult) -> ToolResult:
    return ToolResult(True, result.summary, {**result.data, "disclaimer": SCREENING_DISCLAIMER})


def shariah_check(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.shariah is None:
        return failure("no screening data", "Shariah screening data is not available.")
    symbol = str(args["symbol"]).strip().upper()
    proof = _proof_of(ctx.shariah, symbol)
    if proof is not None and _decisive(proof):
        return _with_disclaimer(proof_result(symbol, proof))
    # An unreadable sample is still said, in plain words, and never hidden behind "not screened".
    row = ctx.shariah.company(symbol)
    if row is not None:
        return _covered(symbol, row)
    if proof is not None and proof.get("data_status") != UNVERIFIED_SAMPLE:
        return _with_disclaimer(proof_result(symbol, proof))
    return _not_covered(symbol, ctx.shariah.company_count())


def fundamentals(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.shariah is None:
        return failure("no fundamentals", "Fundamental data is not available.")
    symbol = str(args["symbol"]).strip().upper()
    row = ctx.shariah.company(symbol)
    if row is None:
        message = (
            "QuantOS does not hold company financial statements. The only balance-sheet figures it has are an "
            "illustrative sample for a few dozen companies, and this is not one of them."
        )
        return ToolResult(
            True,
            f"{symbol}: no fundamentals",
            {"available": False, "symbol": symbol, "message": message},
        )
    data: dict[str, Any] = {
        "available": True,
        "symbol": symbol,
        **{k: _number(row.get(k)) for k in _FUNDAMENTAL_KEYS},
        "dividend_yield_pct": pct(_number(row.get("dividend_yield"))),
    }
    data.update(
        reporting_period=row.get("reporting_period"),
        data_status=UNVERIFIED_SAMPLE,
        data_notice=SAMPLE_DATA_NOTICE,
    )
    return ToolResult(True, f"{symbol}: sample fundamentals", data)


_TEXT = {
    "shariah_check": ToolText(
        "Halal screening",
        "Checks a stock against the halal screening standards and shows every figure it used.",
        "The deterministic Shariah screen for one stock: both standards, every ratio, data status. "
        "Only this tool may state a halal verdict. " + PERCENT_NOTE,
    ),
    "fundamentals": ToolText(
        "Company fundamentals",
        "Shows balance-sheet figures for the few companies in the sample data.",
        "Balance-sheet style figures (sample data, few companies). " + PERCENT_NOTE,
    ),
}


def screening_specs(ctx: ToolContext) -> list[ToolSpec]:
    return [
        bound(ctx, "shariah_check", _TEXT["shariah_check"], (SYMBOL,), shariah_check),
        bound(ctx, "fundamentals", _TEXT["fundamentals"], (SYMBOL,), fundamentals),
    ]


__all__ = ["Param", "SCREENING_DISCLAIMER", "screening_specs"]
