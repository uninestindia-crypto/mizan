"""Unit tests for expanded credentials and live connection testing."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2.credentials import (
    SECRETS,
    verify_credential_connection,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://localhost:8000")


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    return {"X-CSRF-Token": token}


def test_expanded_secrets_definitions() -> None:
    names = {s.name for s in SECRETS}
    # Indian stock brokers
    assert "UPSTOX_API_KEY" in names
    assert "UPSTOX_ACCESS_TOKEN" in names
    assert "KITE_API_KEY" in names
    assert "KITE_ACCESS_TOKEN" in names
    assert "ANGEL_API_KEY" in names
    assert "DHAN_CLIENT_ID" in names
    assert "FYERS_APP_ID" in names

    # AI Cloud providers
    assert "ANTHROPIC_API_KEY" in names
    assert "OPENAI_API_KEY" in names
    assert "GEMINI_API_KEY" in names
    assert "OPENROUTER_API_KEY" in names
    assert "GROQ_API_KEY" in names
    assert "DEEPSEEK_API_KEY" in names
    assert "CUSTOM_AI_BASE_URL" in names


def test_credential_verify_empty_keys() -> None:
    res = verify_credential_connection("openai", {})
    assert res["valid"] is False
    assert "empty" in res["message"].lower()

    res = verify_credential_connection("claude", {})
    assert res["valid"] is False
    assert "empty" in res["message"].lower()

    res = verify_credential_connection("gemini", {})
    assert res["valid"] is False
    assert "empty" in res["message"].lower()


@patch("urllib.request.urlopen")
def test_credential_verify_openai_success(mock_urlopen: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"data": [{"id": "gpt-4o"}, {"id": "o1"}]}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = verify_credential_connection("openai", {"OPENAI_API_KEY": "sk-test-openai-key"})
    assert res["valid"] is True
    assert "Connected" in res["message"]
    assert "2 models" in res["message"]


@patch("urllib.request.urlopen")
def test_credential_verify_upstox_success(mock_urlopen: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"data": {"user_name": "Ravi Trader"}}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    res = verify_credential_connection("upstox", {"UPSTOX_ACCESS_TOKEN": "mock_upstox_token"})
    assert res["valid"] is True
    assert "Connected as Ravi Trader" in res["message"]


def test_test_credential_api_endpoint(client: TestClient, headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/v2/credentials/test",
        json={"provider": "unknown_provider", "credentials": {}},
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["valid"] is False
    assert "Unknown provider" in res_data["message"]
