"""When a filing earns VERIFIED_FILING, and when it is stale or not screened."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from test_filings_builders import FETCHED_AT, TCS_FIXTURE, make_filing, make_row

from quant_system.shariah.filings.extract import extract_figures
from quant_system.shariah.filings.models import FilingFigures, TieOutCheck
from quant_system.shariah.filings.status import data_status_for

FILED_PERIOD_END = date(2024, 9, 30)


def real() -> FilingFigures:
    return extract_figures(TCS_FIXTURE.read_bytes(), make_row(), FETCHED_AT)


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2024, 10, 15), "VERIFIED_FILING"),
        (date(2026, 3, 30), "VERIFIED_FILING"),
        (date(2026, 3, 31), "VERIFIED_FILING"),
        (date(2026, 4, 1), "STALE"),
        (date(2026, 10, 7), "STALE"),
    ],
)
def test_a_clean_filing_is_verified_until_its_balance_sheet_is_over_18_months_old(
    today: date, expected: str
) -> None:
    assert data_status_for(real(), today) == expected


def test_status_values_are_plain_strings() -> None:
    assert data_status_for(real(), date(2024, 10, 15)) == "VERIFIED_FILING"
    assert isinstance(data_status_for(None, date(2024, 10, 15)), str)


def test_the_18_month_rule_counts_calendar_months_across_a_short_february() -> None:
    figures = extract_figures(
        make_filing(period_end=date(2025, 8, 31)),
        make_row(period_end=date(2025, 8, 31)),
        FETCHED_AT,
    )
    assert data_status_for(figures, date(2027, 2, 28)) == "VERIFIED_FILING"
    assert data_status_for(figures, date(2027, 3, 1)) == "STALE"


def test_no_filing_is_not_screened() -> None:
    assert data_status_for(None, date(2024, 10, 15)) == "NOT_SCREENED"


@pytest.mark.parametrize(
    "raw",
    [
        make_filing(balance={"CashAndCashEquivalents": None}),
        make_filing(balance={"Assets": "1811240000000.00"}),
        make_filing(with_balance_sheet=False),
        b"not xml",
    ],
    ids=["partial", "tie-out-failed", "no-balance-sheet", "unreadable"],
)
def test_anything_unreadable_is_not_screened(raw: bytes) -> None:
    figures = extract_figures(raw, make_row(), FETCHED_AT)
    assert data_status_for(figures, date(2024, 10, 15)) == "NOT_SCREENED"


def test_a_read_ok_filing_without_a_recorded_hash_is_not_verified() -> None:
    figures = real()
    unhashed = replace(figures, proof=replace(figures.proof, sha256=""))
    assert data_status_for(unhashed, date(2024, 10, 15)) == "NOT_SCREENED"


def test_a_read_ok_filing_without_a_source_link_is_not_verified() -> None:
    figures = real()
    unlinked = replace(figures, proof=replace(figures.proof, source_url=""))
    assert data_status_for(unlinked, date(2024, 10, 15)) == "NOT_SCREENED"


def test_a_failing_tie_out_blocks_verification_even_if_the_status_says_ok() -> None:
    figures = real()
    tampered = replace(figures, tie_out=(*figures.tie_out, TieOutCheck("x", False, "does not tie")))
    assert data_status_for(tampered, date(2024, 10, 15)) == "NOT_SCREENED"
