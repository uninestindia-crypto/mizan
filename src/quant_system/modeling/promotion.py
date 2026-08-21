"""Evidence-only deterministic promotion decision engine and model cards."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text
from quant_system.evidence import EvidenceDraft, EvidenceResourceType
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.holdout import HoldoutReportV1
from quant_system.modeling.stress import StressReportV1
from quant_system.modeling.validation import RidgeFoldEvaluationV1, _require_decimal_text

_PROMOTION_ID_PATTERN = re.compile(r"promo_[a-z0-9][a-z0-9_-]{0,62}")
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
_PROMOTION_SCHEMA = "quantos.promotion_record"
_MODEL_CARD_SCHEMA = "quantos.model_card"


class PromotionState(StrEnum):
    REJECT = "REJECT"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    SHADOW = "SHADOW"
    PAPER_PILOT = "PAPER_PILOT"
    PAPER = "PAPER"


class GateOperator(StrEnum):
    GTE = "GTE"
    LTE = "LTE"
    GT = "GT"
    LT = "LT"
    EQ = "EQ"
    BOOLEAN = "BOOLEAN"


class PromotionGateId(StrEnum):
    GATE_DEFLATED_SHARPE = "GATE_DEFLATED_SHARPE"
    GATE_MANDATORY_STRESS = "GATE_MANDATORY_STRESS"
    GATE_HOLDOUT_EVALUATION = "GATE_HOLDOUT_EVALUATION"
    GATE_MAX_DRAWDOWN = "GATE_MAX_DRAWDOWN"
    GATE_WORST_FOLD_SHARPE = "GATE_WORST_FOLD_SHARPE"
    GATE_MIN_ATTRIBUTABLE_RECORDS = "GATE_MIN_ATTRIBUTABLE_RECORDS"
    GATE_SCORE_CALIBRATION_INTEGRITY = "GATE_SCORE_CALIBRATION_INTEGRITY"


_ALLOWED_FORWARD_EDGES = {
    PromotionState.REJECT: {PromotionState.RESEARCH_ONLY},
    PromotionState.RESEARCH_ONLY: {PromotionState.SHADOW},
    PromotionState.SHADOW: {PromotionState.PAPER_PILOT},
    PromotionState.PAPER_PILOT: {PromotionState.PAPER},
    PromotionState.PAPER: set(),
}


@dataclass(frozen=True, slots=True)
class GateResultV1:
    gate_id: str
    operator: str
    threshold: str
    observed: str
    unit: str
    passed: bool
    evidence_hash: str

    def __post_init__(self) -> None:
        if not self.gate_id:
            raise ValueError("gate_id cannot be empty")
        if _HASH_PATTERN.fullmatch(self.evidence_hash) is None:
            raise ValueError("evidence_hash must be a SHA-256 hash")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "evidence_hash": self.evidence_hash,
            "gate_id": self.gate_id,
            "observed": self.observed,
            "operator": self.operator,
            "passed": self.passed,
            "schema_id": "quantos.gate_result",
            "schema_version": 1,
            "threshold": self.threshold,
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class GatePolicyV1:
    policy_id: str
    min_deflated_sharpe: str = "0.95"
    max_drawdown: str = "0.15"
    min_fold_sharpe: str = "-0.5"
    min_attributable_records: int = 5
    min_holdout_total_return: str = "0"
    require_stress_tests: bool = True
    require_holdout: bool = True
    policy_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _require_decimal_text(self.min_deflated_sharpe, "min_deflated_sharpe")
        _require_decimal_text(self.max_drawdown, "max_drawdown")
        _require_decimal_text(self.min_fold_sharpe, "min_fold_sharpe")
        _require_decimal_text(self.min_holdout_total_return, "min_holdout_total_return")
        if self.min_attributable_records < 1:
            raise ValueError("min_attributable_records must be positive")
        object.__setattr__(self, "policy_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["policy_hash"] = self.policy_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "max_drawdown": self.max_drawdown,
            "min_attributable_records": self.min_attributable_records,
            "min_deflated_sharpe": self.min_deflated_sharpe,
            "min_fold_sharpe": self.min_fold_sharpe,
            "min_holdout_total_return": self.min_holdout_total_return,
            "policy_id": self.policy_id,
            "require_holdout": self.require_holdout,
            "require_stress_tests": self.require_stress_tests,
            "schema_id": "quantos.gate_policy",
            "schema_version": 1,
        }


@dataclass(frozen=True, slots=True)
class PromotionRecordV1:
    promotion_id: str
    candidate_id: str
    model_id: str
    from_state: PromotionState
    to_state: PromotionState
    requested_at: datetime
    evaluated_at: datetime
    gate_policy_hash: str
    evidence_refs: tuple[str, ...]
    gate_results: tuple[GateResultV1, ...]
    verdict: PromotionState
    failed_gate_codes: tuple[str, ...]
    rollback_model_id: str | None = None
    actor: str = "LOCAL_USER"
    record_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_promotion_record(self)
        object.__setattr__(self, "record_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["record_hash"] = self.record_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "candidate_id": self.candidate_id,
            "evaluated_at": utc_text(self.evaluated_at),
            "evidence_refs": list(self.evidence_refs),
            "failed_gate_codes": list(self.failed_gate_codes),
            "from_state": self.from_state.value,
            "gate_policy_hash": self.gate_policy_hash,
            "gate_results": [g.to_canonical_dict() for g in self.gate_results],
            "model_id": self.model_id,
            "promotion_id": self.promotion_id,
            "requested_at": utc_text(self.requested_at),
            "rollback_model_id": self.rollback_model_id,
            "schema_id": _PROMOTION_SCHEMA,
            "schema_version": 1,
            "to_state": self.to_state.value,
            "verdict": self.verdict.value,
        }


@dataclass(frozen=True, slots=True)
class ModelCardV1:
    model_id: str
    candidate_id: str
    verdict: PromotionState
    created_at: datetime
    monitoring_limits: dict[str, str]
    halt_and_rollback_policy: str
    limitations: tuple[str, ...]
    model_card_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.model_id or not self.candidate_id:
            raise ValueError("model_id and candidate_id cannot be empty")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        object.__setattr__(self, "model_card_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["model_card_hash"] = self.model_card_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "created_at": utc_text(self.created_at),
            "halt_and_rollback_policy": self.halt_and_rollback_policy,
            "limitations": list(self.limitations),
            "model_id": self.model_id,
            "monitoring_limits": self.monitoring_limits,
            "schema_id": _MODEL_CARD_SCHEMA,
            "schema_version": 1,
            "verdict": self.verdict.value,
        }


def evaluate_promotion(
    *,
    candidate_id: str,
    model_id: str,
    from_state: PromotionState,
    to_state: PromotionState,
    fold_evaluations: Sequence[RidgeFoldEvaluationV1],
    holdout_report: HoldoutReportV1 | None = None,
    stress_report: StressReportV1 | None = None,
    policy: GatePolicyV1 | None = None,
    promotion_id: str = "promo_eval_001",
    requested_at: datetime | None = None,
    evaluated_at: datetime | None = None,
    rollback_model_id: str | None = None,
) -> tuple[PromotionRecordV1, ModelCardV1 | None]:
    """Pure, evidence-only promotion decision engine evaluating frozen gates."""
    req_time = requested_at or datetime.now(UTC)
    eval_time = evaluated_at or datetime.now(UTC)
    gate_policy = policy or GatePolicyV1(policy_id="default_shadow_policy_v1")

    # 1. LIVE verdict refusal (out of scope for T2, strictly forbidden)
    if to_state == "LIVE" or from_state == "LIVE":
        raise ModelingError(
            ModelingFailureCode.INVALID_PARAMETER,
            "LIVE verdict is prohibited in QuantOS promotion; live-capital routing requires separate authorized process",
        )

    # 2. State transition validation
    if to_state != from_state:
        # Check backward/demotion vs forward
        allowed_forward = _ALLOWED_FORWARD_EDGES.get(from_state, set())
        if to_state not in allowed_forward:
            # Check if it's a demotion / backward edge
            all_states_order = [
                PromotionState.REJECT,
                PromotionState.RESEARCH_ONLY,
                PromotionState.SHADOW,
                PromotionState.PAPER_PILOT,
                PromotionState.PAPER,
            ]
            from_idx = all_states_order.index(from_state)
            to_idx = all_states_order.index(to_state)
            if to_idx > from_idx:
                raise ModelingError(
                    ModelingFailureCode.ILLEGAL_STATE_TRANSITION,
                    f"illegal forward transition from {from_state.value} to {to_state.value}; skipping intermediate states is prohibited",
                )

    if not fold_evaluations:
        raise ModelingError(
            ModelingFailureCode.PROMOTION_INVALID,
            "promotion evaluation requires at least one fold evaluation",
        )

    # Evaluate gates
    gate_results: list[GateResultV1] = []
    failed_codes: list[str] = []
    evidence_refs: list[str] = [fold.evaluation_hash for fold in fold_evaluations]

    primary_eval = fold_evaluations[0]
    ridge_rep = primary_eval.ridge_report

    # Gate 1: Deflated Sharpe Ratio
    observed_dsr = Decimal(primary_eval.deflated_sharpe_ratio)
    threshold_dsr = Decimal(gate_policy.min_deflated_sharpe)
    dsr_passed = observed_dsr >= threshold_dsr
    gate_results.append(
        GateResultV1(
            gate_id=PromotionGateId.GATE_DEFLATED_SHARPE.value,
            operator=GateOperator.GTE.value,
            threshold=gate_policy.min_deflated_sharpe,
            observed=primary_eval.deflated_sharpe_ratio,
            unit="RATIO",
            passed=dsr_passed,
            evidence_hash=primary_eval.evaluation_hash,
        )
    )
    if not dsr_passed:
        failed_codes.append(PromotionGateId.GATE_DEFLATED_SHARPE.value)

    # Gate 2: Max Drawdown
    observed_dd = Decimal(ridge_rep.metrics.max_drawdown)
    threshold_dd = Decimal(gate_policy.max_drawdown)
    dd_passed = observed_dd <= threshold_dd
    gate_results.append(
        GateResultV1(
            gate_id=PromotionGateId.GATE_MAX_DRAWDOWN.value,
            operator=GateOperator.LTE.value,
            threshold=gate_policy.max_drawdown,
            observed=ridge_rep.metrics.max_drawdown,
            unit="RATIO",
            passed=dd_passed,
            evidence_hash=ridge_rep.metrics_hash,
        )
    )
    if not dd_passed:
        failed_codes.append(PromotionGateId.GATE_MAX_DRAWDOWN.value)

    # Gate 3: Worst Fold Sharpe
    fold_sharpes = [Decimal(f.ridge_report.metrics.sharpe_ratio) for f in fold_evaluations]
    worst_sharpe = min(fold_sharpes)
    threshold_sharpe = Decimal(gate_policy.min_fold_sharpe)
    sharpe_passed = worst_sharpe >= threshold_sharpe
    gate_results.append(
        GateResultV1(
            gate_id=PromotionGateId.GATE_WORST_FOLD_SHARPE.value,
            operator=GateOperator.GTE.value,
            threshold=gate_policy.min_fold_sharpe,
            observed=decimal_text(worst_sharpe),
            unit="RATIO",
            passed=sharpe_passed,
            evidence_hash=primary_eval.evaluation_hash,
        )
    )
    if not sharpe_passed:
        failed_codes.append(PromotionGateId.GATE_WORST_FOLD_SHARPE.value)

    # Gate 4: Minimum Attributable Records
    total_attributable = sum(f.ridge_report.metrics.attributable_count for f in fold_evaluations)
    attrib_passed = total_attributable >= gate_policy.min_attributable_records
    gate_results.append(
        GateResultV1(
            gate_id=PromotionGateId.GATE_MIN_ATTRIBUTABLE_RECORDS.value,
            operator=GateOperator.GTE.value,
            threshold=str(gate_policy.min_attributable_records),
            observed=str(total_attributable),
            unit="COUNT",
            passed=attrib_passed,
            evidence_hash=primary_eval.evaluation_hash,
        )
    )
    if not attrib_passed:
        failed_codes.append(PromotionGateId.GATE_MIN_ATTRIBUTABLE_RECORDS.value)

    # Gate 5: Mandatory Stress Tests
    if gate_policy.require_stress_tests and to_state in {
        PromotionState.SHADOW,
        PromotionState.PAPER_PILOT,
        PromotionState.PAPER,
    }:
        if stress_report is None:
            stress_passed = False
            stress_hash = "0" * 64
        else:
            stress_passed = stress_report.all_passed
            stress_hash = stress_report.report_hash
            evidence_refs.append(stress_report.report_hash)

        gate_results.append(
            GateResultV1(
                gate_id=PromotionGateId.GATE_MANDATORY_STRESS.value,
                operator=GateOperator.BOOLEAN.value,
                threshold="True",
                observed=str(stress_passed),
                unit="BOOLEAN",
                passed=stress_passed,
                evidence_hash=stress_hash,
            )
        )
        if not stress_passed:
            failed_codes.append(PromotionGateId.GATE_MANDATORY_STRESS.value)

    # Gate 6: Holdout Evaluation
    if gate_policy.require_holdout and to_state in {
        PromotionState.SHADOW,
        PromotionState.PAPER_PILOT,
        PromotionState.PAPER,
    }:
        if holdout_report is None:
            holdout_passed = False
            holdout_hash = "0" * 64
            observed_ret = "0"
        else:
            holdout_ret = Decimal(holdout_report.ridge_report.metrics.total_return)
            threshold_ret = Decimal(gate_policy.min_holdout_total_return)
            holdout_passed = holdout_ret >= threshold_ret
            holdout_hash = holdout_report.report_hash
            observed_ret = holdout_report.ridge_report.metrics.total_return
            evidence_refs.append(holdout_report.report_hash)

        gate_results.append(
            GateResultV1(
                gate_id=PromotionGateId.GATE_HOLDOUT_EVALUATION.value,
                operator=GateOperator.GTE.value,
                threshold=gate_policy.min_holdout_total_return,
                observed=observed_ret,
                unit="RATIO",
                passed=holdout_passed,
                evidence_hash=holdout_hash,
            )
        )
        if not holdout_passed:
            failed_codes.append(PromotionGateId.GATE_HOLDOUT_EVALUATION.value)

    # Gate 7: Score calibration integrity
    score_kinds = {d.score_kind for f in fold_evaluations for d in f.ridge_report.decisions}
    calib_passed = score_kinds == {"UNCALIBRATED_SCORE"}
    gate_results.append(
        GateResultV1(
            gate_id=PromotionGateId.GATE_SCORE_CALIBRATION_INTEGRITY.value,
            operator=GateOperator.BOOLEAN.value,
            threshold="UNCALIBRATED_SCORE",
            observed=list(score_kinds)[0] if score_kinds else "UNKNOWN",
            unit="BOOLEAN",
            passed=calib_passed,
            evidence_hash=primary_eval.evaluation_hash,
        )
    )
    if not calib_passed:
        failed_codes.append(PromotionGateId.GATE_SCORE_CALIBRATION_INTEGRITY.value)

    # Determine verdict
    all_gates_passed = len(failed_codes) == 0
    if all_gates_passed:
        verdict = to_state
    else:
        # If any gate fails when advancing, verdict stays at from_state (or demotes to REJECT)
        verdict = from_state if from_state != PromotionState.REJECT else PromotionState.REJECT

    record = PromotionRecordV1(
        promotion_id=promotion_id,
        candidate_id=candidate_id,
        model_id=model_id,
        from_state=from_state,
        to_state=to_state,
        requested_at=req_time,
        evaluated_at=eval_time,
        gate_policy_hash=gate_policy.policy_hash,
        evidence_refs=tuple(sorted(set(evidence_refs))),
        gate_results=tuple(gate_results),
        verdict=verdict,
        failed_gate_codes=tuple(sorted(set(failed_codes))),
        rollback_model_id=rollback_model_id,
    )

    # Generate model card if promoting to SHADOW or PAPER_PILOT
    model_card = None
    if verdict in {PromotionState.SHADOW, PromotionState.PAPER_PILOT, PromotionState.PAPER}:
        model_card = ModelCardV1(
            model_id=model_id,
            candidate_id=candidate_id,
            verdict=verdict,
            created_at=eval_time,
            monitoring_limits={
                "input_missingness_max_fraction": "0.01",
                "score_drift_psi_threshold": "0.25",
                "turnover_max_daily": "2.0",
                "max_drawdown_halt_threshold": "0.15",
                "cost_slippage_max_multiplier": "2.0",
                "risk_rejection_rate_halt_threshold": "0.05",
            },
            halt_and_rollback_policy=(
                "Halt immediately if missing input > 1%, PSI > 0.25, drawdown > 15%, "
                "or risk rejection > 5%. Revert active model reference to verified rollback target."
            ),
            limitations=(
                "Six technical features only.",
                "Executable next-open-to-following-open net cost.",
                "Uncalibrated scores, not probabilities.",
                "Single-process deterministic execution.",
            ),
        )

    return record, model_card


def draft_from_promotion_record(record: PromotionRecordV1) -> EvidenceDraft:
    return EvidenceDraft(
        resource_type=EvidenceResourceType.OPERATION,
        resource_id=f"op_{record.promotion_id}",
        schema_id=_PROMOTION_SCHEMA,
        schema_version=1,
        metadata={
            "candidate_id": record.candidate_id,
            "failed_gate_codes": list(record.failed_gate_codes),
            "from_state": record.from_state.value,
            "gate_policy_hash": record.gate_policy_hash,
            "model_id": record.model_id,
            "promotion_id": record.promotion_id,
            "record_hash": record.record_hash,
            "to_state": record.to_state.value,
            "verdict": record.verdict.value,
        },
        records=(record.to_canonical_dict(),),
        total_order=("promotion_id", "evaluated_at"),
    )


def _validate_promotion_record(record: PromotionRecordV1) -> None:
    if _PROMOTION_ID_PATTERN.fullmatch(record.promotion_id) is None:
        raise ModelingError(ModelingFailureCode.PROMOTION_INVALID, "promotion_id is invalid")
    if _HASH_PATTERN.fullmatch(record.gate_policy_hash) is None:
        raise ModelingError(
            ModelingFailureCode.PROMOTION_INVALID, "gate_policy_hash must be a SHA-256 hash"
        )
    if record.requested_at.tzinfo is None or record.requested_at.utcoffset() is None:
        raise ModelingError(
            ModelingFailureCode.PROMOTION_INVALID, "requested_at must be timezone-aware"
        )
    if record.evaluated_at.tzinfo is None or record.evaluated_at.utcoffset() is None:
        raise ModelingError(
            ModelingFailureCode.PROMOTION_INVALID, "evaluated_at must be timezone-aware"
        )
    if not record.gate_results:
        raise ModelingError(ModelingFailureCode.PROMOTION_INVALID, "gate_results cannot be empty")
