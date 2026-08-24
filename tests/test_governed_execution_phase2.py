"""Phase 2 regressions for governed shadow-execution integrity.

These tests preserve the failures independently reproduced after the Majors 4-9 audit:

* a provider could bind another instrument's bars under the model instrument's map key;
* malformed governed input escaped ``run_session`` and discarded the terminal audit;
* maturity settlement could mutate cash, position, and outcomes before a later entry failed.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from quant_system.core.domain import Quote, Side
from quant_system.data.live_feed import LiveFeedDependencies, UpstoxLiveFeed
from quant_system.execution.governed_strategy import (
    ExecutionSurface,
    GovernedExecutionError,
    GovernedModelStrategy,
)
from quant_system.execution.maturity import SessionHorizonMaturity
from quant_system.execution.realtime_shadow import (
    RealtimeShadowConfig,
    RealtimeShadowRunner,
    ShadowDecisionStatus,
    ShadowHaltReason,
    ShadowProposal,
    ShadowSessionState,
)
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1
from tests.modeling_fixtures import SYMBOL
from tests.test_governed_execution_majors import CALENDAR10, _bundle, _ctx, _window
from tests.test_realtime_shadow import MockLiveStreamTransport, create_upstox_quote_json


def _feed(symbol: str, event_at: datetime) -> UpstoxLiveFeed:
    payload = create_upstox_quote_json(
        symbol=symbol,
        bid="105.00",
        ask="105.10",
        ltp="105.05",
        timestamp_iso=event_at.astimezone(UTC).isoformat(),
    )
    feed = UpstoxLiveFeed(
        access_token="test-token",
        dependencies=LiveFeedDependencies(
            transport=MockLiveStreamTransport(queue=[payload]),
            clock=lambda: event_at,
        ),
    )
    feed.symbol_map["NSE_EQ|INE002A01018"] = symbol
    return feed


def _governed_session(provider: object, decision_at: datetime) -> RealtimeShadowRunner:
    return RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="phase2-input-integrity",
            model_id="model_majors_test",
            freshness_budget_seconds=10_000_000.0,
            max_clock_drift_seconds=10_000_000.0,
            bar_history_provider=provider,  # type: ignore[arg-type]
        ),
        live_feed=_feed(SYMBOL, decision_at),
        strategy=GovernedModelStrategy(_bundle(), ExecutionSurface.SHADOW),
        clock=lambda: decision_at,
    )


def _proposal(proposal_id: str, entry_at: datetime) -> ShadowProposal:
    return ShadowProposal(
        proposal_id=proposal_id,
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


def _seed_entry(
    runner: RealtimeShadowRunner,
    proposal_id: str,
    entry_at: datetime,
) -> None:
    proposal = _proposal(proposal_id, entry_at)
    entry_price = Decimal("100.10")
    runner._record_hypothetical_fill(SYMBOL, Side.BUY, proposal.quantity, entry_price)
    runner._open_entries[proposal_id] = (proposal, entry_price, entry_at)
    runner._decisions.append(proposal)


def test_strategy_rejects_bars_whose_internal_symbol_differs_from_bound_key() -> None:
    window, calendar = _window()
    wrong_instrument = tuple(replace(bar, symbol="RELIANCE") for bar in window)
    decision_at = calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at
    strategy = GovernedModelStrategy(_bundle(), ExecutionSurface.SHADOW)

    with pytest.raises(GovernedExecutionError, match="RELIANCE"):
        strategy.generate_signals(_ctx({SYMBOL: wrong_instrument}, decision_at))


def test_wrong_instrument_provider_halts_session_with_terminal_audit() -> None:
    window, calendar = _window()
    wrong_instrument = tuple(replace(bar, symbol="RELIANCE") for bar in window)
    decision_at = calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at
    runner = _governed_session(lambda _symbol, _when: wrong_instrument, decision_at)

    report = runner.run_session(max_quotes=1)

    assert report.final_state is ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason is ShadowHaltReason.GOVERNED_INPUT_INVALID
    assert report.proposals_generated == 0
    assert report.broker_orders_submitted == 0


@pytest.mark.parametrize(
    "provider",
    [
        pytest.param(lambda _symbol, _when: None, id="not-a-sequence"),
        pytest.param(
            lambda _symbol, _when: (*_window()[0], _window()[0][-1]),
            id="duplicate-exchange-date",
        ),
    ],
)
def test_malformed_governed_provider_halts_session_with_terminal_audit(provider: object) -> None:
    _window_bars, calendar = _window()
    decision_at = calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at
    runner = _governed_session(provider, decision_at)

    report = runner.run_session(max_quotes=1)

    assert report.final_state is ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason is ShadowHaltReason.GOVERNED_INPUT_INVALID
    assert report.proposals_generated == 0
    assert report.broker_orders_submitted == 0


def test_unresolvable_entry_makes_the_whole_maturity_batch_a_no_op() -> None:
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="phase2-atomic-maturity",
            model_id="m1",
            maturity_policy=SessionHorizonMaturity(CALENDAR10),
        ),
        live_feed=None,  # type: ignore[arg-type]
    )
    _seed_entry(runner, "old-resolvable", CALENDAR10.sessions[0].open_at)
    _seed_entry(runner, "new-unresolvable", CALENDAR10.sessions[-1].open_at)
    cash_before = runner._cash
    position_before = runner._positions[SYMBOL]
    now = CALENDAR10.sessions[-1].close_at

    runner._check_matured_outcomes(_quote(now), now)

    report = runner.build_audit_report()
    assert report.final_state is ShadowSessionState.SHADOW_HALTED
    assert report.halt_reason is ShadowHaltReason.MATURITY_UNRESOLVABLE
    assert report.matured_outcomes == ()
    assert report.open_entries == 2
    assert runner._cash == cash_before
    assert runner._positions[SYMBOL] == position_before


def test_valid_multi_entry_maturity_batch_settles_every_entry() -> None:
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="phase2-valid-maturity",
            model_id="m1",
            maturity_policy=SessionHorizonMaturity(CALENDAR10),
        ),
        live_feed=None,  # type: ignore[arg-type]
    )
    _seed_entry(runner, "first", CALENDAR10.sessions[0].open_at)
    _seed_entry(runner, "second", CALENDAR10.sessions[1].open_at)
    now = CALENDAR10.sessions[3].open_at

    runner._check_matured_outcomes(_quote(now), now)

    report = runner.build_audit_report()
    assert report.final_state is not ShadowSessionState.SHADOW_HALTED
    assert [outcome.proposal_id for outcome in report.matured_outcomes] == ["first", "second"]
    assert report.open_entries == 0
    assert SYMBOL not in runner._positions
