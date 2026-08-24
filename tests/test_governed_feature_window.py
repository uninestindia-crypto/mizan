"""Regression tests for the canonical governed feature window.

The same decision bar must produce the same feature vector regardless of how much older history a
serving surface happens to retain.  Wilder RSI and ATR otherwise inherit a hidden seed from the
start of the supplied sequence, so two honest callers can score different strategies.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.evidence import EvidenceStore, EvidenceStoreConfig
from quant_system.execution.governed_strategy import ExecutionSurface, GovernedModelStrategy
from quant_system.modeling import (
    FEATURE_SCHEMA_VERSION_V1,
    ModelingError,
    ModelingFailureCode,
    compute_feature_values,
    draft_from_ridge_evaluation,
    evaluate_governed_ridge_fold,
    run_persisted_ridge_trial,
)
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1
from tests.modeling_fixtures import governed_acquisition, governed_calendar
from tests.modeling_training_fixtures import governed_training_journey
from tests.test_governed_strategy import _bundle, _context


def _oscillating_history(count: int = 55):
    acquisition = governed_acquisition(count=count, calendar=governed_calendar(count))
    bars = []
    for ordinal, bar in enumerate(acquisition.records):
        close = Decimal(100) + Decimal((ordinal * 7) % 17) - Decimal((ordinal * 3) % 11)
        bars.append(
            replace(
                bar,
                open=close,
                high=close + Decimal(2),
                low=close - Decimal(2),
                close=close,
            )
        )
    return tuple(bars)


def test_feature_values_ignore_history_before_the_canonical_window() -> None:
    """Older retained bars may not alter the current decision's governed feature vector."""
    full_history = _oscillating_history()
    canonical_tail = full_history[-FEATURE_WARMUP_BARS_V1:]

    assert compute_feature_values(full_history) == compute_feature_values(canonical_tail)


def test_execution_decision_ignores_history_before_the_canonical_window() -> None:
    """The public strategy boundary must preserve both features and the resulting score."""
    history = _oscillating_history()
    canonical_tail = history[-FEATURE_WARMUP_BARS_V1:]
    decision_time = max(bar.available_at for bar in history)
    journey = governed_training_journey(score_threshold="-99")
    strategy = GovernedModelStrategy(
        _bundle(journey, score_threshold="-99"), ExecutionSurface.SHADOW
    )

    full_signal = strategy.generate_signals(_context(history, decision_time))[0]
    tail_signal = strategy.generate_signals(_context(canonical_tail, decision_time))[0]

    assert full_signal.metadata["feature_values"] == tail_signal.metadata["feature_values"]
    assert full_signal.metadata["raw_score"] == tail_signal.metadata["raw_score"]


def test_persisted_runner_refuses_a_trial_claiming_the_legacy_window(tmp_path: Path) -> None:
    """The governed training entry point may not publish v2 rows under a v1 trial identity."""
    journey = governed_training_journey()
    legacy_claim = replace(
        journey.start,
        feature_schema_version=FEATURE_SCHEMA_VERSION_V1,
    )
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))

    with pytest.raises(ModelingError) as captured:
        run_persisted_ridge_trial(
            store,
            operation_id="op-schema-mismatch",
            start=legacy_claim,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=datetime(2026, 8, 20, 12, 5, tzinfo=UTC),
        )

    assert captured.value.code is ModelingFailureCode.TRAINING_INPUT_MISMATCH


def test_model_publication_cannot_relabel_v2_evaluation_as_legacy() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )
    legacy_claim = replace(
        journey.start,
        feature_schema_version=FEATURE_SCHEMA_VERSION_V1,
    )

    with pytest.raises(ModelingError) as captured:
        draft_from_ridge_evaluation(
            evaluation,
            start=legacy_claim,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
        )

    assert captured.value.code is ModelingFailureCode.TRAINING_INPUT_MISMATCH


def test_exported_evaluator_refuses_legacy_trial_over_v2_features() -> None:
    """Schema identity must be checked before an in-memory model identity can be returned."""
    journey = governed_training_journey()
    legacy_claim = replace(
        journey.start,
        feature_schema_version=FEATURE_SCHEMA_VERSION_V1,
    )
    legacy_registry = type(journey.registry)(starts=(legacy_claim,), outcomes=())

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            legacy_claim,
            legacy_registry,
            journey.features,
            journey.labels,
            journey.fold,
        )

    assert captured.value.code is ModelingFailureCode.TRAINING_INPUT_MISMATCH
