"""The Copilot with no AI key: it still answers the common questions from the tools, honestly, in plain words."""

from __future__ import annotations

import re
from typing import Any

import pytest

from quant_system.copilot.rules import AnswerContext, answer_without_ai
from quant_system.copilot.tools import ToolContext, default_registry
from tests.copilot_fakes import FakeNews, FakeQuotes, WordIndex, make_context

NO_ADVICE = "I can't tell you whether to buy or sell."
NO_ADVICE_WITH_FACTS = f"{NO_ADVICE} Here are the facts to look at yourself:"
MENU_START = "I can answer from what is inside QuantOS"


def _ask(text: str, page: str | None = None, ai: bool = False, **context: Any) -> Any:
    return answer_without_ai(
        text, default_registry(make_context(**context)), AnswerContext(page=page, ai_available=ai)
    )


def test_a_greeting_explains_what_it_can_do_and_how_to_add_ai() -> None:
    result = _ask("hi")
    assert "halal" in result.reply.lower() and "facts" in result.reply.lower()
    assert "Settings" in result.reply and "Settings, then AI" in result.reply
    assert result.model is None


def test_the_ai_hint_is_dropped_once_a_key_exists() -> None:
    assert "add an ai key" not in _ask("hi", ai=True).reply.lower()


def test_a_halal_question_is_answered_by_the_screener_with_its_data_status() -> None:
    result = _ask("is AAA halal?")
    text = result.reply
    assert [s.tool for s in result.steps] == ["find_stock", "shariah_check"]
    assert "AAOIFI" in text and "TASIS" in text
    assert "Compliant" in text
    assert "5.0%" in text and "33%" in text  # a ratio against its limit
    assert "sample" in text.lower() and "not audited" in text.lower()
    assert "not a religious ruling" in text.lower()
    assert "2024-04-12" in text


def test_a_halal_question_about_a_stock_outside_the_sample_says_it_cannot_screen_it() -> None:
    result = _ask("is BBB halal")
    assert "cannot screen" in result.reply.lower()
    assert "compliant" not in result.reply.lower().replace("cannot", "")


def test_the_stock_on_screen_is_used_when_none_is_named() -> None:
    result = _ask("is it halal?", page="/stock/AAA")
    assert "AAOIFI" in result.reply


def test_a_halal_question_with_no_stock_asks_which_one() -> None:
    result = _ask("is it halal?")
    assert "which stock" in result.reply.lower()


def test_price_facts_say_how_old_they_are() -> None:
    result = _ask("how is AAA doing?")
    assert (
        "128" in result.reply
        and "2026-09-28" in result.reply
        and "not live" in result.reply.lower()
    )
    assert "+5.2%" in result.reply or "5.2%" in result.reply


def test_news_is_listed_with_a_warning_that_it_is_unverified() -> None:
    headline = {
        "title": "Alpha wins a big order",
        "source": "Example Times",
        "link": "https://example.test/a",
    }
    result = _ask("news on AAA", news=FakeNews([headline]))
    assert "Alpha wins a big order" in result.reply and "Example Times" in result.reply
    assert "unverified" in result.reply.lower()


def test_live_prices_without_a_token_tell_the_person_where_to_add_one() -> None:
    result = _ask("live price of AAA")
    assert "Settings" in result.reply and "Upstox" in result.reply


def test_live_prices_show_how_fresh_they_are() -> None:
    entry = {
        "last_price": 130.5,
        "label": "LAST_CLOSE",
        "message": "Market closed; this is the last close.",
    }
    result = _ask("price of AAA", quotes=FakeQuotes(entry))
    assert "130.5" in result.reply and "last close" in result.reply.lower()


def test_a_second_opinion_request_becomes_a_button_and_explains_the_need_for_keys() -> None:
    result = _ask("get a second opinion on AAA")
    kinds = {p.kind for p in result.proposals}
    assert "second_opinion" in kinds
    assert "AI key" in result.reply


def test_a_second_opinion_request_with_keys_just_offers_the_button() -> None:
    result = _ask("verify AAA", ai=True)
    assert [p.kind for p in result.proposals] == ["second_opinion"]
    assert "AI key" not in result.reply


def test_a_costs_question_points_at_the_costs_screen() -> None:
    result = _ask("what are the brokerage charges?")
    assert any(p.path == "/tools/costs" for p in result.proposals)


