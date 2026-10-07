"""``GET /api/v2/live/quotes``: validation, the response shape, and the wiring to the app's services."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quant_system.data.upstox_http import HttpResponse
from quant_system.live import QuoteService, QuoteServiceConfig
from quant_system.market.index import IndexNotReadyError, SymbolNotFoundError
from quant_system.server.v2 import live_routes
from quant_system.server.v2 import router as v2_router
from quant_system.server.v2.credentials import CredentialError
from quant_system.server.v2.live_routes import quote_service, router
from tests.live_fakes import (
    CANARY,
    EXPECTED_FIELDS,
    LISTINGS,
    FakeClock,
    FakeTransport,
    LeakyTransport,
    everyone,
)

PATH = "/api/v2/live/quotes"


def app_with(service: Any) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(v2_router.V2Error, v2_router.v2_error_handler)
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[quote_service] = lambda: service
    return TestClient(app)


def real_service(transport: FakeTransport, key: str = CANARY) -> QuoteService:
    config = QuoteServiceConfig(
        resolve_key=LISTINGS.get, key_provider=lambda: key, transport=transport, clock=FakeClock()
    )
    return QuoteService(config)


class NeverCalled:
    def __init__(self) -> None:
        self.asked = 0

    def fetch(self, symbols: Any) -> Any:
        self.asked += 1
        raise AssertionError("the service must not be reached for a bad request")


# ----------------------------------------------------------------------------- the shape


def test_the_answer_has_exactly_connected_message_and_quotes() -> None:
    client = app_with(real_service(FakeTransport(everyone())))
    body = client.get(PATH, params={"symbols": "TCS,INFY"}).json()
    assert set(body) == {"connected", "message", "quotes"}
    assert (body["connected"], body["message"]) == (True, None)
    assert {s: set(entry) for s, entry in body["quotes"].items()} == {
        "TCS": EXPECTED_FIELDS,
        "INFY": EXPECTED_FIELDS,
    }


def test_a_live_price_comes_through_with_its_label_and_time() -> None:
    client = app_with(real_service(FakeTransport(everyone())))
    entry = client.get(PATH, params={"symbols": "TCS"}).json()["quotes"]["TCS"]
    assert entry == {
        "last_price": 4000.5,
        "change_pct": 0.3,
        "label": "LIVE",
        "as_of": "2026-10-06T10:29:45+05:30",
        "source": "Upstox",
        "message": None,
    }


def test_without_a_key_the_answer_says_not_connected_and_what_to_click() -> None:
    transport = FakeTransport(everyone())
    client = app_with(real_service(transport, key=""))
    body = client.get(PATH, params={"symbols": "TCS,INFY"}).json()
    assert body["connected"] is False
    assert body["message"] == "Add your Upstox key in Settings, then Accounts and keys."
    assert {s: e["label"] for s, e in body["quotes"].items()} == {
        "TCS": "UNAVAILABLE",
        "INFY": "UNAVAILABLE",
    }
    assert transport.calls == []


def test_a_busy_upstox_is_a_normal_answer_not_an_error_page() -> None:
    client = app_with(real_service(FakeTransport(HttpResponse(429, b"{}", {}))))
    response = client.get(PATH, params={"symbols": "TCS"})
    assert response.status_code == 200
    assert response.json()["message"] == "Upstox is busy. Try again in a minute."


def test_the_key_never_reaches_the_person_even_when_the_connection_breaks_badly() -> None:
    client = app_with(real_service(LeakyTransport(everyone())))
    response = client.get(PATH, params={"symbols": "TCS"})
    assert (response.status_code, CANARY in response.text) == (200, False)


def test_only_get_is_offered_so_nothing_can_be_written_through_this_route() -> None:
    methods = {m for route in router.routes for m in getattr(route, "methods", set())}
    assert methods == {"GET"}
    assert router.prefix == "/live"


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_writing_to_the_route_is_refused(method: str) -> None:
    client = app_with(NeverCalled())
    assert getattr(client, method)(PATH, params={"symbols": "TCS"}).status_code == 405


# -------------------------------------------------------------------------- validation


def test_symbols_are_upper_cased_and_repeats_are_asked_for_once() -> None:
    client = app_with(real_service(FakeTransport(everyone())))
    body = client.get(PATH, params={"symbols": "tcs, infy,TCS,"}).json()
    assert list(body["quotes"]) == ["TCS", "INFY"]


def test_twenty_symbols_are_allowed() -> None:
    twenty = ",".join(f"SYM{n}" for n in range(20))
    client = app_with(real_service(FakeTransport(everyone())))
    body = client.get(PATH, params={"symbols": twenty}).json()
    assert len(body["quotes"]) == 20


def test_twenty_one_symbols_are_refused_with_a_clear_message() -> None:
    twenty_one = ",".join(f"SYM{n}" for n in range(21))
    service = NeverCalled()
    response = app_with(service).get(PATH, params={"symbols": twenty_one})
    error = response.json()["error"]
    assert (response.status_code, error["code"]) == (422, "TOO_MANY_SYMBOLS")
    assert error["message"] == "Ask for at most 20 shares at a time."
    assert service.asked == 0


def test_repeats_do_not_count_towards_the_limit() -> None:
    many = ",".join(["TCS"] * 30)
    body = (
        app_with(real_service(FakeTransport(everyone()))).get(PATH, params={"symbols": many}).json()
    )
    assert list(body["quotes"]) == ["TCS"]


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param("TCS.NS", id="dot"),
        pytest.param("TC S", id="space-inside"),
        pytest.param("TCS$", id="dollar"),
        pytest.param("TCS;DROP", id="semicolon"),
        pytest.param("../etc", id="path"),
        pytest.param("A" * 16, id="sixteen-characters"),
        pytest.param("TCSſ", id="a-letter-that-upper-cases-into-ascii"),
        pytest.param("๗๗", id="non-latin-digits"),
        pytest.param("TCS%0A", id="percent-sign"),
    ],
)
def test_an_invalid_symbol_is_refused_before_anything_is_asked(bad: str) -> None:
    service = NeverCalled()
    response = app_with(service).get(PATH, params={"symbols": f"INFY,{bad}"})
    error = response.json()["error"]
    assert (response.status_code, error["code"]) == (422, "INVALID_SYMBOL")
    assert error["message"].endswith("is not a valid share symbol.")
    assert service.asked == 0


@pytest.mark.parametrize("good", ["M&M", "BAJAJ-AUTO", "A", "A" * 15, "3MINDIA", "m&m"])
def test_symbols_that_nse_really_uses_are_accepted(good: str) -> None:
    client = app_with(real_service(FakeTransport(everyone())))
    response = client.get(f"{PATH}?symbols={quote(good)}")
    assert (response.status_code, list(response.json()["quotes"])) == (200, [good.upper()])


@pytest.mark.parametrize("query", ["", "?symbols=", "?symbols=,,", "?symbols=%20"])
def test_asking_for_nothing_is_refused_plainly(query: str) -> None:
    service = NeverCalled()
    response = app_with(service).get(PATH + query)
    assert (response.status_code, response.json()["error"]["code"]) == (422, "NO_SYMBOLS")
    assert response.json()["error"]["message"] == "Choose at least one share to price."


def test_the_refusal_uses_the_same_error_shape_as_the_rest_of_the_api() -> None:
    error = app_with(NeverCalled()).get(PATH, params={"symbols": "$"}).json()["error"]
    assert set(error) == {"code", "message", "details", "request_id", "timestamp"}


def test_a_long_bad_symbol_is_not_echoed_back_in_full() -> None:
    error = app_with(NeverCalled()).get(PATH, params={"symbols": "x." * 500}).json()["error"]
    assert len(error["message"]) < 80


# --------------------------------------------------------------------------- the wiring


class FakeIndex:
    def __init__(self, ready: bool = True, **rows: Any) -> None:
        self.ready, self.rows = ready, rows

    def is_ready(self) -> bool:
        return self.ready

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        row = self.rows.get(symbol)
        if isinstance(row, Exception):
            raise row
        if row is None:
            raise SymbolNotFoundError(symbol)
        return {"symbol": symbol, "instrument_key": row, "snapshot": None}


@pytest.mark.parametrize(
    ("index", "symbol", "expected"),
    [
        pytest.param(
            FakeIndex(TCS="NSE_EQ|INE467B01029"), "TCS", "NSE_EQ|INE467B01029", id="known"
        ),
        pytest.param(FakeIndex(TCS="NSE_EQ|INE467B01029"), "NOPE", None, id="unknown"),
        pytest.param(FakeIndex(TCS=""), "TCS", None, id="blank-listing"),
        pytest.param(FakeIndex(ready=False), "TCS", None, id="index-not-built-yet"),
        pytest.param(
            FakeIndex(TCS=IndexNotReadyError("x")), "TCS", None, id="index-vanishes-mid-call"
        ),
        pytest.param(
            FakeIndex(TCS=sqlite3.OperationalError("old schema")),
            "TCS",
            None,
            id="old-index-layout",
        ),
    ],
)
def test_the_listing_comes_from_the_market_index_and_a_missing_one_is_just_unknown(
    index: FakeIndex, symbol: str, expected: str | None
) -> None:
    assert live_routes.index_resolver(index)(symbol) == expected


class FakeStore:
    def __init__(self, **saved: str | Exception) -> None:
        self.saved = saved

    def get(self, name: str) -> str | None:
        value = self.saved.get(name)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.mark.parametrize(
    ("env", "saved", "expected"),
    [
        pytest.param({}, {}, "", id="nothing-anywhere"),
        pytest.param({"UPSTOX_ACCESS_TOKEN": "access"}, {}, "access", id="access-only"),
        pytest.param(
            {"UPSTOX_ACCESS_TOKEN": "access", "UPSTOX_ANALYTICS_TOKEN": "analytics"},
            {},
            "analytics",
            id="analytics-wins-over-access",
        ),
        pytest.param(
            {}, {"UPSTOX_ANALYTICS_TOKEN": "saved"}, "saved", id="falls-back-to-the-saved-key"
        ),
        pytest.param(
            {"UPSTOX_ACCESS_TOKEN": "access"},
            {"UPSTOX_ANALYTICS_TOKEN": "saved"},
            "saved",
            id="a-saved-analytics-key-beats-an-access-key-in-the-environment",
        ),
        pytest.param(
            {"UPSTOX_ANALYTICS_TOKEN": "  spaced  "}, {}, "spaced", id="whitespace-trimmed"
        ),
        pytest.param(
            {"UPSTOX_ANALYTICS_TOKEN": "  "},
            {"UPSTOX_ACCESS_TOKEN": "saved"},
            "saved",
            id="blank-is-absent",
        ),
        pytest.param(
            {},
            {"UPSTOX_ANALYTICS_TOKEN": CredentialError("x")},
            "",
            id="the-store-failing-is-no-key",
        ),
        pytest.param(
            {}, {"UPSTOX_ANALYTICS_TOKEN": OSError("x")}, "", id="the-store-unreadable-is-no-key"
        ),
    ],
)
def test_the_key_comes_from_the_environment_first_then_the_saved_keys(
    env: dict[str, str], saved: dict[str, Any], expected: str
) -> None:
    assert live_routes.key_provider(FakeStore(**saved), env)() == expected


@pytest.fixture()
def fake_services(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    holder = SimpleNamespace(index=FakeIndex(TCS="NSE_EQ|INE467B01029"), credentials=FakeStore())
    monkeypatch.setattr(v2_router, "services", lambda: holder)
    monkeypatch.setattr(live_routes, "_built", None)
    yield holder


def test_one_service_is_shared_so_the_ten_second_cache_survives_between_requests(
    fake_services: SimpleNamespace,
) -> None:
    assert quote_service() is quote_service()


def test_a_reset_of_the_app_services_gives_a_fresh_price_service(
    fake_services: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = quote_service()
    monkeypatch.setattr(
        v2_router, "services", lambda: SimpleNamespace(index=FakeIndex(), credentials=FakeStore())
    )
    assert quote_service() is not first


def test_the_real_dependency_resolves_symbols_through_the_apps_market_index(
    fake_services: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport(everyone())
    monkeypatch.setattr(live_routes, "_transport", lambda: transport)
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", CANARY)
    answer = quote_service().quotes(["TCS", "NOPE"])
    assert (answer["TCS"]["last_price"], answer["NOPE"]["label"]) == (4000.5, "UNAVAILABLE")
    assert (len(transport.calls), transport.calls[0].url.endswith("INE467B01029")) == (1, True)


def test_the_route_module_can_be_imported_before_the_router_it_is_wired_into() -> None:
    source = Path(live_routes.__file__).read_text(encoding="utf-8")
    top_level = [line for line in source.splitlines() if line.startswith(("from ", "import "))]
    assert [line for line in top_level if "server.v2.router" in line] == []


def test_the_response_is_plain_json() -> None:
    client = app_with(real_service(FakeTransport(everyone())))
    text = client.get(PATH, params={"symbols": "TCS"}).text
    assert json.loads(text)["quotes"]["TCS"]["source"] == "Upstox"


def test_seed_resolver_resolves_common_symbols_without_index() -> None:
    res = live_routes.seed_resolver()
    assert res("INFY") == "NSE_EQ|INE009A01021"
    assert res("TCS") == "NSE_EQ|INE467B01029"
    assert res("UNKNOWN_XYZ") is None


def test_combined_resolver_falls_back_to_seed_instruments_when_index_is_empty() -> None:
    res = live_routes.combined_resolver(FakeIndex())
    assert res("INFY") == "NSE_EQ|INE009A01021"
    assert res("UNKNOWN_XYZ") is None


def test_combined_resolver_prefers_index_over_seed() -> None:
    res = live_routes.combined_resolver(FakeIndex(INFY="CUSTOM_KEY"))
    assert res("INFY") == "CUSTOM_KEY"
