"""Executable next-open label and derived-evidence tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.data.market_data import HistoricalAcquisition
from quant_system.evidence import EvidenceResourceType, EvidenceStore, EvidenceStoreConfig
from quant_system.modeling import (
    FeatureDatasetV1,
    HistoricalUniverseSnapshotV1,
    ModelingError,
    ModelingFailureCode,
    MoneyV1,
    RoundTripCostQuoteV1,
    SessionCalendarV1,
    build_feature_dataset,
    build_label_dataset,
    draft_from_feature_dataset,
    draft_from_label_dataset,
)
from quant_system.modeling.rows import FEATURE_ROW_SCHEMA, derived_dataset_hash
from tests.modeling_fixtures import (
    governed_acquisition,
    governed_calendar,
    governed_universe,
    round_trip_cost_quotes,
)


def test_label_uses_first_later_open_then_following_open_and_costs() -> None:
    calendar, universe, acquisition, features = _feature_inputs(26)
    quotes = round_trip_cost_quotes(acquisition, calendar, cost=Decimal("1.1"))

    labels = build_label_dataset(features, acquisition, calendar, quotes)

    row = labels.rows[0]
    assert row.decision_at == calendar.sessions[20].close_at
    assert row.order_at == row.decision_at
    assert row.entry_at == calendar.sessions[21].open_at
    assert row.exit_at == calendar.sessions[22].open_at
    assert row.entry_price == "121"
    assert row.exit_price == "122"
    assert row.gross_return == "0.00826446281"
    assert row.net_return == "-0.000826446281"
    assert row.target == "DOWN"
    assert row.component_costs["all_in"].amount == "1.1"
    assert labels == build_label_dataset(features, acquisition, calendar, quotes)


def test_zero_net_return_is_down() -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("1")),
    )

    assert labels.rows[0].net_return == "0"
    assert labels.rows[0].target == "DOWN"


def test_cost_change_changes_label_and_derived_hash() -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    low_cost = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )
    high_cost = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("1.1")),
    )

    assert low_cost.rows[0].target == "UP"
    assert high_cost.rows[0].target == "DOWN"
    assert low_cost.dataset_hash != high_cost.dataset_hash


def test_future_open_changes_label_but_not_earlier_feature_values() -> None:
    calendar = governed_calendar(26)
    universe = governed_universe()
    original = governed_acquisition(count=26, calendar=calendar, universe=universe)
    changed = governed_acquisition(
        count=26,
        calendar=calendar,
        universe=universe,
        open_overrides={22: Decimal("130")},
    )
    original_features = build_feature_dataset(original, "cand_ridge_v1", calendar, universe)
    changed_features = build_feature_dataset(changed, "cand_ridge_v1", calendar, universe)

    original_labels = build_label_dataset(
        original_features,
        original,
        calendar,
        round_trip_cost_quotes(original, calendar, cost=Decimal("0.1")),
    )
    changed_labels = build_label_dataset(
        changed_features,
        changed,
        calendar,
        round_trip_cost_quotes(changed, calendar, cost=Decimal("0.1")),
    )

    assert original_features.rows[0].features == changed_features.rows[0].features
    assert (
        original_features.rows[0].preprocessing_input_hash
        == changed_features.rows[0].preprocessing_input_hash
    )
    assert original_labels.rows[0].exit_price == "122"
    assert changed_labels.rows[0].exit_price == "130"
    assert original_labels.dataset_hash != changed_labels.dataset_hash


def test_tiny_positive_economic_return_rounds_to_zero_and_is_down() -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(
            acquisition,
            calendar,
            cost=Decimal("0.999999999999999999999999"),
        ),
    )

    assert labels.rows[0].net_return == "0"
    assert labels.rows[0].target == "DOWN"


def test_missing_and_duplicate_cost_quotes_fail_closed() -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    quotes = round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1"))

    with pytest.raises(ModelingError) as missing:
        build_label_dataset(features, acquisition, calendar, quotes[1:])
    with pytest.raises(ModelingError) as duplicate:
        build_label_dataset(features, acquisition, calendar, (*quotes, quotes[0]))

    assert missing.value.code == ModelingFailureCode.COST_QUOTE_MISSING
    assert duplicate.value.code == ModelingFailureCode.COST_QUOTE_MISMATCH


def test_unused_mismatched_cost_quote_is_rejected() -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    quotes = round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1"))
    unrelated = RoundTripCostQuoteV1(
        provider_instrument_id="NSE_EQ|INE467B01029",
        symbol="TCS",
        entry_at=calendar.sessions[0].open_at,
        exit_at=calendar.sessions[1].open_at,
        entry_price=Decimal("100"),
        exit_price=Decimal("101"),
        quantity=1,
        component_costs={"all_in": MoneyV1(Decimal("0.1"), "INR")},
        cost_rule_ids=("nse-test-v1",),
        cost_rule_set_hash="f" * 64,
        execution_contract_version="next-open-v1",
    )

    with pytest.raises(ModelingError) as captured:
        build_label_dataset(features, acquisition, calendar, (*quotes, unrelated))

    assert captured.value.code == ModelingFailureCode.COST_QUOTE_MISMATCH


def test_cost_rule_set_hash_changes_derived_identity_even_when_amounts_match() -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    original_quotes = round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1"))
    changed_first = _copy_quote(original_quotes[0], cost_rule_set_hash="f" * 64)
    changed_quotes = (changed_first, *original_quotes[1:])

    original = build_label_dataset(features, acquisition, calendar, original_quotes)
    changed = build_label_dataset(features, acquisition, calendar, changed_quotes)

    assert original.rows == changed.rows
    assert original.dataset_hash != changed.dataset_hash


def test_nonfinite_or_negative_cost_money_is_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        MoneyV1(Decimal("NaN"), "INR")
    with pytest.raises(ValueError, match="negative"):
        MoneyV1(Decimal("-0.01"), "INR")
    with pytest.raises(TypeError, match="Decimal|string"):
        MoneyV1(0.1, "INR")  # type: ignore[arg-type]


def test_rehashed_feature_instrument_swap_cannot_relabel_another_asset(  # test-allow: loop-in-test - fixture always creates governed feature rows.
) -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    swapped_rows = tuple(
        replace(
            row,
            provider_instrument_id="NSE_EQ|INE467B01029",
            symbol="TCS",
        )
        for row in features.rows
    )
    unsigned_metadata = features.metadata_dict()
    unsigned_metadata.pop("dataset_id")
    unsigned_metadata.pop("dataset_hash")
    swapped_hash = derived_dataset_hash(FEATURE_ROW_SCHEMA, unsigned_metadata, swapped_rows)
    swapped = replace(
        features,
        dataset_id=f"dset_{swapped_hash[:24]}",
        dataset_hash=swapped_hash,
        rows=swapped_rows,
    )

    with pytest.raises(ModelingError) as captured:
        build_label_dataset(
            swapped,
            acquisition,
            calendar,
            round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
        )

    assert captured.value.code == ModelingFailureCode.DATASET_INTEGRITY_INVALID


def test_missing_internal_session_open_fails_closed() -> None:
    calendar = governed_calendar(27)
    universe = governed_universe()
    acquisition = governed_acquisition(
        count=27,
        calendar=calendar,
        universe=universe,
        omitted_source_indexes=frozenset({21}),
    )
    with pytest.raises(ModelingError) as captured:
        build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)

    assert captured.value.code == ModelingFailureCode.CALENDAR_SESSION_MISSING
    assert calendar.sessions[21].exchange_date.isoformat() in str(captured.value)


def test_cost_quote_must_bind_exact_fill_chronology_and_price() -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    quotes = list(round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")))
    quotes[0] = RoundTripCostQuoteV1(
        provider_instrument_id=quotes[0].provider_instrument_id,
        symbol=quotes[0].symbol,
        entry_at=quotes[0].entry_at,
        exit_at=quotes[0].exit_at,
        entry_price=Decimal("999"),
        exit_price=quotes[0].exit_price_decimal,
        quantity=1,
        component_costs={"all_in": MoneyV1(Decimal("0.1"), "INR")},
        cost_rule_ids=("nse-test-v1",),
        cost_rule_set_hash="e" * 64,
        execution_contract_version="next-open-v1",
    )

    with pytest.raises(ModelingError) as captured:
        build_label_dataset(features, acquisition, calendar, tuple(quotes))

    assert captured.value.code == ModelingFailureCode.COST_QUOTE_MISMATCH


def test_feature_and_label_datasets_round_trip_as_immutable_evidence(tmp_path: Path) -> None:
    calendar, _, acquisition, features = _feature_inputs(26)
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        round_trip_cost_quotes(acquisition, calendar, cost=Decimal("0.1")),
    )
    store = EvidenceStore(
        EvidenceStoreConfig(
            root=tmp_path,
            min_free_bytes=0,
            clock=lambda: datetime(2025, 4, 2, 12, 0, tzinfo=UTC),
        )
    )

    feature_commit = store.commit(draft_from_feature_dataset(features), operation_id="op_features")
    label_commit = store.commit(draft_from_label_dataset(labels), operation_id="op_labels")

    opened_features = store.open_verified(EvidenceResourceType.DATASET, features.dataset_id)
    opened_labels = store.open_verified(EvidenceResourceType.DATASET, labels.dataset_id)
    assert opened_features.manifest.manifest_hash == feature_commit.manifest.manifest_hash
    assert opened_labels.manifest.manifest_hash == label_commit.manifest.manifest_hash
    assert opened_features.records[0] == features.rows[0].to_canonical_dict()
    assert opened_labels.records[0] == labels.rows[0].to_canonical_dict()


def _feature_inputs(
    count: int,
) -> tuple[
    SessionCalendarV1,
    HistoricalUniverseSnapshotV1,
    HistoricalAcquisition,
    FeatureDatasetV1,
]:
    calendar = governed_calendar(count)
    universe = governed_universe()
    acquisition = governed_acquisition(count=count, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, "cand_ridge_v1", calendar, universe)
    return calendar, universe, acquisition, features


def _copy_quote(
    quote: RoundTripCostQuoteV1,
    *,
    cost_rule_set_hash: str,
) -> RoundTripCostQuoteV1:
    return RoundTripCostQuoteV1(
        provider_instrument_id=quote.provider_instrument_id,
        symbol=quote.symbol,
        entry_at=quote.entry_at,
        exit_at=quote.exit_at,
        entry_price=quote.entry_price,
        exit_price=quote.exit_price,
        quantity=quote.quantity,
        component_costs=quote.component_costs,
        cost_rule_ids=quote.cost_rule_ids,
        cost_rule_set_hash=cost_rule_set_hash,
        execution_contract_version=quote.execution_contract_version,
    )
