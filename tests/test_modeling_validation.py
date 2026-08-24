"""Fold metrics, baseline timing, and multiplicity tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from quant_system.analytics.errors import MultiplicityError, MultiplicityFailureCode
from quant_system.analytics.multiplicity import OverfittingDiagnostics
from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    TrialRegistryV1,
    TrialState,
    evaluate_governed_ridge_fold,
    fold_spec_hash,
    unsuccessful_outcome,
)
from quant_system.modeling.validation import deflate_ridge_report
from tests.modeling_training_fixtures import (
    _fixture_class_balance as _class_balance,
)
from tests.modeling_training_fixtures import (
    _fixture_rows_hash as _rows_hash,
)
from tests.modeling_training_fixtures import (
    governed_training_journey,
    leaky_zero_removal_fold,
    rebound_journey,
    symbol_collision_features,
)


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


def test_training_label_maturing_inside_validation_window_fails_closed() -> None:
    journey = governed_training_journey()
    leaky = rebound_journey(journey, leaky_zero_removal_fold(journey))
    matured_late = tuple(
        row for row in leaky.fold.train_rows if row.exit_at >= leaky.fold.spec.validation_start
    )

    assert matured_late, "attack requires at least one training label maturing after the boundary"
    assert leaky.fold.purged_record_keys == ()
    assert leaky.fold.embargoed_record_keys == ()
    assert leaky.fold.spec.purge_start == leaky.fold.spec.validation_start

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            leaky.start,
            leaky.registry,
            leaky.features,
            leaky.labels,
            leaky.fold,
        )

    assert captured.value.code == ModelingFailureCode.PARTITION_INVALID
    assert captured.value.offending_record_key == matured_late[0].record_key


def test_declared_label_horizon_must_equal_the_contract_constant() -> None:
    journey = governed_training_journey()
    forged = rebound_journey(
        journey,
        replace(
            journey.fold,
            spec=replace(journey.fold.spec, label_horizon_sessions=1, embargo_sessions=1),
        ),
    )

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            forged.start,
            forged.registry,
            forged.features,
            forged.labels,
            forged.fold,
        )

    assert captured.value.code == ModelingFailureCode.PARTITION_INVALID


def test_candidate_that_never_trades_fails_closed_instead_of_publishing_half() -> None:
    """Red Team Major 6: PSR of a fabricated zero is not a 50 percent chance of an edge."""
    journey = governed_training_journey(score_threshold="1000000")

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            journey.start,
            journey.registry,
            journey.features,
            journey.labels,
            journey.fold,
        )

    assert captured.value.code == ModelingFailureCode.DEGENERATE_RETURN_SERIES


def test_impossible_return_moments_translate_to_a_typed_modeling_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The analytics code must not escape the governed path as a bare ValueError."""
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    def reject_impossible_moments(**_kwargs: object) -> float:
        raise MultiplicityError(
            MultiplicityFailureCode.MOMENT_CONSTRAINT_INVALID,
            "forced impossible moments",
        )

    monkeypatch.setattr(
        OverfittingDiagnostics,
        "deflated_sharpe_ratio",
        staticmethod(reject_impossible_moments),
    )

    with pytest.raises(ModelingError) as captured:
        deflate_ridge_report(evaluation.ridge_report, multiplicity_count=1)

    assert captured.value.code is ModelingFailureCode.MOMENT_CONSTRAINT_INVALID
    assert isinstance(captured.value.__cause__, MultiplicityError)


def test_single_validation_decision_fails_closed_with_a_typed_code() -> None:
    """Red Team Minor 6: a one-period fold escaped as a raw ValueError."""
    journey = governed_training_journey()
    single = replace(
        journey.fold,
        validation_rows=journey.fold.validation_rows[:1],
        spec=replace(
            journey.fold.spec,
            validation_end=journey.fold.validation_rows[0].decision_at,
            validation_row_count=1,
            validation_class_balance=_class_balance(journey.fold.validation_rows[:1]),
            validation_hash=_rows_hash(journey.fold.validation_rows[:1]),
        ),
    )
    forged = rebound_journey(journey, single)

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            forged.start,
            forged.registry,
            forged.features,
            forged.labels,
            forged.fold,
        )

    assert captured.value.code in {
        ModelingFailureCode.PARTITION_INVALID,
        ModelingFailureCode.DEGENERATE_RETURN_SERIES,
    }


def test_two_instruments_sharing_one_symbol_fail_closed() -> None:
    """Red Team Major 3: a symbol join silently kept only the last instrument's features.

    Both datasets are rebound onto the poisoned feature identity, so the evaluator reaches the
    symbol join instead of stopping earlier at the dataset-identity check.
    """
    journey = governed_training_journey()
    poisoned, labels = symbol_collision_features(journey)
    start = replace(
        journey.start,
        dataset_id=labels.dataset_id,
        dataset_hash=labels.dataset_hash,
        universe_policy_hash=poisoned.universe_authority_hash,
    )
    registry = TrialRegistryV1(starts=(start,), outcomes=())

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(start, registry, poisoned, labels, journey.fold)

    assert captured.value.code is ModelingFailureCode.DATASET_INTEGRITY_INVALID
