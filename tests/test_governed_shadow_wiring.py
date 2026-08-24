"""Tests for wiring governed models into the shadow engine.

Kept in its own file rather than added to ``tests/test_realtime_shadow.py``: that file is claimed by
the S9-B2 record and its test count is pinned as evidence by an in-flight adjudication, so new
coverage must not move it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from quant_system.core.domain import Signal
from quant_system.data.live_feed import LiveQuoteRecord, UpstoxLiveFeed
from quant_system.execution.bar_history import AcquisitionBarHistory, BarHistoryProvider
from quant_system.execution.governed_strategy import (
    GOVERNED_BARS_KEY,
    ExecutionSurface,
    GovernedModelStrategy,
    ModelEvidenceIdentityV1,
    PromotedModelBundleV1,
)
from quant_system.execution.realtime_shadow import (
    RealtimeShadowConfig,
    RealtimeShadowRunner,
)
from quant_system.modeling import (
    CURRENT_FEATURE_SCHEMA_ID,
    CURRENT_FEATURE_SCHEMA_VERSION,
    ModelCardV1,
    PromotionState,
)
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1
from quant_system.strategies.base import BaseStrategy, MarketContext
from tests.modeling_fixtures import SYMBOL, governed_acquisition, governed_calendar
from tests.modeling_training_fixtures import governed_training_journey
from tests.test_governed_strategy import _fitted_pair

CANDIDATE = "cand_ridge_v1"


def _acquisition() -> object:
    return governed_acquisition(count=55, calendar=governed_calendar(55))


def _bundle(score_threshold: str) -> PromotedModelBundleV1:
    fitted, preprocessing = _fitted_pair(governed_training_journey())
    card = ModelCardV1(
        model_id="model_shadow_wiring_test",
        candidate_id=CANDIDATE,
        verdict=PromotionState.SHADOW,
        created_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
        monitoring_limits={"max_drawdown": "0.10"},
        halt_and_rollback_policy="halt and roll back",
        limitations=("research only",),
    )
    return PromotedModelBundleV1(
        candidate_id=CANDIDATE,
        model_card=card,
        fitted=fitted,
        standardization=preprocessing,
        score_threshold=score_threshold,
        evidence=ModelEvidenceIdentityV1(
            model_id=card.model_id,
            candidate_id=CANDIDATE,
            trial_id="trial_test_001",
            symbol=SYMBOL,
            fitted_state_hash=fitted.fitted_state_hash,
            preprocessing_state_hash=preprocessing.state_hash,
            score_threshold=score_threshold,
            feature_schema_id=CURRENT_FEATURE_SCHEMA_ID,
            feature_schema_version=CURRENT_FEATURE_SCHEMA_VERSION,
        ),
    )


# ---------------------------------------------------------------------------------------------
# The provider
# ---------------------------------------------------------------------------------------------


def test_provider_serves_only_bars_available_by_the_decision_time() -> None:
    """The execution half of the point-in-time guarantee, enforced at the boundary."""
    acquisition = _acquisition()
    history = AcquisitionBarHistory([acquisition])
    bars = acquisition.records  # type: ignore[attr-defined]
    cutoff = bars[9].available_at

    served = history(SYMBOL, cutoff)

    assert len(served) == 10
    assert all(bar.available_at <= cutoff for bar in served)


def test_provider_returns_nothing_for_an_unknown_symbol() -> None:
    history = AcquisitionBarHistory([_acquisition()])

    assert history("NOT_LISTED", datetime(2030, 1, 1, tzinfo=UTC)) == ()
    assert history.symbols == (SYMBOL,)


def test_provider_serves_nothing_before_any_bar_was_available() -> None:
    acquisition = _acquisition()
    history = AcquisitionBarHistory([acquisition])
    earliest = min(bar.available_at for bar in acquisition.records)  # type: ignore[attr-defined]

    assert history(SYMBOL, earliest - timedelta(days=1)) == ()


# ---------------------------------------------------------------------------------------------
# The engine wiring
# ---------------------------------------------------------------------------------------------


def _live_quote(decision_time: datetime) -> LiveQuoteRecord:
    return LiveQuoteRecord(
        instrument_key="NSE_EQ|INE009A01021",
        symbol=SYMBOL,
        bid=Decimal("100.00"),
        ask=Decimal("100.10"),
        bid_size=100,
        ask_size=100,
        last_price=Decimal("100.05"),
        event_at=decision_time,
        received_at=decision_time,
    )


class _CapturingStrategy(BaseStrategy):
    """Records the context the runner actually built, and proposes nothing."""

    def __init__(self) -> None:
        super().__init__(name="capturing")
        self.contexts: list[MarketContext] = []

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        self.contexts.append(ctx)
        return []


def _run_one_quote(provider: BarHistoryProvider | None, decision_time: datetime) -> MarketContext:
    """Drive the real ``process_live_quote`` path and return the context the strategy saw."""
    strategy = _CapturingStrategy()
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(
            session_id="wiring",
            model_id="m1",
            freshness_budget_seconds=10_000_000.0,
            max_clock_drift_seconds=10_000_000.0,
            bar_history_provider=provider,
        ),
        live_feed=cast(UpstoxLiveFeed, None),
        strategy=strategy,
        clock=lambda: decision_time,
    )
    runner.process_live_quote(_live_quote(decision_time))
    assert strategy.contexts, "the runner never consulted the strategy"
    return strategy.contexts[0]


def test_runner_omits_governed_bars_when_no_provider_is_configured() -> None:
    """Default off: quote-driven strategies see exactly the context they saw before."""
    decision_time = _acquisition().records[FEATURE_WARMUP_BARS_V1].available_at  # type: ignore[attr-defined]

    context = _run_one_quote(None, decision_time)

    assert GOVERNED_BARS_KEY not in context.extra_data
    assert "current_quote" in context.extra_data


def test_runner_populates_governed_bars_from_the_configured_provider() -> None:
    """The wiring under test: engine-sourced point-in-time history reaches the strategy."""
    acquisition = _acquisition()
    decision_time = acquisition.records[FEATURE_WARMUP_BARS_V1].available_at  # type: ignore[attr-defined]
    history = AcquisitionBarHistory([acquisition])

    context = _run_one_quote(history, decision_time)

    served = context.extra_data[GOVERNED_BARS_KEY][SYMBOL]
    assert served == history(SYMBOL, decision_time)
    assert all(bar.available_at <= decision_time for bar in served)


def test_runner_asks_the_provider_for_the_decision_time_not_the_event_time() -> None:
    """A provider must be filtered against the instant the decision is taken."""
    acquisition = _acquisition()
    decision_time = acquisition.records[FEATURE_WARMUP_BARS_V1].available_at  # type: ignore[attr-defined]
    seen: list[tuple[str, datetime]] = []

    def spy(symbol: str, when: datetime) -> tuple:  # type: ignore[type-arg]
        seen.append((symbol, when))
        return ()

    _run_one_quote(spy, decision_time)

    assert seen == [(SYMBOL, decision_time)]


def test_default_configuration_does_not_populate_governed_bars() -> None:
    """Default off: a quote-driven strategy must behave bit-for-bit as before."""
    config = RealtimeShadowConfig(session_id="s", model_id="m")

    assert config.bar_history_provider is None


def test_configuring_a_provider_is_what_turns_governed_bars_on() -> None:
    history = AcquisitionBarHistory([_acquisition()])
    config = RealtimeShadowConfig(session_id="s", model_id="m", bar_history_provider=history)

    assert config.bar_history_provider is history


# ---------------------------------------------------------------------------------------------
# End to end: a governed model reaches a decision from engine-supplied history
# ---------------------------------------------------------------------------------------------


def test_governed_model_decides_from_engine_supplied_history() -> None:
    """The whole point: history the engine supplies drives a real governed decision.

    Exercises the contract the runner fulfils — ``extra_data[GOVERNED_BARS_KEY]`` populated from the
    provider, filtered to the decision time — and confirms the adapter turns it into a signal.
    """
    acquisition = _acquisition()
    history = AcquisitionBarHistory([acquisition])
    decision_time = acquisition.records[FEATURE_WARMUP_BARS_V1 - 1].available_at  # type: ignore[attr-defined]
    strategy = GovernedModelStrategy(_bundle("-99"), ExecutionSurface.SHADOW)

    context = MarketContext(
        current_time=decision_time,
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("1000000.00"),
        extra_data={GOVERNED_BARS_KEY: {SYMBOL: history(SYMBOL, decision_time)}},
    )
    signals = strategy.generate_signals(context)

    assert len(signals) == 1
    assert signals[0].symbol == SYMBOL
    assert signals[0].metadata["model_id"] == "model_shadow_wiring_test"


def test_engine_supplied_history_is_too_short_before_warmup_completes() -> None:
    """Early in a session the model must stay silent rather than emit a degraded signal."""
    acquisition = _acquisition()
    history = AcquisitionBarHistory([acquisition])
    too_early = acquisition.records[FEATURE_WARMUP_BARS_V1 - 3].available_at  # type: ignore[attr-defined]
    strategy = GovernedModelStrategy(_bundle("-99"), ExecutionSurface.SHADOW)

    context = MarketContext(
        current_time=too_early,
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("1000000.00"),
        extra_data={GOVERNED_BARS_KEY: {SYMBOL: history(SYMBOL, too_early)}},
    )

    assert strategy.generate_signals(context) == []
