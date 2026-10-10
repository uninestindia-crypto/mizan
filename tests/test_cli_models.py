"""The live model lists of the AI apps: read from the app or the person's account, never typed in."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.alpha.model_catalog import ModelCatalogError, ModelEntry, _anthropic_entry
from quant_system.server.app import app
from quant_system.server.v2 import cli_bridge, cli_models

AGY_LISTING = """Fetching available models...
gemini-3.8-flash-high\tGemini 3.8 Flash (High)
gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)
gemini-3.8-flash-low\tGemini 3.8 Flash (Low)
gemini-3.7-flash-high\tGemini 3.7 Flash (High)
gemini-3.7-flash-low\tGemini 3.7 Flash (Low)
gemini-3.1-pro-high\tGemini 3.1 Pro (High)
gemini-3.1-pro-low\tGemini 3.1 Pro (Low)
claude-sonnet-4-6\tClaude Sonnet 4.6 (Thinking)
"""

CODEX_PAYLOAD: dict[str, Any] = {
    "models": [
        {
            "slug": "gpt-hidden",
            "display_name": "Hidden",
            "visibility": "hide",
            "priority": 1,
            "supported_reasoning_levels": [{"effort": "low"}],
        },
        {
            "slug": "gpt-5.6-luna",
            "display_name": "GPT-5.6-Luna",
            "visibility": "list",
            "priority": 9,
            "description": "Older and cheaper.",
            "context_window": 272000,
            "default_reasoning_level": "medium",
            "supported_reasoning_levels": [{"effort": "low"}, {"effort": "medium"}],
        },
        {
            "slug": "gpt-6-luna",
            "display_name": "GPT-6-Luna",
            "visibility": "list",
            "priority": 4,
            "description": "Fast and affordable.",
            "context_window": 272000,
            "default_reasoning_level": "medium",
            "supported_reasoning_levels": [
                {"effort": "low"},
                {"effort": "medium"},
                {"effort": "high"},
                {"effort": "max"},
            ],
        },
    ]
}

CLAUDE_HELP = """Usage: claude [options]
  --effort <level>                      Effort level for the current session
                                        (low, medium, high, xhigh, max)
  --model <model>                       Model for the current session. Provide
                                        an alias for the latest model (e.g.
                                        'fable', 'opus', or 'sonnet') or a
                                        model's full name.
