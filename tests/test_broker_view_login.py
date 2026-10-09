"""Signing in: the address, the one-time check on what comes back, the five-field swap, and the key."""

from __future__ import annotations

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from quant_system.broker_view import messages
from quant_system.broker_view.endpoints import CALLBACK_ADDRESS, UPSTOX_AUTHORIZE_URL
from quant_system.broker_view.login import (
    LOGIN_SECONDS,
    LoginCheck,
    LoginTracker,
    authorize_address,
    exchange_form,
    read_exchange_reply,
)
from quant_system.broker_view.loopback import CONNECTED, FAILED, IGNORED
from quant_system.broker_view.service import BrokerViewError
from tests.broker_fakes import (
    APP_KEY,
    APP_SECRET,
    SENTINEL,
    SIGN_IN_CODE,
    FakeSession,
    make_rig,
    token_reply,
)
from tests.live_fakes import FakeClock


def test_the_sign_in_address_goes_to_upstox_and_asks_to_come_back_to_this_computer() -> None:
    address = authorize_address(APP_KEY, "state-1")
    parts = urlsplit(address)
    assert address.startswith(UPSTOX_AUTHORIZE_URL + "?")
    assert parse_qs(parts.query) == {
        "response_type": ["code"],
        "client_id": [APP_KEY],
        "redirect_uri": [CALLBACK_ADDRESS],
        "state": ["state-1"],
    }


def test_the_swap_sends_exactly_five_fields_and_never_the_state() -> None:
    form = exchange_form(SIGN_IN_CODE, APP_KEY, APP_SECRET)
    assert form == {
        "code": SIGN_IN_CODE,
        "client_id": APP_KEY,
        "client_secret": APP_SECRET,
        "redirect_uri": CALLBACK_ADDRESS,
        "grant_type": "authorization_code",
    }


def test_only_the_key_survives_from_the_reply_and_the_person_s_details_are_discarded() -> None:
    assert read_exchange_reply(token_reply(SENTINEL).body) == SENTINEL


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"[]",
        b'{"user_name": "x"}',
        b'{"access_token": ""}',
        b'{"access_token": 5}',
        b'{"access_token": "has a space"}',
        b'{"access_token": "line\\nbreak"}',
        json.dumps({"access_token": "x" * 5000}).encode(),
    ],
)
def test_a_reply_without_a_usable_key_gives_none(raw: bytes) -> None:
    assert read_exchange_reply(raw) is None


def test_a_matching_state_is_accepted_once() -> None:
    tracker = LoginTracker(FakeClock())
    attempt = tracker.begin()
    assert tracker.check_and_consume(attempt.state) is LoginCheck.OK
    assert tracker.check_and_consume(attempt.state) is LoginCheck.USED


def test_a_wrong_missing_or_old_state_is_refused_and_does_not_end_the_open_attempt() -> None:
    tracker = LoginTracker(FakeClock())
    attempt = tracker.begin()
    assert tracker.check_and_consume("guess") is LoginCheck.MISMATCH
    assert tracker.check_and_consume(None) is LoginCheck.MISMATCH
    assert tracker.check_and_consume("") is LoginCheck.MISMATCH
    assert tracker.waiting
    assert tracker.check_and_consume(attempt.state) is LoginCheck.OK


def test_with_no_attempt_open_nothing_is_accepted() -> None:
    assert LoginTracker(FakeClock()).check_and_consume("anything") is LoginCheck.NO_ATTEMPT


def test_a_new_attempt_replaces_the_old_one_which_then_stops_working() -> None:
    tracker = LoginTracker(FakeClock())
    first = tracker.begin()
    second = tracker.begin()
    assert first.state != second.state
    assert tracker.check_and_consume(first.state) is LoginCheck.MISMATCH
    assert tracker.check_and_consume(second.state) is LoginCheck.OK


def test_an_attempt_expires_after_five_minutes() -> None:
    clock = FakeClock()
    tracker = LoginTracker(clock)
    attempt = tracker.begin()
    clock.advance(LOGIN_SECONDS - 1)
    assert tracker.waiting and not tracker.timed_out
    clock.advance(1)
    assert tracker.timed_out and not tracker.waiting
    assert tracker.check_and_consume(attempt.state) is LoginCheck.EXPIRED


def test_every_attempt_has_a_fresh_unguessable_state() -> None:
    tracker = LoginTracker(FakeClock())
    states = {tracker.begin().state for _ in range(50)}
    assert len(states) == 50 and all(len(state) >= 40 for state in states)


# ----------------------------------------------------------------------------- through the whole service


def _begin(rig):  # type: ignore[no-untyped-def]
    reply = rig.view.begin_login()
    state = parse_qs(urlsplit(reply["login_address"]).query)["state"][0]
    return reply, state


def test_starting_a_sign_in_opens_upstox_s_page_and_starts_the_listener() -> None:
    rig = make_rig(key=None)
    reply, state = _begin(rig)
    assert reply["opened"] is True and rig.opened == [reply["login_address"]]
    assert rig.listeners.latest.started == 1
    assert rig.view.status()["brokers"][0]["waiting_for_sign_in"] is True
    assert state


