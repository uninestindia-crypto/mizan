"""Regressions proving published model evidence must bind its own decision records."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.evidence import (
    EvidenceDraft,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    evaluate_governed_ridge_fold,
    succeeded_outcome,
)
from quant_system.modeling.persisted_trials import load_persisted_trial_registry
from quant_system.modeling.training_evidence import (
    draft_from_ridge_evaluation,
    draft_from_trial_outcome,
    draft_from_trial_start,
)
from tests.modeling_training_fixtures import governed_training_journey

STORE_TIME = datetime(2026, 8, 20, 12, 10, tzinfo=UTC)
ENDED_AT = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)


def test_forged_model_metrics_fail_closed_even_when_every_hash_is_rebound(
    tmp_path: Path,
) -> None:
    """Red Team Blocker 2: a rewritten model claiming Sharpe 99 must not verify.

    The forgery leaves each report's ``metrics_hash`` untouched, then recomputes the evaluation
    hash, model id, and terminal outcome exactly as the reader derives them, so every identity
    check the store performs still agrees. Only re-deriving the metrics from the published
    decisions can catch it.
    """
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )
    honest = draft_from_ridge_evaluation(
        evaluation,
        start=journey.start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
    )
    forged = _forge_metrics(honest, sharpe_ratio="99", total_return="12.5")

    assert evaluation.strategy_reports[0].metrics.sharpe_ratio != "99"

    store = _store(tmp_path)
    store.commit(draft_from_trial_start(journey.start), operation_id="op-start")
    store.commit(forged, operation_id="op-model")
    store.commit(
        draft_from_trial_outcome(
            succeeded_outcome(
                journey.start,
                ended_at=ENDED_AT,
                result_hash=str(forged.metadata["evaluation_hash"]),
            )
        ),
        operation_id="op-outcome",
    )

    with pytest.raises(ModelingError) as captured:
        load_persisted_trial_registry(store)

    assert captured.value.code == ModelingFailureCode.MULTIPLICITY_INVALID


def test_honest_model_evidence_still_loads_after_rederivation(tmp_path: Path) -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )
    store = _store(tmp_path)
    store.commit(draft_from_trial_start(journey.start), operation_id="op-start")
    store.commit(
        draft_from_ridge_evaluation(
            evaluation,
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
        ),
        operation_id="op-model",
    )
    store.commit(
        draft_from_trial_outcome(
            succeeded_outcome(
                journey.start,
                ended_at=ENDED_AT,
                result_hash=evaluation.evaluation_hash,
            )
        ),
        operation_id="op-outcome",
    )

    registry = load_persisted_trial_registry(store)

    assert registry.multiplicity_count == 1
    assert registry.outcomes[0].result_hash == evaluation.evaluation_hash


def _forge_metrics(draft: EvidenceDraft, *, sharpe_ratio: str, total_return: str) -> EvidenceDraft:
    metadata: dict[str, Any] = copy.deepcopy(dict(draft.metadata))
    records = tuple(copy.deepcopy(record) for record in draft.records)
    summaries = copy.deepcopy(metadata["strategy_reports"])
    summaries[0]["metrics"]["sharpe_ratio"] = sharpe_ratio
    summaries[0]["metrics"]["total_return"] = total_return
    metadata["strategy_reports"] = summaries
    metadata["deflated_sharpe_ratio"] = "0.999999999999"
    evaluation_hash = canonical_sha256(_unsigned_evaluation(metadata, records, summaries))
    metadata["evaluation_hash"] = evaluation_hash
    metadata["model_id"] = f"model_{evaluation_hash[:24]}"
    return EvidenceDraft(
        resource_type=EvidenceResourceType.MODEL,
        resource_id=f"model_{evaluation_hash[:24]}",
        schema_id="quantos.fold_strategy_decision",
        schema_version=1,
        metadata=metadata,
        records=records,
        total_order=("strategy_id", "decision_at", "symbol"),
    )


def _unsigned_evaluation(
    metadata: dict[str, Any],
    records: tuple[dict[str, Any], ...],
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    reports = [
        {
            "allocation_contract": "EQUAL_WEIGHT_ACTIVE_LONGS_PER_DECISION_TIME",
            "decisions": [
                record for record in records if record.get("strategy_id") == summary["strategy_id"]
            ],
            "metrics": dict(summary["metrics"]),
            "metrics_hash": summary["metrics_hash"],
            "prediction_hash": summary["prediction_hash"],
            "strategy_id": summary["strategy_id"],
        }
        for summary in summaries
    ]
    return {
        "candidate_id": metadata["candidate_id"],
        "deflated_sharpe_ratio": metadata["deflated_sharpe_ratio"],
        "fitted_state": dict(metadata["fitted_state"]),
        "fold_spec_hash": metadata["fold_spec_hash"],
        "multiplicity_count": metadata["multiplicity_count"],
        "preprocessing": dict(metadata["preprocessing"]),
        "schema_id": "quantos.ridge_fold_evaluation",
        "schema_version": 1,
        "strategy_reports": reports,
        "trial_id": metadata["trial_id"],
        "verdict": "RESEARCH_ONLY",
    }


def _store(root: Path) -> EvidenceStore:
    return EvidenceStore(EvidenceStoreConfig(root=root, min_free_bytes=0, clock=lambda: STORE_TIME))


def test_undercounted_model_publish_no_longer_bricks_the_catalog(tmp_path: Path) -> None:
    """Red Team Minor 2 / Blocker 3C: publishing an under-counted evaluation was destructive.

    A caller-invented registry still produces a number from the pure evaluation API, but the
    catalog must stay readable and the next governed trial must still be possible.
    """
    journey = governed_training_journey()
    store = _store(tmp_path)
    store.commit(draft_from_trial_start(journey.start), operation_id="op-start")

    fabricated = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )
    store.commit(
        draft_from_ridge_evaluation(
            fabricated,
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
        ),
        operation_id="op-model",
    )
    store.commit(
        draft_from_trial_outcome(
            succeeded_outcome(
                journey.start,
                ended_at=ENDED_AT,
                result_hash=fabricated.evaluation_hash,
            )
        ),
        operation_id="op-outcome",
    )

    registry = load_persisted_trial_registry(store)
    report = store.rebuild_index()

    assert registry.multiplicity_count == 1
    assert report.invalid_resource_ids == ()
    assert report.orphan_blob_hashes == ()
