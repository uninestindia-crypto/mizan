"""One person, many accounts: each holding belongs to an account, and the portfolio can be seen one account at a time
or all together."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.v2.accounts import ACCOUNT_KINDS, AccountError
from quant_system.server.v2.state import AppState
from tests import test_v2_api as _api

BUY = "2020-08-03"

# The API tests' fixtures (an app over a fixture market store, and a security token), shared rather than copied.
client = _api.client
data_folder = _api.data_folder
headers = _api.headers
ready = _api.ready


def _state(tmp_path: Path) -> AppState:
    return AppState(tmp_path / "state.sqlite")


# ------------------------------------------------------------------------------------- the data layer


def test_a_new_install_has_one_default_account_to_start_with(tmp_path: Path) -> None:
    accounts = _state(tmp_path).accounts()
    assert [(a.name, a.owner, a.kind) for a in accounts] == [("My account", "Me", "Demat account")]


def test_holdings_saved_before_accounts_existed_land_in_the_default_account(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE holdings(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, quantity INTEGER NOT NULL,"
            " avg_price TEXT NOT NULL, buy_date TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);"
            "INSERT INTO holdings(symbol, quantity, avg_price, buy_date, created_at)"
            " VALUES ('AAA', 10, '105.5', '2020-08-03', '2020-08-03T00:00:00+00:00');"
        )
    state = AppState(path)
    default = state.accounts()[0]
    assert [(h.symbol, h.quantity, h.account_id) for h in state.holdings()] == [
        ("AAA", 10, default.id)
    ]


def test_opening_the_same_state_twice_does_not_create_a_second_default_account(
    tmp_path: Path,
) -> None:
    _state(tmp_path)
    assert len(_state(tmp_path).accounts()) == 1


def test_an_account_can_be_added_with_an_owner_a_kind_and_a_broker(tmp_path: Path) -> None:
    state = _state(tmp_path)
    account = state.add_account("Dad's Zerodha", "Father", "Demat account", "Zerodha")
    assert (
        account.name == "Dad's Zerodha"
        and account.owner == "Father"
        and account.broker == "Zerodha"
    )
    assert [a.name for a in state.accounts()] == ["My account", "Dad's Zerodha"]


@pytest.mark.parametrize(
    ("name", "owner", "kind", "message"),
    [
        ("", "Me", "Demat account", "name"),
        ("x" * 61, "Me", "Demat account", "name"),
        ("Okay", "o" * 41, "Demat account", "owner"),
        ("Okay", "Me", "Bitcoin wallet", "kind"),
        ("my ACCOUNT", "Me", "Demat account", "already"),
    ],
)
def test_a_bad_account_is_refused_with_a_plain_reason(
    name: str, owner: str, kind: str, message: str
) -> None:
    with pytest.raises(AccountError) as refused:
        _state_with_default().add_account(name, owner, kind, "")
    assert message in str(refused.value).lower()


def _state_with_default() -> AppState:
    import tempfile

    return AppState(Path(tempfile.mkdtemp()) / "s.sqlite")


@pytest.mark.parametrize("kind", ACCOUNT_KINDS)
def test_every_offered_account_kind_is_accepted(kind: str) -> None:
    assert _state_with_default().add_account("Another", "Me", kind, "").kind == kind


def test_a_holding_goes_to_the_account_it_is_given(tmp_path: Path) -> None:
    state = _state(tmp_path)
    spouse = state.add_account("Spouse demat", "Spouse", "Demat account", "Groww")
    holding = state.add_holding("AAA", 5, Decimal("100"), BUY, "", spouse.id)
    assert holding.account_id == spouse.id


def test_a_holding_with_no_account_goes_to_the_first_one(tmp_path: Path) -> None:
    state = _state(tmp_path)
    assert state.add_holding("AAA", 5, Decimal("100"), BUY, "").account_id == state.accounts()[0].id


def test_a_holding_cannot_be_put_in_an_account_that_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(AccountError, match="does not exist"):
        _state(tmp_path).add_holding("AAA", 5, Decimal("100"), BUY, "", 999)


def test_a_holding_can_be_moved_to_another_account(tmp_path: Path) -> None:
    state = _state(tmp_path)
    spouse = state.add_account("Spouse demat", "Spouse", "Demat account", "")
    holding = state.add_holding("AAA", 5, Decimal("100"), BUY, "")
    moved = state.update_holding(holding.id, 5, Decimal("100"), BUY, "", spouse.id)
    assert moved is not None and moved.account_id == spouse.id


def test_an_account_can_be_renamed_and_its_owner_changed(tmp_path: Path) -> None:
    state = _state(tmp_path)
    account = state.accounts()[0]
    changed = state.update_account(account.id, "Long-term", "Me", "Demat account", "Upstox")
    assert changed is not None and changed.name == "Long-term" and changed.broker == "Upstox"


def test_renaming_to_another_accounts_name_is_refused(tmp_path: Path) -> None:
    state = _state(tmp_path)
    other = state.add_account("Spouse demat", "Spouse", "Demat account", "")
    with pytest.raises(AccountError, match="already"):
        state.update_account(other.id, "My account", "Spouse", "Demat account", "")


def test_the_last_account_cannot_be_deleted(tmp_path: Path) -> None:
    state = _state(tmp_path)
    with pytest.raises(AccountError, match="at least one"):
        state.delete_account(state.accounts()[0].id)


def test_an_account_that_holds_stocks_cannot_be_deleted_without_saying_where_they_go(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    spouse = state.add_account("Spouse demat", "Spouse", "Demat account", "")
    state.add_holding("AAA", 5, Decimal("100"), BUY, "", spouse.id)
    with pytest.raises(AccountError, match="1 stock"):
        state.delete_account(spouse.id)


def test_deleting_an_account_can_move_its_stocks_to_another(tmp_path: Path) -> None:
    state = _state(tmp_path)
    first = state.accounts()[0]
    spouse = state.add_account("Spouse demat", "Spouse", "Demat account", "")
    state.add_holding("AAA", 5, Decimal("100"), BUY, "", spouse.id)
    assert state.delete_account(spouse.id, move_to=first.id) == 1
    assert [h.account_id for h in state.holdings()] == [first.id]
    assert [a.id for a in state.accounts()] == [first.id]


def test_an_empty_account_can_be_deleted(tmp_path: Path) -> None:
    state = _state(tmp_path)
    spare = state.add_account("Spare", "Me", "Other", "")
    assert state.delete_account(spare.id) == 0
    assert len(state.accounts()) == 1


# ------------------------------------------------------------------------------------- the API


def _add(
    client: TestClient, headers: dict[str, str], symbol: str, quantity: int, account: int | None
) -> Any:
    body: dict[str, Any] = {
        "symbol": symbol,
        "quantity": quantity,
        "avg_price": "100",
        "buy_date": BUY,
    }
    if account is not None:
        body["account_id"] = account
    response = client.post("/api/v2/portfolio/holdings", json=body, headers=headers)
    assert response.status_code == 200
    return response.json()


def _new_account(
    client: TestClient, headers: dict[str, str], name: str, owner: str = "Spouse"
) -> int:
    response = client.post(
        "/api/v2/accounts",
        json={"name": name, "owner": owner, "kind": "Demat account", "broker": "Groww"},
        headers=headers,
    )
    assert response.status_code == 200
    return int(response.json()["id"])


def test_the_accounts_list_comes_with_how_many_stocks_each_holds(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    _add(ready, headers, "AAA", 10, spouse)
    listed = ready.get("/api/v2/accounts").json()["accounts"]
    assert [(a["name"], a["holdings"]) for a in listed] == [("My account", 0), ("Spouse demat", 1)]
    assert "Demat account" in ready.get("/api/v2/accounts").json()["kinds"]


def test_a_bad_account_is_refused_by_the_api_in_plain_words(
    ready: TestClient, headers: dict[str, str]
) -> None:
    refused = ready.post(
        "/api/v2/accounts",
        json={"name": "", "owner": "Me", "kind": "Demat account"},
        headers=headers,
    )
    assert refused.status_code == 400 and refused.json()["error"]["code"] == "ACCOUNT_INVALID"
    again = ready.post(
        "/api/v2/accounts",
        json={"name": "my account", "owner": "Me", "kind": "Demat account"},
        headers=headers,
    )
    assert again.status_code == 400 and "already" in again.json()["error"]["message"].lower()


def test_the_portfolio_with_no_account_named_covers_every_account(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    _add(ready, headers, "AAA", 10, None)
    _add(ready, headers, "BBB", 4, spouse)
    summary = ready.get("/api/v2/portfolio").json()
    assert {h["symbol"] for h in summary["holdings"]} == {"AAA", "BBB"}
    assert summary["scope"] == {"account": "all", "name": "All accounts"}
    rows = {a["name"]: a for a in summary["accounts"]}
    assert set(rows) == {"My account", "Spouse demat"}
    assert sum(a["value"] for a in rows.values()) == pytest.approx(summary["totals"]["value"])
    assert sum(a["weight"] for a in rows.values()) == pytest.approx(1.0)


def test_one_account_can_be_viewed_alone_with_its_own_totals_and_weights(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    _add(ready, headers, "AAA", 10, None)
    _add(ready, headers, "BBB", 4, spouse)
    summary = ready.get(f"/api/v2/portfolio?account={spouse}").json()
    assert [h["symbol"] for h in summary["holdings"]] == ["BBB"]
    assert summary["scope"]["name"] == "Spouse demat"
    assert summary["holdings"][0]["weight"] == pytest.approx(1.0)
    assert len(summary["accounts"]) == 2  # the switcher still shows every account


def test_the_same_stock_in_two_accounts_is_one_position_in_the_combined_view(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    _add(ready, headers, "AAA", 10, None)
    _add(ready, headers, "AAA", 30, spouse)
    positions = ready.get("/api/v2/portfolio").json()["positions"]
    assert len(positions) == 1
    aaa = positions[0]
    assert aaa["symbol"] == "AAA" and aaa["quantity"] == 40
    assert aaa["avg_price"] == pytest.approx(100.0) and aaa["cost"] == pytest.approx(4000.0)
    assert sorted((a["account_name"], a["quantity"]) for a in aaa["accounts"]) == [
        ("My account", 10),
        ("Spouse demat", 30),
    ]


def test_the_average_price_of_a_combined_position_is_weighted_by_shares(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    first = {"symbol": "AAA", "quantity": 10, "avg_price": "100", "buy_date": BUY}
    second = {
        "symbol": "AAA",
        "quantity": 30,
        "avg_price": "200",
        "buy_date": BUY,
        "account_id": spouse,
    }
    ready.post("/api/v2/portfolio/holdings", json=first, headers=headers)
    ready.post("/api/v2/portfolio/holdings", json=second, headers=headers)
    aaa = ready.get("/api/v2/portfolio").json()["positions"][0]
    assert aaa["avg_price"] == pytest.approx((10 * 100 + 30 * 200) / 40)


def test_an_account_that_does_not_exist_is_a_plain_not_found(ready: TestClient) -> None:
    missing = ready.get("/api/v2/portfolio?account=999")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_a_stock_is_added_to_the_default_account_when_no_account_is_named_so_older_screens_keep_working(
    ready: TestClient, headers: dict[str, str]
) -> None:
    created = _add(ready, headers, "AAA", 10, None)
    default = ready.get("/api/v2/accounts").json()["accounts"][0]["id"]
    assert created["account_id"] == default


def test_a_stock_can_be_moved_to_another_account_by_editing_it(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    created = _add(ready, headers, "AAA", 10, None)
    body = {
        "symbol": "AAA",
        "quantity": 10,
        "avg_price": "100",
        "buy_date": BUY,
        "account_id": spouse,
    }
    moved = ready.put(f"/api/v2/portfolio/holdings/{created['id']}", json=body, headers=headers)
    assert moved.status_code == 200 and moved.json()["account_id"] == spouse


def test_editing_a_stock_without_naming_an_account_leaves_it_where_it_is(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    created = _add(ready, headers, "AAA", 10, spouse)
    body = {"symbol": "AAA", "quantity": 12, "avg_price": "100", "buy_date": BUY}
    changed = ready.put(f"/api/v2/portfolio/holdings/{created['id']}", json=body, headers=headers)
    assert changed.json()["account_id"] == spouse and changed.json()["quantity"] == 12


def test_deleting_an_account_with_stocks_asks_where_they_should_go(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    _add(ready, headers, "AAA", 10, spouse)
    refused = ready.delete(f"/api/v2/accounts/{spouse}", headers=headers)
    assert refused.status_code == 400 and refused.json()["error"]["code"] == "ACCOUNT_HAS_HOLDINGS"
    first = ready.get("/api/v2/accounts").json()["accounts"][0]["id"]
    done = ready.delete(f"/api/v2/accounts/{spouse}?move_to={first}", headers=headers)
    assert done.status_code == 200 and done.json() == {"deleted": True, "moved": 1}


def test_the_last_account_cannot_be_deleted_through_the_api(
    ready: TestClient, headers: dict[str, str]
) -> None:
    only = ready.get("/api/v2/accounts").json()["accounts"][0]["id"]
    refused = ready.delete(f"/api/v2/accounts/{only}", headers=headers)
    assert refused.status_code == 400 and refused.json()["error"]["code"] == "LAST_ACCOUNT"


def test_an_account_can_be_renamed_through_the_api(
    ready: TestClient, headers: dict[str, str]
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    body = {
        "name": "Spouse long-term",
        "owner": "Spouse",
        "kind": "Demat account",
        "broker": "Groww",
    }
    changed = ready.put(f"/api/v2/accounts/{spouse}", json=body, headers=headers)
    assert changed.status_code == 200 and changed.json()["name"] == "Spouse long-term"
    assert ready.put("/api/v2/accounts/999", json=body, headers=headers).status_code == 404


def test_an_empty_portfolio_still_lists_the_accounts(ready: TestClient) -> None:
    summary = ready.get("/api/v2/portfolio").json()
    assert summary["holdings"] == [] and summary["totals"] is None
    assert [a["name"] for a in summary["accounts"]] == ["My account"]
