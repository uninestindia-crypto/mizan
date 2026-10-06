"""Read-only live prices: every way Upstox can fail, and proof that the key never leaks."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

import quant_system.live as live_package
from quant_system.data.upstox_http import (
    HttpResponse,
    ResponseTooLarge,
    TransportConnectionError,
    TransportTimeout,
)
from quant_system.live import messages
from tests.live_fakes import (
    CANARY,
    OPEN_NOW,
    TCS_LISTING,
    FakeClock,
    FakeTransport,
    LeakyTransport,
    build,
    everyone,
    make_jwt,
    reply,
    tick,
)

# --------------------------------------------------------------------------- failures

FAILURES = [
    pytest.param(HttpResponse(401, b"{}", {}), messages.KEY_REJECTED, False, id="401"),
    pytest.param(HttpResponse(403, b"{}", {}), messages.KEY_REJECTED, False, id="403"),
    pytest.param(HttpResponse(429, b"{}", {}), messages.BUSY, True, id="429"),
    pytest.param(HttpResponse(408, b"{}", {}), messages.TOO_SLOW, True, id="408"),
    pytest.param(HttpResponse(500, b"oops", {}), messages.UNAVAILABLE_NOW, True, id="500"),
    pytest.param(HttpResponse(400, b"{}", {}), messages.UNAVAILABLE_NOW, True, id="400"),
    pytest.param(TransportConnectionError("down"), messages.UNREACHABLE, True, id="network-down"),
    pytest.param(TransportTimeout("slow"), messages.TOO_SLOW, True, id="timeout"),
    pytest.param(
        ResponseTooLarge("big"), messages.TOO_LARGE, True, id="transport-refuses-a-huge-reply"
    ),
    pytest.param(
        RuntimeError("anything"), messages.UNREACHABLE, True, id="anything-else-going-wrong"
    ),
    pytest.param(
        HttpResponse(200, b"not json", {}), messages.UNREADABLE, True, id="malformed-json"
    ),
    pytest.param(
        HttpResponse(200, b"\xff\xfe\x00", {}), messages.UNREADABLE, True, id="not-even-text"
    ),
    pytest.param(
        HttpResponse(200, b"[]", {}), messages.UNREADABLE, True, id="json-but-not-an-object"
    ),
    pytest.param(
        HttpResponse(200, b'{"status": "error"}', {}), messages.UNREADABLE, True, id="error-status"
    ),
    pytest.param(
        HttpResponse(200, b'{"status": "success", "data": []}', {}),
        messages.UNREADABLE,
        True,
        id="data-is-a-list",
    ),
    pytest.param(
        HttpResponse(200, b"[" * 200_000, {}), messages.UNREADABLE, True, id="absurdly-nested"
    ),
    pytest.param(
        HttpResponse(200, b" " * (512 * 1024 + 1), {}),
        messages.TOO_LARGE,
        True,
        id="body-over-the-cap",
    ),
]


@pytest.mark.parametrize(("outcome", "message", "connected"), FAILURES)
def test_every_failure_is_a_plain_sentence_and_never_an_error(
    outcome: HttpResponse | Exception, message: str, connected: bool
) -> None:
    batch = build(FakeTransport(outcome)).fetch(["TCS", "INFY"])
    assert (batch.connected, batch.message) == (connected, message)
    assert {e.label for e in batch.quotes.values()} == {"UNAVAILABLE"}
    assert {e.message for e in batch.quotes.values()} == {message}
    assert re.search(r"\d|http|token|json|_|error|exception", message, re.IGNORECASE) is None


def test_a_reply_over_the_configured_cap_is_refused_even_if_the_transport_let_it_through() -> None:
    big = HttpResponse(200, b" " * 2048, {})
    batch = build(FakeTransport(big), max_response_bytes=2047).fetch(["TCS"])
    assert batch.message == messages.TOO_LARGE


def test_after_upstox_says_it_is_busy_it_is_left_alone_for_ten_seconds() -> None:
    clock = FakeClock()
    transport = FakeTransport(HttpResponse(429, b"{}", {}), everyone())
    service = build(transport, clock)
    first = service.fetch(["TCS"])
    clock.advance(9.0)
    second = service.fetch(["INFY"])
    clock.advance(1.0)
    third = service.fetch(["TCS"])
    assert (first.message, second.message, third.message) == (messages.BUSY, messages.BUSY, None)
    assert len(transport.calls) == 2


def test_when_upstox_says_how_long_to_wait_it_is_left_alone_that_long() -> None:
    clock = FakeClock()
    busy = HttpResponse(429, b"{}", {"Retry-After": "30"})
    transport = FakeTransport(busy, everyone())
    service = build(transport, clock)
    service.fetch(["TCS"])
    clock.advance(29.0)
    still_waiting = service.fetch(["TCS"])
    clock.advance(1.0)
    assert (still_waiting.message, service.fetch(["TCS"]).message, len(transport.calls)) == (
        messages.BUSY,
        None,
        2,
    )


def test_prices_already_held_are_still_served_while_upstox_is_being_left_alone() -> None:
    clock = FakeClock()
    transport = FakeTransport(
        reply({"NSE_EQ:TCS": tick(TCS_LISTING, 4000.5)}), HttpResponse(429, b"{}", {})
    )
    service = build(transport, clock)
    service.fetch(["TCS"])
    clock.advance(5.0)
    service.fetch(["INFY"])  # the busy answer arrives for INFY
    batch = service.fetch(["TCS", "INFY"])
    labels = {symbol: entry.label for symbol, entry in batch.quotes.items()}
    assert (batch.message, labels, len(transport.calls)) == (
        messages.BUSY,
        {"TCS": "LIVE", "INFY": "UNAVAILABLE"},
        2,
    )


def test_some_failures_name_where_to_click_and_none_name_a_setting_or_a_code() -> None:
    clicks = [messages.NO_KEY, messages.KEY_EXPIRED, messages.KEY_REJECTED]
    assert all("Settings, then Accounts and keys" in text for text in clicks)


@pytest.mark.parametrize(
    "name",
    sorted(n for n in dir(messages) if n.isupper()),
)
def test_no_message_names_a_variable_a_code_or_a_file(name: str) -> None:
    text = getattr(messages, name)
    assert (
        re.search(r"[A-Z]{2,}_[A-Z]|\.env|http|\b[45]\d\d\b|terminal|command", text, re.IGNORECASE)
        is None
    )


# --------------------------------------------------------------------- the key never leaks

LEAKS = [
    pytest.param(
        lambda: FakeTransport(HttpResponse(401, CANARY.encode(), {"x": CANARY})),
        id="401-echoing-it",
    ),
    pytest.param(
        lambda: FakeTransport(HttpResponse(200, CANARY.encode(), {})), id="garbled-reply-with-it"
    ),
    pytest.param(
        lambda: FakeTransport(TransportConnectionError(f"failed for {CANARY}")),
        id="network-error-with-it",
    ),
    pytest.param(lambda: FakeTransport(TransportTimeout(CANARY)), id="timeout-with-it"),
    pytest.param(lambda: FakeTransport(ResponseTooLarge(CANARY)), id="oversized-with-it"),
    pytest.param(lambda: LeakyTransport(everyone()), id="library-that-prints-its-headers"),
    pytest.param(
        lambda: FakeTransport(HttpResponse(500, CANARY.encode(), {})), id="server-error-echoing-it"
    ),
]


@pytest.mark.parametrize("make_transport", LEAKS)
def test_the_key_never_appears_in_an_answer_an_error_or_the_log(
    make_transport: Callable[[], FakeTransport], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    service = build(make_transport())
    batch = service.fetch(["TCS"])
    shown = json.dumps(batch.as_dict()) + repr(batch) + repr(service) + caplog.text
    assert CANARY not in shown


def test_a_real_looking_key_is_not_echoed_when_it_is_expired_either() -> None:
    expired = make_jwt(OPEN_NOW - timedelta(days=1), sub=CANARY)
    shown = json.dumps(build(FakeTransport(everyone()), key=expired).fetch(["TCS"]).as_dict())
    assert expired not in shown
    assert CANARY not in shown


def test_the_key_goes_only_in_the_authorization_header_of_a_get() -> None:
    transport = FakeTransport(everyone())
    build(transport).quotes(["TCS"])
    call = transport.calls[0]
    assert CANARY not in call.url
    assert [name for name, value in call.headers.items() if CANARY in value] == ["Authorization"]


def test_nothing_in_this_package_can_place_change_or_cancel_an_order() -> None:
    folder = Path(live_package.__file__).parent
    sources = "\n".join(p.read_text(encoding="utf-8") for p in folder.glob("*.py"))
    forbidden = ("/order", "place_order", 'method="POST"', ".post(", ".put(", ".delete(", ".patch(")
    assert [word for word in forbidden if word in sources] == []
