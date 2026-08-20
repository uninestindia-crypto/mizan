"""Purged and embargoed chronological partition tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta, timezone
from decimal import Decimal

import pytest

from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    build_feature_dataset,
    build_label_dataset,
    build_purged_fold,
)
from quant_system.modeling.rows import (
    LABEL_ROW_SCHEMA,
    derived_dataset_hash,
    require_label_dataset_identity,
)
from tests.modeling_fixtures import (
    governed_acquisition,
    governed_calendar,
    governed_universe,
    round_trip_cost_quotes,
)


def test_walk_forward_fold_purges_overlap_and_embargoes_two_sessions() -> None:
    calendar = governed_calendar(35)
    universe = governed_universe()
    acquisition = governed_acquisition(count=35, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )
    validation_start = calendar.sessions[28].close_at
    validation_end = calendar.sessions[29].close_at

    first = build_purged_fold(
        labels.rows,
        fold_id="fold_001",
        ordinal=1,
        validation_start=validation_start,
        validation_end=validation_end,
        calendar=calendar,
        embargo_sessions=2,
    )
    second = build_purged_fold(
        labels.rows,
        fold_id="fold_001",
        ordinal=1,
        validation_start=validation_start,
        validation_end=validation_end,
        calendar=calendar,
        embargo_sessions=2,
    )

    assert first == second
    assert len(first.train_rows) == 6
    assert len(first.validation_rows) == 2
    assert len(first.purged_record_keys) == 1
    assert len(first.embargoed_record_keys) == 1
    assert all(row.exit_at < validation_start for row in first.train_rows)
    assert first.spec.train_row_count == 6
    assert first.spec.validation_row_count == 2
    assert first.spec.embargo_sessions == 2
    assert first.spec.label_horizon_sessions == 2
    assert first.spec.train_hash != first.spec.validation_hash


def test_embargo_shorter_than_label_horizon_is_rejected() -> None:
    calendar = governed_calendar(35)
    universe = governed_universe()
    acquisition = governed_acquisition(count=35, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )

    with pytest.raises(ModelingError) as captured:
        build_purged_fold(
            labels.rows,
            fold_id="fold_001",
            ordinal=1,
            validation_start=calendar.sessions[28].close_at,
            validation_end=calendar.sessions[29].close_at,
            calendar=calendar,
            embargo_sessions=1,
        )

    assert captured.value.code == ModelingFailureCode.EMBARGO_TOO_SHORT


def test_partition_rejects_non_chronological_input() -> None:
    calendar = governed_calendar(35)
    universe = governed_universe()
    acquisition = governed_acquisition(count=35, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )
    unordered = (labels.rows[1], labels.rows[0], *labels.rows[2:])

    with pytest.raises(ModelingError) as captured:
        build_purged_fold(
            unordered,
            fold_id="fold_001",
            ordinal=1,
            validation_start=calendar.sessions[28].close_at,
            validation_end=calendar.sessions[29].close_at,
            calendar=calendar,
            embargo_sessions=2,
        )

    assert captured.value.code == ModelingFailureCode.RECORD_ORDER_INVALID


def test_partition_revalidates_label_session_chronology() -> None:
    calendar = governed_calendar(35)
    universe = governed_universe()
    acquisition = governed_acquisition(count=35, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )
    changed_first = replace(labels.rows[0], exit_at=calendar.sessions[23].open_at)
    changed_rows = (changed_first, *labels.rows[1:])

    with pytest.raises(ModelingError) as captured:
        build_purged_fold(
            changed_rows,
            fold_id="fold_001",
            ordinal=1,
            validation_start=calendar.sessions[28].close_at,
            validation_end=calendar.sessions[29].close_at,
            calendar=calendar,
            embargo_sessions=2,
        )

    assert captured.value.code == ModelingFailureCode.PARTITION_INVALID


def test_timezone_representation_cannot_bypass_session_embargo(  # test-allow: loop-in-test - fixture guarantees the embargo target exists.
) -> None:
    calendar = governed_calendar(35)
    universe = governed_universe()
    acquisition = governed_acquisition(count=35, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )
    utc_minus_twelve = timezone(-timedelta(hours=12))
    shifted_rows = tuple(
        replace(
            row,
            decision_at=row.decision_at.astimezone(utc_minus_twelve),
            order_at=row.order_at.astimezone(utc_minus_twelve),
        )
        for row in labels.rows
    )

    fold = build_purged_fold(
        shifted_rows,
        fold_id="fold_001",
        ordinal=1,
        validation_start=calendar.sessions[28].close_at,
        validation_end=calendar.sessions[29].close_at,
        calendar=calendar,
        embargo_sessions=2,
    )

    assert len(fold.train_rows) == 6
    assert len(fold.embargoed_record_keys) == 1


def test_multi_symbol_dataset_and_fold_share_chronological_order() -> None:
    calendar = governed_calendar(35)
    universe = governed_universe()
    acquisition = governed_acquisition(count=35, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    base = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )
    rows = tuple(
        sorted(
            (replace(row, symbol=symbol) for row in base.rows for symbol in ("AAA", "BBB")),
            key=lambda row: (row.decision_at, row.symbol),
        )
    )
    provisional = replace(base, dataset_id="dset_provisional", dataset_hash="0" * 64, rows=rows)
    metadata = provisional.metadata_dict()
    metadata.pop("dataset_id")
    metadata.pop("dataset_hash")
    dataset_hash = derived_dataset_hash(LABEL_ROW_SCHEMA, metadata, rows)
    labels = replace(
        provisional,
        dataset_id=f"dset_{dataset_hash[:24]}",
        dataset_hash=dataset_hash,
    )

    require_label_dataset_identity(labels)
    fold = build_purged_fold(
        labels.rows,
        fold_id="fold_multi_001",
        ordinal=1,
        validation_start=calendar.sessions[28].close_at,
        validation_end=calendar.sessions[29].close_at,
        calendar=calendar,
        embargo_sessions=2,
    )

    assert len(fold.validation_rows) == 4
    assert tuple((row.decision_at, row.symbol) for row in fold.validation_rows) == tuple(
        sorted((row.decision_at, row.symbol) for row in fold.validation_rows)
    )
