"""Tests for the Agent CLI Bridge service and API endpoints."""

from __future__ import annotations

import re
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import cli_bridge, cli_models
from quant_system.server.v2.cli_bridge import (
    SUPPORTED_AGENTS,
    launch_agent_session,
    list_cli_status,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://localhost:8000")


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    return {"X-CSRF-Token": token}


def test_supported_agents_registry() -> None:
    agent_ids = [a.id for a in SUPPORTED_AGENTS]
    assert "antigravity" in agent_ids
    assert "codex" in agent_ids
    assert "claude" in agent_ids
    assert "gemini" not in agent_ids


def _everything_an_app_card_says(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Each app's name, install steps and the sentences a finished install, sign-in and missing program leave."""
    monkeypatch.setattr(cli_bridge, "_find", lambda command: f"/bin/{command}")
    monkeypatch.setattr(cli_bridge, "_stream", lambda job, args, timeout: 0)
    monkeypatch.setattr(cli_bridge, "invalidate_cache", lambda: None)
    monkeypatch.setattr(cli_bridge, "_check_auth_status", lambda agent, executable: (True, ""))
    monkeypatch.setattr(cli_bridge, "_probe_results", {})
    shown: dict[str, list[str]] = {}
    for agent in SUPPORTED_AGENTS:
        installed = cli_bridge._Job(agent.id, "install")
        cli_bridge._run_install(installed, agent)
        signed_in = cli_bridge._Job(agent.id, "signin", output=['{"status": "SUCCESS"}'])
        cli_bridge._run_signin(signed_in, agent)
        shown[agent.id] = [
            agent.name,
            *(step.label for step in agent.install),
            installed.message,
            signed_in.message,
        ]
    monkeypatch.setattr(cli_bridge, "_find", lambda command: None)
    for agent in SUPPORTED_AGENTS:
        missing = cli_bridge._Job(agent.id, "signin")
        cli_bridge._run_signin(missing, agent)
        shown[agent.id].append(missing.message)
    return shown


def test_the_sentences_an_app_card_shows_name_each_app_in_plain_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown = _everything_an_app_card_says(monkeypatch)
    assert shown["codex"][-3:-1] == ["Codex is installed.", "Codex is connected."]
    assert shown["antigravity"][-3:-1] == ["Antigravity is installed.", "Antigravity is connected."]
    assert shown["antigravity"][-1] == "Antigravity is not installed yet."
    assert shown["antigravity"][1] == "Downloading the official Antigravity installer"


def test_nothing_a_person_reads_uses_the_developers_word_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    words = [text for texts in _everything_an_app_card_says(monkeypatch).values() for text in texts]
    assert len(words) > 12
    assert [text for text in words if re.search(r"\bCLI\b", text)] == []


def test_an_unknown_app_is_named_in_plain_words() -> None:
    with pytest.raises(ValueError, match="Unknown AI app: nope"):
        cli_bridge.start_agent_job("nope", "install")
    with pytest.raises(ValueError, match="Unknown AI app: nope"):
        launch_agent_session("nope")


def test_list_cli_status_returns_all_agents() -> None:
    status_list = list_cli_status(force=True)
    ids = [item["id"] for item in status_list]
    assert "antigravity" in ids
    assert "codex" in ids
    assert "claude" in ids
    for item in status_list:
        assert "name" in item
        assert "installed" in item
        assert "authenticated" in item
        assert item["install_steps"]
        assert "run_cmd" in item
        assert item["state"] in ("NOT_INSTALLED", "NEEDS_SIGN_IN", "CONNECTED", "UNKNOWN")


def test_auth_detection_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setattr(cli_bridge, "_find", lambda command: r"C:\claude.exe")
    monkeypatch.setattr(cli_bridge, "_run_hidden", lambda args, **kw: (1, "Not logged in"))
    status_list = list_cli_status(force=True)
    claude_info = next(item for item in status_list if item["id"] == "claude")
    assert claude_info["authenticated"] is True
    assert claude_info["state"] == "CONNECTED"
    assert "ANTHROPIC_API_KEY" in claude_info["auth_detail"]
    cli_bridge.invalidate_cache()


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="opens Windows terminal windows; the app is a Windows desktop app",
)
def test_launch_agent_session_run_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    monkeypatch.setattr(
        "quant_system.server.v2.cli_bridge.find_windows_terminal", lambda: "C:\\wt.exe"
    )

    res = launch_agent_session("antigravity", action="run")
    assert res["success"] is True
    assert res["action"] == "run"
    assert res["command"] == "agy"
    assert mock_popen.called


def test_cli_status_api_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v2/cli/status")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    agent_ids = [d["id"] for d in data]
    assert "antigravity" in agent_ids
    assert "codex" in agent_ids
    assert "claude" in agent_ids


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="opens Windows terminal windows; the app is a Windows desktop app",
)
def test_cli_launch_api_endpoint(
    client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    resp = client.post(
        "/api/v2/cli/launch",
        json={"agent_id": "claude", "action": "run"},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True
    assert res_data["command"] == "claude"


def test_cli_capabilities_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The list is whatever the app itself says today, so a made-up name appears only if the app printed it."""
    monkeypatch.setattr(
        cli_bridge,
        "list_cli_status",
        lambda force=False: [
            {"id": "antigravity", "installed": True, "authenticated": True, "version": "1.3.3"}
        ],
    )
    monkeypatch.setattr(cli_models, "_executable", lambda agent: "C:\\agy.exe")
    monkeypatch.setattr(
        cli_models,
        "_capture",
        lambda args, timeout, merge=False: (0, "gemini-9-flash-high\tGemini 9 Flash (High)\n"),
    )
    cli_models.clear_cache()
    data = client.get("/api/v2/cli/antigravity/capabilities").json()
    assert data["agent_id"] == "antigravity"
    assert [m["id"] for m in data["models"]] == ["gemini-9-flash"]
    assert data["thinking_levels"] == ["high"] and data["source"] == "app"
    assert "models" in data and "features" in data
    assert not any(f["name"] == "Quant Model Governance & Invariants" for f in data["features"])
    cli_models.clear_cache()


def test_cli_auto_update_endpoints(client: TestClient, headers: dict[str, str]) -> None:
    get_res = client.get("/api/v2/cli/auto-update")
    assert get_res.status_code == 200
    assert "auto_update_cli" in get_res.json()

    post_res = client.post("/api/v2/cli/auto-update", json={"enabled": True}, headers=headers)
    assert post_res.status_code == 200
    assert post_res.json()["auto_update_cli"] is True


def test_custom_cli_endpoints_crud(client: TestClient, headers: dict[str, str]) -> None:
    # 1. Initial list
    res = client.get("/api/v2/cli/custom")
    assert res.status_code == 200
    initial_items = res.json()
    assert isinstance(initial_items, list)

    # 2. Add custom CLI
    new_cli = {
        "id": "acme-copilot",
        "name": "Acme Copilot",
        "maker": "Acme Corp",
        "command": "acme-cli",
        "install_cmd": "curl -sL https://acme.test/install.sh | bash",
        "update_cmd": "acme-cli update",
        "description": "Enterprise trading assistant CLI",
        "docs_url": "https://acme.test/docs",
        "status_args": "--version",
        "auto_update": True,
    }
    create_res = client.post("/api/v2/cli/custom", json=new_cli, headers=headers)
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"] == "acme-copilot"
    assert created["name"] == "Acme Copilot"

    # 3. Check listed in custom endpoint
    list_res = client.get("/api/v2/cli/custom")
    assert list_res.status_code == 200
    ids = [c["id"] for c in list_res.json()]
    assert "acme-copilot" in ids

    # 4. Check included in /cli/status with is_custom=True
    status_res = client.get("/api/v2/cli/status")
    assert status_res.status_code == 200
    status_agents = {a["id"]: a for a in status_res.json()}
    assert "acme-copilot" in status_agents
    assert status_agents["acme-copilot"]["is_custom"] is True

    # 5. Toggle auto update
    toggle_res = client.post(
        "/api/v2/cli/custom/acme-copilot/auto-update", json={"enabled": False}, headers=headers
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["auto_update"] == 0

    # 6. Delete custom CLI
    del_res = client.delete("/api/v2/cli/custom/acme-copilot", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 7. Confirm deleted
    after_del = client.get("/api/v2/cli/custom")
    assert "acme-copilot" not in [c["id"] for c in after_del.json()]
