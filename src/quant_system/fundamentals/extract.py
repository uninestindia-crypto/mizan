"""Turn one quarterly results filing into figures, each with the tag it came from, and check it against itself.

A figure that is not filed is left out. Nothing is estimated, inferred from another line, or carried over from an
older filing. Banks, lenders and companies in the older accounting format are reported as not read.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import date
from typing import Final

from quant_system.fundamentals import tieouts
from quant_system.fundamentals.lines import BALANCE_SPECS, QUARTER_SPECS, Spec
from quant_system.fundamentals.models import (
    REQUIRED_LINES,
    BalanceFigures,
    Figure,
    QuarterFigures,
    ReadStatus,
    TieOut,
)
from quant_system.shariah.filings.extract import LENDER_TAGS, NOTES, period_label
from quant_system.shariah.filings.models import ResultRow
from quant_system.shariah.filings.xbrl import Period, XbrlDocument, XbrlError, parse_xbrl

MIN_QUARTER_DAYS: Final = 80
MAX_QUARTER_DAYS: Final = 100
NORMAL_QUARTER_DAYS: Final = 91
NOT_A_QUARTER_NOTE: Final = (
    "This filing does not cover a single quarter (it covers a longer stretch), "
    "so QuantOS did not use it."
)
NO_BALANCE_NOTE: Final = "This filing carries no balance sheet."
_FALLBACK_OWNERS: Final = "profit_for_period"


def _lender_note(doc: XbrlDocument) -> str | None:
    entry = (doc.schema_ref or "").lower()
    if "bank" in entry or doc.tags & LENDER_TAGS:
        return NOTES["BANK"]
    return NOTES["NBFC"] if "nbfc" in entry else None


def _blank(row: ResultRow, sha256: str, fetched_at: str) -> QuarterFigures:
    return QuarterFigures(
        symbol=row.symbol,
        isin=row.isin,
        company_name=row.company_name,
        period_end=row.period_end,
        period_start=None,
        period_label=f"Period ended {row.period_end:%d %b %Y}".replace(" 0", " "),
        filed_on=row.filed_on,
        consolidated=row.consolidated,
        audited=row.audited,
        source_url=row.xbrl_url,
        sha256=sha256,
        fetched_at=fetched_at,
        status=ReadStatus.FORMAT_NOT_READ,
    )


def _days(period: Period) -> int:
    assert period.start is not None
    return (period.end - period.start).days + 1


def _quarter_period(doc: XbrlDocument, end: date) -> Period | None:
    """The three-month stretch ending on `end`. Year-to-date contexts in the same file are never used."""
    quarters = [
        p
        for p in doc.duration_periods(end)
        if p.start is not None and MIN_QUARTER_DAYS <= _days(p) <= MAX_QUARTER_DAYS
    ]
    return min(quarters, key=lambda p: abs(_days(p) - NORMAL_QUARTER_DAYS), default=None)


def _read_spec(doc: XbrlDocument, spec: Spec, period: Period) -> Figure | None:
    for tag in spec.tags:
        reading = doc.read_number(tag, period)
        if reading.value is not None:
            return Figure(tag, reading.value, reading.decimals)
    return None


def _read_lines(doc: XbrlDocument, specs: tuple[Spec, ...], period: Period) -> dict[str, Figure]:
    found = {spec.key: _read_spec(doc, spec, period) for spec in specs}
    return {key: figure for key, figure in found.items() if figure is not None}


def _problem(doc: XbrlDocument, spec: Spec, period: Period) -> str | None:
    for tag in spec.tags:
        problem = doc.read_number(tag, period).problem
        if problem:
            return problem
    return None


def _missing(doc: XbrlDocument, lines: dict[str, Figure], period: Period) -> list[str]:
    names = []
    for spec in QUARTER_SPECS:
        if spec.key in REQUIRED_LINES and spec.key not in lines:
            reason = _problem(doc, spec, period)
            names.append(f"{spec.label.lower()} ({reason})" if reason else spec.label.lower())
    return names


def _with_owners_fallback(lines: dict[str, Figure], consolidated: bool) -> dict[str, Figure]:
    """A standalone filing has no owners-and-minority split: its profit for the period is the owners' profit."""
    if "owners_profit" in lines or consolidated or _FALLBACK_OWNERS not in lines:
        return lines
    return {**lines, "owners_profit": lines[_FALLBACK_OWNERS]}


