"""Builders shared by the filings tests. This module holds no tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from quant_system.shariah.filings.models import ResultRow

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "shariah_filings"
TCS_FIXTURE = FIXTURE_DIR / "tcs_2024-09-30_consolidated_trimmed.xml"
TCS_URL = "https://nsearchives.nseindia.com/corporate/xbrl/INDAS_112733_1265368_10102024065944.xml"
FETCHED_AT = "2026-10-07T10:00:00Z"

NAMESPACES = (
    'xmlns:xbrli="http://www.xbrl.org/2003/instance" '
    'xmlns:link="http://www.xbrl.org/2003/linkbase" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" '
    'xmlns:iso4217="http://www.xbrl.org/2003/iso4217" '
    'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
    'xmlns:in-bse-fin="http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"'
)
UNITS = (
    '<xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>'
    '<xbrli:unit id="USD"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
    '<xbrli:unit id="INRPerShare"><xbrli:divide><xbrli:unitNumerator>'
    "<xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unitNumerator><xbrli:unitDenominator>"
    "<xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>"
)

BALANCE_SHEET = {
    "Assets": "1611240000000.00",
    "CurrentAssets": "1269400000000.00",
    "NoncurrentAssets": "341840000000.00",
    "BorrowingsCurrent": "0.00",
    "BorrowingsNoncurrent": "0.00",
    "CashAndCashEquivalents": "81550000000.00",
    "BankBalanceOtherThanCashAndCashEquivalents": "85780000000.00",
    "CurrentInvestments": "357920000000.00",
    "NoncurrentInvestments": "2890000000.00",
    "TradeReceivablesCurrent": "577100000000.00",
    "TradeReceivablesNoncurrent": "1480000000.00",
}
YEAR_TO_DATE = {
    "RevenueFromOperations": "1268720000000.00",
    "OtherIncome": "16910000000.00",
    "FinanceCosts": "3350000000.00",
    "AdjustmentsForInterestIncome": "15860000000.00",
    "PaidUpValueOfEquityShareCapital": "3620000000.00",
    "FaceValueOfEquityShareCapital": "1",
}
QUARTER = {
    "RevenueFromOperations": "642590000000.00",
    "OtherIncome": "7290000000.00",
    "FinanceCosts": "1620000000.00",
    "PaidUpValueOfEquityShareCapital": "3620000000.00",
    "FaceValueOfEquityShareCapital": "1",
}


def fact(tag: str, context: str, value: str, unit: str | None = None) -> str:
    unit = unit or ("INRPerShare" if tag.startswith("FaceValue") else "INR")
    return (
        f'<in-bse-fin:{tag} contextRef="{context}" unitRef="{unit}" decimals="-7">'
        f"{value}</in-bse-fin:{tag}>"
    )


def _context(ident: str, start: date | None, end: date, dimension: bool = False) -> str:
    period = (
        f"<xbrli:instant>{end}</xbrli:instant>"
        if start is None
        else f"<xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate>"
    )
    scenario = (
        '<xbrli:scenario><xbrldi:explicitMember dimension="in-bse-fin:SegmentAxis">'
        "in-bse-fin:OneMember</xbrldi:explicitMember></xbrli:scenario>"
        if dimension
        else ""
    )
    return (
        f'<xbrli:context id="{ident}"><xbrli:entity><xbrli:identifier '
        f'scheme="http://www.nseindia.com/NSESymbol">TST</xbrli:identifier></xbrli:entity>'
        f"<xbrli:period>{period}</xbrli:period>{scenario}</xbrli:context>"
    )


def _merged(base: Mapping[str, str], changes: Mapping[str, str | None] | None) -> dict[str, str]:
    merged: dict[str, str | None] = dict(base)
    merged.update(changes or {})
    return {tag: value for tag, value in merged.items() if value is not None}


def make_filing(**options: Any) -> bytes:
    """A small Ind-AS filing. Context ids are deliberately not the ones NSE uses.

    options: `period_end`, `ytd_start`, `quarter_start` (dates); `balance`, `ytd`, `quarter`
    (tag -> value, None removes the tag); `nse_quirk` declares the year-to-date context with the
    quarter's dates (the real filings do this) and keeps the true start only in the filing's own
    reporting-period fact; `schema` sets the entry point; `nature` sets the standalone/consolidated
    fact; `with_balance_sheet=False` leaves the balance sheet out (a June or December quarter);
    `segments` lists business segment names filed under their own dimension contexts.
    """
    period_end: date = options.get("period_end", date(2024, 9, 30))
    ytd_start: date = options.get("ytd_start", date(2024, 4, 1))
    quarter_start: date = options.get("quarter_start", date(2024, 7, 1))
    ytd_declared = quarter_start if options.get("nse_quirk", False) else ytd_start
    schema = options.get("schema", "Ind-AS_entry_point_2020-03-31.xsd")
    nature = options.get("nature", "Consolidated")
    segments: list[str] = list(options.get("segments", ()))
    parts = [
        f'<?xml version="1.0" encoding="UTF-8"?><xbrli:xbrl {NAMESPACES}>',
        f'<link:schemaRef xlink:type="simple" xlink:href="{schema}"/>',
        _context("Zq", quarter_start, period_end),
        _context("Zy", ytd_declared, period_end),
        _context("Zb", None, period_end),
        _context("Zseg", quarter_start, period_end, dimension=True),
        UNITS,
    ]
    for ctx, start in (("Zq", quarter_start), ("Zy", ytd_start)):
        parts.append(
            f'<in-bse-fin:DateOfStartOfReportingPeriod contextRef="{ctx}">{start}'
            "</in-bse-fin:DateOfStartOfReportingPeriod>"
            f'<in-bse-fin:DateOfEndOfReportingPeriod contextRef="{ctx}">{period_end}'
            "</in-bse-fin:DateOfEndOfReportingPeriod>"
            f'<in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="{ctx}">'
            f"{nature}</in-bse-fin:NatureOfReportStandaloneConsolidated>"
        )
    if options.get("with_balance_sheet", True):
        parts += [
            fact(t, "Zb", v) for t, v in _merged(BALANCE_SHEET, options.get("balance")).items()
        ]
    parts += [fact(t, "Zy", v) for t, v in _merged(YEAR_TO_DATE, options.get("ytd")).items()]
    parts += [fact(t, "Zq", v) for t, v in _merged(QUARTER, options.get("quarter")).items()]
    parts.append(fact("RevenueFromOperations", "Zseg", "999999999999.00"))
    for number, name in enumerate(segments):
        parts.append(_context(f"Zs{number}", quarter_start, period_end, dimension=True))
        parts.append(
            f'<in-bse-fin:DescriptionOfReportableSegment contextRef="Zs{number}">'
            f"{name}</in-bse-fin:DescriptionOfReportableSegment>"
        )
    parts.append("</xbrli:xbrl>")
    return "".join(parts).encode("utf-8")


def make_bank_filing() -> bytes:
    """A bank-style filing: its own entry point, and no current/non-current split."""
    return make_filing(
        schema="banking_entry_point_2019-09-30.xsd",
        balance={
            "CurrentAssets": None,
            "NoncurrentAssets": None,
            "Advances": "5000000000000.00",
            "Deposits": "6000000000000.00",
        },
        ytd={"RevenueFromOperations": None, "InterestEarned": "900000000000.00"},
    )


def make_row(**changes: object) -> ResultRow:
    fields: dict[str, object] = {
        "symbol": "TCS",
        "company_name": "Tata Consultancy Services Limited",
        "isin": "INE467B01029",
        "period_end": date(2024, 9, 30),
        "relating_to": "Second Quarter",
        "period_kind": "Quarterly",
        "consolidated": True,
        "audited": True,
        "ind_as": True,
        "lender_flag": "N",
        "filed_on": date(2024, 10, 10),
        "xbrl_url": TCS_URL,
        "detail_url": None,
    }
    fields.update(changes)
    return ResultRow(**fields)  # type: ignore[arg-type]
