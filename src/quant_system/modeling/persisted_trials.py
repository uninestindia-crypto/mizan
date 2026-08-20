"""Rebuild complete trial multiplicity from verified immutable evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from quant_system.evidence import EvidenceResourceType, EvidenceStore, VerifiedEvidence
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.trials import (
    RidgeTrialStartV1,
    TrialOutcomeV1,
    TrialRegistryV1,
    TrialState,
)

_START_SCHEMA = "quantos.ridge_trial_start"
_OUTCOME_SCHEMA = "quantos.trial_outcome"


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
    return start


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
    return outcome


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
