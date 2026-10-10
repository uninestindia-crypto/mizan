"""Reading one real quarterly filing: the tags it is read from, the checks it must pass, and what is refused."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from quant_system.fundamentals.extract import extract_quarter
from quant_system.fundamentals.models import QuarterFigures, ReadStatus
from tests.fundamentals.support import (
    fixture_bytes,
    fixture_text,
    in_crores,
    listing_row,
    with_value,
    without_fact,
)

STAMP = "2026-10-07T00:00:00Z"
TCS_SEP = "tcs_2024-09-30_consolidated_trimmed.xml"
TCS_DEC = "tcs_2024-12-31_consolidated_trimmed.xml"
STEEL = "tatasteel_2024-09-30_consolidated_trimmed.xml"


def _read(name: str, **row: object) -> QuarterFigures:
    return extract_quarter(fixture_bytes(name), listing_row(**row), STAMP)  # type: ignore[arg-type]


def _read_text(text: str, **row: object) -> QuarterFigures:
    return extract_quarter(text.encode("utf-8"), listing_row(**row), STAMP)  # type: ignore[arg-type]


def _failed(result: QuarterFigures) -> list[str]:
    return [check.name for check in result.tie_out if not check.ok]


def test_a_real_tcs_quarter_is_read_from_the_tags_the_filing_uses() -> None:
    result = _read(TCS_SEP)
    assert result.status is ReadStatus.READ_OK and result.usable
    assert result.period_start == date(2024, 7, 1) and result.period_end == date(2024, 9, 30)
    assert result.period_label == "Three months ended 30 Sep 2024"
    assert result.lines["revenue_from_operations"].tag == "RevenueFromOperations"
    assert result.value("revenue_from_operations") == Decimal("642590000000.00")
    assert result.value("profit_before_tax") == Decimal("160320000000.00")
    assert result.lines["owners_profit"].tag == "ProfitOrLossAttributableToOwnersOfParent"
    assert result.value("owners_profit") == Decimal("119090000000.00")
    assert result.value("eps") == Decimal("32.92")
    assert (
        result.lines["eps"].tag
        == "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
    )


def test_the_quarter_is_taken_not_the_year_to_date_that_sits_in_the_same_file() -> None:
    result = _read(TCS_SEP)
    assert result.value("revenue_from_operations") != Decimal("1268720000000.00")
    assert result.value("profit_for_period") == Decimal("119550000000.00")


def test_the_proof_of_the_filing_travels_with_the_figures() -> None:
    data = fixture_bytes(TCS_SEP)
    result = extract_quarter(data, listing_row(), STAMP)
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.source_url.endswith(".xml") and result.filed_on == date(2024, 10, 10)
    assert result.consolidated and result.fetched_at == STAMP


def test_every_identity_in_the_filing_ties_out_on_the_real_tags() -> None:
    result = _read(TCS_SEP)
    assert [c.outcome for c in result.tie_out] == ["PASS"] * len(result.tie_out)
    names = " ".join(check.name for check in result.tie_out)
    assert "Total income less expenses" in names and "Earnings per share" in names


def test_the_balance_sheet_in_the_same_filing_is_read_with_its_own_tags() -> None:
    sheet = _read(TCS_SEP).balance
    assert sheet is not None and sheet.usable and sheet.as_of == date(2024, 9, 30)
    assert sheet.value("total_assets") == Decimal("1611240000000.00")
    assert sheet.lines["equity_owners"].tag == "EquityAttributableToOwnersOfParent"
    assert sheet.value("equity_owners") == Decimal("1014950000000.00")
    assert sheet.value("borrowings_current") == 0 and sheet.value("borrowings_noncurrent") == 0


def test_a_december_filing_has_the_quarter_and_no_balance_sheet() -> None:
    result = _read(TCS_DEC, period_end=date(2024, 12, 31), filed_on=date(2025, 1, 9))
    assert result.usable and result.balance is None
    assert result.period_start == date(2024, 10, 1) and result.value("eps") == Decimal("34.21")
    assert result.value("revenue_from_operations") == Decimal("639730000000.00")


def test_a_company_with_debt_a_minority_and_exceptional_items_still_ties_out() -> None:
    result = _read(STEEL, symbol="TATASTEEL")
    assert result.usable
    assert result.value("exceptional_items") == Decimal("180900000.00")
    assert result.value("associates_share") == Decimal("-254800000.00")
    assert result.value("minority_profit") == Decimal("-746100000.00")
    assert result.balance is not None and result.balance.usable
    assert result.balance.value("borrowings_noncurrent") == Decimal("713474900000.00")
    assert result.balance.value("borrowings_current") == Decimal("280442700000.00")


def test_figures_that_do_not_add_up_mark_the_quarter_and_exclude_it() -> None:
    wrong = with_value(fixture_text(TCS_SEP), "ProfitBeforeTax", "OneD", "170320000000.00")
    result = _read_text(wrong)
    assert result.status is ReadStatus.TIE_OUT_FAILED and not result.usable
    assert "Total income less expenses equals profit before tax" in _failed(result)
    assert "do not add up" in result.note.lower() or "agree" in result.note.lower()


def test_a_filing_in_the_wrong_unit_is_caught_by_the_size_check() -> None:
    result = _read_text(in_crores(fixture_text(TCS_SEP)))
    assert result.status is ReadStatus.TIE_OUT_FAILED
    assert _failed(result) == ["Amounts are in rupees"]
    assert "different unit" in result.tie_out[1].detail


def test_profit_in_the_wrong_unit_beside_the_right_share_count_is_caught_by_the_per_share_check() -> (
    None
):
    text = with_value(
        fixture_text(TCS_SEP), "ProfitOrLossAttributableToOwnersOfParent", "OneD", "11909.00"
    )
    result = _read_text(text)
    assert result.status is ReadStatus.TIE_OUT_FAILED
    assert "Earnings per share agrees with profit and share count" in _failed(result)


def test_a_required_figure_that_is_missing_is_reported_not_made_up() -> None:
    gone = without_fact(fixture_text(TCS_SEP), "ProfitLossForPeriod", "OneD")
    result = _read_text(gone)
    assert result.status is ReadStatus.READ_PARTIAL and not result.usable
    assert "profit for the period" in result.note.lower()


def test_an_amount_filed_in_another_unit_is_not_read() -> None:
    text = fixture_text(TCS_SEP).replace(
        '<in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="INR"',
        '<in-bse-fin:RevenueFromOperations contextRef="OneD" unitRef="pure"',
    )
    result = _read_text(text)
    assert (
        result.status is ReadStatus.READ_PARTIAL
        and "revenue from operations" in result.note.lower()
    )


def test_a_listing_that_disagrees_with_the_file_about_the_basis_fails_the_check() -> None:
    result = _read(TCS_SEP, consolidated=False)
    assert result.status is ReadStatus.TIE_OUT_FAILED
    assert _failed(result) == ["Filing agrees with NSE's listing"]


def test_a_half_year_filing_is_not_a_quarter_and_is_not_used() -> None:
    text = fixture_text(TCS_DEC)
    text = text.replace(
        "<xbrli:startDate>2024-10-01</xbrli:startDate>",
        "<xbrli:startDate>2024-07-01</xbrli:startDate>",
    )
    text = text.replace(
        ">2024-10-01</in-bse-fin:DateOfStartOfReportingPeriod>",
        ">2024-07-01</in-bse-fin:DateOfStartOfReportingPeriod>",
    )
    result = _read_text(text, period_end=date(2024, 12, 31))
    assert result.status is ReadStatus.NOT_A_QUARTER and not result.usable
    assert "single quarter" in result.note


def test_a_bank_is_reported_as_a_layout_not_read_and_nothing_is_guessed() -> None:
    result = extract_quarter(
        fixture_bytes("hdfcbank_2024-09-30_consolidated_trimmed.xml"),
        listing_row(symbol="HDFCBANK", flag="B"),
        STAMP,
    )
    assert result.status is ReadStatus.FORMAT_NOT_READ and result.lines == {}
    assert "bank" in result.note.lower() and not result.usable


def test_a_bank_file_is_recognised_by_its_own_layout_even_if_the_listing_says_ordinary() -> None:
    result = extract_quarter(
        fixture_bytes("hdfcbank_2024-09-30_consolidated_trimmed.xml"),
        listing_row(symbol="HDFCBANK"),
        STAMP,
    )
    assert result.status is ReadStatus.FORMAT_NOT_READ and "bank" in result.note.lower()


def test_a_company_in_the_older_accounting_format_is_not_read() -> None:
    older = replace(listing_row(), ind_as=False)
    result = extract_quarter(fixture_bytes(TCS_SEP), older, STAMP)
    assert result.status is ReadStatus.FORMAT_NOT_READ and "older" in result.note.lower()


@pytest.mark.parametrize("garbage", [b"", b"not xml at all", b"<!DOCTYPE x [<!ENTITY y 'z'>]><x/>"])
def test_a_file_that_cannot_be_read_safely_is_refused_in_plain_words(garbage: bytes) -> None:
    result = extract_quarter(garbage, listing_row(), STAMP)
    assert result.status is ReadStatus.FORMAT_NOT_READ and result.lines == {}
    assert result.note.endswith("QuantOS skipped it.")


def test_a_read_survives_being_saved_and_loaded() -> None:
    result = _read(TCS_SEP)
    assert QuarterFigures.from_json_dict(result.to_json_dict()) == result


def test_a_stored_number_must_be_text_so_it_cannot_lose_digits() -> None:
    stored = _read(TCS_SEP).to_json_dict()
    stored["lines"]["revenue_from_operations"]["value"] = 642590000000.0
    with pytest.raises(ValueError, match="must be text"):
        QuarterFigures.from_json_dict(stored)
