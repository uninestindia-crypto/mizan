"""Evidence-store adapters that commit a trial start before governed fitting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from quant_system.evidence import (
    CommitResult,
    EvidenceDraft,
    EvidenceResourceType,
    EvidenceStore,
)
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.folds import PartitionedFoldV1
from quant_system.modeling.persisted_trials import (
    load_persisted_trial_registry,
    require_next_persisted_trial,
    require_resumable_persisted_trial,
)
from quant_system.modeling.rows import FeatureDatasetV1, LabelDatasetV1
from quant_system.modeling.trials import (
    RidgeTrialStartV1,
    TrialOutcomeV1,
    TrialState,
    succeeded_outcome,
    unsuccessful_outcome,
)
from quant_system.modeling.validation import (
    RidgeFoldEvaluationV1,
    evaluate_governed_ridge_fold,
)


@dataclass(frozen=True, slots=True)
class PersistedRidgeTrialV1:
    start_commit: CommitResult
    evaluation_commit: CommitResult
    outcome_commit: CommitResult
    evaluation: RidgeFoldEvaluationV1
    outcome: TrialOutcomeV1


def draft_from_trial_start(start: RidgeTrialStartV1) -> EvidenceDraft:
    return EvidenceDraft(
        resource_type=EvidenceResourceType.TRIAL,
        resource_id=start.trial_id,
        schema_id="quantos.ridge_trial_start",
        schema_version=1,
        metadata={
            "candidate_id": start.candidate_id,
            "dataset_hash": start.dataset_hash,
            "dataset_id": start.dataset_id,
            "parameter_hash": start.parameter_hash,
            "start_hash": start.start_hash,
        },
        records=(start.to_canonical_dict(),),
        total_order=("multiplicity_ordinal", "trial_id"),
    )


def draft_from_trial_outcome(outcome: TrialOutcomeV1) -> EvidenceDraft:
    return EvidenceDraft(
        resource_type=EvidenceResourceType.TRIAL,
        resource_id=outcome.resource_id,
        schema_id="quantos.trial_outcome",
        schema_version=1,
        metadata={
            "outcome_hash": outcome.outcome_hash,
            "start_hash": outcome.start_hash,
            "trial_id": outcome.trial_id,
        },
        records=(outcome.to_canonical_dict(),),
        total_order=("trial_id", "state"),
    )


def draft_from_ridge_evaluation(evaluation: RidgeFoldEvaluationV1) -> EvidenceDraft:
    records = _evaluation_records(evaluation)
    metadata: dict[str, Any] = {
        "candidate_id": evaluation.candidate_id,
        "deflated_sharpe_ratio": evaluation.deflated_sharpe_ratio,
        "evaluation_hash": evaluation.evaluation_hash,
        "fitted_state": evaluation.fitted_state.to_canonical_dict(),
        "fold_spec_hash": evaluation.fold_spec_hash,
        "model_id": evaluation.model_id,
        "multiplicity_count": evaluation.multiplicity_count,
        "preprocessing": evaluation.preprocessing.to_canonical_dict(),
        "strategy_reports": _strategy_report_summaries(evaluation),
        "trial_id": evaluation.trial_id,
        "verdict": "RESEARCH_ONLY",
    }
    return EvidenceDraft(
        resource_type=EvidenceResourceType.MODEL,
        resource_id=evaluation.model_id,
        schema_id="quantos.fold_strategy_decision",
        schema_version=1,
        metadata=metadata,
        records=records,
        total_order=("strategy_id", "decision_at", "symbol"),
    )


def _evaluation_records(evaluation: RidgeFoldEvaluationV1) -> tuple[dict[str, Any], ...]:
    records = (
        decision.to_canonical_dict()
        for report in evaluation.strategy_reports
        for decision in report.decisions
    )
    return tuple(
        sorted(
            records,
            key=lambda item: (item["strategy_id"], item["decision_at"], item["symbol"]),
        )
    )


def _strategy_report_summaries(evaluation: RidgeFoldEvaluationV1) -> list[dict[str, Any]]:
    return [
        {
            "metrics": report.metrics.to_canonical_dict(),
            "metrics_hash": report.metrics_hash,
            "prediction_hash": report.prediction_hash,
            "strategy_id": report.strategy_id,
        }
        for report in evaluation.strategy_reports
    ]


def run_persisted_ridge_trial(
    store: EvidenceStore,
    *,
    operation_id: str,
    start: RidgeTrialStartV1,
    feature_dataset: FeatureDatasetV1,
    label_dataset: LabelDatasetV1,
    fold: PartitionedFoldV1,
    ended_at: datetime,
) -> PersistedRidgeTrialV1:
    """Persist STARTED, fit/evaluate, then persist the model and terminal outcome."""
    if not operation_id or len(operation_id) > 96:
        raise ValueError("operation_id must contain 1-96 characters")
    if ended_at.tzinfo is None or ended_at.utcoffset() is None or ended_at < start.created_at:
        raise ModelingError(
            ModelingFailureCode.TRIAL_OUTCOME_INVALID,
            "terminal time must be timezone-aware and cannot precede the trial start",
        )
    start_commit = store.commit(
        draft_from_trial_start(start),
        operation_id=f"{operation_id}-start",
        precondition=lambda: require_next_persisted_trial(store, start),
        duplicate_precondition=lambda: require_resumable_persisted_trial(store, start),
    )
    try:
        registry = load_persisted_trial_registry(store)
        evaluation = evaluate_governed_ridge_fold(
            start,
            registry,
            feature_dataset,
            label_dataset,
            fold,
        )
        evaluation_commit = store.commit(
            draft_from_ridge_evaluation(evaluation),
            operation_id=f"{operation_id}-model",
        )
    except Exception as error:
        failure_code = (
            error.code.value
            if isinstance(error, ModelingError)
            else ModelingFailureCode.TRIAL_EXECUTION_FAILED.value
        )
        failed = unsuccessful_outcome(
            start,
            state=TrialState.FAILED,
            ended_at=ended_at,
            failure_codes=(failure_code,),
        )
        store.commit(
            draft_from_trial_outcome(failed),
            operation_id=f"{operation_id}-failed",
        )
        raise
    outcome = succeeded_outcome(
        start,
        ended_at=ended_at,
        result_hash=evaluation.evaluation_hash,
    )
    outcome_commit = store.commit(
        draft_from_trial_outcome(outcome),
        operation_id=f"{operation_id}-outcome",
    )
    return PersistedRidgeTrialV1(
        start_commit=start_commit,
        evaluation_commit=evaluation_commit,
        outcome_commit=outcome_commit,
        evaluation=evaluation,
        outcome=outcome,
    )
