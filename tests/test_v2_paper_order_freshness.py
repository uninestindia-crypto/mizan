"""A paper book's "tomorrow's orders" must say when they are too old to place.

The orders are decided at one close and fill at the next open. Someone copying them into a real
account acts on the quantities alone, so an order list that is weeks old must never look current.
These tests pin the answer, and the refusal to start a book whose NIFTY reference series ends long
before the prices do (which would start the book in the past).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import paper_books as pb
from quant_system.server.v2 import paths, router
from quant_system.server.v2.auto_update import expected_session
from tests.market_fixtures import DATES, build_standard_store

IST = timezone(timedelta(hours=5, minutes=30))
FRIDAY = date(2026, 10, 2)
MONDAY = date(2026, 10, 5)


# ------------------------------------------------------------------------- the sessions count


def test_weekends_are_not_sessions() -> None:
    assert pb.trading_sessions_between(FRIDAY, FRIDAY + timedelta(days=2), frozenset()) == 0
    assert pb.trading_sessions_between(FRIDAY, MONDAY, frozenset()) == 1


def test_a_holiday_is_not_a_session() -> None:
    assert pb.trading_sessions_between(FRIDAY, MONDAY, frozenset({MONDAY})) == 0


def test_the_range_excludes_its_start_and_includes_its_end() -> None:
    assert pb.trading_sessions_between(MONDAY, MONDAY, frozenset()) == 0
    assert pb.trading_sessions_between(MONDAY, MONDAY + timedelta(days=1), frozenset()) == 1


def test_the_holiday_list_is_read_from_beside_the_market_data(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    (folder / "authorities").mkdir(parents=True)
    (folder / "authorities" / "nse-trading-holidays.json").write_text(
        json.dumps({"holidays": [{"date": "2026-10-02", "description": "Gandhi Jayanti"}]}),
        encoding="utf-8",
    )

    class Index:
        def meta(self) -> dict[str, str]:
            return {"data_folder": str(folder)}

    assert pb.load_holidays(Index()) == frozenset({date(2026, 10, 2)})  # type: ignore[arg-type]


@pytest.mark.parametrize("meta", [{}, {"data_folder": "/nonexistent/place"}])
def test_a_missing_holiday_list_means_no_holidays_not_a_crash(meta: dict[str, str]) -> None:
    class Index:
        def meta(self) -> dict[str, str]:
            return meta

    assert pb.load_holidays(Index()) == frozenset()  # type: ignore[arg-type]


def test_a_malformed_holiday_list_means_no_holidays_not_a_crash(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    (folder / "authorities").mkdir(parents=True)
    (folder / "authorities" / "nse-trading-holidays.json").write_text("{not json", encoding="utf-8")

    class Index:
        def meta(self) -> dict[str, str]:
            return {"data_folder": str(folder)}

    assert pb.load_holidays(Index()) == frozenset()  # type: ignore[arg-type]


# ------------------------------------------------------------------------------- the verdict


def _fresh(as_of: str | None, expected: date, newest: str | None, **kw: Any) -> dict[str, Any]:
    return pb.order_freshness(
        as_of=as_of, expected=expected, newest_data=newest, holidays=frozenset(), **kw
    )


def test_orders_decided_at_the_expected_close_are_current() -> None:
    verdict = _fresh("2026-10-05", MONDAY, "2026-10-05")
    assert verdict["state"] == "CURRENT" and verdict["sessions_missed"] == 0
    assert "5 Oct 2026" in verdict["message"]


def test_friday_orders_are_still_current_on_a_saturday() -> None:
    saturday = datetime(2026, 10, 3, 12, 0, tzinfo=IST)
    verdict = _fresh("2026-10-02", expected_session(saturday), "2026-10-02")
    assert verdict["state"] == "CURRENT"


def test_friday_orders_are_still_current_on_monday_before_the_prices_settle() -> None:
    monday_afternoon = datetime(2026, 10, 5, 17, 0, tzinfo=IST)
    verdict = _fresh("2026-10-02", expected_session(monday_afternoon), "2026-10-02")
    assert verdict["state"] == "CURRENT"


def test_friday_orders_are_out_of_date_once_monday_has_closed() -> None:
    monday_evening = datetime(2026, 10, 5, 19, 0, tzinfo=IST)
    verdict = _fresh("2026-10-02", expected_session(monday_evening), "2026-10-02")
    assert verdict["state"] == "STALE" and verdict["sessions_missed"] == 1
    assert "Do not place them" in verdict["message"]
    assert "1 trading session has passed" in verdict["message"]


def test_a_holiday_does_not_make_orders_out_of_date() -> None:
    verdict = pb.order_freshness(
        as_of="2026-10-02",
        expected=MONDAY,
        newest_data="2026-10-02",
        holidays=frozenset({MONDAY}),
    )
    assert verdict["state"] == "CURRENT"


def test_stale_because_the_market_data_itself_is_old_says_to_update_it() -> None:
    verdict = _fresh("2026-08-21", MONDAY, "2026-08-21")
    assert verdict["state"] == "STALE"
    assert "Your market data ends on 21 Aug 2026" in verdict["message"]


def test_stale_because_the_reference_series_lags_the_prices_says_so() -> None:
    verdict = _fresh("2026-08-21", MONDAY, "2026-10-05")
    assert verdict["state"] == "STALE"
    assert "NIFTY reference series ends there while prices run to 5 Oct 2026" in verdict["message"]
    assert verdict["sessions_missed"] > 1


def test_a_stopped_book_places_no_orders() -> None:
    verdict = _fresh("2026-10-05", MONDAY, "2026-10-05", stopped=True)
    assert verdict["state"] == "STOPPED"


def test_a_book_that_could_not_be_followed_has_no_orders_to_place() -> None:
    verdict = _fresh(None, MONDAY, None)
    assert verdict["state"] == "UNKNOWN"


# ----------------------------------------------------------------------------- through the API


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


_BODY = {
    "name": "Order check",
    "template_id": "buy_hold",
    "params": {},
    "scope": "stocks",
    "symbols": ["AAA"],
    "capital": "100000",
}


def test_a_book_is_refused_when_the_reference_series_ends_long_before_the_prices(
    ready: TestClient, headers: dict[str, str]
) -> None:
    """The standard store's benchmark ends 20 sessions before its stocks do."""
    response = ready.post("/api/v2/paper/mine", json=_BODY, headers=headers)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "PAPER_REFUSED"
    assert "reference series ends on" in error["message"]
    assert "would begin in the past" in error["message"]
    assert ready.get("/api/v2/paper/mine").json() == []  # nothing was saved


