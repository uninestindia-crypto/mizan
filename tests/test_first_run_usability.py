"""First-run usability: finding market data, live AI model names, one-click CLI install/sign-in."""

from __future__ import annotations

import json
import time
import urllib.error
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from quant_system.alpha import model_catalog
from quant_system.alpha.direct_providers import AnthropicClient, OpenAIClient
from quant_system.alpha.key_pool import ManagedKey
from quant_system.alpha.model_catalog import ModelCatalogError, ModelEntry
from quant_system.server.app import app
from quant_system.server.v2 import cli_bridge, paths, router
from quant_system.server.v2.credentials import SECRETS, with_saved_credentials
from tests.market_fixtures import build_standard_store


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    monkeypatch.setattr(paths, "data_scan", paths.DataFolderScan())
    router.reset_services()
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    router.reset_services()


@pytest.fixture()
def headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    return {"X-CSRF-Token": token}


# ---------------------------------------------------------------------------- market data


def test_a_scan_finds_data_nested_deep_and_skips_developer_folders(tmp_path: Path) -> None:
    deep = tmp_path / "Quant OS Project" / "quant_system" / "data"
    build_standard_store(deep)
    hidden = tmp_path / "node_modules" / "pkg" / "data"
    build_standard_store(hidden)  # inside a skipped folder: must not be offered

    found = paths.scan_for_data_folders([tmp_path], max_seconds=10.0)

    assert [folder for folder, _ in found] == [deep.resolve()]
    assert found[0][1] > 0


def test_a_scan_respects_its_depth_limit(tmp_path: Path) -> None:
    build_standard_store(tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "data")
    assert paths.scan_for_data_folders([tmp_path], max_seconds=10.0, max_depth=2) == []


@pytest.mark.parametrize("pick", ["root", "data", "evidence", "market-cache"])
def test_picking_any_folder_around_the_data_resolves_to_the_data_folder(
    tmp_path: Path, pick: str
) -> None:
    checkout = tmp_path / "checkout"
    data = checkout / "data"
    build_standard_store(data)
    chosen = {
        "root": checkout,
        "data": data,
        "evidence": data / "evidence",
        "market-cache": data / "evidence" / "market-cache",
    }[pick]
    assert paths.resolve_data_folder(chosen) == data.resolve()


