"""Fundamentals for the holdings in view: per stock, and for the portfolio as a whole.

Weights come from the portfolio's own valuation (each stock's share of the value in view at its last close). The
portfolio's P/E is a weighted harmonic mean over the holdings that have earnings, which is what the portfolio's
total price over total earnings works out to. Nothing here says what to do with a holding.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Final

from quant_system.fundamentals.service import CompanyAnalysis
from quant_system.fundamentals.views import number

UNKNOWN_SECTOR: Final = "Industry not known"
STATEMENT: Final = (
    "Facts from each company's own filings, shown beside your holdings. Filing dates differ by company. "
    "This is not advice."
)
WEIGHTS_NOTE: Final = (
    "Weights are each stock's share of the value of the holdings in view, at its last close."
)
HEADLINE: Final = {
    "profitable_quarters": "profitable_quarters",
    "profit_growth_ttm_pct": "profit_growth_ttm",
    "net_margin_pct": "net_margin",
    "roe_pct": "roe",
    "debt_to_equity": "debt_to_equity",
    "interest_cover": "interest_cover",
    "pe": "pe",
}
HUNDRED: Final = Decimal(100)
TOP: Final = 5


def _weight(position: dict[str, Any]) -> float | None:
    weight = position.get("weight")
    return float(weight) if weight is not None else None


def _holding(position: dict[str, Any], found: CompanyAnalysis) -> dict[str, Any]:
    weight = _weight(position)
    latest = found.series.latest
    row: dict[str, Any] = {
        "symbol": position["symbol"],
        "name": position.get("name") or found.company_name or None,
        "weight_pct": None if weight is None else round(weight * 100, 2),
        "value": position.get("value"),
        "industry": found.industry,
        "data_status": found.data_status,
        "latest_quarter": latest.period_end.isoformat() if latest else None,
        "scorecard_counts": dict(found.scorecard.counts),
    }
    for name, metric in HEADLINE.items():
        row[name] = number(found.metrics[metric].unit, found.metrics[metric].value)
    return row


def _sector_weights(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for row in rows:
        if row["weight_pct"] is not None:
            sector = row["industry"] or UNKNOWN_SECTOR
            totals[sector] = totals.get(sector, 0.0) + row["weight_pct"]
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    return [{"sector": name, "weight_pct": round(weight, 2)} for name, weight in ordered]


def _average_pe(weighted: list[tuple[float, Decimal]], total_weight: float) -> dict[str, Any]:
    """The weighted harmonic mean: total weight over the sum of weight / P/E."""
    note = (
        "Worked out as total weight divided by the sum of each weight over its P/E, on holdings with positive "
        "earnings. It is the portfolio's price over its earnings, not an average of the ratios."
    )
    if not weighted:
        return {
            "value": None,
            "method": "harmonic mean",
            "holdings_included": 0,
            "weight_included_pct": 0.0,
            "note": note,
        }
    included = sum(weight for weight, _ in weighted)
    value = included / sum(weight / float(pe) for weight, pe in weighted)
    share = included / total_weight * 100 if total_weight else 0.0
    return {
        "value": round(value, 2),
        "method": "harmonic mean",
        "holdings_included": len(weighted),
        "weight_included_pct": round(share, 2),
        "note": note,
    }


def _dates(found: list[CompanyAnalysis]) -> dict[str, Any]:
    latest = [f.series.latest.period_end for f in found if f.series.latest is not None]
    priced = [f.price.as_of for f in found if f.price is not None]
    return {
        "newest_filing": max(latest).isoformat() if latest else None,
        "oldest_latest_quarter": min(latest).isoformat() if latest else None,
        "price_date": max(priced).isoformat() if priced else None,
    }


def portfolio_fundamentals(
    positions: list[dict[str, Any]], analyses: dict[str, CompanyAnalysis], scope: dict[str, Any]
) -> dict[str, Any]:
    """The holdings in view with their fundamentals. `positions` come from the portfolio, one per stock."""
    rows = [_holding(p, analyses[str(p["symbol"])]) for p in positions]
    held = [analyses[str(p["symbol"])] for p in positions]
    weights = sorted((r["weight_pct"] for r in rows if r["weight_pct"] is not None), reverse=True)
    weighted = [
        (_weight(p) or 0.0, a.metrics["pe"].value)
        for p, a in zip(positions, held, strict=True)
        if _weight(p) is not None and a.metrics["pe"].value is not None
    ]
    total_weight = sum(w for w in (_weight(p) for p in positions) if w is not None)
    no_data = [r["symbol"] for r in rows if r["data_status"] == "NOT_AVAILABLE"]
    return {
        "statement": STATEMENT,
        "weights_note": WEIGHTS_NOTE,
        "scope": scope,
        "holdings_count": len(rows),
        "top5_weight_pct": round(sum(weights[:TOP]), 2),
        "sector_weights": _sector_weights(rows),
        "weighted_average_pe": _average_pe(
            [(w, pe) for w, pe in weighted if pe is not None], total_weight
        ),
        "without_data_count": len(no_data),
        "without_data": no_data,
        "stale_count": sum(1 for r in rows if r["data_status"] == "STALE"),
        "holdings_without_value": [r["symbol"] for r in rows if r["weight_pct"] is None],
        "data_dates": _dates(held),
        "holdings": rows,
    }