def test_an_unknown_question_gets_the_menu_not_a_made_up_answer() -> None:
    result = _ask("what will nifty do tomorrow")
    assert "cannot predict" in result.reply.lower() or "i can" in result.reply.lower()
    assert result.steps == []


def test_a_question_about_the_portfolio_uses_the_portfolio_tool_and_shows_rupees_and_percent() -> (
    None
):
    summary = {
        "totals": {"value": 123456.7, "cost": 100000.0, "pnl": 23456.7, "pnl_pct": 23.4567},
        "warnings": ["AAA is 62% of your portfolio (above 40%)."],
        "note": "Values use each stock's last end-of-day close, not live prices.",
    }
    result = _ask("how is my portfolio", portfolio=lambda: summary)
    assert result.steps and result.steps[0].tool == "portfolio_summary"
    assert (
        "₹123,457" in result.reply
        and "+23.5%" in result.reply
        and "62% of your portfolio" in result.reply
    )
    assert "not live prices" in result.reply


def test_an_empty_portfolio_says_how_to_add_holdings() -> None:
    empty = {
        "holdings": [],
        "totals": None,
        "note": "No holdings added yet. Add them on the Portfolio screen.",
    }
    assert "Portfolio screen" in _ask("my portfolio", portfolio=lambda: empty).reply


@pytest.mark.parametrize(
    "text", ["hi", "is AAA halal", "AAA facts", "price of AAA", "second opinion AAA", "?"]
)
def test_no_reply_asks_for_a_terminal_a_file_or_a_code_setting(text: str) -> None:
    reply = _ask(text).reply
    assert not re.search(
        r"terminal|command|\.env|environment variable|[A-Z]{3,}_[A-Z_]{3,}|JSON|API\b", reply
    )


@pytest.mark.parametrize("word", ["buy ", "sell ", "recommend", "guaranteed", "outperform"])
def test_nothing_is_ever_described_as_a_recommendation_or_an_edge(word: str) -> None:
    reply = _ask("is AAA halal").reply.lower() + _ask("AAA facts").reply.lower()
    assert word not in reply


@pytest.mark.parametrize(
    ("percent_points", "shown"), [(23.4567, "+23.5%"), (-4.26, "-4.3%"), (0.31, "+0.3%")]
)
def test_a_percent_from_the_portfolio_tool_is_shown_as_it_is_and_not_multiplied_again(
    percent_points: float, shown: str
) -> None:
    totals = {"value": 1000.0, "cost": 900.0, "pnl": 100.0, "pnl_pct": percent_points}
    result = _ask("my portfolio", portfolio=lambda: {"totals": totals, "warnings": []})
    assert shown in result.reply


# ------------------------------------------------------------------------------------- everyday words are not stocks

EVERYDAY_WORDS = [
    ("is that a good idea?", "IDEA"),
    ("explain beta to me", "BETA"),
    ("how do I value a company", "VALUE"),
    ("take me through the basics", "TAKE"),
    ("what does total return mean", "TOTAL"),
    ("is the global economy slowing", "GLOBAL"),
    ("what is momentum", "MOMENTUM"),
    ("explain alpha to me", "ALPHA"),
    ("a clean energy story", "CLEAN"),
    ("a deep dive please", "DEEP"),
    ("why is oil so expensive", "OIL"),
    ("what is a sigma move", "SIGMA"),
    ("how are star ratings made", "STAR"),
    ("i am happy with this", "HAPPY"),
]


@pytest.mark.parametrize(("text", "word"), EVERYDAY_WORDS)
def test_an_ordinary_word_is_never_taken_for_a_stock(text: str, word: str) -> None:
    result = _ask(text, ai=True, index=WordIndex())
    assert result.steps == [] and result.proposals == []
    assert MENU_START in result.reply and word not in result.reply


@pytest.mark.parametrize(
    ("text", "company"),
    [
        ("how is IDEA doing?", "VODAFONE IDEA LTD"),
        ("facts on BETA", "BETA DRUGS LTD"),
        ("TOTAL stats please", "TOTAL TRANSPORT LTD"),
    ],
)
def test_the_same_word_written_in_capitals_is_read_as_a_stock_symbol(
    text: str, company: str
) -> None:
    result = _ask(text, index=WordIndex())
    assert company in result.reply and "Last close" in result.reply


