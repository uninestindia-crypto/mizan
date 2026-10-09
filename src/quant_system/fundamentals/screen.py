"""A screen over every company held, using only the filters the caller chose.

It never ranks, never scores and never says one company is better than another. It counts what it considered,
what it left out for missing data and what it left out because of the filters, and it says so in the answer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final

from quant_system.fundamentals.service import STALE, CompanyAnalysis
from quant_system.fundamentals.views import number

STATEMENT: Final = "These are filters you chose, not a recommendation."
MAX_LIMIT: Final = 100
Test = Callable[[Decimal, Decimal], bool]


@dataclass(frozen=True)
class Filters:
    min_profitable_quarters: int | None = None
    min_roe_pct: Decimal | None = None
    max_debt_to_equity: Decimal | None = None
    min_interest_cover: Decimal | None = None
    min_ttm_profit_growth_pct: Decimal | None = None
    max_pe: Decimal | None = None
    sector: str | None = None


@dataclass(frozen=True)
class Rule:
    name: str
    metric: str
    test: Test
    words: str


def _at_least(value: Decimal, limit: Decimal) -> bool:
    return value >= limit


def _at_most(value: Decimal, limit: Decimal) -> bool:
    return value <= limit


RULES: Final = (
    Rule(
        "min_profitable_quarters",
        "profitable_quarters",
        _at_least,
        "Profit in at least {} of the last 8 quarters",
    ),
    Rule(
        "min_roe_pct", "roe", _at_least, "Profit of at least {}% of the owners' money (approximate)"
    ),
    Rule(
        "max_debt_to_equity",
        "debt_to_equity",
        _at_most,
        "Borrowings of at most {} times the owners' money",
    ),
    Rule(
        "min_interest_cover",
        "interest_cover",
        _at_least,
        "Profit covers the interest bill at least {} times",
    ),
    Rule(
        "min_ttm_profit_growth_pct",
        "profit_growth_ttm",
        _at_least,
        "Profit over the last four quarters changed by at least {}% against the four before",
    ),
    Rule("max_pe", "pe", _at_most, "Price at most {} times earnings per share"),
)
#: What a caller may sort by: the name used in the request, and the metric (or company field) behind it.
SORT_FIELDS: Final = {
    "symbol": "",
    "profitable_quarters": "profitable_quarters",
    "roe_pct": "roe",
    "debt_to_equity": "debt_to_equity",
    "interest_cover": "interest_cover",
    "ttm_profit_growth_pct": "profit_growth_ttm",
    "pe": "pe",
    "net_margin_pct": "net_margin",
    "ttm_revenue_inr": "ttm_revenue",
    "ttm_net_profit_inr": "ttm_net_profit",
}
ROW_FIELDS: Final = {key: metric for key, metric in SORT_FIELDS.items() if metric}


def _plain(value: Decimal | int) -> str:
    return f"{value.normalize():f}" if isinstance(value, Decimal) else str(value)


def _limit_of(filters: Filters, rule: Rule) -> Decimal | None:
    raw = getattr(filters, rule.name)
    return None if raw is None else Decimal(raw)


def _value(found: CompanyAnalysis, metric: str) -> Decimal | None:
    return found.metrics[metric].value if metric in found.metrics else None


def _verdict(found: CompanyAnalysis, filters: Filters) -> tuple[str, str]:
    """('match', ''), ('missing', rule name) or ('failed', rule name) for one company."""
    for rule in RULES:
        limit = _limit_of(filters, rule)
        if limit is None:
            continue
        value = _value(found, rule.metric)
        if value is None:
            return "missing", rule.name
        if not rule.test(value, limit):
            return "failed", rule.name
    return _industry_verdict(found, filters)


def _industry_verdict(found: CompanyAnalysis, filters: Filters) -> tuple[str, str]:
    if not filters.sector:
        return "match", ""
    if not found.industry:
        return "missing", "sector"
    wanted = filters.sector.strip().lower()
    return ("match", "") if wanted in found.industry.lower() else ("failed", "sector")


def _entry(rule: Rule, limit: Decimal) -> dict[str, Any]:
    return {"filter": rule.name, "value": float(limit), "plain": rule.words.format(_plain(limit))}


def _applied(filters: Filters) -> list[dict[str, Any]]:
    limits = [(rule, _limit_of(filters, rule)) for rule in RULES]
    applied = [_entry(rule, limit) for rule, limit in limits if limit is not None]
    if filters.sector:
        words = f'Industry group contains "{filters.sector.strip()}"'
        applied.append({"filter": "sector", "value": filters.sector, "plain": words})
    return applied


def _row(found: CompanyAnalysis) -> dict[str, Any]:
    latest = found.series.latest
    row: dict[str, Any] = {
        "symbol": found.symbol,
        "company_name": found.company_name or None,
        "industry": found.industry,
        "data_status": found.data_status,
        "latest_quarter": latest.period_end.isoformat() if latest else None,
        "basis": None
        if found.series.consolidated is None
        else ("consolidated" if found.series.consolidated else "standalone"),
        "scorecard_counts": dict(found.scorecard.counts),
    }
    for name, metric in ROW_FIELDS.items():
        row[name] = number(found.metrics[metric].unit, found.metrics[metric].value)
    return row


def _sorted(rows: list[dict[str, Any]], by: str, order: str) -> list[dict[str, Any]]:
    held = sorted(
        (r for r in rows if r.get(by) is not None),
        key=lambda r: (r[by], r["symbol"]),
        reverse=order == "desc",
    )
    return held + sorted((r for r in rows if r.get(by) is None), key=lambda r: r["symbol"])


def _dates(considered: list[CompanyAnalysis]) -> dict[str, Any]:
    latest = [f.series.latest.period_end for f in considered if f.series.latest is not None]
    priced = [f.price.as_of for f in considered if f.price is not None]
    return {
        "newest_filing": max(latest).isoformat() if latest else None,
        "oldest_latest_quarter": min(latest).isoformat() if latest else None,
        "price_date": max(priced).isoformat() if priced else None,
        "snapshot_built_on": None,
    }


def screen(
    considered: list[CompanyAnalysis], filters: Filters, sort: str, order: str, limit: int
) -> dict[str, Any]:
    """Apply the caller's filters. `sort` must be one of SORT_FIELDS and `order` asc or desc (the route checks)."""
    counts: dict[str, list[CompanyAnalysis]] = {"match": [], "missing": [], "failed": []}
    missing_by: dict[str, int] = {}
    for found in considered:
        outcome, name = _verdict(found, filters)
        counts[outcome].append(found)
        if outcome == "missing":
            missing_by[name] = missing_by.get(name, 0) + 1
    rows = _sorted([_row(f) for f in counts["match"]], sort, order)
    cut = rows[: max(0, min(limit, MAX_LIMIT))]
    return {
        "statement": STATEMENT,
        "filters_applied": _applied(filters),
        "sort": {"by": sort, "order": order},
        "considered": len(considered),
        "matched": len(rows),
        "returned": len(cut),
        "excluded_missing_data": len(counts["missing"]),
        "excluded_by_filters": len(counts["failed"]),
        "missing_by_filter": missing_by,
        "stale_in_results": sum(1 for r in rows if r["data_status"] == STALE),
        "data_dates": _dates(considered),
        "results": cut,
    }
