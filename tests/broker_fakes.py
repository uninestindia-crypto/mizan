"""Shared fakes for the broker-view tests: no network, no real account, only invented numbers.

Every transport, vault, listener, clock and browser is injected. The sentinel key below must never appear anywhere a
person, a log, an error or an AI prompt could see it.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from quant_system.broker_view import BrokerView, InMemorySnapshotStore
from quant_system.broker_view.endpoints import (
    UPSTOX_FUNDS_URL,
    UPSTOX_HOLDINGS_URL,
    UPSTOX_POSITIONS_URL,
)
from quant_system.broker_view.loopback import PortBusy
from quant_system.broker_view.upstox_read import UpstoxReader
from quant_system.data.upstox_http import HttpResponse
from tests.live_fakes import OPEN_NOW, Call, FakeClock, make_jwt

SENTINEL = make_jwt(OPEN_NOW + timedelta(hours=17), sub="SENTINEL-KEY-DO-NOT-LEAK")
APP_KEY = "app-key-0000"
# An invented value that tests look for; it is not a real secret.
APP_SECRET = "app-secret-SENTINEL-2"  # pragma: allowlist secret
SIGN_IN_CODE = "mk404x"


class FakeVault:
    def __init__(self, key: str | None = None, available: bool = True) -> None:
        self.key, self._available = key, available
        self.saves: list[str] = []

    @property
    def available(self) -> bool:
        return self._available

    def load(self) -> str | None:
        return self.key

    def save(self, key: str) -> None:
        self.key = key
        self.saves.append(key)

    def forget(self) -> None:
        self.key = None


class FakeReads:
    """A GET-only transport: replies are looked up by address, ignoring the query."""

    def __init__(self, replies: Mapping[str, HttpResponse | Exception] | None = None) -> None:
        self.replies: dict[str, HttpResponse | Exception] = dict(replies or {})
        self.calls: list[Call] = []

    def get(
        self, url: str, *, headers: dict[str, str], timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse:
        self.calls.append(Call(url, dict(headers), timeout_seconds, max_response_bytes))
        outcome = self.replies[url.split("?")[0]]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def asked(self, address: str) -> int:
        return sum(1 for call in self.calls if call.url.split("?")[0] == address)


class FakeSession:
    def __init__(self, exchange: HttpResponse | Exception | None = None) -> None:
        self.exchange = exchange if exchange is not None else token_reply(SENTINEL)
        self.forms: list[dict[str, str]] = []
        self.ended: list[str] = []

    def exchange_code(
        self, form: Mapping[str, str], *, timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse:
        self.forms.append(dict(form))
        if isinstance(self.exchange, Exception):
            raise self.exchange
        return self.exchange

    def end_session(
        self, key: str, *, timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse:
        self.ended.append(key)
        return HttpResponse(200, b"{}", {})


class FakeListener:
    def __init__(self, handler: Callable[[Mapping[str, str]], str], busy: bool) -> None:
        self.handler, self.busy = handler, busy
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        if self.busy:
            raise PortBusy("in use")
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1


class FakeListeners:
    def __init__(self, busy: bool = False) -> None:
        self.busy = busy
        self.made: list[FakeListener] = []

    def __call__(self, handler: Callable[[Mapping[str, str]], str]) -> FakeListener:
        listener = FakeListener(handler, self.busy)
        self.made.append(listener)
        return listener

    @property
    def latest(self) -> FakeListener:
        return self.made[-1]


def success(data: Any) -> HttpResponse:
    return HttpResponse(200, json.dumps({"status": "success", "data": data}).encode(), {})


def failure_reply(status: int, code: str | None = None) -> HttpResponse:
    errors = [{"errorCode": code, "message": "x"}] if code else []
    return HttpResponse(status, json.dumps({"status": "error", "errors": errors}).encode(), {})


def token_reply(key: str | None) -> HttpResponse:
    body: dict[str, Any] = {"user_name": "Invented Name", "email": "invented@example.invalid"}
    if key is not None:
        body["access_token"] = key
    return HttpResponse(200, json.dumps(body).encode(), {})


def holding(symbol: str = "TCS", **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "isin": "INE467B01029",
        "company_name": "Invented Company Limited",
        "trading_symbol": symbol,
        "exchange": "NSE",
        "instrument_token": "NSE_EQ|INE467B01029",
        "product": "D",
        "quantity": 10,
        "t1_quantity": 0,
        "average_price": 3400.0,
        "last_price": 3500.5,
        "close_price": 3480.0,
        "pnl": 1005.0,
        "haircut": 0.1,
        "collateral_quantity": 0,
    }
    row.update(over)
    return row


def position(symbol: str = "INFY", **over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "trading_symbol": symbol,
        "exchange": "NSE",
        "instrument_token": "NSE_EQ|INE009A01021",
        "product": "I",
        "quantity": -5,
        "average_price": 1500.0,
        "last_price": 1490.0,
        "pnl": 50.0,
        "realised": 0.0,
        "unrealised": 50.0,
    }
    row.update(over)
    return row


STANDARD_HOLDINGS = [
    holding("TCS"),
    holding("INFY", quantity=20, average_price=1500.0, last_price=1490.0, close_price=1495.0),
]


def all_replies(
    holdings: list[dict[str, Any]] | None = None,
    positions: list[dict[str, Any]] | None = None,
    funds: dict[str, Any] | None = None,
) -> dict[str, HttpResponse | Exception]:
    return {
        UPSTOX_HOLDINGS_URL: success(STANDARD_HOLDINGS if holdings is None else holdings),
        UPSTOX_POSITIONS_URL: success([position()] if positions is None else positions),
        UPSTOX_FUNDS_URL: success(
            {"equity": {"available_margin": 12000.5, "used_margin": 3000.0}}
            if funds is None
            else funds
        ),
    }


@dataclass
class Rig:
    view: BrokerView
    vault: FakeVault
    store: InMemorySnapshotStore
    reads: FakeReads
    session: FakeSession
    listeners: FakeListeners
    clock: FakeClock
    opened: list[str] = field(default_factory=list)


def make_rig(
    *,
    key: str | None = SENTINEL,
    replies: Mapping[str, HttpResponse | Exception] | None = None,
    keys: tuple[str, str] | None = (APP_KEY, APP_SECRET),
    busy: bool = False,
    session: FakeSession | None = None,
    available: bool = True,
    clock: FakeClock | None = None,
) -> Rig:
    clock = clock or FakeClock()
    vault = FakeVault(key, available)
    store = InMemorySnapshotStore()
    reads = FakeReads(all_replies() if replies is None else replies)
    session = session or FakeSession()
    listeners = FakeListeners(busy)
    opened: list[str] = []

    def open_page(address: str) -> bool:
        opened.append(address)
        return True

    view = BrokerView(
        vault=vault,
        store=store,
        reader=UpstoxReader(reads, clock),
        session=session,
        app_keys=lambda: keys,
        open_page=open_page,
        make_listener=listeners,
        clock=clock,
        background=lambda work: work(),
    )
    return Rig(view, vault, store, reads, session, listeners, clock, opened)
