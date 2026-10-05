"""Mode A: you copy a paper book's orders into your own account by hand.

QuantOS never connects to a broker, so the only way it can know what you did is for you to say. These
tests pin what it keeps (what you placed or skipped, and at what price), what it refuses to keep (an
order the book never decided), and how it compares your price with the paper fill without guessing.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import paper_books as pb
from quant_system.server.v2 import paths, router
from tests.market_fixtures import DATES, build_standard_store

IST = timezone(timedelta(hours=5, minutes=30))


def _state() -> dict[str, Any]:
    """A book that decided at 2026-10-01 and 2026-10-02; its fills are on the next session."""
    return {
        "last_session": "2026-10-02",
        "queued": [{"side": "BUY", "symbol": "TCS", "quantity": 5, "reference_price": 2000.0}],
        "curve": [["2026-09-30", 1.0, 1.0], ["2026-10-01", 1.0, 1.0], ["2026-10-02", 1.0, 1.0]],
        "trades": [
            {
                "date": "2026-10-01",
                "symbol": "INFY",
                "side": "BUY",
                "quantity": 10,
                "price": 1000.0,
            },
            {"date": "2026-10-01", "symbol": "ITC", "side": "SELL", "quantity": 20, "price": 500.0},
        ],
    }


def _placement(as_of: str, symbol: str, side: str, **kw: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "as_of": as_of,
        "symbol": symbol,
        "side": side,
        "status": "PLACED",
        "quantity": 10,
        "price": None,
        "recorded_at": "2026-10-02T10:00:00+00:00",
    }
    row.update(kw)
    return row


# --------------------------------------------------------------------- what a close decided


def test_the_orders_at_the_latest_close_are_the_queue() -> None:
    assert pb.orders_decided_at(_state(), "2026-10-02") == _state()["queued"]


def test_the_orders_at_an_earlier_close_are_the_fills_on_the_next_session() -> None:
    decided = pb.orders_decided_at(_state(), "2026-09-30")
    assert {(o["symbol"], o["side"], o["quantity"]) for o in decided} == {
        ("INFY", "BUY", 10),
        ("ITC", "SELL", 20),
    }
    assert pb.orders_decided_at(_state(), "2026-10-01") == []


def test_a_close_the_book_never_had_decided_nothing() -> None:
    assert pb.orders_decided_at(_state(), "2027-01-01") == []


# ------------------------------------------------------------------------------- tracking


def test_paying_more_than_the_paper_fill_is_worse_for_a_buy() -> None:
    tracking = pb.placement_tracking(
        _state(), [_placement("2026-09-30", "INFY", "BUY", quantity=10, price=1010.0)]
    )
    row = tracking["rows"][0]
    assert row["state"] == "FILLED" and row["paper_price"] == 1000.0
    assert row["worse_bps"] == pytest.approx(100.0)  # 1% worse
    assert row["cost"] == pytest.approx(100.0)  # 10 shares x Rs 10


def test_selling_for_less_than_the_paper_fill_is_worse_for_a_sell() -> None:
    tracking = pb.placement_tracking(
        _state(), [_placement("2026-09-30", "ITC", "SELL", quantity=20, price=495.0)]
    )
    assert tracking["rows"][0]["worse_bps"] == pytest.approx(100.0)
    assert tracking["rows"][0]["cost"] == pytest.approx(100.0)


def test_a_better_price_than_paper_is_a_negative_cost() -> None:
    tracking = pb.placement_tracking(
        _state(), [_placement("2026-09-30", "INFY", "BUY", quantity=10, price=990.0)]
    )
    assert tracking["rows"][0]["worse_bps"] == pytest.approx(-100.0)
    assert tracking["total_cost"] == pytest.approx(-100.0)


def test_an_order_with_no_price_typed_is_not_compared() -> None:
    tracking = pb.placement_tracking(_state(), [_placement("2026-09-30", "INFY", "BUY")])
    assert tracking["rows"][0]["worse_bps"] is None
    assert tracking["compared"] == 0 and tracking["mean_worse_bps"] is None
    assert tracking["total_cost"] is None


def test_a_skipped_order_costs_nothing_and_is_counted() -> None:
    tracking = pb.placement_tracking(
        _state(), [_placement("2026-09-30", "INFY", "BUY", status="SKIPPED", quantity=None)]
    )
    assert tracking["skipped"] == 1 and tracking["placed"] == 0
    assert tracking["rows"][0]["cost"] is None


def test_orders_at_the_latest_close_are_waiting_for_a_paper_fill() -> None:
    tracking = pb.placement_tracking(
        _state(), [_placement("2026-10-02", "TCS", "BUY", quantity=5, price=2001.0)]
    )
    assert tracking["rows"][0]["state"] == "WAITING" and tracking["waiting"] == 1
    assert tracking["rows"][0]["worse_bps"] is None


def test_unrecorded_orders_are_counted_only_for_closes_you_engaged_with() -> None:
    tracking = pb.placement_tracking(
        _state(), [_placement("2026-09-30", "INFY", "BUY", price=1000.0)]
    )
    assert tracking["unrecorded"] == 1  # ITC at that close was never recorded
    assert pb.placement_tracking(_state(), [])["unrecorded"] == 0


def test_the_mean_is_over_the_orders_that_have_both_prices() -> None:
    tracking = pb.placement_tracking(
        _state(),
        [
            _placement("2026-09-30", "INFY", "BUY", price=1010.0),
            _placement("2026-09-30", "ITC", "SELL", quantity=20, price=500.0),
        ],
    )
    assert tracking["compared"] == 2
    assert tracking["mean_worse_bps"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------- through the API


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    monkeypatch.setattr(paths, "data_scan", paths.DataFolderScan())
    monkeypatch.setattr(pb, "MAX_REFERENCE_LAG_SESSIONS", 10_000)
    router.reset_services()
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    router.reset_services()


@pytest.fixture()
def headers(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/v1/csrf-token").json()["csrf_token"]}


@pytest.fixture()
def book(client: TestClient, headers: dict[str, str], tmp_path: Path) -> dict[str, Any]:
    """A book whose orders are CURRENT: the clock stands on the evening of the data's last session."""
    folder = tmp_path / "workspace" / "data"
    build_standard_store(folder)
    client.post("/api/v2/data/folder", json={"path": str(folder)}, headers=headers)
    client.post("/api/v2/data/index/build", headers=headers)
    router.services().job.wait(60)
    created = client.post(
        "/api/v2/paper/mine",
        json={
            "name": "Copy me",
            "template_id": "buy_hold",
            "params": {},
            "scope": "stocks",
            "symbols": ["AAA", "BBB"],
            "capital": "1000000",
        },
        headers=headers,
    ).json()
    last = date.fromisoformat(DATES[299])
    stamp = datetime(last.year, last.month, last.day, 19, 0, tzinfo=IST).astimezone(UTC)
    router.services().paper._clock = lambda: stamp
    return created  # type: ignore[no-any-return]


