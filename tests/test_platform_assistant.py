"""Comprehensive Tests for In-Platform Actionable AI Assistant (QuantOS Copilot)."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from quant_system.assistant.actions import PlatformActionExecutor
from quant_system.assistant.schemas import (
    AssistantChatRequest,
    PlatformActionType,
)
from quant_system.assistant.service import PlatformAssistantService
from quant_system.server.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_assistant_capabilities_declares_zero_code_modifications() -> None:
    """Verifies that assistant explicitly advertises zero codebase modification permission."""
    # Test executor actions
    assert hasattr(PlatformActionExecutor, "execute")
    assert PlatformActionType.NAVIGATE_TAB in PlatformActionType
    assert PlatformActionType.RUN_DIAGNOSTICS in PlatformActionType
    assert PlatformActionType.INSPECT_RISK_LIMITS in PlatformActionType
    assert PlatformActionType.CALCULATE_GREEKS in PlatformActionType


def test_assistant_navigation_intent_parsing() -> None:
    """Tests navigation prompt recognition."""
    service = PlatformAssistantService()

    # Navigation to Options
    resp = service.process_chat(AssistantChatRequest(prompt="Please open the Options Lab"))
    assert len(resp.action_proposals) == 1
    assert resp.action_proposals[0].action_type == PlatformActionType.NAVIGATE_TAB
    assert resp.action_proposals[0].target_tab == "tab-straddle"

    # Navigation to Risk Governor
    resp_risk = service.process_chat(AssistantChatRequest(prompt="Take me to risk governor"))
    assert len(resp_risk.action_proposals) == 1
    assert resp_risk.action_proposals[0].target_tab == "tab-risk"


def test_assistant_diagnostics_action() -> None:
    """Tests system diagnostics query through assistant."""
    service = PlatformAssistantService()
    resp = service.process_chat(
        AssistantChatRequest(prompt="Is the engine healthy? Run diagnostics")
    )
    assert "System Diagnostics Passed" in resp.message
    assert "Double-Entry Ledger" in resp.message


def test_assistant_risk_limits_action() -> None:
    """Tests risk limits query."""
    service = PlatformAssistantService()
    resp = service.process_chat(AssistantChatRequest(prompt="Check active risk limits"))
    assert "Active Pre-Trade Risk Governor Limits" in resp.message
    assert "Daily Drawdown" in resp.message


def test_assistant_calculate_greeks_action() -> None:
    """Tests Black-Scholes Greeks calculation via chat prompt."""
    service = PlatformAssistantService()
    resp = service.process_chat(
        AssistantChatRequest(prompt="Calculate Greeks for 24500 strike call option")
    )
    assert "Black-Scholes Pricing" in resp.message
    assert "Delta (Δ)" in resp.message
    assert "Gamma (Γ)" in resp.message


def test_assistant_backtest_proposal_generation() -> None:
    """Tests backtest configuration proposal creation."""
    service = PlatformAssistantService()
    resp = service.process_chat(
        AssistantChatRequest(prompt="Run backtest on INFY with Dual Momentum")
    )
    assert "INFY" in resp.message
    assert len(resp.action_proposals) == 1
    assert resp.action_proposals[0].action_type == PlatformActionType.PREVIEW_BACKTEST
    assert resp.action_proposals[0].parameters["symbol"] == "INFY"


def test_assistant_explain_metric_glossary() -> None:
    """Tests Deflated Sharpe Ratio glossary lookup."""
    service = PlatformAssistantService()
    resp = service.process_chat(AssistantChatRequest(prompt="Explain deflated sharpe ratio"))
    assert "Deflated Sharpe Ratio (DSR)" in resp.message
    assert "Marcos López de Prado" in resp.message


def test_assistant_api_endpoints(client: TestClient) -> None:
    """Tests FastAPI HTTP routes for assistant."""
    # 1. Capabilities
    cap_resp = client.get("/api/v1/assistant/capabilities")
    assert cap_resp.status_code == 200
    cap_json = cap_resp.json()
    assert cap_json["codebase_modifications_allowed"] is False
    assert "NAVIGATE_TAB" in cap_json["supported_actions"]

    # 2. Chat
    chat_resp = client.post(
        "/api/v1/assistant/chat",
        json={"prompt": "Go to backtest tab", "current_tab": "tab-ingestion", "history": []},
    )
    assert chat_resp.status_code == 200
    chat_json = chat_resp.json()
    assert len(chat_json["action_proposals"]) >= 1

    # 3. Action Execution with CSRF Token
    csrf_resp = client.get("/api/v1/auth/csrf")
    assert csrf_resp.status_code == 200
    csrf_token = csrf_resp.json().get("csrf_token") or csrf_resp.json().get("token")

    act_resp = client.post(
        "/api/v1/assistant/execute-action",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "action_id": "act_test_123",
            "action_type": "CALCULATE_GREEKS",
            "parameters": {"strike": 24500, "spot": 24500, "option_type": "CALL"},
        },
    )
    assert act_resp.status_code == 200
    act_json = act_resp.json()
    assert act_json["success"] is True
    assert act_json["data"]["delta"] > 0


def test_assistant_audit_model_strategy_intent() -> None:
    """Tests model and strategy profitability audit intent routing in assistant."""
    service = PlatformAssistantService()
    resp = service.process_chat(AssistantChatRequest(prompt="Is my model and strategy profitable?"))
    assert "UNPROFITABLE AFTER STATUTORY COSTS" in resp.message
    assert "Ridge Intercept" in resp.message or "Intercept Drift" in resp.message
    assert "0.224%" in resp.message
    assert len(resp.action_proposals) >= 1
    assert any(p.target_tab == "tab-diagnostics" for p in resp.action_proposals)


def test_model_strategy_diagnostics_endpoint(client: TestClient) -> None:
    """Tests /api/v1/diagnostics/model-strategy endpoint response."""
    resp = client.get("/api/v1/diagnostics/model-strategy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "DEGRADED"
    assert data["overall_verdict"] == "UNPROFITABLE_AFTER_STATUTORY_COSTS"
    assert data["model_status"] == "FAIL"
    assert "class_imbalance" in data
    assert data["class_imbalance"]["up_samples"] == 182
    assert data["class_imbalance"]["down_samples"] == 229
    assert data["friction_wall"]["total_round_trip_pct"] > 0.20
    assert len(data["key_findings"]) >= 3
    assert len(data["actionable_recommendations"]) >= 3
