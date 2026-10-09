"""The business-activity test for a stock outside the hand-entered sample: group, name and the filing's own segments."""

from __future__ import annotations

import pytest

from quant_system.shariah.services.activity_check import ActivityStatus, check_activity


def _check(
    name: str = "Example Ltd",
    group: str | None = "Information Technology",
    segments: tuple[str, ...] = (),
    sample: dict[str, object] | None = None,
):
    return check_activity(name, group, segments, sample)


@pytest.mark.parametrize(
    ("segments", "keyword", "rule"),
    [
        (("FMCG - Cigarettes", "Hotels"), "cigarette", "tobacco"),
        (("Distilleries and breweries",), "brewery", "alcohol"),
        (("Indian Made Foreign Liquor",), "liquor", "alcohol"),
        (("Casino operations",), "casino", "gambling"),
        (("Film exhibition",), "film exhibition", "cinema"),
    ],
)
def test_a_prohibited_business_segment_fails_whatever_the_industry_group(
    segments: tuple[str, ...], keyword: str, rule: str
) -> None:
    result = _check(group="Fast Moving Consumer Goods", segments=segments)
    assert result.status is ActivityStatus.FAIL
    assert result.rule == rule and result.matched_keyword == keyword
    assert result.matched_in == "segment"
    assert segments[0].lower() in result.plain.lower()


def test_a_prohibited_word_in_the_company_name_fails() -> None:
    result = _check(name="United Breweries Limited", group="Fast Moving Consumer Goods")
    assert result.status is ActivityStatus.FAIL and result.matched_in == "name"
    assert result.rule == "alcohol"


def test_a_word_inside_a_longer_word_does_not_match() -> None:
    result = _check(name="Careerbeer Technologies", segments=("Software",))
    assert result.status is ActivityStatus.PASS


@pytest.mark.parametrize(
    "name", ["Punjab National Bank", "Bajaj Finserv Limited", "Shriram Finance Ltd"]
)
def test_a_lender_by_name_fails_the_interest_rule(name: str) -> None:
    result = _check(name=name, group="Financial Services")
    assert result.status is ActivityStatus.FAIL and result.rule == "interest_based_finance"
    assert result.matched_in == "name"


def test_a_financial_services_company_without_a_lending_word_is_not_confirmed() -> None:
    result = _check(name="Central Depository Services (India) Limited", group="Financial Services")
    assert result.status is ActivityStatus.NOT_CONFIRMED
    assert "cannot tell" in result.plain.lower()


@pytest.mark.parametrize(
    "group",
    ["Fast Moving Consumer Goods", "Consumer Services", "Media Entertainment & Publication"],
)
def test_a_sensitive_group_with_no_segments_is_not_confirmed(group: str) -> None:
    result = _check(group=group, segments=())
    assert result.status is ActivityStatus.NOT_CONFIRMED
    assert group in result.plain


def test_a_sensitive_group_with_clean_segments_passes_and_shows_the_segments() -> None:
    result = _check(
        group="Fast Moving Consumer Goods",
        segments=("Home Care", "Beauty and Wellbeing", "Foods and Refreshment"),
    )
    assert result.status is ActivityStatus.PASS
    assert result.basis == "industry group and the filing's segments"
    assert result.segments == ("Home Care", "Beauty and Wellbeing", "Foods and Refreshment")


def test_an_ordinary_group_passes_on_the_group_alone_and_says_that_is_all_it_checked() -> None:
    result = _check(group="Capital Goods", segments=())
    assert result.status is ActivityStatus.PASS and result.basis == "industry group only"
    assert "does not have a product-level description" in result.plain


def test_an_it_company_is_failed_for_a_gambling_segment() -> None:
    result = _check(group="Information Technology", segments=("Online betting platform",))
    assert result.status is ActivityStatus.FAIL and result.rule == "gambling"


def test_no_group_and_no_sample_is_not_confirmed() -> None:
    result = _check(group=None)
    assert result.status is ActivityStatus.NOT_CONFIRMED and result.basis == "no classification"


def test_a_sample_row_uses_its_own_classification_and_says_so() -> None:
    sample = {
        "sector": "Financial Services",
        "industry": "Commercial Bank",
        "business_summary": "bank",
        "sector_compliant": 0,
        "sector_failure_reason": "Conventional banking and interest lending (Riba)",
    }
    result = _check(name="HDFC Bank Limited", group=None, sample=sample)
    assert result.status is ActivityStatus.FAIL and result.basis == "sample classification"
    assert result.rule == "interest_based_finance" and result.matched_in == "sample"


def test_a_passing_sample_row_passes_with_its_basis() -> None:
    sample = {
        "sector": "Information Technology",
        "industry": "Software",
        "business_summary": "software services",
        "sector_compliant": 1,
        "sector_failure_reason": None,
    }
    result = _check(group=None, sample=sample)
    assert result.status is ActivityStatus.PASS and result.basis == "sample classification"


def test_segment_text_is_data_never_markup() -> None:
    result = _check(group="Capital Goods", segments=("<script>alert(1)</script> Pumps",))
    assert all("<" not in s and ">" not in s for s in result.segments)
    assert result.status is ActivityStatus.PASS