def _put(client: TestClient, headers: dict[str, str], book_id: str, **body: Any) -> Any:
    payload = {"as_of": DATES[299], "symbol": "AAA", "side": "BUY", "status": "PLACED", **body}
    return client.put(f"/api/v2/paper/mine/{book_id}/placements", json=payload, headers=headers)


def test_the_inbox_lists_a_books_waiting_orders(client: TestClient, book: dict[str, Any]) -> None:
    inbox = client.get("/api/v2/paper/orders").json()
    assert inbox["pending"] == 2
    [entry] = inbox["books"]
    assert entry["id"] == book["id"] and entry["state"] == "CURRENT"
    assert entry["orders"] == 2 and entry["pending"] == 2 and entry["dealt_with"] == 0


def test_recording_an_order_moves_it_out_of_the_inbox(
    client: TestClient, headers: dict[str, str], book: dict[str, Any]
) -> None:
    response = _put(client, headers, book["id"], quantity=3690, price="134.90")
    assert response.status_code == 200
    detail = response.json()
    [saved] = detail["placements"]
    assert saved["symbol"] == "AAA" and saved["quantity"] == 3690 and saved["price"] == 134.9
    assert detail["tracking"]["waiting"] == 1
    inbox = client.get("/api/v2/paper/orders").json()
    assert inbox["pending"] == 1 and inbox["books"][0]["dealt_with"] == 1


