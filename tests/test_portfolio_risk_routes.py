"""The risk routes and what the assistant is told: through the real app, against the shared fixture market store."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quant_system.copilot.rules import AnswerContext, answer_without_ai
from quant_system.copilot.tools import default_registry
from quant_system.server.v2 import broker_routes, copilot_wiring
from quant_system.server.v2 import router as v2_router
from quant_system.server.v2.broker_routes import broker_view_service
from quant_system.server.v2.portfolio_risk import NO_HOLDINGS, NOTE
from tests.broker_fakes import make_rig
from tests.copilot_fakes import make_context
from tests.test_portfolio_accounts import _add, _new_account
from tests.test_portfolio_risk import FakeIndex, rng_returns, series, walk
from tests.test_v2_api import (  # noqa: F401, F811  (shared fixtures)
    client,
    data_folder,
    headers,
    ready,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def add(ready: TestClient, headers: dict[str, str], symbol: str, quantity: int) -> None:  # noqa: F811
    body = {
        "symbol": symbol,
        "quantity": quantity,
        "avg_price": 100,
        "buy_date": "2020-02-03",
        "note": "",
    }
    assert ready.post("/api/v2/portfolio/holdings", json=body, headers=headers).status_code == 200


# ------------------------------------------------------------------------------ hand-entered holdings


def test_with_no_holdings_the_risk_route_says_so(ready: TestClient) -> None:  # noqa: F811
    body = ready.get("/api/v2/portfolio/risk").json()
    assert body["available"] is False and body["message"] == NO_HOLDINGS


def test_with_holdings_the_risk_route_answers_in_the_shared_shape(
    ready: TestClient,  # noqa: F811
    headers: dict[str, str],  # noqa: F811
) -> None:
    add(ready, headers, "AAA", 10)
    add(ready, headers, "BBB", 20)
    body = ready.get("/api/v2/portfolio/risk").json()
    assert set(body) == {
        "available",
        "message",
        "window",
        "volatility_pct",
        "effective_bets",
        "diversification",
        "shrinkage",
        "holdings",
        "left_out",
        "note",
    }
    assert body["note"] == NOTE
    if body["available"]:
        assert {h["symbol"] for h in body["holdings"]} <= {"AAA", "BBB"}
        assert sum(h["money_pct"] for h in body["holdings"]) == pytest.approx(100.0, abs=0.2)
    else:
        assert body["message"]


def test_the_risk_route_follows_the_account_in_view_like_the_portfolio_does(
    ready: TestClient,  # noqa: F811
    headers: dict[str, str],  # noqa: F811
) -> None:
    spouse = _new_account(ready, headers, "Spouse demat")
    _add(ready, headers, "AAA", 10, None)
    _add(ready, headers, "BBB", 4, spouse)
    one = ready.get(f"/api/v2/portfolio/risk?account={spouse}")
    assert one.status_code == 200
    assert "AAA" not in one.text  # the other account's stock is nowhere in it
    both = ready.get("/api/v2/portfolio/risk").json()
    assert both["available"] is False or {h["symbol"] for h in both["holdings"]} == {"AAA", "BBB"}


def test_an_account_that_does_not_exist_is_a_plain_404(
    ready: TestClient,  # noqa: F811
) -> None:
    response = ready.get("/api/v2/portfolio/risk?account=999")
    assert response.status_code == 404 and response.json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_an_account_with_nothing_in_it_says_there_is_nothing_to_look_at(
    ready: TestClient,  # noqa: F811
    headers: dict[str, str],  # noqa: F811
) -> None:
    empty = _new_account(ready, headers, "Parent demat")
    _add(ready, headers, "AAA", 10, None)
    body = ready.get(f"/api/v2/portfolio/risk?account={empty}").json()
    assert body["available"] is False and body["message"] == NO_HOLDINGS


def test_the_risk_route_needs_market_data_and_says_where_to_connect_it(client: TestClient) -> None:  # noqa: F811
    v2_router.services().state.add_holding("AAA", 5, Decimal("100"), "2020-02-03", "")
    response = client.get("/api/v2/portfolio/risk")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INDEX_NOT_READY"


# ------------------------------------------------------------------------------ the broker's holdings


def broker_client(
    monkeypatch: pytest.MonkeyPatch, index: Any, ready_index: bool = True
) -> tuple[TestClient, Any]:
    rig = make_rig()
    rig.view.refresh(force=True)

    class Index(FakeIndex):
        def is_ready(self) -> bool:
            return ready_index

    class Services:
        pass

    services = Services()
    services.index = Index(index.table)  # type: ignore[attr-defined]
    monkeypatch.setattr(v2_router, "services", lambda: services)
    app = FastAPI()
    app.add_exception_handler(v2_router.V2Error, v2_router.v2_error_handler)
    app.include_router(broker_routes.router, prefix="/api/v2")
    app.dependency_overrides[broker_view_service] = lambda: rig.view
    return TestClient(app), rig


def test_the_broker_risk_route_describes_the_stored_holdings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = {s: series(s, walk(rng_returns(300, 40 + i))) for i, s in enumerate(("TCS", "INFY"))}
    web, rig = broker_client(monkeypatch, FakeIndex(table))
    calls = len(rig.reads.calls)
    body = web.get("/api/v2/broker/risk").json()
    assert body["available"] is True
    assert {h["symbol"] for h in body["holdings"]} == {"TCS", "INFY"}
    assert body["holdings"][0]["money_pct"] + body["holdings"][1]["money_pct"] == pytest.approx(
        100.0, abs=0.2
    )
    assert len(rig.reads.calls) == calls  # reading the risk never asks Upstox for anything


def test_broker_holdings_unknown_to_the_market_data_are_named_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = {
        "TCS": series("TCS", walk(rng_returns(300, 50))),
        "OTHER": series("OTHER", walk(rng_returns(300, 51))),
    }
    web, _ = broker_client(monkeypatch, FakeIndex(table))
    body = web.get("/api/v2/broker/risk").json()
    assert [e["symbol"] for e in body["left_out"]] == ["INFY"]


def test_without_market_data_the_broker_risk_route_says_where_to_connect_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web, _ = broker_client(monkeypatch, FakeIndex({}), ready_index=False)
    response = web.get("/api/v2/broker/risk")
    assert response.status_code == 409
    assert (
        response.json()["error"]["message"]
        == "Market data is not connected yet. Open Settings, then Market data."
    )


def test_before_anything_is_connected_there_is_nothing_to_describe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    web, rig = broker_client(monkeypatch, FakeIndex({}))
    rig.view.disconnect()
    body = web.get("/api/v2/broker/risk").json()
    assert body["available"] is False and "no broker holdings" in body["message"]


# ------------------------------------------------------------------------------ what the assistant is told


def test_the_assistants_broker_summary_carries_a_short_risk_picture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = {s: series(s, walk(rng_returns(300, 60 + i))) for i, s in enumerate(("TCS", "INFY"))}
    _, rig = broker_client(monkeypatch, FakeIndex(table))
    rig.view.set_assistant_access(True)
    monkeypatch.setattr(broker_routes, "broker_view_service", lambda: rig.view)
    summary = copilot_wiring._broker_account()
    assert set(summary["risk"]) == {
        "volatility_pct",
        "effective_bets",
        "holdings_counted",
        "sessions",
        "largest_risks",
        "note",
    }
    assert "not a forecast" in summary["risk"]["note"]


def test_the_summary_still_works_when_market_data_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, rig = broker_client(monkeypatch, FakeIndex({}), ready_index=False)
    rig.view.set_assistant_access(True)
    monkeypatch.setattr(broker_routes, "broker_view_service", lambda: rig.view)
    assert "risk" not in copilot_wiring._broker_account()


def test_the_built_in_answer_puts_the_risk_in_plain_words() -> None:
    risk = {
        "volatility_pct": 18.4,
        "effective_bets": 2.3,
        "holdings_counted": 5,
        "sessions": 252,
        "largest_risks": [{"symbol": "TCS", "money_pct": 54.0, "risk_pct": 61.0}],
        "note": NOTE,
    }
    ctx = make_context()
    ctx.portfolio = lambda: {
        "totals": {"value": 100000.0, "cost": 90000.0, "pnl": 10000.0, "pnl_pct": 11.1},
        "warnings": [],
        "holdings": [],
        "risk": risk,
        "note": "n",
    }
    reply = answer_without_ai(
        "how is my portfolio doing?", default_registry(ctx), AnswerContext()
    ).reply
    assert "Typical yearly swing of the whole portfolio: 18.4%" in reply
    assert "about 2.3 independent holdings out of 5" in reply
    assert "TCS: 54% of the money, 61% of the risk" in reply
    assert "not a forecast" in reply
