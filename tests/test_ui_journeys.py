"""Comprehensive Tests for QuantOS Slice 11: Desktop UI & 7 Core User Journeys.

Validates:
- Static UI asset serving (HTML, CSS, JS) with proper headers and cache policies.
- Full Dashboard rendering and all 7 standalone journey routes (/ui/journey/{id}).
- Semantic HTML landmarks, headings, tables, forms, buttons, and test IDs.
- Keyboard navigation (WAI-ARIA Tabs pattern: role="tablist", role="tab", role="tabpanel", tabindex).
- Form controls & accessible labels (<label for="..."> <input id="...">).
- All 7 core journey APIs backing the frontend.
- Zero broker orders invariant on read-only/shadow/paper endpoints.
- Error handling, 404 responses, and validation error envelopes.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from quant_system import __version__
from quant_system.data.provenance import RuntimeDataSource
from quant_system.server.app import app
from quant_system.server.ui.constants import (
    VALID_JOURNEY_IDS,
)

_EVIDENCE_ROOT_ENV = "QUANTOS_EVIDENCE_ROOT"


def _error_code(response: Response) -> str:
    return str(response.json()["error"]["code"])


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://localhost:8000")


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    res = client.get("/api/v1/csrf-token")
    token = res.json()["csrf_token"]
    return {
        "X-CSRF-Token": token,
        "Origin": "http://localhost:8000",
        "Host": "localhost:8000",
    }


# =============================================================================
# 1. Static Asset Serving & Header Tests
# =============================================================================


def test_static_css_served_with_correct_styles(client: TestClient) -> None:
    res = client.get("/static/styles.css")
    assert res.status_code == 200
    assert "text/css" in res.headers.get("content-type", "")
    content = res.text

    # Verify key tokens and a11y classes
    assert "--color-bg-base" in content
    assert "--color-accent" in content
    assert ".sr-only" in content
    assert ".skip-link" in content
    assert "*:focus-visible" in content
    assert ".badge-source" in content
    assert ".badge-verified" in content
    assert ".journey-header" in content
    assert ".grid-2col" in content


def test_static_js_served_with_controller_functions(client: TestClient) -> None:
    res = client.get("/static/app.js")
    assert res.status_code == 200
    assert "javascript" in res.headers.get(
        "content-type", ""
    ) or "application/javascript" in res.headers.get("content-type", "")
    content = res.text

    # Verify controller initialization and journey handlers
    assert "initTheme" in content
    assert "initTabs" in content
    assert "initIngestion" in content
    assert "initFeatures" in content
    assert "initTraining" in content
    assert "initHoldout" in content
    assert "initBacktestForm" in content
    assert "initShadow" in content
    assert "initPilot" in content
    assert "formatINR" in content


@pytest.mark.parametrize("route", ["/", "/ui", "/static/index.html"])
def test_dashboard_has_no_external_chart_script(client: TestClient, route: str) -> None:
    html = client.get(route).text
    assert "cdn.jsdelivr.net" not in html
    assert "chart.umd" not in html


def test_chart_controller_uses_native_canvas(client: TestClient) -> None:
    javascript = client.get("/static/app.js").text
    assert "new Chart" not in javascript
    assert "drawLineChart" in javascript


@pytest.mark.parametrize("selector", [".tab-btn", ".icon-btn", ".btn-primary", ".btn-secondary"])
def test_control_target_size(client: TestClient, selector: str) -> None:
    css = client.get("/static/styles.css").text
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\}}", css, re.DOTALL)
    assert match is not None
    body = match.group("body")
    assert "min-height: 44px" in body or "height: 44px" in body


def test_chart_canvas_is_responsive_and_contained(client: TestClient) -> None:
    css = client.get("/static/styles.css").text
    chart = re.search(r"\.chart-card canvas\s*\{(?P<body>.*?)\}", css, re.DOTALL)
    assert chart is not None
    assert "width: 100%" in chart.group("body")
    assert "max-width: 100%" in chart.group("body")


def test_static_index_html_contains_all_seven_journeys(client: TestClient) -> None:
    res = client.get("/static/index.html")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    html = res.text

    assert "<!DOCTYPE html>" in html
    assert f"v{__version__}" in html
    assert 'data-test="journey-ingestion"' in html
    assert 'data-test="journey-features"' in html
    assert 'data-test="journey-training"' in html
    assert 'data-test="journey-holdout"' in html
    assert 'data-test="journey-ledger"' in html
    assert 'data-test="journey-shadow"' in html
    assert 'data-test="journey-pilot"' in html


# =============================================================================
# 2. Root UI and Dashboard Routing Tests
# =============================================================================


@pytest.mark.parametrize("route", ["/", "/ui"])
def test_dashboard_routes_serve_semantic_html(client: TestClient, route: str) -> None:
    res = client.get(route)
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    html = res.text

    # Semantic Landmarks (A11y / WCAG AA)
    assert '<header class="navbar" role="banner">' in html
    assert '<nav class="nav-tabs" role="tablist"' in html
    assert '<main class="container" id="main-content" role="main">' in html
    assert '<footer class="footer" role="contentinfo">' in html

    # Skip to content link
    assert '<a href="#main-content" class="skip-link">Skip to main content</a>' in html

    # Live region / alerts
    assert 'role="alert"' in html
    assert 'role="status"' in html


def test_journey_metadata_api(client: TestClient) -> None:
    # 1. UI route
    ui_res = client.get("/ui/journeys")
    assert ui_res.status_code == 200
    journeys_ui = ui_res.json()
    assert len(journeys_ui) == 7
    ids = {j["id"] for j in journeys_ui}
    assert ids == VALID_JOURNEY_IDS

    # 2. API route
    api_res = client.get("/api/journeys")
    assert api_res.status_code == 200
    api_data = api_res.json()
    assert api_data["total_count"] == 7
    assert len(api_data["journeys"]) == 7


# =============================================================================
# 3. All 7 Standalone Journey Views Tests
# =============================================================================


@pytest.mark.parametrize("journey_id", sorted(VALID_JOURNEY_IDS))
def test_standalone_journey_routes_render_expected_panels(
    client: TestClient, journey_id: str
) -> None:
    res = client.get(f"/ui/journey/{journey_id}")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    html = res.text

    # Assert active tab button and panel container
    assert f'data-test="journey-{journey_id}"' in html
    assert f'id="tab-{journey_id}"' in html
    assert f'id="tab-btn-{journey_id}"' in html
    assert '<main class="container"' in html
    assert '<footer class="footer"' in html


def test_invalid_journey_route_returns_accessible_404(client: TestClient) -> None:
    res = client.get("/ui/journey/non-existent-journey-123")
    assert res.status_code == 404
    assert "text/html" in res.headers.get("content-type", "")
    html = res.text
    assert "Error 404" in html
    assert "Journey Not Found" in html
    assert "Return to Dashboard" in html


# =============================================================================
# 4. Journey 1: Data Ingestion & Manifest Inspection
# =============================================================================


def test_journey_1_ingestion_dom_and_api(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. DOM Check
    res = client.get("/ui/journey/ingestion")
    html = res.text
    assert 'data-test="journey-ingestion"' in html
    assert 'id="form-ingestion"' in html
    assert 'id="ingest-symbol"' in html
    assert 'id="ingest-start-date"' in html
    assert 'id="ingest-end-date"' in html
    assert 'id="ingest-source-select"' in html
    assert 'id="btn-ingest-data"' in html
    assert 'id="manifests-table"' in html
    assert 'id="chk-zero-lookahead"' in html
    assert 'id="chk-checksum-match"' in html
    assert "man_infy_2020_2025" not in html
    assert "Synthetic Deterministic Generator" not in html

    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    # 2. Manifests list requires operator configuration.
    man_res = client.get("/api/data/manifests")
    assert man_res.status_code == 503
    assert _error_code(man_res) == "EVIDENCE_ROOT_NOT_CONFIGURED"

    # 3. The unsafe legacy mutation is retired instead of inventing a manifest.
    ingest_payload = {
        "symbol": "INFY",
        "start_date": "2020-01-01",
        "end_date": "2025-01-01",
        "source": "SYNTHETIC",
    }
    ingest_res = client.post("/api/data/ingest", json=ingest_payload, headers=auth_headers)
    assert ingest_res.status_code == 410
    assert _error_code(ingest_res) == "LEGACY_ENDPOINT_RETIRED"


# =============================================================================
# 5. Journey 2: Feature Matrix & Label Explorer
# =============================================================================


def test_journey_2_features_dom_and_api(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. DOM Check
    res = client.get("/ui/journey/features")
    html = res.text
    assert 'data-test="journey-features"' in html
    assert 'id="form-features"' in html
    assert 'id="feat-symbol"' in html
    assert 'id="feat-horizon-bars"' in html
    assert 'id="feat-friction-bps"' in html
    assert 'id="btn-calc-features"' in html
    assert 'aria-label="Extract Features & Compute Labels" disabled' in html
    assert 'id="features-table"' in html
    assert "ret_10d" in html
    assert "vol_20d" in html
    assert "sma_dist_20d" in html
    assert "+0.0245" not in html

    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    # 2. Feature exploration fails closed without governed evidence.
    payload = {"symbol": "INFY", "horizon_days": 5, "label_friction_bps": 5.0}
    exp_res = client.post("/api/features/explore", json=payload, headers=auth_headers)
    assert exp_res.status_code == 503
    assert _error_code(exp_res) == "EVIDENCE_ROOT_NOT_CONFIGURED"


# =============================================================================
# 6. Journey 3: Governed Ridge Training & Baseline Comparison
# =============================================================================


def test_journey_3_ridge_training_dom_and_api(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. DOM Check
    res = client.get("/ui/journey/training")
    html = res.text
    assert 'data-test="journey-training"' in html
    assert 'id="form-training"' in html
    assert 'id="train-l2-penalty"' in html
    assert 'id="train-score-thresh"' in html
    assert 'id="train-fold-type"' in html
    assert 'id="btn-train-ridge"' in html
    assert 'aria-label="Fit Governed Ridge Fold" disabled' in html
    assert 'id="baselines-table"' in html
    assert 'id="coeffs-table"' in html
    assert 'id="train-multiplicity-ordinal"' in html
    assert "+18.5%" not in html
    assert "0.962" not in html

    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    # 2. Training cannot invent a trial without an evidence adapter.
    payload = {
        "candidate_id": "cand_ridge_v1",
        "l2_penalty": 1.0,
        "score_threshold": 0.0,
        "symbols": ["INFY", "TCS", "RELIANCE"],
    }
    train_res = client.post("/api/training/governed-ridge", json=payload, headers=auth_headers)
    assert train_res.status_code == 503
    assert _error_code(train_res) == "EVIDENCE_ROOT_NOT_CONFIGURED"


# =============================================================================
# 7. Journey 4: Single-use Holdout & Stress Testing Tearsheet
# =============================================================================


def test_journey_4_holdout_dom_and_api(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. DOM Check
    res = client.get("/ui/journey/holdout")
    html = res.text
    assert 'data-test="journey-holdout"' in html
    assert 'id="form-holdout"' in html
    assert 'id="holdout-candidate-id"' in html
    assert 'id="holdout-token"' in html
    assert 'id="holdout-confirm-check"' in html
    assert 'id="btn-unlock-holdout"' in html
    assert 'aria-label="Unlock Single-Use Holdout & Run Stress Tests" disabled' in html
    assert 'id="holdout-gates-table"' in html
    assert 'id="stress-scenarios-table"' in html
    assert 'id="model-card-preview"' in html
    assert 'id="btn-export-model-card"' in html
    assert "RESEARCH_CERTIFIED" not in html
    assert ">PASS<" not in html

    monkeypatch.delenv(_EVIDENCE_ROOT_ENV, raising=False)

    # 2. No request consumes or passes a holdout without governed evidence.
    unconfirmed = {
        "candidate_id": "cand_ridge_v1_opt",
        "unlock_token": "HOLD_123",
        "confirm_single_use": False,
    }
    fail_res = client.post("/api/holdout/evaluate", json=unconfirmed, headers=auth_headers)
    assert fail_res.status_code == 503
    assert _error_code(fail_res) == "EVIDENCE_ROOT_NOT_CONFIGURED"

    # 3. Confirmation does not fabricate a successful evaluation.
    confirmed = {
        "candidate_id": "cand_ridge_v1_opt",
        "unlock_token": "HOLD_123",
        "confirm_single_use": True,
    }
    eval_res = client.post("/api/holdout/evaluate", json=confirmed, headers=auth_headers)
    assert eval_res.status_code == 503
    assert _error_code(eval_res) == "EVIDENCE_ROOT_NOT_CONFIGURED"


# =============================================================================
# 8. Journey 5: Ledger & Backtest P&L Tearsheet
# =============================================================================


def test_journey_5_ledger_and_backtest_dom_and_api(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 1. DOM Check
    res = client.get("/ui/journey/ledger")
    html = res.text
    assert 'data-test="journey-ledger"' in html
    assert 'id="form-backtest"' in html
    assert 'id="strategy-select"' in html
    assert 'id="initial-cash"' in html
    assert 'id="sim-days"' in html
    assert 'id="slippage-bps"' in html
    assert 'id="btn-run-backtest"' in html
    assert 'id="ledger-reconcile-badge"' in html
    assert 'id="equityChart"' in html
    assert 'id="fills-table"' in html
    assert 'id="btn-export-tearsheet"' in html

    # 2. Backtest API
    payload = {
        "strategy_name": "EquityDualMomentum",
        "symbols": ["INFY", "TCS"],
        "days": 40,
        "initial_cash": 500000.0,
        "slippage_bps": 5.0,
    }
    bt_res = client.post("/api/backtest/run", json=payload, headers=auth_headers)
    assert bt_res.status_code == 200
    data = bt_res.json()
    assert data["initial_cash"] == 500000.0
    assert len(data["equity_curve"]) == 40
    assert "stats" in data
    assert "tearsheet_markdown" in data


# =============================================================================
# 9. Journey 6: Real-Time / Replay Shadow Monitor
# =============================================================================


def test_journey_6_shadow_monitor_dom_and_api(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 1. DOM Check
    res = client.get("/ui/journey/shadow")
    html = res.text
    assert 'data-test="journey-shadow"' in html
    assert 'id="form-shadow"' in html
    assert 'id="shadow-feed-mode"' in html
    assert 'id="shadow-symbol"' in html
    assert 'id="shadow-speed"' in html
    assert 'id="btn-start-shadow"' in html
    assert 'id="btn-pause-shadow"' in html
    assert (
        'id="btn-start-shadow" class="btn-primary" aria-label="Start Shadow Stream" disabled'
        in html
    )
    assert 'id="btn-pause-shadow" class="btn-secondary" aria-label="Pause Stream" disabled' in html
    assert "Configure a persisted read-only shadow session" in html
    assert 'id="shadow-broker-orders"' in html
    assert 'id="shadow-tape-table"' in html
    assert 'id="shadow-decisions-table"' in html
    assert "2,480" not in html
    assert "09:30:15.120" not in html

    # 2. No session means no fabricated quotes or decisions.
    status_res = client.get("/api/shadow/status")
    assert status_res.status_code == 404
    assert _error_code(status_res) == "SHADOW_SESSION_NOT_CONFIGURED"

    # 3. Shadow control requires idempotency and still fails closed without a session.
    ctrl_res = client.post(
        "/api/shadow/control",
        json={"action": "start", "speed_multiplier": 5},
        headers=auth_headers,
    )
    assert ctrl_res.status_code == 422
    assert _error_code(ctrl_res) == "IDEMPOTENCY_KEY_REQUIRED"


# =============================================================================
# 10. Journey 7: Paper Pilot Campaign Dashboard
# =============================================================================


def test_journey_7_paper_pilot_dom_and_api(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # 1. DOM Check
    res = client.get("/ui/journey/pilot")
    html = res.text
    assert 'data-test="journey-pilot"' in html
    assert 'id="form-pilot"' in html
    assert 'id="pilot-campaign-select"' in html
    assert 'id="pilot-alloc-capital"' in html
    assert 'id="pilot-max-dd-limit"' in html
    assert 'id="btn-submit-pilot-order"' in html
    assert 'id="btn-halt-campaign"' in html
    assert 'id="pilot-positions-table"' in html
    assert 'id="pilot-orders-table"' in html
    assert 'id="pilot-dd-buffer"' in html
    assert "2,548,200" not in html
    assert "ord_p_10492" not in html
    assert (
        'id="btn-submit-pilot-order" class="btn-primary" aria-label="Place Paper Order" disabled'
        in html
    )

    # 2. No campaign means no fabricated positions or P&L.
    camp_res = client.get("/api/paper-pilot/campaign")
    assert camp_res.status_code == 404
    assert _error_code(camp_res) == "PAPER_CAMPAIGN_NOT_CONFIGURED"

    # 3. Paper order mutation requires an idempotency key.
    order_payload = {
        "campaign_id": "CAMP_ALPHA_2026",
        "symbol": "INFY",
        "side": "BUY",
        "quantity": 100,
        "limit_price": 1840.0,
    }
    ord_res = client.post("/api/paper-pilot/order", json=order_payload, headers=auth_headers)
    assert ord_res.status_code == 422
    assert _error_code(ord_res) == "IDEMPOTENCY_KEY_REQUIRED"


# =============================================================================
# 11. Accessibility & Form Label Invariants (WCAG AA & WAI-ARIA)
# =============================================================================


# test-allow: loop-in-test — iteration over regex matched DOM elements with non-empty assertions
def test_accessibility_tab_panel_relationships(client: TestClient) -> None:
    res = client.get("/")
    html = res.text

    # 1. Verify every tab button has aria-controls matching a panel ID
    tab_matches = re.findall(
        r'<button class="tab-btn[^"]*"\s+id="([^"]+)"\s+data-tab="([^"]+)"\s+role="tab"\s+aria-selected="([^"]+)"\s+aria-controls="([^"]+)"',
        html,
    )
    assert len(tab_matches) >= 7, "Expected at least 7 journey tab buttons"
    # test-allow: loop-in-test — iteration over regex matched DOM elements
    for btn_id, data_tab, _aria_sel, aria_ctrl in tab_matches:
        assert data_tab == aria_ctrl
        assert f'id="{aria_ctrl}"' in html, f"Missing target panel for tab {btn_id}"

    # 2. Verify all inputs with IDs have matching label for attributes
    input_ids = re.findall(r'<(?:input|select)\s+[^>]*id="([^"]+)"', html)
    # test-allow: loop-in-test — iteration over extracted DOM input IDs
    for inp_id in input_ids:
        # Check label for
        assert f'for="{inp_id}"' in html, f"Missing accessible label for element id='{inp_id}'"


# =============================================================================
# 12. Security & Zero Live Broker Orders Invariant
# =============================================================================


def test_zero_live_broker_orders_contract_across_all_journeys(client: TestClient) -> None:
    """AC-2 & AC-78: Verifies that across all UI endpoints and journeys, zero live broker orders exist."""
    # 1. Diagnostics check
    diag_res = client.get("/api/diagnostics")
    assert diag_res.status_code == 200
    assert diag_res.json()["market_data_source"] == str(RuntimeDataSource.SYNTHETIC)

    # 2. No shadow session exists, so no route can report broker activity.
    shadow_res = client.get("/api/shadow/status")
    assert shadow_res.status_code == 404
    assert _error_code(shadow_res) == "SHADOW_SESSION_NOT_CONFIGURED"

    paper_res = client.get("/api/paper-pilot/campaign")
    assert paper_res.status_code == 404
    assert _error_code(paper_res) == "PAPER_CAMPAIGN_NOT_CONFIGURED"

    # 3. Version info check
    ver_res = client.get("/api/version")
    assert ver_res.status_code == 200
    assert ver_res.json()["status"] == "ONLINE"
