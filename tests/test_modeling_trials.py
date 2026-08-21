"""Immutable trial lifecycle, multiplicity, and persistence tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quant_system.evidence import (
    EvidenceBusy,
    EvidenceNotFound,
    EvidenceResourceType,
    EvidenceStorageError,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    TrialRegistryV1,
    TrialState,
    draft_from_trial_outcome,
    draft_from_trial_start,
    evaluate_governed_ridge_fold,
    run_persisted_ridge_trial,
    succeeded_outcome,
    unsuccessful_outcome,
)
from quant_system.modeling.metrics import StrategyMetricsV1
from quant_system.modeling.persisted_trials import load_persisted_trial_registry
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


@pytest.mark.parametrize(
    ("field_name", "value"),
    (("numpy_seed", False), ("multiplicity_ordinal", True), ("feature_schema_version", True)),
)
def test_trial_integer_fields_reject_booleans(field_name: str, value: bool) -> None:
    with pytest.raises(ModelingError) as captured:
        replace(governed_training_journey().start, **{field_name: value})

    assert captured.value.code == ModelingFailureCode.TRIAL_INVALID


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


def test_success_without_verified_model_is_rejected(tmp_path: Path) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    store.commit(draft_from_trial_start(journey.start), operation_id="op-forged-start")
    forged = succeeded_outcome(journey.start, ended_at=ENDED_AT, result_hash="f" * 64)
    store.commit(draft_from_trial_outcome(forged), operation_id="op-forged-outcome")

    with pytest.raises(ModelingError) as captured:
        load_persisted_trial_registry(store)

    assert captured.value.code == ModelingFailureCode.MULTIPLICITY_INVALID


def test_alias_manifest_identity_is_rejected(tmp_path: Path) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    alias = replace(draft_from_trial_start(journey.start), resource_id="trial_alias_001")
    store.commit(alias, operation_id="op-alias-start")

    with pytest.raises(ModelingError) as captured:
        load_persisted_trial_registry(store)

    assert captured.value.code == ModelingFailureCode.MULTIPLICITY_INVALID


def test_model_commit_failure_terminalizes_attempt(tmp_path: Path, monkeypatch) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    original_commit = store.commit

    def fail_model(draft, **kwargs):
        if draft.resource_type == EvidenceResourceType.MODEL:
            raise EvidenceStorageError("injected model publication failure")
        return original_commit(draft, **kwargs)

    monkeypatch.setattr(store, "commit", fail_model)
    with pytest.raises(EvidenceStorageError):
        run_persisted_ridge_trial(
            store,
            operation_id="op-model-store-failure",
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=ENDED_AT,
        )
    monkeypatch.setattr(store, "commit", original_commit)

    outcome = store.open_verified(EvidenceResourceType.TRIAL, journey.start.outcome_resource_id)
    assert outcome.records[0]["state"] == "FAILED"
    assert outcome.records[0]["failure_codes"] == ["TRIAL_EXECUTION_FAILED"]

    next_start = replace(
        journey.start,
        trial_id="trial_ridge_002",
        multiplicity_ordinal=2,
        l2_penalty="2",
    )
    next_run = run_persisted_ridge_trial(
        store,
        operation_id="op-after-model-store-failure",
        start=next_start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )
    assert next_run.evaluation.multiplicity_count == 2


def test_outcome_commit_failure_can_resume_same_attempt(tmp_path: Path, monkeypatch) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    original_commit = store.commit

    def fail_outcome(draft, **kwargs):
        if draft.schema_id == "quantos.trial_outcome":
            raise EvidenceStorageError("injected outcome publication failure")
        return original_commit(draft, **kwargs)

    monkeypatch.setattr(store, "commit", fail_outcome)
    with pytest.raises(EvidenceStorageError):
        run_persisted_ridge_trial(
            store,
            operation_id="op-outcome-store-failure",
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=ENDED_AT,
        )
    monkeypatch.setattr(store, "commit", original_commit)

    with pytest.raises(EvidenceNotFound):
        store.open_verified(EvidenceResourceType.TRIAL, journey.start.outcome_resource_id)
    resumed = run_persisted_ridge_trial(
        store,
        operation_id="op-outcome-store-resume",
        start=journey.start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )
    assert resumed.start_commit.deduplicated is True
    assert resumed.evaluation_commit.deduplicated is True
    assert resumed.outcome.state == TrialState.SUCCEEDED


def test_start_only_interruption_can_resume_same_attempt(tmp_path: Path) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    store.commit(draft_from_trial_start(journey.start), operation_id="op-start-before-kill")

    resumed = run_persisted_ridge_trial(
        store,
        operation_id="op-start-after-restart",
        start=journey.start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )

    assert resumed.start_commit.deduplicated is True
    assert resumed.evaluation_commit.deduplicated is False
    assert resumed.outcome.state == TrialState.SUCCEEDED


def test_trial_id_colliding_with_a_derived_outcome_id_is_rejected() -> None:
    """Red Team Blocker 4: `trial_alpha_outcome` collides with `trial_alpha`'s outcome id."""
    with pytest.raises(ModelingError) as captured:
        replace(governed_training_journey().start, trial_id="trial_alpha_outcome")

    assert captured.value.code == ModelingFailureCode.TRIAL_INVALID


