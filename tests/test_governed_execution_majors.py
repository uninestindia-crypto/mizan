"""Regressions for Red Team Majors 4-9 on the governed execution path.

4. The strategy scored any symbol handed to it, including invented ones.
5. Malformed bar history raised TypeError/AttributeError, which no caller can type-match.
6. A MaturityPolicyError escaped the session, losing the audit report entirely.
7. A pre-open entry matured on the same calendar day, ten minutes after filling.
8. Duplicate exchange dates changed feature values; training rejects the same bars.
9. Open exposure was invisible in the audit report.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.core.domain import Quote, Side
from quant_system.data.live_feed import LiveFeedDependencies, UpstoxLiveFeed
from quant_system.execution.governed_strategy import (
    GOVERNED_BARS_KEY,
    ExecutionSurface,
    GovernedExecutionError,
    GovernedModelStrategy,
    ModelEvidenceIdentityV1,
    PromotedModelBundleV1,
)
from quant_system.execution.maturity import MaturityPolicyError, SessionHorizonMaturity
from quant_system.execution.realtime_shadow import (
    RealtimeShadowConfig,
    RealtimeShadowRunner,
    ShadowDecisionStatus,
    ShadowHaltReason,
    ShadowProposal,
    ShadowSessionState,
)
from quant_system.modeling import ModelCardV1, PromotionState
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1
from tests.modeling_fixtures import SYMBOL, governed_acquisition, governed_calendar
from tests.modeling_training_fixtures import governed_training_journey
from tests.test_governed_strategy import _fitted_pair
from tests.test_realtime_shadow import MockLiveStreamTransport, create_upstox_quote_json

CANDIDATE = "cand_ridge_v1"
CALENDAR10 = governed_calendar(10)


def _bundle(*, symbol: str = SYMBOL, threshold: str = "-99") -> PromotedModelBundleV1:
    fitted, preprocessing = _fitted_pair(governed_training_journey())
    card = ModelCardV1(
        model_id="model_majors_test",
        candidate_id=CANDIDATE,
        verdict=PromotionState.SHADOW,
        created_at=datetime(2026, 8, 23, tzinfo=UTC),
        monitoring_limits={},
        halt_and_rollback_policy="halt",
        limitations=("research only",),
    )
    return PromotedModelBundleV1(
        candidate_id=CANDIDATE,
        model_card=card,
        fitted=fitted,
        standardization=preprocessing,
        score_threshold=threshold,
        evidence=ModelEvidenceIdentityV1(
            model_id=card.model_id,
            candidate_id=CANDIDATE,
            trial_id="trial_majors",
            symbol=symbol,
            fitted_state_hash=fitted.fitted_state_hash,
            preprocessing_state_hash=preprocessing.state_hash,
            score_threshold=threshold,
        ),
    )


def _ctx(history: object, decision_time: datetime):
    from quant_system.strategies.base import MarketContext

    return MarketContext(
        current_time=decision_time,
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("100000"),
        extra_data={GOVERNED_BARS_KEY: history},
    )


def _window():
    journey = governed_training_journey()
    acq = governed_acquisition(count=55, calendar=journey.calendar)
    return acq.records[:FEATURE_WARMUP_BARS_V1], journey.calendar


# -------------------------------------------------------------------------------------------
# Major 4 — a single-instrument model must only score its own instrument
# -------------------------------------------------------------------------------------------


def test_strategy_refuses_a_symbol_the_model_was_not_fitted_on() -> None:
    """It emitted BUY for RELIANCE and for TOTALLY_MADE_UP from an INFY-fitted model."""
    window, calendar = _window()
    strategy = GovernedModelStrategy(_bundle(symbol=SYMBOL), ExecutionSurface.SHADOW)
    decision_time = calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at

    with pytest.raises(GovernedExecutionError, match="was fitted on"):
        strategy.generate_signals(_ctx({"TOTALLY_MADE_UP": window}, decision_time))


def test_strategy_still_scores_the_symbol_it_was_fitted_on() -> None:
    window, calendar = _window()
    strategy = GovernedModelStrategy(_bundle(symbol=SYMBOL), ExecutionSurface.SHADOW)
    decision_time = calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at

    signals = strategy.generate_signals(_ctx({SYMBOL: window}, decision_time))

    assert [s.symbol for s in signals] == [SYMBOL]


# -------------------------------------------------------------------------------------------
# Major 5 — malformed history must be typed
# -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "a string", 7, {"not": "a sequence"}])
def test_malformed_bar_history_raises_a_typed_error(bad: object) -> None:
    """None gave TypeError, a string gave AttributeError — neither is type-matchable."""
    _, calendar = _window()
    strategy = GovernedModelStrategy(_bundle(), ExecutionSurface.SHADOW)
    decision_time = calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at

    with pytest.raises(GovernedExecutionError):
        strategy.generate_signals(_ctx({SYMBOL: bad}, decision_time))


def test_an_empty_bar_sequence_is_a_genuine_no_signal_not_an_error() -> None:
    """Served nothing is a real model outcome; malformed is not. They must stay distinct."""
    _, calendar = _window()
    strategy = GovernedModelStrategy(_bundle(), ExecutionSurface.SHADOW)
    decision_time = calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at

    assert strategy.generate_signals(_ctx({SYMBOL: ()}, decision_time)) == []


# -------------------------------------------------------------------------------------------
# Major 8 — duplicate exchange dates
# -------------------------------------------------------------------------------------------


def test_duplicate_exchange_dates_are_refused_as_training_refuses_them() -> None:
    """Training rejects these bars with RECORD_ORDER_INVALID; execution silently accepted them."""
    window, calendar = _window()
    strategy = GovernedModelStrategy(_bundle(), ExecutionSurface.SHADOW)
    decision_time = calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at
    overlapped = (*window, window[-1])

    with pytest.raises(GovernedExecutionError, match="duplicate"):
        strategy.generate_signals(_ctx({SYMBOL: overlapped}, decision_time))


# -------------------------------------------------------------------------------------------
# Major 7 — a pre-open entry must not mature the same day
# -------------------------------------------------------------------------------------------


def test_a_pre_open_entry_does_not_mature_ten_minutes_later() -> None:
    """Entry 09:05, today's open 09:15 — the old rule matured it the same calendar day."""
    policy = SessionHorizonMaturity(CALENDAR10)
    pre_open = CALENDAR10.sessions[1].open_at - timedelta(minutes=10)

    matures = policy.matures_at(pre_open)

    assert matures == CALENDAR10.sessions[2].open_at
    assert matures.date() != pre_open.date()


