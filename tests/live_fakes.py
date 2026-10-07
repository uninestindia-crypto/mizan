"""Shared fakes for the live-price tests: a clock, a recording transport, and Upstox-shaped replies.

No test touches the network. The transport and the clock are injected.
"""

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from quant_system.data.upstox_http import (
    HttpResponse,
)
from quant_system.live import QuoteService, QuoteServiceConfig

TCS_LISTING = "NSE_EQ|INE467B01029"
INFY_LISTING = "NSE_EQ|INE009A01021"
RELIANCE_LISTING = "NSE_EQ|INE002A01018"
LISTINGS = {"TCS": TCS_LISTING, "INFY": INFY_LISTING, "RELIANCE": RELIANCE_LISTING}

CANARY = "canary-9f2c41-must-never-appear"
OPEN_NOW = datetime(2026, 10, 6, 5, 0, 0, tzinfo=UTC)  # Tuesday 10:30 in India
FRESH = "2026-10-06T10:29:45+05:30"  # 15 seconds before OPEN_NOW
EXPECTED_FIELDS = {"last_price", "change_pct", "label", "as_of", "source", "message"}


def utc(*moment: int) -> datetime:
    return datetime(*moment, tzinfo=UTC)


class FakeClock:
    def __init__(self, now: datetime = OPEN_NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@dataclass
class Call:
    url: str
    headers: dict[str, str]
    timeout_seconds: float
    max_response_bytes: int


class FakeTransport:
    """Plays its outcomes in order and then repeats the last one. It can only GET."""

    def __init__(self, *outcomes: HttpResponse | Exception) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[Call] = []

    def get(
        self, url: str, *, headers: dict[str, str], timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse:
        self.calls.append(Call(url, dict(headers), timeout_seconds, max_response_bytes))
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class SlowTransport(FakeTransport):
    """A reply that takes `seconds` on the service's own clock."""

    def __init__(self, clock: FakeClock, seconds: float, outcome: HttpResponse) -> None:
        super().__init__(outcome)
        self.clock, self.seconds = clock, seconds

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        self.clock.advance(self.seconds)
        return super().get(url, **kwargs)


class LeakyTransport(FakeTransport):
    """Fails the way a careless library does: with the request headers inside the error text."""

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        super().get(url, **kwargs)
        raise RuntimeError(f"request failed, headers were {kwargs['headers']}")


def tick(
    listing: str, price: float, at: str = FRESH, net_change: float | None = 12.0
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "instrument_token": listing,
        "last_price": price,
        "timestamp": at,
        "ohlc": {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
    }
    if net_change is not None:
        entry["net_change"] = net_change
    return entry


def reply(data: dict[str, Any]) -> HttpResponse:
    return HttpResponse(200, json.dumps({"status": "success", "data": data}).encode(), {})


def everyone(at: str = FRESH) -> HttpResponse:
    return reply(
        {
            "NSE_EQ:TCS": tick(TCS_LISTING, 4000.5, at),
            "NSE_EQ:INFY": tick(INFY_LISTING, 1500.25, at),
            "NSE_EQ:RELIANCE": tick(RELIANCE_LISTING, 2900.0, at),
        }
    )


def make_jwt(expires_at: datetime, **claims: Any) -> str:
    def part(payload: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    body = {"exp": int(expires_at.timestamp()), **claims}
    return ".".join([part({"alg": "none"}), part(body), "c2ln"])


def build(
    transport: FakeTransport,
    clock: FakeClock | None = None,
    key: str = CANARY,
    **overrides: Any,
) -> QuoteService:
    config = QuoteServiceConfig(
        resolve_key=LISTINGS.get,
        key_provider=lambda: key,
        transport=transport,
        clock=clock or FakeClock(),
        **overrides,
    )
    return QuoteService(config)
