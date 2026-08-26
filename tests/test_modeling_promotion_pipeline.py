"""X-1 regression: the Slice 5 stack must have a real caller that publishes its evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from quant_system.evidence import (
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling import evaluate_governed_ridge_fold
from quant_system.modeling.holdout import (
    HoldoutVaultTracker,
    create_holdout_partition,
)
from quant_system.modeling.promotion import PromotionState
from quant_system.modeling.promotion_pipeline import run_persisted_promotion
from quant_system.modeling.rows import MoneyV1, RoundTripCostQuoteV1
from tests.modeling_training_fixtures import governed_training_journey


def _store(root: Path) -> EvidenceStore:
    return EvidenceStore(
        EvidenceStoreConfig(
            root=root,
            # A stress scenario record and a promotion record are legitimately larger than the
            # 1 KiB other evidence tests use; the store's real default is 16 MiB.
            chunk_uncompressed_bytes=256 * 1024,
            max_bundle_bytes=4 * 1024 * 1024,
            min_free_bytes=0,
            clock=lambda: datetime(2026, 8, 22, tzinfo=UTC),
        )
    )


def _cost_quotes(journey: Any) -> tuple[RoundTripCostQuoteV1, ...]:
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


def _run(tmp_path: Path) -> tuple[EvidenceStore, Any]:
    store = _store(tmp_path / "evidence")
    journey = governed_training_journey()
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
        journey.calendar,
        holdout_id="holdout_pipeline_001",
        holdout_start=journey.calendar.sessions[48].close_at,
        holdout_end=journey.calendar.sessions[52].close_at,
    )
    result = run_persisted_promotion(
        store,
        operation_id="promo_pipeline_op_001",
        holdout=partition,
        unlock_token=token,
        tracker=HoldoutVaultTracker(store),
        evaluation=evaluation,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        cost_quotes=_cost_quotes(journey),
        calendar=journey.calendar,
        multiplicity_count=1,
        from_state=PromotionState.RESEARCH_ONLY,
        to_state=PromotionState.SHADOW,
        evaluation_id="holdout_eval_pipeline_001",
        promotion_id="promo_pipeline_001",
        evaluated_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    )
    return store, result


# test-allow: loop-in-test — iteration over fixed tuple of required schema strings
def test_promotion_pipeline_publishes_every_slice5_evidence_kind(tmp_path: Path) -> None:
    """X-1: holdout, stress and promotion evidence was never published by anything.

    The stack was implemented, tested, and unreachable — `evaluate_promotion`,
    `evaluate_governed_holdout` and `run_mandatory_stress_suite` had no caller in src/
    outside their own defining modules.
    """
    store, _ = _run(tmp_path)

    published = {
        verified.manifest.schema_id
        for resource_type in (
            EvidenceResourceType.OPERATION,
            EvidenceResourceType.MODEL,
            EvidenceResourceType.BUNDLE,
        )
        for verified in store.list_verified(resource_type)
    }

    for schema in (
        "quantos.holdout_evaluation_start",
        # draft_from_holdout_report emits per-decision records under this schema id, not
        # the _HOLDOUT_REPORT_SCHEMA constant, which names nothing that is published.
        "quantos.holdout_strategy_decision",
        "quantos.holdout_evaluation_outcome",
        "quantos.stress_report",
        "quantos.promotion_record",
    ):
        assert schema in published, f"{schema} was never published; found {sorted(published)}"


def test_promotion_pipeline_returns_the_governed_verdict(tmp_path: Path) -> None:
    """The pipeline must surface the real verdict, not assume success."""
    _, result = _run(tmp_path)

    assert result.holdout_report.holdout_id == "holdout_pipeline_001"
    assert result.stress_report.scenario_results
    assert result.promotion_record.promotion_id == "promo_pipeline_001"
    assert result.promotion_record.verdict in set(PromotionState)
    # A model card exists only on a successful forward promotion.
    if result.promotion_record.verdict != PromotionState.SHADOW:
        assert result.model_card is None


def test_promotion_pipeline_consumes_the_holdout_exactly_once(tmp_path: Path) -> None:
    """The pipeline must not defeat the single-use vault it depends on (see H-2)."""
    store, _ = _run(tmp_path)

    fresh = HoldoutVaultTracker(store)
    assert fresh.is_consumed("holdout_pipeline_001")
