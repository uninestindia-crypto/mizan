"""The Copilot with no AI key: it still answers the common questions from the tools, honestly, in plain words."""

from __future__ import annotations

import re
from typing import Any

import pytest

from quant_system.copilot.rules import AnswerContext, answer_without_ai
from quant_system.copilot.tools import default_registry
from tests.copilot_fakes import make_context


def _ask(text: str, page: str | None = None, ai: bool = False, **context: Any) -> Any:
    return answer_without_ai(
        text, default_registry(make_context(**context)), AnswerContext(page=page, ai_available=ai)
    )


def test_a_greeting_explains_what_it_can_do_and_how_to_add_ai() -> None:
    result = _ask("hi")
    assert "halal" in result.reply.lower() and "facts" in result.reply.lower()
    assert "Settings" in result.reply and "AI key" in result.reply
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
    class News:
        def headlines(self, query: str) -> list[dict[str, Any]]:
            return [
                {
                    "title": "Alpha wins a big order",
                    "source": "Example Times",
                    "link": "https://example.test/a",
                }
            ]

    result = _ask("news on AAA", news=News())
    assert "Alpha wins a big order" in result.reply and "Example Times" in result.reply
    assert "unverified" in result.reply.lower()


def test_live_prices_without_a_token_tell_the_person_where_to_add_one() -> None:
    result = _ask("live price of AAA")
    assert "Settings" in result.reply and "Upstox" in result.reply


def test_live_prices_show_how_fresh_they_are() -> None:
    class Quotes:
        def quotes(self, symbols: Any) -> dict[str, Any]:
            return {
                "AAA": {
                    "last_price": 130.5,
                    "label": "LAST_CLOSE",
                    "message": "Market closed; this is the last close.",
                }
            }

    result = _ask("price of AAA", quotes=Quotes())
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


def test_a_question_about_the_portfolio_uses_the_portfolio_tool() -> None:
    result = _ask("how is my portfolio", portfolio=lambda: {"holdings": 2, "value": 1000.0})
    assert result.steps and result.steps[0].tool == "portfolio_summary"


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
