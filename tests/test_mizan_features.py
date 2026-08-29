"""Tests for the shared Mizan v3 feature kernel.

The defect under guard is the one `agent_context/work/active/20260826-NOTICE-mizan-v3-reintroduces-window-dependence.md`
records: `rsi_14_centered` is an EMA with no bounded window, so before this kernel existed the same
decision bar produced different feature values depending on how much history happened to be
supplied. Schema v2 closed exactly this for the six-feature family and the v3 family reopened it.

The central test here is `test_features_are_identical_however_much_history_precedes_the_window`.
Nothing in the repository asserted that property before, which is why nothing caught the defect.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.data.market_data import PointInTimeBar
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.mizan_features import (
    MIZAN_CANONICAL_WINDOW_BARS,
    MIZAN_MINIMUM_BARS,
    apply_cross_sectional_ranks,
    canonical_mizan_window,
    compute_mizan_cross_section,
    compute_mizan_feature_values,
    mizan_schema_identity,
    wilder_rsi,
)
from quant_system.modeling.rows import (
    FEATURE_NAMES_V3,
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V3,
)

START = date(2016, 1, 4)


def _bars(count: int, symbol: str = "AAA", seed: int = 1) -> tuple[PointInTimeBar, ...]:
    """A deterministic ascending bar series with enough variation to move every feature."""
    bars: list[PointInTimeBar] = []
    close = 100.0
    for index in range(count):
        # Deterministic pseudo-random walk; no `random` so the series is reproducible everywhere.
        step = math.sin((index + seed) * 0.7) * 0.02 + math.cos((index + seed) * 0.23) * 0.01
        close = max(1.0, close * (1.0 + step))
        exchange_date = START + timedelta(days=index)
        event_at = datetime(2016, 1, 4, tzinfo=UTC) + timedelta(days=index, hours=10)
        bars.append(
            PointInTimeBar(
                provider_instrument_id=f"NSE_EQ|{symbol}",
                symbol=symbol,
                exchange_date=exchange_date,
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


def _values(bars: tuple[PointInTimeBar, ...], index: int | None = None) -> dict[str, str]:
    vix, nifty = _macro(bars)
    window = canonical_mizan_window(bars, index)
    got = compute_mizan_feature_values(window, india_vix_by_date=vix, nifty_by_date=nifty)
    assert got is not None
    return got


# --------------------------------------------------------------------------------------------
# The property that was missing, and that the defect exploited.
# --------------------------------------------------------------------------------------------


def test_features_are_identical_however_much_history_precedes_the_window() -> None:
    """The same decision bar must score identically from 500 bars of history or from 2000.

    This is the guarantee schema v2 established for the six-feature family and the v3 family lost.
    Before the canonical window existed, `rsi_14_centered` differed by up to 0.246 of its own
    standard deviation between a 51-bar and a full-history feed. Nothing asserted this, so nothing
    caught it.
    """
    long_series = _bars(2000)
    short_series = long_series[-500:]
    # Macro is keyed by date and built once, so both feeds see identical macro inputs. Building it
    # per-series would vary the three macro features by construction and test the fixture, not the
    # kernel -- which is exactly what the first version of this test did.
    vix, nifty = _macro(long_series)

    long_values = compute_mizan_feature_values(
        canonical_mizan_window(long_series), india_vix_by_date=vix, nifty_by_date=nifty
    )
    short_values = compute_mizan_feature_values(
        canonical_mizan_window(short_series), india_vix_by_date=vix, nifty_by_date=nifty
    )

    assert long_values == short_values, "the decision bar scored differently on more history"
    assert long_values is not None
    # And specifically the recursive member, which is the one that could drift.
    assert long_values["rsi_14_centered"] == short_values["rsi_14_centered"]


def test_a_window_shorter_than_the_canonical_one_really_does_change_rsi() -> None:
    """The regression is only meaningful if the underlying sensitivity is real. It is."""
    series = _bars(2000)
    vix, nifty = _macro(series)

    canonical = compute_mizan_feature_values(
        canonical_mizan_window(series), india_vix_by_date=vix, nifty_by_date=nifty
    )
    minimum = compute_mizan_feature_values(
        series[-MIZAN_MINIMUM_BARS:], india_vix_by_date=vix, nifty_by_date=nifty
    )
    assert canonical is not None and minimum is not None
    assert canonical["rsi_14_centered"] != minimum["rsi_14_centered"]
    # Bounded features are unaffected by how much history precedes them.
    for bounded in ("return_1", "return_5", "return_21", "sma_20_distance", "sma_50_distance"):
        assert canonical[bounded] == minimum[bounded]


def test_a_window_longer_than_the_canonical_one_is_refused_not_truncated() -> None:
    """Silently truncating would hide a caller that thinks it is supplying more information."""
    series = _bars(MIZAN_CANONICAL_WINDOW_BARS + 1)
    vix, nifty = _macro(series)
    with pytest.raises(ModelingError) as error:
        compute_mizan_feature_values(series, india_vix_by_date=vix, nifty_by_date=nifty)
    assert error.value.code is ModelingFailureCode.TRAINING_INPUT_MISMATCH


# --------------------------------------------------------------------------------------------
# Window selection.
# --------------------------------------------------------------------------------------------


def test_the_canonical_window_is_the_trailing_cap() -> None:
    series = _bars(1000)
    window = canonical_mizan_window(series)
    assert len(window) == MIZAN_CANONICAL_WINDOW_BARS
    assert window[-1] is series[-1]


def test_the_canonical_window_is_the_whole_prefix_when_history_is_short() -> None:
    """Below the cap the window is the full prefix, which is what the store builder fed."""
    series = _bars(120)
    window = canonical_mizan_window(series)
    assert len(window) == 120
    assert window[0] is series[0]


def test_the_canonical_window_ends_at_the_requested_decision_bar() -> None:
    series = _bars(1000)
    window = canonical_mizan_window(series, 600)
    assert window[-1] is series[600]
    assert len(window) == MIZAN_CANONICAL_WINDOW_BARS


def test_too_little_history_for_the_family_is_refused() -> None:
    series = _bars(MIZAN_MINIMUM_BARS - 1)
    with pytest.raises(ModelingError) as error:
        canonical_mizan_window(series)
    assert error.value.code is ModelingFailureCode.TRAINING_INPUT_MISMATCH


def test_a_decision_index_outside_the_records_is_refused() -> None:
    with pytest.raises(ModelingError) as error:
        canonical_mizan_window(_bars(100), 500)
    assert error.value.code is ModelingFailureCode.INVALID_PARAMETER


def test_reverse_chronology_is_refused() -> None:
    """An exported v2 kernel accepted reverse order and had to be repaired at `88a7ac9`."""
    series = _bars(120)
    vix, nifty = _macro(series)
    with pytest.raises(ModelingError) as error:
        compute_mizan_feature_values(
            tuple(reversed(series)), india_vix_by_date=vix, nifty_by_date=nifty
        )
    assert error.value.code is ModelingFailureCode.RECORD_ORDER_INVALID


# --------------------------------------------------------------------------------------------
# Shape, format, and the not-computable cases.
# --------------------------------------------------------------------------------------------


def test_every_declared_feature_is_produced_in_schema_order() -> None:
    values = _values(_bars(600))
    assert tuple(values) == FEATURE_NAMES_V3


def test_values_use_the_stores_own_ten_decimal_format() -> None:
    """The training dataset consumed this text; more digits would be values no row ever held."""
    for text in _values(_bars(600)).values():
        mantissa = text.split(".")[1]
        assert len(mantissa) == 10, text


def test_the_schema_identity_is_v3() -> None:
    assert mizan_schema_identity() == (FEATURE_SCHEMA_ID_V3, FEATURE_SCHEMA_VERSION_V3)


def test_a_row_with_missing_macro_data_is_not_computable() -> None:
    """The builder skips these rather than substituting a value, and so does the kernel."""
    series = _bars(600)
    _, nifty = _macro(series)
    assert (
        compute_mizan_feature_values(
            canonical_mizan_window(series), india_vix_by_date={}, nifty_by_date=nifty
        )
        is None
    )


def test_a_row_missing_only_the_five_session_macro_lag_is_not_computable() -> None:
    series = _bars(600)
    vix, nifty = _macro(series)
    del vix[series[-6].exchange_date.isoformat()]
    assert (
        compute_mizan_feature_values(
            canonical_mizan_window(series), india_vix_by_date=vix, nifty_by_date=nifty
        )
        is None
    )


# --------------------------------------------------------------------------------------------
# Cross-sectional ranks.
# --------------------------------------------------------------------------------------------


def test_ranks_are_centred_on_zero_and_span_the_cross_section() -> None:
    section = {
        s: dict.fromkeys(FEATURE_NAMES_V3, "0.0000000000") for s in ("AAA", "BBB", "CCC", "DDD")
    }
    for i, s in enumerate(("AAA", "BBB", "CCC", "DDD")):
        section[s]["return_5"] = f"{i * 0.01:.10f}"
        section[s]["volume_zscore"] = f"{-i * 0.5:.10f}"
    apply_cross_sectional_ranks(section)
    momentum = [float(section[s]["cs_rank_momentum_5"]) for s in ("AAA", "BBB", "CCC", "DDD")]
    assert momentum == [-0.25, 0.0, 0.25, 0.5]
    # The reversed driver produces the reversed ranking.
    volume = [float(section[s]["cs_rank_volume_surprise"]) for s in ("AAA", "BBB", "CCC", "DDD")]
    assert volume == [0.5, 0.25, 0.0, -0.25]


def test_ranks_depend_on_how_many_names_are_present() -> None:
    """This is why an execution surface must serve the whole cross-section, not a subset."""
    four = {
        s: dict.fromkeys(FEATURE_NAMES_V3, "0.0000000000") for s in ("AAA", "BBB", "CCC", "DDD")
    }
    two = {s: dict.fromkeys(FEATURE_NAMES_V3, "0.0000000000") for s in ("AAA", "BBB")}
    for section in (four, two):
        for i, s in enumerate(sorted(section)):
            section[s]["return_5"] = f"{i * 0.01:.10f}"
    apply_cross_sectional_ranks(four)
    apply_cross_sectional_ranks(two)
    assert four["AAA"]["cs_rank_momentum_5"] != two["AAA"]["cs_rank_momentum_5"]


def test_ranking_ties_resolve_identically_on_every_run() -> None:
    section = {
        s: dict.fromkeys(FEATURE_NAMES_V3, "0.0000000000") for s in ("EEE", "AAA", "CCC", "BBB")
    }
    first = {s: dict(v) for s, v in section.items()}
    second = {s: dict(v) for s, v in section.items()}
    apply_cross_sectional_ranks(first)
    apply_cross_sectional_ranks(second)
    assert first == second


def test_an_empty_cross_section_is_a_no_op() -> None:
    section: dict[str, dict[str, str]] = {}
    apply_cross_sectional_ranks(section)
    assert section == {}


def test_the_cross_section_entry_point_produces_ranked_rows_for_every_served_name() -> None:
    symbols = ("AAA", "BBB", "CCC", "DDD", "EEE")
    bars = {s: _bars(600, symbol=s, seed=i + 1) for i, s in enumerate(symbols)}
    vix, nifty = _macro(bars["AAA"])
    section = compute_mizan_cross_section(bars, india_vix_by_date=vix, nifty_by_date=nifty)
    assert set(section) == set(symbols)
    for values in section.values():
        assert tuple(values) == FEATURE_NAMES_V3
    ranks = sorted(float(v["cs_rank_momentum_5"]) for v in section.values())
    assert ranks == [-0.3, -0.1, 0.1, 0.3, 0.5]


# --------------------------------------------------------------------------------------------
# The promoted RSI itself.
# --------------------------------------------------------------------------------------------


def test_rsi_is_neutral_before_it_has_a_period_of_data() -> None:
    assert wilder_rsi([100.0] * 10) == [50.0] * 10


def test_rsi_saturates_upward_on_an_unbroken_advance() -> None:
    assert wilder_rsi([100.0 + i for i in range(60)])[-1] == 100.0


def test_rsi_is_neutral_on_a_flat_series() -> None:
    assert wilder_rsi([100.0] * 60)[-1] == 50.0


def test_rsi_seed_influence_decays_as_the_wilder_ema_predicts() -> None:
    """(13/14)^n is why 400 is the canonical window and 51 is not."""
    assert (13 / 14) ** MIZAN_MINIMUM_BARS > 1e-3
    assert (13 / 14) ** MIZAN_CANONICAL_WINDOW_BARS < 1e-12
