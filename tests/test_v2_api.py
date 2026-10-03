"""API v2 end to end through the FastAPI app, against the fixture market store."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import paths, router
from quant_system.server.v2.credentials import CredentialStore
from tests.market_fixtures import build_standard_store


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    # The first-run search for market data must never walk this machine's real drives in a test.
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    monkeypatch.setattr(paths, "data_scan", paths.DataFolderScan())
    router.reset_services()
    test_store = CredentialStore(prefix=f"QuantOS-test-{uuid.uuid4().hex[:8]}:")
    router.services().credentials = test_store
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    for secret in test_store.status():
        test_store.delete(str(secret["name"]))
    router.reset_services()


@pytest.fixture()
def headers(client: TestClient) -> dict[str, str]:
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    return {"X-CSRF-Token": token}


@pytest.fixture()
def data_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "workspace" / "data"
    build_standard_store(folder)
    return folder


@pytest.fixture()
def ready(client: TestClient, headers: dict[str, str], data_folder: Path) -> TestClient:
    assert (
        client.post(
            "/api/v2/data/folder", json={"path": str(data_folder)}, headers=headers
        ).status_code
        == 200
    )
    assert client.post("/api/v2/data/index/build", headers=headers).json()["started"] is True
    router.services().job.wait(60)
    assert router.services().job.state == "DONE"
    return client


def _error(response: Any) -> str:
    return str(response.json()["error"]["code"])


# ----------------------------------------------------------------------- status and data


def test_status_before_any_data(client: TestClient) -> None:
    body = client.get("/api/v2/status").json()
    assert body["index"]["ready"] is False
    assert body["data_folder"]["valid"] is False
    assert body["settings"]["onboarding_complete"] is False
    assert body["costs_covered_from"] == "2020-07-01"


def test_data_screens_say_the_index_is_not_ready(client: TestClient) -> None:
    response = client.get("/api/v2/market/overview")
    assert response.status_code == 409 and _error(response) == "INDEX_NOT_READY"


def test_a_folder_without_market_data_is_refused(
    client: TestClient, headers: dict[str, str], tmp_path: Path
) -> None:
    response = client.post("/api/v2/data/folder", json={"path": str(tmp_path)}, headers=headers)
    assert response.status_code == 400 and _error(response) == "NOT_A_DATA_FOLDER"


def test_mutations_need_the_csrf_token(client: TestClient, data_folder: Path) -> None:
    response = client.post("/api/v2/data/folder", json={"path": str(data_folder)})
    assert response.status_code == 403


def test_building_the_index_makes_the_market_ready(ready: TestClient) -> None:
    status = ready.get("/api/v2/status").json()
    assert status["index"]["ready"] is True
    assert status["index"]["symbols"] == 4
    assert status["index"]["stale"] is False
    assert status["index"]["matches_folder"] is True
    assert status["data_folder"]["candidates"] == [] or all(
        {"path", "datasets"} <= set(c) for c in status["data_folder"]["candidates"]
    )
    assert status["index"]["job"]["state"] == "DONE"


# ---------------------------------------------------------------------------- market


def test_market_endpoints(ready: TestClient) -> None:
    overview = ready.get("/api/v2/market/overview").json()
    assert overview["benchmark"]["symbol"] == "NIFTYBEES"
    screener = ready.get("/api/v2/market/screener", params={"universe": "liquid"}).json()
    assert [r["symbol"] for r in screener["rows"]] == ["AAA", "BBB"]
    assert ready.get("/api/v2/market/screener", params={"universe": "moon"}).status_code == 422
    assert ready.get("/api/v2/market/search", params={"q": "alp"}).json()[0]["symbol"] == "AAA"
    bars = ready.get(
        "/api/v2/market/bars/aaa", params={"start": "2020-06-01", "end": "2020-06-30"}
    ).json()
    assert bars["symbol"] == "AAA" and len(bars["dates"]) == len(bars["close"]) > 15
    assert ready.get("/api/v2/market/bars/ZZZ").status_code == 404


def test_stock_page(ready: TestClient) -> None:
    body = ready.get("/api/v2/stocks/BBB").json()
    assert body["info"]["name"] == "BETA LTD"
    assert any(a["breaks_history"] for a in body["actions"])
    assert set(body["stats"]) >= {"ret_1m", "vol_1y", "max_drawdown_1y", "beta_1y"}
    assert body["in_watchlist"] is False and body["flags"] == []


# ------------------------------------------------------------------------------- lab


def test_lab_runs_are_saved_and_every_run_counts_as_a_trial(
    ready: TestClient, headers: dict[str, str]
) -> None:
    templates = ready.get("/api/v2/lab/templates").json()
    assert {t["id"] for t in templates["templates"]} == {
        "buy_hold",
        "trend",
        "breakout",
        "momentum",
        "pullback",
    }
    first = ready.post(
        "/api/v2/lab/runs", json={"template_id": "buy_hold", "symbols": ["AAA"]}, headers=headers
    ).json()
    second = ready.post(
        "/api/v2/lab/runs",
        json={
            "template_id": "trend",
            "params": {"fast": 10, "slow": 40},
            "symbols": ["AAA", "BBB"],
        },
        headers=headers,
    ).json()
    assert (first["verdict"]["trials"], second["verdict"]["trials"]) == (1, 2)
    history = ready.get("/api/v2/lab/runs").json()
    assert [row["id"] for row in history] == [second["id"], first["id"]]
    assert ready.get(f"/api/v2/lab/runs/{first['id']}").json()["template"]["id"] == "buy_hold"
    assert ready.get("/api/v2/lab/runs/nope").status_code == 404
    assert ready.get("/api/v2/lab/templates").json()["runs_so_far"] == 2


def test_lab_refusals_are_readable(ready: TestClient, headers: dict[str, str]) -> None:
    response = ready.post(
        "/api/v2/lab/runs", json={"template_id": "buy_hold", "symbols": ["DDD"]}, headers=headers
    )
    assert response.status_code == 400 and _error(response) == "LAB_REFUSED"
    assert "demerger" in response.json()["error"]["message"]
    assert ready.get("/api/v2/lab/runs").json() == []  # a refused request is not a trial


def test_lab_uses_capital_from_settings(ready: TestClient, headers: dict[str, str]) -> None:
    ready.put("/api/v2/settings", json={"money": {"capital": "250000"}}, headers=headers)
    run = ready.post(
        "/api/v2/lab/runs", json={"template_id": "buy_hold", "symbols": ["AAA"]}, headers=headers
    ).json()
    assert run["capital"] == 250000.0


# -------------------------------------------------------------------------- settings


def test_settings_patch_validation_and_protected_fields(
    client: TestClient, headers: dict[str, str]
) -> None:
    body = client.put(
        "/api/v2/settings",
        json={"style": "swing", "broker": {"delivery_per_order": "20"}, "data_folder": "C:\\evil"},
        headers=headers,
    ).json()
    assert body["style"] == "swing" and body["broker"]["delivery_per_order"] == "20"
    assert body["data_folder"] is None
    bad = client.put(
        "/api/v2/settings", json={"money": {"risk_per_trade_pct": "50"}}, headers=headers
    )
    assert bad.status_code == 422 and _error(bad) == "INVALID_SETTINGS"
    accepted = client.post("/api/v2/settings/disclaimer", headers=headers).json()
    assert accepted["disclaimer_accepted_at"]


# ---------------------------------------------------------------- watchlist, portfolio


def test_watchlist(ready: TestClient, headers: dict[str, str]) -> None:
    assert ready.post("/api/v2/watchlist", json={"symbol": "aaa"}, headers=headers).json() == [
        "AAA"
    ]
    assert (
        ready.post("/api/v2/watchlist", json={"symbol": "ZZZ"}, headers=headers).status_code == 404
    )
    rows = ready.get("/api/v2/watchlist").json()
    assert rows[0]["symbol"] == "AAA" and len(rows[0]["spark"]) > 30
    assert ready.get("/api/v2/stocks/AAA").json()["in_watchlist"] is True
    assert ready.delete("/api/v2/watchlist/AAA", headers=headers).json() == []


def test_portfolio_crud_and_valuation(ready: TestClient, headers: dict[str, str]) -> None:
    assert ready.get("/api/v2/portfolio").json()["holdings"] == []
    created = ready.post(
        "/api/v2/portfolio/holdings",
        json={"symbol": "AAA", "quantity": 10, "avg_price": "105.50", "buy_date": "2020-08-03"},
        headers=headers,
    ).json()
    ready.post(
        "/api/v2/portfolio/holdings",
        json={"symbol": "BBB", "quantity": 1, "avg_price": "180", "buy_date": "2020-08-03"},
        headers=headers,
    )
    summary = ready.get("/api/v2/portfolio").json()
    aaa = next(h for h in summary["holdings"] if h["symbol"] == "AAA")
    assert aaa["cost"] == 1055.0 and aaa["value"] > 0 and aaa["exit_charges"] > 0
    assert summary["totals"]["value"] == pytest.approx(sum(h["value"] for h in summary["holdings"]))
    assert summary["warnings"]  # AAA dominates a two-stock portfolio
    assert summary["nifty"]["count"] == 2
    updated = ready.put(
        f"/api/v2/portfolio/holdings/{created['id']}",
        json={"symbol": "AAA", "quantity": 20, "avg_price": "105.50", "buy_date": "2020-08-03"},
        headers=headers,
    ).json()
    assert updated["quantity"] == 20
    future = ready.post(
        "/api/v2/portfolio/holdings",
        json={"symbol": "AAA", "quantity": 1, "avg_price": "1", "buy_date": "2999-01-01"},
        headers=headers,
    )
    assert future.status_code == 400 and _error(future) == "FUTURE_DATE"
    assert ready.delete(f"/api/v2/portfolio/holdings/{created['id']}", headers=headers).json() == {
        "deleted": True
    }
    assert (
        ready.delete(f"/api/v2/portfolio/holdings/{created['id']}", headers=headers).status_code
        == 404
    )


# ------------------------------------------------------------------------------ paper


def test_paper_books_are_read_only_views_with_the_honesty_label(
    ready: TestClient, data_folder: Path
) -> None:
    workspace = data_folder.parent
    xs = workspace / "logs" / "xs_monthly_new" / "paper_watch"
    xs.mkdir(parents=True)
    state = {
        "capital": "1000000",
        "cash": "500000",
        "open": [
            {"symbol": "AAA", "shares": 100, "entry_date": "2020-09-01", "entry_value": "12000"}
        ],
        "closed": [],
        "unresolved": [],
        "runs": [],
    }
    (xs / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (workspace / "logs" / "paper_runs").mkdir(parents=True)
    books = {b["id"]: b for b in ready.get("/api/v2/paper/books").json()}
    assert books["xs-monthly"]["position_count"] == 1
    assert books["xs-monthly"]["positions"][0]["market_value"] != 12000
    assert books["flagship"]["status"] == "WAITING"
    assert all("Not evidence" in b["label"] for b in books.values())
    assert (xs / "state.json").read_text(encoding="utf-8") == json.dumps(state)


# ------------------------------------------------------------------------------ tools


def test_cost_calculator(client: TestClient, headers: dict[str, str]) -> None:
    body = client.post(
        "/api/v2/tools/costs",
        json={
            "segment": "delivery",
            "buy_price": "1000",
            "sell_price": "1010",
            "quantity": 100,
            "trade_date": "2025-01-02",
        },
        headers=headers,
    ).json()
    buy_rules = {line["label"]: line["rule_id"] for line in body["buy"]["lines"]}
    assert buy_rules["Securities transaction tax (STT)"] == "STT-EQ-DEL-20041001"
    assert body["net_pnl"] == pytest.approx(body["gross_pnl"] - body["charges"])
    assert 1000 < body["breakeven_price"] < 1010
    old = client.post(
        "/api/v2/tools/costs",
        json={"buy_price": "1", "sell_price": "1", "quantity": 1, "trade_date": "2019-01-01"},
        headers=headers,
    )
    assert old.status_code == 400 and "1 Jul 2020" in old.json()["error"]["message"]


def test_position_size_uses_money_rules(client: TestClient, headers: dict[str, str]) -> None:
    body = client.post(
        "/api/v2/tools/position-size", json={"entry": "500", "stop": "480"}, headers=headers
    ).json()
    assert body["quantity"] == 500  # 1% of 10,00,000 = 10,000 at risk / 20 per share
    assert body["max_loss"] == 10000.0 and body["direction"] == "long"
    bad = client.post(
        "/api/v2/tools/position-size", json={"entry": "500", "stop": "500"}, headers=headers
    )
    assert bad.status_code == 400


def test_options_payoff_long_straddle(client: TestClient, headers: dict[str, str]) -> None:
    body = client.post(
        "/api/v2/tools/options-payoff",
        json={
            "spot": 24000,
            "days_to_expiry": 7,
            "volatility_pct": 14,
            "legs": [
                {"kind": "call", "side": "buy", "strike": 24000, "premium": 180, "lot_size": 75},
                {"kind": "put", "side": "buy", "strike": 24000, "premium": 170, "lot_size": 75},
            ],
        },
        headers=headers,
    ).json()
    assert body["max_profit"] is None
    assert body["max_loss"] == pytest.approx(-350 * 75, abs=1)
    assert body["breakevens"] == pytest.approx([23650, 24350], abs=2)
    assert body["net_premium"] == pytest.approx(350 * 75)


# ------------------------------------------------------------------------ credentials


@pytest.mark.skipif(os.name != "nt", reason="Windows Credential Manager")
def test_secrets_are_stored_but_never_returned(client: TestClient, headers: dict[str, str]) -> None:
    body = client.put(
        "/api/v2/credentials/HF_TOKEN", json={"value": "hf_example_value"}, headers=headers
    ).json()
    hf = next(s for s in body["secrets"] if s["name"] == "HF_TOKEN")
    assert hf["stored"] is True and hf["source"] == "credential_manager"
    assert "hf_example_value" not in json.dumps(client.get("/api/v2/credentials").json())
    body = client.delete("/api/v2/credentials/HF_TOKEN", headers=headers).json()
    assert next(s for s in body["secrets"] if s["name"] == "HF_TOKEN")["stored"] is False
    refused = client.put("/api/v2/credentials/PATH", json={"value": "x"}, headers=headers)
    assert refused.status_code == 400 and _error(refused) == "CREDENTIAL_REFUSED"
    os.environ.pop("HF_TOKEN", None)


def test_ai_tools_are_detected_without_installing_anything(client: TestClient) -> None:
    tools = client.get("/api/v2/ai-tools").json()
    assert [t["command"] for t in tools] == ["claude", "codex", "gemini"]
    assert all("install" in t for t in tools)


# ------------------------------------------------------------------------------- SPA


def test_client_routes_serve_the_app_or_explain_it_is_not_built(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "spa-empty"
    empty.mkdir()
    monkeypatch.setattr(paths, "spa_dir", lambda: empty)
    missing = client.get("/lab/new/trend")
    assert (
        missing.status_code == 503 and "not built" in missing.text and "<script" not in missing.text
    )
    built = tmp_path / "spa-built"
    built.mkdir()
    (built / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    monkeypatch.setattr(paths, "spa_dir", lambda: built)
    for route in ("/", "/markets", "/stock/INFY", "/lab", "/portfolio", "/settings/data"):
        response = client.get(route)
        assert response.status_code == 200 and "id=root" in response.text
    assert client.get("/classic").status_code == 200
    assert client.get("/api/v2/definitely-not-a-route").status_code == 404


def test_an_index_from_another_folder_is_flagged_and_a_source_checkout_is_not_a_data_folder(
    ready: TestClient, headers: dict[str, str], tmp_path: Path
) -> None:
    other = tmp_path / "other" / "data"
    build_standard_store(other)
    assert (
        ready.post("/api/v2/data/folder", json={"path": str(other)}, headers=headers).status_code
        == 200
    )
    index = ready.get("/api/v2/status").json()["index"]
    assert index["ready"] is True and index["matches_folder"] is False and index["stale"] is False
    checkout = tmp_path / "checkout" / "data"
    (checkout / "evidence" / "market-cache" / "not-a-cache").mkdir(parents=True)
    (checkout / "evidence" / "market-cache" / "not-a-cache" / "readme.txt").write_text(
        "x", encoding="utf-8"
    )
    assert paths.is_data_folder(checkout) is False
    refused = ready.post("/api/v2/data/folder", json={"path": str(checkout)}, headers=headers)
    assert refused.status_code == 400 and _error(refused) == "NOT_A_DATA_FOLDER"
