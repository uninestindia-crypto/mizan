"""The Copilot over HTTP: status, chat, second opinions, saved agents and their runs, end to end through the app."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.copilot.llm import ChatReply
from quant_system.copilot.sources import SqliteShariahSource
from quant_system.copilot.verify_jobs import VerifyJobs
from quant_system.server.app import app
from quant_system.server.v2 import (
    cli_bridge,
    copilot_ai,
    copilot_routes,
    copilot_wiring,
    paths,
    router,
)
from quant_system.server.v2.credentials import CredentialStore
from tests.copilot_fakes import SAMPLE_ROW, FakeNews, FakeQuotes, StubModel, opinion_json
from tests.market_fixtures import build_standard_store

CANARY = "canary-ai-value-QQ77"


class _Inline:
    def __call__(self, task: Callable[[], None]) -> None:
        task()


class Lab:
    """What a test can set: the saved AI keys, and the chat models they would build."""

    def __init__(self) -> None:
        self.keys: dict[str, str] = {}
        self.models: dict[str, StubModel] = {}


def _shariah_db(tmp_path: Path) -> Path:
    path = tmp_path / "shariah.sqlite"
    columns = ", ".join(f"{name} TEXT" for name in SAMPLE_ROW)
    with sqlite3.connect(path) as conn:
        conn.execute(f"CREATE TABLE companies ({columns})")
        marks = ", ".join("?" for _ in SAMPLE_ROW)
        conn.execute(f"INSERT INTO companies VALUES ({marks})", tuple(SAMPLE_ROW.values()))
    return path


@pytest.fixture()
def lab() -> Lab:
    return Lab()


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lab: Lab) -> Iterator[TestClient]:
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    monkeypatch.setattr(paths, "data_scan", paths.DataFolderScan())
    monkeypatch.setattr(copilot_routes, "_store", None)
    monkeypatch.setattr(copilot_routes, "_conversations", None)
    monkeypatch.setattr(copilot_routes, "_jobs", VerifyJobs(spawn=_Inline()))
    monkeypatch.setattr(copilot_wiring, "_NEWS", FakeNews())
    database = _shariah_db(tmp_path)
    monkeypatch.setattr(
        copilot_wiring, "_shariah", lambda: SqliteShariahSource(lambda: sqlite3.connect(database))
    )
    monkeypatch.setattr(copilot_wiring, "key_lookup", lambda provider: lab.keys.get(provider))
    monkeypatch.setattr(
        copilot_routes, "verify_models", lambda ids: [lab.models[p] for p in ids if p in lab.models]
    )
    monkeypatch.setattr(copilot_routes, "chat_model", lambda: next(iter(lab.models.values()), None))
    monkeypatch.setattr(copilot_ai, "installed_apps", lambda: {})  # no AI app on the test computer
    monkeypatch.setattr(cli_bridge, "list_cli_status", lambda force=False: [])
    router.reset_services()
    test_store = CredentialStore(prefix=f"QuantOS-test-{uuid.uuid4().hex[:8]}:")
    router.services().credentials = test_store
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    router.reset_services()


@pytest.fixture()
def headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/v1/csrf-token").json()["csrf_token"]}


@pytest.fixture()
def ready(client: TestClient, headers: dict[str, str], tmp_path: Path) -> TestClient:
    folder = tmp_path / "workspace" / "data"
    build_standard_store(folder)
    assert (
        client.post("/api/v2/data/folder", json={"path": str(folder)}, headers=headers).status_code
        == 200
    )
    client.post("/api/v2/data/index/build", headers=headers)
    router.services().job.wait(60)
    return client


def _chat(
    client: TestClient, headers: dict[str, str], text: str, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    body = {"messages": [{"role": "user", "content": text}], **(extra or {})}
    response = client.post("/api/v2/copilot/chat", json=body, headers=headers)
    assert response.status_code == 200
    return dict(response.json())


# ------------------------------------------------------------------------------------- status


def test_status_lists_providers_and_never_returns_a_key(client: TestClient, lab: Lab) -> None:
    lab.keys["openai"] = CANARY
    body = client.get("/api/v2/copilot/status").json()
    ready = {p["id"]: p["ready"] for p in body["providers"]}
    assert body["ai_ready"] is True and ready["openai"] is True and ready["anthropic"] is False
    assert CANARY not in json.dumps(body) and "Accounts and keys" in body["live_prices"]["message"]


def test_status_with_no_keys_says_the_ai_is_not_ready(client: TestClient) -> None:
    assert client.get("/api/v2/copilot/status").json()["ai_ready"] is False
    assert not any(m["ready"] for m in client.get("/api/v2/copilot/models").json()["models"])


# ------------------------------------------------------------------------------------- chat


def test_without_an_ai_key_a_halal_question_is_answered_from_the_screener(
    ready: TestClient, headers: dict[str, str]
) -> None:
    body = _chat(ready, headers, "is AAA halal?", {"page": "/stock/AAA"})
    assert body["mode"] == "built_in" and body["provider"] is None and body["model"] is None
    assert "AAOIFI" in body["reply"] and "not a religious ruling" in body["reply"].lower()
    assert [s["label"] for s in body["steps"]][-1] == "Halal screening"
    assert any(p["path"] == "/settings/ai" for p in body["proposals"])


def test_with_an_ai_key_the_model_answers_and_says_which_one(
    ready: TestClient, headers: dict[str, str], lab: Lab
) -> None:
    lab.models["openai"] = StubModel("openai", json.dumps({"final": "AAA is a sample company."}))
    body = _chat(ready, headers, "tell me about AAA")
    assert body == {
        **body,
        "reply": "AAA is a sample company.",
        "mode": "ai",
        "provider": "openai",
        "error": None,
    }


def test_when_the_ai_fails_the_person_gets_the_reason_and_the_built_in_answer(
    ready: TestClient, headers: dict[str, str], lab: Lab
) -> None:
    lab.models["openai"] = StubModel("openai", ChatReply(None, 401, f"HTTP 401 {CANARY}"))
    body = _chat(ready, headers, "is AAA halal?")
    assert (
        body["mode"] == "built_in"
        and "did not accept your key" in body["reply"]
        and "AAOIFI" in body["reply"]
    )
    assert CANARY not in json.dumps(body) and "HTTP" not in body["reply"]


def test_a_chat_as_an_agent_can_only_use_that_agents_tools(
    ready: TestClient, headers: dict[str, str]
) -> None:
    draft = {
        "name": "Facts only",
        "tools": ["stock_facts"],
        "steps": ["Show the facts about {symbol}."],
    }
    agent = ready.post("/api/v2/copilot/agents", json=draft, headers=headers).json()
    body = _chat(ready, headers, "is AAA halal?", {"agent_id": agent["id"]})
    assert "not set up to look that up" in body["reply"]


def test_a_malformed_chat_request_is_refused(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post("/api/v2/copilot/chat", json={"messages": []}, headers=headers)
    assert response.status_code == 422


def test_writing_to_the_copilot_needs_the_security_token(client: TestClient) -> None:
    body = {"messages": [{"role": "user", "content": "hi"}]}
    assert client.post("/api/v2/copilot/chat", json=body).status_code in (400, 403)


# ------------------------------------------------------------------------------------- second opinion


def _verify(client: TestClient, headers: dict[str, str], **extra: Any) -> Any:
    body = {"symbol": "AAA", "providers": ["openai"], "recheck": False, **extra}
    return client.post("/api/v2/copilot/verify", json=body, headers=headers)


def test_a_second_opinion_runs_and_returns_the_result_with_the_disclosure(
    ready: TestClient, headers: dict[str, str], lab: Lab
) -> None:
    lab.models["openai"] = StubModel("openai", opinion_json("MIXED"))
    lab.models["groq"] = StubModel("groq", opinion_json("MIXED"))
    started = _verify(ready, headers, providers=["openai", "groq"])
    assert started.status_code == 202
    done = ready.get(f"/api/v2/copilot/verify/{started.json()['job_id']}").json()
    assert done["status"] == "done" and done["progress"] == {"done": 2, "total": 2}
    result = done["result"]
    assert (
        result["consensus"] == "AGREE"
        and result["reading"] == "MIXED"
        and "not independent evidence" in result["disclosure"]
    )
    assert result["halal"]["data_status"] == "UNVERIFIED_SAMPLE"


def test_a_second_opinion_without_any_ai_key_says_what_to_click(
    ready: TestClient, headers: dict[str, str]
) -> None:
    response = _verify(ready, headers)
    assert response.status_code == 422 and response.json()["error"]["code"] == "NO_AI_KEY"
    assert "Accounts and keys" in response.json()["error"]["message"]


def test_a_second_opinion_on_a_stock_with_no_price_facts_asks_no_ai_and_says_what_to_check(
    ready: TestClient, headers: dict[str, str], lab: Lab
) -> None:
    lab.models["openai"] = StubModel("openai", opinion_json("MIXED"))
    started = _verify(ready, headers, symbol="ZZZ")
    result = ready.get(f"/api/v2/copilot/verify/{started.json()['job_id']}").json()["result"]
    assert lab.models["openai"].calls == []
    assert (result["asked"], result["answered"], result["consensus"]) == (0, 0, "NONE")
    assert result["verdicts"] == [] and result["notes"] == []
    assert (
        "no AI was asked" in result["headline"]
        and "Settings, then Market data" in result["headline"]
    )
    assert "not independent evidence" in result["disclosure"]


@pytest.mark.parametrize(
    "extra", [{"symbol": "AAA; DROP"}, {"providers": []}, {"providers": ["a"] * 7}]
)
def test_a_bad_second_opinion_request_is_refused(
    client: TestClient, headers: dict[str, str], extra: dict[str, Any]
) -> None:
    assert _verify(client, headers, **extra).status_code == 422


def test_an_unknown_second_opinion_is_a_plain_not_found(client: TestClient) -> None:
    response = client.get("/api/v2/copilot/verify/nope")
    assert response.status_code == 404 and "Start it again" in response.json()["error"]["message"]


def test_too_many_second_opinions_at_once_asks_the_person_to_wait(
    ready: TestClient, headers: dict[str, str], lab: Lab, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(copilot_routes, "_jobs", VerifyJobs(spawn=lambda _task: None))
    lab.models["openai"] = StubModel("openai", opinion_json())
    statuses = [_verify(ready, headers).status_code for _ in range(4)]
    assert statuses == [202, 202, 202, 429]


# ------------------------------------------------------------------------------------- agents


DRAFT = {
    "name": "My check",
    "description": "d",
    "instructions": "",
    "tools": ["stock_facts", "shariah_check"],
    "steps": ["Show the facts about {symbol}.", "Is {symbol} halal?"],
}


def test_the_form_gets_friendly_tool_labels_and_the_ready_made_agents(client: TestClient) -> None:
    tools = client.get("/api/v2/copilot/tools").json()["tools"]
    assert {"name": "stock_facts", "label": "Price facts"}.items() <= next(
        t for t in tools if t["name"] == "stock_facts"
    ).items()
    agents = client.get("/api/v2/copilot/agents").json()
    assert (
        agents["agents"] == []
        and agents["recipes"]
        and all(r["built_in"] for r in agents["recipes"])
    )


def test_an_agent_can_be_created_changed_listed_and_deleted(
    client: TestClient, headers: dict[str, str]
) -> None:
    created = client.post("/api/v2/copilot/agents", json=DRAFT, headers=headers)
    assert created.status_code == 201 and created.json()["needs_symbol"] is True
    agent_id = created.json()["id"]
    changed = client.put(
        f"/api/v2/copilot/agents/{agent_id}", json={**DRAFT, "name": "Renamed"}, headers=headers
    )
    assert changed.status_code == 200 and changed.json()["name"] == "Renamed"
    assert [a["name"] for a in client.get("/api/v2/copilot/agents").json()["agents"]] == ["Renamed"]
    assert client.delete(f"/api/v2/copilot/agents/{agent_id}", headers=headers).json() == {
        "deleted": True
    }
    assert client.delete(f"/api/v2/copilot/agents/{agent_id}", headers=headers).status_code == 404


def test_a_rejected_form_returns_each_problem_with_its_field(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v2/copilot/agents", json={**DRAFT, "name": "", "tools": []}, headers=headers
    )
    error = response.json()["error"]
    assert response.status_code == 422 and error["code"] == "AGENT_INVALID"
    assert error["message"] == "Check the highlighted fields."
    assert {p["field"] for p in error["details"]["problems"]} == {"name", "tools"}


def test_changing_an_agent_that_does_not_exist_is_a_plain_not_found(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.put("/api/v2/copilot/agents/nope", json=DRAFT, headers=headers)
    assert response.status_code == 404 and "no longer exists" in response.json()["error"]["message"]


def test_a_ready_made_agent_runs_with_no_ai_key(ready: TestClient, headers: dict[str, str]) -> None:
    result = ready.post(
        "/api/v2/copilot/agents/recipe-check-stock/run", json={"symbol": "AAA"}, headers=headers
    ).json()
    assert result["completed"] is True and result["symbol"] == "AAA" and len(result["steps"]) == 4
    assert "AAOIFI" in result["steps"][1]["reply"] and "No AI is set up" in result["note"]
    assert any(p["kind"] == "second_opinion" for p in result["proposals"])


def test_a_saved_agent_runs_and_a_missing_stock_is_asked_for(
    ready: TestClient, headers: dict[str, str]
) -> None:
    agent = ready.post("/api/v2/copilot/agents", json=DRAFT, headers=headers).json()
    asked = ready.post(f"/api/v2/copilot/agents/{agent['id']}/run", json={}, headers=headers).json()
    assert asked["steps"] == [] and "which stock" in asked["note"].lower()
    ran = ready.post(
        f"/api/v2/copilot/agents/{agent['id']}/run", json={"symbol": "aaa"}, headers=headers
    ).json()
    assert ran["completed"] is True and ran["symbol"] == "AAA"


def test_running_an_agent_that_does_not_exist_is_a_plain_not_found(
    client: TestClient, headers: dict[str, str]
) -> None:
    assert (
        client.post("/api/v2/copilot/agents/nope/run", json={}, headers=headers).status_code == 404
    )


def test_no_copilot_route_can_place_an_order() -> None:
    routes = [getattr(route, "path", "") for route in copilot_routes.router.routes]
    forbidden = ("order", "buy", "sell", "trade", "place", "execute")
    assert routes and not [p for p in routes if any(word in p for word in forbidden)]


@pytest.mark.parametrize("path", ["/agents", "/agents/new"])
def test_the_agents_screen_survives_a_refresh(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    built = tmp_path / "built"
    built.mkdir()
    (built / "index.html").write_text("<!doctype html><title>QuantOS</title>", encoding="utf-8")
    monkeypatch.setattr(paths, "spa_dir", lambda: built)
    response = client.get(path)
    assert response.status_code == 200 and "QuantOS" in response.text


# ------------------------------------------------------------------------------------- live prices


@pytest.fixture()
def no_upstox_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)


@pytest.mark.usefixtures("no_upstox_key")
def test_without_a_broker_key_the_status_and_the_prices_route_say_what_to_click(
    client: TestClient,
) -> None:
    live = client.get("/api/v2/copilot/status").json()["live_prices"]
    assert live["ready"] is False and "Accounts and keys" in live["message"]
    prices = client.get("/api/v2/live/quotes?symbols=AAA").json()
    assert prices["connected"] is False and "Accounts and keys" in prices["message"]


def test_with_a_broker_key_the_status_is_ready_and_never_shows_the_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", CANARY)
    body = client.get("/api/v2/copilot/status").json()
    assert body["live_prices"] == {"ready": True, "message": None} and CANARY not in json.dumps(
        body
    )


def test_the_copilot_prices_a_stock_from_the_live_service_with_its_freshness_label(
    ready: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = {
        "last_price": 130.5,
        "label": "LAST_CLOSE",
        "message": "The market is closed. This is the last closing price.",
    }
    monkeypatch.setattr(copilot_wiring, "_quotes", lambda: FakeQuotes(entry))
    body = _chat(ready, headers, "price of AAA")
    assert "130.5" in body["reply"] and "last closing price" in body["reply"]


def _expired_key() -> str:
    import base64

    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'none'})}.{part({'exp': 1})}.{CANARY}"


def test_an_expired_broker_key_is_not_reported_as_ready(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", _expired_key())
    body = client.get("/api/v2/copilot/status").json()
    assert body["live_prices"]["ready"] is False and "expired" in body["live_prices"]["message"]
    assert CANARY not in json.dumps(body)


# ------------------------------------------------------------------------------------- Shariah mode


def test_in_shariah_mode_a_plain_question_about_a_stock_opens_with_the_screener(
    ready: TestClient, headers: dict[str, str]
) -> None:
    router.services().state.update_settings({"shariah_mode": True})
    body = _chat(ready, headers, "how is AAA doing?")
    assert body["reply"].startswith("**From QuantOS's halal screener: AAA")
    assert "Halal screening" in [s["label"] for s in body["steps"]]


def test_switching_the_mode_off_takes_effect_on_the_very_next_question(
    ready: TestClient, headers: dict[str, str]
) -> None:
    router.services().state.update_settings({"shariah_mode": True})
    assert "halal screener" in _chat(ready, headers, "how is AAA doing?")["reply"]
    router.services().state.update_settings({"shariah_mode": False})
    assert "halal screener" not in _chat(ready, headers, "how is AAA doing?")["reply"]