def test_a_skipped_order_also_leaves_the_inbox(
    client: TestClient, headers: dict[str, str], book: dict[str, Any]
) -> None:
    assert _put(client, headers, book["id"], status="SKIPPED").status_code == 200
    assert client.get("/api/v2/paper/orders").json()["pending"] == 1


def test_recording_again_corrects_the_earlier_note(
    client: TestClient, headers: dict[str, str], book: dict[str, Any]
) -> None:
    _put(client, headers, book["id"], quantity=10, price="100")
    detail = _put(client, headers, book["id"], quantity=12, price="101").json()
    assert [(p["quantity"], p["price"]) for p in detail["placements"]] == [(12, 101.0)]


def test_clearing_a_note_puts_the_order_back_in_the_inbox(
    client: TestClient, headers: dict[str, str], book: dict[str, Any]
) -> None:
    _put(client, headers, book["id"], quantity=10)
    cleared = client.delete(
        f"/api/v2/paper/mine/{book['id']}/placements",
        params={"as_of": DATES[299], "symbol": "AAA", "side": "BUY"},
        headers=headers,
    )
    assert cleared.status_code == 200 and cleared.json()["placements"] == []
    assert client.get("/api/v2/paper/orders").json()["pending"] == 2


def test_an_order_the_book_never_decided_is_refused(
    client: TestClient, headers: dict[str, str], book: dict[str, Any]
) -> None:
    response = _put(client, headers, book["id"], symbol="TCS", quantity=1)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PLACEMENT_REFUSED"
    wrong_side = _put(client, headers, book["id"], side="SELL", quantity=1)
    assert wrong_side.status_code == 400
    assert client.get(f"/api/v2/paper/mine/{book['id']}").json()["placements"] == []


def test_placing_without_saying_how_many_shares_is_refused(
    client: TestClient, headers: dict[str, str], book: dict[str, Any]
) -> None:
    response = _put(client, headers, book["id"])
    assert response.status_code == 400 and "how many shares" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    "body", [{"quantity": 0}, {"quantity": 1, "price": "-3"}, {"side": "HOLD"}]
)
def test_nonsense_is_refused_before_it_is_stored(
    client: TestClient, headers: dict[str, str], book: dict[str, Any], body: dict[str, Any]
) -> None:
    assert _put(client, headers, book["id"], **body).status_code == 422


def test_an_unknown_book_is_not_found(
    client: TestClient, headers: dict[str, str], book: dict[str, Any]
) -> None:
    """``book`` is here for the market data it connects; the id asked for is a different one."""
    assert _put(client, headers, "nope", quantity=1).status_code == 404


def test_a_stopped_book_leaves_the_inbox(
    client: TestClient, headers: dict[str, str], book: dict[str, Any]
) -> None:
    client.post(f"/api/v2/paper/mine/{book['id']}/stop", headers=headers)
    assert client.get("/api/v2/paper/orders").json() == {"books": [], "pending": 0}


def test_out_of_date_orders_are_listed_but_nothing_is_pending(
    client: TestClient, book: dict[str, Any]
) -> None:
    router.services().paper._clock = lambda: datetime(2030, 1, 1, tzinfo=UTC)
    inbox = client.get("/api/v2/paper/orders").json()
    assert inbox["pending"] == 0
    assert [(b["state"], b["pending"]) for b in inbox["books"]] == [("STALE", 0)]