def test_picking_a_folder_with_no_market_data_resolves_to_nothing(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    assert paths.resolve_data_folder(tmp_path / "empty") is None


def test_the_background_search_runs_on_its_own_and_reports_what_it_found(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = tmp_path / "somewhere" / "data"
    build_standard_store(found)
    monkeypatch.setattr(paths, "_user_folders", lambda: [tmp_path / "somewhere"])

    first = client.get("/api/v2/status").json()["data_folder"]
    assert first["scan"] in ("RUNNING", "DONE")

    deadline = time.monotonic() + 15
    body: dict[str, Any] = {}
    while time.monotonic() < deadline:
        body = client.get("/api/v2/status").json()["data_folder"]
        if body["scan"] == "DONE":
            break
        time.sleep(0.1)
    assert body["scan"] == "DONE"
    assert [c["path"] for c in body["candidates"]] == [str(found.resolve())]


def test_the_folder_picker_endpoint_returns_the_chosen_path_or_null(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(router, "pick_folder", lambda title, initial: "D:\\Chosen")
    assert client.post("/api/v2/system/pick-folder", json={}, headers=headers).json() == {
        "path": "D:\\Chosen"
    }
    monkeypatch.setattr(router, "pick_folder", lambda title, initial: None)
    assert client.post("/api/v2/system/pick-folder", json={}, headers=headers).json() == {
        "path": None
    }


def test_a_folder_dialog_failure_is_a_readable_error(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(title: str, initial: str | None) -> str | None:
        raise router.FolderPickerError("no dialog here")

    monkeypatch.setattr(router, "pick_folder", broken)
    response = client.post("/api/v2/system/pick-folder", json={}, headers=headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "FOLDER_DIALOG_UNAVAILABLE"


def test_choosing_the_parent_of_the_data_folder_is_accepted(
    client: TestClient, headers: dict[str, str], tmp_path: Path
) -> None:
    checkout = tmp_path / "checkout"
    build_standard_store(checkout / "data")
    response = client.post("/api/v2/data/folder", json={"path": str(checkout)}, headers=headers)
    assert response.status_code == 200
    assert response.json()["data_folder"] == str((checkout / "data").resolve())


# ------------------------------------------------------------------------------ AI models


def _fake_http(payloads: dict[str, Any]) -> Callable[[str, dict[str, str], float], Any]:
    def get_json(url: str, headers: dict[str, str], timeout: float) -> Any:
        for fragment, payload in payloads.items():
            if fragment in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise AssertionError(f"unexpected URL {url}")

    return get_json


@pytest.fixture(autouse=True)
def _fresh_catalog() -> Iterator[None]:
    model_catalog.clear_cache()
    yield
    model_catalog.clear_cache()


def test_anthropic_models_are_listed_newest_per_family(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "data": [
            {
                "id": "claude-opus-9-0-20991001",
                "display_name": "Claude Opus 9",
                "created_at": "2099-10-01T00:00:00Z",
            },
            {
                "id": "claude-sonnet-9-1-20990901",
                "display_name": "Claude Sonnet 9.1",
                "created_at": "2099-09-01T00:00:00Z",
            },
            {
                "id": "claude-sonnet-8-0-20980101",
                "display_name": "Claude Sonnet 8",
                "created_at": "2098-01-01T00:00:00Z",
            },
            {
                "id": "claude-haiku-9-0-20990801",
                "display_name": "Claude Haiku 9",
                "created_at": "2099-08-01T00:00:00Z",
            },
        ]
    }
    monkeypatch.setattr(model_catalog, "_get_json", _fake_http({"anthropic.com": payload}))
    models = model_catalog.fetch_models("anthropic", "sk-test")
    newest = model_catalog.newest_models("anthropic", models)
    assert [m.name for m in newest] == ["Claude Opus 9", "Claude Sonnet 9.1", "Claude Haiku 9"]
    assert model_catalog.latest_model_id("anthropic", "sk-test", prefer=("sonnet",)) == (
        "claude-sonnet-9-1-20990901"
    )


def test_openai_list_drops_non_chat_models_snapshots_and_fine_tunes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "data": [
            {"id": "gpt-9", "created": 300},
            {"id": "gpt-9-2099-01-01", "created": 301},  # dated copy of gpt-9
            {"id": "text-embedding-9", "created": 400},
            {"id": "gpt-9-mini-tts", "created": 400},
            {"id": "ft:gpt-9:acme::abc", "created": 500},
            {"id": "o9", "created": 200},
        ]
    }
    monkeypatch.setattr(model_catalog, "_get_json", _fake_http({"openai.com": payload}))
    assert [m.id for m in model_catalog.fetch_models("openai", "sk-test")] == ["gpt-9", "o9"]


def test_gemini_sorts_by_version_then_tier_and_sends_the_key_in_a_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def get_json(url: str, headers: dict[str, str], timeout: float) -> Any:
        seen["url"], seen["headers"] = url, headers
        return {
            "models": [
                {
                    "name": "models/gemini-2.5-pro",
                    "displayName": "Gemini 2.5 Pro",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-3.1-flash",
                    "displayName": "Gemini 3.1 Flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-3.1-pro",
                    "displayName": "Gemini 3.1 Pro",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-embedding-1",
                    "displayName": "Embedding",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }

    monkeypatch.setattr(model_catalog, "_get_json", get_json)
    models = model_catalog.fetch_models("gemini", "AIza-secret")
    assert [m.id for m in models] == ["gemini-3.1-pro", "gemini-3.1-flash", "gemini-2.5-pro"]
    assert "AIza-secret" not in seen["url"]
    assert seen["headers"]["x-goog-api-key"] == "AIza-secret"


def test_a_missing_key_or_a_rejected_key_is_a_plain_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ModelCatalogError, match="API key"):
        model_catalog.fetch_models("openai", None)
    rejected = urllib.error.HTTPError("u", 401, "Unauthorized", None, None)  # type: ignore[arg-type]
    monkeypatch.setattr(model_catalog, "_get_json", _fake_http({"openai.com": rejected}))
    with pytest.raises(ModelCatalogError, match="rejected"):
        model_catalog.fetch_models("openai", "sk-bad")
    with pytest.raises(ModelCatalogError, match="Unknown provider"):
        model_catalog.fetch_models("nope", "x")


def test_the_model_list_is_cached_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = MagicMock(return_value={"data": [{"id": "gpt-9", "created": 1}]})
    monkeypatch.setattr(model_catalog, "_get_json", lambda *a: calls(*a))
    model_catalog.fetch_models("openai", "sk-a")
    model_catalog.fetch_models("openai", "sk-a")
    assert calls.call_count == 1
    model_catalog.fetch_models("openai", "sk-b")
    assert calls.call_count == 2


def test_the_models_endpoint_reads_the_saved_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-saved")
    monkeypatch.setattr(
        router,
        "fetch_models",
        lambda provider, key, refresh=False: (
            [ModelEntry("claude-opus-9", "Claude Opus 9", 1.0)] if key == "sk-ant-saved" else []
        ),
    )
    body = client.get("/api/v2/ai/models/anthropic").json()
    assert body["newest"][0]["name"] == "Claude Opus 9" and body["total"] == 1
    assert client.get("/api/v2/ai/models/not-a-provider").status_code == 404


def test_the_models_endpoint_explains_a_missing_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    response = client.get("/api/v2/ai/models/groq")
    assert response.status_code == 400 and response.json()["error"]["code"] == "MODELS_UNAVAILABLE"


def test_clients_pick_the_newest_model_themselves_and_an_explicit_model_still_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, tuple[str, ...]]] = []

    def latest(provider: str, key: str | None, *, prefer: tuple[str, ...] = ()) -> str:
        seen.append((provider, prefer))
        return "newest-model"

    monkeypatch.setattr("quant_system.alpha.direct_providers.latest_model_id", latest)
    key = MagicMock(spec=ManagedKey)
    key.secret_value = "k"
    request = AnthropicClient().build_request("hi", key)
    assert json.loads(request.data or b"")["model"] == "newest-model"  # type: ignore[arg-type]
    assert seen == [("anthropic", ("sonnet",))]
    pinned = OpenAIClient(default_model="pinned").build_request("hi", key)
    assert json.loads(pinned.data or b"")["model"] == "pinned"  # type: ignore[arg-type]
    override = AnthropicClient().build_request("hi", key, model="chosen")
    assert json.loads(override.data or b"")["model"] == "chosen"  # type: ignore[arg-type]


def test_a_client_that_cannot_choose_a_model_reports_it_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def latest(provider: str, key: str | None, *, prefer: tuple[str, ...] = ()) -> str:
        raise ModelCatalogError("offline")

    monkeypatch.setattr("quant_system.alpha.direct_providers.latest_model_id", latest)
    key = MagicMock(spec=ManagedKey)
    key.secret_value = "k"
    text, status, _, error = AnthropicClient().execute("hi", key)
    assert text is None and status == 503 and "offline" in str(error)


def test_no_model_name_is_hard_coded_in_the_ai_provider_help_text() -> None:
    help_text = " ".join(s.help for s in SECRETS if s.group == "AI Cloud Providers")
    for stale in ("3.5", "3.7", "GPT-4", "o1", "1.5", "2.0", "V3", "R1", "Mixtral"):
        assert stale not in help_text


# ------------------------------------------------------------------------- saved keys


def test_a_saved_key_is_used_when_the_page_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-saved")
    assert with_saved_credentials({"OPENAI_API_KEY": ""})["OPENAI_API_KEY"] == "sk-saved"
    assert with_saved_credentials({"OPENAI_API_KEY": "sk-typed"})["OPENAI_API_KEY"] == "sk-typed"


def test_testing_a_saved_key_reaches_the_provider(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-saved")
    captured: dict[str, str] = {}

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"data": [{"id": "x"}]}'

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        captured["auth"] = request.get_header("Authorization")
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    body = client.post(
        "/api/v2/credentials/test",
        json={"provider": "openai", "credentials": {"OPENAI_API_KEY": ""}},
        headers=headers,
    ).json()
    assert body["valid"] is True and captured["auth"] == "Bearer sk-saved"


# ------------------------------------------------------------------------------ CLI bridge


def test_the_commands_match_each_vendors_documentation() -> None:
    agents = {a.id: a for a in cli_bridge.SUPPORTED_AGENTS}
    assert agents["antigravity"].install[0].argument == (
        "irm https://antigravity.google/cli/install.ps1 | iex"
    )
    assert agents["claude"].signin_args == ("auth", "login")
    assert agents["claude"].status_args == ("auth", "status")
    assert agents["codex"].signin_args == ("login",)
    assert agents["codex"].status_args == ("login", "status")
    # Nothing here may ask a person to type a command: browser sign-in never opens a terminal.
    assert all(a.signin_mode == "browser" for a in agents.values() if a.id != "gemini")


def test_a_cli_installed_a_moment_ago_is_found_without_restarting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "agy" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "agy.exe").write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert str(bin_dir) in cli_bridge.search_path().split(";")
    assert cli_bridge._find("agy") is not None


def test_sign_in_state_comes_from_the_cli_not_from_a_config_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".claude").mkdir()  # Claude's folder exists even when nobody is signed in
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    claude = next(a for a in cli_bridge.SUPPORTED_AGENTS if a.id == "claude")

    monkeypatch.setattr(cli_bridge, "_run_hidden", lambda args, **kw: (1, "Not logged in"))
    assert cli_bridge._check_auth_status(claude, "claude.exe") == (False, "Not signed in yet")

    monkeypatch.setattr(cli_bridge, "_run_hidden", lambda args, **kw: (0, "Logged in"))
    assert cli_bridge._check_auth_status(claude, "claude.exe") == (True, "Signed in")


def test_a_cli_with_no_status_command_is_unknown_not_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_bridge, "_probe_results", {})
    agy = next(a for a in cli_bridge.SUPPORTED_AGENTS if a.id == "antigravity")
    signed_in, _ = cli_bridge._check_auth_status(agy, "agy.exe")
    assert signed_in is None


