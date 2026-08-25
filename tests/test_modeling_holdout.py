"""Comprehensive tests for cryptographic single-use holdout unlocking and evaluation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.evidence import EvidenceStore, EvidenceStoreConfig
from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    evaluate_governed_holdout,
    evaluate_governed_ridge_fold,
)
from quant_system.modeling.holdout import (
    HoldoutEvaluationOutcomeV1,
    HoldoutEvaluationStartV1,
    HoldoutVaultTracker,
    create_holdout_partition,
    draft_from_holdout_outcome,
    draft_from_holdout_report,
    draft_from_holdout_start,
)
from tests.modeling_training_fixtures import governed_training_journey


def test_holdout_partition_creation_and_integrity() -> None:
    journey = governed_training_journey()
    calendar = journey.calendar

    holdout_start = calendar.sessions[48].close_at
    holdout_end = calendar.sessions[52].close_at

    partition, token = create_holdout_partition(
        journey.labels,
        journey.features,
        calendar,
        holdout_id="holdout_journey_001",
        holdout_start=holdout_start,
        holdout_end=holdout_end,
        embargo_sessions=2,
    )

    assert partition.spec.holdout_id == "holdout_journey_001"
    assert partition.spec.candidate_id == journey.features.candidate_id
    assert len(partition.discovery_rows) > 0
    assert len(partition.holdout_rows) > 0
    assert partition.spec.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()

    # Verify disjointness
    disc_keys = {r.record_key for r in partition.discovery_rows}
    hold_keys = {r.record_key for r in partition.holdout_rows}
    assert disc_keys.isdisjoint(hold_keys)


def test_holdout_unlock_and_evaluation_success(tmp_path: Path) -> None:
    journey = governed_training_journey()
    calendar = journey.calendar

    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    holdout_start = calendar.sessions[48].close_at
    holdout_end = calendar.sessions[52].close_at

    partition, token = create_holdout_partition(
        journey.labels,
        journey.features,
        calendar,
        holdout_id="holdout_test_001",
        holdout_start=holdout_start,
        holdout_end=holdout_end,
    )

    tracker = HoldoutVaultTracker(_vault_store(tmp_path / "evidence"))
    report = evaluate_governed_holdout(
        partition,
        token,
        tracker,
        evaluation,
        journey.features,
        journey.labels,
        multiplicity_count=1,
        evaluation_id="holdout_eval_test_001",
    )

    assert report.holdout_id == "holdout_test_001"
    assert report.candidate_id == journey.features.candidate_id
    assert report.model_id == evaluation.model_id
    assert len(report.strategy_reports) == 5
    assert report.ridge_report.strategy_id == "RIDGE"
    assert Decimal(report.deflated_sharpe_ratio).is_finite()
    assert tracker.is_consumed("holdout_test_001")


def test_holdout_second_access_raises_already_consumed(tmp_path: Path) -> None:
    journey = governed_training_journey()
    calendar = journey.calendar

    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    holdout_start = calendar.sessions[48].close_at
    holdout_end = calendar.sessions[52].close_at

    partition, token = create_holdout_partition(
        journey.labels,
        journey.features,
        calendar,
        holdout_id="holdout_single_use_001",
        holdout_start=holdout_start,
        holdout_end=holdout_end,
    )

    tracker = HoldoutVaultTracker(_vault_store(tmp_path / "evidence"))

    # First unlock: SUCCEEDS
    evaluate_governed_holdout(
        partition,
        token,
        tracker,
        evaluation,
        journey.features,
        journey.labels,
        multiplicity_count=1,
        evaluation_id="holdout_eval_su_001",
    )

    # Second unlock attempt with same holdout: MUST RAISE HOLDOUT_ALREADY_CONSUMED
    with pytest.raises(ModelingError) as exc_info:
        evaluate_governed_holdout(
            partition,
            token,
            tracker,
            evaluation,
            journey.features,
            journey.labels,
            multiplicity_count=1,
            evaluation_id="holdout_eval_su_002",
        )

    assert exc_info.value.code == ModelingFailureCode.HOLDOUT_ALREADY_CONSUMED
    assert "already been unlocked and consumed" in str(exc_info.value)


def test_holdout_invalid_token_rejected(tmp_path: Path) -> None:
    journey = governed_training_journey()
    calendar = journey.calendar

    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    holdout_start = calendar.sessions[48].close_at
    holdout_end = calendar.sessions[52].close_at

    partition, _correct_token = create_holdout_partition(
        journey.labels,
        journey.features,
        calendar,
        holdout_id="holdout_token_check_001",
        holdout_start=holdout_start,
        holdout_end=holdout_end,
    )

    tracker = HoldoutVaultTracker(_vault_store(tmp_path / "evidence"))
    wrong_token = "invalid_token_hex_000000000000000000000000000000000000000000000000"

    with pytest.raises(ModelingError) as exc_info:
        evaluate_governed_holdout(
            partition,
            wrong_token,
            tracker,
            evaluation,
            journey.features,
            journey.labels,
            multiplicity_count=1,
            evaluation_id="holdout_eval_tc_001",
        )

    assert exc_info.value.code == ModelingFailureCode.HOLDOUT_TOKEN_INVALID
    assert "does not match cryptographic token hash" in str(exc_info.value)


def test_holdout_evidence_draft_generation(tmp_path: Path) -> None:
    journey = governed_training_journey()
    calendar = journey.calendar

    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    holdout_start = calendar.sessions[48].close_at
    holdout_end = calendar.sessions[52].close_at

    partition, token = create_holdout_partition(
        journey.labels,
        journey.features,
        calendar,
        holdout_id="holdout_draft_001",
        holdout_start=holdout_start,
        holdout_end=holdout_end,
    )

    tracker = HoldoutVaultTracker(_vault_store(tmp_path / "evidence"))
    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)

    report = evaluate_governed_holdout(
        partition,
        token,
        tracker,
        evaluation,
        journey.features,
        journey.labels,
        multiplicity_count=1,
        evaluation_id="holdout_eval_draft_001",
        evaluated_at=now,
    )

    start = HoldoutEvaluationStartV1(
        evaluation_id="holdout_eval_draft_001",
        holdout_id=partition.spec.holdout_id,
        candidate_id=evaluation.candidate_id,
        model_id=evaluation.model_id,
        trial_id=evaluation.trial_id,
        started_at=now,
        token_hash=partition.spec.token_hash,
    )
    start_draft = draft_from_holdout_start(start)
    assert start_draft.schema_id == "quantos.holdout_evaluation_start"
    assert start_draft.metadata["candidate_id"] == evaluation.candidate_id

    outcome = HoldoutEvaluationOutcomeV1(
        evaluation_id="holdout_eval_draft_001",
        start_hash=start.start_hash,
        state="SUCCEEDED",
        ended_at=now,
        result_hash=report.report_hash,
        failure_codes=(),
    )
    outcome_draft = draft_from_holdout_outcome(outcome)
    assert outcome_draft.schema_id == "quantos.holdout_evaluation_outcome"
    assert outcome_draft.metadata["state"] == "SUCCEEDED"

    report_draft = draft_from_holdout_report(report)
    assert report_draft.schema_id == "quantos.holdout_strategy_decision"
    assert len(report_draft.records) > 0


# -------------------------------------------------------------------------
# Ring 5: H-2 regression — single use must survive a new tracker
# -------------------------------------------------------------------------


def _vault_store(root: Path) -> EvidenceStore:
    return EvidenceStore(
        EvidenceStoreConfig(
            root=root,
            chunk_uncompressed_bytes=1024,
            max_bundle_bytes=8192,
            min_free_bytes=0,
            clock=lambda: datetime(2026, 8, 22, tzinfo=UTC),
        )
    )


def test_holdout_single_use_survives_a_new_tracker(tmp_path: Path) -> None:
    """H-2: vault state was in-memory only, so a second tracker reopened a consumed holdout.

    Unlimited re-use turns a final holdout into a second validation set, which is the most
    direct way this system could manufacture a false positive.
    """
    store = _vault_store(tmp_path / "evidence")
    journey = governed_training_journey()
    calendar = journey.calendar

    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )
    partition, token = create_holdout_partition(
        journey.labels,
        journey.features,
        calendar,
        holdout_id="holdout_durable_001",
        holdout_start=calendar.sessions[48].close_at,
        holdout_end=calendar.sessions[52].close_at,
    )

    evaluate_governed_holdout(
        partition,
        token,
        HoldoutVaultTracker(store),
        evaluation,
        journey.features,
        journey.labels,
        multiplicity_count=1,
        evaluation_id="holdout_eval_durable_001",
    )

    # A brand new tracker over the SAME store. This is the defeat the finding describes.
    fresh = HoldoutVaultTracker(store)
    assert fresh.is_consumed("holdout_durable_001"), (
        "a new tracker must see prior consumption; vault state cannot be in-memory only"
    )

    with pytest.raises(ModelingError) as excinfo:
        evaluate_governed_holdout(
            partition,
            token,
            fresh,
            evaluation,
            journey.features,
            journey.labels,
            multiplicity_count=1,
            evaluation_id="holdout_eval_durable_002",
        )
    assert excinfo.value.code == ModelingFailureCode.HOLDOUT_ALREADY_CONSUMED


def test_holdout_vault_requires_a_durable_store(tmp_path: Path) -> None:
    """H-2: an optional store would leave the default construction exactly as unsafe."""
    with pytest.raises(TypeError):
        HoldoutVaultTracker()  # type: ignore[call-arg]


def test_a_failed_consumption_commit_leaves_the_holdout_unconsumed(tmp_path: Path) -> None:
    """H-2 durability: the vault must never believe a use it failed to record.

    `record_start` publishes to the store *before* mutating memory, and a comment claims that a
    failed commit therefore leaves nothing marked consumed. That claim shipped without a test,
    which an independent reviewer identified as the weakest part of the change. If the ordering
    were reversed, a crash mid-publish would burn the holdout: memory would refuse a second
    unlock while the store held no record of the first, so the single most important governance
    property would fail closed in the wrong direction — unusable rather than protected.
    """
    store = _vault_store(tmp_path / "evidence")
    tracker = HoldoutVaultTracker(store)

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated store failure during consumption publish")

    tracker._store.commit = _refuse  # type: ignore[method-assign]

    start = HoldoutEvaluationStartV1(
        evaluation_id="holdout_eval_durability_001",
        holdout_id="holdout_durability_001",
        candidate_id="cand_ridge_v1",
        model_id="model_durability_0001",
        trial_id="trial_durability_001",
        started_at=datetime(2026, 8, 25, tzinfo=UTC),
        token_hash="a" * 64,
    )

    with pytest.raises(RuntimeError, match="simulated store failure"):
        tracker.record_start(start)

    assert tracker.is_consumed("holdout_durability_001") is False, (
        "the vault marked a holdout consumed after the durable record failed to publish"
    )
    assert tracker.is_token_consumed("a" * 64) is False

    # And a fresh tracker over the same store must agree: nothing was ever recorded.
    assert HoldoutVaultTracker(store).is_consumed("holdout_durability_001") is False
