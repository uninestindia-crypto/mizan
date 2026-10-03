"""Tests for the Agent CLI Bridge service and API endpoints."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
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
    assert "gemini" in agent_ids


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
        assert "install_cmd" in item
        assert "signin_cmd" in item
        assert "run_cmd" in item


def test_auth_detection_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    status_list = list_cli_status(force=True)
    claude_info = next(item for item in status_list if item["id"] == "claude")
    assert claude_info["authenticated"] is True
    assert "ANTHROPIC_API_KEY" in claude_info["auth_detail"]


def test_launch_agent_session_run_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    monkeypatch.setattr("quant_system.server.v2.cli_bridge.find_windows_terminal", lambda: "C:\\wt.exe")

    res = launch_agent_session("antigravity", action="run")
    assert res["success"] is True
    assert res["action"] == "run"
    assert res["command"] == "agy"
    assert mock_popen.called


def test_launch_agent_session_signin_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    monkeypatch.setattr("quant_system.server.v2.cli_bridge.find_windows_terminal", lambda: None)

    res = launch_agent_session("codex", action="signin")
    assert res["success"] is True
    assert res["action"] == "signin"
    assert res["command"] == "codex login"
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


def test_cli_launch_api_endpoint(client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
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
