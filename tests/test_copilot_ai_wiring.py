"""The choice of AI, end to end through the app: Settings picks it, the Copilot uses it, and "Test this AI" checks it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.copilot import cli_chat
from quant_system.copilot.ai_choice import AiChoice
from quant_system.copilot.cli_chat import RunResult
from quant_system.copilot.llm import ChatModel, ChatReply
from quant_system.server.v2 import cli_bridge, copilot_ai
from tests import test_copilot_routes as _routes

client = _routes.client
headers = _routes.headers
ready = _routes.ready
lab = _routes.lab

PATHS = {"claude": "/x/claude", "codex": "/x/codex"}


class Wire:
    """What a test can set about this computer: which AI apps are installed, which keys are saved, how an app answers."""

    def __init__(self) -> None:
        self.keys: dict[str, str] = {}
        self.apps: dict[str, str] = {}
        self.run = RunResult(0, "")
        self.calls: list[list[str]] = []

    def runner(
        self, argv: list[str], stdin: str, timeout: float, env: Mapping[str, str]
    ) -> RunResult:
        self.calls.append(argv)
        return self.run


class Api:
    """A key-based model that answers with its own name, so a test can tell who spoke."""

    def __init__(self, provider: str, key: str) -> None:
        self.provider, self.model, self.key = provider, None, key

    def complete(self, system: str, user: str, **_kw: Any) -> ChatReply:
        return ChatReply(f"answer from {self.provider}", 200, None, None, "m")


@pytest.fixture()
def wire(monkeypatch: pytest.MonkeyPatch) -> Wire:
    wire = Wire()
    monkeypatch.setattr(copilot_ai, "installed_apps", lambda: dict(wire.apps))
    monkeypatch.setattr(copilot_ai, "_RUNNER", wire.runner)
    monkeypatch.setattr(copilot_ai, "_API", Api)
    monkeypatch.setattr(copilot_ai, "_lookup", lambda provider: wire.keys.get(provider))
    monkeypatch.setattr(cli_chat.CliChat, "_env", lambda self: {})
    return wire


def _chat_model(choice: AiChoice) -> ChatModel | None:
    return copilot_ai.build_chat(choice)


# ----------------------------------------------------------------------------- picking the model


def test_nothing_set_up_means_no_model(wire: Wire) -> None:
    assert _chat_model(AiChoice()) is None


def test_a_signed_in_app_is_used_with_no_key_at_all(wire: Wire) -> None:
    wire.apps = dict(PATHS)
    wire.run = RunResult(0, "hello from the app")
    model = _chat_model(AiChoice())
    assert model is not None and model.provider == "cli:claude"
    assert model.complete("s", "u").text == "hello from the app"


def test_a_key_is_the_backup_when_the_app_cannot_answer(wire: Wire) -> None:
    wire.apps = {"claude": "/x/claude"}
    wire.keys = {"openai": "k"}
    wire.run = RunResult(1, "", "Not logged in")
    model = _chat_model(AiChoice())
    assert model is not None and model.complete("s", "u").text == "answer from openai"
    assert model.provider == "openai"


def test_choosing_the_key_first_asks_the_key_first(wire: Wire) -> None:
    wire.apps = {"claude": "/x/claude"}
    wire.keys = {"openai": "k"}
    model = _chat_model(AiChoice(source="api"))
    assert model is not None and model.complete("s", "u").text == "answer from openai"
    assert wire.calls == []


def test_a_person_who_turns_the_backup_off_never_has_the_other_kind_asked(wire: Wire) -> None:
    wire.keys = {"openai": "k"}
    assert _chat_model(AiChoice(source="cli", fallback=False)) is None


def test_a_blank_saved_key_does_not_count(wire: Wire) -> None:
    wire.keys = {"openai": "   "}
    assert _chat_model(AiChoice()) is None


def test_second_opinions_can_name_an_app_or_a_key(wire: Wire) -> None:
    wire.apps, wire.keys = {"codex": "/x/codex"}, {"openai": "k", "gemini": "k"}
    chosen = copilot_ai.verify_models(
        ["cli:codex", "openai", "cli:gemini", "nonsense", "anthropic"]
    )
    assert [m.provider for m in chosen] == ["cli:codex", "openai"]


# ----------------------------------------------------------------------------- settings


def test_the_ai_choice_starts_as_the_app_on_this_computer_with_a_key_as_backup(
    client: TestClient,
) -> None:
    body = client.get("/api/v2/settings").json()
    assert (body["ai_source"], body["ai_cli"], body["ai_api"], body["ai_fallback"]) == (
        "cli",
        None,
        None,
        True,
    )


def test_the_choice_can_be_changed_and_is_kept(client: TestClient, headers: dict[str, str]) -> None:
    patch = {"ai_source": "api", "ai_cli": "codex", "ai_api": "openai", "ai_fallback": False}
    assert client.put("/api/v2/settings", json=patch, headers=headers).status_code == 200
    body = client.get("/api/v2/settings").json()
    assert (body["ai_source"], body["ai_cli"], body["ai_api"], body["ai_fallback"]) == (
        "api",
        "codex",
        "openai",
        False,
    )


@pytest.mark.parametrize(
    "patch", [{"ai_source": "magic"}, {"ai_cli": "gemini"}, {"ai_api": "x" * 100}]
)
def test_a_choice_that_makes_no_sense_is_refused(
    client: TestClient, headers: dict[str, str], patch: dict[str, Any]
) -> None:
    assert client.put("/api/v2/settings", json=patch, headers=headers).status_code == 422


def test_the_copilot_uses_the_choice_saved_in_settings(
    client: TestClient, headers: dict[str, str], wire: Wire
) -> None:
    wire.keys = {"openai": "k"}
    client.put("/api/v2/settings", json={"ai_source": "api", "ai_api": "openai"}, headers=headers)
    assert copilot_ai.current_choice() == AiChoice("api", None, "openai", True)


# ----------------------------------------------------------------------------- what Settings shows


def _states(**states: str) -> list[dict[str, Any]]:
    return [
        {"id": name, "name": name.title(), "state": state, "installed": state != "NOT_INSTALLED"}
        for name, state in states.items()
    ]


def test_the_status_lists_the_apps_and_counts_a_signed_in_one_as_ready(
    client: TestClient, wire: Wire, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli_bridge,
        "list_cli_status",
        lambda force=False: _states(
            claude="CONNECTED", codex="NEEDS_SIGN_IN", antigravity="CONNECTED", other="CONNECTED"
        ),
    )
    body = client.get("/api/v2/copilot/status").json()
    apps = {a["id"]: a for a in body["apps"]}
    assert set(apps) == {"antigravity", "claude", "codex"}  # an app that cannot chat is not offered
    assert apps["claude"]["ready"] is True and apps["codex"]["ready"] is False and apps["antigravity"]["ready"] is True
    assert body["ai_ready"] is True and body["ai"]["source"] == "cli"


def test_no_key_and_no_app_is_not_ready(
    client: TestClient, wire: Wire, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli_bridge, "list_cli_status", lambda force=False: _states(claude="NOT_INSTALLED")
    )
    assert client.get("/api/v2/copilot/status").json()["ai_ready"] is False


# ----------------------------------------------------------------------------- test this AI


def test_testing_an_app_that_answers_says_so_and_records_that_it_is_signed_in(
    client: TestClient, headers: dict[str, str], wire: Wire, monkeypatch: pytest.MonkeyPatch
) -> None:
    wire.apps, wire.run = {"antigravity": "/x/agy"}, RunResult(0, "OK")
    seen: list[tuple[str, bool]] = []
    monkeypatch.setattr(cli_bridge, "record_probe", lambda agent, ok: seen.append((agent, ok)))
    body = client.post(
        "/api/v2/copilot/ai/test", json={"model": "cli:antigravity"}, headers=headers
    ).json()
    assert body["ok"] is True and "Antigravity" in body["who"] and seen == [("antigravity", True)]


def test_testing_an_app_that_is_signed_out_says_how_to_fix_it(
    client: TestClient, headers: dict[str, str], wire: Wire, monkeypatch: pytest.MonkeyPatch
) -> None:
    wire.apps, wire.run = {"claude": "/x/claude"}, RunResult(1, "", "Not logged in")
    seen: list[tuple[str, bool]] = []
    monkeypatch.setattr(cli_bridge, "record_probe", lambda agent, ok: seen.append((agent, ok)))
    body = client.post(
        "/api/v2/copilot/ai/test", json={"model": "cli:claude"}, headers=headers
    ).json()
    assert body["ok"] is False and "signed in" in body["message"] and seen == [("claude", False)]


def test_testing_an_app_that_is_not_installed_says_so(
    client: TestClient, headers: dict[str, str], wire: Wire
) -> None:
    body = client.post(
        "/api/v2/copilot/ai/test", json={"model": "cli:codex"}, headers=headers
    ).json()
    assert body["ok"] is False and "not installed" in body["message"]


def test_testing_a_key_never_returns_the_key(
    client: TestClient, headers: dict[str, str], wire: Wire
) -> None:
    wire.keys = {"openai": "canary-key-ZZ91"}
    response = client.post("/api/v2/copilot/ai/test", json={"model": "openai"}, headers=headers)
    assert response.json()["ok"] is True and "canary-key-ZZ91" not in response.text


def test_testing_with_nothing_named_tests_whatever_the_copilot_would_use(
    client: TestClient, headers: dict[str, str], wire: Wire
) -> None:
    wire.keys = {"openai": "k"}
    body = client.post("/api/v2/copilot/ai/test", json={}, headers=headers).json()
    assert body["ok"] is True and body["who"] == "OpenAI"


def test_testing_with_nothing_set_up_points_to_settings(
    client: TestClient, headers: dict[str, str], wire: Wire
) -> None:
    body = client.post("/api/v2/copilot/ai/test", json={}, headers=headers).json()
    assert body["ok"] is False and "Settings" in body["message"]
