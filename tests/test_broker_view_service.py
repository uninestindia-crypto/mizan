"""The broker view as a whole: what it fetches, when it stops, what it says, and that the key never escapes."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from quant_system.broker_view import messages
from quant_system.broker_view.endpoints import (
    UPSTOX_FUNDS_URL,
    UPSTOX_HOLDINGS_URL,
    UPSTOX_POSITIONS_URL,
)
from quant_system.broker_view.service import THROTTLE_SECONDS, next_key_end
from quant_system.data.upstox_http import (
    ResponseTooLarge,
    TransportConnectionError,
    TransportTimeout,
)
from tests.broker_fakes import (
    SENTINEL,
    all_replies,
    failure_reply,
    holding,
    make_rig,
    success,
)
from tests.live_fakes import OPEN_NOW, FakeClock, make_jwt


def refreshed(**kwargs: Any):  # type: ignore[no-untyped-def]
    rig = make_rig(**kwargs)
    problem = rig.view.refresh(force=True)
    return rig, problem


# ----------------------------------------------------------------------------- what is fetched and shown


def test_a_refresh_reads_holdings_positions_and_cash_with_get_requests_only() -> None:
    rig, problem = refreshed()
    assert problem is None
    assert [call.url.split("?")[0] for call in rig.reads.calls] == [
        UPSTOX_HOLDINGS_URL,
        UPSTOX_POSITIONS_URL,
        UPSTOX_FUNDS_URL,
    ]
    assert rig.reads.calls[2].url.endswith("?segment=SEC")
    assert all(call.headers["Authorization"] == f"Bearer {SENTINEL}" for call in rig.reads.calls)


def test_the_figures_are_worked_out_in_exact_decimals_from_prices_and_quantities() -> None:
    rig, _ = refreshed()
    snapshot = rig.view.snapshot()
    totals = snapshot["totals"]
    # TCS 10 x 3500.5 = 35005.0 (paid 34000.0); INFY 20 x 1490.0 = 29800.0 (paid 30000.0)
    assert totals["value"] == 64805.0 and totals["invested"] == 64000.0
    assert totals["pnl"] == 805.0 and totals["pnl_pct"] == 1.26
    assert totals["today"] == 105.0  # TCS +205.0, INFY -100.0 against yesterday's close
    tcs = next(h for h in snapshot["holdings"] if h["symbol"] == "TCS")
    assert tcs["value"] == 35005.0 and tcs["pnl"] == 1005.0 and tcs["weight_pct"] == 54.02
    assert snapshot["cash"] == {"available": 12000.5, "in_use": 3000.0}
    assert (
        snapshot["positions"][0]["product"] == "Intraday"
        and snapshot["positions"][0]["quantity"] == -5
    )


def test_the_biggest_holding_comes_first_and_a_concentration_warning_names_it() -> None:
    snapshot = refreshed()[0].view.snapshot()
    assert [h["symbol"] for h in snapshot["holdings"]] == ["TCS", "INFY"]
    assert snapshot["warnings"] == [
        "TCS is 54% of your holdings (above 25%).",
        "INFY is 46% of your holdings (above 25%).",
    ]


def test_every_snapshot_says_it_is_view_only_and_carries_the_time_it_was_fetched() -> None:
    snapshot = refreshed()[0].view.snapshot()
    assert snapshot["view_only"] is True and snapshot["label"] == messages.SNAPSHOT_LABEL
    assert snapshot["fetched_at"] == "2026-10-06T10:30:00+05:30"
    assert snapshot["freshness"] == "UP_TO_DATE"
    assert snapshot["connected"] is True and snapshot["message"] is None


def test_figures_go_older_after_five_minutes() -> None:
    rig, _ = refreshed()
    rig.clock.advance(301)
    assert rig.view.snapshot()["freshness"] == "OLDER"


def test_recently_bought_shares_are_shown_apart_and_not_valued_as_held() -> None:
    rig, _ = refreshed(replies=all_replies(holdings=[holding(quantity=0, t1_quantity=4)]))
    snapshot = rig.view.snapshot()
    assert snapshot["totals"]["value"] == 0.0
    assert snapshot["totals"]["arriving_value"] == 14002.0
    assert "4 shares" in snapshot["totals"]["arriving_note"]


def test_a_day_s_move_is_left_out_when_a_share_has_no_close_to_compare_with() -> None:
    rig, _ = refreshed(replies=all_replies(holdings=[holding(close_price=None)]))
    assert rig.view.snapshot()["totals"]["today"] is None


def test_the_reply_holds_nothing_that_identifies_the_person_or_the_company() -> None:
    text = json.dumps(refreshed()[0].view.snapshot())
    for leak in ("Invented", "invented@", "instrument_token", "NSE_EQ|", SENTINEL):
        assert leak not in text


# ----------------------------------------------------------------------------- partial and failing replies


def test_one_unreadable_holding_is_counted_and_the_rest_are_shown() -> None:
    rig, _ = refreshed(replies=all_replies(holdings=[holding(), holding("BAD", quantity=1.5)]))
    snapshot = rig.view.snapshot()
    assert [h["symbol"] for h in snapshot["holdings"]] == ["TCS"]
    assert snapshot["skipped"] == {"holdings": 1, "positions": 0}
    assert "1 holding could not be read and was not shown." in snapshot["notes"]


def test_positions_failing_does_not_hide_the_holdings() -> None:
    replies = all_replies()
    replies[UPSTOX_POSITIONS_URL] = failure_reply(500)
    rig, problem = refreshed(replies=replies)
    snapshot = rig.view.snapshot()
    assert problem is None and len(snapshot["holdings"]) == 2 and snapshot["positions"] == []
    assert messages.POSITIONS_MISSING in snapshot["notes"]


def test_cash_failing_leaves_cash_empty_with_a_note() -> None:
    replies = all_replies()
    replies[UPSTOX_FUNDS_URL] = TransportTimeout("slow")
    rig, _ = refreshed(replies=replies)
    snapshot = rig.view.snapshot()
    assert snapshot["cash"] == {"available": None, "in_use": None}
    assert messages.FUNDS_MISSING in snapshot["notes"]


def test_between_midnight_and_half_past_five_in_india_cash_is_not_asked_for() -> None:
    clock = FakeClock(datetime(2026, 10, 6, 20, 0, tzinfo=UTC))  # 01:30 the next morning in India
    rig = make_rig(key=make_jwt(clock.now + timedelta(hours=8)), clock=clock)
    rig.view.refresh(force=True)
    assert rig.reads.asked(UPSTOX_FUNDS_URL) == 0 and rig.reads.asked(UPSTOX_HOLDINGS_URL) == 1
    snapshot = rig.view.snapshot()
    assert messages.FUNDS_WINDOW in snapshot["notes"] and len(snapshot["holdings"]) == 2


def test_cash_is_asked_for_again_once_it_is_half_past_five() -> None:
    clock = FakeClock(datetime(2026, 10, 6, 0, 0, tzinfo=UTC))  # 05:30 in India
    rig = make_rig(key=make_jwt(clock.now + timedelta(hours=8)), clock=clock)
    rig.view.refresh(force=True)
    assert rig.reads.asked(UPSTOX_FUNDS_URL) == 1


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (TransportTimeout("x"), messages.TOO_SLOW),
        (TransportConnectionError("x"), messages.UNREACHABLE),
        (ResponseTooLarge("x"), messages.TOO_LARGE),
        (RuntimeError(f"leaky {SENTINEL}"), messages.UNREACHABLE),
        (failure_reply(429), messages.BUSY),
        (failure_reply(503), messages.UNAVAILABLE),
        (success({"not": "a list"}), messages.UNREADABLE),
    ],
)
def test_a_failed_read_says_what_happened_in_words_and_keeps_the_last_figures(
    outcome: Any, message: str
) -> None:
    rig, _ = refreshed()
    rig.clock.advance(60)
    rig.reads.replies[UPSTOX_HOLDINGS_URL] = outcome
    assert rig.view.refresh() == message
    snapshot = rig.view.snapshot()
    assert snapshot["message"] == message and len(snapshot["holdings"]) == 2
    assert rig.vault.key == SENTINEL  # a slow or busy broker does not end the sign-in


# ----------------------------------------------------------------------------- the key


def test_upstox_refusing_the_key_forgets_it_and_keeps_the_last_figures() -> None:
    rig, _ = refreshed()
    rig.clock.advance(60)
    rig.reads.replies[UPSTOX_HOLDINGS_URL] = failure_reply(401, "UDAPI100050")
    assert rig.view.refresh() == messages.KEY_REJECTED
    assert rig.vault.key is None
    snapshot = rig.view.snapshot()
    assert snapshot["connected"] is False and len(snapshot["holdings"]) == 2
    assert snapshot["message"] == messages.KEY_REJECTED


def test_a_request_for_a_registered_address_keeps_the_key_and_says_why() -> None:
    rig, _ = refreshed()
    rig.clock.advance(60)
    rig.reads.replies[UPSTOX_HOLDINGS_URL] = failure_reply(401, "UDAPI1221")
    assert rig.view.refresh() == messages.STATIC_IP_REQUIRED
    assert rig.vault.key == SENTINEL and rig.view.snapshot()["connected"] is True


def test_a_key_that_says_it_has_ended_is_forgotten_without_asking_upstox() -> None:
    ended = make_jwt(OPEN_NOW - timedelta(hours=1))
    rig = make_rig(key=ended)
    assert rig.view.refresh(force=True) == messages.KEY_ENDED
    assert rig.reads.calls == [] and rig.vault.key is None


def test_a_key_that_does_not_say_when_it_ends_is_dropped_at_the_time_recorded_at_sign_in() -> None:
    rig = make_rig(key="opaque-key-without-an-expiry")
    rig.store.set_key_ends_at("upstox", OPEN_NOW + timedelta(minutes=5))
    assert rig.view.refresh(force=True) is None and rig.vault.key is not None
    rig.clock.advance(301)
    assert rig.view.refresh(force=True) == messages.KEY_ENDED
    assert rig.vault.key is None and len(rig.reads.calls) == 3


def test_figures_stay_visible_after_the_sign_in_ends_with_the_message_that_names_the_click() -> (
    None
):
    rig, _ = refreshed()
    rig.clock.advance(timedelta(hours=18).total_seconds())
    snapshot = rig.view.snapshot()
    assert snapshot["connected"] is False and snapshot["message"] == messages.KEY_ENDED
    assert len(snapshot["holdings"]) == 2 and snapshot["freshness"] == "OLDER"
    assert rig.reads.asked(UPSTOX_HOLDINGS_URL) == 1


def test_the_next_sign_in_end_is_half_past_three_in_the_morning_india_time() -> None:
    assert (
        next_key_end(datetime(2026, 10, 6, 5, 0, tzinfo=UTC)).isoformat()
        == "2026-10-07T03:30:00+05:30"
    )
    assert (
        next_key_end(datetime(2026, 10, 5, 20, 0, tzinfo=UTC)).isoformat()
        == "2026-10-06T03:30:00+05:30"
    )


# ----------------------------------------------------------------------------- limits and states


def test_a_second_refresh_inside_thirty_seconds_does_not_ask_upstox_again() -> None:
    rig, _ = refreshed()
    rig.clock.advance(THROTTLE_SECONDS - 1)
    assert rig.view.refresh() is None
    assert rig.reads.asked(UPSTOX_HOLDINGS_URL) == 1
    rig.clock.advance(2)
    rig.view.refresh()
    assert rig.reads.asked(UPSTOX_HOLDINGS_URL) == 2


def test_reading_the_snapshot_never_asks_upstox_for_anything() -> None:
    rig = make_rig()
    for _ in range(3):
        rig.view.snapshot()
        rig.view.status()
    assert rig.reads.calls == []


def test_before_anything_is_set_up_the_message_names_the_first_click() -> None:
    snapshot = make_rig(key=None, keys=None).view.snapshot()
    assert snapshot["connected"] is False and snapshot["message"] == messages.NOT_SET_UP
    assert snapshot["freshness"] == "NONE" and snapshot["totals"] is None


def test_once_the_keys_are_saved_but_not_connected_the_message_names_connect() -> None:
    assert make_rig(key=None).view.snapshot()["message"] == messages.NOT_CONNECTED


def test_status_reports_the_setup_the_sign_in_and_when_it_ends() -> None:
    rig, _ = refreshed()
    rig.store.set_key_ends_at("upstox", OPEN_NOW + timedelta(hours=17))
    broker = rig.view.status()["brokers"][0]
    assert broker["id"] == "upstox" and broker["set_up"] is True and broker["connected"] is True
    assert broker["key_ends_at"] == "2026-10-07T03:30:00+05:30"
    assert broker["callback_address"] == "http://127.0.0.1:47610/upstox/callback"
    assert rig.view.status()["assistant_access"] is False


# ----------------------------------------------------------------------------- leaving


def test_disconnecting_signs_out_forgets_the_key_and_deletes_the_figures() -> None:
    rig, _ = refreshed()
    status = rig.view.disconnect()
    assert rig.session.ended == [SENTINEL]
    assert rig.vault.key is None and rig.store.load("upstox") is None
    assert status["brokers"][0]["connected"] is False
    assert rig.view.snapshot()["holdings"] == []


def test_disconnecting_with_a_key_that_has_ended_does_not_try_to_sign_out() -> None:
    rig = make_rig(key=make_jwt(OPEN_NOW - timedelta(hours=1)))
    rig.view.disconnect()
    assert rig.session.ended == [] and rig.vault.key is None


def test_disconnecting_when_nothing_is_connected_is_harmless() -> None:
    rig = make_rig(key=None)
    assert rig.view.disconnect()["brokers"][0]["connected"] is False
    assert rig.session.ended == []


# ----------------------------------------------------------------------------- the key never escapes


def test_the_key_never_appears_in_the_environment_a_log_or_any_reply(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG")
    before = dict(os.environ)
    rig, _ = refreshed()
    rig.clock.advance(60)
    rig.reads.replies[UPSTOX_POSITIONS_URL] = RuntimeError(f"leaky {SENTINEL}")
    rig.view.refresh()
    rig.view.set_assistant_access(True)
    replies = [rig.view.status(), rig.view.snapshot(), rig.view.assistant_summary()]
    rig.view.disconnect()
    assert dict(os.environ) == before
    assert SENTINEL not in caplog.text
    assert SENTINEL not in json.dumps(replies)
    assert [r for r in caplog.records if SENTINEL in r.getMessage()] == []
