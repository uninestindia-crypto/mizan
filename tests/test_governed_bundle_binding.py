"""Regressions for Red Team Blockers 1 and 3 on the governed execution path.

B1: a bundle accepted a model card from one model paired with the fitted state of another, because
`candidate_id` was doing the binding and every model in a campaign shares one.

B3: the adapter reimplemented scoring in Decimal, and disagreed with `predict_ridge_scores` at the
threshold boundary — trading where validation recorded nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.evidence import (
    EvidenceDraft,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
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
    FEATURE_SCHEMA_ID_V1,
    FEATURE_SCHEMA_VERSION_V1,
    ModelCardV1,
    PromotionState,
    compute_feature_values,
    standardize_feature_values,
)
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1
from quant_system.modeling.ridge import predict_ridge_scores
from quant_system.strategies.base import MarketContext
from scripts.run_governed_shadow_session import _model_symbol_for
from tests.modeling_fixtures import SYMBOL, governed_acquisition, governed_calendar
from tests.modeling_training_fixtures import governed_training_journey
from tests.test_governed_strategy import _fitted_pair

CANDIDATE = "cand_ridge_v1"


def _model_store(root: Path, symbols: tuple[str, ...]) -> EvidenceStore:
    store = EvidenceStore(EvidenceStoreConfig(root=root, min_free_bytes=0))
    records = tuple(
        sorted(
            (
                {
                    "strategy_id": "RIDGE",
                    "decision_at": f"2025-01-{ordinal + 2:02d}T10:00:00Z",
                    "symbol": symbol,
                }
                for ordinal, symbol in enumerate(symbols)
            ),
            key=lambda record: (
                record["strategy_id"],
                record["decision_at"],
                record["symbol"],
            ),
        )
    )
    store.commit(
        EvidenceDraft(
            resource_type=EvidenceResourceType.MODEL,
            resource_id="model_symbol_test",
            schema_id="quantos.fold_strategy_decision",
            schema_version=1,
            metadata={},
            records=records,
            total_order=("strategy_id", "decision_at", "symbol"),
        ),
        operation_id="publish-model-symbol-test",
    )
    return store


def _card(model_id: str, candidate_id: str = CANDIDATE) -> ModelCardV1:
    return ModelCardV1(
        model_id=model_id,
        candidate_id=candidate_id,
        verdict=PromotionState.SHADOW,
        created_at=datetime(2026, 8, 23, tzinfo=UTC),
        monitoring_limits={"max_drawdown": "0.10"},
        halt_and_rollback_policy="halt and roll back",
        limitations=("research only",),
    )


def _identity(
    model_id: str,
    fitted: object,
    standardization: object,
    threshold: str,
) -> ModelEvidenceIdentityV1:
    return ModelEvidenceIdentityV1(
        model_id=model_id,
        candidate_id=CANDIDATE,
        trial_id="trial_uni_018",
        symbol=SYMBOL,
        fitted_state_hash=fitted.fitted_state_hash,  # type: ignore[attr-defined]
        preprocessing_state_hash=standardization.state_hash,  # type: ignore[attr-defined]
        score_threshold=threshold,
        feature_schema_id=CURRENT_FEATURE_SCHEMA_ID,
        feature_schema_version=CURRENT_FEATURE_SCHEMA_VERSION,
    )


# -------------------------------------------------------------------------------------------
# Blocker 1
# -------------------------------------------------------------------------------------------


def test_bundle_refuses_a_card_from_a_different_model_than_the_fitted_state() -> None:
    """The exact Red Team break: good model's card, bad model's coefficients, same candidate_id."""
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    # Identity says these artefacts belong to model A...
    identity = _identity("model_A_the_good_one", fitted, standardization, "0")

    # ...but the card claims model B. Both carry the same candidate_id, as every campaign model does.
    with pytest.raises(GovernedExecutionError, match="model_id"):
        PromotedModelBundleV1(
            candidate_id=CANDIDATE,
            model_card=_card("model_B_a_different_model"),
            fitted=fitted,
            standardization=standardization,
            score_threshold="0",
            evidence=identity,
        )


def test_bundle_refuses_fitted_state_that_the_evidence_does_not_describe() -> None:
    """Swapping in another trial's coefficients must fail even when every id lines up."""
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    identity = ModelEvidenceIdentityV1(
        model_id="model_A",
        candidate_id=CANDIDATE,
        trial_id="trial_uni_018",
        symbol=SYMBOL,
        fitted_state_hash="f" * 64,  # a different model's fitted state
        preprocessing_state_hash=standardization.state_hash,
        score_threshold="0",
        feature_schema_id=CURRENT_FEATURE_SCHEMA_ID,
        feature_schema_version=CURRENT_FEATURE_SCHEMA_VERSION,
    )

    with pytest.raises(GovernedExecutionError, match="fitted state"):
        PromotedModelBundleV1(
            candidate_id=CANDIDATE,
            model_card=_card("model_A"),
            fitted=fitted,
            standardization=standardization,
            score_threshold="0",
            evidence=identity,
        )


def test_bundle_refuses_a_threshold_the_trial_did_not_validate() -> None:
    """-9.99 was accepted where the validated value was -0.13382."""
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    identity = _identity("model_A", fitted, standardization, "-0.13382")

    with pytest.raises(GovernedExecutionError, match="score_threshold"):
        PromotedModelBundleV1(
            candidate_id=CANDIDATE,
            model_card=_card("model_A"),
            fitted=fitted,
            standardization=standardization,
            score_threshold="-9.99",
            evidence=identity,
        )


