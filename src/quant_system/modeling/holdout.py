"""Cryptographic single-use holdout vault and immutable evaluation tracking."""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256, utc_text
from quant_system.evidence import (
    EvidenceDraft,
    EvidenceResourceType,
)
from quant_system.modeling.authorities import SessionCalendarV1
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.metrics import (
    STRATEGY_ORDER_V1,
    StrategyFoldReportV1,
    build_strategy_report,
)
from quant_system.modeling.preprocessing import transform_feature_rows
from quant_system.modeling.ridge import predict_ridge_scores
from quant_system.modeling.rows import (
    LABEL_HORIZON_SESSIONS_V1,
    FeatureDatasetV1,
    FeatureRowV1,
    LabelDatasetV1,
    LabelRowV1,
    require_feature_dataset_identity,
    require_label_dataset_identity,
)
from quant_system.modeling.validation import (
    RidgeFoldEvaluationV1,
    _label_key,
    _label_rows_hash,
    _previous_matured_targets,
    _require_decimal_text,
    deflate_ridge_report,
)

_HOLDOUT_ID_PATTERN = re.compile(r"holdout_[a-z0-9][a-z0-9_-]{0,62}")
_EVALUATION_ID_PATTERN = re.compile(r"holdout_eval_[a-z0-9][a-z0-9_-]{0,62}")
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
_HOLDOUT_START_SCHEMA = "quantos.holdout_evaluation_start"
_HOLDOUT_OUTCOME_SCHEMA = "quantos.holdout_evaluation_outcome"
_HOLDOUT_REPORT_SCHEMA = "quantos.holdout_report"


@dataclass(frozen=True, slots=True)
class HoldoutSpecV1:
    holdout_id: str
    candidate_id: str
    dataset_id: str
    dataset_hash: str
    discovery_start: datetime
    discovery_end: datetime
    holdout_start: datetime
    holdout_end: datetime
    purge_start: datetime
    purge_end: datetime
    embargo_sessions: int
    label_horizon_sessions: int
    discovery_row_count: int
    holdout_row_count: int
    discovery_hash: str
    holdout_hash: str
    token_hash: str
    spec_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_holdout_spec(self)
        object.__setattr__(self, "spec_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["spec_hash"] = self.spec_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "dataset_hash": self.dataset_hash,
            "dataset_id": self.dataset_id,
            "discovery_end": utc_text(self.discovery_end),
            "discovery_hash": self.discovery_hash,
            "discovery_row_count": self.discovery_row_count,
            "discovery_start": utc_text(self.discovery_start),
            "embargo_sessions": self.embargo_sessions,
            "holdout_end": utc_text(self.holdout_end),
            "holdout_hash": self.holdout_hash,
            "holdout_id": self.holdout_id,
            "holdout_row_count": self.holdout_row_count,
            "holdout_start": utc_text(self.holdout_start),
            "label_horizon_sessions": self.label_horizon_sessions,
            "purge_end": utc_text(self.purge_end),
            "purge_start": utc_text(self.purge_start),
            "schema_id": "quantos.holdout_spec",
            "schema_version": 1,
            "token_hash": self.token_hash,
        }


@dataclass(frozen=True, slots=True)
class HoldoutPartitionV1:
    spec: HoldoutSpecV1
    discovery_rows: tuple[LabelRowV1, ...]
    holdout_rows: tuple[LabelRowV1, ...]
    purged_record_keys: tuple[str, ...]
    embargoed_record_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HoldoutEvaluationStartV1:
    evaluation_id: str
    holdout_id: str
    candidate_id: str
    model_id: str
    trial_id: str
    started_at: datetime
    token_hash: str
    start_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if _EVALUATION_ID_PATTERN.fullmatch(self.evaluation_id) is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                "evaluation_id is invalid",
            )
        if _HOLDOUT_ID_PATTERN.fullmatch(self.holdout_id) is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                "holdout_id is invalid",
            )
        if _HASH_PATTERN.fullmatch(self.token_hash) is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                "token_hash must be a SHA-256 hash",
            )
        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                "started_at must be timezone-aware",
            )
        object.__setattr__(self, "start_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["start_hash"] = self.start_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "evaluation_id": self.evaluation_id,
            "holdout_id": self.holdout_id,
            "model_id": self.model_id,
            "schema_id": _HOLDOUT_START_SCHEMA,
            "schema_version": 1,
            "started_at": utc_text(self.started_at),
            "token_hash": self.token_hash,
            "trial_id": self.trial_id,
        }


