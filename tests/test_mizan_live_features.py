"""Tests for the live Mizan cross-section provider.

The defect under guard is recorded in
`agent_context/work/active/20260829-claude-live-mizan-feature-provider.md`: the paper runner built
all fifteen model inputs by hand, so `rsi_14_centered` could reach ±50 against a trained range of
±0.45, the macro features were constants, and the cross-sectional ranks were not ranks. This module
exists so the live path calls the same kernel training calls, and these tests hold it to that.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.data.market_data import PointInTimeBar
from quant_system.execution.mizan_live_features import (
    MAX_STANDARDIZED_DEVIATION,
    CrossSectionCoverage,
    MizanLiveFeatureError,
    build_live_cross_section,
    refuse_extreme_rows,
    select_top_fraction,
)
from quant_system.modeling.mizan_features import MIZAN_CANONICAL_WINDOW_BARS, MIZAN_MINIMUM_BARS
from quant_system.modeling.rows import FEATURE_NAMES_V3

START = date(2016, 1, 4)


def _bars(count: int, symbol: str = "AAA", seed: int = 1) -> tuple[PointInTimeBar, ...]:
    bars: list[PointInTimeBar] = []
    close = 100.0
    for index in range(count):
        close = max(1.0, close * (1.0 + math.sin((index + seed) * 0.7) * 0.02))
        event_at = datetime(2016, 1, 4, tzinfo=UTC) + timedelta(days=index, hours=10)
        bars.append(
            PointInTimeBar(
                provider_instrument_id=f"NSE_EQ|{symbol}",
                symbol=symbol,
                exchange_date=START + timedelta(days=index),
                event_at=event_at,
                provider_at=event_at,
                ingested_at=event_at + timedelta(hours=1),
                available_at=event_at,
                open=Decimal(str(round(close * 0.995, 4))),
                high=Decimal(str(round(close * 1.01, 4))),
                low=Decimal(str(round(close * 0.99, 4))),
                close=Decimal(str(round(close, 4))),
                volume=1000 + (index * 37) % 900,
                open_interest=0,
                source_row_index=index,
            )
        )
    return tuple(bars)


def _macro(bars: tuple[PointInTimeBar, ...]) -> tuple[dict[str, float], dict[str, float]]:
    vix = {b.exchange_date.isoformat(): 14.0 + (i % 11) * 0.5 for i, b in enumerate(bars)}
    nifty = {b.exchange_date.isoformat(): 17000.0 + i * 3.5 for i, b in enumerate(bars)}
    return vix, nifty


def _universe(names: tuple[str, ...], count: int = 600) -> dict[str, tuple[PointInTimeBar, ...]]:
    return {name: _bars(count, symbol=name, seed=i + 1) for i, name in enumerate(names)}


def _build(bars, **kwargs):
    reference = next(iter(bars.values()))
    vix, nifty = _macro(reference)
    return build_live_cross_section(bars, india_vix_by_date=vix, nifty_by_date=nifty, **kwargs)


# --------------------------------------------------------------------------------------------
# The values reach the model in the shape training produced.
# --------------------------------------------------------------------------------------------


def test_every_feature_the_schema_declares_is_produced() -> None:
    section, _ = _build(_universe(("AAA", "BBB", "CCC")))
    assert set(section) == {"AAA", "BBB", "CCC"}
    for values in section.values():
        assert tuple(values) == FEATURE_NAMES_V3


def test_rsi_lands_inside_the_range_the_model_was_trained_on() -> None:
    """The old runner clamped this to +/-50; `rsi/100 - 0.5` cannot leave [-0.5, 0.5]."""
    section, _ = _build(_universe(("AAA", "BBB", "CCC", "DDD")))
    for values in section.values():
        rsi = float(values["rsi_14_centered"])
        assert -0.5 <= rsi <= 0.5, rsi


def test_the_cross_sectional_ranks_are_real_ranks() -> None:
    """They must span the cross-section and centre on zero, not be a rescaled volume z-score."""
    names = ("AAA", "BBB", "CCC", "DDD", "EEE")
    section, _ = _build(_universe(names))
    ranks = sorted(float(section[s]["cs_rank_momentum_5"]) for s in names)
    assert ranks == [-0.3, -0.1, 0.1, 0.3, 0.5]


def test_macro_features_track_the_supplied_series_rather_than_constants() -> None:
    bars = _universe(("AAA",))
    vix, nifty = _macro(bars["AAA"])
    first, _ = build_live_cross_section(bars, india_vix_by_date=vix, nifty_by_date=nifty)
    bumped = {day: value * 2.0 for day, value in vix.items()}
    second, _ = build_live_cross_section(bars, india_vix_by_date=bumped, nifty_by_date=nifty)
    assert first["AAA"]["india_vix_level"] != second["AAA"]["india_vix_level"]


# --------------------------------------------------------------------------------------------
# Window and decision-date discipline.
# --------------------------------------------------------------------------------------------


def test_history_is_capped_at_the_canonical_window() -> None:
    """More history must not change the decision; the kernel refuses over-long windows outright."""
    # The same series, sliced -- not two separately generated ones, which would put the decision
    # bar on different dates and test nothing.
    full = _bars(1500)
    vix, nifty = _macro(full)
    long_section, _ = build_live_cross_section(
        {"AAA": full}, india_vix_by_date=vix, nifty_by_date=nifty
    )
    short_section, _ = build_live_cross_section(
        {"AAA": full[-MIZAN_CANONICAL_WINDOW_BARS:]},
        india_vix_by_date=vix,
        nifty_by_date=nifty,
    )
    assert long_section["AAA"] == short_section["AAA"]


def test_as_of_truncates_to_the_requested_decision_date() -> None:
    bars = _universe(("AAA",), count=600)
    cutoff = bars["AAA"][-10].exchange_date
    section, _ = _build(bars, as_of=cutoff)
    full, _ = _build(bars)
    assert section["AAA"] != full["AAA"]


def test_a_cross_section_spanning_two_decision_dates_is_refused() -> None:
    """Ranking Friday's name against Wednesday's is not the comparison the model was fitted to."""
    bars = _universe(("AAA", "BBB"))
    bars["BBB"] = bars["BBB"][:-3]
    with pytest.raises(MizanLiveFeatureError, match="decision dates"):
        _build(bars)


def test_a_symbol_without_enough_history_is_reported_not_dropped_silently() -> None:
    bars = _universe(("AAA", "BBB"))
    bars["BBB"] = bars["BBB"][-(MIZAN_MINIMUM_BARS - 1) :]
    section, coverage = _build(bars)
    assert set(section) == {"AAA"}
    assert coverage.skipped_short_history == ("BBB",)
    assert coverage.requested == ("AAA", "BBB")
    assert coverage.fraction == 0.5


def test_no_symbols_at_all_is_an_error() -> None:
    with pytest.raises(MizanLiveFeatureError, match="no symbols"):
        build_live_cross_section({}, india_vix_by_date={}, nifty_by_date={})


def test_a_universe_where_nothing_has_enough_history_is_an_error() -> None:
    bars = {"AAA": _bars(10), "BBB": _bars(10, symbol="BBB")}
    with pytest.raises(MizanLiveFeatureError, match="bars the feature family needs"):
        _build(bars)


def test_coverage_summary_names_what_was_lost() -> None:
    coverage = CrossSectionCoverage(
        requested=("A", "B", "C", "D"),
        scored=("A", "B"),
        skipped_short_history=("C",),
        skipped_not_computable=("D",),
    )
    assert coverage.fraction == 0.5
    assert "2/4" in coverage.summary()
    assert "1 short history" in coverage.summary()
    assert "1 not computable" in coverage.summary()


# --------------------------------------------------------------------------------------------
# Selection.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("population", "expected"),
    [(1, 1), (5, 1), (10, 2), (43, 9), (50, 10), (423, 85)],
)
def test_the_fraction_rounds_up_and_is_exact_at_boundaries(population: int, expected: int) -> None:
    """0.2 * 50 is 10.000000000000002 in binary float; a naive ceil would take 11 of 50."""
    scores = {f"S{i:04d}": float(population - i) for i in range(population)}
    assert len(select_top_fraction(scores, 0.20)) == expected


def test_selection_takes_the_highest_scores_strongest_first() -> None:
    scores = {"AAA": 0.1, "BBB": 0.9, "CCC": 0.5, "DDD": 0.7}
    assert select_top_fraction(scores, 0.5) == ("BBB", "DDD")


def test_the_score_floor_removes_names_that_would_otherwise_be_taken() -> None:
    scores = {"AAA": 0.10, "BBB": 0.02, "CCC": 0.01, "DDD": 0.005}
    assert select_top_fraction(scores, 1.0) == ("AAA", "BBB", "CCC", "DDD")
    assert select_top_fraction(scores, 1.0, score_threshold=0.03) == ("AAA",)


def test_ties_resolve_identically_on_every_run() -> None:
    scores = dict.fromkeys(("EEE", "AAA", "CCC", "BBB", "DDD"), 0.5)
    assert select_top_fraction(scores, 0.4) == select_top_fraction(scores, 0.4) == ("AAA", "BBB")


def test_an_empty_cross_section_selects_nothing() -> None:
    assert select_top_fraction({}, 0.2) == ()


@pytest.mark.parametrize("fraction", [0.0, -0.1, 1.5])
def test_an_invalid_fraction_is_refused(fraction: float) -> None:
    with pytest.raises(MizanLiveFeatureError, match="fraction must lie"):
        select_top_fraction({"AAA": 1.0}, fraction)


# --------------------------------------------------------------------------------------------
# Refusing rows that would dominate a linear score.
# --------------------------------------------------------------------------------------------


def _flat_state() -> tuple[dict[str, float], dict[str, float]]:
    return (dict.fromkeys(FEATURE_NAMES_V3, 0.0), dict.fromkeys(FEATURE_NAMES_V3, 1.0))


def _row(**overrides: float) -> dict[str, str]:
    values = dict.fromkeys(FEATURE_NAMES_V3, "0.0000000000")
    for name, value in overrides.items():
        values[name] = f"{value:.10f}"
    return values


def test_an_ordinary_cross_section_is_untouched() -> None:
    means, scales = _flat_state()
    section = {"AAA": _row(return_1=0.5), "BBB": _row(return_1=-0.5)}
    kept, refused = refuse_extreme_rows(section, means=means, scales=scales)
    assert refused == ()
    assert kept == section


def test_a_row_beyond_the_limit_is_refused() -> None:
    """BBTC's real case: a 423x volume spike gave a standardized value of 272."""
    means, scales = _flat_state()
    section = {"AAA": _row(return_1=0.5), "BBTC": _row(volume_zscore=272.0)}
    kept, refused = refuse_extreme_rows(section, means=means, scales=scales)
    assert refused == ("BBTC",)
    assert set(kept) == {"AAA"}


