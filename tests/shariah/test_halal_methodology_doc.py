"""The methodology page says what the code does: a threshold or a word that drifts fails here."""

import shutil
import sqlite3
from pathlib import Path

import pytest

from quant_system.shariah.core.config import settings
from quant_system.shariah.core.methodology import METHODOLOGY_VERSION, NOT_COVERED
from quant_system.shariah.services.screener_service import evaluate_company_shariah
from quant_system.shariah.services.sector_rules import (
    IT_BLOCKING_WORDS,
    IT_SECTOR_NAMES,
    SECTOR_RULES,
)

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "HALAL_METHODOLOGY.md"
SEED_DB = ROOT / "data" / "shariah" / "halal_stocks.db"
THRESHOLDS = [
    "MAX_DEBT_RATIO",
    "MAX_CASH_RATIO",
    "MAX_RECEIVABLES_RATIO",
    "MAX_IMPERMISSIBLE_REVENUE_RATIO",
    "WARN_DEBT_RATIO",
    "WARN_CASH_RATIO",
    "WARN_RECEIVABLES_RATIO",
    "WARN_IMPERMISSIBLE_REVENUE_RATIO",
]
RULE_WORDS = [
    (rule.rule, word) for rule in SECTOR_RULES for word in (*rule.keywords, *rule.sector_names)
]
NOT_SCREENED_HEADING = "### What is not screened"
RATIO_ROWS = [
    ("Interest-bearing debt", "debt_ratio", "total_debt"),
    ("Cash and interest-bearing investments", "cash_ratio", "total_cash_and_investments"),
    ("Trade receivables", "receivables_ratio", "total_receivables"),
    ("Impermissible income", "impermissible_income_ratio", "total_impermissible_income"),
]
# One company whose four denominators are all different, so a wrong denominator cannot hide.
DENOMINATOR_VALUES = {
    "36-month average market capitalisation": 100.0,
    "total assets": 50.0,
    "total revenue": 20.0,
}


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


def line_naming(doc: str, name: str) -> str:
    return next(line for line in doc.splitlines() if f"`{name}`" in line and "|" in line)


def ratio_row(doc: str, name: str) -> list[str]:
    """The cells of one row of the step 2 table."""
    line = next(line for line in doc.splitlines() if line.startswith(f"| {name} |"))
    return [cell.strip() for cell in line.strip("|").split("|")]


@pytest.mark.parametrize("name", THRESHOLDS)
def test_each_threshold_is_stated_exactly_as_the_code_has_it(doc: str, name: str) -> None:
    value = getattr(settings, name)

    line = line_naming(doc, name)

    assert f"| {value:g} |" in line
    assert f"| {value * 100:g}% |" in line


def test_the_nisab_is_stated_as_the_code_has_it(doc: str) -> None:
    line = line_naming(doc, "DEFAULT_SILVER_NISAB_INR")

    assert f"{settings.DEFAULT_SILVER_NISAB_INR:.1f}" in line
    assert f"Rs {settings.DEFAULT_SILVER_NISAB_INR:,.0f}" in line


@pytest.mark.parametrize(
    ("limit_name", "warn_name"),
    [
        ("MAX_DEBT_RATIO", "WARN_DEBT_RATIO"),
        ("MAX_CASH_RATIO", "WARN_CASH_RATIO"),
        ("MAX_RECEIVABLES_RATIO", "WARN_RECEIVABLES_RATIO"),
        ("MAX_IMPERMISSIBLE_REVENUE_RATIO", "WARN_IMPERMISSIBLE_REVENUE_RATIO"),
    ],
)
def test_the_ratio_table_carries_both_the_limit_and_where_the_warning_starts(
    doc: str, limit_name: str, warn_name: str
) -> None:
    limit = (
        f"| {getattr(settings, limit_name) * 100:g}% | {getattr(settings, warn_name) * 100:g}% |"
    )

    assert limit in doc


def test_the_version_in_the_page_is_the_version_in_the_code(doc: str) -> None:
    assert f"`{METHODOLOGY_VERSION}`" in doc