@dataclass(frozen=True, slots=True)
class HoldoutEvaluationOutcomeV1:
    evaluation_id: str
    start_hash: str
    state: str
    ended_at: datetime
    result_hash: str | None
    failure_codes: tuple[str, ...]
    outcome_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if _EVALUATION_ID_PATTERN.fullmatch(self.evaluation_id) is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                "evaluation_id is invalid",
            )
        if _HASH_PATTERN.fullmatch(self.start_hash) is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                "start_hash must be a SHA-256 hash",
            )
        if self.ended_at.tzinfo is None or self.ended_at.utcoffset() is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                "ended_at must be timezone-aware",
            )
        if self.state not in {"SUCCEEDED", "FAILED"}:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                "holdout outcome state must be SUCCEEDED or FAILED",
            )
        if self.state == "SUCCEEDED":
            if self.result_hash is None or self.failure_codes:
                raise ModelingError(
                    ModelingFailureCode.HOLDOUT_INVALID,
                    "successful holdout outcome requires result_hash and no failure codes",
                )
            if _HASH_PATTERN.fullmatch(self.result_hash) is None:
                raise ModelingError(
                    ModelingFailureCode.HOLDOUT_INVALID,
                    "result_hash must be a SHA-256 hash",
                )
        else:
            if self.result_hash is not None or not self.failure_codes:
                raise ModelingError(
                    ModelingFailureCode.HOLDOUT_INVALID,
                    "failed holdout outcome requires failure codes and no result_hash",
                )
        object.__setattr__(self, "outcome_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["outcome_hash"] = self.outcome_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "ended_at": utc_text(self.ended_at),
            "evaluation_id": self.evaluation_id,
            "failure_codes": list(self.failure_codes),
            "result_hash": self.result_hash,
            "schema_id": _HOLDOUT_OUTCOME_SCHEMA,
            "schema_version": 1,
            "start_hash": self.start_hash,
            "state": self.state,
        }


@dataclass(frozen=True, slots=True)
class HoldoutReportV1:
    holdout_id: str
    candidate_id: str
    model_id: str
    trial_id: str
    spec_hash: str
    evaluated_at: datetime
    strategy_reports: tuple[StrategyFoldReportV1, ...]
    multiplicity_count: int
    deflated_sharpe_ratio: str
    report_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if tuple(report.strategy_id for report in self.strategy_reports) != STRATEGY_ORDER_V1:
            raise ValueError(
                "holdout report must contain ridge and four baselines in contract order"
            )
        if self.multiplicity_count < 1:
            raise ValueError("holdout multiplicity must be positive")
        if _HASH_PATTERN.fullmatch(self.spec_hash) is None:
            raise ValueError("spec_hash must be a SHA-256 hash")
        _require_decimal_text(self.deflated_sharpe_ratio, "deflated_sharpe_ratio")
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        object.__setattr__(self, "report_hash", canonical_sha256(self._unsigned_dict()))

    @property
    def ridge_report(self) -> StrategyFoldReportV1:
        return self.strategy_reports[0]

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["report_hash"] = self.report_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "deflated_sharpe_ratio": self.deflated_sharpe_ratio,
            "evaluated_at": utc_text(self.evaluated_at),
            "holdout_id": self.holdout_id,
            "model_id": self.model_id,
            "multiplicity_count": self.multiplicity_count,
            "schema_id": _HOLDOUT_REPORT_SCHEMA,
            "schema_version": 1,
            "spec_hash": self.spec_hash,
            "strategy_reports": [report.to_canonical_dict() for report in self.strategy_reports],
            "trial_id": self.trial_id,
        }


class HoldoutVaultTracker:
    """In-memory or store-backed state tracker enforcing single-use holdout unlocking."""

    def __init__(self) -> None:
        self._consumed_holdout_ids: dict[str, datetime] = {}
        self._consumed_tokens: dict[str, datetime] = {}
        self._evaluation_starts: dict[str, HoldoutEvaluationStartV1] = {}

    def is_consumed(self, holdout_id: str) -> bool:
        return holdout_id in self._consumed_holdout_ids

    def is_token_consumed(self, token_hash: str) -> bool:
        return token_hash in self._consumed_tokens

    def require_unconsumed(self, holdout_id: str, token_hash: str) -> None:
        if self.is_consumed(holdout_id) or self.is_token_consumed(token_hash):
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_ALREADY_CONSUMED,
                f"holdout {holdout_id} has already been unlocked and consumed",
            )

    def record_start(self, start: HoldoutEvaluationStartV1) -> None:
        self.require_unconsumed(start.holdout_id, start.token_hash)
        self._consumed_holdout_ids[start.holdout_id] = start.started_at
        self._consumed_tokens[start.token_hash] = start.started_at
        self._evaluation_starts[start.evaluation_id] = start


