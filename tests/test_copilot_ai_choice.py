"""Which AI answers: the app already signed in on this computer by default, a saved key if the person prefers it."""

from __future__ import annotations

import pytest

from quant_system.copilot.ai_choice import AiChoice, FallbackChat, plan_models
from quant_system.copilot.llm import ChatReply

CLIS = ["codex", "claude"]  # as found, in no particular order
KEYS = ["openai", "anthropic"]


class Scripted:
    """A chat model that answers with a fixed reply and remembers it was asked."""

    def __init__(self, provider: str, reply: ChatReply, model: str | None = None) -> None:
        self.provider, self.model, self.reply, self.asked = provider, model, reply, 0

    def complete(
        self, system: str, user: str, *, max_tokens: int = 900, timeout: float = 60.0
    ) -> ChatReply:
        self.asked += 1
        return self.reply


def _ok(text: str = "fine", model: str | None = None) -> ChatReply:
    return ChatReply(text, 200, None, None, model)


def _bad(status: int = 503) -> ChatReply:
    return ChatReply(None, status, f"failed {status}")


# ---------------------------------------------------------------------------------- the order


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        (AiChoice(), ["cli:claude", "cli:codex", "anthropic", "openai"]),
        (AiChoice(cli="codex"), ["cli:codex", "cli:claude", "anthropic", "openai"]),
        (AiChoice(source="api"), ["anthropic", "openai", "cli:claude", "cli:codex"]),
        (AiChoice(source="api", api="openai"), ["openai", "anthropic", "cli:claude", "cli:codex"]),
        (AiChoice(fallback=False), ["cli:claude", "cli:codex"]),
        (AiChoice(source="api", fallback=False), ["anthropic", "openai"]),
        (AiChoice(cli="gemini"), ["cli:claude", "cli:codex", "anthropic", "openai"]),
        (AiChoice(cli="nonsense", api="nope"), ["cli:claude", "cli:codex", "anthropic", "openai"]),
    ],
)
def test_the_order_follows_the_choice_and_ignores_what_is_not_there(
    choice: AiChoice, expected: list[str]
) -> None:
    assert plan_models(choice, CLIS, KEYS) == expected


def test_the_default_is_the_signed_in_app_not_a_key() -> None:
    assert AiChoice().source == "cli" and AiChoice().fallback is True


def test_with_nothing_set_up_there_is_nothing_to_ask() -> None:
    assert plan_models(AiChoice(), [], []) == []


def test_an_app_that_cannot_chat_is_never_planned() -> None:
    assert plan_models(AiChoice(), ["unsupported_agent"], []) == []


def test_antigravity_is_planned_when_ready() -> None:
    assert plan_models(AiChoice(), ["antigravity"], []) == ["cli:antigravity"]


def test_only_keys_when_no_app_is_installed() -> None:
    assert plan_models(AiChoice(), [], KEYS) == ["anthropic", "openai"]


# ---------------------------------------------------------------------------------- trying them in turn


def test_the_first_that_answers_is_the_one_used_and_the_rest_are_left_alone() -> None:
    first, second = Scripted("cli:claude", _ok("one", "m1")), Scripted("openai", _ok("two"))
    chat = FallbackChat([first, second])
    reply = chat.complete("s", "u")
    assert reply.text == "one" and (chat.provider, chat.model) == ("cli:claude", "m1")
    assert second.asked == 0


def test_when_the_first_fails_the_next_answers_and_the_chat_says_who_did() -> None:
    first, second = Scripted("cli:claude", _bad(492)), Scripted("openai", _ok("two", "gpt-x"))
    chat = FallbackChat([first, second])
    reply = chat.complete("s", "u")
    assert reply.text == "two" and (chat.provider, chat.model) == ("openai", "gpt-x")


def test_when_all_fail_the_first_ones_reason_is_what_the_person_hears() -> None:
    chat = FallbackChat([Scripted("cli:claude", _bad(492)), Scripted("openai", _bad(429))])
    reply = chat.complete("s", "u")
    assert reply.text is None and reply.status == 492


def test_a_question_that_is_too_long_is_not_tried_on_the_others() -> None:
    first, second = Scripted("cli:claude", _bad(413)), Scripted("openai", _ok())
    assert FallbackChat([first, second]).complete("s", "u").status == 413
    assert second.asked == 0


def test_a_model_that_raised_is_skipped_not_fatal() -> None:
    class Raises:
        provider, model = "cli:codex", None

        def complete(self, *_a: object, **_k: object) -> ChatReply:
            raise RuntimeError("boom")

    chat = FallbackChat([Raises(), Scripted("openai", _ok("two"))])
    assert chat.complete("s", "u").text == "two"


def test_there_must_be_at_least_one_model_to_ask() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FallbackChat([])


def test_a_single_model_is_asked_directly() -> None:
    only = Scripted("openai", _ok("solo"))
    assert FallbackChat([only]).complete("s", "u").text == "solo"
