"""Turn one filing into figures, each with the tag it came from, and check it against itself.

A figure that is not filed is left out. Nothing is estimated, inferred from another line, or carried over
from an older filing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from quant_system.shariah.filings.models import (
    FigureLine,
    FilingFigures,
    FilingProof,
    ReadStatus,
    ResultRow,
    TieOutCheck,
    clean_text,
    shares_from,
)
from quant_system.shariah.filings.xbrl import Period, XbrlDocument, XbrlError, parse_xbrl

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
TOLERANCE_RATIO = Decimal("0.005")
TOLERANCE_FLOOR = Decimal(10_000_000)
MIN_TOTAL_ASSETS = Decimal(10_000_000)
MAX_TOTAL_ASSETS = Decimal(10) ** 15
MAX_SEGMENTS = 20
MAX_SEGMENT_CHARS = 120
LENDER_TAGS = frozenset({"Advances", "Deposits", "InterestEarned", "NameOfBank"})

CHECK_REQUIRED = "All required figures are present"
CHECK_UNITS = "Amounts are in rupees"
CHECK_ASSETS = "Assets add up"
CHECK_SHARES = "Share count is a whole number"
CHECK_SIGNS = "Revenue and other income are not negative"
CHECK_LISTING = "Filing agrees with NSE's listing"

NOTES = {
    "BANK": "This company is a bank. Banks file their results in a layout QuantOS does not read, "
    "so no balance-sheet figures were taken from this filing.",
    "NBFC": "This company is a lender (a non-bank finance company). Lenders file their results in a "
    "layout QuantOS does not read, so no balance-sheet figures were taken from this filing.",
    "NON_IND_AS": "This company files its results in the older Indian accounting format, "
    "which QuantOS does not read.",
    "OTHER": "This company files its results in a layout QuantOS does not read.",
}


@dataclass(frozen=True)
class LineSpec:
    key: str
    tag: str
    label: str
    where: str  # "balance" (at the balance-sheet date), "profit" (the profit period) or "capital"
    required: bool = False


SPECS = (
    LineSpec("total_assets", "Assets", "Total assets", "balance", True),
    LineSpec("current_assets", "CurrentAssets", "Current assets", "balance", True),
    LineSpec("noncurrent_assets", "NoncurrentAssets", "Non-current assets", "balance", True),
    LineSpec(
        "held_for_sale_assets",
        "NoncurrentAssetsClassifiedAsHeldForSale",
        "Assets held for sale",
        "balance",
    ),
    LineSpec(
        "regulatory_deferral_assets",
        "RegulatoryDeferralAccountDebitBalancesAndRelatedDeferredTaxAssets",
        "Regulatory deferral account debit balances",
        "balance",
    ),
    LineSpec("borrowings_current", "BorrowingsCurrent", "Borrowings, current", "balance"),
    LineSpec("borrowings_noncurrent", "BorrowingsNoncurrent", "Borrowings, non-current", "balance"),
    LineSpec(
        "cash_and_equivalents",
        "CashAndCashEquivalents",
        "Cash and cash equivalents",
        "balance",
        True,
    ),
    LineSpec(
        "other_bank_balances",
        "BankBalanceOtherThanCashAndCashEquivalents",
        "Other bank balances",
        "balance",
    ),
    LineSpec("current_investments", "CurrentInvestments", "Investments, current", "balance"),
    LineSpec(
        "noncurrent_investments", "NoncurrentInvestments", "Investments, non-current", "balance"
    ),
    LineSpec(
        "trade_receivables_current",
        "TradeReceivablesCurrent",
        "Trade receivables, current",
        "balance",
    ),
    LineSpec(
        "trade_receivables_noncurrent",
        "TradeReceivablesNoncurrent",
        "Trade receivables, non-current",
        "balance",
    ),
    LineSpec(
        "revenue_from_operations",
        "RevenueFromOperations",
        "Revenue from operations",
        "profit",
        True,
    ),
    LineSpec("other_income", "OtherIncome", "Other income", "profit", True),
    LineSpec("finance_costs", "FinanceCosts", "Finance costs", "profit"),
    LineSpec(
        "interest_income_adjustment",
        "AdjustmentsForInterestIncome",
        "Interest income (adjusted in the cash flow statement)",
        "profit",
    ),
    LineSpec(
        "paid_up_equity_capital",
        "PaidUpValueOfEquityShareCapital",
        "Paid-up equity share capital",
        "capital",
        True,
    ),
    LineSpec(
        "face_value", "FaceValueOfEquityShareCapital", "Face value per share", "capital", True
    ),
)
ANY_OF = (
    ("trade receivables", ("trade_receivables_current", "trade_receivables_noncurrent")),
    ("borrowings", ("borrowings_current", "borrowings_noncurrent")),
)


def format_date(when: date) -> str:
    return f"{when.day} {MONTHS[when.month - 1]} {when.year}"


def period_label(period: Period) -> str:
    """Words for a stretch of time, e.g. "Six months ended 30 Sep 2024"."""
    if period.start is None:
        return f"Balance sheet at {format_date(period.end)}"
    months = round(((period.end - period.start).days + 1) / 30.4375)
    words = {1: "One month", 2: "Two months", 3: "Three months", 6: "Six months", 9: "Nine months"}
    head = "Year" if months == 12 else words.get(months, f"{months} months")
    return f"{head} ended {format_date(period.end)}"


def clean_segment_names(names: list[str]) -> tuple[str, ...]:
    """Business segment names are text from outside the app: bounded in count and length, no markup."""
    cleaned: list[str] = []
    for name in names:
        text = clean_text(name, MAX_SEGMENT_CHARS)
        if text and text not in cleaned:
            cleaned.append(text)
    return tuple(cleaned[:MAX_SEGMENTS])


def _proof(row: ResultRow, sha256: str, fetched_at: str, label: str) -> FilingProof:
    return FilingProof(
        source_url=row.xbrl_url,
        detail_url=row.detail_url,
        period_end=row.period_end,
        period_label=label,
        filed_on=row.filed_on,
        consolidated=row.consolidated,
        audited=row.audited,
        ind_as=row.ind_as,
        sha256=sha256,
        fetched_at=fetched_at,
    )


def _result(row: ResultRow, proof: FilingProof, status: ReadStatus, note: str) -> FilingFigures:
    """Figures with nothing read yet; callers add what they found with `replace`."""
    return FilingFigures(
        symbol=row.symbol,
        isin=row.isin,
        company_name=row.company_name,
        proof=proof,
        lines={},
        tie_out=(),
        read_status=status,
        read_note=note,
    )


def _lender_note(doc: XbrlDocument) -> str | None:
    entry = (doc.schema_ref or "").lower()
    if "bank" in entry or doc.tags & LENDER_TAGS:
        return NOTES["BANK"]
    return NOTES["NBFC"] if "nbfc" in entry else None


def _has_reading(doc: XbrlDocument, tags: tuple[str, ...], period: Period) -> bool:
    readings = [doc.read_number(tag, period) for tag in tags]
    return any(r.value is not None or r.problem is not None for r in readings)


def _profit_period(doc: XbrlDocument, end: date) -> Period | None:
    """The longest stretch ending at the balance-sheet date that carries revenue or other income."""
    tags = ("RevenueFromOperations", "OtherIncome")
    return next((p for p in doc.duration_periods(end) if _has_reading(doc, tags, p)), None)


def _periods_for(
    spec: LineSpec, doc: XbrlDocument, end: date, profit: Period | None
) -> list[Period]:
    if spec.where == "balance":
        return [Period(None, end)]
    if spec.where == "profit":
        return [profit] if profit else []
    ordered = ([profit] if profit else []) + [p for p in doc.duration_periods(end) if p != profit]
    return [*ordered, Period(None, end)]


def _read_lines(
    doc: XbrlDocument, end: date, profit: Period | None
) -> tuple[dict[str, FigureLine], dict[str, str]]:
    lines: dict[str, FigureLine] = {}
    problems: dict[str, str] = {}
    for spec in SPECS:
        for period in _periods_for(spec, doc, end, profit):
            reading = doc.read_number(spec.tag, period)
            if reading.value is not None:
                lines[spec.key] = FigureLine(
                    spec.tag, spec.label, reading.value, period_label(period), reading.decimals
                )
                problems.pop(spec.key, None)
                break
            if reading.problem is not None:
                problems.setdefault(spec.key, reading.problem)
    return lines, problems


def _missing(lines: dict[str, FigureLine], problems: dict[str, str]) -> list[str]:
    """Plain names of required figures that are absent, with the reason when one was filed badly."""
    names = []
    for spec in SPECS:
        if spec.required and spec.key not in lines:
            names.append(_with_reason(spec.label.lower(), problems.get(spec.key)))
    for name, keys in ANY_OF:
        if not any(key in lines for key in keys):
            reasons = [problems[key] for key in keys if key in problems]
            names.append(_with_reason(name, reasons[0] if reasons else None))
    return names


def _with_reason(name: str, reason: str | None) -> str:
    return f"{name} ({reason})" if reason else name


def _inr(amount: Decimal) -> str:
    return f"INR {amount:,.0f}"


def _unknown(name: str, needs: str) -> TieOutCheck:
    return TieOutCheck(name, False, f"Not checked: {needs} was not found in the filing.")


def _check_units(lines: dict[str, FigureLine]) -> TieOutCheck:
    assets = lines.get("total_assets")
    if assets is None:
        return _unknown(CHECK_UNITS, "total assets")
    total = assets.value_inr
    if MIN_TOTAL_ASSETS <= total <= MAX_TOTAL_ASSETS:
        return TieOutCheck(
            CHECK_UNITS,
            True,
            f"Every figure is filed in Indian rupees, and total assets of {_inr(total)} is in the "
            "range expected for a listed company.",
        )
    return TieOutCheck(
        CHECK_UNITS,
        False,
        f"Total assets of {_inr(total)} is outside INR 10 million to INR 1,000 trillion, so the "
        "filing may be in a different unit. QuantOS did not guess.",
    )


def _check_assets(lines: dict[str, FigureLine]) -> TieOutCheck:
    """Total assets = current + non-current, plus the two lines the layout shows apart from them."""
    keys = ("total_assets", "current_assets", "noncurrent_assets")
    if not all(key in lines for key in keys):
        return _unknown(CHECK_ASSETS, "total, current or non-current assets")
    total, current, noncurrent = (lines[key].value_inr for key in keys)
    extras = [
        lines[k] for k in ("held_for_sale_assets", "regulatory_deferral_assets") if k in lines
    ]
    parts = f"Current assets {_inr(current)} plus non-current assets {_inr(noncurrent)}"
    for extra in extras:
        parts += f" plus {extra.label.lower()} {_inr(extra.value_inr)}"
    summed = current + noncurrent + sum((extra.value_inr for extra in extras), Decimal(0))
    allowed = max(total * TOLERANCE_RATIO, TOLERANCE_FLOOR)
    gap = abs(summed - total)
    detail = (
        f"{parts} is {_inr(summed)}; total assets is {_inr(total)}. The difference is {_inr(gap)}. "
        f"The allowed difference is 0.5 percent of total assets or INR 10 million, whichever is "
        f"larger ({_inr(allowed)})."
    )
    return TieOutCheck(CHECK_ASSETS, gap <= allowed, detail)


def _check_shares(lines: dict[str, FigureLine]) -> TieOutCheck:
    if "paid_up_equity_capital" not in lines or "face_value" not in lines:
        return _unknown(CHECK_SHARES, "paid-up capital or face value")
    paid, face = lines["paid_up_equity_capital"].value_inr, lines["face_value"].value_inr
    shares = shares_from(paid, face)
    if shares is not None:
        return TieOutCheck(
            CHECK_SHARES,
            True,
            f"Paid-up capital of {_inr(paid)} divided by a face value of INR {face} per share gives "
            f"{shares:,} shares.",
        )
    reason = (
        "Paid-up capital and face value must both be above zero."
        if paid <= 0 or face <= 0
        else "Paid-up capital divided by face value does not give a whole number of shares."
    )
    return TieOutCheck(CHECK_SHARES, False, reason)


def _check_signs(lines: dict[str, FigureLine]) -> TieOutCheck:
    keys = ("revenue_from_operations", "other_income")
    if not all(key in lines for key in keys):
        return _unknown(CHECK_SIGNS, "revenue or other income")
    negative = [lines[key].label for key in keys if lines[key].value_inr < 0]
    if negative:
        return TieOutCheck(
            CHECK_SIGNS, False, f"{' and '.join(negative)} is filed as a negative amount."
        )
    return TieOutCheck(
        CHECK_SIGNS, True, "Revenue from operations and other income are zero or more."
    )


def _check_listing(doc: XbrlDocument, row: ResultRow) -> TieOutCheck:
    problems = []
    ends = doc.declared_period_ends()
    if ends and row.period_end not in ends:
        problems.append("the filing's own period end differs from NSE's listing")
    nature = doc.read_text("NatureOfReportStandaloneConsolidated")
    if nature is not None and (nature.strip().lower() == "consolidated") != row.consolidated:
        problems.append(
            "the filing says it is " + nature.strip().lower() + " but NSE lists it differently"
        )
    if problems:
        return TieOutCheck(CHECK_LISTING, False, "; ".join(problems).capitalize() + ".")
    return TieOutCheck(
        CHECK_LISTING,
        True,
        "The filing's own period end and consolidated or standalone label match NSE's listing.",
    )


def _tie_outs(
    doc: XbrlDocument, row: ResultRow, lines: dict[str, FigureLine], missing: list[str]
) -> tuple[TieOutCheck, ...]:
    required = (
        TieOutCheck(CHECK_REQUIRED, False, "Missing: " + ", ".join(missing) + ".")
        if missing
        else TieOutCheck(CHECK_REQUIRED, True, "Every required figure was found in the filing.")
    )
    return (
        required,
        _check_units(lines),
        _check_assets(lines),
        _check_shares(lines),
        _check_signs(lines),
        _check_listing(doc, row),
    )


def _read_note(missing: list[str], checks: tuple[TieOutCheck, ...]) -> tuple[ReadStatus, str]:
    if missing:
        return (
            ReadStatus.READ_PARTIAL,
            "The filing does not carry these required figures: " + ", ".join(missing) + ".",
        )
    failed = [check.name for check in checks if not check.ok]
    if failed:
        return ReadStatus.TIE_OUT_FAILED, "The filing does not agree with itself on: " + ", ".join(
            failed
        ) + "."
    return ReadStatus.READ_OK, ""


def extract_figures(data: bytes, row: ResultRow, fetched_at: str) -> FilingFigures:
    """Read one filing as fetched. Never raises on the file's content."""
    sha256 = hashlib.sha256(data).hexdigest()
    plain_end = f"Period ended {format_date(row.period_end)}"
    unread = _proof(row, sha256, fetched_at, plain_end)
    if row.format_kind != "IND_AS":
        return _result(row, unread, ReadStatus.FORMAT_NOT_READ, NOTES[row.format_kind])
    try:
        doc = parse_xbrl(data)
    except XbrlError as error:
        return _result(row, unread, ReadStatus.FORMAT_NOT_READ, f"{error} QuantOS skipped it.")
    lender = _lender_note(doc)
    if lender is not None:
        return _result(row, unread, ReadStatus.FORMAT_NOT_READ, lender)
    names = clean_segment_names(doc.read_texts("DescriptionOfReportableSegment"))
    if not doc.has_instant(row.period_end):
        note = (
            f"This filing does not carry a balance sheet for {format_date(row.period_end)}. "
            "June and December quarters usually do not."
        )
        blank = _result(row, unread, ReadStatus.NO_BALANCE_SHEET, note)
        return replace(blank, segment_names=names)
    if not ({"CurrentAssets", "NoncurrentAssets"} & doc.tags):
        return _result(row, unread, ReadStatus.FORMAT_NOT_READ, NOTES["OTHER"])
    profit = _profit_period(doc, row.period_end)
    lines, problems = _read_lines(doc, row.period_end, profit)
    missing = _missing(lines, problems)
    checks = _tie_outs(doc, row, lines, missing)
    status, note = _read_note(missing, checks)
    label = period_label(profit) if profit else plain_end
    proof = _proof(row, sha256, fetched_at, label)
    result = _result(row, proof, status, note)
    return replace(result, lines=lines, tie_out=checks, segment_names=names)
