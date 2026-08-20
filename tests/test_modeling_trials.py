"""Immutable trial lifecycle, multiplicity, and persistence tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quant_system.evidence import (
    EvidenceNotFound,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    TrialRegistryV1,
    TrialState,
    evaluate_governed_ridge_fold,
    run_persisted_ridge_trial,
    succeeded_outcome,
    unsuccessful_outcome,
)
from tests.modeling_training_fixtures import governed_training_journey

ENDED_AT = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)


def test_registry_counts_success_failure_cancel_and_abandonment() -> None:
    first = governed_training_journey().start
    second = replace(first, trial_id="trial_ridge_002", multiplicity_ordinal=2)
    third = replace(first, trial_id="trial_ridge_003", multiplicity_ordinal=3)
    fourth = replace(first, trial_id="trial_ridge_004", multiplicity_ordinal=4)
    outcomes = (
        succeeded_outcome(first, ended_at=ENDED_AT, result_hash="b" * 64),
        unsuccessful_outcome(
            second,
            state=TrialState.FAILED,
            ended_at=ENDED_AT,
            failure_codes=("MODEL_FIT_FAILED",),
        ),
        unsuccessful_outcome(
            third,
            state=TrialState.CANCELLED,
            ended_at=ENDED_AT,
            failure_codes=("USER_CANCELLED",),
        ),
        unsuccessful_outcome(
            fourth,
            state=TrialState.ABANDONED,
            ended_at=ENDED_AT,
            failure_codes=("MANUAL_REVIEW_ABANDONED",),
        ),
    )

    registry = TrialRegistryV1(starts=(first, second, third, fourth), outcomes=outcomes)

    assert registry.multiplicity_count == 4
    assert {outcome.state for outcome in registry.outcomes} == {
        TrialState.SUCCEEDED,
        TrialState.FAILED,
        TrialState.CANCELLED,
        TrialState.ABANDONED,
    }


def test_registry_rejects_duplicate_ordinals_and_mismatched_outcomes() -> None:
    first = governed_training_journey().start
    duplicate = replace(first, trial_id="trial_ridge_002")
    unrelated = replace(first, trial_id="trial_ridge_999", multiplicity_ordinal=9)
    outcome = unsuccessful_outcome(
        unrelated,
        state=TrialState.FAILED,
        ended_at=ENDED_AT,
        failure_codes=("MODEL_FIT_FAILED",),
    )

    with pytest.raises(ModelingError) as duplicate_error:
        TrialRegistryV1(starts=(first, duplicate), outcomes=())
    with pytest.raises(ModelingError) as mismatch_error:
        TrialRegistryV1(starts=(first,), outcomes=(outcome,))

    assert duplicate_error.value.code == ModelingFailureCode.MULTIPLICITY_INVALID
    assert mismatch_error.value.code == ModelingFailureCode.MULTIPLICITY_INVALID


def test_registry_rejects_gapped_ordinals_and_outcomes_before_start() -> None:
    first = governed_training_journey().start
    gapped = replace(first, trial_id="trial_ridge_002", multiplicity_ordinal=3)
    early = unsuccessful_outcome(
        first,
        state=TrialState.FAILED,
        ended_at=first.created_at - timedelta(seconds=1),
        failure_codes=("MODEL_FIT_FAILED",),
    )

    with pytest.raises(ModelingError) as ordinal_error:
        TrialRegistryV1(starts=(first, gapped), outcomes=())
    with pytest.raises(ModelingError) as chronology_error:
        TrialRegistryV1(starts=(first,), outcomes=(early,))

    assert ordinal_error.value.code == ModelingFailureCode.MULTIPLICITY_INVALID
    assert chronology_error.value.code == ModelingFailureCode.MULTIPLICITY_INVALID


def test_evaluation_requires_every_prior_attempt_to_have_terminal_outcome() -> None:
    journey = governed_training_journey()
    prior = replace(journey.start, trial_id="trial_ridge_prior", multiplicity_ordinal=1)
    current = replace(journey.start, multiplicity_ordinal=2)
    registry = TrialRegistryV1(starts=(prior, current), outcomes=())

    with pytest.raises(ModelingError) as captured:
        evaluate_governed_ridge_fold(
            current,
            registry,
            journey.features,
            journey.labels,
            journey.fold,
        )

    assert captured.value.code == ModelingFailureCode.MULTIPLICITY_INVALID


def test_trial_parameters_reject_zero_noncanonical_and_nonfixed_seed() -> None:
    start = governed_training_journey().start

    with pytest.raises(ModelingError) as zero_l2:
        replace(start, l2_penalty="0")
    with pytest.raises(ModelingError) as noncanonical_l2:
        replace(start, l2_penalty="1.0")
    with pytest.raises(ModelingError) as nonfinite_threshold:
        replace(start, score_threshold="NaN")
    with pytest.raises(ModelingError) as nonfixed_seed:
        replace(start, numpy_seed=1)

    assert zero_l2.value.code == ModelingFailureCode.INVALID_PARAMETER
    assert noncanonical_l2.value.code == ModelingFailureCode.INVALID_PARAMETER
    assert nonfinite_threshold.value.code == ModelingFailureCode.INVALID_PARAMETER
    assert nonfixed_seed.value.code == ModelingFailureCode.TRIAL_INVALID


def test_registry_counts_prior_trials_across_governed_search_identities() -> None:
    first = governed_training_journey().start
    mismatched = replace(
        first,
        trial_id="trial_ridge_002",
        dataset_hash="f" * 64,
        multiplicity_ordinal=2,
    )

    registry = TrialRegistryV1(starts=(first, mismatched), outcomes=())

    assert registry.multiplicity_count == 2


def test_persisted_success_commits_start_model_and_outcome(tmp_path: Path) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))

    run = run_persisted_ridge_trial(
        store,
        operation_id="op-slice4-success",
        start=journey.start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )

    stored_start = store.open_verified(EvidenceResourceType.TRIAL, journey.start.trial_id)
    stored_model = store.open_verified(EvidenceResourceType.MODEL, run.evaluation.model_id)
    stored_outcome = store.open_verified(
        EvidenceResourceType.TRIAL,
        journey.start.outcome_resource_id,
    )
    assert stored_start.records[0]["state"] == "STARTED"
    assert stored_model.manifest.metadata["evaluation_hash"] == run.evaluation.evaluation_hash
    assert stored_outcome.records[0]["state"] == "SUCCEEDED"
    assert run.outcome.result_hash == run.evaluation.evaluation_hash


def test_failure_still_persists_start_and_typed_terminal_outcome(tmp_path: Path) -> None:
    journey = governed_training_journey()
    invalid = replace(journey.start, dataset_hash="f" * 64)
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))

    with pytest.raises(ModelingError) as captured:
        run_persisted_ridge_trial(
            store,
            operation_id="op-slice4-failure",
            start=invalid,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=ENDED_AT,
        )

    stored_start = store.open_verified(EvidenceResourceType.TRIAL, invalid.trial_id)
    stored_outcome = store.open_verified(
        EvidenceResourceType.TRIAL,
        invalid.outcome_resource_id,
    )
    assert captured.value.code == ModelingFailureCode.TRAINING_INPUT_MISMATCH
    assert stored_start.records[0]["state"] == "STARTED"
    assert stored_outcome.records[0]["state"] == "FAILED"
    assert stored_outcome.records[0]["failure_codes"] == ["TRAINING_INPUT_MISMATCH"]


def test_duplicate_trial_start_never_refits_or_creates_second_outcome(tmp_path: Path) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    first = run_persisted_ridge_trial(
        store,
        operation_id="op-slice4-duplicate",
        start=journey.start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )

    with pytest.raises(ModelingError) as captured:
        run_persisted_ridge_trial(
            store,
            operation_id="op-slice4-duplicate",
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=ENDED_AT,
        )

    assert first.outcome.state == TrialState.SUCCEEDED
    assert captured.value.code == ModelingFailureCode.TRIAL_ALREADY_RECORDED


def test_persistence_rejects_terminal_time_before_trial_start(tmp_path: Path) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))

    with pytest.raises(ModelingError) as captured:
        run_persisted_ridge_trial(
            store,
            operation_id="op-slice4-time",
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=journey.start.created_at - timedelta(seconds=1),
        )

    assert captured.value.code == ModelingFailureCode.TRIAL_OUTCOME_INVALID


def test_persisted_history_blocks_multiplicity_reset(tmp_path: Path) -> None:
    first = governed_training_journey()
    reset = governed_training_journey(trial_id="trial_ridge_002")
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    first_run = run_persisted_ridge_trial(
        store,
        operation_id="op-slice4-first",
        start=first.start,
        feature_dataset=first.features,
        label_dataset=first.labels,
        fold=first.fold,
        ended_at=ENDED_AT,
    )
    assert first_run.evaluation.multiplicity_count == 1

    with pytest.raises(ModelingError) as captured:
        run_persisted_ridge_trial(
            store,
            operation_id="op-slice4-reset",
            start=reset.start,
            feature_dataset=reset.features,
            label_dataset=reset.labels,
            fold=reset.fold,
            ended_at=ENDED_AT,
        )

    assert captured.value.code == ModelingFailureCode.MULTIPLICITY_INVALID
    with pytest.raises(EvidenceNotFound):
        store.open_verified(EvidenceResourceType.TRIAL, reset.start.trial_id)

    # A materially different parameter search must still inherit the persisted
    # global multiplicity count; it cannot begin a fresh local search.
    legitimate = replace(
        reset.start,
        l2_penalty="2",
        multiplicity_ordinal=2,
    )
    second = run_persisted_ridge_trial(
        store,
        operation_id="op-slice4-second",
        start=legitimate,
        feature_dataset=reset.features,
        label_dataset=reset.labels,
        fold=reset.fold,
        ended_at=ENDED_AT,
    )

    assert second.evaluation.multiplicity_count == 2
