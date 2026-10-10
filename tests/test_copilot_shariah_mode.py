"""In Shariah mode the Copilot leads with the screener's verdict for any stock it discusses, and never the reverse."""

from __future__ import annotations

import json
from typing import Any

import pytest

from quant_system.copilot.agent import CopilotAgent, Message, build_system_prompt
from quant_system.copilot.llm import ChatReply
from quant_system.copilot.rules import AnswerContext, answer_without_ai
from quant_system.copilot.tools import default_registry
from tests.copilot_fakes import make_context


class _Scripted:
    provider = "fake"
    model: str | None = "fake-model"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.prompts: list[tuple[str, str]] = []

    def complete(
        self, system: str, user: str, *, max_tokens: int = 900, timeout: float = 60.0
    ) -> ChatReply:
        self.prompts.append((system, user))
        return ChatReply(self.replies.pop(0), 200, model="fake-model")


def _say(text: str) -> str:
    return json.dumps({"final": text})


def _registry(**context: Any) -> Any:
    return default_registry(make_context(**context))


def _ask(text: str, *, mode: bool, page: str | None = None, **context: Any) -> Any:
    ask = AnswerContext(page=page, ai_available=True, shariah_mode=mode)
    return answer_without_ai(text, _registry(**context), ask)


def test_the_system_prompt_names_shariah_mode_only_when_it_is_on() -> None:
    registry = _registry()
    on = build_system_prompt(registry, None, shariah_mode=True)
    off = build_system_prompt(registry, None)
    assert "Shariah mode" in on and "shariah_check first" in on
    assert "Shariah mode" not in off


def test_on_a_stock_page_the_screener_runs_first_and_its_block_ends_up_in_the_reply() -> None:
    model = _Scripted([_say("Alpha has been steady.")])
    agent = CopilotAgent(model, _registry())
    result = agent.run([Message("user", "how is it doing?")], page="/stock/AAA", shariah_mode=True)
    assert [s.tool for s in result.steps][:1] == ["shariah_check"]
    assert "AAOIFI" in model.prompts[0][1]
    assert "From QuantOS's halal screener: AAA" in result.reply
    assert result.halal is not None


def test_with_the_mode_off_the_stock_page_does_not_run_the_screener_by_itself() -> None:
    model = _Scripted([_say("Alpha has been steady.")])
    result = CopilotAgent(model, _registry()).run(
        [Message("user", "how is it doing?")], page="/stock/AAA"
    )
    assert result.steps == [] and "halal screener" not in result.reply


@pytest.mark.parametrize("page", ["/", "/stock", "/settings/accounts", None])
def test_off_a_stock_page_nothing_is_run_ahead_of_the_question(page: str | None) -> None:
    model = _Scripted([_say("Hello.")])
    result = CopilotAgent(model, _registry()).run(
        [Message("user", "hi")], page=page, shariah_mode=True
    )
    assert result.steps == []


def test_an_assistant_that_may_not_screen_is_not_forced_to() -> None:
    model = _Scripted([_say("Alpha has been steady.")])
    result = CopilotAgent(model, _registry()).run(
        [Message("user", "how is it doing?")],
        page="/stock/AAA",
        shariah_mode=True,
        allowed={"stock_facts"},
    )
    assert result.steps == []


def test_a_built_in_answer_about_a_stock_opens_with_the_screener_in_shariah_mode() -> None:
    result = _ask("how is AAA doing?", mode=True)
    assert result.reply.startswith("**From QuantOS's halal screener: AAA")
    assert result.reply.index("halal screener") < result.reply.index("Last close")
    assert [s.tool for s in result.steps if s.tool == "shariah_check"] == ["shariah_check"]


def test_the_same_answer_has_no_screener_block_when_the_mode_is_off() -> None:
    result = _ask("how is AAA doing?", mode=False)
    assert "halal screener" not in result.reply and "Last close" in result.reply


def test_a_stock_the_screener_has_no_data_for_is_said_to_be_unscreened_before_its_facts() -> None:
    result = _ask("how is BBB doing?", mode=True)
    assert result.reply.lower().startswith("quantos cannot screen bbb")
    assert "Last close" in result.reply


def test_the_halal_question_is_not_answered_twice() -> None:
    result = _ask("is AAA halal?", mode=True)
    assert result.reply.count("From QuantOS's halal screener") == 1


def test_the_watchlist_is_labelled_with_each_stocks_verdict() -> None:
    result = _ask("show my watchlist", mode=True, watchlist=lambda: ["AAA", "BBB"])
    assert "- AAA: compliant" in result.reply
    assert "- BBB: not screened" in result.reply


def test_the_watchlist_is_plain_when_the_mode_is_off() -> None:
    result = _ask("show my watchlist", mode=False, watchlist=lambda: ["AAA", "BBB"])
    assert "Your watchlist: AAA, BBB" in result.reply
