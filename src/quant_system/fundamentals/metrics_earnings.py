"""Metrics from the profit-and-loss lines: four-quarter totals, growth, margins, steadiness and interest cover."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import NamedTuple

from quant_system.fundamentals import fmt
from quant_system.fundamentals.metric_types import (
    COUNT,
    INR,
    PER_SHARE,
    PERCENT,
    TIMES,
    Metric,
    Metrics,
    Proof,
    Span,
    build,
    figure_proof,
    missing,
)
from quant_system.fundamentals.metric_words import NUMBER_WORDS
from quant_system.fundamentals.models import Figure, QuarterFigures
from quant_system.fundamentals.series import Series

NO_QUARTERS = "No usable quarterly filing is held for this company yet."
SHARES_CHANGED = (
    "Approximate: the number of shares changed during these quarters, "
    "so they are not all on one share count."
)
HUNDRED = Decimal(100)
SHARE_CHANGE = Decimal("1.005")
EIGHT = 8
MIN_HELD = 4
Getter = Callable[[QuarterFigures], Figure | None]


class Measure(NamedTuple):
    """A figure to read from each quarter, and its name in plain words."""

    getter: Getter
    what: str


def reason_for_run(series: Series, offset: int, count: int) -> str:
    """Why `count` quarters in a row, starting `offset` back from the latest, cannot be used."""
    if not series.slots:
        return NO_QUARTERS
    start = len(series.slots) - offset - count
    if start < 0:
        have = max(0, len(series.slots) - offset)
        return f"This needs {NUMBER_WORDS[count]} quarters in a row and only {have} are held."
    window = series.slots[start : len(series.slots) - offset]
    gaps = [slot.period_end for slot in window if slot.quarter is None]
    when = fmt.day(gaps[0]) if gaps else "that period"
    return f"The quarter ended {when} has no usable filing, so a run of {NUMBER_WORDS[count]} quarters is not complete."


def line(key: str) -> Getter:
    return lambda quarter: quarter.lines.get(key)


def owners_profit(quarter: QuarterFigures) -> Figure | None:
    return quarter.profit_figure()


def proofs_of(run: list[QuarterFigures], getter: Getter, label: str) -> list[Proof] | None:
    found = [(quarter, getter(quarter)) for quarter in run]
    if any(figure is None for _, figure in found):
        return None
    return [figure_proof(q, figure, label) for q, figure in found if figure is not None]


def total(proofs: list[Proof]) -> Decimal:
    return sum((proof.value for proof in proofs), Decimal(0))


def four_quarters(run: list[QuarterFigures]) -> str:
    return f"Four quarters ended {fmt.day(run[-1].period_end)}"


def _sum_metric(
    series: Series, key: str, unit: str, getter: Getter, what: str
) -> tuple[Metric, list[QuarterFigures] | None]:
    run = series.run(0, 4)
    if run is None:
        return missing(key, unit, reason_for_run(series, 0, 4)), None
    proofs = proofs_of(run, getter, what)
    if proofs is None:
        return missing(
            key, unit, f"{what} is not filed for every one of the last four quarters."
        ), None
    metric = build(key, unit, total(proofs), Span(four_quarters(run), run[-1].period_end))
    return replace(metric, inputs=tuple(proofs)), run


def _shares_changed(run: list[QuarterFigures]) -> bool:
    counts = [quarter.shares for quarter in run]
    known = [count for count in counts if count is not None]
    return len(known) < len(counts) or max(known) > min(known) * SHARE_CHANGE


def _profit_note(run: list[QuarterFigures]) -> str:
    if any(q.consolidated and "owners_profit" not in q.lines for q in run):
        return "The filing does not split profit between owners and minority holders, so profit for the period is used."
    return ""


def totals(series: Series) -> Metrics:
    revenue, _ = _sum_metric(
        series, "ttm_revenue", INR, line("revenue_from_operations"), "Revenue from operations"
    )
    profit, run = _sum_metric(series, "ttm_net_profit", INR, owners_profit, "Profit for the owners")
    eps, eps_run = _sum_metric(series, "ttm_eps", PER_SHARE, line("eps"), "Earnings per share")
    if run is not None:
        profit = replace(profit, note=_profit_note(run))
    if eps_run is not None and _shares_changed(eps_run):
        note = SHARES_CHANGED
        eps = replace(eps, note=note, approximate=True)
    return {"ttm_revenue": revenue, "ttm_net_profit": profit, "ttm_eps": eps}


# ------------------------------------------------------------------------------------------------ growth


def _quarter_growth(series: Series, key: str, getter: Getter, what: str) -> Metric:
    now, before = series.at(0), series.at(4)
    if now is None or before is None:
        reason = (
            NO_QUARTERS if now is None else "The same quarter a year earlier has no usable filing."
        )
        return missing(key, PERCENT, reason)
    first, second = getter(now), getter(before)
    if first is None or second is None:
        return missing(key, PERCENT, f"{what} is not filed for one of the two quarters.")
    if second.value <= 0:
        return missing(
            key,
            PERCENT,
            f"{what} a year earlier was zero or a loss, so a percentage change is not meaningful.",
        )
    value = (first.value - second.value) / second.value * HUNDRED
    period = f"{now.period_label} against {before.period_label}"
    metric = build(key, PERCENT, value, Span(period, now.period_end))
    return replace(
        metric, inputs=(figure_proof(now, first, what), figure_proof(before, second, what))
    )


def _run_growth(series: Series, key: str, offset: int, measure: Measure) -> Metric:
    getter, what = measure
    now, before = series.run(0, 4), series.run(offset, 4)
    if now is None or before is None:
        return missing(key, PERCENT, reason_for_run(series, 0 if now is None else offset, 4))
    first, second = proofs_of(now, getter, what), proofs_of(before, getter, what)
    if first is None or second is None:
        return missing(key, PERCENT, f"{what} is not filed for every quarter needed.")
    if total(second) <= 0:
        return missing(
            key,
            PERCENT,
            f"{what} in the earlier four quarters was zero or a loss, so a percentage change is not meaningful.",
        )
    value = (total(first) - total(second)) / total(second) * HUNDRED
    period = (
        f"{four_quarters(now)} against the four quarters ended {fmt.day(before[-1].period_end)}"
    )
    return replace(
        build(key, PERCENT, value, Span(period, now[-1].period_end)), inputs=(*first, *second)
    )


def growth(series: Series) -> Metrics:
    sales, profit = (
        Measure(line("revenue_from_operations"), "Sales"),
        Measure(owners_profit, "Profit"),
    )
    return {
        "revenue_growth_quarter": _quarter_growth(series, "revenue_growth_quarter", *sales),
        "profit_growth_quarter": _quarter_growth(series, "profit_growth_quarter", *profit),
        "revenue_growth_ttm": _run_growth(series, "revenue_growth_ttm", 4, sales),
        "profit_growth_ttm": _run_growth(series, "profit_growth_ttm", 4, profit),
        "revenue_change_3y": _run_growth(series, "revenue_change_3y", 12, sales),
        "profit_change_3y": _run_growth(series, "profit_change_3y", 12, profit),
    }


# ----------------------------------------------------------------------------------------------- margins


def _net_margin(earnings: Metrics) -> Metric:
    revenue, profit = earnings["ttm_revenue"], earnings["ttm_net_profit"]
    if revenue.value is None or profit.value is None:
        return missing("net_margin", PERCENT, revenue.reason or profit.reason)
    if revenue.value <= 0:
        return missing(
            "net_margin",
            PERCENT,
            "Sales over the last four quarters were zero, so a margin is not meaningful.",
        )
    value = profit.value / revenue.value * HUNDRED
    metric = build("net_margin", PERCENT, value, Span(revenue.period, revenue.as_of))
    return replace(metric, inputs=(*profit.inputs, *revenue.inputs), note=profit.note)


def _operating_margin(series: Series) -> Metric:
    run = series.run(0, 4)
    if run is None:
        return missing("operating_margin", PERCENT, reason_for_run(series, 0, 4))
    sales = proofs_of(run, line("revenue_from_operations"), "Revenue from operations")
    spent = proofs_of(run, line("expenses"), "Total expenses")
    interest = proofs_of(run, line("finance_costs"), "Finance costs")
    if sales is None or spent is None:
        return missing(
            "operating_margin",
            PERCENT,
            "Sales or total expenses are not filed for every one of the last four quarters.",
        )
    if interest is None:
        return missing(
            "operating_margin",
            PERCENT,
            "Finance costs are not filed, so operating profit cannot be worked out.",
        )
    if total(sales) <= 0:
        return missing(
            "operating_margin",
            PERCENT,
            "Sales over the last four quarters were zero, so a margin is not meaningful.",
        )
    operating = total(sales) - (total(spent) - total(interest))
    span = Span(four_quarters(run), run[-1].period_end)
    metric = build("operating_margin", PERCENT, operating / total(sales) * HUNDRED, span)
    return replace(metric, inputs=(*sales, *spent, *interest))


def margins(series: Series, earnings: Metrics) -> Metrics:
    return {"net_margin": _net_margin(earnings), "operating_margin": _operating_margin(series)}


# ------------------------------------------------------------------------------------ steadiness and cover


def _profitable_quarters(series: Series) -> Metric:
    window = series.slots[-EIGHT:]
    held = [slot.quarter for slot in window if slot.quarter is not None]
    if len(held) < MIN_HELD:
        return missing(
            "profitable_quarters",
            COUNT,
            f"At least {NUMBER_WORDS[MIN_HELD]} of the last eight quarters are needed and {len(held)} are held.",
        )
    proofs = proofs_of(held, owners_profit, "Profit for the owners")
    if proofs is None:
        return missing("profitable_quarters", COUNT, "Profit is not filed for every quarter held.")
    count = sum(1 for proof in proofs if proof.value > 0)
    period = f"The last eight quarters, ended {fmt.day(held[-1].period_end)}"
    metric = build("profitable_quarters", COUNT, Decimal(count), Span(period, held[-1].period_end))
    return replace(
        metric, inputs=tuple(proofs), extra={"out_of": EIGHT, "quarters_held": len(held)}
    )


def _interest_cover(series: Series) -> Metric:
    run = series.run(0, 4)
    if run is None:
        return missing("interest_cover", TIMES, reason_for_run(series, 0, 4))
    before_tax = proofs_of(run, line("profit_before_tax"), "Profit before tax")
    interest = proofs_of(run, line("finance_costs"), "Finance costs")
    if before_tax is None or interest is None:
        return missing(
            "interest_cover",
            TIMES,
            "Profit before tax or finance costs are not filed for every one of the last four quarters.",
        )
    if total(interest) <= 0:
        none = (
            "No interest cost was filed in these four quarters, so interest cover does not apply."
        )
        return replace(missing("interest_cover", TIMES, none), extra={"code": "NO_FINANCE_COSTS"})
    value = (total(before_tax) + total(interest)) / total(interest)
    metric = build("interest_cover", TIMES, value, Span(four_quarters(run), run[-1].period_end))
    return replace(metric, inputs=(*before_tax, *interest))


def steadiness(series: Series) -> Metrics:
    return {
        "profitable_quarters": _profitable_quarters(series),
        "interest_cover": _interest_cover(series),
    }


def earnings_metrics(series: Series) -> Metrics:
    """Every metric that needs only the profit-and-loss lines."""
    found = totals(series)
    return {**found, **growth(series), **margins(series, found), **steadiness(series)}
