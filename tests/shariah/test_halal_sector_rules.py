"""The sector test names the rule that fired and the word it matched on, and decides exactly as before."""

import pytest

from quant_system.shariah.schemas.screening import SectorRuleResult
from quant_system.shariah.services.screener_service import check_sector_compliance
from quant_system.shariah.services.sector_rules import SECTOR_RULES, explain_sector_compliance

KEYWORD_CASES = [(rule.rule, word) for rule in SECTOR_RULES for word in rule.keywords]
SECTOR_NAME_CASES = [(rule.rule, name) for rule in SECTOR_RULES for name in rule.sector_names]

RIBA = "Conventional banking and interest lending (Riba)"
KHAMR = "Commercial manufacturing and distribution of liquor and beer (Khamr)"
DHARAR = "Manufacturing or distribution of tobacco and nicotine products (Dharar)"
MAYSIR = "Operation of gambling or gaming ventures (Maysir/Qimar)"
CINEMA = "Commercial cinema theater exhibition of unscreened non-halal media"

# What the screener answered before the rules became a table, captured from the old code:
# (sector, industry, business summary, compliant, reason).
OLD_ANSWERS = [
    ("Financial Services", "Commercial Banking", "", False, RIBA),
    ("Insurance", "Life", "", False, RIBA),
    ("Industrials", "Lender", "A housing finance company", False, RIBA),
    ("Consumer Staples", "Distilleries, Breweries & Alcohol", "", False, KHAMR),
    ("Consumer Staples", "Cigarettes, Tobacco, FMCG", "", False, DHARAR),
    ("Consumer Discretionary", "Casinos, Gaming", "", False, MAYSIR),
    ("Consumer Services", "Multiplex", "Runs cinema halls", False, CINEMA),
    ("Information Technology", "Software", "Enterprise software", True, None),
    ("IT", "Services", "Consulting", True, None),
    ("Information Technology", "Software", "Builds an online casino", False, MAYSIR),
    ("Healthcare", "Pharmaceuticals", "Generic medicines", True, None),
    ("Industrials", "Heavy Electrical Equipment", "Power equipment", True, None),
]


@pytest.mark.parametrize(("rule_id", "word"), KEYWORD_CASES)
def test_each_keyword_fires_its_own_rule_and_is_named(rule_id: str, word: str) -> None:
    result = explain_sector_compliance("Industrials", "Widgets", f"A maker of {word} products")

    assert (result.compliant, result.rule, result.matched_keyword) == (False, rule_id, word)


@pytest.mark.parametrize(("rule_id", "name"), SECTOR_NAME_CASES)
def test_a_banned_sector_name_fires_its_rule_and_is_named(rule_id: str, name: str) -> None:
    result = explain_sector_compliance(name.title(), "Anything", "")

    assert (result.compliant, result.rule, result.matched_keyword) == (False, rule_id, name)


@pytest.mark.parametrize(("rule_id", "word"), KEYWORD_CASES)
def test_the_plain_check_still_answers_with_the_same_reason(rule_id: str, word: str) -> None:
    explained = explain_sector_compliance("Industrials", "Widgets", f"A maker of {word} products")

    answer = check_sector_compliance("Industrials", "Widgets", f"A maker of {word} products")

    assert answer == (False, explained.reason)
    assert rule_id == explained.rule


@pytest.mark.parametrize(("sector", "industry", "summary", "compliant", "reason"), OLD_ANSWERS)
def test_the_verdict_is_exactly_what_the_old_code_gave(
    sector: str, industry: str, summary: str, compliant: bool, reason: str | None
) -> None:
    assert check_sector_compliance(sector, industry, summary) == (compliant, reason)


@pytest.mark.parametrize(
    ("sector", "industry", "summary"),
    [
        ("Information Technology", "Software", "Enterprise software"),
        ("Healthcare", "Pharmaceuticals", "Generic medicines"),
        ("Industrials", "Heavy Electrical Equipment", ""),
    ],
)
def test_a_company_no_rule_matches_has_no_rule_and_no_word(
    sector: str, industry: str, summary: str
) -> None:
    result = explain_sector_compliance(sector, industry, summary)

    assert result == SectorRuleResult(compliant=True)


def test_an_it_company_that_runs_a_casino_loses_the_it_exemption() -> None:
    result = explain_sector_compliance(
        "Information Technology", "Software", "Builds an online casino"
    )

    assert (result.compliant, result.rule, result.matched_keyword) == (False, "gambling", "casino")


def test_the_first_word_in_the_rule_list_is_the_one_named() -> None:
    result = explain_sector_compliance("Consumer Staples", "Cigarettes, Tobacco and snacks", "")

    assert result.matched_keyword == "cigarettes, tobacco"