@pytest.mark.parametrize("rule", [rule.rule for rule in SECTOR_RULES])
def test_every_sector_rule_is_named_in_the_page(doc: str, rule: str) -> None:
    assert f"`{rule}`" in doc


@pytest.mark.parametrize(("rule", "word"), RULE_WORDS)
def test_every_word_a_sector_rule_matches_on_is_listed_on_that_rules_row(
    doc: str, rule: str, word: str
) -> None:
    assert f"`{word}`" in line_naming(doc, rule)


@pytest.mark.parametrize("word", [*IT_SECTOR_NAMES, *IT_BLOCKING_WORDS])
def test_the_information_technology_exemption_is_described_with_its_words(
    doc: str, word: str
) -> None:
    assert f"`{word}`" in doc


@pytest.mark.parametrize("line", ["pork", "weapons"])
def test_what_is_not_screened_is_said_and_only_there(doc: str, line: str) -> None:
    before, _, after = doc.partition(NOT_SCREENED_HEADING)

    assert line in after.split("\n## ")[0]
    assert line not in before.lower()


@pytest.mark.parametrize(("name", "attribute", "numerator"), RATIO_ROWS)
def test_each_ratio_divides_by_what_the_page_says(
    doc: str, name: str, attribute: str, numerator: str
) -> None:
    _, aaoifi_denominator, tasis_denominator, _, _ = ratio_row(doc, name)
    company = {
        numerator: 10.0,
        "avg_36m_market_cap": 100.0,
        "total_assets": 50.0,
        "total_revenue": 20.0,
    }

    aaoifi, tasis, _, _ = evaluate_company_shariah(company)

    assert getattr(aaoifi, attribute).actual_value == pytest.approx(
        10.0 / DENOMINATOR_VALUES[aaoifi_denominator]
    )
    assert getattr(tasis, attribute).actual_value == pytest.approx(
        10.0 / DENOMINATOR_VALUES[tasis_denominator]
    )


def test_a_ratio_exactly_at_its_limit_fails_as_the_page_says() -> None:
    company = {
        "total_debt": 33.0,
        "total_assets": 100.0,
        "avg_36m_market_cap": 100.0,
        "total_revenue": 1.0,
    }

    aaoifi, _, _, _ = evaluate_company_shariah(company)

    assert aaoifi.debt_ratio.is_compliant is False


def test_a_zero_denominator_fails_closed_as_the_page_says() -> None:
    aaoifi, _, _, _ = evaluate_company_shariah({"total_debt": 1.0, "avg_36m_market_cap": 0.0})

    assert aaoifi.debt_ratio.actual_value == 1.0


@pytest.mark.parametrize(
    "statement",
    [
        "screening aid, not a fatwa",
        "No scholar has reviewed",
        "UNVERIFIED_SAMPLE",
        "no refresh schedule",
        "hand-entered sample of 39 companies",
        "does not place orders",
    ],
)
def test_the_limits_are_stated_plainly(doc: str, statement: str) -> None:
    assert statement in doc


def test_the_sample_really_has_the_number_of_companies_the_page_states(
    tmp_path: Path, doc: str
) -> None:
    copy = tmp_path / "sample.db"
    shutil.copyfile(SEED_DB, copy)
    conn = sqlite3.connect(copy)
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()

    assert f"hand-entered sample of {count} companies" in doc


def test_the_open_questions_are_left_open(doc: str) -> None:
    assert doc.count("Open question:") >= 5


@pytest.mark.parametrize(
    ("sentence", "phrase"),
    [
        (NOT_COVERED[0], "No scholar has reviewed"),
        (NOT_COVERED[1], "hand-entered sample"),
        (NOT_COVERED[3], "not a fatwa"),
    ],
)
def test_what_every_verdict_says_it_does_not_cover_agrees_with_the_page(
    doc: str, sentence: str, phrase: str
) -> None:
    assert phrase in sentence
    assert phrase in doc
