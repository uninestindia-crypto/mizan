"""Deterministic governed Slice 4 training journey fixtures."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal

from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.modeling import (
    FeatureDatasetV1,
    FeatureRowV1,
    LabelDatasetV1,
    LabelRowV1,
    PartitionedFoldV1,
    RidgeTrialStartV1,
    SessionCalendarV1,
    TrialRegistryV1,
    build_feature_dataset,
    build_label_dataset,
    build_purged_fold,
    fold_spec_hash,
)
from quant_system.modeling.rows import (
    FEATURE_ROW_SCHEMA,
    LABEL_ROW_SCHEMA,
    derived_dataset_hash,
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


def rebound_journey(
    journey: TrainingJourneyV1,
    fold: PartitionedFoldV1,
) -> TrainingJourneyV1:
    """Re-pin a journey's trial start and registry onto a rewritten fold."""
    start = replace(journey.start, fold_spec_hashes=(fold_spec_hash(fold),))
    return replace(
        journey,
        fold=fold,
        start=start,
        registry=TrialRegistryV1(starts=(start,), outcomes=()),
    )


def leaky_zero_removal_fold(journey: TrainingJourneyV1) -> PartitionedFoldV1:
    """Rebuild the governed fold with every purged and embargoed row back in training.

    Reproduces the Red Team Blocker 1 attack: the removal evidence is emptied, the purge
    boundary is collapsed onto the validation start, and every summary field is recomputed so
    the fold is internally consistent and correctly hashed.
    """
    removed_keys = {*journey.fold.purged_record_keys, *journey.fold.embargoed_record_keys}
    train_rows = tuple(
        row
        for row in journey.labels.rows
        if row.decision_at < journey.fold.spec.validation_start
        and (
            row.record_key in removed_keys
            or row.record_key in {member.record_key for member in journey.fold.train_rows}
        )
    )
    spec = replace(
        journey.fold.spec,
        train_end=train_rows[-1].decision_at,
        purge_start=journey.fold.spec.validation_start,
        purge_end=journey.fold.spec.validation_start,
        train_row_count=len(train_rows),
        train_class_balance=_fixture_class_balance(train_rows),
        train_hash=_fixture_rows_hash(train_rows),
    )
    return replace(
        journey.fold,
        spec=spec,
        train_rows=train_rows,
        purged_record_keys=(),
        embargoed_record_keys=(),
    )


def symbol_collision_features(
    journey: TrainingJourneyV1,
) -> tuple[FeatureDatasetV1, LabelDatasetV1]:
    """Duplicate every feature row under a second instrument sharing one symbol.

    Reproduces the Red Team Major 3 attack. Each clone keeps the symbol and decision time but
    takes a different ``provider_instrument_id`` and constant features, so record keys stay
    unique and the dataset identity is rebuilt to be internally consistent.
    """
    clones = tuple(
        replace(
            row,
            provider_instrument_id="ZZZ_EQ|INE009A01021",
            features=dict.fromkeys(row.features, "0.5"),
        )
        for row in journey.features.rows
    )
    rows = tuple(
        sorted(
            journey.features.rows + clones,
            key=lambda row: (row.candidate_id, row.decision_at, row.provider_instrument_id),
        )
    )
    poisoned = _rebind_feature_identity(replace(journey.features, rows=rows))
    labels = _rebind_label_identity(
        replace(
            journey.labels,
            feature_dataset_id=poisoned.dataset_id,
            feature_dataset_hash=poisoned.dataset_hash,
        )
    )
    return poisoned, labels


def _rebind_feature_identity(dataset: FeatureDatasetV1) -> FeatureDatasetV1:
    metadata = dataset.metadata_dict()
    metadata.pop("dataset_id")
    metadata.pop("dataset_hash")
    dataset_hash = derived_dataset_hash(FEATURE_ROW_SCHEMA, metadata, dataset.rows)
    return replace(dataset, dataset_hash=dataset_hash, dataset_id=f"dset_{dataset_hash[:24]}")


def _rebind_label_identity(dataset: LabelDatasetV1) -> LabelDatasetV1:
    metadata = dataset.metadata_dict()
    metadata.pop("dataset_id")
    metadata.pop("dataset_hash")
    dataset_hash = derived_dataset_hash(LABEL_ROW_SCHEMA, metadata, dataset.rows)
    return replace(dataset, dataset_hash=dataset_hash, dataset_id=f"dset_{dataset_hash[:24]}")


def _fixture_class_balance(rows: tuple[LabelRowV1, ...]) -> dict[str, int]:
    return {
        "DOWN": sum(row.target == "DOWN" for row in rows),
        "UP": sum(row.target == "UP" for row in rows),
    }


def _fixture_rows_hash(rows: tuple[LabelRowV1, ...]) -> str:
    return canonical_sha256(
        {
            "records": [row.to_canonical_dict() for row in rows],
            "schema_id": "quantos.fold_label_rows",
            "schema_version": 1,
        }
    )