def test_old_data_makes_a_books_orders_out_of_date_in_both_views(
    ready: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pb, "MAX_REFERENCE_LAG_SESSIONS", 10_000)
    book = ready.post("/api/v2/paper/mine", json=_BODY, headers=headers).json()
    assert book["orders"]["state"] == "STALE"  # the fixture's prices are from 2020-2021
    assert "Do not place them" in book["orders"]["message"]
    assert book["orders"]["as_of"] == DATES[299]

    listed = ready.get("/api/v2/paper/mine").json()
    assert listed[0]["orders_state"] == "STALE"
    assert ready.get(f"/api/v2/paper/mine/{book['id']}").json()["orders"]["state"] == "STALE"


def test_orders_are_current_when_no_session_has_happened_since_the_close(
    ready: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pb, "MAX_REFERENCE_LAG_SESSIONS", 10_000)
    book = ready.post("/api/v2/paper/mine", json=_BODY, headers=headers).json()
    last = date.fromisoformat(DATES[299])
    router.services().paper._clock = lambda: datetime(
        last.year, last.month, last.day, 19, 0, tzinfo=IST
    ).astimezone(UTC)
    detail = ready.get(f"/api/v2/paper/mine/{book['id']}").json()
    assert detail["orders"]["state"] == "CURRENT"
    assert ready.get("/api/v2/paper/mine").json()[0]["orders_state"] == "CURRENT"


def test_a_stopped_book_reports_no_orders(
    ready: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pb, "MAX_REFERENCE_LAG_SESSIONS", 10_000)
    book = ready.post("/api/v2/paper/mine", json=_BODY, headers=headers).json()
    stopped = ready.post(f"/api/v2/paper/mine/{book['id']}/stop", headers=headers).json()
    assert stopped["orders"]["state"] == "STOPPED"