def _wait_for_job(agent_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = cli_bridge.job_snapshot(agent_id)
        assert snapshot is not None
        if snapshot["state"] != "RUNNING":
            return snapshot
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_install_runs_in_the_background_and_ends_done_when_the_program_appears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[list[str]] = []

    def stream(job: Any, args: list[str], timeout: float) -> int:
        commands.append(args)
        return 0

    monkeypatch.setattr(cli_bridge, "_stream", stream)
    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\agy.exe")
    monkeypatch.setattr(cli_bridge, "_jobs", {})
    started = cli_bridge.start_agent_job("antigravity", "install")
    assert started["success"] is True and started["job"]["action"] == "install"
    done = _wait_for_job("antigravity")
    assert done["state"] == "DONE"
    assert "install.ps1" in commands[0][-1] and commands[0][0] == "powershell.exe"


def test_install_that_finishes_but_leaves_nothing_behind_is_reported_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_bridge, "_stream", lambda job, args, timeout: 0)
    monkeypatch.setattr(cli_bridge, "_find", lambda command: None)
    monkeypatch.setattr(cli_bridge, "_jobs", {})
    cli_bridge.start_agent_job("claude", "install")
    assert _wait_for_job("claude")["state"] == "FAILED"


def test_a_npm_tool_without_node_installs_node_first(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[list[str]] = []
    installed = {"npm": False}

    def find(command: str) -> str | None:
        if command == "npm":
            return "C:\\npm.cmd" if installed["npm"] else None
        if command == "winget":
            return "C:\\winget.exe"
        return "C:\\codex.cmd" if installed["npm"] else None

    def stream(job: Any, args: list[str], timeout: float) -> int:
        ran.append(args)
        if "winget" in args[0]:
            installed["npm"] = True
        return 0

    monkeypatch.setattr(cli_bridge, "_stream", stream)
    monkeypatch.setattr(cli_bridge, "_find", find)
    monkeypatch.setattr(cli_bridge, "_jobs", {})
    cli_bridge.start_agent_job("codex", "install")
    assert _wait_for_job("codex")["state"] == "DONE"
    assert "OpenJS.NodeJS.LTS" in ran[0] and ran[1][1:] == ["install", "-g", "@openai/codex"]


def test_signing_in_opens_no_terminal_and_ends_connected_when_the_cli_agrees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    popen = MagicMock()
    monkeypatch.setattr(cli_bridge.subprocess, "Popen", popen)
    ran: list[list[str]] = []
    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\codex.cmd")
    monkeypatch.setattr(cli_bridge, "_stream", lambda job, args, timeout: ran.append(args) or 0)
    monkeypatch.setattr(cli_bridge, "_check_auth_status", lambda agent, exe: (True, "Signed in"))
    monkeypatch.setattr(cli_bridge, "_jobs", {})
    cli_bridge.start_agent_job("codex", "signin")
    assert _wait_for_job("codex")["state"] == "DONE"
    assert ran == [["C:\\codex.cmd", "login"]]
    assert not popen.called


def test_signing_in_that_is_not_completed_is_failed_and_can_be_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\claude.exe")
    monkeypatch.setattr(cli_bridge, "_stream", lambda job, args, timeout: 1)
    monkeypatch.setattr(cli_bridge, "_check_auth_status", lambda agent, exe: (False, "no"))
    monkeypatch.setattr(cli_bridge, "_jobs", {})
    cli_bridge.start_agent_job("claude", "signin")
    assert _wait_for_job("claude")["state"] == "FAILED"
    cli_bridge.start_agent_job("claude", "signin")  # a failed job does not block a new one
    assert _wait_for_job("claude")["action"] == "signin"


def test_antigravity_sign_in_is_judged_by_its_own_json_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def stream(job: Any, args: list[str], timeout: float) -> int:
        job.output.append('{"conversation_id":"x","status":"SUCCESS","response":"OK\\n"}')
        return 0

    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\agy.exe")
    monkeypatch.setattr(cli_bridge, "_stream", stream)
    monkeypatch.setattr(cli_bridge, "_jobs", {})
    monkeypatch.setattr(cli_bridge, "_probe_results", {})
    cli_bridge.start_agent_job("antigravity", "signin")
    assert _wait_for_job("antigravity")["state"] == "DONE"
    assert cli_bridge._probe_results["antigravity"][1] is True


def test_a_second_click_joins_the_running_job_instead_of_starting_another(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    release = threading.Event()
    calls: list[int] = []

    def stream(job: Any, args: list[str], timeout: float) -> int:
        calls.append(1)
        release.wait(5)
        return 0

    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\codex.cmd")
    monkeypatch.setattr(cli_bridge, "_stream", stream)
    monkeypatch.setattr(cli_bridge, "_check_auth_status", lambda agent, exe: (True, "Signed in"))
    monkeypatch.setattr(cli_bridge, "_jobs", {})
    first = cli_bridge.start_agent_job("codex", "signin")
    second = cli_bridge.start_agent_job("codex", "signin")
    assert first["job"]["id"] == second["job"]["id"]
    release.set()
    _wait_for_job("codex")
    assert len(calls) == 1


def test_the_launch_endpoint_starts_a_job_for_install_and_signin(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[tuple[str, str]] = []

    def fake_start(agent_id: str, action: str) -> dict[str, Any]:
        started.append((agent_id, action))
        return {"success": True, "action": action, "job": {"state": "RUNNING"}, "message": "x"}

    monkeypatch.setattr(router, "start_agent_job", fake_start)
    for action in ("install", "signin"):
        response = client.post(
            "/api/v2/cli/launch", json={"agent_id": "codex", "action": action}, headers=headers
        )
        assert response.status_code == 200 and response.json()["job"]["state"] == "RUNNING"
    assert started == [("codex", "install"), ("codex", "signin")]


def test_gemini_sign_in_is_the_one_that_needs_a_terminal(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    popen = MagicMock()
    monkeypatch.setattr(cli_bridge.subprocess, "Popen", popen)
    monkeypatch.setattr(cli_bridge, "find_windows_terminal", lambda: None)
    response = client.post(
        "/api/v2/cli/launch", json={"agent_id": "gemini", "action": "signin"}, headers=headers
    )
    assert response.status_code == 200 and response.json()["command"] == "gemini"
    assert popen.called


def test_an_unknown_agent_is_refused(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v2/cli/launch", json={"agent_id": "nope", "action": "install"}, headers=headers
    )
    assert response.status_code == 400 and response.json()["error"]["code"] == "CLI_LAUNCH_FAILED"


def test_a_gateway_lists_the_well_known_makers_not_whoever_published_last() -> None:
    models = [
        ModelEntry("unknown-lab/new-model", "Unknown", 900.0),
        ModelEntry("openai/gpt-9", "OpenAI: GPT-9", 800.0),
        ModelEntry("openai/gpt-8", "OpenAI: GPT-8", 700.0),
        ModelEntry("anthropic/claude-opus-9", "Anthropic: Opus 9", 600.0),
    ]
    newest = model_catalog.newest_models("openrouter", models)
    assert [m.name for m in newest] == ["OpenAI: GPT-9", "Anthropic: Opus 9"]


def test_a_sign_in_code_reaches_only_a_running_sign_in_that_asked_for_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[str] = []

    class _Stdin:
        def write(self, text: str) -> None:
            written.append(text)

        def flush(self) -> None:
            return None

    class _Process:
        stdin = _Stdin()

    job = cli_bridge._Job(agent_id="claude", action="signin", interactive=True)
    job.process = _Process()  # type: ignore[assignment]
    monkeypatch.setattr(cli_bridge, "_jobs", {"claude": job})
    assert cli_bridge.send_job_input("claude", " abc-123 ") is True
    assert written == ["abc-123\n"]
    job.interactive = False
    assert cli_bridge.send_job_input("claude", "x") is False
    job.interactive, job.state = True, "DONE"
    assert cli_bridge.send_job_input("claude", "x") is False
    assert cli_bridge.send_job_input("codex", "x") is False


def test_only_claude_signs_in_with_a_pasted_code() -> None:
    assert [a.id for a in cli_bridge.SUPPORTED_AGENTS if a.accepts_code] == ["claude"]


def test_the_code_endpoint_refuses_when_nothing_is_waiting(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post("/api/v2/cli/jobs/claude/input", json={"text": "abc"}, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_SIGN_IN_WAITING"


# ------------------------------------------------------------- keys never go into a file


@pytest.fixture()
def credential_client(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    import uuid

    from quant_system.server.v2.credentials import CredentialStore

    store = CredentialStore(prefix=f"QuantOS-test-{uuid.uuid4().hex[:8]}:")
    router.services().credentials = store
    yield client
    for secret in store.status():
        store.delete(str(secret["name"]))
    monkeypatch.delenv("HF_TOKEN", raising=False)


def test_saving_a_key_writes_nothing_to_a_dot_env_file(
    credential_client: TestClient, headers: dict[str, str], tmp_path: Path
) -> None:
    response = credential_client.put(
        "/api/v2/credentials/HF_TOKEN", json={"value": "hf_example_value"}, headers=headers
    )
    assert response.status_code == 200
    assert not (tmp_path / "app" / ".env").exists()


def test_removing_a_key_clears_only_its_own_leftover_line(
    credential_client: TestClient, headers: dict[str, str], tmp_path: Path
) -> None:
    env_file = tmp_path / "app" / ".env"
    credential_client.put(
        "/api/v2/credentials/HF_TOKEN", json={"value": "hf_example_value"}, headers=headers
    )
    credential_client.put(
        "/api/v2/credentials/GROQ_API_KEY", json={"value": "gsk_example"}, headers=headers
    )
    # What an older build left behind, plus the person's own settings.
    env_file.write_text(
        "PORT=8000\nHF_TOKEN=hf_example_value\nGROQ_API_KEY=my-own-different-value\n",
        encoding="utf-8",
    )
    credential_client.delete("/api/v2/credentials/HF_TOKEN", headers=headers)
    credential_client.delete("/api/v2/credentials/GROQ_API_KEY", headers=headers)
    assert (
        env_file.read_text(encoding="utf-8") == "PORT=8000\nGROQ_API_KEY=my-own-different-value\n"
    )


def test_scrubbing_leaves_a_file_alone_when_nothing_matches(tmp_path: Path) -> None:
    from quant_system.server.v2.credentials import scrub_mirrored_value

    env_file = tmp_path / ".env"
    env_file.write_bytes(b"A=1\r\nB=2\r\n")
    assert scrub_mirrored_value(env_file, "A", "other") is False
    assert scrub_mirrored_value(env_file, "A", None) is False
    assert scrub_mirrored_value(tmp_path / "missing.env", "A", "1") is False
    assert env_file.read_bytes() == b"A=1\r\nB=2\r\n"
    assert scrub_mirrored_value(env_file, "A", "1") is True
    assert env_file.read_bytes() == b"B=2\r\n"  # the other line and its line ending are untouched


# ------------------------------------------- every key the Settings page accepts is used


def test_the_key_pool_loads_gemini_deepseek_and_mistral_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from quant_system.alpha.key_pool import KeyPoolManager, ProviderType

    monkeypatch.setenv("GEMINI_API_KEY", "g-1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "d-1")
    monkeypatch.setenv("MISTRAL_API_KEYS", "m-1,m-2")
    pool = KeyPoolManager()
    pool.load_from_env()
    assert pool.get_active_key(ProviderType.GEMINI) is not None
    assert pool.get_active_key(ProviderType.DEEPSEEK) is not None
    assert [k.secret_value for k in pool.keys if k.provider == ProviderType.MISTRAL] == [
        "m-1",
        "m-2",
    ]


def _key(secret: str = "secret-value") -> Any:
    key = MagicMock(spec=ManagedKey)
    key.secret_value = secret
    return key


def test_every_provider_with_a_settings_card_has_a_client() -> None:
    from quant_system.alpha.direct_providers import get_direct_client_for_provider
    from quant_system.alpha.key_pool import ProviderType

    for provider in (
        ProviderType.OPENROUTER,
        ProviderType.GROQ,
        ProviderType.OPENAI,
        ProviderType.ANTHROPIC,
        ProviderType.GEMINI,
        ProviderType.DEEPSEEK,
        ProviderType.MISTRAL,
    ):
        assert get_direct_client_for_provider(provider) is not None


def test_deepseek_and_mistral_requests_name_the_newest_model_and_force_no_json_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from quant_system.alpha.direct_providers import DeepSeekClient, MistralClient

    seen: list[tuple[str, tuple[str, ...]]] = []

    def latest(provider: str, key: str | None, *, prefer: tuple[str, ...] = ()) -> str:
        seen.append((provider, prefer))
        return f"{provider}-newest"

    monkeypatch.setattr("quant_system.alpha.direct_providers.latest_model_id", latest)
    for client, url in (
        (DeepSeekClient(), "https://api.deepseek.com/chat/completions"),
        (MistralClient(), "https://api.mistral.ai/v1/chat/completions"),
    ):
        request = client.build_request("hello", _key("k"))
        body = json.loads(request.data or b"")  # type: ignore[arg-type]
        assert request.full_url == url
        assert request.get_header("Authorization") == "Bearer k"
        assert body["model"].endswith("-newest") and "response_format" not in body
        assert body["messages"][-1] == {"role": "user", "content": "hello"}
        assert (
            client.parse_response_content(b'{"choices": [{"message": {"content": "hi there"}}]}')
            == "hi there"
        )
    assert [p for p, _ in seen] == ["deepseek", "mistral"]


def test_gemini_request_keeps_the_key_out_of_the_url_and_reads_the_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from quant_system.alpha.direct_providers import GeminiClient

    monkeypatch.setattr(
        "quant_system.alpha.direct_providers.latest_model_id",
        lambda provider, key, *, prefer=(): "gemini-9-flash",
    )
    client = GeminiClient()
    request = client.build_request("hello", _key("AIza-secret"))
    assert request.full_url.endswith("/models/gemini-9-flash:generateContent")
    assert "AIza-secret" not in request.full_url
    assert request.get_header("X-goog-api-key") == "AIza-secret"
    reply = b'{"candidates": [{"content": {"parts": [{"text": "Hel"}, {"text": "lo"}]}}]}'
    assert client.parse_response_content(reply) == "Hello"
    assert client.parse_response_content(b'{"candidates": []}') == ""


def test_the_assistant_falls_back_to_the_new_providers() -> None:
    import inspect

    from quant_system.assistant import service

    source = inspect.getsource(service)
    for name in ("GEMINI", "DEEPSEEK", "MISTRAL"):
        assert f"ProviderType.{name}" in source


# ------------------------------------------------------------------ downloading the data


def test_the_download_api_starts_reports_and_stops(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from quant_system.market.downloader import MarketDownload

    started: list[Path] = []
    monkeypatch.setattr(
        MarketDownload, "start", lambda self, folder, **kw: started.append(folder) or True
    )
    body = client.post("/api/v2/data/download", headers=headers).json()
    assert body["started"] is True
    assert started == [paths.app_root() / "data"]  # inside the install folder, never another drive
    assert client.get("/api/v2/data/download").json()["state"] == "IDLE"
    assert client.get("/api/v2/status").json()["download"]["state"] == "IDLE"
    assert client.post("/api/v2/data/download/cancel", headers=headers).status_code == 200


def test_a_finished_download_is_connected_and_indexed_without_another_click(
    client: TestClient, tmp_path: Path
) -> None:
    folder = tmp_path / "downloaded" / "data"
    build_standard_store(folder)
    router._connect_downloaded_data(folder)
    router.services().job.wait(60)
    status = client.get("/api/v2/status").json()
    assert status["data_folder"]["valid"] is True
    assert status["index"]["ready"] is True and status["index"]["matches_folder"] is True


# ----------------------------------------- chat requests adapt to what the provider accepts


def _send_recorder(monkeypatch: pytest.MonkeyPatch, answers: list[Any]) -> list[dict[str, Any]]:
    """Replace the network: record each JSON body sent, answer from ``answers`` in order."""
    sent: list[dict[str, Any]] = []

    class _Response:
        status = 200

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"choices": [{"message": {"content": "hello"}}]}'

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        sent.append(json.loads(request.data))
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return sent


def test_a_chat_request_does_not_force_json_mode_but_the_advisory_panel_still_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "quant_system.alpha.direct_providers.latest_model_id",
        lambda provider, key, *, prefer=(): "m",
    )
    sent = _send_recorder(monkeypatch, [None, None])
    advisory = OpenAIClient()
    assert advisory.execute("hi", _key())[0] == "hello"
    chat = OpenAIClient()
    chat.json_mode = False
    assert chat.execute("hi", _key())[0] == "hello"
    assert sent[0]["response_format"] == {"type": "json_object"}  # unchanged for the panel
    assert "response_format" not in sent[1]


def test_a_model_that_refuses_a_temperature_is_retried_once_without_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io

    monkeypatch.setattr(
        "quant_system.alpha.direct_providers.latest_model_id",
        lambda provider, key, *, prefer=(): "reasoning-model",
    )
    refusal = urllib.error.HTTPError(
        "u",
        400,
        "Bad Request",
        {},  # type: ignore[arg-type]
        io.BytesIO(b"Unsupported value: 'temperature' does not support 0.1 with this model."),
    )
    sent = _send_recorder(monkeypatch, [refusal, None])
    client = OpenAIClient()
    text, status, _, _ = client.execute("hi", _key())
    assert (text, status) == ("hello", 200)
    assert "temperature" in sent[0] and "temperature" not in sent[1]
    assert client.omit_temperature is True  # remembered for the next question


def test_other_client_errors_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setattr(
        "quant_system.alpha.direct_providers.latest_model_id",
        lambda provider, key, *, prefer=(): "m",
    )
    bad_key = urllib.error.HTTPError(
        "u",
        401,
        "Unauthorized",
        {},
        io.BytesIO(b"invalid key"),  # type: ignore[arg-type]
    )
    sent = _send_recorder(monkeypatch, [bad_key])
    text, status, _, error = OpenAIClient().execute("hi", _key())
    assert text is None and status == 401 and "invalid key" in str(error)
    assert len(sent) == 1


def test_the_assistant_asks_for_prose_not_json() -> None:
    import inspect

    from quant_system.assistant import service

    assert "client.json_mode = False" in inspect.getsource(service)