def _with_owners_equity(lines: dict[str, Figure], consolidated: bool) -> dict[str, Figure]:
    """A standalone company has no minority, so its total equity is its owners' equity."""
    if "equity_owners" in lines or consolidated or "equity_total" not in lines:
        return lines
    return {**lines, "equity_owners": lines["equity_total"]}


def read_balance(doc: XbrlDocument, end: date, consolidated: bool) -> BalanceFigures | None:
    """The balance sheet at `end`, or None when the filing carries none."""
    if not doc.has_instant(end):
        return None
    lines = _read_lines(doc, BALANCE_SPECS, Period(None, end))
    if "total_assets" not in lines:
        return None
    lines = _with_owners_equity(lines, consolidated)
    return BalanceFigures(
        end, lines, (tieouts.check_balance(lines), tieouts.check_balance_signs(lines))
    )


def _checks(
    doc: XbrlDocument, row: ResultRow, lines: dict[str, Figure], missing: list[str]
) -> tuple[TieOut, ...]:
    shares = _shares(lines)
    return (
        tieouts.check_required(missing),
        tieouts.check_units(lines),
        tieouts.check_profit(lines),
        tieouts.check_tax(lines),
        tieouts.check_owners(lines),
        tieouts.check_eps(lines, shares),
        tieouts.check_listing(
            doc.declared_period_ends(),
            doc.read_text("NatureOfReportStandaloneConsolidated"),
            (row.period_end, row.consolidated),
        ),
    )


def _shares(lines: dict[str, Figure]) -> int | None:
    paid, face = lines.get("paid_up_capital"), lines.get("face_value")
    if (
        paid is None
        or face is None
        or paid.value <= 0
        or face.value <= 0
        or paid.value % face.value != 0
    ):
        return None
    return int(paid.value // face.value)


def _status(missing: list[str], checks: tuple[TieOut, ...]) -> tuple[ReadStatus, str]:
    if missing:
        return (
            ReadStatus.READ_PARTIAL,
            "The filing does not carry these required figures: " + ", ".join(missing) + ".",
        )
    failed = [check.name for check in checks if not check.ok]
    if failed:
        return ReadStatus.TIE_OUT_FAILED, "The filing does not agree with itself on: " + "; ".join(
            failed
        ) + "."
    return ReadStatus.READ_OK, ""


def extract_quarter(data: bytes, row: ResultRow, fetched_at: str) -> QuarterFigures:
    """Read one filing as fetched. Never raises on the file's content."""
    blank = _blank(row, hashlib.sha256(data).hexdigest(), fetched_at)
    if row.format_kind != "IND_AS":
        return replace(blank, note=NOTES[row.format_kind])
    try:
        doc = parse_xbrl(data)
    except XbrlError as error:
        return replace(blank, note=f"{error} QuantOS skipped it.")
    lender = _lender_note(doc)
    if lender is not None:
        return replace(blank, note=lender)
    period = _quarter_period(doc, row.period_end)
    if period is None:
        return replace(blank, status=ReadStatus.NOT_A_QUARTER, note=NOT_A_QUARTER_NOTE)
    return _read_quarter(doc, row, replace(blank, period_start=period.start), period)


def _read_quarter(
    doc: XbrlDocument, row: ResultRow, blank: QuarterFigures, period: Period
) -> QuarterFigures:
    lines = _with_owners_fallback(_read_lines(doc, QUARTER_SPECS, period), row.consolidated)
    missing = _missing(doc, lines, period)
    checks = _checks(doc, row, lines, missing)
    status, note = _status(missing, checks)
    return replace(
        blank,
        period_label=period_label(period),
        status=status,
        note=note,
        lines=lines,
        tie_out=checks,
        balance=read_balance(doc, row.period_end, row.consolidated),
    )
