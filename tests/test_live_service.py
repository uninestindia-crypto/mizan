"""How the live-price service behaves when Upstox is slow, busy or refuses a batch because of one bad share.

The batch-splitting tests use a stand-in for Upstox that refuses any request naming a bad share. That is how the
real service is believed to behave, but it could not be checked against the real service, so the proof here is
only as good as that assumption.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from quant_system.data.upstox_http import HttpResponse
from quant_system.live import QuoteService, QuoteServiceConfig, messages
from tests.live_fakes import (
    CANARY,
    FRESH,
    FakeClock,
    FakeTransport,
    build,
    everyone,
    reply,
    tick,
)

BUSY_FOR = HttpResponse(429, b"{}", {"Retry-After": "300"})
SERVER_ERROR = HttpResponse(500, b"oops", {})


class ReentrantTransport(FakeTransport):
    """While its first request is still in flight, another request finishes: a second visitor arriving."""

    def __init__(self, during: Callable[[], Any], *outcomes: HttpResponse) -> None:
        super().__init__(*outcomes)
        self.during = during
        self.fired = False

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        if not self.fired:
            self.fired = True
            self.during()
        return super().get(url, **kwargs)


def test_a_short_wait_that_arrives_late_does_not_cut_a_longer_one_short() -> None:
    clock = FakeClock()
    holder: dict[str, QuoteService] = {}
    transport = ReentrantTransport(
        lambda: holder["service"].fetch(["INFY"]), BUSY_FOR, SERVER_ERROR, everyone()
    )
    holder["service"] = service = build(transport, clock)
    service.fetch(["TCS"])  # while it waits, INFY's request is told to wait five minutes
    asked = len(transport.calls)
    clock.advance(11)
    after_ten_seconds = service.fetch(["RELIANCE"])
    still_asked = len(transport.calls)
    clock.advance(289)
    after_five_minutes = service.fetch(["RELIANCE"])
    assert (after_ten_seconds.message, still_asked) == (messages.BUSY_LONGER, asked)
    assert (after_five_minutes.message, len(transport.calls)) == (None, asked + 1)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        pytest.param(HttpResponse(429, b"{}", {}), messages.BUSY, id="busy-with-no-wait-given"),
        pytest.param(HttpResponse(429, b"{}", {"Retry-After": "30"}), messages.BUSY, id="busy-30s"),
        pytest.param(
            HttpResponse(429, b"{}", {"Retry-After": "120"}), messages.BUSY, id="busy-120s"
        ),
        pytest.param(
            HttpResponse(429, b"{}", {"Retry-After": "121"}), messages.BUSY_LONGER, id="busy-121s"
        ),
        pytest.param(
            HttpResponse(429, b"{}", {"Retry-After": "3600"}),
            messages.BUSY_LONGER,
            id="busy-an-hour",
        ),
        pytest.param(
            HttpResponse(429, b"{}", {"Retry-After": "99999"}),
            messages.BUSY,
            id="a-wait-too-big-to-believe",
        ),
        pytest.param(
            HttpResponse(503, b"{}", {"Retry-After": "60"}), messages.UNAVAILABLE_NOW, id="down-60s"
        ),
        pytest.param(
            HttpResponse(503, b"{}", {"Retry-After": "600"}),
            messages.UNAVAILABLE_LONGER,
            id="down-ten-minutes",
        ),
        pytest.param(SERVER_ERROR, messages.UNAVAILABLE_NOW, id="down-with-no-wait-given"),
    ],
)
def test_a_wait_longer_than_two_minutes_is_not_called_a_minute(
    response: HttpResponse, message: str
) -> None:
    service = build(FakeTransport(response))
    first = service.fetch(["TCS"])
    assert first.message == message
    assert service.fetch(["INFY"]).message == message  # the same words while it is being left alone


@pytest.mark.parametrize("text", [messages.BUSY_LONGER, messages.UNAVAILABLE_LONGER])
def test_the_longer_waits_say_what_to_do_in_plain_words(text: str) -> None:
    assert text.endswith("Try again in a few minutes.") and not any(c.isdigit() for c in text)


# --------------------------------------------------------------------------- one bad share in a batch


def key_of(symbol: str) -> str:
    return f"NSE_EQ|{symbol}"


class PickyUpstox:
    """Refuses a whole request that names a bad share, and otherwise prices every share it is asked about."""

    def __init__(self, bad: set[str], status: int = 400) -> None:
        self.bad, self.status = {key_of(s) for s in bad}, status
        self.calls: list[list[str]] = []

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        wanted = url.split("instrument_key=", 1)[1].split(",")
        self.calls.append(wanted)
        if self.bad & set(wanted):
            return HttpResponse(self.status, b"{}", {})
        data = {
            f"NSE_EQ:{k.split('|')[1]}": tick(k, 100.0 + n, FRESH) for n, k in enumerate(wanted)
        }
        return reply(data)


def picky_service(upstox: Any) -> QuoteService:
    config = QuoteServiceConfig(
        resolve_key=key_of, key_provider=lambda: CANARY, transport=upstox, clock=FakeClock()
    )
    return QuoteService(config)


def labels(batch: Any) -> dict[str, str]:
    return {symbol: entry.label.value for symbol, entry in batch.quotes.items()}


@pytest.mark.parametrize("status", [400, 404, 405, 422])
def test_one_bad_share_does_not_take_the_others_down_with_it(status: int) -> None:
    upstox = PickyUpstox({"INFY"}, status)
    batch = picky_service(upstox).fetch(["TCS", "INFY", "RELIANCE"])
    assert labels(batch) == {"TCS": "LIVE", "INFY": "UNAVAILABLE", "RELIANCE": "LIVE"}
    assert batch.quotes["INFY"].message == messages.no_price("INFY")
    assert (batch.connected, batch.message) == (True, None)
    assert len(upstox.calls) <= 6


@pytest.mark.parametrize("bad", ["S0", "S7", "S12", "S19"])
def test_a_big_batch_with_one_bad_share_costs_at_most_six_requests_and_still_prices_most(
    bad: str,
) -> None:
    symbols = [f"S{n}" for n in range(20)]
    upstox = PickyUpstox({bad})
    batch = picky_service(upstox).fetch(symbols)
    priced = [s for s, label in labels(batch).items() if label == "LIVE"]
    assert len(upstox.calls) <= 6
    assert bad not in priced and len(priced) >= 15
    assert batch.connected is True


def test_a_share_that_is_still_refused_is_not_asked_for_again_within_ten_seconds() -> None:
    upstox = PickyUpstox({"INFY"})
    service = picky_service(upstox)
    service.fetch(["TCS", "INFY", "RELIANCE"])
    asked = len(upstox.calls)
    service.fetch(["TCS", "INFY", "RELIANCE"])
    assert len(upstox.calls) == asked


def test_a_batch_where_every_share_is_refused_is_reported_once_and_then_left_alone() -> None:
    upstox = PickyUpstox({"TCS", "INFY", "RELIANCE", "WIPRO"})
    service = picky_service(upstox)
    first = service.fetch(["TCS", "INFY", "RELIANCE", "WIPRO"])
    asked = len(upstox.calls)
    second = service.fetch(["TCS", "INFY", "RELIANCE", "WIPRO"])
    assert (first.message, second.message) == (messages.UNAVAILABLE_NOW, messages.UNAVAILABLE_NOW)
    assert set(labels(first).values()) == {"UNAVAILABLE"} and asked <= 6
    assert len(upstox.calls) == asked


def test_a_single_share_that_is_refused_is_not_split_and_is_reported_as_before() -> None:
    upstox = PickyUpstox({"TCS"})
    batch = picky_service(upstox).fetch(["TCS"])
    assert (len(upstox.calls), batch.message) == (1, messages.UNAVAILABLE_NOW)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        pytest.param(HttpResponse(401, b"{}", {}), messages.KEY_REJECTED, id="key-refused"),
        pytest.param(HttpResponse(403, b"{}", {}), messages.KEY_REJECTED, id="key-forbidden"),
        pytest.param(HttpResponse(429, b"{}", {}), messages.BUSY, id="busy"),
        pytest.param(HttpResponse(408, b"{}", {}), messages.TOO_SLOW, id="timeout"),
        pytest.param(SERVER_ERROR, messages.UNAVAILABLE_NOW, id="server-error"),
    ],
)
def test_only_a_refused_request_is_split_never_a_busy_or_broken_one(
    response: HttpResponse, message: str
) -> None:
    transport = FakeTransport(response)
    batch = build(transport).fetch(["TCS", "INFY", "RELIANCE"])
    assert (len(transport.calls), batch.message) == (1, message)


def test_a_busy_answer_while_looking_for_the_bad_share_stops_the_search() -> None:
    transport = FakeTransport(HttpResponse(400, b"{}", {}), HttpResponse(429, b"{}", {}))
    batch = build(transport).fetch(["TCS", "INFY", "RELIANCE"])
    assert (len(transport.calls), batch.message, batch.connected) == (2, messages.BUSY, True)
    assert set(labels(batch).values()) == {"UNAVAILABLE"}


def test_prices_already_found_are_kept_when_the_search_is_stopped_by_a_busy_answer() -> None:
    refused = HttpResponse(400, b"{}", {})
    first_half = reply(
        {
            "NSE_EQ:TCS": tick("NSE_EQ|INE467B01029", 4000.5, FRESH),
            "NSE_EQ:INFY": tick("NSE_EQ|INE009A01021", 1500.0, FRESH),
        }
    )
    transport = FakeTransport(refused, first_half, HttpResponse(429, b"{}", {}))
    batch = build(transport).fetch(["TCS", "INFY", "RELIANCE"])
    assert labels(batch) == {"TCS": "LIVE", "INFY": "LIVE", "RELIANCE": "UNAVAILABLE"}
    assert (batch.message, len(transport.calls)) == (messages.BUSY, 3)


def test_the_key_is_not_in_what_the_split_requests_say_about_themselves() -> None:
    upstox = PickyUpstox({"INFY"})
    batch = picky_service(upstox).fetch(["TCS", "INFY", "RELIANCE"])
    assert CANARY not in json.dumps(batch.as_dict()) + json.dumps(upstox.calls)