def test_the_limit_is_applied_after_standardizing_not_to_the_raw_value() -> None:
    """A raw 20 is extreme against a scale of 0.1 and unremarkable against a scale of 10."""
    means = dict.fromkeys(FEATURE_NAMES_V3, 0.0)
    section = {"AAA": _row(volume_zscore=20.0)}
    tight = dict.fromkeys(FEATURE_NAMES_V3, 0.1)
    loose = dict.fromkeys(FEATURE_NAMES_V3, 10.0)
    assert refuse_extreme_rows(section, means=means, scales=tight)[1] == ("AAA",)
    assert refuse_extreme_rows(section, means=means, scales=loose)[1] == ()


def test_the_mean_is_subtracted_before_measuring_distance() -> None:
    means = dict.fromkeys(FEATURE_NAMES_V3, 100.0)
    scales = dict.fromkeys(FEATURE_NAMES_V3, 1.0)
    # Every feature sits exactly on its mean, so the row is zero deviations out despite the values
    # themselves being large. Setting only one feature would leave the other fourteen 100 away.
    on_the_mean = dict.fromkeys(FEATURE_NAMES_V3, "100.0000000000")
    assert refuse_extreme_rows({"AAA": on_the_mean}, means=means, scales=scales)[1] == ()


def test_a_zero_scale_feature_cannot_refuse_a_row() -> None:
    """Zero-variance features carry scale 0; dividing by them would refuse everything."""
    means = dict.fromkeys(FEATURE_NAMES_V3, 0.0)
    scales = dict.fromkeys(FEATURE_NAMES_V3, 0.0)
    assert (
        refuse_extreme_rows({"AAA": _row(volume_zscore=1e9)}, means=means, scales=scales)[1] == ()
    )


def test_refusal_is_not_clipping() -> None:
    """A surviving row keeps its exact values; nothing is rewritten on the way through."""
    means, scales = _flat_state()
    section = {"AAA": _row(return_1=3.25)}
    kept, _ = refuse_extreme_rows(section, means=means, scales=scales)
    assert kept["AAA"]["return_1"] == "3.2500000000"


def test_a_non_positive_limit_is_refused() -> None:
    means, scales = _flat_state()
    with pytest.raises(MizanLiveFeatureError, match="limit must be positive"):
        refuse_extreme_rows({"AAA": _row()}, means=means, scales=scales, limit=0.0)


def test_the_default_limit_sits_clear_of_the_observed_distribution() -> None:
    """Measured live: per-name max |z| had median 1.5, p90 2.1, p99 7.0; BBTC was 271.8."""
    assert MAX_STANDARDIZED_DEVIATION > 7.0
    assert MAX_STANDARDIZED_DEVIATION < 271.8
