"""Tests for the governed model to execution adapter.

The defect under guard: the system that executed was not the system that was validated. These tests
hold the adapter to the two properties that make it faithful — it computes features with the
training kernel, and it reproduces the decision rule the model was actually evaluated under.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.core.domain import Side
from quant_system.execution.governed_strategy import (
    GOVERNED_BARS_KEY,
    ExecutionSurface,
    GovernedExecutionError,
    GovernedModelStrategy,
    ModelEvidenceIdentityV1,
    PromotedModelBundleV1,
)
from quant_system.modeling import (
    CURRENT_FEATURE_SCHEMA_ID,
    CURRENT_FEATURE_SCHEMA_VERSION,
    ModelCardV1,
    PromotionState,
    RidgeFittedStateV1,
    StandardizationStateV1,
    build_feature_dataset,
    compute_feature_values,
    fit_standardization,
    standardize_feature_values,
    transform_feature_rows,
)
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1
from quant_system.modeling.ridge import fit_ridge_classifier
from quant_system.strategies.base import MarketContext
from tests.modeling_fixtures import (
    INSTRUMENT_KEY,
    SYMBOL,
    governed_acquisition,
    governed_calendar,
    governed_universe,
)
from tests.modeling_training_fixtures import fold_feature_rows, governed_training_journey

CANDIDATE = "cand_ridge_v1"


@pytest.fixture(scope="module")
def journey() -> object:
    return governed_training_journey()


def _fitted_pair(journey: object) -> tuple[RidgeFittedStateV1, StandardizationStateV1]:
    """Fit exactly as the training stack does, so the two states genuinely bind."""
    train_features = fold_feature_rows(journey, validation=False)  # type: ignore[arg-type]
    preprocessing = fit_standardization(train_features)
    fitted = fit_ridge_classifier(
        journey.start,  # type: ignore[attr-defined]
        preprocessing,
        transform_feature_rows(train_features, preprocessing),
        tuple(row.target for row in journey.fold.train_rows),  # type: ignore[attr-defined]
    )
    return fitted, preprocessing


def _card(
    verdict: PromotionState = PromotionState.SHADOW,
    candidate_id: str = CANDIDATE,
) -> ModelCardV1:
    return ModelCardV1(
        model_id="model_governed_adapter_test",
        candidate_id=candidate_id,
        verdict=verdict,
        created_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
        monitoring_limits={"max_drawdown": "0.10"},
        halt_and_rollback_policy="halt on breach and roll back to the previous active model",
        limitations=("research evidence only",),
    )


def _bundle(
    journey: object,
    *,
    verdict: PromotionState = PromotionState.SHADOW,
    score_threshold: str = "0",
    candidate_id: str = CANDIDATE,
) -> PromotedModelBundleV1:
    fitted, preprocessing = _fitted_pair(journey)
    card = _card(verdict, candidate_id)
    return PromotedModelBundleV1(
        candidate_id=candidate_id,
        model_card=card,
        fitted=fitted,
        standardization=preprocessing,
        score_threshold=score_threshold,
        evidence=ModelEvidenceIdentityV1(
            model_id=card.model_id,
            candidate_id=candidate_id,
            trial_id="trial_test_001",
            symbol=SYMBOL,
            fitted_state_hash=fitted.fitted_state_hash,
            preprocessing_state_hash=preprocessing.state_hash,
            score_threshold=score_threshold,
            feature_schema_id=CURRENT_FEATURE_SCHEMA_ID,
            feature_schema_version=CURRENT_FEATURE_SCHEMA_VERSION,
        ),
    )


def _context(bars: tuple[object, ...], decision_time: datetime) -> MarketContext:
    return MarketContext(
        current_time=decision_time,
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("100000"),
        extra_data={GOVERNED_BARS_KEY: {SYMBOL: bars}},
    )


# ---------------------------------------------------------------------------------------------
# R1 — feature identity. This is the property the whole adapter rests on.
# ---------------------------------------------------------------------------------------------


# test-allow: loop-in-test — the governed feature builder guarantees a non-empty closed dataset.
def test_adapter_features_are_identical_to_training_features() -> None:
    """Execution features must equal training features bar for bar, not merely approximate them.

    What this proves: the adapter selects the same bar window the training builder does —
    oldest-first, inclusive of the decision bar. A one-bar shift in either direction fails it,
    which was confirmed by mutation.

    What it structurally cannot prove: arithmetic identity. Both sides call
    ``compute_feature_values``, so mutating that kernel moves both sides together and this
    assertion stays green. That is by design, not an oversight — arithmetic identity is
    guaranteed by there being exactly one implementation, which is the whole point of promoting
    the kernel. The failure mode this defends against is a second implementation reappearing;
    the defence is structural, and the test guards the windowing that a shared kernel cannot.
    """
    calendar = governed_calendar(55)
    universe = governed_universe()
    acquisition = governed_acquisition(count=55, calendar=calendar, universe=universe)
    dataset = build_feature_dataset(acquisition, CANDIDATE, calendar, universe)

    adapter_values = [
        compute_feature_values(acquisition.records[: FEATURE_WARMUP_BARS_V1 + offset])
        for offset in range(len(dataset.rows))
    ]
    training_values = [dict(row.features) for row in dataset.rows]

    assert adapter_values == training_values


def test_adapter_standardization_is_identical_to_training_standardization(journey: object) -> None:
    _, preprocessing = _fitted_pair(journey)
    row = fold_feature_rows(journey, validation=True)[0]  # type: ignore[arg-type]

    assert (
        standardize_feature_values(row.features, preprocessing)
        == transform_feature_rows((row,), preprocessing)[0]
    )


# ---------------------------------------------------------------------------------------------
# The validated decision rule
# ---------------------------------------------------------------------------------------------


def test_strategy_emits_buy_only_when_the_score_clears_the_threshold(journey: object) -> None:
    """Reproduces validation.py: a row is UP when its score exceeds score_threshold."""
    fitted, preprocessing = _fitted_pair(journey)
    acquisition = governed_acquisition(count=55, calendar=journey.calendar)  # type: ignore[attr-defined]
    window = acquisition.records[:FEATURE_WARMUP_BARS_V1]
    decision_time = journey.calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at  # type: ignore[attr-defined]

    standardized = standardize_feature_values(compute_feature_values(window), preprocessing)
    score = Decimal(fitted.intercept) + sum(
        (Decimal(v) * Decimal(c) for v, c in zip(standardized, fitted.coefficients, strict=True)),
        start=Decimal(0),
    )

    below = GovernedModelStrategy(
        _bundle(journey, score_threshold=str(score + Decimal("1"))), ExecutionSurface.SHADOW
    )
    above = GovernedModelStrategy(
        _bundle(journey, score_threshold=str(score - Decimal("1"))), ExecutionSurface.SHADOW
    )

    assert below.generate_signals(_context(window, decision_time)) == []
    assert len(above.generate_signals(_context(window, decision_time))) == 1


def test_strategy_never_emits_a_sell(journey: object) -> None:
    """Long-only is a correctness property: the model was never evaluated short."""
    acquisition = governed_acquisition(count=55, calendar=journey.calendar)  # type: ignore[attr-defined]
    window = acquisition.records[:FEATURE_WARMUP_BARS_V1]
    decision_time = journey.calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at  # type: ignore[attr-defined]
    strategy = GovernedModelStrategy(
        _bundle(journey, score_threshold="-99"), ExecutionSurface.SHADOW
    )

    signals = strategy.generate_signals(_context(window, decision_time))

    assert signals
    assert {signal.side for signal in signals} == {Side.BUY}


def test_score_inside_the_abstention_band_emits_nothing(journey: object) -> None:
    """A model barely above its threshold must abstain, not trade at negligible conviction."""
    acquisition = governed_acquisition(count=55, calendar=journey.calendar)  # type: ignore[attr-defined]
    window = acquisition.records[:FEATURE_WARMUP_BARS_V1]
    decision_time = journey.calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at  # type: ignore[attr-defined]
    bundle = _bundle(journey, score_threshold="-99")

    assert GovernedModelStrategy(bundle, ExecutionSurface.SHADOW).generate_signals(
        _context(window, decision_time)
    )
    assert (
        GovernedModelStrategy(
            bundle, ExecutionSurface.SHADOW, abstain_band="1000"
        ).generate_signals(_context(window, decision_time))
        == []
    )


def test_signal_metadata_reconciles_the_decision_to_the_model(journey: object) -> None:
    acquisition = governed_acquisition(count=55, calendar=journey.calendar)  # type: ignore[attr-defined]
    window = acquisition.records[:FEATURE_WARMUP_BARS_V1]
    decision_time = journey.calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at  # type: ignore[attr-defined]
    bundle = _bundle(journey, score_threshold="-99")

    signal = GovernedModelStrategy(bundle, ExecutionSurface.SHADOW).generate_signals(
        _context(window, decision_time)
    )[0]

    assert signal.metadata["model_card_hash"] == bundle.model_card.model_card_hash
    assert signal.metadata["fitted_state_hash"] == bundle.fitted.fitted_state_hash
    assert signal.metadata["preprocessing_state_hash"] == bundle.standardization.state_hash
    assert signal.metadata["score_threshold"] == "-99"
    assert signal.metadata["feature_values"] == compute_feature_values(window)
    assert 0.0 <= signal.strength <= 1.0


# ---------------------------------------------------------------------------------------------
# R5 — bundle integrity and verdict gating
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("verdict", [PromotionState.REJECT, PromotionState.RESEARCH_ONLY])
def test_bundle_refuses_a_non_executable_verdict(journey: object, verdict: PromotionState) -> None:
    with pytest.raises(GovernedExecutionError, match="not executable"):
        _bundle(journey, verdict=verdict)


def test_shadow_verdict_may_not_drive_the_paper_pilot(journey: object) -> None:
    """A verdict is a ceiling. Handing a shadow model to the pilot must not silently promote it."""
    bundle = _bundle(journey, verdict=PromotionState.SHADOW)

    with pytest.raises(GovernedExecutionError, match="may not drive the"):
        GovernedModelStrategy(bundle, ExecutionSurface.PAPER_PILOT)


def test_paper_verdict_may_drive_every_promotion_surface(journey: object) -> None:
    bundle = _bundle(journey, verdict=PromotionState.PAPER)

    assert GovernedModelStrategy(bundle, ExecutionSurface.SHADOW).surface is ExecutionSurface.SHADOW
    assert GovernedModelStrategy(bundle, ExecutionSurface.PAPER).surface is ExecutionSurface.PAPER


def test_a_promotable_model_may_not_drive_the_research_observation_surface(journey: object) -> None:
    """RESEARCH_PAPER is not "the most permissive surface" -- it is a different purpose.

    A promotable model running there would file its results as research observation rather than as
    a pilot, which is the opposite of the mistake the exemption exists to prevent.
    """
    bundle = _bundle(journey, verdict=PromotionState.PAPER)

    with pytest.raises(GovernedExecutionError, match="may not drive the RESEARCH_PAPER"):
        GovernedModelStrategy(bundle, ExecutionSurface.RESEARCH_PAPER)


def test_bundle_refuses_a_card_describing_a_different_candidate(journey: object) -> None:
    fitted, preprocessing = _fitted_pair(journey)

    other = _card(candidate_id="cand_something_else")
    with pytest.raises(GovernedExecutionError, match="candidate"):
        PromotedModelBundleV1(
            candidate_id=CANDIDATE,
            model_card=other,
            fitted=fitted,
            standardization=preprocessing,
            score_threshold="0",
            evidence=ModelEvidenceIdentityV1(
                model_id=other.model_id,
                candidate_id="cand_something_else",
                trial_id="trial_test_001",
                symbol=SYMBOL,
                fitted_state_hash=fitted.fitted_state_hash,
                preprocessing_state_hash=preprocessing.state_hash,
                score_threshold="0",
                feature_schema_id=CURRENT_FEATURE_SCHEMA_ID,
                feature_schema_version=CURRENT_FEATURE_SCHEMA_VERSION,
            ),
        )


def test_bundle_refuses_a_standardization_that_did_not_produce_the_fit(journey: object) -> None:
    """Scoring live features with a mismatched scaler silently changes the model."""
    fitted, _ = _fitted_pair(journey)
    other = fit_standardization(fold_feature_rows(journey, validation=True))  # type: ignore[arg-type]

    card = _card()
    with pytest.raises(GovernedExecutionError, match="mismatched scaler|not produced"):
        PromotedModelBundleV1(
            candidate_id=CANDIDATE,
            model_card=card,
            fitted=fitted,
            standardization=other,
            score_threshold="0",
            evidence=ModelEvidenceIdentityV1(
                model_id=card.model_id,
                candidate_id=CANDIDATE,
                trial_id="trial_test_001",
                symbol=SYMBOL,
                fitted_state_hash=fitted.fitted_state_hash,
                preprocessing_state_hash=other.state_hash,
                score_threshold="0",
                feature_schema_id=CURRENT_FEATURE_SCHEMA_ID,
                feature_schema_version=CURRENT_FEATURE_SCHEMA_VERSION,
            ),
        )


# ---------------------------------------------------------------------------------------------
# R5 — surface faults versus genuine model outcomes
# ---------------------------------------------------------------------------------------------


def test_missing_bar_history_raises_rather_than_silently_abstaining(journey: object) -> None:
    """A misconfigured surface must not be indistinguishable from a model with no opinion."""
    strategy = GovernedModelStrategy(_bundle(journey), ExecutionSurface.SHADOW)
    context = MarketContext(
        current_time=datetime(2026, 8, 22, 10, 0, tzinfo=UTC),
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("1"),
        extra_data={},
    )

    with pytest.raises(GovernedExecutionError, match=GOVERNED_BARS_KEY):
        strategy.generate_signals(context)


def test_insufficient_warmup_emits_no_signal_rather_than_a_degraded_one(journey: object) -> None:
    acquisition = governed_acquisition(count=55, calendar=journey.calendar)  # type: ignore[attr-defined]
    short_window = acquisition.records[: FEATURE_WARMUP_BARS_V1 - 1]
    decision_time = journey.calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at  # type: ignore[attr-defined]
    strategy = GovernedModelStrategy(
        _bundle(journey, score_threshold="-99"), ExecutionSurface.SHADOW
    )

    assert strategy.generate_signals(_context(short_window, decision_time)) == []


def test_bars_not_yet_available_are_excluded_from_the_decision(journey: object) -> None:
    """The execution half of the point-in-time guarantee."""
    acquisition = governed_acquisition(count=55, calendar=journey.calendar)  # type: ignore[attr-defined]
    window = acquisition.records[:FEATURE_WARMUP_BARS_V1]
    strategy = GovernedModelStrategy(
        _bundle(journey, score_threshold="-99"), ExecutionSurface.SHADOW
    )
    before_any_bar_was_available = min(bar.available_at for bar in window) - timedelta(days=1)

    assert strategy.generate_signals(_context(window, before_any_bar_was_available)) == []


def test_unknown_symbol_simply_produces_no_signal(journey: object) -> None:
    strategy = GovernedModelStrategy(_bundle(journey), ExecutionSurface.SHADOW)
    context = MarketContext(
        current_time=datetime(2026, 8, 22, 10, 0, tzinfo=UTC),
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("1"),
        extra_data={GOVERNED_BARS_KEY: {}},
    )

    assert strategy.generate_signals(context) == []


def test_instrument_key_fixture_matches_the_symbol_under_test() -> None:
    """Guards the fixture assumption the other cases rely on."""
    assert INSTRUMENT_KEY.endswith("INE009A01021")
    assert SYMBOL == "INFY"
