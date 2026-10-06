"""Shariah screening and fundamentals. The deterministic screener decides; nothing here lets a model overrule it.

Every result says what the data is. The bundled screening data is an illustrative hand-entered sample, so each
verdict carries ``UNVERIFIED_SAMPLE`` and the sample's notice, and a stock outside the sample is reported as
something QuantOS cannot screen, never guessed at.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quant_system.copilot.registry import Param, ToolContext, ToolResult, ToolSpec, bound, failure
from quant_system.copilot.tools_market import SYMBOL, pct
from quant_system.shariah.schemas.screening import SAMPLE_DATA_NOTICE, UNVERIFIED_SAMPLE

SCREENING_DISCLAIMER = (
    "A screening aid built on published thresholds, not a religious ruling (fatwa). It does not replace a "
    "qualified scholar's judgement."
)
_FUNDAMENTAL_KEYS = (
    "pe_ratio",
    "pb_ratio",
    "dividend_yield",
    "market_cap",
    "total_assets",
    "total_debt",
    "total_cash_and_investments",
    "total_revenue",
)


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
    message = (
        f"QuantOS cannot screen {symbol}: its screening data is an illustrative sample of {count} companies "
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

    aaoifi, tasis, divergence, reason = evaluate_company_shariah(dict(row))
    standards = [_standard(aaoifi), _standard(tasis)]
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
        "purification_ratio_pct": pct(row.get("purification_ratio")),
        "provenance": {
            "reporting_period": row.get("reporting_period"),
            "filing_date": row.get("filing_date"),
            "source_document": row.get("source_document"),
        },
        "data_status": UNVERIFIED_SAMPLE,
        "data_notice": SAMPLE_DATA_NOTICE,
        "disclaimer": SCREENING_DISCLAIMER,
    }
    verdicts = ", ".join(f"{s['standard']} {s['status']}" for s in standards)
    return ToolResult(True, f"{symbol}: {verdicts} (sample data)", data)


def shariah_check(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.shariah is None:
        return failure("no screening data", "Shariah screening data is not available.")
    symbol = str(args["symbol"]).strip().upper()
    row = ctx.shariah.company(symbol)
    if row is None:
        return _not_covered(symbol, ctx.shariah.company_count())
    return _covered(symbol, row)


def fundamentals(ctx: ToolContext, args: Mapping[str, Any]) -> ToolResult:
    if ctx.shariah is None:
        return failure("no fundamentals", "Fundamental data is not available.")
    symbol = str(args["symbol"]).strip().upper()
    row = ctx.shariah.company(symbol)
    if row is None:
        message = (
            "QuantOS has no fundamentals feed. The only balance-sheet figures it holds are an illustrative "
            "sample for a few dozen companies, and this is not one of them."
        )
        return ToolResult(
            True,
            f"{symbol}: no fundamentals",
            {"available": False, "symbol": symbol, "message": message},
        )
    data: dict[str, Any] = {
        "available": True,
        "symbol": symbol,
        **{k: row.get(k) for k in _FUNDAMENTAL_KEYS},
    }
    data.update(
        reporting_period=row.get("reporting_period"),
        data_status=UNVERIFIED_SAMPLE,
        data_notice=SAMPLE_DATA_NOTICE,
    )
    return ToolResult(True, f"{symbol}: sample fundamentals", data)


_SHARIAH_HELP = (
    "The deterministic Shariah screen for one stock: both standards, every ratio, data status. "
    "Only this tool may state a halal verdict."
)


def screening_specs(ctx: ToolContext) -> list[ToolSpec]:
    return [
        bound(ctx, "shariah_check", "Halal screening", _SHARIAH_HELP, (SYMBOL,), shariah_check),
        bound(
            ctx,
            "fundamentals",
            "Company fundamentals",
            "Balance-sheet style figures (sample data, few companies).",
            (SYMBOL,),
            fundamentals,
        ),
    ]


__all__ = ["Param", "SCREENING_DISCLAIMER", "screening_specs"]