def test_a_correctly_bound_bundle_is_still_accepted() -> None:
    """The repair must not refuse honest inputs."""
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    identity = _identity("model_A", fitted, standardization, "0")

    bundle = PromotedModelBundleV1(
        candidate_id=CANDIDATE,
        model_card=_card("model_A"),
        fitted=fitted,
        standardization=standardization,
        score_threshold="0",
        evidence=identity,
    )

    assert bundle.model_id == "model_A"


def test_identity_is_derived_from_one_manifest_so_a_pairing_cannot_be_mixed() -> None:
    """The factory reads a single published record; it cannot straddle two models."""
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    metadata = {
        "model_id": "model_A",
        "candidate_id": CANDIDATE,
        "trial_id": "trial_uni_018",
        "feature_schema_id": CURRENT_FEATURE_SCHEMA_ID,
        "feature_schema_version": CURRENT_FEATURE_SCHEMA_VERSION,
        "fitted_state": {"fitted_state_hash": fitted.fitted_state_hash},
        "preprocessing": {"state_hash": standardization.state_hash},
    }

    identity = ModelEvidenceIdentityV1.from_manifest_metadata(
        metadata, score_threshold="0", symbol=SYMBOL
    )

    assert identity.model_id == "model_A"
    assert identity.fitted_state_hash == fitted.fitted_state_hash


def test_legacy_model_manifest_without_window_schema_fails_closed() -> None:
    """Pre-repair fitted states must not be relabelled as canonical-window models."""
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    legacy_metadata = {
        "model_id": "model_legacy",
        "candidate_id": CANDIDATE,
        "trial_id": "trial_legacy_001",
        "fitted_state": {"fitted_state_hash": fitted.fitted_state_hash},
        "preprocessing": {"state_hash": standardization.state_hash},
    }

    with pytest.raises(GovernedExecutionError, match="feature_schema_id"):
        ModelEvidenceIdentityV1.from_manifest_metadata(
            legacy_metadata, score_threshold="0", symbol=SYMBOL
        )


def test_expanding_window_v1_model_is_not_executable_as_v2() -> None:
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    identity = ModelEvidenceIdentityV1(
        model_id="model_legacy",
        candidate_id=CANDIDATE,
        trial_id="trial_legacy_001",
        symbol=SYMBOL,
        fitted_state_hash=fitted.fitted_state_hash,
        preprocessing_state_hash=standardization.state_hash,
        score_threshold="0",
        feature_schema_id=FEATURE_SCHEMA_ID_V1,
        feature_schema_version=FEATURE_SCHEMA_VERSION_V1,
    )

    with pytest.raises(GovernedExecutionError, match="incompatible feature schema"):
        PromotedModelBundleV1(
            candidate_id=CANDIDATE,
            model_card=_card("model_legacy"),
            fitted=fitted,
            standardization=standardization,
            score_threshold="0",
            evidence=identity,
        )


def test_real_evidence_loader_derives_the_bound_symbol_from_published_decisions(
    tmp_path: Path,
) -> None:
    store = _model_store(tmp_path / "evidence", (SYMBOL, SYMBOL))

    assert _model_symbol_for(store, "model_symbol_test") == SYMBOL


def test_real_evidence_loader_refuses_a_multi_instrument_model(tmp_path: Path) -> None:
    store = _model_store(tmp_path / "evidence", (SYMBOL, "RELIANCE"))

    with pytest.raises(GovernedExecutionError, match="exactly one published instrument"):
        _model_symbol_for(store, "model_symbol_test")


# -------------------------------------------------------------------------------------------
# Blocker 3
# -------------------------------------------------------------------------------------------


def test_adapter_scores_with_the_validated_scorer() -> None:
    """The executing scorer must BE predict_ridge_scores, not a parallel implementation.

    The Red Team found a 4e-13 disagreement that flipped a decision at the threshold. Equality here
    is the property; anything that reintroduces a second scoring path fails it.
    """
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    acquisition = governed_acquisition(count=55, calendar=journey.calendar)
    window = acquisition.records[:FEATURE_WARMUP_BARS_V1]

    standardized = standardize_feature_values(compute_feature_values(window), standardization)
    validated = predict_ridge_scores(fitted, (standardized,))[0]

    from quant_system.execution.governed_strategy import score_row

    assert score_row(fitted, standardized) == Decimal(validated)


def test_decision_matches_validation_at_the_exact_threshold_boundary() -> None:
    """A score equal to the threshold is DOWN in validation, so it must not trade here."""
    journey = governed_training_journey()
    fitted, standardization = _fitted_pair(journey)
    acquisition = governed_acquisition(count=55, calendar=journey.calendar)
    window = acquisition.records[:FEATURE_WARMUP_BARS_V1]
    decision_time = journey.calendar.sessions[FEATURE_WARMUP_BARS_V1 - 1].close_at

    standardized = standardize_feature_values(compute_feature_values(window), standardization)
    exact = predict_ridge_scores(fitted, (standardized,))[0]

    identity = _identity("model_A", fitted, standardization, exact)
    bundle = PromotedModelBundleV1(
        candidate_id=CANDIDATE,
        model_card=_card("model_A"),
        fitted=fitted,
        standardization=standardization,
        score_threshold=exact,
        evidence=identity,
    )
    strategy = GovernedModelStrategy(bundle, ExecutionSurface.SHADOW)
    context = MarketContext(
        current_time=decision_time,
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("100000"),
        extra_data={GOVERNED_BARS_KEY: {SYMBOL: window}},
    )

    # score > threshold is strictly false when they are equal: validation records DOWN.
    assert strategy.generate_signals(context) == []


def test_governed_calendar_fixture_is_the_one_under_test() -> None:
    """Guards the fixture assumption the cases above rely on."""
    assert len(governed_calendar(55).sessions) == 55
