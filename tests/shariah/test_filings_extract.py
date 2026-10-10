"""Figures and tie-outs read from a filing, including the cases that must refuse."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from decimal import Decimal

import pytest
from test_filings_builders import (
    FETCHED_AT,
    TCS_FIXTURE,
    TCS_URL,
    fact,
    make_bank_filing,
    make_filing,
    make_row,
)

from quant_system.shariah.filings.extract import extract_figures
from quant_system.shariah.filings.models import FilingFigures, ReadStatus
from quant_system.shariah.filings.xbrl import MAX_XBRL_BYTES

REAL = TCS_FIXTURE.read_bytes()


def read_real() -> FilingFigures:
    return extract_figures(REAL, make_row(), FETCHED_AT)


def failed_checks(figures: FilingFigures) -> list[str]:
    return [check.name for check in figures.tie_out if not check.ok]


@pytest.mark.parametrize(
    ("key", "tag", "label", "value", "context"),
    [
        (
            "total_assets",
            "Assets",
            "Total assets",
            "1611240000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "current_assets",
            "CurrentAssets",
            "Current assets",
            "1269400000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "noncurrent_assets",
            "NoncurrentAssets",
            "Non-current assets",
            "341840000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "borrowings_current",
            "BorrowingsCurrent",
            "Borrowings, current",
            "0.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "borrowings_noncurrent",
            "BorrowingsNoncurrent",
            "Borrowings, non-current",
            "0.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "cash_and_equivalents",
            "CashAndCashEquivalents",
            "Cash and cash equivalents",
            "81550000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "other_bank_balances",
            "BankBalanceOtherThanCashAndCashEquivalents",
            "Other bank balances",
            "85780000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "current_investments",
            "CurrentInvestments",
            "Investments, current",
            "357920000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "noncurrent_investments",
            "NoncurrentInvestments",
            "Investments, non-current",
            "2890000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "trade_receivables_current",
            "TradeReceivablesCurrent",
            "Trade receivables, current",
            "577100000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "trade_receivables_noncurrent",
            "TradeReceivablesNoncurrent",
            "Trade receivables, non-current",
            "1480000000.00",
            "Balance sheet at 30 Sep 2024",
        ),
        (
            "revenue_from_operations",
            "RevenueFromOperations",
            "Revenue from operations",
            "1268720000000.00",
            "Six months ended 30 Sep 2024",
        ),
        (
            "other_income",
            "OtherIncome",
            "Other income",
            "16910000000.00",
            "Six months ended 30 Sep 2024",
        ),
        (
            "finance_costs",
            "FinanceCosts",
            "Finance costs",
            "3350000000.00",
            "Six months ended 30 Sep 2024",
        ),
        (
            "interest_income_adjustment",
            "AdjustmentsForInterestIncome",
            "Interest income (adjusted in the cash flow statement)",
            "15860000000.00",
            "Six months ended 30 Sep 2024",
        ),
        (
            "paid_up_equity_capital",
            "PaidUpValueOfEquityShareCapital",
            "Paid-up equity share capital",
            "3620000000.00",
            "Six months ended 30 Sep 2024",
        ),
        (
            "face_value",
            "FaceValueOfEquityShareCapital",
            "Face value per share",
            "1",
            "Six months ended 30 Sep 2024",
        ),
    ],
)
def test_real_filing_lines_are_read_exactly(
    key: str, tag: str, label: str, value: str, context: str
) -> None:
    line = read_real().lines[key]
    assert (line.xbrl_tag, line.label, line.value_inr, line.context) == (
        tag,
        label,
        Decimal(value),
        context,
    )
    assert str(line.value_inr) == value


def test_real_filing_reads_ok_and_ties_out() -> None:
    figures = read_real()
    assert figures.read_status is ReadStatus.READ_OK
    assert figures.read_note == ""
    assert failed_checks(figures) == []
    assert [check.name for check in figures.tie_out] == [
        "All required figures are present",
        "Amounts are in rupees",
        "Assets add up",
        "Share count is a whole number",
        "Revenue and other income are not negative",
        "Filing agrees with NSE's listing",
    ]
    assert figures.shares_in_issue == 3_620_000_000


def test_real_filing_carries_its_proof() -> None:
    proof = read_real().proof
    assert proof.source_url == TCS_URL
    assert proof.sha256 == hashlib.sha256(REAL).hexdigest()
    assert proof.period_end == date(2024, 9, 30)
    assert proof.period_label == "Six months ended 30 Sep 2024"
    assert proof.filed_on == date(2024, 10, 10)
    assert (proof.consolidated, proof.audited, proof.ind_as) == (True, True, True)
    assert proof.fetched_at == FETCHED_AT
    assert proof.detail_url is None


def test_identity_comes_from_the_listing_row() -> None:
    figures = read_real()
    assert (figures.symbol, figures.isin) == ("TCS", "INE467B01029")
    assert figures.company_name == "Tata Consultancy Services Limited"


def test_real_filing_lists_the_business_segment_names_it_reports() -> None:
    assert read_real().segment_names == (
        "Banking, Financial Services and Insurance",
        "Communication, Media and Technology",
        "Consumer Business",
        "Life Sciences and Healthcare",
        "Manufacturing",
        "Others",
    )


def test_segment_text_is_cleaned_because_it_comes_from_outside() -> None:
    names = [
        "  Cloud\n  services  ",
        "&lt;b&gt;Bold&lt;/b&gt; shop",
        "A" * 300,
        "Cloud services",
        "",
        "Pay\u202eroll",
    ]
    figures = extract_figures(make_filing(segments=names), make_row(), FETCHED_AT)
    assert figures.segment_names == ("Cloud services", "Bold shop", "A" * 120, "Payroll")


def test_segments_are_capped_at_twenty() -> None:
    names = [f"Segment {number}" for number in range(30)]
    figures = extract_figures(make_filing(segments=names), make_row(), FETCHED_AT)
    assert figures.segment_names == tuple(names[:20])


def test_a_filing_with_no_segments_has_an_empty_list() -> None:
    assert extract_figures(make_filing(), make_row(), FETCHED_AT).segment_names == ()


def test_filing_with_comparative_instants_uses_the_row_date() -> None:
    prior = (
        '<xbrli:context id="Zprev"><xbrli:entity><xbrli:identifier scheme="s">T</xbrli:identifier>'
        "</xbrli:entity><xbrli:period><xbrli:instant>2024-03-31</xbrli:instant></xbrli:period>"
        "</xbrli:context>"
        + fact("Assets", "Zprev", "1500000000000.00")
        + fact("CurrentAssets", "Zprev", "1200000000000.00")
    )
    raw = make_filing().replace(b"</xbrli:xbrl>", prior.encode() + b"</xbrli:xbrl>")
    now = extract_figures(raw, make_row(), FETCHED_AT)
    assert now.lines["total_assets"].value_inr == Decimal("1611240000000.00")
    assert now.read_status is ReadStatus.READ_OK
    march = extract_figures(raw, make_row(period_end=date(2024, 3, 31)), FETCHED_AT)
    assert march.lines["total_assets"].value_inr == Decimal("1500000000000.00")
    assert march.read_status is ReadStatus.READ_PARTIAL


def test_march_quarter_reads_the_full_year_as_the_profit_period() -> None:
    raw = make_filing(
        period_end=date(2025, 3, 31), ytd_start=date(2024, 4, 1), quarter_start=date(2025, 1, 1)
    )
    row = make_row(period_end=date(2025, 3, 31), relating_to="Fourth Quarter")
    figures = extract_figures(raw, row, FETCHED_AT)
    assert figures.read_status is ReadStatus.READ_OK
    assert figures.proof.period_label == "Year ended 31 Mar 2025"
    assert figures.lines["revenue_from_operations"].context == "Year ended 31 Mar 2025"
    assert figures.lines["revenue_from_operations"].value_inr == Decimal("1268720000000.00")
    assert figures.lines["total_assets"].context == "Balance sheet at 31 Mar 2025"


def test_the_nse_quirk_of_a_year_context_with_quarter_dates_is_resolved() -> None:
    figures = extract_figures(make_filing(nse_quirk=True), make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.READ_OK
    assert figures.lines["revenue_from_operations"].value_inr == Decimal("1268720000000.00")


def test_a_filing_with_only_a_quarter_says_so_and_still_reads() -> None:
    quarter_only = dict.fromkeys(
        (
            "RevenueFromOperations",
            "OtherIncome",
            "FinanceCosts",
            "AdjustmentsForInterestIncome",
            "PaidUpValueOfEquityShareCapital",
            "FaceValueOfEquityShareCapital",
        )
    )
    figures = extract_figures(make_filing(ytd=quarter_only), make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.READ_OK
    assert figures.proof.period_label == "Three months ended 30 Sep 2024"
    assert figures.lines["revenue_from_operations"].context == "Three months ended 30 Sep 2024"
    assert figures.lines["revenue_from_operations"].value_inr == Decimal("642590000000.00")
    assert "interest_income_adjustment" not in figures.lines


@pytest.mark.parametrize(
    ("changes", "phrase"),
    [
        (
            {"balance": {"TradeReceivablesCurrent": None, "TradeReceivablesNoncurrent": None}},
            "trade receivables",
        ),
        ({"balance": {"CashAndCashEquivalents": None}}, "cash and cash equivalents"),
        ({"balance": {"BorrowingsCurrent": None, "BorrowingsNoncurrent": None}}, "borrowings"),
        ({"balance": {"Assets": None}}, "total assets"),
        ({"balance": {"CurrentAssets": None}}, "current assets"),
        ({"balance": {"NoncurrentAssets": None}}, "non-current assets"),
        (
            {"ytd": {"RevenueFromOperations": None}, "quarter": {"RevenueFromOperations": None}},
            "revenue from operations",
        ),
        ({"ytd": {"OtherIncome": None}, "quarter": {"OtherIncome": None}}, "other income"),
        (
            {
                "ytd": {"PaidUpValueOfEquityShareCapital": None},
                "quarter": {"PaidUpValueOfEquityShareCapital": None},
            },
            "paid-up",
        ),
        (
            {
                "ytd": {"FaceValueOfEquityShareCapital": None},
                "quarter": {"FaceValueOfEquityShareCapital": None},
            },
            "face value",
        ),
        ({"balance": {"Assets": "12O0.00"}}, "total assets"),
    ],
)
def test_a_missing_required_figure_is_a_partial_read_that_names_it(
    changes: dict[str, dict[str, str | None]], phrase: str
) -> None:
    figures = extract_figures(make_filing(**changes), make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.READ_PARTIAL
    assert phrase in figures.read_note.lower()
    assert "All required figures are present" in failed_checks(figures)


def test_one_borrowings_line_is_enough_and_zero_counts_as_filed() -> None:
    only_current = {"BorrowingsNoncurrent": None}
    figures = extract_figures(make_filing(balance=only_current), make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.READ_OK
    assert "borrowings_noncurrent" not in figures.lines
    assert figures.lines["borrowings_current"].value_inr == Decimal("0.00")


def test_a_missing_figure_is_never_invented() -> None:
    figures = extract_figures(
        make_filing(balance={"CurrentInvestments": None, "OtherIncome": None}),
        make_row(),
        FETCHED_AT,
    )
    assert "current_investments" not in figures.lines
    assert figures.read_status is ReadStatus.READ_OK


def test_revenue_filed_only_under_a_dimension_is_not_used() -> None:
    figures = extract_figures(
        make_filing(ytd={"RevenueFromOperations": None}, quarter={"RevenueFromOperations": None}),
        make_row(),
        FETCHED_AT,
    )
    assert "revenue_from_operations" not in figures.lines
    assert figures.read_status is ReadStatus.READ_PARTIAL


def test_an_amount_not_in_rupees_is_reported_in_plain_words() -> None:
    raw = make_filing().replace(
        b'<in-bse-fin:Assets contextRef="Zb" unitRef="INR"',
        b'<in-bse-fin:Assets contextRef="Zb" unitRef="USD"',
    )
    figures = extract_figures(raw, make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.READ_PARTIAL
    assert "rupees" in figures.read_note


@pytest.mark.parametrize(
    ("assets", "expected"),
    [
        ("1619240000000.00", ReadStatus.READ_OK),
        ("1620240000000.00", ReadStatus.TIE_OUT_FAILED),
        ("1811240000000.00", ReadStatus.TIE_OUT_FAILED),
        ("1411240000000.00", ReadStatus.TIE_OUT_FAILED),
    ],
)
def test_current_plus_noncurrent_must_equal_total_assets(assets: str, expected: ReadStatus) -> None:
    figures = extract_figures(make_filing(balance={"Assets": assets}), make_row(), FETCHED_AT)
    assert figures.read_status is expected


@pytest.mark.parametrize(
    ("extra", "total", "expected"),
    [
        ({"NoncurrentAssetsClassifiedAsHeldForSale": "50000000000.00"}, "1661240000000.00", ReadStatus.READ_OK),
        ({"RegulatoryDeferralAccountDebitBalancesAndRelatedDeferredTaxAssets": "50000000000.00"}, "1661240000000.00", ReadStatus.READ_OK),
        ({"NoncurrentAssetsClassifiedAsHeldForSale": "20000000000.00", "RegulatoryDeferralAccountDebitBalancesAndRelatedDeferredTaxAssets": "30000000000.00"}, "1661240000000.00", ReadStatus.READ_OK),
        ({}, "1661240000000.00", ReadStatus.TIE_OUT_FAILED),
        ({"NoncurrentAssetsClassifiedAsHeldForSale": "50000000000.00"}, "1611240000000.00", ReadStatus.TIE_OUT_FAILED),
    ],
    ids=["held-for-sale", "regulatory-deferral", "both", "gap-with-nothing-filed", "extra-not-in-total"],
)  # fmt: skip
def test_lines_shown_apart_from_current_and_noncurrent_assets_are_added_when_filed(
    extra: dict[str, str], total: str, expected: ReadStatus
) -> None:
    figures = extract_figures(
        make_filing(balance={"Assets": total, **extra}), make_row(), FETCHED_AT
    )
    assert figures.read_status is expected


def test_assets_held_for_sale_and_regulatory_deferral_are_kept_as_figures_and_named_in_the_check() -> (
    None
):
    balance = {
        "Assets": "1661240000000.00",
        "NoncurrentAssetsClassifiedAsHeldForSale": "50000000000.00",
    }
    figures = extract_figures(make_filing(balance=balance), make_row(), FETCHED_AT)
    line = figures.lines["held_for_sale_assets"]
    assert (line.xbrl_tag, line.label) == (
        "NoncurrentAssetsClassifiedAsHeldForSale",
        "Assets held for sale",
    )
    check = next(c for c in figures.tie_out if c.name == "Assets add up")
    assert "plus assets held for sale INR 50,000,000,000" in check.detail


def test_the_assets_tolerance_is_stated_in_the_detail() -> None:
    figures = extract_figures(
        make_filing(balance={"Assets": "1811240000000.00"}), make_row(), FETCHED_AT
    )
    check = next(c for c in figures.tie_out if c.name == "Assets add up")
    assert check.ok is False
    assert "0.5 percent" in check.detail
    assert "INR 10 million" in check.detail
    assert "whichever is larger" in check.detail
    assert figures.read_status is ReadStatus.TIE_OUT_FAILED
    assert "Assets add up" in figures.read_note


def test_a_small_company_may_differ_by_the_absolute_tolerance() -> None:
    small = {
        "Assets": "100000000.00",
        "CurrentAssets": "60000000.00",
        "NoncurrentAssets": "45000000.00",
    }
    figures = extract_figures(make_filing(balance=small), make_row(), FETCHED_AT)
    assert "Assets add up" not in failed_checks(figures)


def test_the_real_file_fails_when_its_assets_are_altered() -> None:
    altered = REAL.replace(b">1611240000000.00<", b">1811240000000.00<")
    figures = extract_figures(altered, make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.TIE_OUT_FAILED
    assert figures.proof.sha256 == hashlib.sha256(altered).hexdigest()


def test_the_real_file_fails_when_its_receivables_are_removed() -> None:
    stripped = re.sub(rb"<in-bse-fin:TradeReceivables\w+ [^\n]*\n", b"", REAL)
    figures = extract_figures(stripped, make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.READ_PARTIAL
    assert "trade receivables" in figures.read_note.lower()


@pytest.mark.parametrize(
    ("changes", "failing"),
    [
        ({"ytd": {"RevenueFromOperations": "-5.00"}}, "Revenue and other income are not negative"),
        ({"ytd": {"OtherIncome": "-1.00"}}, "Revenue and other income are not negative"),
        ({"ytd": {"FaceValueOfEquityShareCapital": "7"}}, "Share count is a whole number"),
        ({"ytd": {"FaceValueOfEquityShareCapital": "0"}}, "Share count is a whole number"),
        (
            {"ytd": {"PaidUpValueOfEquityShareCapital": "-3620000000.00"}},
            "Share count is a whole number",
        ),
        (
            {
                "balance": {
                    "Assets": "5000000.00",
                    "CurrentAssets": "3000000.00",
                    "NoncurrentAssets": "2000000.00",
                }
            },
            "Amounts are in rupees",
        ),
        (
            {
                "balance": {
                    "Assets": "9000000000000000000.00",
                    "CurrentAssets": "9000000000000000000.00",
                    "NoncurrentAssets": "0.00",
                }
            },
            "Amounts are in rupees",
        ),
    ],
)
def test_other_tie_outs_fail_with_their_own_name(
    changes: dict[str, dict[str, str | None]], failing: str
) -> None:
    figures = extract_figures(make_filing(**changes), make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.TIE_OUT_FAILED
    assert failing in failed_checks(figures)


def test_shares_in_issue_is_none_when_the_count_is_not_a_whole_number() -> None:
    changes = {"FaceValueOfEquityShareCapital": "7"}
    figures = extract_figures(make_filing(ytd=changes, quarter=changes), make_row(), FETCHED_AT)
    assert figures.shares_in_issue is None


def test_the_filing_must_agree_with_the_listing() -> None:
    figures = extract_figures(make_filing(nature="Standalone"), make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.TIE_OUT_FAILED
    assert failed_checks(figures) == ["Filing agrees with NSE's listing"]
    agreed = extract_figures(
        make_filing(nature="Standalone"), make_row(consolidated=False), FETCHED_AT
    )
    assert agreed.read_status is ReadStatus.READ_OK


def test_a_period_with_no_balance_sheet_is_reported_as_such() -> None:
    figures = extract_figures(make_filing(with_balance_sheet=False), make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.NO_BALANCE_SHEET
    assert "balance sheet" in figures.read_note
    assert figures.proof.sha256 != ""


def test_the_listing_date_must_match_a_balance_sheet_in_the_file() -> None:
    row = make_row(period_end=date(2024, 12, 31), relating_to="Third Quarter")
    assert extract_figures(REAL, row, FETCHED_AT).read_status is ReadStatus.NO_BALANCE_SHEET


@pytest.mark.parametrize(
    ("raw", "row", "phrase"),
    [
        (make_bank_filing(), make_row(), "bank"),
        (make_filing(), make_row(lender_flag="B", ind_as=False), "bank"),
        (make_filing(), make_row(lender_flag="F", ind_as=True), "lender"),
        (make_filing(), make_row(ind_as=False), "older"),
    ],
    ids=["bank-xbrl", "bank-flag", "lender-flag", "non-ind-as"],
)
def test_formats_the_reader_does_not_handle_are_named_in_plain_words(
    raw: bytes, row: object, phrase: str
) -> None:
    figures = extract_figures(raw, row, FETCHED_AT)  # type: ignore[arg-type]
    assert figures.read_status is ReadStatus.FORMAT_NOT_READ
    assert phrase in figures.read_note.lower()
    assert figures.lines == {}
    assert figures.segment_names == ()
    assert figures.proof.sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "raw",
    [
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>',
        b"<x>" + b"a" * MAX_XBRL_BYTES + b"</x>",
        b"this is not xml",
    ],
    ids=["doctype", "oversized", "malformed"],
)
def test_hostile_or_broken_files_never_raise_and_never_yield_figures(raw: bytes) -> None:
    figures = extract_figures(raw, make_row(), FETCHED_AT)
    assert figures.read_status is ReadStatus.FORMAT_NOT_READ
    assert figures.lines == {}
    assert figures.proof.sha256 == hashlib.sha256(raw).hexdigest()
    assert "could not be read" in figures.read_note
