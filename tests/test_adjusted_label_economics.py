"""What a label measures when a corporate action falls inside the holding window.

The defect being closed
-----------------------
``scripts/train_mizan.py`` fed the model features computed on corporate-action-adjusted bars while
``build_label_dataset`` read entry and exit opens straight off the raw provider acquisition. Adjusting
one side and not the other is worse than adjusting neither: the model would be fitted on corrected
inputs against targets containing every uncorrected corporate-action break. That mismatch is what
blocked the governed retrain.

Two things had to be true at once and this file pins both.

**The return must be economic.** A 1:1 bonus halves the quote and doubles the share count. The raw
price ratio says the holder lost 50%; the holder in fact broke even. The label must say zero.

**The costs must stay executable.** NSE charges are not all ad valorem -- a flat DP charge and a
capped brokerage do not scale with a synthetic adjusted price -- so a cost priced on adjusted prices
would misstate the rupee amount. Costs are quoted on the raw executable opens and expressed as a
fraction of the raw notional. Both the cost fraction and the gross return are then fractions of the
same economic position, and nothing is counted twice.

And the case neither can handle: a window spanning an action **of unknown size**. The adjusted series
cannot correct it because nothing sized it, and the raw ratio across it is a fabricated return. The
label is refused.

Every expected number below is derived by hand in the test that uses it, from prices the test sets.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from quant_system.data.adjusted_acquisition import (
    derive_adjusted_acquisition,
    reference_from_plan,
)
from quant_system.data.adjustment_provenance import AdjustmentBasis, AdjustmentStatus
from quant_system.data.corporate_actions import AdjustmentPlan, build_adjustment_factors
from quant_system.data.market_data import HistoricalAcquisition
from quant_system.modeling import (
    ModelingError,
    ModelingFailureCode,
    build_feature_dataset,
    build_label_dataset,
)
from tests.modeling_fixtures import (
    governed_acquisition,
    governed_calendar,
    governed_universe,
    round_trip_cost_quotes,
)

CANDIDATE = "cand_adjusted_labels"
DERIVED_AT = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)


def _bar_points(acquisition: HistoricalAcquisition):
    from quant_system.data.corporate_actions import BarPoint

    return [
        BarPoint(
            on=record.exchange_date,
            open=record.open,
            high=record.high,
            low=record.low,
            close=record.close,
            volume=record.volume,
        )
        for record in sorted(acquisition.records, key=lambda r: r.exchange_date)
    ]


def _derive(
    acquisition: HistoricalAcquisition,
    actions: list[tuple[date, str]],
    *,
    basis: AdjustmentBasis = AdjustmentBasis.PRICE_RETURN,
) -> tuple[HistoricalAcquisition, AdjustmentPlan]:
    plan = build_adjustment_factors(
        actions, _bar_points(acquisition), total_return=basis is AdjustmentBasis.TOTAL_RETURN
    )
    reference = reference_from_plan(
        plan,
        manifest=acquisition.manifest,
        basis=basis,
        authority_content_hash="a" * 64,
        authority_source_url="https://example.test/nse/corporate-actions",
        authority_publication_date=date(2026, 9, 1),
        code_revision="test-revision",
        derived_at=DERIVED_AT,
    )
    return derive_adjusted_acquisition(acquisition, plan, reference), plan


def _pipeline(acquisition: HistoricalAcquisition, calendar, universe):
    return build_feature_dataset(acquisition, CANDIDATE, calendar, universe)


def _bonus_series(count: int = 30, ex_index: int = 23):
    """A series with a genuine, unapplied 1:1 bonus break and no market movement at all.

    Flat at 100 up to the ex-date and flat at 50 from it, so the ex-date gap is exactly the
    published ratio and every other session's return is exactly zero. That makes every expected
    number below an exact hand calculation rather than an approximation.
    """
    calendar = governed_calendar(count)
    universe = governed_universe()
    ex_date = calendar.sessions[ex_index].exchange_date
    prices = {i: (Decimal("100") if i < ex_index else Decimal("50")) for i in range(count)}
    raw = governed_acquisition(
        count=count,
        calendar=calendar,
        universe=universe,
        open_overrides=prices,
        close_overrides=dict(prices),
    )
    return calendar, universe, raw, ex_date


# --- the economics -----------------------------------------------------------------------------


def test_a_bonus_inside_the_window_gives_a_zero_return_not_a_fifty_percent_loss() -> None:
    """Hand calculation.

    Sessions are priced so the ex-date open is exactly half the previous close, which is what an
    unapplied 1:1 bonus looks like. Entry open 100, exit open 50 raw.

    Raw ratio      : (50 - 100) / 100 = -0.5   <- a 50% loss that never happened
    Adjusted entry : 100 x 0.5 = 50 (bars before the ex-date are rebased)
    Adjusted exit  : 50 (on or after the ex-date, untouched)
    Economic return: (50 - 50) / 50 = 0        <- the holder broke even
    """
    calendar, universe, raw, ex_date = _bonus_series()
    adjusted, plan = _derive(raw, [(ex_date, "Bonus 1:1")])

    assert len(plan.factors) == 1, "the provider clearly has not applied this one"
    assert plan.factors[0].factor == Decimal("0.5")

    raw_labels = build_label_dataset(
        _pipeline(raw, calendar, universe),
        raw,
        calendar,
        round_trip_cost_quotes(raw, calendar, cost=Decimal("0")),
    )
    adjusted_labels = build_label_dataset(
        _pipeline(adjusted, calendar, universe),
        adjusted,
        calendar,
        round_trip_cost_quotes(raw, calendar, cost=Decimal("0")),
        execution_acquisition=raw,
    )

    spanning_raw = _row_for_exit(raw_labels, ex_date)
    spanning_adjusted = _row_for_exit(adjusted_labels, ex_date)
    assert Decimal(spanning_raw.gross_return) == Decimal("-0.5")
    assert Decimal(spanning_adjusted.gross_return) == Decimal("0")


def test_costs_are_charged_on_the_raw_notional_not_the_adjusted_one() -> None:
    """The other half of the identity, also by hand.

    Same setup, but with a flat INR 1 round-trip cost on a quantity of 1.

    Raw entry notional : 100 x 1 = 100
    Cost fraction      : 1 / 100 = 0.01
    Net return         : 0 (economic gross) - 0.01 = -0.01

    Had the cost been divided by the *adjusted* entry notional of 50, the fraction would have been
    0.02 -- a real rupee charge doubled by a synthetic price ratio.
    """
    calendar, universe, raw, ex_date = _bonus_series()
    adjusted, _ = _derive(raw, [(ex_date, "Bonus 1:1")])

    labels = build_label_dataset(
        _pipeline(adjusted, calendar, universe),
        adjusted,
        calendar,
        round_trip_cost_quotes(raw, calendar, cost=Decimal("1")),
        execution_acquisition=raw,
    )
    row = _row_for_exit(labels, ex_date)
    assert Decimal(row.gross_return) == Decimal("0")
    assert Decimal(row.net_return) == Decimal("-0.01")


def test_a_window_spanning_an_unsized_action_is_refused_not_measured() -> None:
    """A demerger carries no published ratio, so no factor exists and no return is defensible."""
    calendar = governed_calendar(30)
    universe = governed_universe()
    ex_index = 23
    ex_date = calendar.sessions[ex_index].exchange_date
    opens = {i: (Decimal("100") if i < ex_index else Decimal("36")) for i in range(30)}
    raw = governed_acquisition(
        count=30,
        calendar=calendar,
        universe=universe,
        open_overrides=opens,
        close_overrides=dict(opens),
    )
    adjusted, plan = _derive(raw, [(ex_date, "Demerger")])

    assert plan.factors == (), "a ratio-less action is never sized from its own gap"
    assert [item.reason for item in plan.unresolved] == ["RATIO_NOT_PUBLISHED"]

    labels = build_label_dataset(
        _pipeline(adjusted, calendar, universe),
        adjusted,
        calendar,
        round_trip_cost_quotes(raw, calendar, cost=Decimal("0")),
        execution_acquisition=raw,
    )
    exits = {row.exit_at.date() for row in labels.rows}
    assert ex_date not in exits, "no label may be published across an action of unknown size"
    assert labels.rows, "only the spanning window is refused, not the whole dataset"


def test_windows_outside_the_action_are_unaffected() -> None:
    """The refusal must be surgical: adjacent windows keep their labels."""
    calendar = governed_calendar(30)
    universe = governed_universe()
    ex_index = 23
    ex_date = calendar.sessions[ex_index].exchange_date
    opens = {i: (Decimal("100") if i < ex_index else Decimal("36")) for i in range(30)}
    raw = governed_acquisition(
        count=30,
        calendar=calendar,
        universe=universe,
        open_overrides=opens,
        close_overrides=dict(opens),
    )
    adjusted, _ = _derive(raw, [(ex_date, "Demerger")])
    labels = build_label_dataset(
        _pipeline(adjusted, calendar, universe),
        adjusted,
        calendar,
        round_trip_cost_quotes(raw, calendar, cost=Decimal("0")),
        execution_acquisition=raw,
    )
    earlier = [row for row in labels.rows if row.exit_at.date() < ex_date]
    assert earlier, "windows entirely before the action must still produce labels"
    assert all(Decimal(row.gross_return) == Decimal("0") for row in earlier), (
        "prices are flat before the action, so those returns are exactly zero"
    )


# --- identity and provenance --------------------------------------------------------------------


def test_the_adjusted_acquisition_gets_its_own_identity_and_declares_itself_adjusted() -> None:
    calendar, universe, raw, ex_date = _bonus_series()
    adjusted, plan = _derive(raw, [(ex_date, "Bonus 1:1")])

    assert plan.factors, "this series really does need adjusting"
    assert adjusted.manifest.manifest_hash != raw.manifest.manifest_hash
    assert adjusted.manifest.dataset_id != raw.manifest.dataset_id
    assert adjusted.manifest.canonical_content_hash != raw.manifest.canonical_content_hash
    assert raw.manifest.adjustment is None, "the raw acquisition is never mutated"
    assert adjusted.manifest.adjustment is not None
    assert adjusted.manifest.adjustment.status is AdjustmentStatus.ADJUSTED
    assert adjusted.manifest.adjustment.source_manifest_hash == raw.manifest.manifest_hash
    assert adjusted.manifest.adjustment.code_revision == "test-revision"


def test_an_adjustment_that_changes_no_bar_still_gets_a_distinct_identity() -> None:
    """A "we checked and nothing needed doing" series is a different claim from "we never checked".

    On the default rising fixture the 1:1 bonus is judged already applied by the provider, so no
    factor is produced and every bar is byte-identical. The content hash is therefore the same --
    correctly, because the content is the same -- but the *manifest* hash must still differ, because
    the derived artifact asserts an adjustment method, an authority and a code revision that the raw
    one does not.
    """
    calendar = governed_calendar(30)
    universe = governed_universe()
    ex_date = calendar.sessions[23].exchange_date
    raw = governed_acquisition(count=30, calendar=calendar, universe=universe)
    adjusted, plan = _derive(raw, [(ex_date, "Bonus 1:1")])

    assert plan.factors == (), "a rising series shows the provider already applied it"
    assert adjusted.manifest.canonical_content_hash == raw.manifest.canonical_content_hash
    assert adjusted.manifest.manifest_hash != raw.manifest.manifest_hash
    assert adjusted.manifest.adjustment is not None


def test_labels_from_the_adjusted_series_bind_the_adjusted_dataset() -> None:
    """A label set built on adjusted prices must not claim the raw dataset as its source."""
    calendar, universe, raw, ex_date = _bonus_series()
    adjusted, _ = _derive(raw, [(ex_date, "Bonus 1:1")])

    quotes = round_trip_cost_quotes(raw, calendar, cost=Decimal("0"))
    raw_labels = build_label_dataset(_pipeline(raw, calendar, universe), raw, calendar, quotes)
    adjusted_labels = build_label_dataset(
        _pipeline(adjusted, calendar, universe),
        adjusted,
        calendar,
        quotes,
        execution_acquisition=raw,
    )
    assert adjusted_labels.source_dataset_hash == adjusted.manifest.manifest_hash
    assert adjusted_labels.source_dataset_hash != raw_labels.source_dataset_hash
    assert adjusted_labels.dataset_hash != raw_labels.dataset_hash


def test_an_execution_acquisition_the_series_was_not_derived_from_is_refused() -> None:
    """The return and the costs must come from the same instrument's same history.

    A Red Team recheck on this codebase already found the near-miss version of this bug once: a
    bundle bound the *map key* rather than each bar's own identity, so bars for one symbol passed
    under another symbol's label. Here the guard is the derivation link -- the adjusted manifest
    names the exact raw manifest hash it came from, and anything else is refused rather than
    silently priced.
    """
    calendar, universe, raw, ex_date = _bonus_series()
    adjusted, _ = _derive(raw, [(ex_date, "Bonus 1:1")])
    unrelated = replace(raw.manifest, manifest_hash="9" * 64)
    mismatched = HistoricalAcquisition(manifest=unrelated, records=raw.records)

    with pytest.raises(ModelingError) as error:
        build_label_dataset(
            _pipeline(adjusted, calendar, universe),
            adjusted,
            calendar,
            round_trip_cost_quotes(raw, calendar, cost=Decimal("0")),
            execution_acquisition=mismatched,
        )
    assert error.value.code is ModelingFailureCode.DATASET_INTEGRITY_INVALID
    assert "not derived from" in str(error.value)


def test_an_execution_acquisition_for_a_different_symbol_is_refused() -> None:
    """The cheaper half of the same guard: a different symbol never reaches the derivation check."""
    calendar, universe, raw, ex_date = _bonus_series()
    adjusted, _ = _derive(raw, [(ex_date, "Bonus 1:1")])
    other_symbol = HistoricalAcquisition(
        manifest=replace(raw.manifest, symbol="OTHER"), records=raw.records
    )

    with pytest.raises(ModelingError) as error:
        build_label_dataset(
            _pipeline(adjusted, calendar, universe),
            adjusted,
            calendar,
            round_trip_cost_quotes(raw, calendar, cost=Decimal("0")),
            execution_acquisition=other_symbol,
        )
    assert error.value.code is ModelingFailureCode.DATASET_INTEGRITY_INVALID
    assert "different instrument" in str(error.value)


def test_an_execution_acquisition_without_an_adjusted_measure_is_refused() -> None:
    """Two raw series is not a meaningful pairing and would hide which one was priced."""
    calendar = governed_calendar(30)
    universe = governed_universe()
    raw = governed_acquisition(count=30, calendar=calendar, universe=universe)
    other = governed_acquisition(count=29, calendar=calendar, universe=universe)
    with pytest.raises(ModelingError) as error:
        build_label_dataset(
            _pipeline(raw, calendar, universe),
            raw,
            calendar,
            round_trip_cost_quotes(raw, calendar, cost=Decimal("0")),
            execution_acquisition=other,
        )
    assert error.value.code is ModelingFailureCode.DATASET_INTEGRITY_INVALID


def test_the_default_path_is_byte_for_byte_what_it_was() -> None:
    """Backward compatibility: omitting the new argument must reproduce the old dataset exactly."""
    calendar = governed_calendar(30)
    universe = governed_universe()
    raw = governed_acquisition(count=30, calendar=calendar, universe=universe)
    quotes = round_trip_cost_quotes(raw, calendar, cost=Decimal("1.1"))
    features = _pipeline(raw, calendar, universe)

    implicit = build_label_dataset(features, raw, calendar, quotes)
    explicit = build_label_dataset(features, raw, calendar, quotes, execution_acquisition=raw)
    assert implicit.dataset_hash == explicit.dataset_hash
    assert len(implicit.rows) == len(explicit.rows)


def _row_for_exit(labels: object, exit_date: date):
    matches = [row for row in labels.rows if row.exit_at.date() == exit_date]  # type: ignore[attr-defined]
    assert matches, f"no label exits on {exit_date.isoformat()}"
    return matches[0]
