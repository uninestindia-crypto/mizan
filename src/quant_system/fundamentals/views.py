"""A company's analysis as plain JSON-ready dictionaries: numbers are numbers, dates are ISO text, words are plain."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

from quant_system.fundamentals.metric_types import COUNT, INR, Metric, PriceQuote, Proof
from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.scorecard import Fact, Scorecard
from quant_system.fundamentals.series import Series
from quant_system.fundamentals.service import CompanyAnalysis

STATEMENT: Final = (
    "These are facts from the company's own filings, with their dates. Rules of thumb are labelled as such. "
    "This is not advice and not a forecast."
)
NOT_COVERED: Final = (
    "Figures are as the company filed them, in rupees, and are not adjusted for later splits, bonuses or buybacks.",
    "Lease liabilities are not itemised in the results filing, so borrowings do not include them.",
    "Dividends are not part of the quarterly results filing and are not shown.",
    "Price ratios use QuantOS's own end-of-day price; the price date is shown beside each ratio.",
    "Rules of thumb are conventions. The same limits are used for every industry.",
)


def number(unit: str, value: Decimal | None) -> int | float | None:
    """A metric value as a JSON number: whole rupees, counts as integers, ratios to two places."""
    if value is None:
        return None
    if unit in (INR, COUNT):
        return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _money(value: Decimal, unit: str) -> int | float:
    """Rupee amounts as whole numbers when they are whole; per-share figures as decimals."""
    if unit == INR and value == value.to_integral_value():
        return int(value)
    return float(value)


def proof_view(proof: Proof) -> dict[str, Any]:
    return {
        "kind": proof.kind,
        "label": proof.label,
        "tag": proof.tag,
        "value": _money(proof.value, proof.unit),
        "unit": proof.unit,
        "period": proof.period,
        "period_end": proof.period_end.isoformat(),
        "filed_on": proof.filed_on.isoformat() if proof.filed_on else None,
        "filing_url": proof.source_url or None,
        "sha256": proof.sha256 or None,
    }


def metric_view(metric: Metric) -> dict[str, Any]:
    return {
        "key": metric.key,
        "label": metric.label,
        "unit": metric.unit,
        "value": number(metric.unit, metric.value),
        "available": metric.available,
        "reason": metric.reason or None,
        "formula": metric.formula,
        "period": metric.period or None,
        "as_of": metric.as_of.isoformat() if metric.as_of else None,
        "approximate": metric.approximate,
        "note": metric.note or None,
        "extra": dict(metric.extra),
        "inputs": [proof_view(p) for p in metric.inputs],
    }


def fact_view(fact: Fact) -> dict[str, Any]:
    return {
        "key": fact.key,
        "status": fact.status,
        "sentence": fact.sentence,
        "rule_of_thumb": fact.rule or None,
        "metric": fact.metric or None,
    }


def scorecard_view(card: Scorecard) -> dict[str, Any]:
    return {
        "header": card.header,
        "facts": [fact_view(f) for f in card.facts],
        "counts": dict(card.counts),
    }


def quarter_view(item: QuarterFigures) -> dict[str, Any]:
    profit = item.profit_figure()
    return {
        "period_end": item.period_end.isoformat(),
        "period_label": item.period_label,
        "filed_on": item.filed_on.isoformat() if item.filed_on else None,
        "audited": item.audited,
        "consolidated": item.consolidated,
        "revenue_inr": _line(item, "revenue_from_operations"),
        "net_profit_inr": _money(profit.value, INR) if profit else None,
        "eps": _line(item, "eps"),
        "filing_url": item.source_url,
        "sha256": item.sha256,
    }


def _line(item: QuarterFigures, key: str) -> int | float | None:
    figure = item.lines.get(key)
    if figure is None:
        return None
    return float(figure.value) if key == "eps" else _money(figure.value, INR)


def series_view(series: Series) -> dict[str, Any]:
    return {
        "held": sum(1 for slot in series.slots if slot.quarter is not None),
        "quarters": [quarter_view(s.quarter) for s in series.slots if s.quarter is not None],
        "gaps": [day.isoformat() for day in series.gaps],
        "excluded": [
            {"period_end": q.period_end.isoformat(), "status": q.status.value, "reason": q.note}
            for q in series.excluded
        ],
        "notes": list(series.notes),
    }


def basis_view(series: Series) -> dict[str, Any]:
    if series.consolidated is None:
        return {"consolidated": None, "label": None}
    label = (
        "Consolidated: the company and its subsidiaries together"
        if series.consolidated
        else "Standalone: the company on its own"
    )
    return {"consolidated": series.consolidated, "label": label}


def price_view(price: PriceQuote | None) -> dict[str, Any] | None:
    if price is None:
        return None
    return {
        "close": float(price.close),
        "as_of": price.as_of.isoformat(),
        "source": "QuantOS end-of-day price data",
    }


def latest_view(series: Series) -> dict[str, Any] | None:
    latest = series.latest
    return quarter_view(latest) if latest is not None else None


def company_view(found: CompanyAnalysis) -> dict[str, Any]:
    """Everything the stock screen needs about one company's fundamentals."""
    return {
        "symbol": found.symbol,
        "company_name": found.company_name or None,
        "industry": found.industry,
        "data_status": found.data_status,
        "data_notice": found.data_notice,
        "read_status": found.read_status,
        "basis": basis_view(found.series),
        "latest_quarter": latest_view(found.series),
        "series": series_view(found.series),
        "metrics": {key: metric_view(m) for key, m in found.metrics.items()},
        "scorecard": scorecard_view(found.scorecard),
        "price": price_view(found.price),
        "today": found.today.isoformat(),
        "not_covered": list(NOT_COVERED),
        "statement": STATEMENT,
    }
