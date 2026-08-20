"""Deterministic governed Slice 4 training journey fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from quant_system.modeling import (
    FeatureDatasetV1,
    FeatureRowV1,
    LabelDatasetV1,
    PartitionedFoldV1,
    RidgeTrialStartV1,
    SessionCalendarV1,
    TrialRegistryV1,
    build_feature_dataset,
    build_label_dataset,
    build_purged_fold,
    fold_spec_hash,
)
from tests.modeling_fixtures import (
    governed_acquisition,
    governed_calendar,
    governed_universe,
    round_trip_cost_quotes,
)


@dataclass(frozen=True, slots=True)
class TrainingJourneyV1:
    calendar: SessionCalendarV1
    features: FeatureDatasetV1
    labels: LabelDatasetV1
    fold: PartitionedFoldV1
    start: RidgeTrialStartV1
    registry: TrialRegistryV1


def governed_training_journey(
    *,
    l2_penalty: str = "1",
    score_threshold: str = "0",
    multiplicity_ordinal: int = 1,
    trial_id: str = "trial_ridge_001",
) -> TrainingJourneyV1:
    count = 55
    calendar = governed_calendar(count)
    universe = governed_universe()
    open_overrides = {
        index: Decimal(100 + index) + (Decimal(3) if index % 4 < 2 else Decimal(-3))
        for index in range(count)
    }
    acquisition = governed_acquisition(
        count=count,
        calendar=calendar,
        universe=universe,
        open_overrides=open_overrides,
    )
    features = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )
    fold = build_purged_fold(
        labels.rows,
        fold_id="fold_ridge_001",
        ordinal=1,
        validation_start=calendar.sessions[40].close_at,
        validation_end=calendar.sessions[47].close_at,
        calendar=calendar,
        embargo_sessions=2,
    )
    start = RidgeTrialStartV1(
        trial_id=trial_id,
        candidate_id=features.candidate_id,
        created_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
        dataset_id=labels.dataset_id,
        dataset_hash=labels.dataset_hash,
        universe_policy_hash=features.universe_authority_hash,
        l2_penalty=l2_penalty,
        score_threshold=score_threshold,
        numpy_seed=0,
        fold_spec_hashes=(fold_spec_hash(fold),),
        source_revision="e6002d2bd73759beb8e4cb5a8354b2eb0e77f8f6",  # pragma: allowlist secret - public Git revision fixture.
        environment_lock_hash="a" * 64,
        architecture="windows-arm64-cpython-3.13-numpy-2.5.2",
        multiplicity_ordinal=multiplicity_ordinal,
    )
    return TrainingJourneyV1(
        calendar=calendar,
        features=features,
        labels=labels,
        fold=fold,
        start=start,
        registry=TrialRegistryV1(starts=(start,), outcomes=()),
    )


def fold_feature_rows(
    journey: TrainingJourneyV1,
    *,
    validation: bool,
) -> tuple[FeatureRowV1, ...]:
    labels = journey.fold.validation_rows if validation else journey.fold.train_rows
    feature_index = {
        (row.candidate_id, row.symbol, row.decision_at): row for row in journey.features.rows
    }
    return tuple(feature_index[(row.candidate_id, row.symbol, row.decision_at)] for row in labels)
