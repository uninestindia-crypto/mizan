"""Builders shared by the fundamentals tests: real trimmed filings, listing rows, and small hand-made quarters."""

from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from quant_system.fundamentals.models import (
    BalanceFigures,
    Figure,
    QuarterFigures,
    ReadStatus,
    TieOut,
)
from quant_system.shariah.filings.models import ResultRow

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "fundamentals"
CRORE = Decimal(10_000_000)


def cr(amount: int | float) -> int:
    """An amount in crore as whole rupees."""
    return int(Decimal(str(amount)) * CRORE)


SOURCE = "https://nsearchives.nseindia.com/corporate/xbrl/"


def quarter_ends(count: int, last: date = date(2024, 12, 31)) -> list[date]:
    """`count` quarter-end dates, oldest first, the last being `last` (a month end)."""
    found: list[date] = []
    year, month = last.year, last.month
    for _ in range(count):
        found.append(date(year, month, calendar.monthrange(year, month)[1]))
        year, month = (year - 1, month + 9) if month <= 3 else (year, month - 3)
    return found[::-1]


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_text(name: str) -> str:
    return fixture_bytes(name).decode("utf-8")


def listing_row(
    symbol: str = "TCS",
    period_end: date = date(2024, 9, 30),
    consolidated: bool = True,
    flag: str = "N",
    filed_on: date | None = date(2024, 10, 10),
) -> ResultRow:
    """A line of NSE's list of results, as the filings client would hand it over."""
    return ResultRow(
        symbol=symbol,
        company_name=f"{symbol} Limited",
        isin="INE467B01029",
        period_end=period_end,
        relating_to="Second Quarter",
        period_kind="Quarterly",
        consolidated=consolidated,
        audited=True,
        ind_as=flag == "N",
        lender_flag=flag,
        filed_on=filed_on,
        xbrl_url=f"{SOURCE}{symbol}_{period_end.isoformat()}_{int(consolidated)}.xml",
        detail_url=None,
    )


def with_value(text: str, tag: str, context: str, value: str) -> str:
    """The same filing with one fact's number changed."""
    pattern = rf'(<in-bse-fin:{tag} contextRef="{context}"[^>]*>)[^<]*(<)'
    changed, count = re.subn(pattern, rf"\g<1>{value}\g<2>", text)
    assert count == 1, f"{tag} in {context} was not found exactly once"
    return changed


def without_fact(text: str, tag: str, context: str) -> str:
    pattern = rf'<in-bse-fin:{tag} contextRef="{context}"[^>]*>[^<]*</in-bse-fin:{tag}>\r?\n'
    changed, count = re.subn(pattern, "", text)
    assert count == 1, f"{tag} in {context} was not found exactly once"
    return changed


def in_crores(text: str) -> str:
    """The same filing with every rupee amount divided by a crore: the mistake a unit check must catch."""

    def shrink(match: re.Match[str]) -> str:
        amount = Decimal(match.group(3)) / CRORE
        return f"{match.group(1)}{amount:.2f}{match.group(4)}"

    return re.sub(
        r'(<in-bse-fin:\w+ contextRef="\w+" unitRef="INR" [^>]*>)()([\d.-]+)(<)', shrink, text
    )


# ----------------------------------------------------------------------------------------- hand-made quarters

_PASS = (TieOut("Filing agrees with itself", "PASS", "Made by hand for a test."),)


def figure(tag: str, value: int | str | Decimal) -> Figure:
    return Figure(tag, Decimal(value), "-7")


def balance(
    as_of: date,
    equity_owners: int,
    borrowings: tuple[int, int] = (0, 0),
    equity_total: int | None = None,
) -> BalanceFigures:
    lines = {
        "total_assets": figure("Assets", equity_owners * 3),
        "equity_total": figure("Equity", equity_total or equity_owners),
        "equity_owners": figure("EquityAttributableToOwnersOfParent", equity_owners),
        "borrowings_current": figure("BorrowingsCurrent", borrowings[0]),
        "borrowings_noncurrent": figure("BorrowingsNoncurrent", borrowings[1]),
    }
    return BalanceFigures(as_of, lines, _PASS)


def quarter(
    period_end: date,
    revenue: int,
    profit: int,
    finance: int | None = None,
    eps: str | None = None,
    consolidated: bool = True,
    shares: int | None = None,
) -> QuarterFigures:
    """A quarter with round numbers. Tax is a third of profit when profit is positive, so profit before tax adds it."""
    tax = profit // 3 if profit > 0 else 0
    lines = {
        "revenue_from_operations": figure("RevenueFromOperations", revenue),
        "total_income": figure("Income", revenue),
        "expenses": figure("Expenses", revenue - profit - tax),
        "profit_before_tax": figure("ProfitBeforeTax", profit + tax),
        "tax_expense": figure("TaxExpense", tax),
        "profit_for_period": figure("ProfitLossForPeriod", profit),
        "owners_profit": figure("ProfitOrLossAttributableToOwnersOfParent", profit),
    }
    if finance is not None:
        lines["finance_costs"] = figure("FinanceCosts", finance)
    if shares is not None:
        lines["paid_up_capital"] = figure("PaidUpValueOfEquityShareCapital", shares * 10)
        lines["face_value"] = Figure("FaceValueOfEquityShareCapital", Decimal(10), "INF")
    if eps is not None:
        lines["eps"] = Figure(
            "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations", Decimal(eps), "INF"
        )
    stamp = f"{period_end.isoformat()}"
    return QuarterFigures(
        symbol="ABC",
        isin="INE000A01010",
        company_name="ABC Limited",
        period_end=period_end,
        period_start=None,
        period_label=f"Three months ended {stamp}",
        filed_on=period_end + timedelta(days=20),
        consolidated=consolidated,
        audited=True,
        source_url=f"{SOURCE}ABC_{stamp}_{int(consolidated)}.xml",
        sha256=hashlib.sha256(stamp.encode()).hexdigest(),
        fetched_at="2026-10-07T00:00:00Z",
        status=ReadStatus.READ_OK,
        lines=lines,
        tie_out=_PASS,
    )


def with_balance(item: QuarterFigures, sheet: BalanceFigures) -> QuarterFigures:
    return replace(item, balance=sheet)


FRESH = date(
    2021, 3, 1
)  # the fixture market data runs through 2020, so filings to Dec 2020 are recent on this day


def fund_rows(symbol: str, step: int = 3) -> list[QuarterFigures]:
    """Eight quarters to Dec 2020 for a company: sales 100..170 crore, profit step x 3..10 crore, one balance sheet."""
    ends = quarter_ends(8, date(2020, 12, 31))
    items = [
        quarter(
            e,
            cr(100 + 10 * i),
            cr(step * (i + 3)),
            cr(2),
            str(Decimal(step * (i + 3)) / 10),
            shares=10_000_000,
        )
        for i, e in enumerate(ends)
    ]
    items[6] = with_balance(items[6], balance(ends[6], cr(400), (cr(30), cr(10))))
    return [replace(item, symbol=symbol, company_name=f"{symbol} Limited") for item in items]
