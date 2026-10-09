"""Fundamentals across accounts, and the lots on the portfolio's positions, through the real app."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.fundamentals.jobs import FundamentalsJobs
from quant_system.fundamentals.runtime import Runtime
from quant_system.fundamentals.service import FundamentalsService
from quant_system.fundamentals.store import FundamentalsStore
from quant_system.server.app import app
from quant_system.server.v2 import fundamentals_routes, router
from quant_system.server.v2.holding_periods import HOLDING_PERIOD_NOTE
from tests import test_v2_api as _api
from tests.fundamentals.fakes import FakeNse
from tests.fundamentals.jobs_support import Held
from tests.fundamentals.support import FRESH
from tests.fundamentals.support import fund_rows as _rows

client = _api.client
data_folder = _api.data_folder
headers = _api.headers
ready = _api.ready

BUY = "2020-08-03"


@pytest.fixture()
def store(client: TestClient, tmp_path: Path) -> Iterator[FundamentalsStore]:
    held = FundamentalsStore(None, tmp_path / "fund.sqlite")
    jobs = FundamentalsJobs(
        held, lambda: FakeNse({}), lambda: datetime(2026, 10, 7, tzinfo=UTC), Held()
    )
    runtime = Runtime(FundamentalsService(held, lambda: FRESH), jobs)
    app.dependency_overrides[fundamentals_routes.runtime] = lambda: runtime
    yield held
    app.dependency_overrides.pop(fundamentals_routes.runtime, None)


def _add(
    client: TestClient,
    headers: dict[str, str],
    symbol: str,
    quantity: int,
    account: int,
    bought: str = BUY,
) -> None:
    body = {
        "symbol": symbol,
        "quantity": quantity,
        "avg_price": "100",
        "buy_date": bought,
        "note": "",
        "account_id": account,
    }
    assert client.post("/api/v2/portfolio/holdings", json=body, headers=headers).status_code == 200


def _two_accounts(client: TestClient, headers: dict[str, str]) -> tuple[int, int]:
    first = client.get("/api/v2/accounts").json()["accounts"][0]["id"]
    body = {"name": "Spouse demat", "owner": "Spouse", "kind": "Demat account", "broker": "Groww"}
    second = client.post("/api/v2/accounts", json=body, headers=headers).json()["id"]
    return int(first), int(second)


def test_fundamentals_follow_the_holdings_in_view_across_every_account(
    ready: TestClient, headers: dict[str, str], store: FundamentalsStore
) -> None:
    store.put(_rows("AAA"))
    store.put_industry({"AAA": "Information Technology"}, "2020-12-31")
    one, two = _two_accounts(ready, headers)
    _add(ready, headers, "AAA", 10, one)
    _add(ready, headers, "AAA", 5, two, "2020-09-01")
    _add(ready, headers, "BBB", 20, one)
    body = ready.get("/api/v2/portfolio/fundamentals").json()
    assert (
        body["scope"] == {"account": "all", "name": "All accounts"} and body["holdings_count"] == 2
    )
    assert body["without_data"] == ["BBB"] and body["without_data_count"] == 1
    held = {h["symbol"]: h for h in body["holdings"]}
    assert held["AAA"]["roe_pct"] == 25.5 and held["AAA"]["industry"] == "Information Technology"
    assert held["AAA"]["weight_pct"] + held["BBB"]["weight_pct"] == pytest.approx(100.0, abs=0.05)
    assert body["top5_weight_pct"] == pytest.approx(100.0, abs=0.05)
    assert (
        body["weighted_average_pe"]["holdings_included"] == 1
        and body["weighted_average_pe"]["method"] == "harmonic mean"
    )
    names = {row["sector"] for row in body["sector_weights"]}
    assert names == {"Information Technology", "Industry not known"}


def test_one_account_shows_only_what_it_holds(
    ready: TestClient, headers: dict[str, str], store: FundamentalsStore
) -> None:
    store.put(_rows("AAA"))
    one, two = _two_accounts(ready, headers)
    _add(ready, headers, "AAA", 5, two)
    _add(ready, headers, "BBB", 20, one)
    body = ready.get("/api/v2/portfolio/fundamentals", params={"account": two}).json()
    assert body["scope"]["account"] == two and body["scope"]["name"] == "Spouse demat"
    assert [h["symbol"] for h in body["holdings"]] == ["AAA"] and body["holdings"][0][
        "weight_pct"
    ] == 100.0


def test_an_unknown_account_and_a_malformed_one_are_plain_errors(
    ready: TestClient, store: FundamentalsStore
) -> None:
    missing = ready.get("/api/v2/portfolio/fundamentals", params={"account": 9999})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"
    bad = ready.get("/api/v2/portfolio/fundamentals", params={"account": "abc"})
    assert (
        bad.status_code == 422
        and bad.json()["error"]["message"] == "Pick All accounts or one of your accounts."
    )


def test_no_holdings_gives_an_empty_valid_answer(
    ready: TestClient, store: FundamentalsStore
) -> None:
    body = ready.get("/api/v2/portfolio/fundamentals").json()
    assert (
        body["holdings_count"] == 0
        and body["holdings"] == []
        and body["weighted_average_pe"]["value"] is None
    )


def test_holdings_with_no_market_data_connected_say_so_in_plain_words(
    client: TestClient, store: FundamentalsStore
) -> None:
    router.services().state.add_holding("AAA", 5, Decimal("100"), BUY, "")
    response = client.get("/api/v2/portfolio/fundamentals")
    assert response.status_code == 409 and response.json()["error"]["code"] == "INDEX_NOT_READY"
    assert (
        response.json()["error"]["message"]
        == "Market data is not connected yet. Open Settings, then Market data."
    )


def test_each_position_on_the_portfolio_lists_its_buy_lots_with_their_holding_periods(
    ready: TestClient, headers: dict[str, str]
) -> None:
    one, two = _two_accounts(ready, headers)
    _add(ready, headers, "AAA", 10, one, "2020-08-03")
    _add(ready, headers, "AAA", 5, two, "2020-09-01")
    positions = ready.get("/api/v2/portfolio").json()["positions"]
    lots = positions[0]["lots"]
    assert [(lot["quantity"], lot["buy_date"], lot["account_id"]) for lot in lots] == [
        (10, "2020-08-03", one),
        (5, "2020-09-01", two),
    ]
    assert lots[0]["long_term_on"] == "2021-08-03" and lots[0]["is_long_term"] is True
    assert isinstance(lots[0]["days_held"], int) and lots[0]["days_held"] > 365
    assert positions[0]["lots_note"] == HOLDING_PERIOD_NOTE


def test_lots_carry_no_tax_figures_and_the_existing_fields_are_unchanged(
    ready: TestClient, headers: dict[str, str]
) -> None:
    one, _ = _two_accounts(ready, headers)
    _add(ready, headers, "AAA", 10, one)
    body: dict[str, Any] = ready.get("/api/v2/portfolio").json()
    position = body["positions"][0]
    assert {"symbol", "quantity", "avg_price", "cost", "accounts", "value", "pnl", "weight"} <= set(
        position
    )
    assert set(position["lots"][0]) == {
        "holding_id",
        "account_id",
        "account_name",
        "quantity",
        "buy_date",
        "days_held",
        "long_term_on",
        "is_long_term",
    }
    assert date.fromisoformat(position["lots"][0]["long_term_on"]) > date.fromisoformat(
        position["lots"][0]["buy_date"]
    )
