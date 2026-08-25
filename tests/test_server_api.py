"""Tests for QuantOS FastAPI REST API Endpoints and Local Trust Boundary."""

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system import __version__
from quant_system.data.provenance import ACCESS_TOKEN_ENV_VAR, RuntimeDataSource, describe
from quant_system.server.app import app
from quant_system.server.supervisor import supervisor


@pytest.fixture(autouse=True)
def cleanup_supervisor() -> Any:
    """Ensures supervisor is cleaned up before and after each test."""
    supervisor.shutdown()
    with supervisor._lock:
        supervisor._operations.clear()
        supervisor._idempotency_map.clear()
        supervisor._active_op_id = None
        supervisor._active_process = None
        supervisor._active_queue = None
        supervisor._active_cancel_event = None
    yield
    supervisor.shutdown()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def csrf_token(client: TestClient) -> str:
    res = client.get("/api/v1/csrf-token")
    assert res.status_code == 200
    token = res.json()["csrf_token"]
    assert isinstance(token, str)
    assert len(token) > 10
    return token


@pytest.fixture
def auth_headers(csrf_token: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf_token}


# =====================================================================
# Version and Strategy Discovery Tests
# =====================================================================


# test-allow: loop-in-test — Parity check across legacy and versioned paths
def test_api_version(client: TestClient) -> None:
    for path in ["/api/v1/version", "/api/version"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["version"] == __version__
        assert data["name"] == "QuantOS"
        assert data["status"] == "ONLINE"


# test-allow: loop-in-test — Parity check across legacy and versioned paths
def test_api_strategies(client: TestClient) -> None:
    for path in ["/api/v1/strategies", "/api/strategies"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        names = [s["name"] for s in data]
        assert "EquityDualMomentum" in names
        assert "IntradayATMStraddle" in names
        assert "DirectionalVerticalSpreads" in names


# =====================================================================
# Anti-CSRF Protection & Token Verification Tests
# =====================================================================


# test-allow: loop-in-test — Parity check across legacy and versioned paths
def test_csrf_token_issuance(client: TestClient) -> None:
    for path in ["/api/v1/csrf-token", "/api/v1/auth/csrf", "/api/csrf-token", "/api/auth/csrf"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert "csrf_token" in data
        assert "expires_at" in data
        assert "message" in data


def test_state_mutating_endpoint_requires_csrf_token(client: TestClient) -> None:
    payload = {
        "max_position_weight": 0.20,
        "max_daily_drawdown_pct": 0.025,
        "max_total_drawdown_pct": 0.08,
        "max_portfolio_leverage": 1.0,
        "min_cash_buffer_pct": 0.06,
        "max_allowed_spread_pct": 0.01,
        "allow_naked_short": False,
    }
    # 1. Missing CSRF Token -> 403 Forbidden
    res = client.post("/api/v1/risk/limits", json=payload)
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "CSRF_TOKEN_MISSING"

    # 2. Invalid CSRF Token -> 403 Forbidden
    res = client.post(
        "/api/v1/risk/limits",
        json=payload,
        headers={"X-CSRF-Token": "invalid-token-123"},
    )
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "CSRF_TOKEN_INVALID"


def test_api_risk_limits_get_and_post(client: TestClient, auth_headers: dict[str, str]) -> None:
    get_res = client.get("/api/v1/risk/limits")
    assert get_res.status_code == 200
    init_data = get_res.json()
    assert "max_position_weight" in init_data

    update_payload = {
        "max_position_weight": 0.20,
        "max_daily_drawdown_pct": 0.025,
        "max_total_drawdown_pct": 0.08,
        "max_portfolio_leverage": 1.0,
        "min_cash_buffer_pct": 0.06,
        "max_allowed_spread_pct": 0.01,
        "allow_naked_short": False,
    }
    post_res = client.post("/api/v1/risk/limits", json=update_payload, headers=auth_headers)
    assert post_res.status_code == 200
    updated = post_res.json()
    assert updated["max_position_weight"] == 0.20
    assert updated["max_daily_drawdown_pct"] == 0.025


# =====================================================================
# Host Header Validation (DNS Rebinding Defense) Tests
# =====================================================================


@pytest.mark.parametrize(
    "valid_host",
    [
        "localhost",
        "127.0.0.1",
        "localhost:8000",
        "127.0.0.1:8000",
        "[::1]",
        "[::1]:8080",
        "testserver",
    ],
)
def test_valid_loopback_host_header_allowed(client: TestClient, valid_host: str) -> None:
    res = client.get("/api/v1/version", headers={"Host": valid_host})
    assert res.status_code == 200


@pytest.mark.parametrize(
    "hostile_host",
    [
        "evil.com",
        "attacker.org",
        "192.168.1.100",
        "10.0.0.1",
        "0.0.0.0",
        "dns-rebind.attacker.net:8000",
        "quantos.malicious.site",
    ],
)
def test_hostile_host_header_rejected(client: TestClient, hostile_host: str) -> None:
    res = client.get("/api/v1/version", headers={"Host": hostile_host})
    assert res.status_code == 400
    err = res.json()["error"]
    assert err["code"] == "INVALID_HOST"
    assert "is not allowed" in err["message"]


# =====================================================================
# Strict CORS and Hostile Origin Defense Tests
# =====================================================================


@pytest.mark.parametrize(
    "valid_origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://localhost:8443",
        "http://[::1]:8080",
    ],
)
def test_valid_loopback_origin_cors_allowed(client: TestClient, valid_origin: str) -> None:
    # 1. Normal GET Request
    res = client.get("/api/v1/version", headers={"Origin": valid_origin})
    assert res.status_code == 200
    assert res.headers.get("Access-Control-Allow-Origin") == valid_origin
    assert res.headers.get("Access-Control-Allow-Credentials") == "true"

    # 2. OPTIONS Preflight
    preflight_res = client.options("/api/v1/version", headers={"Origin": valid_origin})
    assert preflight_res.status_code == 204
    assert preflight_res.headers.get("Access-Control-Allow-Origin") == valid_origin
    assert "GET" in preflight_res.headers.get("Access-Control-Allow-Methods", "")


@pytest.mark.parametrize(
    "hostile_origin",
    [
        "http://evil.com",
        "https://attacker.org",
        "http://malicious.website.local",
        "http://192.168.1.55:3000",
    ],
)
def test_hostile_origin_cors_rejected(client: TestClient, hostile_origin: str) -> None:
    # 1. Normal Request with Hostile Origin
    res = client.get("/api/v1/version", headers={"Origin": hostile_origin})
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "FORBIDDEN_ORIGIN"

    # 2. OPTIONS Preflight with Hostile Origin
    preflight_res = client.options("/api/v1/version", headers={"Origin": hostile_origin})
    assert preflight_res.status_code == 403
    err = preflight_res.json()["error"]
    assert err["code"] == "FORBIDDEN_ORIGIN"


# =====================================================================
# Security Headers and Unified Error Envelope Tests
# =====================================================================


def test_security_headers_present_on_all_responses(client: TestClient) -> None:
    res = client.get("/api/v1/version")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'self'" in res.headers.get("Content-Security-Policy", "")
    assert "no-store" in res.headers.get("Cache-Control", "")
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "X-Request-ID" in res.headers


def test_unified_error_envelope_format_on_404(client: TestClient) -> None:
    res = client.get("/api/v1/non-existent-endpoint")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    err = data["error"]
    assert "code" in err
    assert "message" in err
    assert "request_id" in err
    assert "timestamp" in err


# =====================================================================
# Input Bounds Enforcement (AC-76) Tests
# =====================================================================


def test_input_bounds_exceeded_symbols_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 6 symbols (limit is 5)
    payload = {
        "strategy_name": "EquityDualMomentum",
        "symbols": ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN"],
        "days": 40,
    }
    res = client.post("/api/v1/operations/backtest", json=payload, headers=auth_headers)
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"


def test_input_bounds_exceeded_days_rejected(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 3651 days (limit is 3650 / 10 years)
    payload = {
        "strategy_name": "EquityDualMomentum",
        "symbols": ["INFY", "TCS"],
        "days": 3651,
    }
    res = client.post("/api/v1/operations/backtest", json=payload, headers=auth_headers)
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"


# =====================================================================
# Asynchronous Operations API & Polling Tests (/api/v1/operations)
# =====================================================================


# test-allow: loop-in-test — Polling asynchronous worker process execution
def test_create_and_poll_backtest_operation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    payload = {
        "strategy_name": "EquityDualMomentum",
        "symbols": ["INFY", "TCS"],
        "days": 40,
        "initial_cash": 500000.0,
        "slippage_bps": 5.0,
        "params": {"lookback_fast": 5, "lookback_slow": 15, "top_n": 1},
    }
    # 1. Submit Operation -> 202 Accepted
    create_res = client.post("/api/v1/operations/backtest", json=payload, headers=auth_headers)
    assert create_res.status_code == 202
    create_data = create_res.json()
    op_id = create_data["operation_id"]
    location = create_res.headers.get("Location")
    assert location == f"/api/v1/operations/{op_id}"
    assert create_data["status"] in ("PENDING", "RUNNING")

    # 2. Poll Operation until Completion
    max_wait = 15.0
    t0 = time.monotonic()
    final_op = None

    while time.monotonic() - t0 < max_wait:
        poll_res = client.get(f"/api/v1/operations/{op_id}")
        assert poll_res.status_code == 200
        poll_data = poll_res.json()
        assert poll_data["operation_id"] == op_id
        assert 0.0 <= poll_data["progress"] <= 1.0

        if poll_data["status"] == "SUCCEEDED":
            final_op = poll_data
            break
        elif poll_data["status"] in ("FAILED", "LOST", "CANCELLED"):
            pytest.fail(f"Operation failed unexpectedly: {poll_data}")
        # test-allow: sleep-in-test — Polling asynchronous worker process execution
        time.sleep(0.1)

    assert final_op is not None
    assert final_op["status"] == "SUCCEEDED"
    assert final_op["progress"] == 1.0
    assert final_op["result"] is not None
    assert final_op["result"]["initial_cash"] == 500000.0
    assert len(final_op["result"]["equity_curve"]) == 40
    assert "stats" in final_op["result"]


def test_operation_idempotent_submission(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "action": "sleep",
        "duration": 1.5,
        "message": "Testing idempotency key deduplication",
    }
    idem_headers = {**auth_headers, "Idempotency-Key": "test-idem-unique-key-999"}

    # First Submission -> 202 Accepted
    res1 = client.post("/api/v1/operations/custom", json=payload, headers=idem_headers)
    assert res1.status_code == 202
    op_id_1 = res1.json()["operation_id"]

    # Second Submission with SAME Idempotency-Key -> returns SAME Operation
    res2 = client.post("/api/v1/operations/custom", json=payload, headers=idem_headers)
    assert res2.status_code == 202
    op_id_2 = res2.json()["operation_id"]

    assert op_id_1 == op_id_2


def test_concurrent_operation_limit_enforced(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 1. Launch a long running operation
    slow_payload = {"action": "sleep", "duration": 2.0, "message": "Slow op"}
    res1 = client.post(
        "/api/v1/operations/custom",
        json=slow_payload,
        headers={**auth_headers, "Idempotency-Key": "slow-key-1"},
    )
    assert res1.status_code == 202
    op1_id = res1.json()["operation_id"]

    # 2. Attempt to launch a second operation with a DIFFERENT key -> 409 Conflict (AC-77)
    second_payload = {"action": "compute", "duration": 0.1}
    res2 = client.post(
        "/api/v1/operations/custom",
        json=second_payload,
        headers={**auth_headers, "Idempotency-Key": "second-key-2"},
    )
    assert res2.status_code == 409
    err = res2.json()["error"]
    assert err["code"] == "CONCURRENT_LIMIT"
    assert "single-operation compute lease" in err["message"]

    # 3. Cancel the first operation
    cancel_res = client.post(f"/api/v1/operations/{op1_id}/cancel", headers=auth_headers)
    assert cancel_res.status_code == 200

    # 4. Now a new operation can be submitted successfully
    res3 = client.post(
        "/api/v1/operations/custom",
        json=second_payload,
        headers={**auth_headers, "Idempotency-Key": "third-key-3"},
    )
    assert res3.status_code == 202


def test_operation_cancellation(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {"action": "sleep", "duration": 5.0, "message": "To be cancelled"}
    create_res = client.post("/api/v1/operations/custom", json=payload, headers=auth_headers)
    assert create_res.status_code == 202
    op_id = create_res.json()["operation_id"]

    # Cancel the operation
    cancel_res = client.post(f"/api/v1/operations/{op_id}/cancel", headers=auth_headers)
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["operation_id"] == op_id
    assert cancel_data["status"] == "CANCELLED"

    # Verify polled status is CANCELLED
    poll_res = client.get(f"/api/v1/operations/{op_id}")
    assert poll_res.status_code == 200
    assert poll_res.json()["status"] == "CANCELLED"


def test_list_operations(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {"action": "compute"}
    client.post("/api/v1/operations/custom", json=payload, headers=auth_headers)

    res = client.get("/api/v1/operations")
    assert res.status_code == 200
    ops = res.json()
    assert isinstance(ops, list)
    assert len(ops) >= 1


def test_operation_not_found(client: TestClient) -> None:
    res = client.get("/api/v1/operations/op-nonexistent-12345")
    assert res.status_code == 404
    err = res.json()["error"]
    assert err["code"] == "OPERATION_NOT_FOUND"


# =====================================================================
# Financial & Diagnostics Endpoints Tests (Synchronous & Legacy)
# =====================================================================


# test-allow: loop-in-test — Parity check across legacy and versioned paths
def test_api_backtest_run_sync(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "strategy_name": "EquityDualMomentum",
        "symbols": ["INFY", "TCS"],
        "days": 40,
        "initial_cash": 500000.0,
        "slippage_bps": 5.0,
        "params": {"lookback_fast": 5, "lookback_slow": 15, "top_n": 1},
    }
    for path in ["/api/v1/backtest/run", "/api/backtest/run"]:
        res = client.post(path, json=payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["initial_cash"] == 500000.0
        assert len(data["equity_curve"]) == 40
        assert "stats" in data
        assert "tearsheet_markdown" in data


# test-allow: loop-in-test — Parity check across legacy and versioned paths
def test_api_straddle_simulate(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "spot_price": 24500.0,
        "volatility": 0.18,
        "days_to_expiry": 7,
        "risk_free_rate": 0.07,
        "quantity": 25,
    }
    for path in ["/api/v1/straddle/simulate", "/api/straddle/simulate"]:
        res = client.post(path, json=payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["atm_strike"] == 24500.0
        assert "call_greeks" in data
        assert "put_greeks" in data
        assert data["call_greeks"]["delta"] > 0
        assert data["put_greeks"]["delta"] < 0
        assert data["daily_theta_income"] > 0


# test-allow: loop-in-test — Parity check across legacy and versioned paths
def test_api_diagnostics(client: TestClient) -> None:
    for path in ["/api/v1/diagnostics", "/api/diagnostics"]:
        res = client.get(path)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "HEALTHY"
        assert data["ledger_integrity_verified"] is True
        assert data["checks_passed"] == data["total_checks"]


# test-allow: loop-in-test — Parity check across legacy and versioned paths
def test_api_monte_carlo(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "strategy_name": "EquityDualMomentum",
        "num_simulations": 1000,
        "horizon_days": 100,
        "initial_capital": 1000000.0,
    }
    for path in ["/api/v1/monte-carlo/run", "/api/monte-carlo/run"]:
        res = client.post(path, json=payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["num_simulations"] == 1000
        assert len(data["percentile_50th"]) == 101
        assert "var_95_pct" in data
        assert "cvar_95_pct" in data


# test-allow: loop-in-test — Parity check across legacy and versioned paths
def test_api_portfolio_optimize(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = {
        "symbols": ["INFY", "TCS", "RELIANCE"],
        "days": 60,
        "risk_free_rate": 0.07,
    }
    for path in ["/api/v1/portfolio/optimize", "/api/portfolio/optimize"]:
        res = client.post(path, json=payload, headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["symbols"] == ["INFY", "TCS", "RELIANCE"]
        assert "max_sharpe_point" in data
        assert "min_variance_point" in data
        assert "risk_parity_weights" in data


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        pytest.param(
            "/api/v1/backtest/run",
            {
                "strategy_name": "EquityDualMomentum",
                "symbols": ["INFY", "TCS"],
                "days": 40,
                "initial_cash": 500000.0,
                "slippage_bps": 5.0,
                "params": {"lookback_fast": 5, "lookback_slow": 15, "top_n": 1},
            },
            id="backtest",
        ),
        pytest.param(
            "/api/v1/monte-carlo/run",
            {
                "strategy_name": "EquityDualMomentum",
                "num_simulations": 1000,
                "horizon_days": 100,
                "initial_capital": 1000000.0,
            },
            id="monte-carlo",
        ),
        pytest.param(
            "/api/v1/portfolio/optimize",
            {"symbols": ["INFY", "TCS", "RELIANCE"], "days": 60, "risk_free_rate": 0.07},
            id="portfolio-optimize",
        ),
    ],
)
def test_api_results_declare_their_data_source(
    client: TestClient,
    auth_headers: dict[str, str],
    endpoint: str,
    payload: dict[str, Any],
) -> None:
    res = client.post(endpoint, json=payload, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["data_source"] == str(RuntimeDataSource.SYNTHETIC)
    assert data["data_source_disclosure"] == describe(RuntimeDataSource.SYNTHETIC)


def test_api_diagnostics_reports_absent_credentials(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ACCESS_TOKEN_ENV_VAR, raising=False)
    res = client.get("/api/v1/diagnostics")
    assert res.status_code == 200
    data = res.json()
    assert data["market_data_credentials_configured"] is False
    assert data["market_data_source"] == str(RuntimeDataSource.SYNTHETIC)


def test_api_diagnostics_reports_present_credentials_without_echoing_them(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ACCESS_TOKEN_ENV_VAR, "super-secret-token")
    res = client.get("/api/v1/diagnostics")
    assert res.status_code == 200
    assert res.json()["market_data_credentials_configured"] is True
    assert "super-secret-token" not in res.text
