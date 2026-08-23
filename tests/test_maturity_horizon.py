"""Regression tests for the governed maturity horizon.

The defect under guard: `_check_matured_outcomes` matured an open entry on the first same-symbol
quote after its fill, so a model validated on a two-session label could open and close a position
inside one session. That is a different strategy, not a noisier measurement of the same one.

Kept out of `tests/test_realtime_shadow.py`, which is claimed by the S9-B2 record and whose test
count is pinned as evidence by in-flight adjudications.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.core.domain import Quote, Side
from quant_system.execution.maturity import (
    ImmediateMaturity,
    MaturityPolicyError,
    SessionHorizonMaturity,
)
from quant_system.execution.realtime_shadow import (
    RealtimeShadowConfig,
    RealtimeShadowRunner,
    ShadowDecisionStatus,
    ShadowProposal,
)
from quant_system.modeling.rows import LABEL_HORIZON_SESSIONS_V1
from tests.modeling_fixtures import SYMBOL, governed_calendar

CALENDAR = governed_calendar(10)


def _proposal(entry_at: datetime) -> ShadowProposal:
    return ShadowProposal(
        proposal_id="p1",
        model_id="m1",
        symbol=SYMBOL,
        side=Side.BUY,
        quantity=10,
        signal_strength=1.0,
        quote_bid=Decimal("100.00"),
        quote_ask=Decimal("100.10"),
        quote_mid=Decimal("100.05"),
        quote_timestamp=entry_at,
        decision_at=entry_at,
        quote_latency_seconds=0.0,
        risk_approved=True,
        status=ShadowDecisionStatus.APPROVED,
    )


def _quote(at: datetime) -> Quote:
    return Quote(
        symbol=SYMBOL,
        timestamp=at,
        bid=Decimal("105.00"),
        ask=Decimal("105.10"),
        bid_size=100,
        ask_size=100,
    )


def _runner(policy: object | None) -> RealtimeShadowRunner:
    return RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="maturity",
            model_id="m1",
            maturity_policy=policy,  # type: ignore[arg-type]
        ),
        live_feed=None,  # type: ignore[arg-type]
    )


def _mature(policy: object | None, entry_at: datetime, quote_at: datetime) -> int:
    """Seed one open entry, present a later quote, and report how many outcomes matured."""
    runner = _runner(policy)
    runner._open_entries["p1"] = (_proposal(entry_at), Decimal("100.10"), entry_at)
    runner._check_matured_outcomes(_quote(quote_at), quote_at)
    return len(runner._matured_outcomes)


# ---------------------------------------------------------------------------------------------
# The defect, and the repair
# ---------------------------------------------------------------------------------------------


def test_without_a_policy_an_entry_still_matures_inside_its_own_session() -> None:
    """Documents the pre-existing behaviour the horizon exists to override.

    This is not an endorsement. It pins the default so that the change is provably opt-in and any
    future edit that silently alters unconfigured sessions fails here.
    """
    entry_at = CALENDAR.sessions[0].open_at + timedelta(minutes=5)
    same_session = CALENDAR.sessions[0].close_at - timedelta(minutes=5)

    assert _mature(None, entry_at, same_session) == 1


def test_session_horizon_refuses_to_mature_inside_the_entry_session() -> None:
    """The repair: a two-session strategy must not become an intraday one."""
    policy = SessionHorizonMaturity(CALENDAR)
    entry_at = CALENDAR.sessions[0].open_at + timedelta(minutes=5)
    same_session = CALENDAR.sessions[0].close_at - timedelta(minutes=5)

    assert _mature(policy, entry_at, same_session) == 0


def test_session_horizon_matures_on_the_following_session() -> None:
    policy = SessionHorizonMaturity(CALENDAR)
    entry_at = CALENDAR.sessions[0].open_at + timedelta(minutes=5)
    next_session = CALENDAR.sessions[1].open_at + timedelta(minutes=1)

    assert _mature(policy, entry_at, next_session) == 1


def test_maturity_is_not_permitted_one_instant_before_the_next_open() -> None:
    """The boundary is the next session's open, not merely a new calendar day."""
    policy = SessionHorizonMaturity(CALENDAR)
    entry_at = CALENDAR.sessions[0].open_at + timedelta(minutes=5)
    just_before = CALENDAR.sessions[1].open_at - timedelta(seconds=1)

    assert _mature(policy, entry_at, just_before) == 0
    assert _mature(policy, entry_at, CALENDAR.sessions[1].open_at) == 1


def test_a_longer_horizon_holds_across_more_sessions() -> None:
    policy = SessionHorizonMaturity(CALENDAR, holding_sessions=3)
    entry_at = CALENDAR.sessions[0].open_at + timedelta(minutes=5)

    assert _mature(policy, entry_at, CALENDAR.sessions[2].open_at) == 0
    assert _mature(policy, entry_at, CALENDAR.sessions[3].open_at) == 1


# ---------------------------------------------------------------------------------------------
# The policy itself
# ---------------------------------------------------------------------------------------------


def test_default_holding_matches_the_validated_label_horizon() -> None:
    """LABEL_HORIZON_SESSIONS_V1 counts decision -> entry -> exit; from the entry that is one."""
    assert LABEL_HORIZON_SESSIONS_V1 == 2
    assert SessionHorizonMaturity(CALENDAR).holding_sessions == LABEL_HORIZON_SESSIONS_V1 - 1


def test_entry_session_is_resolved_by_instant_not_by_calendar_date() -> None:
    """An entry after a session's close still belongs to that session, not the next one."""
    policy = SessionHorizonMaturity(CALENDAR)
    after_close = CALENDAR.sessions[0].close_at + timedelta(hours=1)

    assert policy.matures_at(after_close) == CALENDAR.sessions[1].open_at


def test_immediate_policy_names_the_no_horizon_choice() -> None:
    entry_at = CALENDAR.sessions[0].open_at

    assert ImmediateMaturity().matures_at(entry_at) == entry_at


def test_entry_before_any_session_opened_fails_closed() -> None:
    policy = SessionHorizonMaturity(CALENDAR)
    before_everything = CALENDAR.sessions[0].open_at - timedelta(days=1)

    with pytest.raises(MaturityPolicyError, match="no exchange session had opened"):
        policy.matures_at(before_everything)


def test_horizon_beyond_the_calendar_fails_closed_rather_than_maturing_early() -> None:
    policy = SessionHorizonMaturity(CALENDAR)
    last_entry = CALENDAR.sessions[-1].open_at

    with pytest.raises(MaturityPolicyError, match="calendar ends before"):
        policy.matures_at(last_entry)


def test_naive_entry_time_is_refused() -> None:
    policy = SessionHorizonMaturity(CALENDAR)

    with pytest.raises(MaturityPolicyError, match="timezone-aware"):
        policy.matures_at(datetime(2025, 1, 2, 10, 0))


def test_a_zero_session_horizon_is_refused() -> None:
    with pytest.raises(MaturityPolicyError, match="at least one session"):
        SessionHorizonMaturity(CALENDAR, holding_sessions=0)
