"""Metrics that need a balance sheet, a price, or both: borrowings, return on equity, P/E, earnings yield and P/B.

The balance sheet is used only when it is recent enough (within nine months of the latest quarter) and ties out.
The price is always the platform's own last close, and both dates are stated.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import NamedTuple

from quant_system.fundamentals import fmt
from quant_system.fundamentals.metric_types import (
    PERCENT,
    TIMES,
    Metric,
    Metrics,
    PriceQuote,
    Span,
    build,
    figure_proof,
    missing,
    price_proof,
)
from quant_system.fundamentals.models import BalanceFigures, QuarterFigures
from quant_system.fundamentals.series import Series

MAX_BALANCE_AGE_MONTHS = 9
HUNDRED = Decimal(100)
NO_SHEET = (
    "No balance sheet is held for this company yet. The September and March filings carry one."
)
NO_PRICE = "Market data is not connected, so price-based figures are not shown."
NO_OWNERS_EQUITY = "The filing does not give the owners' equity, so this cannot be worked out."
NO_EQUITY = "The owners' equity is zero or negative, so this ratio is not meaningful."


class Sheet(NamedTuple):
    quarter: QuarterFigures
    balance: BalanceFigures


def _months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def _latest_sheet(series: Series) -> Sheet | str:
    """The newest usable balance sheet, or the plain reason there is none that can be used."""
    held = [
        Sheet(slot.quarter, slot.quarter.balance)
        for slot in series.slots
        if slot.quarter is not None
        and slot.quarter.balance is not None
        and slot.quarter.balance.usable
    ]
    if not held or series.latest is None:
        return NO_SHEET
    newest = max(held, key=lambda sheet: sheet.balance.as_of)
    age = _months_between(newest.balance.as_of, series.latest.period_end)
    if age > MAX_BALANCE_AGE_MONTHS:
        return (
            f"The newest balance sheet is for {fmt.day(newest.balance.as_of)}, more than nine months "
            "before the latest quarter, so balance-sheet figures are not shown."
        )
    return newest


def _owners_equity(sheet: Sheet, key: str) -> tuple[Decimal | None, str]:
    equity = sheet.balance.value("equity_owners")
    if equity is None:
        return None, NO_OWNERS_EQUITY
    return (equity, "") if equity > 0 else (None, NO_EQUITY)


def _debt_to_equity(sheet: Sheet) -> Metric:
    key = "debt_to_equity"
    lines = sheet.balance.lines
    debts = [lines[k] for k in ("borrowings_current", "borrowings_noncurrent") if k in lines]
    equity, reason = _owners_equity(sheet, key)
    if not debts:
        return missing(
            key,
            TIMES,
            "Borrowings are not filed in this balance sheet, so the ratio cannot be worked out.",
        )
    if equity is None:
        return missing(key, TIMES, reason)
    quarter, balance = sheet
    value = sum((figure.value for figure in debts), Decimal(0)) / equity
    metric = build(
        key, TIMES, value, Span(f"Balance sheet at {fmt.day(balance.as_of)}", balance.as_of)
    )
    inputs = [figure_proof(quarter, figure, "Borrowings") for figure in debts]
    inputs.append(figure_proof(quarter, lines["equity_owners"], "Equity of the owners"))
    note = ""
    if len(debts) == 1:
        note = "Only one of current and non-current borrowings is filed; the other is not counted."
    lease = " Lease liabilities are not itemised in the results filing, so they are not counted."
    return replace(metric, inputs=tuple(inputs), note=note + lease)


def _roe(sheet: Sheet, earnings: Metrics) -> Metric:
    key = "roe"
    profit = earnings["ttm_net_profit"]
    equity, reason = _owners_equity(sheet, key)
    if profit.value is None or profit.as_of is None:
        return missing(key, PERCENT, profit.reason)
    if equity is None:
        return missing(key, PERCENT, reason)
    quarter, balance = sheet
    period = f"{profit.period} against equity at {fmt.day(balance.as_of)}"
    span = Span(period, min(profit.as_of, balance.as_of))
    metric = build(key, PERCENT, profit.value / equity * HUNDRED, span)
    note = (
        "Approximate: profit is for the last four quarters but equity is at one date, and the year's "
        "average equity is not used."
    )
    inputs = (
        *profit.inputs,
        figure_proof(quarter, balance.lines["equity_owners"], "Equity of the owners"),
    )
    return replace(metric, inputs=inputs, note=note, approximate=True)


def _price_period(earnings: Metric, price: PriceQuote) -> str:
    ended = fmt.day(earnings.as_of) if earnings.as_of else ""
    return f"Close of {fmt.day(price.as_of)} against earnings for the four quarters ended {ended}"


def _price_ratios(earnings: Metrics, price: PriceQuote | None) -> Metrics:
    eps = earnings["ttm_eps"]
    if price is None:
        return {k: missing(k, u, NO_PRICE) for k, u in (("pe", TIMES), ("earnings_yield", PERCENT))}
    if eps.value is None or eps.as_of is None:
        return {
            k: missing(k, u, eps.reason) for k, u in (("pe", TIMES), ("earnings_yield", PERCENT))
        }
    if eps.value <= 0:
        why = "Earnings per share over the last four quarters is zero or negative, so this is not meaningful."
        return {k: missing(k, u, why) for k, u in (("pe", TIMES), ("earnings_yield", PERCENT))}
    inputs = (price_proof(price), *eps.inputs)
    period = _price_period(eps, price)
    pe = replace(
        build("pe", TIMES, price.close / eps.value, Span(period, eps.as_of)),
        inputs=inputs,
        note=eps.note,
    )
    yield_ = build(
        "earnings_yield", PERCENT, eps.value / price.close * HUNDRED, Span(period, eps.as_of)
    )
    return {"pe": pe, "earnings_yield": replace(yield_, inputs=inputs, note=eps.note)}


def _pb(sheet: Sheet, price: PriceQuote) -> Metric:
    key = "pb"
    equity, reason = _owners_equity(sheet, key)
    quarter, balance = sheet
    shares = quarter.shares
    if equity is None:
        return missing(key, TIMES, reason)
    if shares is None:
        return missing(
            key, TIMES, "The filing with this balance sheet does not give the number of shares."
        )
    book = equity / shares
    period = f"Close of {fmt.day(price.as_of)} against equity at {fmt.day(balance.as_of)}"
    inputs = (
        price_proof(price),
        figure_proof(quarter, balance.lines["equity_owners"], "Equity of the owners"),
    )
    note = "Uses the number of shares filed with the balance sheet."
    return replace(
        build(key, TIMES, price.close / book, Span(period, balance.as_of)), inputs=inputs, note=note
    )


def balance_metrics(series: Series, price: PriceQuote | None, earnings: Metrics) -> Metrics:
    """Every metric that needs a balance sheet or a price."""
    found = _price_ratios(earnings, price)
    sheet = _latest_sheet(series)
    if isinstance(sheet, str):
        reasons = {
            k: missing(k, u, sheet)
            for k, u in (("debt_to_equity", TIMES), ("roe", PERCENT), ("pb", TIMES))
        }
        return {**found, **reasons}
    found["debt_to_equity"] = _debt_to_equity(sheet)
    found["roe"] = _roe(sheet, earnings)
    found["pb"] = _pb(sheet, price) if price is not None else missing("pb", TIMES, NO_PRICE)
    return found
