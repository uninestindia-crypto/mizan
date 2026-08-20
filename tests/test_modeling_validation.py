"""Fold metrics, baseline timing, and multiplicity tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    TrialRegistryV1,
    TrialState,
    evaluate_governed_ridge_fold,
    fold_spec_hash,
    unsuccessful_outcome,
)
from tests.modeling_training_fixtures import governed_training_journey


def test_all_strategies_share_validation_chronology_and_cost_bound_returns(  # test-allow: loop-in-test - evaluation construction guarantees five non-empty reports.
) -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    expected_times = tuple(row.decision_at for row in journey.fold.validation_rows)
    assert all(
        tuple(decision.decision_at for decision in report.decisions) == expected_times
        for report in evaluation.strategy_reports
    )
    assert all(
        decision.realized_net_return
        == (
            journey.fold.validation_rows[index].net_return
            if decision.predicted_target == "UP"
            else "0"
        )
        for report in evaluation.strategy_reports
        for index, decision in enumerate(report.decisions)
    )


def test_previous_sign_uses_only_labels_matured_by_each_decision(  # test-allow: loop-in-test - the governed fixture guarantees validation decisions.
) -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )
    previous = evaluation.strategy_reports[3]

    for decision in previous.decisions:
        matured = tuple(row for row in journey.labels.rows if row.exit_at <= decision.decision_at)
        assert matured
        assert decision.predicted_target == matured[-1].target


def test_multiplicity_changes_dsr_but_not_predictions_or_metrics() -> None:
    journey = governed_training_journey()
    prior = replace(
        journey.start,
        trial_id="trial_prior_001",
        multiplicity_ordinal=1,
    )
    current = replace(journey.start, multiplicity_ordinal=2)
    prior_outcome = unsuccessful_outcome(
        prior,
        state=TrialState.FAILED,
        ended_at=journey.start.created_at,
        failure_codes=("MODEL_FIT_FAILED",),
    )
    registry = TrialRegistryV1(starts=(prior, current), outcomes=(prior_outcome,))
    one_trial = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )
    two_trials = evaluate_governed_ridge_fold(
        current,
        registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    assert one_trial.ridge_report.prediction_hash == two_trials.ridge_report.prediction_hash
    assert one_trial.ridge_report.metrics_hash == two_trials.ridge_report.metrics_hash
    assert one_trial.deflated_sharpe_ratio != two_trials.deflated_sharpe_ratio
    assert two_trials.multiplicity_count == 2


def test_forged_fold_rows_and_hashes_fail_closed() -> None:
    journey = governed_training_journey()
    forged_row = replace(journey.fold.train_rows[0], symbol="TCS")
    forged_fold = replace(
        journey.fold,
        train_rows=(forged_row, *journey.fold.train_rows[1:]),
    )

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            journey.start,
            journey.registry,
            journey.features,
            journey.labels,
            forged_fold,
        )

    assert captured.value.code == ModelingFailureCode.TRAINING_INPUT_MISMATCH


def test_forged_fold_class_balance_fails_closed_even_when_rehashed() -> None:
    journey = governed_training_journey()
    forged_spec = replace(
        journey.fold.spec,
        train_class_balance={"DOWN": 0, "UP": journey.fold.spec.train_row_count},
    )
    forged_fold = replace(journey.fold, spec=forged_spec)
    forged_start = replace(journey.start, fold_spec_hashes=(fold_spec_hash(forged_fold),))
    registry = TrialRegistryV1(starts=(forged_start,), outcomes=())

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            forged_start,
            registry,
            journey.features,
            journey.labels,
            forged_fold,
        )

    assert captured.value.code == ModelingFailureCode.PARTITION_INVALID


def test_forged_fold_time_bounds_fail_closed_even_when_rehashed() -> None:
    journey = governed_training_journey()
    forged_spec = replace(
        journey.fold.spec,
        train_end=journey.fold.train_rows[-2].decision_at,
    )
    forged_fold = replace(journey.fold, spec=forged_spec)
    forged_start = replace(journey.start, fold_spec_hashes=(fold_spec_hash(forged_fold),))
    registry = TrialRegistryV1(starts=(forged_start,), outcomes=())

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            forged_start,
            registry,
            journey.features,
            journey.labels,
            forged_fold,
        )

    assert captured.value.code == ModelingFailureCode.PARTITION_INVALID
