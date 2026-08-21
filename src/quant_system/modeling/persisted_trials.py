"""Rebuild complete trial multiplicity from verified immutable evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.evidence import EvidenceResourceType, EvidenceStore, VerifiedEvidence
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.metrics import (
    ALLOCATION_CONTRACT_V1,
    strategy_report_from_records,
)
from quant_system.modeling.trials import (
    RidgeTrialStartV1,
    TrialOutcomeV1,
    TrialRegistryV1,
    TrialState,
)
from quant_system.modeling.validation import deflate_ridge_report

_START_SCHEMA = "quantos.ridge_trial_start"
_OUTCOME_SCHEMA = "quantos.trial_outcome"
_MODEL_SCHEMA = "quantos.fold_strategy_decision"
_START_METADATA_KEYS = {
    "candidate_id",
    "dataset_hash",
    "dataset_id",
    "parameter_hash",
    "start_hash",
}
_RIDGE_STRATEGY = "RIDGE"
_OUTCOME_METADATA_KEYS = {"outcome_hash", "start_hash", "trial_id"}
_MODEL_METADATA_KEYS = {
    "candidate_id",
    "deflated_sharpe_ratio",
    "evaluation_hash",
    "fitted_state",
    "fold_spec_hash",
    "model_id",
    "multiplicity_count",
    "preprocessing",
    "strategy_reports",
    "trial_id",
    "verdict",
}


def load_persisted_trial_registry(store: EvidenceStore) -> TrialRegistryV1:
    starts, outcomes = _load_trial_records(store)
    if not starts:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "persisted trial registry contains no immutable starts",
        )
    return TrialRegistryV1(
        starts=tuple(sorted(starts, key=lambda start: start.multiplicity_ordinal)),
        outcomes=tuple(sorted(outcomes, key=lambda outcome: outcome.trial_id)),
    )


def campaign_deflated_sharpe_ratios(store: EvidenceStore) -> dict[str, str]:
    """Re-deflate every published model against the complete immutable attempt count.

    Each model publishes a deflated Sharpe computed against its own ordinal, because the
    campaign was still open when that evidence was written and immutable evidence cannot be
    rewritten afterwards. Reading the published number alone therefore overstates every early
    attempt in a finished sweep. This recomputes each one against the final attempt count,
    from the published decisions, without modifying any stored resource.
    """
    registry = load_persisted_trial_registry(store)
    multiplicity_count = registry.multiplicity_count
    deflations: dict[str, str] = {}
    for evidence in store.list_verified(EvidenceResourceType.MODEL):
        trial_id = _text(evidence.manifest.metadata, "trial_id")
        decisions = tuple(
            record for record in evidence.records if record.get("strategy_id") == _RIDGE_STRATEGY
        )
        ridge_report = strategy_report_from_records(_RIDGE_STRATEGY, decisions)
        deflations[trial_id] = deflate_ridge_report(
            ridge_report,
            multiplicity_count=multiplicity_count,
        )
    return deflations


def require_next_persisted_trial(store: EvidenceStore, start: RidgeTrialStartV1) -> None:
    """Atomic commit precondition: prior persisted trials are terminal and ordinal is next."""
    starts, outcomes = _load_trial_records(store)
    expected_ordinal = len(starts) + 1
    if start.multiplicity_ordinal != expected_ordinal:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            f"trial ordinal must be {expected_ordinal} from persisted history",
        )
    if not starts:
        return
    registry = TrialRegistryV1(
        starts=tuple(sorted(starts, key=lambda item: item.multiplicity_ordinal)),
        outcomes=tuple(sorted(outcomes, key=lambda item: item.trial_id)),
    )
    if {outcome.trial_id for outcome in registry.outcomes} != {
        prior.trial_id for prior in registry.starts
    }:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "every persisted prior trial needs one terminal outcome before another start",
        )


def require_resumable_persisted_trial(store: EvidenceStore, start: RidgeTrialStartV1) -> None:
    """Atomic duplicate precondition: only the latest exact open start may resume."""
    starts, outcomes = _load_trial_records(store)
    ordered = tuple(sorted(starts, key=lambda item: item.multiplicity_ordinal))
    matching = tuple(item for item in ordered if item.start_hash == start.start_hash)
    if len(matching) != 1 or not ordered or ordered[-1].start_hash != start.start_hash:
        raise ModelingError(
            ModelingFailureCode.TRIAL_ALREADY_RECORDED,
            "duplicate trial start is not the latest exact resumable attempt",
        )
    terminal = next(
        (outcome for outcome in outcomes if outcome.trial_id == start.trial_id),
        None,
    )
    if terminal is not None:
        raise ModelingError(
            ModelingFailureCode.TRIAL_ALREADY_RECORDED,
            _terminal_trial_message(terminal),
        )
    TrialRegistryV1(starts=ordered, outcomes=tuple(outcomes)).require_ready_for_evaluation(start)


def _terminal_trial_message(outcome: TrialOutcomeV1) -> str:
    """Explain that a trial is already complete and, on success, where its result lives."""
    detail = (
        f"trial {outcome.trial_id} is already terminal in state {outcome.state.value} "
        "and cannot be resumed"
    )
    if outcome.state is TrialState.SUCCEEDED and outcome.result_hash is not None:
        detail = f"{detail}; its result is published as models/model_{outcome.result_hash[:24]}"
    return detail


def _load_trial_records(
    store: EvidenceStore,
) -> tuple[list[RidgeTrialStartV1], list[TrialOutcomeV1]]:
    starts: list[RidgeTrialStartV1] = []
    outcomes: list[TrialOutcomeV1] = []
    for evidence in store.list_verified(EvidenceResourceType.TRIAL):
        if evidence.manifest.schema_id == _START_SCHEMA:
            starts.append(_parse_start(evidence))
            continue
        if evidence.manifest.schema_id == _OUTCOME_SCHEMA:
            outcomes.append(_parse_outcome(evidence))
            continue
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            f"unsupported persisted trial schema: {evidence.manifest.schema_id}",
        )
    _require_success_model_evidence(store, starts, outcomes)
    return starts, outcomes


def _parse_start(evidence: VerifiedEvidence) -> RidgeTrialStartV1:
    record = _single_record(evidence)
    try:
        parameters = _mapping(record, "parameters")
        start = RidgeTrialStartV1(
            trial_id=_text(record, "trial_id"),
            candidate_id=_text(record, "candidate_id"),
            created_at=_timestamp(record, "created_at"),
            dataset_id=_text(record, "dataset_id"),
            dataset_hash=_text(record, "dataset_hash"),
            universe_policy_hash=_text(record, "universe_policy_hash"),
            l2_penalty=_text(parameters, "l2_penalty"),
            score_threshold=_text(parameters, "score_threshold"),
            numpy_seed=_integer(parameters, "numpy_seed"),
            fold_spec_hashes=_text_tuple(record, "fold_spec_hashes"),
            source_revision=_text(record, "source_revision"),
            environment_lock_hash=_text(record, "environment_lock_hash"),
            architecture=_text(record, "architecture"),
            multiplicity_ordinal=_integer(record, "multiplicity_ordinal"),
            model_family=_text(record, "model_family"),
            model_contract_version=_text(record, "model_contract_version"),
            feature_schema_id=_text(record, "feature_schema_id"),
            feature_schema_version=_integer(record, "feature_schema_version"),
            label_contract_version=_text(record, "label_contract_version"),
        )
    except (KeyError, TypeError, ValueError, ArithmeticError, ModelingError) as error:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "persisted trial start is not valid canonical v1 evidence",
        ) from error
    if start.to_canonical_dict() != record:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "persisted trial start does not match its derived identity",
        )
    _require_start_manifest(evidence, start)
    return start


def _require_start_manifest(evidence: VerifiedEvidence, start: RidgeTrialStartV1) -> None:
    expected_metadata = {
        "candidate_id": start.candidate_id,
        "dataset_hash": start.dataset_hash,
        "dataset_id": start.dataset_id,
        "parameter_hash": start.parameter_hash,
        "start_hash": start.start_hash,
    }
    if (
        evidence.manifest.resource_id != start.trial_id
        or evidence.manifest.schema_version != 1
        or evidence.manifest.total_order != ("multiplicity_ordinal", "trial_id")
        or set(evidence.manifest.metadata) != _START_METADATA_KEYS
        or evidence.manifest.metadata != expected_metadata
    ):
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "persisted trial start manifest does not bind its canonical record",
        )


def _parse_outcome(evidence: VerifiedEvidence) -> TrialOutcomeV1:
    record = _single_record(evidence)
    try:
        state = TrialState(_text(record, "state"))
        outcome = TrialOutcomeV1(
            trial_id=_text(record, "trial_id"),
            start_hash=_text(record, "start_hash"),
            state=state,
            ended_at=_timestamp(record, "ended_at"),
            result_hash=_optional_text(record, "result_hash"),
            failure_codes=_text_tuple(record, "failure_codes"),
        )
    except (KeyError, TypeError, ValueError, ArithmeticError, ModelingError) as error:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "persisted trial outcome is not valid canonical v1 evidence",
        ) from error
    if outcome.to_canonical_dict() != record:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "persisted trial outcome does not match its derived identity",
        )
    expected_metadata = {
        "outcome_hash": outcome.outcome_hash,
        "start_hash": outcome.start_hash,
        "trial_id": outcome.trial_id,
    }
    if (
        evidence.manifest.resource_id != outcome.resource_id
        or evidence.manifest.schema_version != 1
        or evidence.manifest.total_order != ("trial_id", "state")
        or set(evidence.manifest.metadata) != _OUTCOME_METADATA_KEYS
        or evidence.manifest.metadata != expected_metadata
    ):
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "persisted trial outcome manifest does not bind its canonical record",
        )
    return outcome


def _require_success_model_evidence(
    store: EvidenceStore,
    starts: list[RidgeTrialStartV1],
    outcomes: list[TrialOutcomeV1],
) -> None:
    successful = tuple(outcome for outcome in outcomes if outcome.state == TrialState.SUCCEEDED)
    if not successful:
        return
    starts_by_id = {start.trial_id: start for start in starts}
    links = tuple(
        _parse_model_link(evidence, starts_by_id)
        for evidence in store.list_verified(EvidenceResourceType.MODEL)
    )
    for outcome in successful:
        expected = (outcome.trial_id, outcome.result_hash)
        if sum(link == expected for link in links) != 1:
            raise ModelingError(
                ModelingFailureCode.MULTIPLICITY_INVALID,
                "successful trial outcome must resolve to exactly one verified model evaluation",
            )


def _parse_model_link(
    evidence: VerifiedEvidence,
    starts_by_id: dict[str, RidgeTrialStartV1],
) -> tuple[str, str]:
    manifest = evidence.manifest
    metadata = manifest.metadata
    try:
        if (
            manifest.schema_id != _MODEL_SCHEMA
            or manifest.schema_version != 1
            or manifest.total_order != ("strategy_id", "decision_at", "symbol")
            or set(metadata) != _MODEL_METADATA_KEYS
        ):
            raise ValueError("model manifest contract mismatch")
        trial_id = _text(metadata, "trial_id")
        evaluation_hash = _text(metadata, "evaluation_hash")
        model_id = _text(metadata, "model_id")
        start = starts_by_id[trial_id]
        if (
            manifest.resource_id != model_id
            or model_id != f"model_{evaluation_hash[:24]}"
            or _text(metadata, "candidate_id") != start.candidate_id
            or _text(metadata, "fold_spec_hash") not in start.fold_spec_hashes
            or _integer(metadata, "multiplicity_count") != start.multiplicity_ordinal
            or _text(metadata, "verdict") != "RESEARCH_ONLY"
        ):
            raise ValueError("model identity does not bind its trial")
        reports = _rebuild_strategy_reports(evidence, metadata)
        unsigned_evaluation = {
            "candidate_id": start.candidate_id,
            "deflated_sharpe_ratio": _text(metadata, "deflated_sharpe_ratio"),
            "fitted_state": dict(_mapping(metadata, "fitted_state")),
            "fold_spec_hash": _text(metadata, "fold_spec_hash"),
            "multiplicity_count": _integer(metadata, "multiplicity_count"),
            "preprocessing": dict(_mapping(metadata, "preprocessing")),
            "schema_id": "quantos.ridge_fold_evaluation",
            "schema_version": 1,
            "strategy_reports": reports,
            "trial_id": trial_id,
            "verdict": "RESEARCH_ONLY",
        }
        if canonical_sha256(unsigned_evaluation) != evaluation_hash:
            raise ValueError("evaluation content hash mismatch")
    except (KeyError, TypeError, ValueError) as error:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "persisted model evidence does not bind one canonical trial evaluation",
        ) from error
    return trial_id, evaluation_hash


def _rebuild_strategy_reports(
    evidence: VerifiedEvidence,
    metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    summaries = metadata["strategy_reports"]
    if not isinstance(summaries, list):
        raise TypeError("strategy_reports must be a list")
    reports: list[dict[str, Any]] = []
    assigned = 0
    for summary in summaries:
        if not isinstance(summary, dict) or set(summary) != {
            "metrics",
            "metrics_hash",
            "prediction_hash",
            "strategy_id",
        }:
            raise TypeError("strategy report summary is invalid")
        strategy_id = _text(summary, "strategy_id")
        decisions = [
            record for record in evidence.records if record.get("strategy_id") == strategy_id
        ]
        assigned += len(decisions)
        rederived = strategy_report_from_records(strategy_id, tuple(decisions)).to_canonical_dict()
        claimed = {
            "allocation_contract": ALLOCATION_CONTRACT_V1,
            "decisions": decisions,
            "metrics": dict(_mapping(summary, "metrics")),
            "metrics_hash": _text(summary, "metrics_hash"),
            "prediction_hash": _text(summary, "prediction_hash"),
            "strategy_id": strategy_id,
        }
        if canonical_sha256(rederived) != canonical_sha256(claimed):
            raise ValueError("published strategy summary does not bind its decision records")
        reports.append(rederived)
    if assigned != len(evidence.records):
        raise ValueError("model decisions do not match strategy summaries")
    return reports


def _single_record(evidence: VerifiedEvidence) -> dict[str, Any]:
    if len(evidence.records) != 1:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "each immutable trial resource must contain exactly one record",
        )
    return evidence.records[0]


def _mapping(record: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = record[name]
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be an object")
    return value


def _text(record: Mapping[str, Any], name: str) -> str:
    value = record[name]
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text")
    return value


def _optional_text(record: Mapping[str, Any], name: str) -> str | None:
    value = record[name]
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{name} must be text or null")
    return value


def _integer(record: Mapping[str, Any], name: str) -> int:
    value = record[name]
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    return value


def _text_tuple(record: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = record[name]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TypeError(f"{name} must be a list of text")
    return tuple(value)


def _timestamp(record: Mapping[str, Any], name: str) -> datetime:
    return datetime.fromisoformat(_text(record, name).replace("Z", "+00:00"))
