"""End-to-end governed behavior for DSR moment-bound equality and failures."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.analytics.errors import MultiplicityError, MultiplicityFailureCode
from quant_system.analytics.multiplicity import OverfittingDiagnostics
from quant_system.evidence import EvidenceResourceType, EvidenceStore, EvidenceStoreConfig
from quant_system.modeling import (
    SCORE_KIND_V1,
    FoldDecisionV1,
    ModelingError,
    ModelingFailureCode,
    StrategyFoldReportV1,
    run_persisted_ridge_trial,
)
from quant_system.modeling.metrics import calculate_strategy_metrics
from quant_system.modeling.validation import deflate_ridge_report
from tests.modeling_training_fixtures import governed_training_journey


def _two_point_ridge_report() -> StrategyFoldReportV1:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    decisions = tuple(
        FoldDecisionV1(
            strategy_id="RIDGE",
            symbol="NIFTY50",
            decision_at=start + timedelta(days=index),
            predicted_target="UP" if index == 29 else "DOWN",
            actual_target="UP",
            realized_net_return="0.05" if index == 29 else "0",
            score="1" if index == 29 else "-1",
            score_kind=SCORE_KIND_V1,
        )
        for index in range(30)
    )
    return StrategyFoldReportV1(
        strategy_id="RIDGE",
        decisions=decisions,
        metrics=calculate_strategy_metrics(decisions),
    )


def test_governed_deflation_accepts_a_valid_two_point_return_series() -> None:
    report = _two_point_ridge_report()

    probability = Decimal(deflate_ridge_report(report, multiplicity_count=2))

    assert Decimal("0") <= probability <= Decimal("1")


def test_impossible_moments_persist_the_specific_terminal_failure_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journey = governed_training_journey()
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path / "evidence", min_free_bytes=0))

    def reject_impossible_moments(**_kwargs: object) -> float:
        raise MultiplicityError(
            MultiplicityFailureCode.MOMENT_CONSTRAINT_INVALID,
            "forced impossible moments",
        )

    monkeypatch.setattr(
        OverfittingDiagnostics,
        "deflated_sharpe_ratio",
        staticmethod(reject_impossible_moments),
    )

    with pytest.raises(ModelingError) as captured:
        run_persisted_ridge_trial(
            store,
            operation_id="op-invalid-moments",
            start=journey.start,
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=journey.start.created_at + timedelta(minutes=1),
        )

    outcome = store.open_verified(
        EvidenceResourceType.TRIAL,
        journey.start.outcome_resource_id,
    )
    assert captured.value.code is ModelingFailureCode.MOMENT_CONSTRAINT_INVALID
    assert outcome.records[0]["state"] == "FAILED"
    assert outcome.records[0]["failure_codes"] == ["MOMENT_CONSTRAINT_INVALID"]
