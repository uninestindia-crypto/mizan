"""Which Upstox key is used, whether it is ready, and that a refused key is not sent again and again."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from quant_system.data.upstox_http import HttpResponse
from quant_system.live import QuoteService, QuoteServiceConfig, messages
from quant_system.live.upstox_key import pick_key
from quant_system.server.v2 import live_routes
from quant_system.server.v2.credentials import CredentialError
from tests.live_fakes import (
    CANARY,
    LISTINGS,
    OPEN_NOW,
    FakeClock,
    FakeTransport,
    everyone,
    make_jwt,
)
from tests.test_live_routes import FakeStore

GOOD = make_jwt(OPEN_NOW + timedelta(days=30))
GOOD_TOO = make_jwt(OPEN_NOW + timedelta(hours=5))
EXPIRED = make_jwt(OPEN_NOW - timedelta(days=1))
ANALYTICS, ACCESS = "UPSTOX_ANALYTICS_TOKEN", "UPSTOX_ACCESS_TOKEN"


def _read(**keys: str) -> Any:
    return lambda name: keys.get(name)


@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        pytest.param({ANALYTICS: EXPIRED, ACCESS: GOOD}, GOOD, id="expired-analytics-good-access"),
        pytest.param({ANALYTICS: GOOD, ACCESS: GOOD_TOO}, GOOD, id="both-good-analytics-first"),
        pytest.param({ANALYTICS: GOOD, ACCESS: EXPIRED}, GOOD, id="good-analytics-expired-access"),
        pytest.param({ANALYTICS: EXPIRED, ACCESS: EXPIRED}, EXPIRED, id="both-expired-the-first"),
        pytest.param({ANALYTICS: "  ", ACCESS: EXPIRED}, EXPIRED, id="only-an-expired-access"),
        pytest.param(
            {ANALYTICS: "plain-key", ACCESS: GOOD}, "plain-key", id="unknown-expiry-is-tried"
        ),
        pytest.param(
            {ANALYTICS: EXPIRED, ACCESS: "plain-key"}, "plain-key", id="expired-then-unknown"
        ),
        pytest.param({ACCESS: f"  {GOOD}  "}, GOOD, id="whitespace-trimmed"),
        pytest.param({}, "", id="nothing"),
        pytest.param({ANALYTICS: "", ACCESS: "  "}, "", id="only-blanks"),
    ],
)
def test_the_first_key_that_can_still_be_used_is_chosen(
    keys: dict[str, str], expected: str
) -> None:
    assert pick_key(_read(**keys), OPEN_NOW) == expected


def test_the_provider_passes_over_an_expired_key_when_another_is_good() -> None:
    store = FakeStore(UPSTOX_ANALYTICS_TOKEN=EXPIRED, UPSTOX_ACCESS_TOKEN=GOOD)
    assert live_routes.key_provider(store, {}, lambda: OPEN_NOW)() == GOOD


@pytest.mark.parametrize(
    ("env", "saved", "ready", "message"),
    [
        pytest.param({}, {}, False, messages.NO_KEY, id="no-key-at-all"),
        pytest.param({ANALYTICS: GOOD}, {}, True, None, id="a-good-key-in-the-environment"),
        pytest.param({}, {ACCESS: GOOD}, True, None, id="a-good-saved-key"),
        pytest.param({ANALYTICS: "plain-key"}, {}, True, None, id="a-key-with-no-expiry-is-tried"),
        pytest.param(
            {ANALYTICS: EXPIRED}, {}, False, messages.KEY_EXPIRED, id="only-an-expired-key"
        ),
        pytest.param(
            {}, {ANALYTICS: EXPIRED}, False, messages.KEY_EXPIRED, id="a-saved-expired-key"
        ),
        pytest.param(
            {ANALYTICS: EXPIRED, ACCESS: GOOD}, {}, True, None, id="expired-analytics-good-access"
        ),
        pytest.param({}, {ANALYTICS: EXPIRED, ACCESS: GOOD}, True, None, id="the-same-when-saved"),
        pytest.param(
            {}, {ANALYTICS: CredentialError("x")}, False, messages.NO_KEY, id="the-store-failing"
        ),
    ],
)
def test_the_status_says_ready_only_when_the_chosen_key_can_be_used(
    env: dict[str, str], saved: dict[str, Any], ready: bool, message: str | None
) -> None:
    answer = live_routes.key_readiness(FakeStore(**saved), env, lambda: OPEN_NOW)
    assert answer == {"ready": ready, "message": message}


def test_an_expired_key_is_told_in_words_that_name_the_click() -> None:
    answer = live_routes.key_readiness(FakeStore(), {ANALYTICS: EXPIRED}, lambda: OPEN_NOW)
    assert answer["message"] == (
        "Your Upstox key has expired. Open Settings, then Accounts and keys, and sign in again."
    )


def test_the_readiness_never_returns_the_key() -> None:
    answer = live_routes.key_readiness(FakeStore(), {ANALYTICS: CANARY}, lambda: OPEN_NOW)
    assert CANARY not in repr(answer)


# ------------------------------------------------------------------------------ a refused key

REFUSED = HttpResponse(401, b"{}", {})


def _service(transport: FakeTransport, clock: FakeClock, keys: list[str]) -> QuoteService:
    config = QuoteServiceConfig(
        resolve_key=LISTINGS.get,
        key_provider=lambda: keys[0],
        transport=transport,
        clock=clock,
    )
    return QuoteService(config)


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_key_is_not_sent_again_for_a_minute_and_then_is_tried_once_more(
    status: int,
) -> None:
    clock = FakeClock()
    transport = FakeTransport(HttpResponse(status, b"{}", {}), everyone())
    service = _service(transport, clock, [CANARY])
    first = service.fetch(["TCS"])
    clock.advance(30)
    second = service.fetch(["INFY"])
    clock.advance(29)
    third = service.fetch(["TCS", "INFY"])
    assert len(transport.calls) == 1
    assert (first.message, second.message, third.message) == (messages.KEY_REJECTED,) * 3
    assert [b.connected for b in (first, second, third)] == [False, False, False]
    clock.advance(1)
    assert (service.fetch(["TCS"]).connected, len(transport.calls)) == (True, 2)


def test_a_newly_saved_key_is_tried_at_once_even_while_the_old_one_is_remembered_as_refused() -> (
    None
):
    clock, keys = FakeClock(), [CANARY]
    transport = FakeTransport(REFUSED, everyone())
    service = _service(transport, clock, keys)
    assert service.fetch(["TCS"]).connected is False
    keys[0] = "a-different-key"
    batch = service.fetch(["TCS"])
    assert (batch.connected, len(transport.calls)) == (True, 2)
    assert transport.calls[1].headers["Authorization"] == "Bearer a-different-key"


def test_going_back_to_the_refused_key_within_the_minute_does_not_send_it_again() -> None:
    clock, keys = FakeClock(), [CANARY]
    transport = FakeTransport(REFUSED, everyone())
    service = _service(transport, clock, keys)
    service.fetch(["TCS"])
    keys[0] = "another-key"
    service.fetch(["TCS"])
    keys[0] = CANARY
    clock.advance(11)
    assert service.fetch(["INFY"]).connected is False
    assert len(transport.calls) == 2  # the refused key was sent once; the other key once


def test_the_refused_key_itself_is_not_kept_anywhere_in_the_service() -> None:
    service = _service(FakeTransport(REFUSED), FakeClock(), [CANARY])
    service.fetch(["TCS"])
    assert CANARY not in repr(vars(service._rejections))  # only a one-way mark of it is held
