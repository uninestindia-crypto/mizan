"""Two to four companies side by side. Only companies reported on the same basis are put in the same lines."""

from __future__ import annotations

from typing import Any, Final

from quant_system.fundamentals import fmt
from quant_system.fundamentals.metric_types import Metric
from quant_system.fundamentals.service import CompanyAnalysis
from quant_system.fundamentals.views import number

STATEMENT: Final = (
    "Facts from each company's own filings, side by side. This is not a ranking and not advice."
)
COMPARE_METRICS: Final = (
    "ttm_revenue",
    "ttm_net_profit",
    "ttm_eps",
    "net_margin",
    "operating_margin",
    "revenue_growth_ttm",
    "profit_growth_ttm",
    "profitable_quarters",
    "interest_cover",
    "debt_to_equity",
    "roe",
    "pe",
    "pb",
    "earnings_yield",
)


def _basis_name(consolidated: bool | None) -> str | None:
    return None if consolidated is None else ("consolidated" if consolidated else "standalone")


def _value(metric: Metric) -> dict[str, Any]:
    return {
        "value": number(metric.unit, metric.value),
        "unit": metric.unit,
        "available": metric.available,
        "reason": metric.reason or None,
        "as_of": metric.as_of.isoformat() if metric.as_of else None,
        "period": metric.period or None,
        "approximate": metric.approximate,
    }


def _column(found: CompanyAnalysis, included: bool, reason: str | None) -> dict[str, Any]:
    latest = found.series.latest
    return {
        "symbol": found.symbol,
        "company_name": found.company_name or None,
        "industry": found.industry,
        "included": included,
        "reason": reason,
        "basis": _basis_name(found.series.consolidated),
        "data_status": found.data_status,
        "latest_quarter": latest.period_end.isoformat() if latest else None,
        "scorecard_counts": dict(found.scorecard.counts),
    }


def _reference_basis(found: list[CompanyAnalysis]) -> bool | None:
    """The basis the comparison is made on: the first company with data sets it."""
    return next((f.series.consolidated for f in found if f.series.latest is not None), None)


def _excluded_reason(found: CompanyAnalysis, reference: bool | None) -> str | None:
    if found.series.latest is None:
        return found.data_notice
    if found.series.consolidated != reference:
        theirs, ours = _basis_name(found.series.consolidated), _basis_name(reference)
        return f"Its figures are {theirs}, not {ours}, so they are not put in the same lines."
    return None


def _notes(
    found: list[CompanyAnalysis], included: list[CompanyAnalysis], reference: bool | None
) -> list[str]:
    notes = []
    if (
        len(included) < len(found)
        and len(included) >= 1
        and any(f.series.latest is not None and f.series.consolidated != reference for f in found)
    ):
        notes.append(
            "Some companies are on a different basis, so the comparison is not like for like for them."
        )
    ends = {f.series.latest.period_end for f in included if f.series.latest is not None}
    if len(ends) > 1:
        shown = ", ".join(
            f"{f.symbol} {fmt.day(f.series.latest.period_end)}" for f in included if f.series.latest
        )
        notes.append(
            f"The companies' latest filings are for different quarters ({shown}), so their periods do not line up."
        )
    return notes


def compare(found: list[CompanyAnalysis]) -> dict[str, Any]:
    """Put the companies side by side. The caller has already checked that there are two to four."""
    reference = _reference_basis(found)
    reasons = {f.symbol: _excluded_reason(f, reference) for f in found}
    included = [f for f in found if reasons[f.symbol] is None]
    comparable = len(included) >= 2
    notes = _notes(found, included, reference)
    if not comparable:
        notes.insert(
            0,
            "These companies are not like for like on one basis, so they cannot be compared line by line.",
        )
    rows = [
        {
            "key": key,
            "label": included[0].metrics[key].label if included else key,
            "unit": included[0].metrics[key].unit if included else "",
            "values": {f.symbol: _value(f.metrics[key]) for f in included},
        }
        for key in COMPARE_METRICS
    ]
    return {
        "statement": STATEMENT,
        "comparable": comparable,
        "basis": _basis_name(reference),
        "companies": [_column(f, reasons[f.symbol] is None, reasons[f.symbol]) for f in found],
        "rows": rows if included else [],
        "notes": notes,
    }
