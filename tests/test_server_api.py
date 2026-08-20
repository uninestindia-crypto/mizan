"""Tests for QuantOS FastAPI REST API Endpoints."""

import pytest
from fastapi.testclient import TestClient

from quant_system import __version__
from quant_system.server.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_api_version(client: TestClient) -> None:
    res = client.get("/api/version")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == __version__
    assert data["name"] == "QuantOS"
    assert data["status"] == "ONLINE"


def test_api_strategies(client: TestClient) -> None:
    res = client.get("/api/strategies")
    assert res.status_code == 200
    data = res.json()
    names = [s["name"] for s in data]
    assert "EquityDualMomentum" in names
    assert "IntradayATMStraddle" in names
    assert "DirectionalVerticalSpreads" in names


def test_api_risk_limits_get_and_post(client: TestClient) -> None:
    # Get current limits
    get_res = client.get("/api/risk/limits")
    assert get_res.status_code == 200
    init_data = get_res.json()
    assert "max_position_weight" in init_data

    # Update limits
    update_payload = {
        "max_position_weight": 0.20,
        "max_daily_drawdown_pct": 0.025,
        "max_total_drawdown_pct": 0.08,
        "max_portfolio_leverage": 1.0,
        "min_cash_buffer_pct": 0.06,
        "max_allowed_spread_pct": 0.01,
        "allow_naked_short": False,
    }
    post_res = client.post("/api/risk/limits", json=update_payload)
    assert post_res.status_code == 200
    updated = post_res.json()
    assert updated["max_position_weight"] == 0.20
    assert updated["max_daily_drawdown_pct"] == 0.025


def test_api_backtest_run(client: TestClient) -> None:
    payload = {
        "strategy_name": "EquityDualMomentum",
        "symbols": ["INFY", "TCS"],
        "days": 40,
        "initial_cash": 500000.0,
        "slippage_bps": 5.0,
        "params": {"lookback_fast": 5, "lookback_slow": 15, "top_n": 1},
    }
    res = client.post("/api/backtest/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["initial_cash"] == 500000.0
    assert len(data["equity_curve"]) == 40
    assert "stats" in data
    assert "tearsheet_markdown" in data


def test_api_straddle_simulate(client: TestClient) -> None:
    payload = {
        "spot_price": 24500.0,
        "volatility": 0.18,
        "days_to_expiry": 7,
        "risk_free_rate": 0.07,
        "quantity": 25,
    }
    res = client.post("/api/straddle/simulate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["atm_strike"] == 24500.0
    assert "call_greeks" in data
    assert "put_greeks" in data
    assert data["call_greeks"]["delta"] > 0
    assert data["put_greeks"]["delta"] < 0
    assert data["daily_theta_income"] > 0


def test_api_diagnostics(client: TestClient) -> None:
    res = client.get("/api/diagnostics")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["ledger_integrity_verified"] is True
    assert data["checks_passed"] == data["total_checks"]


def test_api_monte_carlo(client: TestClient) -> None:
    payload = {
        "strategy_name": "EquityDualMomentum",
        "num_simulations": 1000,
        "horizon_days": 100,
        "initial_capital": 1000000.0,
    }
    res = client.post("/api/monte-carlo/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["num_simulations"] == 1000
    assert len(data["percentile_50th"]) == 101
    assert "var_95_pct" in data
    assert "cvar_95_pct" in data


def test_api_portfolio_optimize(client: TestClient) -> None:
    payload = {
        "symbols": ["INFY", "TCS", "RELIANCE"],
        "days": 60,
        "risk_free_rate": 0.07,
    }
    res = client.post("/api/portfolio/optimize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["symbols"] == ["INFY", "TCS", "RELIANCE"]
    assert "max_sharpe_point" in data
    assert "min_variance_point" in data
    assert "risk_parity_weights" in data
