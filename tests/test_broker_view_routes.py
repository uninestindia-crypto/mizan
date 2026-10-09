"""``/api/v2/broker``: the shape of every reply, the refusals, the writes that need the anti-forgery header, and no key."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quant_system.broker_view import messages
from quant_system.server.app import app as real_app
from quant_system.server.v2 import router as v2_router
from quant_system.server.v2.broker_routes import broker_view_service, router
from tests.broker_fakes import APP_SECRET, SENTINEL, SIGN_IN_CODE, Rig, make_rig

BASE = "/api/v2/broker"
BANNED_IN_A_PATH = ("order", "buy", "sell", "trade", "place", "execute")


@pytest.fixture
def rig() -> Rig:
    return make_rig(key=None)


@pytest.fixture
def client(rig: Rig) -> Iterator[TestClient]:
    app = FastAPI()
    app.add_exception_handler(v2_router.V2Error, v2_router.v2_error_handler)
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[broker_view_service] = lambda: rig.view
    yield TestClient(app)


def test_the_routes_are_exactly_these_and_none_can_trade() -> None:
    found = {
        (method, route.path)
        for route in router.routes
        for method in getattr(route, "methods", set())
    }
    assert found == {
        ("GET", "/broker/status"),
        ("POST", "/broker/upstox/connect"),
        ("DELETE", "/broker/upstox/connect"),
        ("GET", "/broker/snapshot"),
        ("GET", "/broker/risk"),
        ("POST", "/broker/refresh"),
        ("DELETE", "/broker/connection"),
        ("PUT", "/broker/assistant-access"),
    }
    assert not [p for _, p in found for word in BANNED_IN_A_PATH if word in p]


def test_the_routes_are_part_of_the_running_app() -> None:
    paths = real_app.openapi()["paths"]
    assert {"/api/v2/broker/status", "/api/v2/broker/snapshot", "/api/v2/broker/refresh"} <= set(
        paths
    )


def test_status_shape(client: TestClient) -> None:
    body = client.get(f"{BASE}/status").json()
    assert set(body) == {"brokers", "assistant_access", "available"}
    assert set(body["brokers"][0]) == {
        "id",
        "label",
        "set_up",
        "connected",
        "waiting_for_sign_in",
        "key_ends_at",
        "callback_address",
        "message",
    }


def test_connect_opens_the_sign_in_page_and_says_so(client: TestClient, rig: Rig) -> None:
    body = client.post(f"{BASE}/upstox/connect").json()
    assert body["opened"] is True and body["login_address"] == rig.opened[0]
    assert parse_qs(urlsplit(body["login_address"]).query)["response_type"] == ["code"]


def test_connect_without_the_saved_app_keys_is_refused_in_plain_words() -> None:
    rig = make_rig(key=None, keys=None)
    app = FastAPI()
    app.add_exception_handler(v2_router.V2Error, v2_router.v2_error_handler)
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[broker_view_service] = lambda: rig.view
    response = TestClient(app).post(f"{BASE}/upstox/connect")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "BROKER_NOT_SET_UP"
    assert response.json()["error"]["message"] == messages.SAVE_KEYS_FIRST


def test_connect_with_the_return_address_taken_says_what_to_do() -> None:
    rig = make_rig(key=None, busy=True)
    app = FastAPI()
    app.add_exception_handler(v2_router.V2Error, v2_router.v2_error_handler)
    app.include_router(router, prefix="/api/v2")
    app.dependency_overrides[broker_view_service] = lambda: rig.view
    response = TestClient(app).post(f"{BASE}/upstox/connect")
    assert response.status_code == 409 and response.json()["error"]["code"] == "CALLBACK_BUSY"


def test_cancel_is_safe_to_repeat(client: TestClient) -> None:
    assert client.delete(f"{BASE}/upstox/connect").status_code == 200
    assert client.delete(f"{BASE}/upstox/connect").status_code == 200


def test_the_snapshot_before_anything_is_connected_says_what_to_click(client: TestClient) -> None:
    body = client.get(f"{BASE}/snapshot").json()
    assert body["connected"] is False and body["message"] == messages.NOT_CONNECTED
    assert body["view_only"] is True and body["holdings"] == [] and body["totals"] is None


def test_assistant_access_is_off_until_the_person_turns_it_on(client: TestClient) -> None:
    assert client.get(f"{BASE}/status").json()["assistant_access"] is False
    assert (
        client.put(f"{BASE}/assistant-access", json={"allowed": True}).json()["assistant_access"]
        is True
    )
    assert (
        client.put(f"{BASE}/assistant-access", json={"allowed": False}).json()["assistant_access"]
        is False
    )


@pytest.mark.parametrize("body", [{}, {"allowed": "maybe"}, {"allowed": None}, []])
def test_assistant_access_needs_a_yes_or_a_no(client: TestClient, body: Any) -> None:
    assert client.put(f"{BASE}/assistant-access", json=body).status_code == 422


def test_a_whole_visit_connect_look_refresh_leave_never_shows_the_key_or_the_app_secret(
    client: TestClient, rig: Rig
) -> None:
    bodies = []
    reply = client.post(f"{BASE}/upstox/connect")
    bodies.append(reply.text)
    state = parse_qs(urlsplit(reply.json()["login_address"]).query)["state"][0]
    rig.view.finish_login({"code": SIGN_IN_CODE, "state": state})
    bodies.append(client.get(f"{BASE}/status").text)
    snapshot = client.get(f"{BASE}/snapshot")
    bodies.append(snapshot.text)
    assert snapshot.json()["connected"] is True and snapshot.json()["holdings"]
    rig.clock.advance(60)
    bodies.append(client.post(f"{BASE}/refresh").text)
    bodies.append(client.delete(f"{BASE}/connection").text)
    joined = "\n".join(bodies)
    assert SENTINEL not in joined and APP_SECRET not in joined and SIGN_IN_CODE not in joined
    assert json.loads(bodies[-1])["brokers"][0]["connected"] is False


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", f"{BASE}/upstox/connect"),
        ("delete", f"{BASE}/upstox/connect"),
        ("post", f"{BASE}/refresh"),
        ("delete", f"{BASE}/connection"),
        ("put", f"{BASE}/assistant-access"),
    ],
)
def test_every_write_is_refused_without_the_anti_forgery_header(method: str, path: str) -> None:
    client = TestClient(real_app, base_url="http://localhost:8000")
    response = getattr(client, method)(path)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_TOKEN_MISSING"