def test_a_good_return_swaps_the_code_saves_the_key_and_fetches_the_first_figures() -> None:
    rig = make_rig(key=None)
    _, state = _begin(rig)
    outcome = rig.view.finish_login({"code": SIGN_IN_CODE, "state": state})
    assert outcome == CONNECTED
    assert rig.session.forms == [exchange_form(SIGN_IN_CODE, APP_KEY, APP_SECRET)]
    assert rig.vault.saves == [SENTINEL]
    snapshot = rig.view.snapshot()
    assert snapshot["connected"] is True and snapshot["totals"]["value"] is not None
    assert rig.store.key_ends_at("upstox") is not None


@pytest.mark.parametrize(
    "returned", [{"code": SIGN_IN_CODE}, {"code": SIGN_IN_CODE, "state": "guess"}, {}]
)
def test_a_return_with_a_missing_or_wrong_state_is_ignored_before_any_swap(returned) -> None:  # type: ignore[no-untyped-def]
    rig = make_rig(key=None)
    _begin(rig)
    assert rig.view.finish_login(returned) == IGNORED
    assert rig.session.forms == [] and rig.vault.saves == []


def test_a_return_with_no_sign_in_open_is_ignored() -> None:
    rig = make_rig(key=None)
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": "x"}) == IGNORED
    assert rig.session.forms == []


def test_a_state_cannot_be_used_twice() -> None:
    rig = make_rig(key=None)
    _, state = _begin(rig)
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": state}) == CONNECTED
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": state}) == IGNORED
    assert len(rig.session.forms) == 1


def test_an_old_state_is_refused_and_the_screen_says_it_timed_out() -> None:
    rig = make_rig(key=None)
    _, state = _begin(rig)
    rig.clock.advance(LOGIN_SECONDS + 1)
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": state}) == IGNORED
    assert rig.session.forms == []
    assert rig.view.status()["brokers"][0]["message"] == messages.LOGIN_TIMED_OUT


def test_waiting_too_long_shows_the_timeout_and_stops_the_listener() -> None:
    rig = make_rig(key=None)
    _begin(rig)
    rig.clock.advance(timedelta(minutes=6).total_seconds())
    broker = rig.view.status()["brokers"][0]
    assert broker["waiting_for_sign_in"] is False and broker["message"] == messages.LOGIN_TIMED_OUT
    assert rig.listeners.latest.stopped >= 1


def test_an_upstox_refusal_at_sign_in_changes_nothing_and_says_what_to_click() -> None:
    rig = make_rig(key=None, session=FakeSession(token_reply(None)))
    _, state = _begin(rig)
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": state}) == FAILED
    assert (
        rig.vault.saves == []
        and rig.view.status()["brokers"][0]["message"] == messages.LOGIN_FAILED
    )


def test_a_person_who_says_no_on_upstox_s_page_leaves_nothing_behind() -> None:
    rig = make_rig(key=None)
    _, state = _begin(rig)
    assert rig.view.finish_login({"error": "access_denied", "state": state}) == FAILED
    assert rig.session.forms == [] and rig.vault.saves == []


def test_a_failing_swap_is_reported_without_the_text_of_the_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG")
    leaky = RuntimeError(f"swap failed, form was client_secret={APP_SECRET} key={SENTINEL}")
    rig = make_rig(key=None, session=FakeSession(leaky))
    _, state = _begin(rig)
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": state}) == FAILED
    assert APP_SECRET not in caplog.text and SENTINEL not in caplog.text
    assert rig.view.status()["brokers"][0]["message"] == messages.LOGIN_FAILED


def test_starting_without_the_app_key_and_secret_says_to_save_them_first() -> None:
    rig = make_rig(key=None, keys=None)
    with pytest.raises(BrokerViewError) as caught:
        rig.view.begin_login()
    assert (caught.value.status, caught.value.code) == (422, "BROKER_NOT_SET_UP")
    assert caught.value.message == messages.SAVE_KEYS_FIRST
    assert rig.opened == [] and rig.listeners.made == []


def test_a_busy_return_address_is_reported_and_no_page_is_opened() -> None:
    rig = make_rig(key=None, busy=True)
    with pytest.raises(BrokerViewError) as caught:
        rig.view.begin_login()
    assert (caught.value.status, caught.value.code) == (409, "CALLBACK_BUSY")
    assert rig.opened == [] and rig.view.status()["brokers"][0]["waiting_for_sign_in"] is False


def test_where_nothing_can_be_saved_the_connection_says_it_is_not_available() -> None:
    rig = make_rig(key=None, available=False)
    with pytest.raises(BrokerViewError) as caught:
        rig.view.begin_login()
    assert caught.value.code == "BROKER_UNAVAILABLE"
    assert rig.view.status()["available"] is False


def test_cancelling_stops_the_listener_and_ends_the_attempt() -> None:
    rig = make_rig(key=None)
    _, state = _begin(rig)
    status = rig.view.cancel_login()
    assert status["brokers"][0]["waiting_for_sign_in"] is False
    assert rig.listeners.latest.stopped == 1
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": state}) == IGNORED


def test_a_second_click_replaces_the_first_attempt() -> None:
    rig = make_rig(key=None)
    _, first = _begin(rig)
    _, second = _begin(rig)
    assert rig.listeners.made[0].stopped == 1
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": first}) == IGNORED
    assert rig.view.finish_login({"code": SIGN_IN_CODE, "state": second}) == CONNECTED