def test_reserved_outcome_suffix_cannot_deadlock_a_store(tmp_path: Path) -> None:
    """Red Team Blocker 4 blast radius: the store must stay usable after the rejection."""
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))

    with pytest.raises(ModelingError):
        replace(journey.start, trial_id="trial_alpha_outcome")

    run = run_persisted_ridge_trial(
        store,
        operation_id="op-after-rejection",
        start=replace(journey.start, trial_id="trial_alpha"),
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )

    assert run.outcome.state is TrialState.SUCCEEDED
    assert sorted(path.name for path in (tmp_path / "evidence" / "trials").iterdir()) == [
        "trial_alpha",
        "trial_alpha_outcome",
    ]
    assert load_persisted_trial_registry(store).multiplicity_count == 1


def test_failed_outcome_commit_failure_preserves_the_original_diagnosis(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Red Team Major 4: a failing FAILED-fallback replaced the real failure code.

    The caller was shown ``EvidenceBusy`` from the fallback commit while the actual reason the
    trial failed survived only on ``__context__``. The original error must reach the caller,
    carrying a note that says what state the store is now in.
    """
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    original_commit = store.commit

    def fail_model_and_fallback(draft, **kwargs):
        if draft.resource_type == EvidenceResourceType.MODEL:
            raise ModelingError(
                ModelingFailureCode.MODEL_FIT_FAILED,
                "injected fit failure",
            )
        if draft.schema_id == "quantos.trial_outcome":
            raise EvidenceBusy("evidence mutation is owned by op-other (pid 5284)")
        return original_commit(draft, **kwargs)

    monkeypatch.setattr(store, "commit", fail_model_and_fallback)

    with pytest.raises(ModelingError) as captured:
        run_persisted_ridge_trial(
            store,
            operation_id="op-lease-contention",
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=ENDED_AT,
        )

    assert captured.value.code is ModelingFailureCode.MODEL_FIT_FAILED
    notes = getattr(captured.value, "__notes__", [])
    assert any("remains open" in note for note in notes)
    assert any("replay" in note for note in notes)


@pytest.mark.parametrize(
    "field_name",
    ("ordinal", "embargo_sessions", "label_horizon_sessions", "train_row_count"),
)
def test_fold_spec_integer_fields_reject_booleans(field_name: str) -> None:
    """Red Team Minor 3: bool subclasses int, so True entered the fold spec hash as JSON true."""
    journey = governed_training_journey()

    with pytest.raises((ModelingError, ValueError)):
        replace(journey.fold.spec, **{field_name: True})


@pytest.mark.parametrize(
    "field_name",
    ("max_drawdown_duration_rows", "attributable_count", "trade_count"),
)
def test_strategy_metric_counts_reject_booleans(field_name: str) -> None:
    """Red Team Minor 3: the same gap in the published metric counts."""
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    with pytest.raises((ModelingError, ValueError)):
        replace(evaluation.ridge_report.metrics, **{field_name: True})


@pytest.mark.parametrize(
    "dataset_id",
    (
        "dset_" + "a" * 10_000,
        "dset_\u202eabc",
        "dset_a\u200bb",
        "dset_\U0001f600",
    ),
)
def test_trial_dataset_id_rejects_unbounded_and_deceptive_text(dataset_id: str) -> None:
    """Red Team Minor 5: zero-width and RTL text render identically but hash differently."""
    with pytest.raises(ModelingError) as captured:
        replace(governed_training_journey().start, dataset_id=dataset_id)

    assert captured.value.code == ModelingFailureCode.TRIAL_INVALID


def test_completed_trial_replay_says_where_to_read_the_result(tmp_path: Path) -> None:
    """Red Team Minor 1: a crash after the outcome published looked like a failure.

    Replaying the exact start of an already-successful trial raised
    ``TRIAL_ALREADY_RECORDED: terminal trial cannot be resumed``, which a caller cannot
    distinguish from a genuine failure and which does not say the result is already there.
    """
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))
    run = run_persisted_ridge_trial(
        store,
        operation_id="op-first",
        start=journey.start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )

    with pytest.raises(ModelingError) as captured:
        run_persisted_ridge_trial(
            store,
            operation_id="op-replay-after-crash",
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=ENDED_AT,
        )

    assert captured.value.code is ModelingFailureCode.TRIAL_ALREADY_RECORDED
    message = str(captured.value)
    assert "SUCCEEDED" in message
    assert run.evaluation.model_id in message


def test_sharpe_cannot_be_published_beside_a_volatility_that_rounds_to_zero() -> None:
    """Red Team Minor 4: the published ratio was unverifiable from the published inputs."""
    with pytest.raises(ValueError, match="volatility"):
        StrategyMetricsV1(
            accuracy="0.5",
            balanced_accuracy=None,
            total_return="0.000000000001",
            annualized_volatility="0",
            sharpe_ratio="14.849242404917",
            sortino_ratio="0",
            max_drawdown="0",
            max_drawdown_duration_rows=0,
            turnover="0",
            exposure="1",
            concentration="1",
            attributable_count=8,
            trade_count=8,
            hit_rate="1",
            profit_factor=None,
        )
