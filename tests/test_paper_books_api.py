"""Paper books through the /api/v2 surface, against the fixture market store."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import paper_books, paths, router
from quant_system.server.v2.paper_books import MAX_BOOKS
from tests.market_fixtures import DATES, build_standard_store


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


@pytest.fixture()
def ready(
    client: TestClient,
    headers: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    # The standard store's benchmark ends 20 sessions before its stocks, which is irrelevant to
    # what these tests replay. The refusal of such a store is pinned in
    # tests/test_v2_paper_order_freshness.py.
    monkeypatch.setattr(paper_books, "MAX_REFERENCE_LAG_SESSIONS", 10_000)
    folder = tmp_path / "workspace" / "data"
    build_standard_store(folder)
    assert (
        client.post("/api/v2/data/folder", json={"path": str(folder)}, headers=headers).status_code
        == 200
    )
    client.post("/api/v2/data/index/build", headers=headers)
    router.services().job.wait(60)
    return client


def _body(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "My first idea",
        "template_id": "buy_hold",
        "params": {},
        "scope": "stocks",
        "symbols": ["AAA"],
        "capital": "100000",
    }
    body.update(changes)
    return body


def test_there_are_no_books_to_start_with_and_the_data_must_be_ready(client: TestClient) -> None:
    assert client.get("/api/v2/paper/mine").status_code == 409  # no market data yet


def test_starting_a_book_returns_a_waiting_book_with_tomorrows_orders(
    ready: TestClient, headers: dict[str, str]
) -> None:
    assert ready.get("/api/v2/paper/mine").json() == []
    created = ready.post("/api/v2/paper/mine", json=_body(), headers=headers)
    assert created.status_code == 200
    book = created.json()
    assert book["name"] == "My first idea" and book["status"] == "WAITING"
    assert book["start_session"] == DATES[299] and book["equity"] == 100_000.0
    assert [(q["side"], q["symbol"]) for q in book["queued"]] == [("BUY", "AAA")]
    assert "session_equity" not in book  # the replay's internals are not part of the API

    listed = ready.get("/api/v2/paper/mine").json()
    assert [b["id"] for b in listed] == [book["id"]]
    assert listed[0]["queued"] == 1 and listed[0]["error"] is None
    assert ready.get(f"/api/v2/paper/mine/{book['id']}").json()["id"] == book["id"]


def test_a_book_can_be_stopped_but_never_deleted(
    ready: TestClient, headers: dict[str, str]
) -> None:
    book_id = ready.post("/api/v2/paper/mine", json=_body(), headers=headers).json()["id"]
    stopped = ready.post(f"/api/v2/paper/mine/{book_id}/stop", headers=headers).json()
    assert stopped["status"] == "STOPPED" and stopped["stop_session"] == DATES[299]
    again = ready.post(f"/api/v2/paper/mine/{book_id}/stop", headers=headers).json()
    assert again["stop_session"] == DATES[299]  # stopping twice changes nothing
    assert ready.delete(f"/api/v2/paper/mine/{book_id}", headers=headers).status_code in (404, 405)
    assert [b["status"] for b in ready.get("/api/v2/paper/mine").json()] == ["STOPPED"]


def test_bad_requests_are_refused_in_plain_words(
    ready: TestClient, headers: dict[str, str]
) -> None:
    unknown = ready.post("/api/v2/paper/mine", json=_body(template_id="nope"), headers=headers)
    assert unknown.status_code == 400 and unknown.json()["error"]["code"] == "PAPER_REFUSED"
    missing = ready.post("/api/v2/paper/mine", json=_body(symbols=["NOPE"]), headers=headers)
    assert (
        missing.status_code == 400
        and "not in the market data" in missing.json()["error"]["message"]
    )
    none = ready.post("/api/v2/paper/mine", json=_body(symbols=[]), headers=headers)
    assert none.status_code == 400 and "between 1 and" in none.json()["error"]["message"]
    poor = ready.post("/api/v2/paper/mine", json=_body(capital="5000"), headers=headers)
    assert poor.status_code == 422  # below the schema minimum
    nameless = ready.post("/api/v2/paper/mine", json=_body(name=""), headers=headers)
    assert nameless.status_code == 422
    assert ready.get("/api/v2/paper/mine/nope").status_code == 404
    assert ready.post("/api/v2/paper/mine/nope/stop", headers=headers).status_code == 404
    assert ready.get("/api/v2/paper/mine").json() == []  # nothing half-created


def test_books_survive_a_restart_and_keep_their_recorded_start(
    ready: TestClient, headers: dict[str, str]
) -> None:
    book_id = ready.post("/api/v2/paper/mine", json=_body(), headers=headers).json()["id"]
    router.reset_services()
    listed = ready.get("/api/v2/paper/mine").json()
    assert [b["id"] for b in listed] == [book_id]
    assert listed[0]["start_session"] == DATES[299]


def test_the_most_books_running_at_once_is_limited(
    ready: TestClient, headers: dict[str, str]
) -> None:
    for number in range(MAX_BOOKS):
        response = ready.post(
            "/api/v2/paper/mine", json=_body(name=f"Book {number}"), headers=headers
        )
        assert response.status_code == 200
    extra = ready.post("/api/v2/paper/mine", json=_body(name="One too many"), headers=headers)
    assert extra.status_code == 400 and "already have" in extra.json()["error"]["message"]


def test_a_provider_readjustment_is_reported_not_hidden(
    ready: TestClient, headers: dict[str, str]
) -> None:
    book_id = ready.post("/api/v2/paper/mine", json=_body(), headers=headers).json()["id"]
    state = router.services().state
    assert state.paper_snapshots(book_id) == {DATES[299]: 100_000.0}  # recorded once, at the start
    # Pretend the books's recorded value for that day was 5% different when it was first seen.
    with state._connect() as conn:
        conn.execute(
            "UPDATE paper_snapshots SET equity = ? WHERE book_id = ?", (105_000.0, book_id)
        )
    router.services().paper._cache.clear()
    book = ready.get(f"/api/v2/paper/mine/{book_id}").json()
    assert book["status"] == "ATTENTION"
    assert any("re-adjusted past prices" in note for note in book["attention"])
    # The record itself is never rewritten.
    assert state.paper_snapshots(book_id) == {DATES[299]: 105_000.0}


def test_a_book_that_cannot_be_replayed_says_why_in_both_views(
    ready: TestClient, headers: dict[str, str]
) -> None:
    book_id = ready.post("/api/v2/paper/mine", json=_body(), headers=headers).json()["id"]
    state = router.services().state
    with state._connect() as conn:  # the stock later disappears from the market data
        conn.execute(
            "UPDATE paper_books SET spec_json = REPLACE(spec_json, '\"AAA\"', '\"GONE\"') WHERE id = ?",
            (book_id,),
        )
    router.services().paper._cache.clear()
    listed = ready.get("/api/v2/paper/mine").json()
    assert listed[0]["status"] == "ATTENTION" and "not in the market data" in listed[0]["error"]
    detail = ready.get(f"/api/v2/paper/mine/{book_id}").json()
    assert "not in the market data" in detail["error"]
    assert detail["template"]["name"] == "Buy and hold"  # the page can still name the rule