def create_holdout_partition(
    label_dataset: LabelDatasetV1,
    feature_dataset: FeatureDatasetV1,
    calendar: SessionCalendarV1,
    *,
    holdout_id: str,
    holdout_start: datetime,
    holdout_end: datetime,
    embargo_sessions: int = LABEL_HORIZON_SESSIONS_V1,
    unlock_token: str | None = None,
) -> tuple[HoldoutPartitionV1, str]:
    """Partition labels and features chronologically into discovery and holdout sets."""
    require_feature_dataset_identity(feature_dataset)
    require_label_dataset_identity(label_dataset)
    if _HOLDOUT_ID_PATTERN.fullmatch(holdout_id) is None:
        raise ModelingError(
            ModelingFailureCode.HOLDOUT_INVALID,
            "holdout_id is invalid",
        )
    if label_dataset.candidate_id != feature_dataset.candidate_id:
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            "label and feature datasets must share candidate_id",
        )
    if embargo_sessions < LABEL_HORIZON_SESSIONS_V1:
        raise ModelingError(
            ModelingFailureCode.EMBARGO_TOO_SHORT,
            "embargo must be at least the maximum label horizon",
        )
    holdout_ordinal = calendar.ordinal_for_close(holdout_start)
    if holdout_ordinal is None:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "holdout_start must be an exchange-session close",
        )
    end_ordinal = calendar.ordinal_for_close(holdout_end)
    if end_ordinal is None:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "holdout_end must be an exchange-session close",
        )
    if holdout_start > holdout_end:
        raise ModelingError(
            ModelingFailureCode.HOLDOUT_INVALID,
            "holdout_start must not follow holdout_end",
        )

    embargo_closes = {
        session.close_at
        for session in calendar.sessions[
            max(0, holdout_ordinal - embargo_sessions) : holdout_ordinal
        ]
    }

    holdout_rows = tuple(
        row for row in label_dataset.rows if holdout_start <= row.decision_at <= holdout_end
    )
    candidates = tuple(row for row in label_dataset.rows if row.decision_at < holdout_start)
    purged = tuple(row for row in candidates if row.exit_at >= holdout_start)
    purge_keys = {row.record_key for row in purged}
    after_purge = tuple(row for row in candidates if row.record_key not in purge_keys)
    embargoed = tuple(row for row in after_purge if row.decision_at in embargo_closes)
    embargo_keys = {row.record_key for row in embargoed}
    discovery_rows = tuple(row for row in after_purge if row.record_key not in embargo_keys)

    if not discovery_rows or not holdout_rows:
        raise ModelingError(
            ModelingFailureCode.HOLDOUT_INVALID,
            "holdout partition must retain non-empty discovery and holdout sets",
        )

    removed = tuple(sorted((*purged, *embargoed), key=lambda row: (row.decision_at, row.symbol)))
    purge_start = removed[0].decision_at if removed else holdout_start

    token = unlock_token or secrets.token_hex(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    spec = HoldoutSpecV1(
        holdout_id=holdout_id,
        candidate_id=label_dataset.candidate_id,
        dataset_id=label_dataset.dataset_id,
        dataset_hash=label_dataset.dataset_hash,
        discovery_start=discovery_rows[0].decision_at,
        discovery_end=discovery_rows[-1].decision_at,
        holdout_start=holdout_start,
        holdout_end=holdout_end,
        purge_start=purge_start,
        purge_end=holdout_start,
        embargo_sessions=embargo_sessions,
        label_horizon_sessions=LABEL_HORIZON_SESSIONS_V1,
        discovery_row_count=len(discovery_rows),
        holdout_row_count=len(holdout_rows),
        discovery_hash=_label_rows_hash(discovery_rows),
        holdout_hash=_label_rows_hash(holdout_rows),
        token_hash=token_hash,
    )

    partition = HoldoutPartitionV1(
        spec=spec,
        discovery_rows=discovery_rows,
        holdout_rows=holdout_rows,
        purged_record_keys=tuple(row.record_key for row in purged),
        embargoed_record_keys=tuple(row.record_key for row in embargoed),
    )
    return partition, token


def evaluate_governed_holdout(
    holdout: HoldoutPartitionV1,
    unlock_token: str,
    tracker: HoldoutVaultTracker,
    evaluation: RidgeFoldEvaluationV1,
    feature_dataset: FeatureDatasetV1,
    label_dataset: LabelDatasetV1,
    multiplicity_count: int,
    *,
    score_threshold: str = "0",
    evaluation_id: str = "holdout_eval_001",
    evaluated_at: datetime | None = None,
) -> HoldoutReportV1:
    """Evaluate candidate model on final holdout with strict single-use token verification."""
    now = evaluated_at or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ModelingError(
            ModelingFailureCode.HOLDOUT_INVALID,
            "evaluated_at must be timezone-aware",
        )

    # 1. Cryptographic token verification
    token_hash = hashlib.sha256(unlock_token.encode("utf-8")).hexdigest()
    if token_hash != holdout.spec.token_hash:
        raise ModelingError(
            ModelingFailureCode.HOLDOUT_TOKEN_INVALID,
            "holdout unlock token does not match cryptographic token hash",
        )

    # 2. Single-use enforcement
    tracker.require_unconsumed(holdout.spec.holdout_id, token_hash)

    # 3. Identity and integrity check
    if evaluation.candidate_id != holdout.spec.candidate_id:
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            "evaluation candidate_id does not match holdout spec",
        )

    start = HoldoutEvaluationStartV1(
        evaluation_id=evaluation_id,
        holdout_id=holdout.spec.holdout_id,
        candidate_id=evaluation.candidate_id,
        model_id=evaluation.model_id,
        trial_id=evaluation.trial_id,
        started_at=now,
        token_hash=token_hash,
    )
    tracker.record_start(start)

    # 4. Feature lookup and prediction on holdout
    feature_index: dict[tuple[str, str, datetime], FeatureRowV1] = {
        (row.candidate_id, row.symbol, row.decision_at): row for row in feature_dataset.rows
    }
    for row in holdout.holdout_rows:
        if _label_key(row) not in feature_index:
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "holdout label has no exact feature row",
                offending_record_key=row.record_key,
            )

    holdout_features = tuple(feature_index[_label_key(row)] for row in holdout.holdout_rows)
    transformed_holdout = transform_feature_rows(holdout_features, evaluation.preprocessing)
    scores = predict_ridge_scores(evaluation.fitted_state, transformed_holdout)

    # Thresholding
    threshold = Decimal(score_threshold)
    candidate_targets = tuple("UP" if Decimal(score) > threshold else "DOWN" for score in scores)

    target_sets = {
        "RIDGE": candidate_targets,
        "NO_TRADE": tuple("DOWN" for _ in holdout.holdout_rows),
        "BUY_AND_HOLD": tuple("UP" for _ in holdout.holdout_rows),
        "PREVIOUS_SIGN": _previous_matured_targets(label_dataset.rows, holdout.holdout_rows),
        "EQUITY_DUAL_MOMENTUM": tuple(
            "UP"
            if Decimal(row.features["return_10"]) > 0
            and Decimal(row.features["sma_20_distance"]) > 0
            else "DOWN"
            for row in holdout_features
        ),
    }

    reports = tuple(
        build_strategy_report(
            strategy_id,
            holdout.holdout_rows,
            target_sets[strategy_id],
            scores if strategy_id == "RIDGE" else None,
        )
        for strategy_id in STRATEGY_ORDER_V1
    )

    dsr = deflate_ridge_report(reports[0], multiplicity_count=multiplicity_count)

    return HoldoutReportV1(
        holdout_id=holdout.spec.holdout_id,
        candidate_id=evaluation.candidate_id,
        model_id=evaluation.model_id,
        trial_id=evaluation.trial_id,
        spec_hash=holdout.spec.spec_hash,
        evaluated_at=now,
        strategy_reports=reports,
        multiplicity_count=multiplicity_count,
        deflated_sharpe_ratio=dsr,
    )