"""


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    cli_models.clear_cache()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def _installed(monkeypatch: pytest.MonkeyPatch, agent_id: str, version: str = "1.0.0") -> None:
    monkeypatch.setattr(
        cli_bridge,
        "list_cli_status",
        lambda force=False: [
            {"id": agent_id, "installed": True, "authenticated": True, "version": version}
        ],
    )
    monkeypatch.setattr(cli_models, "_executable", lambda agent: f"C:\\{agent}.exe")


def _run(monkeypatch: pytest.MonkeyPatch, output: str, code: int = 0) -> list[list[str]]:
    seen: list[list[str]] = []

    def capture(args: list[str], timeout: float, *, merge: bool = False) -> tuple[int, str]:
        seen.append(args)
        return code, output

    monkeypatch.setattr(cli_models, "_capture", capture)
    return seen


# ------------------------------------------------------------------------------------------- Antigravity


def test_antigravity_tiers_become_one_model_with_thinking_levels() -> None:
    models = {m["id"]: m for m in cli_models.parse_antigravity_models(AGY_LISTING)}
    flash = models["gemini-3.8-flash"]
    assert flash["name"] == "Gemini 3.8 Flash"
    assert flash["thinking"] == {"levels": ["low", "medium", "high"], "default": None}
    assert flash["variants"]["high"] == "gemini-3.8-flash-high"
    assert models["gemini-3.1-pro"]["thinking"]["levels"] == ["low", "high"]  # no medium tier
    assert models["claude-sonnet-4-6"]["thinking"] is None


def test_newest_is_marked_only_where_there_is_an_older_one_to_compare() -> None:
    models = {m["id"]: m for m in cli_models.parse_antigravity_models(AGY_LISTING)}
    assert models["gemini-3.8-flash"]["newest"] is True
    assert models["gemini-3.7-flash"]["newest"] is False
    assert models["gemini-3.1-pro"]["newest"] is False  # the only Pro: not "newest" of anything
    assert models["claude-sonnet-4-6"]["newest"] is False


def test_antigravity_answer_comes_from_its_own_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(monkeypatch, "antigravity")
    ran = _run(monkeypatch, AGY_LISTING)
    answer = cli_models.fetch_cli_capabilities("antigravity")
    assert ran == [["C:\\antigravity.exe", "models"]]
    assert answer["source"] == "app" and answer["thinking_levels"] == ["low", "medium", "high"]
    assert [m["id"] for m in answer["models"]][:2] == ["gemini-3.8-flash", "gemini-3.7-flash"]
    assert answer["features"][0]["description"] == "4 found. The newest is Gemini 3.8 Flash."


def test_no_made_up_list_when_the_app_cannot_be_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(monkeypatch, "antigravity")
    _run(monkeypatch, "not signed in", code=1)
    answer = cli_models.fetch_cli_capabilities("antigravity")
    assert answer["models"] == [] and answer["source"] == "none"
    assert "signed in" in answer["note"] and answer["features"] == []


# ------------------------------------------------------------------------------------------------- Codex


def test_codex_models_keep_the_listed_ones_in_the_apps_own_order() -> None:
    models = cli_models.parse_codex_models(CODEX_PAYLOAD)
    assert [m["id"] for m in models] == ["gpt-6-luna", "gpt-5.6-luna"]  # hidden one left out
    top = models[0]
    assert top["recommended"] is True and top["newest"] is True
    assert top["thinking"] == {"levels": ["low", "medium", "high", "max"], "default": "medium"}
    assert top["context_window"] == 272000 and top["description"] == "Fast and affordable."


def test_codex_is_asked_for_its_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(monkeypatch, "codex")
    ran = _run(monkeypatch, "warning: x\n" + json.dumps(CODEX_PAYLOAD))
    answer = cli_models.fetch_cli_capabilities("codex")
    assert ran == [["C:\\codex.exe", "debug", "models"]]
    assert answer["source"] == "app" and answer["thinking_levels"] == [
        "low",
        "medium",
        "high",
        "max",
    ]


def test_codex_falls_back_to_the_list_it_saved_and_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _installed(monkeypatch, "codex")
    _run(monkeypatch, "", code=1)
    cache = tmp_path / ".codex"
    cache.mkdir()
    saved = {**CODEX_PAYLOAD, "fetched_at": "2026-10-09T10:00:00Z"}
    (cache / "models_cache.json").write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    answer = cli_models.fetch_cli_capabilities("codex")
    assert (
        answer["source"] == "app_saved" and answer["saved_list_checked"] == "2026-10-09T10:00:00Z"
    )
    assert "saved earlier" in answer["note"] and len(answer["models"]) == 2


# ------------------------------------------------------------------------------------------- Claude Code


def test_claude_help_states_its_newest_name_choices_and_levels() -> None:
    assert cli_models.parse_claude_help(CLAUDE_HELP) == (
        ["fable", "opus", "sonnet"],
        ["low", "medium", "high", "xhigh", "max"],
    )
    assert cli_models.parse_claude_help("nothing useful") == ([], [])


def test_claude_without_a_key_shows_its_own_choices_and_asks_for_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _installed(monkeypatch, "claude")
    _run(monkeypatch, CLAUDE_HELP)
    answer = cli_models.fetch_cli_capabilities("claude")
    assert [m["id"] for m in answer["models"]] == ["fable", "opus", "sonnet"]
    assert answer["thinking_levels"] == ["low", "medium", "high", "xhigh", "max"]
    assert "Anthropic key" in answer["note"] and answer["source"] == "app"
    assert (
        answer["features"][1]["description"]
        == "You can choose: Low, Medium, High, Extra high, Maximum."
    )


def test_claude_with_a_key_adds_the_exact_models_from_the_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _installed(monkeypatch, "claude")
    _run(monkeypatch, CLAUDE_HELP)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    entries = [
        ModelEntry(
            "claude-fable-9-0", "Claude Fable 9", 4_102_444_800.0, 1_000_000, ("low", "high")
        ),
        ModelEntry("claude-opus-9-0", "Claude Opus 9", 4_102_358_400.0, 200_000, ()),
    ]
    asked: list[Any] = []

    def fake_fetch(provider: str, key: str | None, *, refresh: bool = False) -> list[ModelEntry]:
        asked.append((provider, key, refresh))
        return entries

    monkeypatch.setattr(cli_models, "fetch_models", fake_fetch)
    answer = cli_models.fetch_cli_capabilities("claude", force_refresh=True)
    assert asked == [("anthropic", "sk-ant-test", True)]
    assert answer["source"] == "app_and_account"
    exact = answer["models"][3]
    assert exact["id"] == "claude-fable-9-0" and exact["released"] == "2100-01-01"
    assert exact["context_window"] == 1_000_000 and exact["thinking"]["levels"] == ["low", "high"]
    assert answer["note"] is None


def test_claude_account_failure_keeps_the_apps_choices_and_says_why(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _installed(monkeypatch, "claude")
    _run(monkeypatch, CLAUDE_HELP)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-bad")

    def refuse(*args: Any, **kwargs: Any) -> list[ModelEntry]:
        raise ModelCatalogError("The provider rejected this key.")

    monkeypatch.setattr(cli_models, "fetch_models", refuse)
    answer = cli_models.fetch_cli_capabilities("claude")
    assert len(answer["models"]) == 3 and "rejected this key" in answer["note"]


def test_the_models_call_keeps_release_date_size_and_thinking_levels() -> None:
    entry = _anthropic_entry(
        {
            "id": "claude-x",
            "display_name": "Claude X",
            "created_at": "2099-01-01T00:00:00Z",
            "max_input_tokens": 500000,
            "capabilities": {
                "effort": {"low": {"supported": True}, "max": {"supported": True}, "high": {}},
            },
        }
    )
    assert entry.max_input_tokens == 500000 and entry.effort_levels == ("low", "max")
    assert entry.as_dict()["effort_levels"] == ["low", "max"]
    bare = _anthropic_entry({"id": "claude-y"})
    assert bare.effort_levels == () and "effort_levels" not in bare.as_dict()


# ---------------------------------------------------------------------------- not installed, company, cache


def test_an_app_that_is_not_installed_lists_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_bridge,
        "list_cli_status",
        lambda force=False: [{"id": "codex", "installed": False, "version": None}],
    )
    answer = cli_models.fetch_cli_capabilities("codex")
    assert answer["models"] == [] and "Install this app first" in answer["note"]


def test_a_company_app_gets_no_invented_model(monkeypatch: pytest.MonkeyPatch) -> None:
    acme = replace(cli_bridge.SUPPORTED_AGENTS[0], id="acme", name="Acme", maker="Acme Corp")
    monkeypatch.setattr(cli_bridge, "get_agent", lambda agent_id: acme)
    monkeypatch.setattr(cli_bridge, "is_custom_agent", lambda agent_id: True)
    monkeypatch.setattr(
        cli_bridge,
        "list_cli_status",
        lambda force=False: [{"id": "acme", "installed": True, "version": "9"}],
    )
    answer = cli_models.fetch_cli_capabilities("acme")
    assert answer["models"] == [] and answer["is_custom"] is True
    assert answer["note"] == "This app chooses its own model."


def test_an_unknown_app_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown AI app: nope"):
        cli_models.fetch_cli_capabilities("nope")


def test_a_good_answer_is_remembered_and_refresh_asks_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _installed(monkeypatch, "codex")
    ran = _run(monkeypatch, json.dumps(CODEX_PAYLOAD))
    first = cli_models.fetch_cli_capabilities("codex")
    again = cli_models.fetch_cli_capabilities("codex")
    assert len(ran) == 1 and again["last_fetched"] == first["last_fetched"]
    cli_models.fetch_cli_capabilities("codex", force_refresh=True)
    assert len(ran) == 2


def test_a_failed_read_is_not_remembered(monkeypatch: pytest.MonkeyPatch) -> None:
    _installed(monkeypatch, "codex")
    ran = _run(monkeypatch, "", code=1)
    monkeypatch.setattr(Path, "home", lambda: Path("Z:/no-such-home"))
    cli_models.fetch_cli_capabilities("codex")
    cli_models.fetch_cli_capabilities("codex")
    assert len(ran) == 2


def test_a_new_version_of_the_app_is_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    ran = _run(monkeypatch, json.dumps(CODEX_PAYLOAD))
    _installed(monkeypatch, "codex", "1.0.0")
    cli_models.fetch_cli_capabilities("codex")
    cli_models.fetch_cli_capabilities("codex")
    assert len(ran) == 1
    _installed(monkeypatch, "codex", "2.0.0")  # updated: the old list belongs to the old version
    cli_models.fetch_cli_capabilities("codex")
    assert len(ran) == 2


# ------------------------------------------------------------------------------------------------- route


def test_the_capabilities_route_passes_refresh_through(monkeypatch: pytest.MonkeyPatch) -> None:
    from quant_system.server.v2 import router

    seen: list[tuple[str, bool]] = []

    def fake(agent_id: str, force_refresh: bool = False) -> dict[str, Any]:
        if agent_id == "nope":
            raise ValueError("Unknown AI app: nope")
        seen.append((agent_id, force_refresh))
        return {"agent_id": agent_id, "models": []}

    monkeypatch.setattr(router, "fetch_cli_capabilities", fake)
    client = TestClient(app, base_url="http://localhost:8000")
    assert client.get("/api/v2/cli/codex/capabilities").status_code == 200
    assert client.get("/api/v2/cli/codex/capabilities?refresh=true").status_code == 200
    assert seen == [("codex", False), ("codex", True)]
    assert client.get("/api/v2/cli/nope/capabilities").status_code == 404
