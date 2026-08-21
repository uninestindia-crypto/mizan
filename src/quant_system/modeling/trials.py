"""Immutable trial starts, terminal outcomes, and complete multiplicity accounting."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.rows import (
    FEATURE_SCHEMA_ID_V1,
    FEATURE_SCHEMA_VERSION_V1,
    LABEL_CONTRACT_VERSION_V1,
)

MODEL_FAMILY_V1 = "RIDGE_CLASSIFIER"
MODEL_CONTRACT_VERSION_V1 = "ridge-six-v1"
SCORE_KIND_V1 = "UNCALIBRATED_SCORE"
_OUTCOME_SUFFIX = "_outcome"

_TRIAL_ID_PATTERN = re.compile(r"trial_[a-z0-9][a-z0-9_-]{0,62}")
_CANDIDATE_PATTERN = re.compile(r"cand_[a-z0-9][a-z0-9_-]{0,91}")
_DATASET_ID_PATTERN = re.compile(r"dset_[a-z0-9][a-z0-9_-]{0,91}")
_REVISION_PATTERN = re.compile(r"[0-9a-f]{7,64}")
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")


class TrialState(StrEnum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True, slots=True)
class RidgeTrialStartV1:
    trial_id: str
    candidate_id: str
    created_at: datetime
    dataset_id: str
    dataset_hash: str
    universe_policy_hash: str
    l2_penalty: str
    score_threshold: str
    numpy_seed: int
    fold_spec_hashes: tuple[str, ...]
    source_revision: str
    environment_lock_hash: str
    architecture: str
    multiplicity_ordinal: int
    model_family: str = MODEL_FAMILY_V1
    model_contract_version: str = MODEL_CONTRACT_VERSION_V1
    feature_schema_id: str = FEATURE_SCHEMA_ID_V1
    feature_schema_version: int = FEATURE_SCHEMA_VERSION_V1
    label_contract_version: str = LABEL_CONTRACT_VERSION_V1
    parameter_hash: str = field(init=False)
    start_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_trial_start(self)
        l2_penalty = _canonical_decimal(self.l2_penalty, "l2_penalty")
        threshold = _canonical_decimal(self.score_threshold, "score_threshold")
        if Decimal(l2_penalty) <= 0:
            raise ModelingError(
                ModelingFailureCode.INVALID_PARAMETER,
                "l2_penalty must be positive",
            )
        object.__setattr__(self, "l2_penalty", l2_penalty)
        object.__setattr__(self, "score_threshold", threshold)
        parameter_hash = canonical_sha256(self.parameter_dict())
        object.__setattr__(self, "parameter_hash", parameter_hash)
        object.__setattr__(self, "start_hash", canonical_sha256(self._unsigned_dict()))

    @property
    def outcome_resource_id(self) -> str:
        return f"{self.trial_id}{_OUTCOME_SUFFIX}"

    def parameter_dict(self) -> dict[str, Any]:
        return {
            "l2_penalty": self.l2_penalty,
            "numpy_seed": self.numpy_seed,
            "score_threshold": self.score_threshold,
        }

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["start_hash"] = self.start_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "architecture": self.architecture,
            "candidate_id": self.candidate_id,
            "created_at": utc_text(self.created_at),
            "dataset_hash": self.dataset_hash,
            "dataset_id": self.dataset_id,
            "environment_lock_hash": self.environment_lock_hash,
            "feature_schema_id": self.feature_schema_id,
            "feature_schema_version": self.feature_schema_version,
            "fold_spec_hashes": list(self.fold_spec_hashes),
            "label_contract_version": self.label_contract_version,
            "model_contract_version": self.model_contract_version,
            "model_family": self.model_family,
            "multiplicity_ordinal": self.multiplicity_ordinal,
            "parameter_hash": self.parameter_hash,
            "parameters": self.parameter_dict(),
            "schema_id": "quantos.ridge_trial_start",
            "schema_version": 1,
            "source_revision": self.source_revision,
            "state": TrialState.STARTED.value,
            "trial_id": self.trial_id,
            "universe_policy_hash": self.universe_policy_hash,
        }


@dataclass(frozen=True, slots=True)
class TrialOutcomeV1:
    trial_id: str
    start_hash: str
    state: TrialState
    ended_at: datetime
    result_hash: str | None
    failure_codes: tuple[str, ...]
    outcome_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_trial_outcome(self)
        object.__setattr__(self, "outcome_hash", canonical_sha256(self._unsigned_dict()))

    @property
    def resource_id(self) -> str:
        return f"{self.trial_id}{_OUTCOME_SUFFIX}"

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["outcome_hash"] = self.outcome_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "ended_at": utc_text(self.ended_at),
            "failure_codes": list(self.failure_codes),
            "result_hash": self.result_hash,
            "schema_id": "quantos.trial_outcome",
            "schema_version": 1,
            "start_hash": self.start_hash,
            "state": self.state.value,
            "trial_id": self.trial_id,
        }


@dataclass(frozen=True, slots=True)
class TrialRegistryV1:
    starts: tuple[RidgeTrialStartV1, ...]
    outcomes: tuple[TrialOutcomeV1, ...]

    def __post_init__(self) -> None:
        _validate_registry_starts(self.starts)
        starts_by_id = {start.trial_id: start for start in self.starts}
        outcome_ids = tuple(outcome.trial_id for outcome in self.outcomes)
        if len(set(outcome_ids)) != len(outcome_ids):
            raise ModelingError(
                ModelingFailureCode.MULTIPLICITY_INVALID,
                "trial start cannot have multiple terminal outcomes",
            )
        for outcome in self.outcomes:
            _validate_registered_outcome(outcome, starts_by_id)

    @property
    def multiplicity_count(self) -> int:
        return len(self.starts)

    def contains_start(self, start: RidgeTrialStartV1) -> bool:
        return any(candidate.start_hash == start.start_hash for candidate in self.starts)

    def require_ready_for_evaluation(self, current: RidgeTrialStartV1) -> None:
        if not self.contains_start(current) or self.starts[-1].start_hash != current.start_hash:
            raise ModelingError(
                ModelingFailureCode.MULTIPLICITY_INVALID,
                "evaluation trial must be the latest registered immutable start",
            )
        completed_ids = {outcome.trial_id for outcome in self.outcomes}
        prior_ids = {start.trial_id for start in self.starts[:-1]}
        if current.trial_id in completed_ids or completed_ids != prior_ids:
            raise ModelingError(
                ModelingFailureCode.MULTIPLICITY_INVALID,
                "every prior trial needs one terminal outcome and the current trial must be open",
            )


def succeeded_outcome(
    start: RidgeTrialStartV1,
    *,
    ended_at: datetime,
    result_hash: str,
) -> TrialOutcomeV1:
    return TrialOutcomeV1(
        trial_id=start.trial_id,
        start_hash=start.start_hash,
        state=TrialState.SUCCEEDED,
        ended_at=ended_at,
        result_hash=result_hash,
        failure_codes=(),
    )


def unsuccessful_outcome(
    start: RidgeTrialStartV1,
    *,
    state: TrialState,
    ended_at: datetime,
    failure_codes: tuple[str, ...],
) -> TrialOutcomeV1:
    return TrialOutcomeV1(
        trial_id=start.trial_id,
        start_hash=start.start_hash,
        state=state,
        ended_at=ended_at,
        result_hash=None,
        failure_codes=tuple(sorted(set(failure_codes))),
    )


def _validate_trial_outcome(outcome: TrialOutcomeV1) -> None:
    if _TRIAL_ID_PATTERN.fullmatch(outcome.trial_id) is None:
        raise ModelingError(ModelingFailureCode.TRIAL_OUTCOME_INVALID, "trial_id is invalid")
    if outcome.trial_id.endswith(_OUTCOME_SUFFIX):
        raise ModelingError(
            ModelingFailureCode.TRIAL_OUTCOME_INVALID,
            f"trial_id cannot end with the reserved suffix {_OUTCOME_SUFFIX!r}",
        )
    _require_hash(
        outcome.start_hash,
        "start_hash",
        failure_code=ModelingFailureCode.TRIAL_OUTCOME_INVALID,
    )
    _require_aware(
        outcome.ended_at,
        "ended_at",
        failure_code=ModelingFailureCode.TRIAL_OUTCOME_INVALID,
    )
    if outcome.state == TrialState.STARTED:
        raise ModelingError(
            ModelingFailureCode.TRIAL_OUTCOME_INVALID,
            "terminal outcome cannot remain STARTED",
        )
    if tuple(sorted(set(outcome.failure_codes))) != outcome.failure_codes:
        raise ModelingError(
            ModelingFailureCode.TRIAL_OUTCOME_INVALID,
            "failure_codes must be unique and sorted",
        )
    if outcome.state == TrialState.SUCCEEDED:
        _validate_successful_outcome(outcome)
        return
    if outcome.result_hash is not None or not outcome.failure_codes:
        raise ModelingError(
            ModelingFailureCode.TRIAL_OUTCOME_INVALID,
            "non-success outcome requires failure codes and no result hash",
        )


def _validate_successful_outcome(outcome: TrialOutcomeV1) -> None:
    if outcome.result_hash is None or outcome.failure_codes:
        raise ModelingError(
            ModelingFailureCode.TRIAL_OUTCOME_INVALID,
            "successful outcome requires one result hash and no failures",
        )
    _require_hash(
        outcome.result_hash,
        "result_hash",
        failure_code=ModelingFailureCode.TRIAL_OUTCOME_INVALID,
    )


def _validate_registry_starts(starts: tuple[RidgeTrialStartV1, ...]) -> None:
    if not starts:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "trial registry must contain at least one start",
        )
    trial_ids = tuple(start.trial_id for start in starts)
    ordinals = tuple(start.multiplicity_ordinal for start in starts)
    if len(set(trial_ids)) != len(trial_ids) or len(set(ordinals)) != len(ordinals):
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "trial starts must have unique IDs and multiplicity ordinals",
        )
    if ordinals != tuple(range(1, len(starts) + 1)):
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "trial starts must use contiguous multiplicity order starting at one",
        )


def _validate_registered_outcome(
    outcome: TrialOutcomeV1,
    starts_by_id: dict[str, RidgeTrialStartV1],
) -> None:
    start = starts_by_id.get(outcome.trial_id)
    if start is None or outcome.start_hash != start.start_hash:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "trial outcome does not bind one registered start",
        )
    if outcome.ended_at < start.created_at:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "trial outcome cannot precede its immutable start",
        )


def _validate_trial_start_hashes(start: RidgeTrialStartV1) -> None:
    for value, name in (
        (start.dataset_hash, "dataset_hash"),
        (start.universe_policy_hash, "universe_policy_hash"),
        (start.environment_lock_hash, "environment_lock_hash"),
    ):
        _require_hash(value, name)
    if not start.fold_spec_hashes or tuple(sorted(set(start.fold_spec_hashes))) != (
        start.fold_spec_hashes
    ):
        raise ModelingError(
            ModelingFailureCode.TRIAL_INVALID,
            "fold_spec_hashes must be non-empty, unique, and sorted",
        )
    for fold_hash in start.fold_spec_hashes:
        _require_hash(fold_hash, "fold_spec_hash")


def _validate_trial_start_contract(start: RidgeTrialStartV1) -> None:
    if (
        type(start.numpy_seed) is not int
        or type(start.multiplicity_ordinal) is not int
        or type(start.feature_schema_version) is not int
    ):
        raise ModelingError(
            ModelingFailureCode.TRIAL_INVALID,
            "ridge integer fields cannot use booleans or non-integer values",
        )
    if start.numpy_seed != 0 or start.multiplicity_ordinal < 1:
        raise ModelingError(
            ModelingFailureCode.TRIAL_INVALID,
            "ridge v1 requires seed zero and a positive multiplicity ordinal",
        )
    if (
        start.model_family != MODEL_FAMILY_V1
        or start.model_contract_version != MODEL_CONTRACT_VERSION_V1
        or start.feature_schema_id != FEATURE_SCHEMA_ID_V1
        or start.feature_schema_version != FEATURE_SCHEMA_VERSION_V1
        or start.label_contract_version != LABEL_CONTRACT_VERSION_V1
    ):
        raise ModelingError(ModelingFailureCode.TRIAL_INVALID, "trial contract version is invalid")


def _validate_trial_start(start: RidgeTrialStartV1) -> None:
    if _TRIAL_ID_PATTERN.fullmatch(start.trial_id) is None:
        raise ModelingError(ModelingFailureCode.TRIAL_INVALID, "trial_id is invalid")
    if start.trial_id.endswith(_OUTCOME_SUFFIX):
        raise ModelingError(
            ModelingFailureCode.TRIAL_INVALID,
            f"trial_id cannot end with the reserved suffix {_OUTCOME_SUFFIX!r}",
        )
    if _CANDIDATE_PATTERN.fullmatch(start.candidate_id) is None:
        raise ModelingError(ModelingFailureCode.TRIAL_INVALID, "candidate_id is invalid")
    if _DATASET_ID_PATTERN.fullmatch(start.dataset_id) is None:
        raise ModelingError(ModelingFailureCode.TRIAL_INVALID, "dataset_id is invalid")
    _require_aware(start.created_at, "created_at")
    _validate_trial_start_hashes(start)
    if _REVISION_PATTERN.fullmatch(start.source_revision) is None:
        raise ModelingError(ModelingFailureCode.TRIAL_INVALID, "source_revision is invalid")
    if not start.dataset_id or not start.architecture or len(start.architecture) > 128:
        raise ModelingError(
            ModelingFailureCode.TRIAL_INVALID,
            "dataset and architecture identities are required",
        )
    _validate_trial_start_contract(start)


def _canonical_decimal(value: str, field_name: str) -> str:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ModelingError(
            ModelingFailureCode.INVALID_PARAMETER,
            f"{field_name} must be canonical decimal text",
        ) from error
    if not parsed.is_finite() or decimal_text(parsed) != value:
        raise ModelingError(
            ModelingFailureCode.INVALID_PARAMETER,
            f"{field_name} must be finite canonical decimal text",
        )
    return value


def _require_hash(
    value: str,
    field_name: str,
    *,
    failure_code: ModelingFailureCode = ModelingFailureCode.TRIAL_INVALID,
) -> None:
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ModelingError(
            failure_code,
            f"{field_name} must be a SHA-256 hash",
        )


def _require_aware(
    value: datetime,
    field_name: str,
    *,
    failure_code: ModelingFailureCode = ModelingFailureCode.TRIAL_INVALID,
) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ModelingError(
            failure_code,
            f"{field_name} must be timezone-aware",
        )