def draft_from_holdout_start(start: HoldoutEvaluationStartV1) -> EvidenceDraft:
    return EvidenceDraft(
        resource_type=EvidenceResourceType.OPERATION,
        resource_id=f"op_{start.evaluation_id}",
        schema_id=_HOLDOUT_START_SCHEMA,
        schema_version=1,
        metadata={
            "candidate_id": start.candidate_id,
            "holdout_id": start.holdout_id,
            "model_id": start.model_id,
            "start_hash": start.start_hash,
            "token_hash": start.token_hash,
            "trial_id": start.trial_id,
        },
        records=(start.to_canonical_dict(),),
        total_order=("evaluation_id", "started_at"),
    )


def draft_from_holdout_outcome(outcome: HoldoutEvaluationOutcomeV1) -> EvidenceDraft:
    return EvidenceDraft(
        resource_type=EvidenceResourceType.OPERATION,
        resource_id=f"op_{outcome.evaluation_id}_outcome",
        schema_id=_HOLDOUT_OUTCOME_SCHEMA,
        schema_version=1,
        metadata={
            "evaluation_id": outcome.evaluation_id,
            "outcome_hash": outcome.outcome_hash,
            "start_hash": outcome.start_hash,
            "state": outcome.state,
        },
        records=(outcome.to_canonical_dict(),),
        total_order=("evaluation_id", "state"),
    )


