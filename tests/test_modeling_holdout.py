"""Comprehensive tests for cryptographic single-use holdout unlocking and evaluation."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest

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


def test_holdout_unlock_and_evaluation_success() -> None:
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

    tracker = HoldoutVaultTracker()
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


def test_holdout_second_access_raises_already_consumed() -> None:
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

    tracker = HoldoutVaultTracker()

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


def test_holdout_invalid_token_rejected() -> None:
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

    tracker = HoldoutVaultTracker()
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


def test_holdout_evidence_draft_generation() -> None:
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

    tracker = HoldoutVaultTracker()
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
