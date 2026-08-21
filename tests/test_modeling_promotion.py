"""Comprehensive tests for deterministic promotion decision engine and gates."""

from __future__ import annotations

from decimal import Decimal

import pytest

from quant_system.modeling import (
    GatePolicyV1,
    ModelingError,
    ModelingFailureCode,
    PromotionGateId,
    PromotionState,
    draft_from_promotion_record,
    evaluate_governed_holdout,
    evaluate_governed_ridge_fold,
    evaluate_promotion,
    run_mandatory_stress_suite,
)
from quant_system.modeling.holdout import HoldoutVaultTracker, create_holdout_partition
from quant_system.modeling.rows import MoneyV1, RoundTripCostQuoteV1
from tests.modeling_training_fixtures import governed_training_journey


def _sample_cost_quotes(journey) -> tuple[RoundTripCostQuoteV1, ...]:
    return tuple(
        RoundTripCostQuoteV1(
            provider_instrument_id="NSE_EQ|INE009A01021",
            symbol=row.symbol,
            entry_at=row.entry_at,
            exit_at=row.exit_at,
            entry_price=Decimal("100"),
            exit_price=Decimal("101"),
            quantity=1,
            component_costs={"all_in": MoneyV1("0.1", "INR")},
            cost_rule_ids=("nse-test-v1",),
            cost_rule_set_hash="e" * 64,
            execution_contract_version="next-open-v1",
        )
        for row in journey.fold.validation_rows
    )


def test_promotion_research_only_to_shadow_success() -> None:
    journey = governed_training_journey()
    calendar = journey.calendar

    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    # Prepare holdout
    holdout_start = calendar.sessions[48].close_at
    holdout_end = calendar.sessions[52].close_at
    partition, token = create_holdout_partition(
        journey.labels,
        journey.features,
        calendar,
        holdout_id="holdout_promo_001",
        holdout_start=holdout_start,
        holdout_end=holdout_end,
    )
    tracker = HoldoutVaultTracker()
    holdout_report = evaluate_governed_holdout(
        partition,
        token,
        tracker,
        evaluation,
        journey.features,
        journey.labels,
        multiplicity_count=1,
    )

    # Prepare stress report
    cost_quotes = _sample_cost_quotes(journey)
    stress_report = run_mandatory_stress_suite(
        evaluation.ridge_report.decisions,
        journey.fold.validation_rows,
        cost_quotes,
        journey.calendar,
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
    )

    # Gate policy matching fixture metrics
    policy = GatePolicyV1(
        policy_id="test_policy_001",
        min_deflated_sharpe="0",
        max_drawdown="0.5",
        min_fold_sharpe="-1",
        min_attributable_records=1,
        min_holdout_total_return="-0.5",
        require_stress_tests=True,
        require_holdout=True,
    )

    record, model_card = evaluate_promotion(
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
        from_state=PromotionState.RESEARCH_ONLY,
        to_state=PromotionState.SHADOW,
        fold_evaluations=(evaluation,),
        holdout_report=holdout_report,
        stress_report=stress_report,
        policy=policy,
    )

    assert record.failed_gate_codes == (), (
        f"Failed gates: {record.failed_gate_codes}; Gate results: {record.gate_results}"
    )
    assert record.verdict == PromotionState.SHADOW
    assert model_card is not None
    assert model_card.verdict == PromotionState.SHADOW
    assert "max_drawdown_halt_threshold" in model_card.monitoring_limits


def test_promotion_live_verdict_strictly_prohibited() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    with pytest.raises(ModelingError) as exc_info:
        evaluate_promotion(
            candidate_id=journey.features.candidate_id,
            model_id=evaluation.model_id,
            from_state=PromotionState.SHADOW,
            to_state="LIVE",  # type: ignore[arg-type]
            fold_evaluations=(evaluation,),
        )

    assert exc_info.value.code == ModelingFailureCode.INVALID_PARAMETER
    assert "LIVE verdict is prohibited" in str(exc_info.value)


def test_promotion_illegal_forward_skip_rejected() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    # Attempting to jump directly from RESEARCH_ONLY to PAPER_PILOT or PAPER
    with pytest.raises(ModelingError) as exc_info:
        evaluate_promotion(
            candidate_id=journey.features.candidate_id,
            model_id=evaluation.model_id,
            from_state=PromotionState.RESEARCH_ONLY,
            to_state=PromotionState.PAPER_PILOT,
            fold_evaluations=(evaluation,),
        )

    assert exc_info.value.code == ModelingFailureCode.ILLEGAL_STATE_TRANSITION
    assert "skipping intermediate states is prohibited" in str(exc_info.value)


def test_promotion_fails_when_stress_tests_fail() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    # Policy requiring stress tests, but stress report is omitted or failed
    policy = GatePolicyV1(
        policy_id="stress_required_policy",
        min_deflated_sharpe="0",
        require_stress_tests=True,
        require_holdout=False,
    )

    record, model_card = evaluate_promotion(
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
        from_state=PromotionState.RESEARCH_ONLY,
        to_state=PromotionState.SHADOW,
        fold_evaluations=(evaluation,),
        stress_report=None,  # missing stress report
        policy=policy,
    )

    # Must refuse promotion to SHADOW, remaining in RESEARCH_ONLY
    assert record.verdict == PromotionState.RESEARCH_ONLY
    assert PromotionGateId.GATE_MANDATORY_STRESS.value in record.failed_gate_codes
    assert model_card is None


def test_promotion_fails_when_dsr_below_threshold() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    # Set strict DSR threshold of 0.9999
    policy = GatePolicyV1(
        policy_id="high_dsr_policy",
        min_deflated_sharpe="0.9999",
        require_stress_tests=False,
        require_holdout=False,
    )

    record, model_card = evaluate_promotion(
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
        from_state=PromotionState.RESEARCH_ONLY,
        to_state=PromotionState.SHADOW,
        fold_evaluations=(evaluation,),
        policy=policy,
    )

    assert record.verdict == PromotionState.RESEARCH_ONLY
    assert PromotionGateId.GATE_DEFLATED_SHARPE.value in record.failed_gate_codes
    assert model_card is None


def test_promotion_record_draft_generation() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    policy = GatePolicyV1(
        policy_id="draft_policy",
        min_deflated_sharpe="0",
        max_drawdown="0.5",
        require_stress_tests=False,
        require_holdout=False,
    )

    record, _ = evaluate_promotion(
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
        from_state=PromotionState.RESEARCH_ONLY,
        to_state=PromotionState.SHADOW,
        fold_evaluations=(evaluation,),
        policy=policy,
        promotion_id="promo_draft_001",
    )

    draft = draft_from_promotion_record(record)
    assert draft.schema_id == "quantos.promotion_record"
    assert draft.resource_id == "op_promo_draft_001"
    assert draft.metadata["verdict"] == "SHADOW"