@pytest.mark.parametrize("text", ["is aaa halal?", "how is aaa doing?", "is idea halal"])
def test_a_symbol_in_lower_case_is_not_guessed_and_the_person_is_told_how_to_write_it(
    text: str,
) -> None:
    result = _ask(text, index=WordIndex())
    assert result.steps == []
    assert "which stock" in result.reply.lower() and "capital letters" in result.reply


def test_a_stock_named_in_capitals_beats_the_one_on_screen() -> None:
    result = _ask("is IDEA halal?", page="/stock/AAA", index=WordIndex())
    assert "IDEA" in result.reply and "ALPHA" not in result.reply


def test_the_stock_a_workflow_passes_in_wins_over_words_in_the_text() -> None:
    registry = default_registry(make_context(index=WordIndex()))
    context = AnswerContext(symbol="AAA")
    result = answer_without_ai("show me the facts, not the idea behind them", registry, context)
    assert "ALPHA LTD" in result.reply and "Last close" in result.reply


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("is TCS or INFY halal?", "TCS or INFY"),
        ("compare INFY and TCS facts", "INFY or TCS"),
        ("news on TCS, INFY and WIPRO", "TCS, INFY or WIPRO"),
        ("second opinion on TCS vs INFY", "TCS or INFY"),
    ],
)
def test_two_stocks_in_one_question_get_a_plain_question_and_no_guess(
    text: str, names: str
) -> None:
    result = _ask(text, index=WordIndex())
    assert f"Which stock do you mean: {names}?" in result.reply
    assert {s.tool for s in result.steps} == {"find_stock"}  # no screener, news or opinion was run


@pytest.mark.parametrize(
    "text", ["AAA", "AAA facts", "is AAA halal?", "second opinion on AAA", "AAA and AAA", "AAA AAA"]
)
def test_the_stock_lookup_is_recorded_once_per_symbol(text: str) -> None:
    result = _ask(text, ai=True)
    assert [s.tool for s in result.steps].count("find_stock") == 1


# ------------------------------------------------------------------------------------- asking for advice


@pytest.mark.parametrize("text", ["Should I buy AAA?", "Is AAA a good buy?", "sell AAA?"])
def test_a_question_that_asks_for_advice_gets_the_facts_with_a_plain_line_first(
    text: str,
) -> None:
    reply = _ask(text).reply
    assert reply.startswith(NO_ADVICE_WITH_FACTS)
    assert "Last close" in reply and "ALPHA LTD" in reply


def test_a_halal_question_that_also_asks_for_advice_gets_the_line_before_the_screener() -> None:
    reply = _ask("is AAA halal to buy?").reply
    assert reply.startswith(NO_ADVICE_WITH_FACTS) and "AAOIFI" in reply


def test_an_advice_question_with_no_facts_to_show_still_says_it_cannot_advise() -> None:
    reply = _ask("should I buy TCS or INFY", index=WordIndex()).reply
    assert reply.startswith(NO_ADVICE) and "Here are the facts" not in reply
    assert "Which stock do you mean: TCS or INFY?" in reply


def test_an_advice_question_that_matches_nothing_gets_the_menu_which_already_says_so() -> None:
    reply = _ask("is it wise to sell?", ai=True).reply
    assert reply.startswith(MENU_START) and "what to buy or sell" in reply


@pytest.mark.parametrize("text", ["how is AAA doing?", "is AAA halal", "AAA facts"])
def test_a_question_that_does_not_ask_for_advice_gets_no_such_line(text: str) -> None:
    assert "can't tell you whether" not in _ask(text).reply


@pytest.mark.parametrize(
    "text", ["Is TCS halal?", "How is INFY doing?", "News on RELIANCE", "second opinion on TCS"]
)
def test_with_no_market_data_the_answer_says_so_and_names_the_click(text: str) -> None:
    registry = default_registry(ToolContext(index=None, shariah=None))
    reply = answer_without_ai(text, registry, AnswerContext(ai_available=True)).reply
    assert "Market data is not connected yet" in reply and "Settings, then Market data" in reply
    assert "capital letters" not in reply


def test_the_halal_block_is_flat_labelled_and_says_it_is_the_screeners_own_result() -> None:
    block = _ask("is AAA halal?").reply
    assert block.startswith("**From QuantOS's halal screener: AAA (Alpha Ltd)**")
    assert "**AAOIFI: Compliant**" in block and "**TASIS: Compliant**" in block
    assert "\n  - " not in block  # no nested list: every screen shows a flat list the same way
