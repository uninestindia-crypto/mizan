"""The governed promotion pipeline: the production caller of the Slice 5 stack.

Until this module existed, `evaluate_governed_holdout`, `run_mandatory_stress_suite` and
`evaluate_promotion` had no caller anywhere in `src/` outside their own defining modules, so no
holdout, stress, or promotion evidence was ever published. The stack was implemented, tested, and
unreachable (Red Team finding X-1).

This module chains the three and publishes every artefact each one produces. It decides nothing
itself: the verdict is whatever `evaluate_promotion` returns, and a failing gate is published as
faithfully as a passing one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from quant_system.evidence import EvidenceStore
from quant_system.modeling.authorities import SessionCalendarV1
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.holdout import (
    HoldoutEvaluationOutcomeV1,
    HoldoutPartitionV1,
    HoldoutReportV1,
    HoldoutVaultTracker,
    draft_from_holdout_outcome,
    draft_from_holdout_report,
    draft_from_holdout_start,
    evaluate_governed_holdout,
)
from quant_system.modeling.promotion import (
    GatePolicyV1,
    ModelCardV1,
    PromotionRecordV1,
    PromotionState,
    draft_from_promotion_record,
    evaluate_promotion,
)
from quant_system.modeling.rows import (
    FeatureDatasetV1,
    LabelDatasetV1,
    RoundTripCostQuoteV1,
)
from quant_system.modeling.stress import (
    StressReportV1,
    draft_from_stress_report,
    run_mandatory_stress_suite,
)
from quant_system.modeling.validation import RidgeFoldEvaluationV1


@dataclass(frozen=True, slots=True)
class PersistedPromotionV1:
    """Everything the pipeline produced, with the evidence already published."""

    holdout_report: HoldoutReportV1
    stress_report: StressReportV1
    promotion_record: PromotionRecordV1
    model_card: ModelCardV1 | None


def run_persisted_promotion(
    store: EvidenceStore,
    *,
    operation_id: str,
    holdout: HoldoutPartitionV1,
    unlock_token: str,
    tracker: HoldoutVaultTracker,
    evaluation: RidgeFoldEvaluationV1,
    feature_dataset: FeatureDatasetV1,
    label_dataset: LabelDatasetV1,
    cost_quotes: tuple[RoundTripCostQuoteV1, ...]
    | Mapping[tuple[str, datetime], RoundTripCostQuoteV1],
    calendar: SessionCalendarV1,
    multiplicity_count: int,
    from_state: PromotionState,
    to_state: PromotionState,
    fold_evaluations: Sequence[RidgeFoldEvaluationV1] | None = None,
    policy: GatePolicyV1 | None = None,
    score_threshold: str = "0",
    evaluation_id: str = "holdout_eval_001",
    promotion_id: str = "promo_eval_001",
    evaluated_at: datetime | None = None,
    adverse_spread_slippage_bps: Decimal = Decimal("20"),
    max_tolerated_drawdown: Decimal = Decimal("0.25"),
) -> PersistedPromotionV1:
    """Unlock the holdout once, stress the candidate, decide promotion, publish all of it."""
    if not operation_id or len(operation_id) > 96:
        raise ValueError("operation_id must contain 1-96 characters")
    now = evaluated_at or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ModelingError(
            ModelingFailureCode.HOLDOUT_INVALID,
            "evaluated_at must be timezone-aware",
        )

    # 1. Final holdout. Single use is enforced by the tracker's durable vault.
    holdout_report = evaluate_governed_holdout(
        holdout,
        unlock_token,
        tracker,
        evaluation,
        feature_dataset,
        label_dataset,
        multiplicity_count,
        score_threshold=score_threshold,
        evaluation_id=evaluation_id,
        evaluated_at=now,
    )

    # The start record is published only after the unlock actually succeeded, so the evidence
    # never claims an unlock that did not happen.
    start = tracker.get_evaluation_start(evaluation_id)
    if start is None:
        raise ModelingError(
            ModelingFailureCode.HOLDOUT_INVALID,
            f"vault recorded no evaluation start for {evaluation_id}",
        )
    store.commit(draft_from_holdout_start(start), operation_id=f"{operation_id}-holdout-start")
    store.commit(
        draft_from_holdout_report(holdout_report),
        operation_id=f"{operation_id}-holdout-report",
    )
    store.commit(
        draft_from_holdout_outcome(
            HoldoutEvaluationOutcomeV1(
                evaluation_id=evaluation_id,
                start_hash=start.start_hash,
                state="SUCCEEDED",
                ended_at=now,
                result_hash=holdout_report.report_hash,
                failure_codes=(),
            )
        ),
        operation_id=f"{operation_id}-holdout-outcome",
    )

    # 2. Mandatory stress suite over the same decisions the candidate actually made.
    stress_report = run_mandatory_stress_suite(
        evaluation.ridge_report.decisions,
        label_dataset.rows,
        cost_quotes,
        calendar,
        candidate_id=holdout.spec.candidate_id,
        model_id=evaluation.model_id,
        evaluated_at=now,
        adverse_spread_slippage_bps=adverse_spread_slippage_bps,
        max_tolerated_drawdown=max_tolerated_drawdown,
    )
    store.commit(
        draft_from_stress_report(stress_report),
        operation_id=f"{operation_id}-stress",
    )

    # 3. Evidence-only promotion decision. Whatever it returns is what gets published.
    promotion_record, model_card = evaluate_promotion(
        candidate_id=holdout.spec.candidate_id,
        model_id=evaluation.model_id,
        from_state=from_state,
        to_state=to_state,
        fold_evaluations=list(fold_evaluations) if fold_evaluations else [evaluation],
        holdout_report=holdout_report,
        stress_report=stress_report,
        policy=policy,
        promotion_id=promotion_id,
        requested_at=now,
        evaluated_at=now,
    )
    store.commit(
        draft_from_promotion_record(promotion_record),
        operation_id=f"{operation_id}-promotion",
    )

    return PersistedPromotionV1(
        holdout_report=holdout_report,
        stress_report=stress_report,
        promotion_record=promotion_record,
        model_card=model_card,
    )