def draft_from_holdout_report(report: HoldoutReportV1) -> EvidenceDraft:
    records = tuple(
        decision.to_canonical_dict()
        for report_item in report.strategy_reports
        for decision in report_item.decisions
    )
    sorted_records = tuple(
        sorted(
            records,
            key=lambda item: (item["strategy_id"], item["decision_at"], item["symbol"]),
        )
    )
    metadata: dict[str, Any] = {
        "candidate_id": report.candidate_id,
        "deflated_sharpe_ratio": report.deflated_sharpe_ratio,
        "evaluated_at": utc_text(report.evaluated_at),
        "holdout_id": report.holdout_id,
        "model_id": report.model_id,
        "multiplicity_count": report.multiplicity_count,
        "report_hash": report.report_hash,
        "spec_hash": report.spec_hash,
        "strategy_reports": [
            {
                "metrics": r.metrics.to_canonical_dict(),
                "metrics_hash": r.metrics_hash,
                "prediction_hash": r.prediction_hash,
                "strategy_id": r.strategy_id,
            }
            for r in report.strategy_reports
        ],
        "trial_id": report.trial_id,
    }
    return EvidenceDraft(
        resource_type=EvidenceResourceType.MODEL,
        resource_id=f"model_{report.report_hash[:24]}_holdout",
        schema_id="quantos.holdout_strategy_decision",
        schema_version=1,
        metadata=metadata,
        records=sorted_records,
        total_order=("strategy_id", "decision_at", "symbol"),
    )


def _validate_holdout_spec(spec: HoldoutSpecV1) -> None:
    if _HOLDOUT_ID_PATTERN.fullmatch(spec.holdout_id) is None:
        raise ModelingError(ModelingFailureCode.HOLDOUT_INVALID, "holdout_id is invalid")
    for value, name in (
        (spec.dataset_hash, "dataset_hash"),
        (spec.discovery_hash, "discovery_hash"),
        (spec.holdout_hash, "holdout_hash"),
        (spec.token_hash, "token_hash"),
    ):
        if _HASH_PATTERN.fullmatch(value) is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                f"{name} must be a SHA-256 hash",
            )
    for dt_val, dt_name in (
        (spec.discovery_start, "discovery_start"),
        (spec.discovery_end, "discovery_end"),
        (spec.holdout_start, "holdout_start"),
        (spec.holdout_end, "holdout_end"),
        (spec.purge_start, "purge_start"),
        (spec.purge_end, "purge_end"),
    ):
        if dt_val.tzinfo is None or dt_val.utcoffset() is None:
            raise ModelingError(
                ModelingFailureCode.HOLDOUT_INVALID,
                f"{dt_name} must be timezone-aware",
            )
    if spec.discovery_row_count < 1 or spec.holdout_row_count < 1:
        raise ModelingError(
            ModelingFailureCode.HOLDOUT_INVALID,
            "discovery and holdout row counts must be positive",
        )
    if spec.embargo_sessions < spec.label_horizon_sessions:
        raise ModelingError(
            ModelingFailureCode.EMBARGO_TOO_SHORT,
            "embargo must be at least label horizon",
        )
