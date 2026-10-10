"""The person's own order of AIs, and how one message can ask to be answered: model, thinking, speed.

Everything that reaches an app's command line or a provider's request is checked here, because a chosen model name is
text a person typed or a list returned, and it must never be able to act as an option.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Mapping
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.copilot import cli_chat
from quant_system.copilot.ai_choice import AiChoice, OrderEntry, plan_entries, plan_models
from quant_system.copilot.ai_prefs import (
    AnswerPrefs,
    clean_model,
    clean_thinking,
    effective_thinking,
    preset,
)
from quant_system.copilot.cli_chat import RunResult, build_command
from quant_system.copilot.llm import ChatReply, ProviderChat, RawResponse
from quant_system.server.v2 import copilot_ai, copilot_routes
from tests import test_copilot_routes as _routes
from tests.copilot_fakes import StubModel

client = _routes.client
headers = _routes.headers
lab = _routes.lab

APPS = {"claude", "codex", "antigravity"}


# --------------------------------------------------------------------------------------------- the plan


def test_the_persons_order_is_followed_across_apps_and_keys() -> None:
    choice = AiChoice(
        order=(
            OrderEntry("openai", "gpt-x", "high"),
            OrderEntry("cli:codex"),
            OrderEntry("cli:claude", "fable"),
        )
    )
    entries = plan_entries(choice, APPS, {"openai", "anthropic"})
    assert entries == [
        OrderEntry("openai", "gpt-x", "high"),
        OrderEntry("cli:codex"),
        OrderEntry("cli:claude", "fable"),
    ]
    assert plan_models(choice, APPS, {"openai"}) == ["openai", "cli:codex", "cli:claude"]


def test_an_ai_that_is_not_set_up_or_not_listed_is_never_asked() -> None:
    choice = AiChoice(order=(OrderEntry("anthropic"), OrderEntry("cli:claude")))
    assert plan_models(choice, {"claude", "codex"}, {"openai"}) == [
        "cli:claude"
    ]  # codex, openai: not listed


def test_an_ai_listed_twice_is_asked_once() -> None:
    choice = AiChoice(order=(OrderEntry("cli:claude", "a"), OrderEntry("cli:claude", "b")))
    assert plan_entries(choice, APPS, set()) == [OrderEntry("cli:claude", "a")]


def test_with_the_backup_off_only_the_first_ready_ai_is_asked() -> None:
    choice = AiChoice(
        order=(OrderEntry("anthropic"), OrderEntry("cli:codex"), OrderEntry("cli:claude")),
        fallback=False,
    )
    assert plan_models(choice, APPS, {"openai"}) == ["cli:codex"]


def test_with_no_order_the_older_rules_decide_exactly_as_before() -> None:
    assert plan_models(AiChoice(), APPS, {"openai", "anthropic"}) == [
        "cli:claude",
        "cli:codex",
        "cli:antigravity",
        "anthropic",
        "openai",
    ]
    assert plan_entries(AiChoice(), {"codex"}, set()) == [OrderEntry("cli:codex")]


# ------------------------------------------------------------------------------------------ safe values


@pytest.mark.parametrize(
    "name", ["--help", "-m", " --x", "a b", 'a"b', "a;b", "x" * 81, "a\nb", "$(x)"]
)
def test_a_model_name_that_could_act_as_an_option_or_more_is_refused(name: str) -> None:
    with pytest.raises(ValueError):
        clean_model(name)


@pytest.mark.parametrize(
    "name", ["fable", "gpt-5.6-luna", "claude-fable-5-1[1m]", "gemini-3.8-flash-high", "a/b:c_d"]
)
def test_real_model_names_are_accepted(name: str) -> None:
    assert clean_model(name) == name


def test_blank_means_the_ais_own_choice_and_levels_are_a_short_list() -> None:
    assert clean_model("  ") is None and clean_model(None) is None
    assert clean_thinking(" HIGH ") == "high" and clean_thinking(None) is None
    with pytest.raises(ValueError):
        clean_thinking("huge")


def test_speed_stands_for_limits_and_a_levels_choice_wins_over_it() -> None:
    assert preset("quick").chat_steps < preset("balanced").chat_steps < preset("careful").chat_steps
    assert preset("quick").deadline < preset("balanced").deadline < preset("careful").deadline
    assert preset(None) == preset("balanced") and preset("nonsense") == preset("balanced")
    assert (
        effective_thinking(None, "quick") == "low" and effective_thinking(None, "careful") == "high"
    )
    assert effective_thinking(None, "balanced") is None
    assert effective_thinking("max", "quick") == "max"


# --------------------------------------------------------------------------------- the app command lines


def test_the_base_command_lines_are_unchanged_when_nothing_is_chosen() -> None:
    assert build_command("claude", "c") == [
        "c", "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config", "--max-turns", "1",
    ]  # fmt: skip
    assert build_command("codex", "x")[-1] == "-" and "-m" not in build_command("codex", "x")
    assert (
        build_command("antigravity", "a")[:2] == ["a", "-p"]
        and len(build_command("antigravity", "a")) == 3
    )


def test_a_chosen_model_and_level_are_added_and_the_safety_switches_stay() -> None:
    claude = build_command("claude", "c", model="fable", thinking="high")
    assert claude[-4:] == ["--model", "fable", "--effort", "high"]
    assert "--tools" in claude and "--strict-mcp-config" in claude
    codex = build_command("codex", "x", model="gpt-6-luna", thinking="xhigh")
    assert codex[-1] == "-" and codex[codex.index("-m") + 1] == "gpt-6-luna"
    assert codex[codex.index("-c") + 1] == 'model_reasoning_effort="xhigh"'
    assert codex[codex.index("--sandbox") + 1] == "read-only"
    agy = build_command("antigravity", "a", model="gemini-3.8-flash-high", thinking="low")
    assert agy[-4:] == ["--model", "gemini-3.8-flash-high", "--effort", "low"]


def test_a_level_an_app_does_not_know_is_left_off_its_command() -> None:
    assert "--effort" not in build_command("claude", "c", thinking="ultra")
    assert "--effort" not in build_command("antigravity", "a", thinking="ultra")
    assert 'model_reasoning_effort="ultra"' in build_command("codex", "x", thinking="ultra")


def test_a_model_name_that_is_not_safe_never_reaches_a_command() -> None:
    for agent in ("claude", "codex", "antigravity"):
        with pytest.raises(ValueError):
            build_command(agent, "x", model="--dangerously-skip-permissions")
    with pytest.raises(ValueError):
        cli_chat.CliChat("claude", "c", model="--help")


def test_a_company_app_is_never_given_a_model_or_level(monkeypatch: pytest.MonkeyPatch) -> None:
    from quant_system.server.v2 import cli_bridge

    monkeypatch.setattr(cli_bridge, "is_custom_agent", lambda agent_id: agent_id == "acme")
    command = build_command("acme", "acme.exe", model="m", thinking="high")
    assert "--model" not in command and "--effort" not in command


def test_the_chosen_model_is_kept_for_every_question_not_only_the_first() -> None:
    seen: list[list[str]] = []

    def runner(argv: list[str], stdin: str, timeout: float, env: Mapping[str, str]) -> RunResult:
        seen.append(argv)
        return RunResult(0, "hello")

    chat = cli_chat.CliChat(
        "codex", "x", runner=runner, environment={}, model="gpt-6-luna", thinking="high"
    )
    chat.complete("s", "u")
    chat.complete("s", "u")
    assert all("gpt-6-luna" in argv for argv in seen) and len(seen) == 2


# ------------------------------------------------------------------------------ the providers' requests


def _capture(status: int = 200, body: bytes | None = None) -> tuple[list[dict[str, Any]], Any]:
    sent: list[dict[str, Any]] = []
    ok = json.dumps({"content": [{"type": "text", "text": "hi"}]}).encode()

    def transport(request: urllib.request.Request, timeout: float) -> RawResponse:
        payload = json.loads(request.data or b"{}")  # type: ignore[arg-type]
        sent.append(payload)
        return RawResponse(
            status if "thinking" in payload or status == 200 else 200, body or ok, {}
        )

    return sent, transport


def test_a_chosen_level_is_sent_to_anthropic_with_room_for_the_thinking() -> None:
    sent, transport = _capture()
    chat = ProviderChat("anthropic", "k", "claude-x", transport=transport, thinking="high")
    assert chat.complete("s", "u").text == "hi"
    assert sent[0]["output_config"] == {"effort": "high"} and sent[0]["thinking"] == {
        "type": "adaptive"
    }
    assert sent[0]["max_tokens"] >= 8000


def test_nothing_about_thinking_is_sent_when_none_was_chosen() -> None:
    sent, transport = _capture()
    ProviderChat("anthropic", "k", "claude-x", transport=transport).complete("s", "u")
    assert (
        "thinking" not in sent[0]
        and "output_config" not in sent[0]
        and sent[0]["max_tokens"] == 900
    )


def test_a_level_the_provider_cannot_take_is_not_sent() -> None:
    sent, transport = _capture()
    ProviderChat("anthropic", "k", "m", transport=transport, thinking="ultra").complete("s", "u")
    assert "output_config" not in sent[0]
    sent, transport = _capture()
    ProviderChat("deepseek", "k", "m", transport=transport, thinking="high").complete("s", "u")
    assert "reasoning_effort" not in sent[0] and "reasoning" not in sent[0]


def test_openai_style_providers_name_the_setting_in_their_own_way() -> None:
    reply = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
    for provider, key, expected in (
        ("openai", "reasoning_effort", "medium"),
        ("groq", "reasoning_effort", "medium"),
        ("openrouter", "reasoning", {"effort": "medium"}),
    ):
        sent, transport = _capture(body=reply)
        chat = ProviderChat(provider, "k", "m", transport=transport, thinking="medium")
        assert chat.complete("s", "u").text == "ok"
        assert sent[0][key] == expected, provider


def test_gemini_gets_its_own_thinking_setting() -> None:
    reply = json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}).encode()
    sent, transport = _capture(body=reply)
    ProviderChat("gemini", "k", "gemini-x", transport=transport, thinking="low").complete("s", "u")
    assert sent[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}


def test_a_model_that_refuses_the_setting_is_asked_again_without_it() -> None:
    sent, transport = _capture(status=400)
    chat = ProviderChat("anthropic", "k", "old-model", transport=transport, thinking="high")
    reply = chat.complete("s", "u")
    assert reply.text == "hi" and len(sent) == 2
    assert "thinking" in sent[0] and "thinking" not in sent[1] and sent[1]["max_tokens"] == 900


def test_a_real_error_without_a_setting_is_not_retried() -> None:
    calls: list[int] = []

    def transport(request: urllib.request.Request, timeout: float) -> RawResponse:
        calls.append(1)
        return RawResponse(400, b"bad", {})

    reply = ProviderChat("anthropic", "k", "m", transport=transport).complete("s", "u")
    assert reply.text is None and reply.status == 400 and len(calls) == 1


# ------------------------------------------------------------------------------------- building the chat


class ApiWithChoices:
    """A key-based model that records the model and level it was built with."""

    built: list[tuple[str, str | None, str | None]] = []

    def __init__(
        self, provider: str, key: str, model: str | None = None, thinking: str | None = None
    ) -> None:
        self.provider, self.model, self.thinking = provider, model, thinking
        ApiWithChoices.built.append((provider, model, thinking))

    def complete(self, system: str, user: str, **_kw: Any) -> ChatReply:
        return ChatReply(f"answer from {self.provider}", 200, None, None, self.model)


@pytest.fixture()
def computer(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {
        "apps": {"claude": "/x/claude", "codex": "/x/codex"},
        "keys": {"openai": "k"},
        "calls": [],
    }

    def runner(argv: list[str], stdin: str, timeout: float, env: Mapping[str, str]) -> RunResult:
        state["calls"].append(argv)
        return RunResult(0, "from an app")

    ApiWithChoices.built = []
    monkeypatch.setattr(copilot_ai, "installed_apps", lambda: dict(state["apps"]))
    monkeypatch.setattr(copilot_ai, "_RUNNER", runner)
    monkeypatch.setattr(copilot_ai, "_API", ApiWithChoices)
    monkeypatch.setattr(copilot_ai, "_lookup", lambda provider: state["keys"].get(provider))
    monkeypatch.setattr(cli_chat.CliChat, "_env", lambda self: {})
    return state


def test_each_ai_in_the_order_is_built_with_its_own_model_and_level(
    computer: dict[str, Any],
) -> None:
    choice = AiChoice(
        order=(
            OrderEntry("cli:codex", "gpt-6-luna", "high"),
            OrderEntry("openai", "gpt-x", "low"),
        )
    )
    model = copilot_ai.build_chat(choice)
    assert model is not None and model.complete("s", "u").text == "from an app"
    assert (
        "gpt-6-luna" in computer["calls"][0]
        and 'model_reasoning_effort="high"' in computer["calls"][0]
    )
    assert ApiWithChoices.built == [("openai", "gpt-x", "low")]


def test_the_speed_sets_the_level_only_where_the_person_chose_none(
    computer: dict[str, Any],
) -> None:
    choice = AiChoice(order=(OrderEntry("openai"), OrderEntry("cli:claude", None, "max")))
    copilot_ai.build_chat(choice, AnswerPrefs(speed="quick"))
    assert ApiWithChoices.built == [("openai", None, "low")]  # quick stands for a low level
    ApiWithChoices.built.clear()
    model = copilot_ai.build_chat(
        AiChoice(order=(OrderEntry("cli:claude", None, "max"),)), AnswerPrefs(speed="quick")
    )
    assert model is not None
    model.complete("s", "u")
    assert computer["calls"][0][-2:] == [
        "--effort",
        "max",
    ]  # the person's own level beats the speed


def test_one_message_can_ask_for_a_different_ai_first_and_keeps_the_rest_as_backup(
    computer: dict[str, Any],
) -> None:
    choice = AiChoice(
        order=(OrderEntry("cli:claude"), OrderEntry("cli:codex"), OrderEntry("openai"))
    )
    model = copilot_ai.build_chat(choice, AnswerPrefs(ai="openai", model="gpt-y", thinking="high"))
    assert model is not None and model.provider == "openai"
    assert ApiWithChoices.built[0] == ("openai", "gpt-y", "high")
    assert isinstance(model, copilot_ai.FallbackChat) and len(model._models) == 3


def test_asking_for_an_ai_with_the_backup_off_uses_only_that_one(computer: dict[str, Any]) -> None:
    choice = AiChoice(order=(OrderEntry("cli:claude"), OrderEntry("openai")), fallback=False)
    model = copilot_ai.build_chat(choice, AnswerPrefs(ai="openai"))
    assert model is not None and not isinstance(model, copilot_ai.FallbackChat)


def test_asking_for_an_ai_that_is_not_set_up_changes_nothing(computer: dict[str, Any]) -> None:
    choice = AiChoice(order=(OrderEntry("cli:claude"),))
    model = copilot_ai.build_chat(choice, AnswerPrefs(ai="anthropic", model="x"))
    assert model is not None and model.provider == "cli:claude"


def test_a_model_for_the_first_ai_without_naming_one_applies_to_the_first(
    computer: dict[str, Any],
) -> None:
    choice = AiChoice(order=(OrderEntry("cli:codex", "old", "low"), OrderEntry("openai")))
    model = copilot_ai.build_chat(choice, AnswerPrefs(model="gpt-6-luna"))
    assert model is not None
    model.complete("s", "u")
    argv = computer["calls"][0]
    assert argv[argv.index("-m") + 1] == "gpt-6-luna" and 'model_reasoning_effort="low"' in argv


def test_a_model_name_in_the_order_that_is_not_safe_leaves_that_ai_out(
    computer: dict[str, Any],
) -> None:
    bad = OrderEntry("cli:claude", "--help")
    model = copilot_ai.build_chat(AiChoice(order=(bad, OrderEntry("openai"))))
    assert model is not None and model.provider == "openai"


# ------------------------------------------------------------------------------------- settings over HTTP


def _put(client: TestClient, headers: dict[str, str], patch: dict[str, Any]) -> Any:
    return client.put("/api/v2/settings", json=patch, headers=headers)


def test_the_order_and_defaults_start_empty_and_are_kept(
    client: TestClient, headers: dict[str, str]
) -> None:
    body = client.get("/api/v2/settings").json()
    assert body["ai_order"] == [] and body["ai_defaults"] == {"speed": "balanced", "helpers": 1}
    order = [{"id": "cli:codex", "model": "gpt-6-luna", "thinking": "high"}, {"id": "openai"}]
    assert (
        _put(client, headers, {"ai_order": order, "ai_defaults": {"speed": "careful"}}).status_code
        == 200
    )
    saved = client.get("/api/v2/settings").json()
    assert saved["ai_order"][0] == order[0] and saved["ai_order"][1] == {
        "id": "openai",
        "model": None,
        "thinking": None,
    }
    assert saved["ai_defaults"] == {"speed": "careful", "helpers": 1}  # only the speed changed
    assert copilot_ai.current_choice().order[0] == OrderEntry("cli:codex", "gpt-6-luna", "high")
    assert copilot_ai.current_defaults() == ("careful", 1)


def test_a_new_order_replaces_the_old_one(client: TestClient, headers: dict[str, str]) -> None:
    _put(client, headers, {"ai_order": [{"id": "openai"}, {"id": "cli:claude"}]})
    _put(client, headers, {"ai_order": [{"id": "cli:claude"}]})
    assert [e["id"] for e in client.get("/api/v2/settings").json()["ai_order"]] == ["cli:claude"]
    _put(client, headers, {"ai_order": []})
    assert client.get("/api/v2/settings").json()["ai_order"] == []


@pytest.mark.parametrize(
    "order",
    [
        [{"id": "gemini-cli"}],  # not an AI this app knows
        [{"id": "cli:claude"}, {"id": "cli:claude"}],  # twice
        [{"id": "openai", "model": "--help"}],  # could act as an option
        [{"id": "openai", "thinking": "enormous"}],
        [{"model": "x"}],
        "openai",
        [{"id": "openai"}] * 13,
    ],
)
def test_an_order_that_makes_no_sense_is_refused_and_nothing_changes(
    client: TestClient, headers: dict[str, str], order: Any
) -> None:
    assert _put(client, headers, {"ai_order": order}).status_code == 422
    assert client.get("/api/v2/settings").json()["ai_order"] == []


def test_defaults_outside_the_allowed_choices_are_refused(
    client: TestClient, headers: dict[str, str]
) -> None:
    for bad in ({"speed": "warp"}, {"helpers": 0}, {"helpers": 4}):
        assert _put(client, headers, {"ai_defaults": bad}).status_code == 422


def test_the_status_tells_the_screens_the_order_and_the_defaults(
    client: TestClient, headers: dict[str, str]
) -> None:
    _put(client, headers, {"ai_order": [{"id": "openai", "model": "gpt-x", "thinking": "low"}]})
    body = client.get("/api/v2/copilot/status").json()
    assert body["ai"]["order"] == [{"id": "openai", "model": "gpt-x", "thinking": "low"}]
    assert body["defaults"] == {"speed": "balanced", "helpers": 1}


# ------------------------------------------------------------------------------------- chat over HTTP


def test_a_message_can_carry_what_it_wants_and_the_speed_sets_the_limits(
    client: TestClient, headers: dict[str, str], lab: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[AnswerPrefs] = []
    stub = StubModel("openai", json.dumps({"final": "Here you go."}))

    def chat_for(prefs: AnswerPrefs) -> StubModel:
        asked.append(prefs)
        return stub

    monkeypatch.setattr(copilot_routes, "chat_model_for", chat_for)
    limits: list[dict[str, Any]] = []
    real = copilot_routes.CopilotAgent

    class Watch(real):  # type: ignore[valid-type, misc]
        def __init__(self, model: Any, registry: Any, **kwargs: Any) -> None:
            limits.append(kwargs)
            super().__init__(model, registry, **kwargs)

    monkeypatch.setattr(copilot_routes, "CopilotAgent", Watch)
    body = {
        "messages": [{"role": "user", "content": "hello"}],
        "prefs": {
            "ai": "openai",
            "model": "gpt-x",
            "thinking": "high",
            "speed": "quick",
            "helpers": 2,
        },
    }
    reply = client.post("/api/v2/copilot/chat", json=body, headers=headers)
    assert reply.status_code == 200 and reply.json()["reply"].startswith("Here you go.")
    assert asked == [AnswerPrefs("openai", "gpt-x", "high", "quick", 2)]
    assert limits[0]["max_steps"] == preset("quick").chat_steps
    assert limits[0]["deadline_seconds"] == preset("quick").deadline


def test_a_message_without_choices_uses_the_saved_speed(
    client: TestClient, headers: dict[str, str], lab: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put(client, headers, {"ai_defaults": {"speed": "careful"}})
    lab.models["openai"] = StubModel("openai", json.dumps({"final": "ok"}))
    limits: list[dict[str, Any]] = []
    real = copilot_routes.CopilotAgent

    class Watch(real):  # type: ignore[valid-type, misc]
        def __init__(self, model: Any, registry: Any, **kwargs: Any) -> None:
            limits.append(kwargs)
            super().__init__(model, registry, **kwargs)

    monkeypatch.setattr(copilot_routes, "CopilotAgent", Watch)
    body = {"messages": [{"role": "user", "content": "hello"}]}
    assert client.post("/api/v2/copilot/chat", json=body, headers=headers).status_code == 200
    assert limits[0]["max_steps"] == preset("careful").chat_steps


@pytest.mark.parametrize(
    "prefs",
    [
        {"model": "--help"},
        {"thinking": "huge"},
        {"speed": "warp"},
        {"helpers": 9},
        {"model": "x" * 200},
    ],
)
def test_a_message_asking_for_something_that_makes_no_sense_gets_a_plain_refusal(
    client: TestClient, headers: dict[str, str], prefs: dict[str, Any]
) -> None:
    body = {"messages": [{"role": "user", "content": "hello"}], "prefs": prefs}
    response = client.post("/api/v2/copilot/chat", json=body, headers=headers)
    assert response.status_code == 422
    text = json.dumps(response.json())
    assert "pydantic" not in text and "String should" not in text


def test_the_test_button_asks_the_ai_exactly_as_it_is_set_up(
    client: TestClient, headers: dict[str, str], computer: dict[str, Any]
) -> None:
    body = {"model": "cli:codex", "chosen_model": "gpt-6-luna", "thinking": "high"}
    result = client.post("/api/v2/copilot/ai/test", json=body, headers=headers).json()
    assert result["ok"] is True
    argv = computer["calls"][0]
    assert argv[argv.index("-m") + 1] == "gpt-6-luna" and 'model_reasoning_effort="high"' in argv
    bad = client.post(
        "/api/v2/copilot/ai/test",
        json={"model": "cli:codex", "chosen_model": "--help"},
        headers=headers,
    )
    assert bad.status_code == 422
