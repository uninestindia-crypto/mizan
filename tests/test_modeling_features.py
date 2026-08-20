"""Point-in-time and deterministic feature-contract tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import ROUND_DOWN, ROUND_UP, Decimal, localcontext

import pytest

from quant_system.data.market_data import DatasetStatus, HistoricalAcquisition, SourceStatus
from quant_system.data.market_data_evidence import decimal_text
from quant_system.modeling import (
    FEATURE_NAMES_V1,
    ModelingError,
    ModelingFailureCode,
    build_feature_dataset,
)
from tests.modeling_fixtures import (
    INSTRUMENT_KEY,
    governed_acquisition,
    governed_calendar,
    governed_universe,
)


def test_six_feature_rows_are_exact_point_in_time_and_repeatable() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    acquisition = governed_acquisition(count=26, calendar=calendar, universe=universe)

    first = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    second = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)

    assert first == second
    assert first.dataset_id.startswith("dset_")
    assert len(first.rows) == 6
    row = first.rows[0]
    assert tuple(row.features) == FEATURE_NAMES_V1
    assert dict(row.features) == {
        "return_1": "0.008368200837",
        "return_5": "0.04329004329",
        "return_10": "0.090497737557",
        "rsi_14_centered": "1",
        "sma_20_distance": "0.078838174274",
        "atr_14_normalized": "0.02489626556",
    }
    assert row.decision_at == calendar.sessions[20].close_at
    assert row.information_cutoff_at == calendar.sessions[20].close_at
    assert row.universe_authority_hash == universe.authority.content_hash
    assert row.provider_instrument_id == INSTRUMENT_KEY


def test_post_cutoff_input_fails_with_the_offending_record() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    acquisition = governed_acquisition(
        count=26,
        calendar=calendar,
        universe=universe,
        delayed_source_index=0,
    )

    with pytest.raises(ModelingError) as captured:
        build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)

    assert captured.value.code == ModelingFailureCode.POINT_IN_TIME_VIOLATION
    assert captured.value.offending_record_key is not None
    assert "source_row_index=0" in captured.value.offending_record_key


@pytest.mark.parametrize(
    ("missing_corporate", "missing_universe", "expected_code"),
    [
        (True, False, ModelingFailureCode.CORPORATE_ACTION_AUTHORITY_MISSING),
        (False, True, ModelingFailureCode.UNIVERSE_AUTHORITY_MISSING),
    ],
)
# test-allow: no-assertion - the checker cannot parse this multiline parametrized signature.
def test_missing_authority_blocks_governed_feature_construction(
    missing_corporate: bool,
    missing_universe: bool,
    expected_code: ModelingFailureCode,
) -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    acquisition = governed_acquisition(
        count=26,
        calendar=calendar,
        universe=universe,
        corporate_authority=not missing_corporate,
    )
    if missing_universe:
        manifest = replace(acquisition.manifest, historical_universe_authority=None)
        acquisition = _replace_manifest_identity(acquisition, manifest)

    with pytest.raises(ModelingError) as captured:
        build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)

    assert captured.value.code == expected_code


def test_instrument_not_in_effective_historical_universe_is_rejected() -> None:
    calendar = governed_calendar(26)
    excluded = governed_universe(members=("NSE_EQ|INE467B01029",))
    acquisition = governed_acquisition(count=26, calendar=calendar, universe=excluded)

    with pytest.raises(ModelingError) as captured:
        build_feature_dataset(acquisition, "cand_ridge_v1", calendar, excluded)

    assert captured.value.code == ModelingFailureCode.UNIVERSE_MEMBER_INELIGIBLE


def test_partial_acquisition_cannot_be_used_for_governed_features() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    acquisition = governed_acquisition(count=26, calendar=calendar, universe=universe)
    partial_manifest = replace(
        acquisition.manifest,
        status=DatasetStatus.PARTIAL,
        source_status=SourceStatus.PARTIAL,
    )
    partial = _replace_manifest_identity(acquisition, partial_manifest)

    with pytest.raises(ModelingError) as captured:
        build_feature_dataset(partial, "cand_ridge_v1", calendar, universe)

    assert captured.value.code == ModelingFailureCode.DATASET_NOT_GOVERNED


def test_changed_future_outcome_does_not_change_earlier_feature_inputs() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    original = governed_acquisition(count=26, calendar=calendar, universe=universe)
    changed = governed_acquisition(
        count=26,
        calendar=calendar,
        universe=universe,
        close_overrides={25: original.records[25].close + 100},
    )

    original_row = build_feature_dataset(original, "cand_ridge_v1", calendar, universe).rows[0]
    changed_row = build_feature_dataset(changed, "cand_ridge_v1", calendar, universe).rows[0]

    assert original_row.features == changed_row.features
    assert original_row.preprocessing_input_hash == changed_row.preprocessing_input_hash
    assert original_row.dataset_hash != changed_row.dataset_hash


def test_record_order_change_is_rejected() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    acquisition = governed_acquisition(count=26, calendar=calendar, universe=universe)
    records = list(acquisition.records)
    records[20], records[21] = records[21], records[20]
    reordered = governed_acquisition(count=26, calendar=calendar, universe=universe)
    reordered = replace(reordered, records=tuple(records))

    with pytest.raises(ModelingError) as captured:
        build_feature_dataset(reordered, "cand_ridge_v1", calendar, universe)

    assert captured.value.code in {
        ModelingFailureCode.DATASET_INTEGRITY_INVALID,
        ModelingFailureCode.RECORD_ORDER_INVALID,
    }


def test_authority_published_after_decision_is_rejected() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    late_universe = governed_universe(
        publication_date=calendar.sessions[20].exchange_date + timedelta(days=1),
    )
    acquisition = governed_acquisition(count=26, calendar=calendar, universe=universe)

    with pytest.raises(ModelingError) as captured:
        build_feature_dataset(acquisition, "cand_ridge_v1", calendar, late_universe)

    assert captured.value.code == ModelingFailureCode.UNIVERSE_AUTHORITY_MISMATCH


def test_same_day_date_only_authority_is_ambiguous_and_fails_closed() -> None:
    calendar = governed_calendar(26)
    same_day_universe = governed_universe(
        publication_date=calendar.sessions[20].exchange_date,
    )
    acquisition = governed_acquisition(
        count=26,
        calendar=calendar,
        universe=same_day_universe,
    )

    with pytest.raises(ModelingError) as captured:
        build_feature_dataset(
            acquisition,
            "cand_ridge_v1",
            calendar,
            same_day_universe,
        )

    assert captured.value.code == ModelingFailureCode.UNIVERSE_AUTHORITY_NOT_EFFECTIVE


def test_feature_hash_and_decimal_text_ignore_process_decimal_context() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    acquisition = governed_acquisition(count=26, calendar=calendar, universe=universe)

    with localcontext() as context:
        context.prec = 9
        context.rounding = ROUND_DOWN
        first = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
        first_decimal = decimal_text(Decimal("123456789.123456789000"))
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_UP
        second = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
        second_decimal = decimal_text(Decimal("123456789.123456789000"))

    assert first == second
    assert first_decimal == second_decimal == "123456789.123456789"


@pytest.mark.parametrize(
    "close_overrides",
    [
        {index: Decimal("150") for index in range(26)},
        {index: Decimal(200 - index) for index in range(26)},
        {index: Decimal(150 + (index % 2)) for index in range(26)},
    ],
)
# test-allow: no-assertion - checker cannot parse this multiline parametrized signature.
def test_feature_family_remains_finite_across_flat_falling_and_alternating_paths(
    close_overrides: dict[int, Decimal],
) -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    acquisition = governed_acquisition(
        count=26,
        calendar=calendar,
        universe=universe,
        close_overrides=close_overrides,
    )

    dataset = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)

    assert len(dataset.rows) == 6
    assert all(
        Decimal(value).is_finite() for row in dataset.rows for value in row.features.values()
    )


def _replace_manifest_identity(
    acquisition: HistoricalAcquisition,
    manifest: object,
) -> HistoricalAcquisition:
    from quant_system.data.market_data import DatasetManifest
    from quant_system.data.market_data_evidence import canonical_sha256

    if not isinstance(manifest, DatasetManifest):
        raise TypeError("manifest fixture must be a DatasetManifest")
    unsigned = replace(manifest, dataset_id="", manifest_hash="")
    manifest_hash = canonical_sha256(unsigned.to_canonical_dict(include_identity=False))
    signed = replace(
        unsigned,
        dataset_id=f"dset_{manifest_hash[:24]}",
        manifest_hash=manifest_hash,
    )
    return replace(acquisition, manifest=signed)
