"""Deterministic governed ridge fit and score-contract tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    evaluate_governed_ridge_fold,
    fit_ridge_classifier,
    fit_standardization,
    transform_feature_rows,
)
from tests.modeling_training_fixtures import fold_feature_rows, governed_training_journey


def test_governed_ridge_fold_is_exactly_repeatable_with_pinned_hashes() -> None:
    journey = governed_training_journey()

    first = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )
    second = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    assert first == second
    assert (
        first.evaluation_hash
        == "69eff821d3edd726d709b522e25e02b7b17f90d29411c15adb34867dda4cc01c"  # pragma: allowlist secret - deterministic public test hash.
    )
    assert (
        first.fitted_state.fitted_state_hash
        == (
            "158bea8b60261760af6a3df9dbee132ce087dd9f374e765db0874578300a185f"  # pragma: allowlist secret - deterministic public test hash.
        )
    )
    assert (
        first.ridge_report.prediction_hash
        == (
            "af2001a9aa94c4a25edb745eff88f5fe2f9f540c5989732aa5721fdf2f99e7ec"  # pragma: allowlist secret - deterministic public test hash.
        )
    )
    assert (
        first.ridge_report.metrics_hash
        == (
            "320375e5c2dcdaedf8d5bc26d2d7ca7224557bc37da4f01adfb738e073af8a91"  # pragma: allowlist secret - deterministic public test hash.
        )
    )


def test_ridge_reports_uncalibrated_scores_and_all_required_baselines() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    assert tuple(report.strategy_id for report in evaluation.strategy_reports) == (
        "RIDGE",
        "NO_TRADE",
        "BUY_AND_HOLD",
        "PREVIOUS_SIGN",
        "EQUITY_DUAL_MOMENTUM",
    )
    assert {decision.score_kind for decision in evaluation.ridge_report.decisions} == {
        "UNCALIBRATED_SCORE"
    }
    assert evaluation.ridge_report.metrics.accuracy == "0.875"
    assert evaluation.ridge_report.metrics.trade_count == 7
    assert evaluation.model_id.startswith("model_")


def test_l2_change_changes_fit_but_not_train_only_preprocessing() -> None:
    first_journey = governed_training_journey(l2_penalty="1")
    changed_journey = governed_training_journey(
        l2_penalty="2",
        trial_id="trial_ridge_002",
    )

    first = evaluate_governed_ridge_fold(
        first_journey.start,
        first_journey.registry,
        first_journey.features,
        first_journey.labels,
        first_journey.fold,
    )
    changed = evaluate_governed_ridge_fold(
        changed_journey.start,
        changed_journey.registry,
        changed_journey.features,
        changed_journey.labels,
        changed_journey.fold,
    )

    assert first.preprocessing == changed.preprocessing
    assert first.fitted_state.fitted_state_hash != changed.fitted_state.fitted_state_hash
    assert first.ridge_report.prediction_hash != changed.ridge_report.prediction_hash


def test_score_equal_to_threshold_is_down_by_contract() -> None:
    baseline_journey = governed_training_journey()
    baseline = evaluate_governed_ridge_fold(
        baseline_journey.start,
        baseline_journey.registry,
        baseline_journey.features,
        baseline_journey.labels,
        baseline_journey.fold,
    )
    threshold = baseline.ridge_report.decisions[0].score
    assert threshold is not None
    boundary_journey = governed_training_journey(
        score_threshold=threshold,
        trial_id="trial_ridge_boundary",
    )

    boundary = evaluate_governed_ridge_fold(
        boundary_journey.start,
        boundary_journey.registry,
        boundary_journey.features,
        boundary_journey.labels,
        boundary_journey.fold,
    )

    assert boundary.ridge_report.decisions[0].score == threshold
    assert boundary.ridge_report.decisions[0].predicted_target == "DOWN"


def test_constant_targets_and_insufficient_rows_fail_closed() -> None:
    journey = governed_training_journey()
    training_rows = fold_feature_rows(journey, validation=False)
    preprocessing = fit_standardization(training_rows)
    transformed = transform_feature_rows(training_rows, preprocessing)

    with pytest.raises(ModelingError) as constant:
        fit_ridge_classifier(
            journey.start,
            preprocessing,
            transformed,
            ("UP",) * len(transformed),
        )
    with pytest.raises(ModelingError) as insufficient:
        fit_ridge_classifier(
            journey.start,
            preprocessing,
            transformed[:7],
            tuple(row.target for row in journey.fold.train_rows[:7]),
        )

    assert constant.value.code == ModelingFailureCode.CONSTANT_TARGET
    assert insufficient.value.code == ModelingFailureCode.INSUFFICIENT_TRAINING_ROWS


def test_unregistered_trial_and_wrong_dataset_identity_fail_closed() -> None:
    journey = governed_training_journey()
    other = governed_training_journey(trial_id="trial_ridge_999")
    wrong_dataset = replace(journey.start, dataset_hash="f" * 64)

    with pytest.raises(ModelingError) as unregistered:
        evaluate_governed_ridge_fold(
            other.start,
            journey.registry,
            journey.features,
            journey.labels,
            journey.fold,
        )
    with pytest.raises(ModelingError) as mismatch:
        evaluate_governed_ridge_fold(
            wrong_dataset,
            type(journey.registry)(starts=(wrong_dataset,), outcomes=()),
            journey.features,
            journey.labels,
            journey.fold,
        )

    assert unregistered.value.code == ModelingFailureCode.MULTIPLICITY_INVALID
    assert mismatch.value.code == ModelingFailureCode.TRAINING_INPUT_MISMATCH
