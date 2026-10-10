"""Checks a filing makes against itself. A filing that fails one is marked and left out of every metric.

Nothing is repaired. A check that cannot be made because an input was not filed is SKIPPED, which is not a failure.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from quant_system.fundamentals import fmt
from quant_system.fundamentals.models import FAIL, PASS, SKIPPED, Figure, TieOut

Lines = dict[str, Figure]

CHECK_REQUIRED: Final = "All required figures are present"
CHECK_UNITS: Final = "Amounts are in rupees"
CHECK_PROFIT: Final = "Total income less expenses equals profit before tax"
CHECK_TAX: Final = "Profit before tax less tax equals profit for the period"
CHECK_OWNERS: Final = "Owners and minority shares add up to profit for the period"
CHECK_EPS: Final = "Earnings per share agrees with profit and share count"
CHECK_LISTING: Final = "Filing agrees with NSE's listing"
CHECK_BALANCE: Final = "Equity plus liabilities equals total assets"
CHECK_SIGNS: Final = "Borrowings and cash are not negative"

MIN_INCOME: Final = Decimal(100_000)
MAX_INCOME: Final = Decimal(10) ** 15
LEEWAY_RATIO: Final = Decimal("0.001")
EPS_ROUNDING: Final = Decimal("0.005")
EPS_BAND: Final = Decimal("0.5")


def _value(lines: Lines, key: str) -> Decimal | None:
    line = lines.get(key)
    return line.value if line else None


def allowed_gap(lines: Lines, keys: tuple[str, ...], scale: Decimal) -> Decimal:
    """Three times the unit the filer rounded to, plus a tenth of a percent of `scale`."""
    rounding = max((lines[key].rounding_inr() for key in keys if key in lines), default=Decimal(0))
    return rounding * 6 + abs(scale) * LEEWAY_RATIO


def _skipped(name: str, needs: str) -> TieOut:
    return TieOut(name, SKIPPED, f"Not checked: {needs} was not filed.")


def _compare(name: str, expected: Decimal, filed: Decimal, allowed: Decimal) -> TieOut:
    gap = abs(expected - filed)
    detail = (
        f"The parts come to {fmt.inr(expected)}; the filing states {fmt.inr(filed)}. "
        f"The difference is {fmt.inr(gap)} and the allowed difference is {fmt.inr(allowed)}."
    )
    return TieOut(name, PASS if gap <= allowed else FAIL, detail)


def check_required(missing: list[str]) -> TieOut:
    if missing:
        return TieOut(CHECK_REQUIRED, FAIL, "Missing: " + ", ".join(missing) + ".")
    return TieOut(CHECK_REQUIRED, PASS, "Every required figure was found in the filing.")


def check_units(lines: Lines) -> TieOut:
    income = _value(lines, "total_income")
    if income is None:
        return _skipped(CHECK_UNITS, "total income")
    if income == 0 or MIN_INCOME <= income <= MAX_INCOME:
        return TieOut(
            CHECK_UNITS,
            PASS,
            f"Total income of {fmt.inr(income)} is in the range of a listed company.",
        )
    return TieOut(
        CHECK_UNITS,
        FAIL,
        f"Total income of {fmt.inr(income)} for a whole quarter is outside Rs 1 lakh to Rs 10 lakh crore, "
        "so the filing may be in a different unit. QuantOS did not guess.",
    )


def check_profit(lines: Lines) -> TieOut:
    income, expenses = _value(lines, "total_income"), _value(lines, "expenses")
    filed = _value(lines, "profit_before_tax")
    if income is None or expenses is None or filed is None:
        return _skipped(CHECK_PROFIT, "total income, expenses or profit before tax")
    expected = income - expenses + (_value(lines, "exceptional_items") or Decimal(0))
    keys = ("total_income", "expenses", "profit_before_tax")
    return _compare(CHECK_PROFIT, expected, filed, allowed_gap(lines, keys, income))


def check_tax(lines: Lines) -> TieOut:
    before, tax = _value(lines, "profit_before_tax"), _value(lines, "tax_expense")
    filed = _value(lines, "profit_for_period")
    if before is None or tax is None or filed is None:
        return _skipped(CHECK_TAX, "profit before tax, tax or profit for the period")
    extras = ("discontinued_after_tax", "associates_share", "regulatory_movement")
    expected = before - tax + sum((_value(lines, key) or Decimal(0) for key in extras), Decimal(0))
    keys = ("profit_before_tax", "tax_expense", "profit_for_period", *extras)
    return _compare(CHECK_TAX, expected, filed, allowed_gap(lines, keys, before))


def check_owners(lines: Lines) -> TieOut:
    owners, minority = _value(lines, "owners_profit"), _value(lines, "minority_profit")
    filed = _value(lines, "profit_for_period")
    if owners is None or minority is None or filed is None:
        return _skipped(CHECK_OWNERS, "the owners' or the minority share of profit")
    keys = ("owners_profit", "minority_profit", "profit_for_period")
    return _compare(CHECK_OWNERS, owners + minority, filed, allowed_gap(lines, keys, filed))


def check_eps(lines: Lines, shares: int | None) -> TieOut:
    eps, profit = (
        _value(lines, "eps"),
        _value(lines, "owners_profit") or _value(lines, "profit_for_period"),
    )
    if eps is None or profit is None or shares is None:
        return _skipped(CHECK_EPS, "earnings per share, profit or the share count")
    implied = eps * shares
    allowed = shares * EPS_ROUNDING + abs(profit) * EPS_BAND
    same_sign = (implied >= 0) == (profit >= 0) or abs(profit) <= allowed
    ok = abs(implied - profit) <= allowed and same_sign
    detail = (
        f"Earnings per share of {fmt.per_share(eps)} on {shares:,} shares gives {fmt.inr(implied)}; "
        f"profit is {fmt.inr(profit)}. Share counts move during a quarter, so up to half of profit is allowed."
    )
    return TieOut(CHECK_EPS, PASS if ok else FAIL, detail)


def check_listing(
    declared_ends: set[date], nature: str | None, wanted: tuple[date, bool]
) -> TieOut:
    period_end, consolidated = wanted
    problems = []
    if declared_ends and period_end not in declared_ends:
        problems.append("the filing's own period end differs from NSE's listing")
    if nature is not None and (nature.strip().lower() == "consolidated") != consolidated:
        problems.append(
            f"the filing says it is {nature.strip().lower()} but NSE lists it differently"
        )
    if problems:
        return TieOut(CHECK_LISTING, FAIL, "; ".join(problems).capitalize() + ".")
    return TieOut(
        CHECK_LISTING,
        PASS,
        "The filing's own period end and consolidated or standalone label match NSE's listing.",
    )


def check_balance(lines: Lines) -> TieOut:
    assets, equity = _value(lines, "total_assets"), _value(lines, "equity_total")
    liabilities = _value(lines, "liabilities")
    if assets is None or equity is None or liabilities is None:
        return _skipped(CHECK_BALANCE, "total assets, equity or liabilities")
    keys = ("total_assets", "equity_total", "liabilities")
    return _compare(CHECK_BALANCE, equity + liabilities, assets, allowed_gap(lines, keys, assets))


def check_balance_signs(lines: Lines) -> TieOut:
    names = ("borrowings_current", "borrowings_noncurrent", "cash_and_equivalents")
    negative = [key for key in names if (_value(lines, key) or Decimal(0)) < 0]
    if negative:
        return TieOut(
            CHECK_SIGNS, FAIL, "These are filed as negative amounts: " + ", ".join(negative) + "."
        )
    return TieOut(CHECK_SIGNS, PASS, "Borrowings and cash are zero or more.")
