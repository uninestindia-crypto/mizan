"""Read-only live prices: labels, matching, batching, caching, and every way Upstox can fail.

No test here touches the network. The transport and the clock are injected, and the Upstox key
variables are never read: each test hands the service its own key provider.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import quant_system.live as live_package
from quant_system.data.upstox_http import (
    HttpResponse,
    ResponseTooLarge,
    TransportConnectionError,
    TransportTimeout,
)
from quant_system.live import QuoteService, QuoteServiceConfig, messages
from quant_system.live.market_hours import is_session_open
from quant_system.market.index import SymbolNotFoundError

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


# ----------------------------------------------------------------------------- labels

LABEL_CASES = [
    pytest.param(OPEN_NOW, FRESH, "LIVE", id="open-and-fresh"),
    pytest.param(OPEN_NOW, "2026-10-06T10:29:01+05:30", "LIVE", id="open-59-seconds-old"),
    pytest.param(
        OPEN_NOW, "2026-10-06T10:29:00+05:30", "DELAYED", id="open-exactly-60-seconds-old"
    ),
    pytest.param(OPEN_NOW, "2026-10-06T10:20:00+05:30", "DELAYED", id="open-ten-minutes-old"),
    pytest.param(
        OPEN_NOW, "2026-10-05T15:30:00+05:30", "DELAYED", id="open-but-quote-is-from-yesterday"
    ),
    pytest.param(
        OPEN_NOW, "2026-10-06T11:30:00+05:30", "DELAYED", id="open-quote-an-hour-in-the-future"
    ),
    pytest.param(
        utc(2026, 10, 6, 4, 0),
        "2026-10-06T09:29:50+05:30",
        "LIVE",
        id="open-at-0930-india-is-0400-utc",
    ),
    pytest.param(
        utc(2026, 10, 6, 11, 0),
        "2026-10-06T15:29:58+05:30",
        "LAST_CLOSE",
        id="1630-india-is-1100-utc-closed",
    ),
    pytest.param(
        utc(2026, 10, 6, 3, 44, 59),
        "2026-10-05T15:30:00+05:30",
        "LAST_CLOSE",
        id="one-second-before-the-open",
    ),
    pytest.param(
        utc(2026, 10, 6, 3, 45, 0), "2026-10-06T09:14:59+05:30", "LIVE", id="the-open-itself"
    ),
    pytest.param(
        utc(2026, 10, 6, 9, 59, 59),
        "2026-10-06T15:29:58+05:30",
        "LIVE",
        id="one-second-before-the-close",
    ),
    pytest.param(
        utc(2026, 10, 6, 10, 0, 0), "2026-10-06T15:29:58+05:30", "LAST_CLOSE", id="the-close-itself"
    ),
    pytest.param(
        utc(2026, 10, 6, 20, 0), "2026-10-06T15:30:00+05:30", "LAST_CLOSE", id="late-evening"
    ),
    pytest.param(
        utc(2026, 10, 10, 5, 0), "2026-10-09T15:30:00+05:30", "LAST_CLOSE", id="saturday-midday"
    ),
    pytest.param(
        utc(2026, 10, 11, 5, 0), "2026-10-09T15:30:00+05:30", "LAST_CLOSE", id="sunday-midday"
    ),
]


@pytest.mark.parametrize(("now", "quoted_at", "expected"), LABEL_CASES)
def test_the_label_follows_the_session_clock_in_india_and_the_age_of_the_quote(
    now: datetime, quoted_at: str, expected: str
) -> None:
    service = build(FakeTransport(everyone(quoted_at)), FakeClock(now))
    entry = service.quotes(["TCS"])["TCS"]
    assert entry["label"] == expected
    assert entry["last_price"] == 4000.5
    assert (entry["message"] is None) == (expected == "LIVE")


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        pytest.param(utc(2026, 10, 6, 5, 0), True, id="tuesday-midday"),
        pytest.param(utc(2026, 10, 9, 9, 59, 59), True, id="friday-last-second"),
        pytest.param(
            utc(2026, 10, 9, 20, 30), False, id="friday-night-utc-is-saturday-morning-in-india"
        ),
        pytest.param(utc(2026, 10, 5, 3, 45), True, id="monday-open"),
        pytest.param(utc(2026, 10, 4, 5, 0), False, id="sunday"),
        pytest.param(datetime(2026, 10, 6, 5, 0), True, id="a-clock-without-a-zone-is-read-as-utc"),
    ],
)
def test_the_session_is_open_only_on_weekdays_between_0915_and_1530_india(
    moment: datetime, expected: bool
) -> None:
    assert is_session_open(moment) is expected


def test_the_time_is_given_with_the_india_offset_whatever_zone_upstox_wrote_it_in() -> None:
    data = {"NSE_EQ:TCS": tick(TCS_LISTING, 4000.5, "2026-10-06T04:59:45+00:00")}
    service = build(FakeTransport(reply(data)))
    assert service.quotes(["TCS"])["TCS"]["as_of"] == "2026-10-06T10:29:45+05:30"


@pytest.mark.parametrize("fraction", [".78", ".250", ".123456"])
def test_fractional_seconds_in_the_quote_time_are_read(fraction: str) -> None:
    """The real feed writes `2026-10-06T11:21:45.78+05:30`: two digits after the point."""
    row = tick(TCS_LISTING, 4000.5, f"2026-10-06T10:29:45{fraction}+05:30")
    entry = build(FakeTransport(reply({"NSE_EQ:TCS": row}))).quotes(["TCS"])["TCS"]
    assert (entry["as_of"], entry["label"]) == ("2026-10-06T10:29:45+05:30", "LIVE")


@pytest.mark.parametrize(
    "stamp",
    [
        pytest.param("2026-10-06T10:29:45", id="no-zone"),
        pytest.param("yesterday", id="not-a-time"),
        pytest.param(1791279585, id="a-number"),
        pytest.param("2026-10-06T10:29:45+05:30" + "0" * 80, id="absurdly-long"),
    ],
)
def test_a_quote_time_that_cannot_be_trusted_means_the_price_is_never_called_live(
    stamp: Any,
) -> None:
    """A time with no zone could be anywhere, so the price is treated as having no time at all."""
    row = tick(TCS_LISTING, 4000.5, stamp)
    entry = build(FakeTransport(reply({"NSE_EQ:TCS": row}))).quotes(["TCS"])["TCS"]
    assert (entry["label"], entry["as_of"], entry["last_price"]) == ("DELAYED", None, 4000.5)


def test_a_price_with_no_time_while_the_market_is_open_is_never_called_live() -> None:
    row = tick(TCS_LISTING, 4000.5)
    del row["timestamp"]
    entry = build(FakeTransport(reply({"NSE_EQ:TCS": row}))).quotes(["TCS"])["TCS"]
    assert (entry["label"], entry["as_of"], entry["message"]) == ("DELAYED", None, messages.NO_TIME)


def test_a_naive_clock_is_read_as_utc() -> None:
    clock = FakeClock(datetime(2026, 10, 6, 5, 0, 0))
    assert build(FakeTransport(everyone()), clock).quotes(["TCS"])["TCS"]["label"] == "LIVE"


@pytest.mark.parametrize(
    ("net_change", "expected"),
    [
        pytest.param(12.0, 0.3, id="up"),
        pytest.param(-24.0, -0.6, id="down"),
        pytest.param(0.0, 0.0, id="flat"),
        pytest.param(None, None, id="the-reply-does-not-say"),
    ],
)
def test_the_change_is_against_the_previous_close_when_the_reply_gives_it(
    net_change: float | None, expected: float | None
) -> None:
    row = tick(TCS_LISTING, 4000.0, net_change=net_change)
    entry = build(FakeTransport(reply({"NSE_EQ:TCS": row}))).quotes(["TCS"])["TCS"]
    assert entry["change_pct"] == expected


@pytest.mark.parametrize("net_change", [4000.0, 5000.0, "up", True, float("nan")])
def test_a_change_that_cannot_be_right_is_left_out_rather_than_guessed(net_change: Any) -> None:
    row = tick(TCS_LISTING, 4000.0, net_change=None)
    row["net_change"] = net_change
    entry = build(FakeTransport(reply({"NSE_EQ:TCS": row}))).quotes(["TCS"])["TCS"]
    assert (entry["change_pct"], entry["label"]) == (None, "LIVE")


@pytest.mark.parametrize(
    "price", [0, -5.0, "four thousand", None, True, float("nan"), float("inf"), 10**400]
)
def test_an_unusable_price_is_unavailable_never_zero(price: Any) -> None:
    row = tick(TCS_LISTING, 1.0)
    row["last_price"] = price
    entry = build(FakeTransport(reply({"NSE_EQ:TCS": row}))).quotes(["TCS"])["TCS"]
    assert entry == {
        "last_price": None,
        "change_pct": None,
        "label": "UNAVAILABLE",
        "as_of": None,
        "source": "Upstox",
        "message": messages.no_price("TCS"),
    }


def test_every_answer_has_exactly_the_fields_the_copilot_expects() -> None:
    answer = build(FakeTransport(everyone())).quotes(["TCS", "INFY"])
    assert {symbol: set(entry) for symbol, entry in answer.items()} == {
        "TCS": EXPECTED_FIELDS,
        "INFY": EXPECTED_FIELDS,
    }
    assert json.loads(json.dumps(answer)) == answer


# ------------------------------------------------------------------ batching and matching


def test_the_whole_request_goes_out_as_one_read_only_call() -> None:
    transport = FakeTransport(everyone())
    build(transport).quotes(["TCS", "INFY", "RELIANCE"])
    (call,) = transport.calls
    assert call.url.startswith("https://api.upstox.com/v2/market-quote/quotes?instrument_key=")
    assert call.url.split("=", 1)[1] == f"{TCS_LISTING},{INFY_LISTING},{RELIANCE_LISTING}"
    assert call.headers["Authorization"] == f"Bearer {CANARY}"
    assert call.headers["Accept"] == "application/json"


def test_the_call_is_bounded_in_time_and_in_size() -> None:
    transport = FakeTransport(everyone())
    build(transport).quotes(["TCS"])
    assert (transport.calls[0].timeout_seconds, transport.calls[0].max_response_bytes) == (
        8.0,
        512 * 1024,
    )


def test_replies_are_matched_by_the_instrument_in_each_entry_not_by_how_it_is_labelled() -> None:
    data = {
        "anything-at-all": tick(INFY_LISTING, 1500.25),
        "something-else": tick(TCS_LISTING, 4000.5),
    }
    answer = build(FakeTransport(reply(data))).quotes(["TCS", "INFY"])
    assert (answer["TCS"]["last_price"], answer["INFY"]["last_price"]) == (4000.5, 1500.25)


def test_an_entry_labelled_for_one_share_but_carrying_another_is_not_used() -> None:
    data = {"NSE_EQ:TCS": tick(INFY_LISTING, 1500.25)}
    answer = build(FakeTransport(reply(data))).quotes(["TCS"])
    assert answer["TCS"]["label"] == "UNAVAILABLE"


def test_an_entry_for_a_share_nobody_asked_about_is_ignored() -> None:
    answer = build(FakeTransport(everyone())).quotes(["INFY"])
    assert set(answer) == {"INFY"}


def test_an_entry_with_no_instrument_is_matched_only_when_keyed_by_the_instrument_itself() -> None:
    bare = tick(TCS_LISTING, 4000.5)
    del bare["instrument_token"]
    keyed = build(FakeTransport(reply({TCS_LISTING: bare}))).quotes(["TCS"])["TCS"]
    labelled = build(FakeTransport(reply({"NSE_EQ:TCS": bare}))).quotes(["TCS"])["TCS"]
    assert (keyed["label"], labelled["label"]) == ("LIVE", "UNAVAILABLE")


def test_a_share_that_upstox_leaves_out_is_unavailable_and_the_others_are_still_priced() -> None:
    transport = FakeTransport(reply({"NSE_EQ:INFY": tick(INFY_LISTING, 1500.25)}))
    answer = build(transport).quotes(["TCS", "INFY"])
    assert answer["TCS"]["label"] == "UNAVAILABLE"
    assert answer["TCS"]["message"] == messages.no_price("TCS")
    assert answer["INFY"]["label"] == "LIVE"


def test_two_names_for_one_instrument_are_both_priced_from_one_entry() -> None:
    listings = {"TCS": TCS_LISTING, "TCSOLD": TCS_LISTING}
    transport = FakeTransport(reply({"NSE_EQ:TCS": tick(TCS_LISTING, 4000.5)}))
    config = QuoteServiceConfig(
        resolve_key=listings.get,
        key_provider=lambda: CANARY,
        transport=transport,
        clock=FakeClock(),
    )
    answer = QuoteService(config).quotes(["TCS", "TCSOLD"])
    assert (answer["TCS"]["last_price"], answer["TCSOLD"]["last_price"]) == (4000.5, 4000.5)
    assert transport.calls[0].url.count(TCS_LISTING) == 1


def test_symbols_are_cleaned_up_and_asked_for_once() -> None:
    transport = FakeTransport(everyone())
    answer = build(transport).quotes(["tcs", " TCS ", "", "infy"])
    assert (list(answer), len(transport.calls)) == (["TCS", "INFY"], 1)


@pytest.mark.parametrize(
    "resolver",
    [
        pytest.param(lambda _symbol: None, id="the-index-has-no-listing"),
        pytest.param(lambda _symbol: "  ", id="the-listing-is-blank"),
    ],
)
def test_a_share_that_is_not_in_the_market_data_is_unavailable_and_costs_no_request(
    resolver: Callable[[str], str | None],
) -> None:
    transport = FakeTransport(everyone())
    config = QuoteServiceConfig(
        resolve_key=resolver, key_provider=lambda: CANARY, transport=transport, clock=FakeClock()
    )
    entry = QuoteService(config).quotes(["NOPE"])["NOPE"]
    assert (entry["label"], entry["message"], transport.calls) == (
        "UNAVAILABLE",
        messages.not_in_market_data("NOPE"),
        [],
    )


def _missing(symbol: str) -> str:
    raise SymbolNotFoundError(symbol)


def test_the_index_refusing_a_symbol_is_the_same_as_not_knowing_it() -> None:
    transport = FakeTransport(everyone())
    config = QuoteServiceConfig(
        resolve_key=_missing, key_provider=lambda: CANARY, transport=transport, clock=FakeClock()
    )
    answer = QuoteService(config).quotes(["NOPE"])
    assert answer["NOPE"]["message"] == messages.not_in_market_data("NOPE")


def test_only_the_known_shares_are_sent_when_some_are_not_in_the_market_data() -> None:
    transport = FakeTransport(everyone())
    answer = build(transport).quotes(["TCS", "NOPE"])
    assert (answer["TCS"]["label"], answer["NOPE"]["label"]) == ("LIVE", "UNAVAILABLE")
    assert transport.calls[0].url.endswith(f"instrument_key={TCS_LISTING}")


def test_a_reply_is_read_when_it_arrives_not_when_the_request_started() -> None:
    clock = FakeClock()
    slow = SlowTransport(clock, 5.0, everyone("2026-10-06T10:29:04+05:30"))  # 56 s old at the start
    entry = build(slow, clock).quotes(["TCS"])["TCS"]
    assert entry["label"] == "DELAYED"


# ----------------------------------------------------------------------------- caching


def test_a_second_ask_within_ten_seconds_is_answered_without_asking_upstox_again() -> None:
    clock, transport = FakeClock(), FakeTransport(everyone())
    service = build(transport, clock)
    first = service.quotes(["TCS", "INFY"])
    clock.advance(9.9)
    assert service.quotes(["TCS", "INFY"])["TCS"]["last_price"] == first["TCS"]["last_price"]
    assert len(transport.calls) == 1


def test_after_ten_seconds_the_price_is_fetched_again() -> None:
    clock, transport = FakeClock(), FakeTransport(everyone())
    service = build(transport, clock)
    service.quotes(["TCS"])
    clock.advance(10.0)
    service.quotes(["TCS"])
    assert len(transport.calls) == 2


def test_only_the_shares_not_already_held_are_asked_for() -> None:
    transport = FakeTransport(everyone())
    service = build(transport)
    service.quotes(["TCS"])
    service.quotes(["TCS", "INFY"])
    assert transport.calls[1].url.endswith(f"instrument_key={INFY_LISTING}")


def test_a_share_upstox_left_out_is_not_asked_for_again_within_ten_seconds() -> None:
    transport = FakeTransport(reply({}))
    service = build(transport)
    service.quotes(["TCS"])
    answer = service.quotes(["TCS"])
    assert (answer["TCS"]["label"], len(transport.calls)) == ("UNAVAILABLE", 1)


def test_a_held_price_is_relabelled_by_the_clock_when_it_is_served_again() -> None:
    clock = FakeClock()
    service = build(FakeTransport(everyone("2026-10-06T10:29:05+05:30")), clock)  # 55 s old
    first = service.quotes(["TCS"])["TCS"]["label"]
    clock.advance(9.0)
    assert (first, service.quotes(["TCS"])["TCS"]["label"]) == ("LIVE", "DELAYED")


def test_the_cache_is_bounded_and_forgets_the_oldest_first() -> None:
    transport = FakeTransport(everyone())
    service = build(transport, max_cached=2)
    for_each = [["TCS"], ["INFY"], ["RELIANCE"], ["TCS"], ["RELIANCE"]]
    answers = [service.quotes(symbols) for symbols in for_each]
    assert len(answers) == 5
    assert len(transport.calls) == 4  # TCS was forgotten and fetched again; RELIANCE was still held


def test_a_full_cache_keeps_the_newest_prices() -> None:
    clock, transport = FakeClock(), FakeTransport(everyone())
    service = build(transport, clock, max_cached=2)
    service.quotes(["TCS"])
    clock.advance(11.0)
    service.quotes(["INFY"])
    service.quotes(["RELIANCE"])
    service.quotes(["INFY"])
    assert len(transport.calls) == 3  # INFY and RELIANCE both survived


def test_many_threads_asking_at_once_each_get_a_complete_answer() -> None:
    service = build(FakeTransport(everyone()))
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = list(pool.map(lambda _n: service.quotes(["TCS", "INFY"]), range(24)))
    assert all(set(a) == {"TCS", "INFY"} and a["TCS"]["label"] == "LIVE" for a in answers)


# ------------------------------------------------------------------------------- the key


def test_with_no_key_nothing_is_requested_and_the_message_says_what_to_click() -> None:
    transport = FakeTransport(everyone())
    batch = build(transport, key="  ").fetch(["TCS", "INFY"])
    assert batch.connected is False
    assert batch.message == "Add an Upstox token in Settings, then Accounts and keys."
    assert {s: e.label for s, e in batch.quotes.items()} == {
        "TCS": "UNAVAILABLE",
        "INFY": "UNAVAILABLE",
    }
    assert (transport.calls, batch.quotes["TCS"].message) == ([], batch.message)


def test_an_expired_key_is_reported_without_making_a_request() -> None:
    expired = make_jwt(OPEN_NOW - timedelta(seconds=1))
    transport = FakeTransport(everyone())
    batch = build(transport, key=expired).fetch(["TCS"])
    assert batch.connected is False
    assert (
        batch.message
        == "Your Upstox key has expired. Open Settings, then Accounts and keys, and sign in again."
    )
    assert (transport.calls, batch.quotes["TCS"].label) == ([], "UNAVAILABLE")


def test_a_key_expiring_this_very_second_counts_as_expired() -> None:
    batch = build(FakeTransport(everyone()), key=make_jwt(OPEN_NOW)).fetch(["TCS"])
    assert batch.message == messages.KEY_EXPIRED


@pytest.mark.parametrize(
    "key",
    [
        pytest.param(make_jwt(OPEN_NOW + timedelta(days=300)), id="a-key-with-a-year-left"),
        pytest.param(make_jwt(OPEN_NOW + timedelta(seconds=1)), id="a-key-with-a-second-left"),
        pytest.param("not-a-jwt-at-all", id="not-a-jwt"),
        pytest.param("aaa.bbb.ccc", id="three-parts-that-are-not-base64-json"),
        pytest.param(
            "aaa." + base64.urlsafe_b64encode(b"[1]").decode() + ".ccc",
            id="payload-is-not-an-object",
        ),
        pytest.param(
            "aaa." + base64.urlsafe_b64encode(b'{"sub": "x"}').decode() + ".ccc",
            id="no-expiry-claim",
        ),
        pytest.param(
            "aaa." + base64.urlsafe_b64encode(b'{"exp": 1e999}').decode() + ".ccc",
            id="absurd-expiry",
        ),
    ],
)
def test_a_key_that_is_not_known_to_be_expired_is_tried(key: str) -> None:
    transport = FakeTransport(everyone())
    batch = build(transport, key=key).fetch(["TCS"])
    assert (batch.connected, batch.quotes["TCS"].label, len(transport.calls)) == (True, "LIVE", 1)


def test_the_key_is_read_afresh_each_time_so_a_newly_saved_key_works_at_once() -> None:
    keys = ["", CANARY]
    transport = FakeTransport(everyone())
    config = QuoteServiceConfig(
        resolve_key=LISTINGS.get,
        key_provider=lambda: keys.pop(0),
        transport=transport,
        clock=FakeClock(),
    )
    service = QuoteService(config)
    assert (service.fetch(["TCS"]).connected, service.fetch(["TCS"]).connected) == (False, True)


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


def test_a_rejected_key_is_not_remembered_so_fixing_it_works_straight_away() -> None:
    transport = FakeTransport(HttpResponse(401, b"{}", {}), everyone())
    service = build(transport)
    first, second = service.fetch(["TCS"]), service.fetch(["TCS"])
    assert (first.connected, second.connected, len(transport.calls)) == (False, True, 2)


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