def test_an_intraday_entry_still_matures_on_the_next_session() -> None:
    policy = SessionHorizonMaturity(CALENDAR10)
    intraday = CALENDAR10.sessions[1].open_at + timedelta(minutes=10)

    assert policy.matures_at(intraday) == CALENDAR10.sessions[2].open_at


def test_an_entry_after_the_close_belongs_to_the_next_session() -> None:
    """An entry after today's close did not trade today, so its holding starts tomorrow.

    This replaces an earlier assertion that treated a post-close entry as belonging to the session
    that had already ended. That produced the pre-open defect as its mirror image: resolving an
    entry to a session that is not open at that instant is what let a position be held for ten
    minutes and counted as a session.
    """
    policy = SessionHorizonMaturity(CALENDAR10)
    after_close = CALENDAR10.sessions[0].close_at + timedelta(hours=1)

    assert policy.matures_at(after_close) == CALENDAR10.sessions[2].open_at


# -------------------------------------------------------------------------------------------
# Major 6 — a maturity failure must halt the session, not escape it
# -------------------------------------------------------------------------------------------


def _seeded_runner(policy: object) -> RealtimeShadowRunner:
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="majors",
            model_id="m1",
            maturity_policy=policy,  # type: ignore[arg-type]
        ),
        live_feed=None,  # type: ignore[arg-type]
    )
    entry_at = CALENDAR10.sessions[-1].open_at
    proposal = ShadowProposal(
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
    runner._open_entries["p1"] = (proposal, Decimal("100.10"), entry_at)
    runner._decisions.append(proposal)
    return runner


def test_an_unresolvable_maturity_halts_the_session_and_keeps_the_audit() -> None:
    """It escaped run_session: state RUNNING, no halt reason, one decision lost, no report."""
    policy = SessionHorizonMaturity(CALENDAR10)  # calendar ends before the horizon
    runner = _seeded_runner(policy)
    later = CALENDAR10.sessions[-1].close_at
    quote = Quote(
        symbol=SYMBOL,
        timestamp=later,
        bid=Decimal("105.00"),
        ask=Decimal("105.10"),
        bid_size=100,
        ask_size=100,
    )

    runner._check_matured_outcomes(quote, later)

    assert runner.state is ShadowSessionState.SHADOW_HALTED
    assert runner.halt_reason is ShadowHaltReason.MATURITY_UNRESOLVABLE
    report = runner.build_audit_report()
    assert report.proposals_generated == 1, "the decision must survive into the audit"
    assert report.matured_outcomes == (), "no outcome may be fabricated from an unresolved maturity"


def test_run_session_returns_the_halted_audit_when_maturity_is_unresolvable() -> None:
    later = CALENDAR10.sessions[-1].close_at.astimezone(UTC)
    payload = create_upstox_quote_json(
        symbol=SYMBOL,
        bid="105.00",
        ask="105.10",
        ltp="105.05",
        timestamp_iso=later.isoformat(),
    )
    transport = MockLiveStreamTransport(queue=[payload])
    feed = UpstoxLiveFeed(
        access_token="test-token",
        dependencies=LiveFeedDependencies(transport=transport, clock=lambda: later),
    )
    feed.symbol_map["NSE_EQ|INE002A01018"] = SYMBOL
    runner = _seeded_runner(SessionHorizonMaturity(CALENDAR10))
    runner.live_feed = feed
    runner._clock = lambda: later

    report = runner.run_session(max_quotes=1)

    assert report.final_state is ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason is ShadowHaltReason.MATURITY_UNRESOLVABLE
    assert report.proposals_generated == 1
    assert report.matured_outcomes == ()


def test_the_halt_reports_no_outcome_count_it_could_not_compute() -> None:
    """A handler that reports a failure must not emit a partial result under cover of reporting.

    Generalised from a peer session's promotion CLI, which asserts the attempt count is absent from
    its refusal output so a later edit cannot recover a partial count through the same handler.
    """
    runner = _seeded_runner(SessionHorizonMaturity(CALENDAR10))
    later = CALENDAR10.sessions[-1].close_at
    quote = Quote(
        symbol=SYMBOL,
        timestamp=later,
        bid=Decimal("105.00"),
        ask=Decimal("105.10"),
        bid_size=100,
        ask_size=100,
    )

    runner._check_matured_outcomes(quote, later)

    assert runner.halt_details is not None
    assert "pnl" not in runner.halt_details.lower()
    assert "outcome_" not in runner.halt_details


def test_a_resolvable_maturity_is_unaffected() -> None:
    """The repair must not turn working maturities into halts."""
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="majors",
            model_id="m1",
            maturity_policy=SessionHorizonMaturity(CALENDAR10),
        ),
        live_feed=None,  # type: ignore[arg-type]
    )
    entry_at = CALENDAR10.sessions[0].open_at + timedelta(minutes=5)
    proposal = ShadowProposal(
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
    runner._open_entries["p1"] = (proposal, Decimal("100.10"), entry_at)
    later = CALENDAR10.sessions[2].open_at
    quote = Quote(
        symbol=SYMBOL,
        timestamp=later,
        bid=Decimal("105.00"),
        ask=Decimal("105.10"),
        bid_size=100,
        ask_size=100,
    )

    runner._check_matured_outcomes(quote, later)

    assert runner.state is not ShadowSessionState.SHADOW_HALTED
    assert len(runner._matured_outcomes) == 1


def test_maturity_policy_error_is_still_raised_by_the_policy_itself() -> None:
    """The runner catches it; the policy must keep failing closed for direct callers."""
    with pytest.raises(MaturityPolicyError):
        SessionHorizonMaturity(CALENDAR10).matures_at(CALENDAR10.sessions[-1].open_at)


# -------------------------------------------------------------------------------------------
# Major 9 — open exposure must be visible in the audit
# -------------------------------------------------------------------------------------------


def test_audit_report_states_open_exposure() -> None:
    """A held position reported nothing: matured_outcomes 0 and no field mentioning exposure."""
    runner = _seeded_runner(None)

    report = runner.build_audit_report()

    assert report.open_entries == 1
    assert report.open_symbols == (SYMBOL,)


def test_a_session_with_nothing_open_reports_zero_exposure() -> None:
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(session_id="majors", model_id="m1"),
        live_feed=None,  # type: ignore[arg-type]
    )

    report = runner.build_audit_report()

    assert report.open_entries == 0
    assert report.open_symbols == ()
