"""Comprehensive unit tests for the Point-in-Time Multi-Factor Ranking Engine (R1).

Verifies:
1. Intermediate momentum calculation against known values.
2. Short-term mean-reversion dampening calculation and effect.
3. Idiosyncratic volatility computation and positive scaling.
4. Strict point-in-time isolation (future bars are rejected or inaccessible).
5. Deterministic tie-breaking by symbol (lexicographic ascending).
6. Handling of missing/insufficient history fail-closed.
7. Dataclass contracts (FactorComponents, RankedSymbol, MultiFactorRankingEngine).
8. Scoring method variations (ratio, ratio_zscore, linear_zscore).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import pytest

from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.ranking import (
    FactorComponents,
    FactorConfig,
    MultiFactorRankingEngine,
    PointInTimeBar,
    PointInTimeError,
    RankedSymbol,
    compute_idiosyncratic_volatility,
    compute_intermediate_momentum,
    compute_short_term_reversion,
)


def _generate_bars(
    symbol: str,
    start_date: date,
    closes: list[float],
    base_volume: int = 100000,
    locked_indices: set[int] | None = None,
) -> list[Bar]:
    """Generate a contiguous sequence of Bar objects from close prices."""
    locked = locked_indices or set()
    bars: list[Bar] = []
    current_date = start_date
    for i, c in enumerate(closes):
        # Skip weekends to simulate trading calendar
        while current_date.weekday() >= 5:
            current_date += timedelta(days=1)
        close_d = Decimal(str(round(c, 4)))
        is_locked = i in locked
        if is_locked:
            bar = Bar(
                symbol=symbol,
                exchange_date=current_date,
                open=close_d,
                high=close_d,
                low=close_d,
                close=close_d,
                volume=0,
            )
        else:
            bar = Bar(
                symbol=symbol,
                exchange_date=current_date,
                open=close_d,
                high=close_d + Decimal("1.00"),
                low=max(close_d - Decimal("1.00"), Decimal("0.01")),
                close=close_d,
                volume=base_volume,
            )
        bars.append(bar)
        current_date += timedelta(days=1)
    return bars


def test_intermediate_momentum_known_values() -> None:
    """Intermediate momentum matches exact hand-calculated returns."""
    start = date(2025, 1, 1)
    # 64 sessions: initial 100.0, linear rise to 150.0
    n = 64
    closes = [100.0 + (50.0 * i / (n - 1)) for i in range(n)]
    bars = _generate_bars("TEST", start, closes)
    as_of = bars[-1].exchange_date

    mom = compute_intermediate_momentum(bars, as_of, window=63)
    assert mom is not None
    # Expected: (150.0 - 100.0) / 100.0 = 0.50
    assert pytest.approx(mom, rel=1e-6) == 0.50

    # Test declining series: 100.0 to 80.0
    declining_closes = [100.0 - (20.0 * i / (n - 1)) for i in range(n)]
    dec_bars = _generate_bars("TEST_DEC", start, declining_closes)
    dec_mom = compute_intermediate_momentum(dec_bars, dec_bars[-1].exchange_date, window=63)
    assert dec_mom is not None
    # Expected: (80.0 - 100.0) / 100.0 = -0.20
    assert pytest.approx(dec_mom, rel=1e-6) == -0.20


def test_mean_reversion_dampening_calculation_and_effect() -> None:
    """Mean-reversion dampening penalizes recent short-term spikes."""
    start = date(2025, 1, 1)
    n = 64

    # STEADY: climbs from 100 to 140 over first 58 bars, then stays flat at 140 for last 5 bars
    # intermediate return = (140 - 100) / 100 = 0.40, short return (last 5) = (140 - 140) / 140 = 0.0
    steady_closes = [100.0 + (40.0 * i / 58) for i in range(59)] + [140.0] * 5
    assert len(steady_closes) == n
    steady_bars = _generate_bars("STEADY", start, steady_closes)
    as_of = steady_bars[-1].exchange_date

    # SPIKE: flat at 100 for first 58 bars, then violently jumps to 140 over last 5 bars
    # intermediate return = (140 - 100) / 100 = 0.40, short return (last 5) = (140 - 100) / 100 = 0.40
    spike_closes = [100.0] * 59 + [100.0 + (40.0 * k / 5) for k in range(1, 6)]
    assert len(spike_closes) == n
    spike_bars = _generate_bars("SPIKE", start, spike_closes)

    rev_steady = compute_short_term_reversion(steady_bars, as_of, window=5)
    rev_spike = compute_short_term_reversion(spike_bars, as_of, window=5)

    assert rev_steady is not None and rev_spike is not None
    assert pytest.approx(rev_steady, abs=1e-6) == 0.0
    assert pytest.approx(rev_spike, rel=1e-6) == 0.40

    # Multi-factor engine ranking: STEADY must outrank SPIKE due to reversion penalty
    engine = MultiFactorRankingEngine(FactorConfig(dampening_lambda=0.5, scoring_method="ratio"))
    bars_by_symbol = {"STEADY": steady_bars, "SPIKE": spike_bars}
    rankings = engine.rank_universe(as_of, ["STEADY", "SPIKE"], bars_by_symbol)

    assert len(rankings) == 2
    assert rankings[0].symbol == "STEADY"
    assert rankings[0].rank == 1
    assert rankings[1].symbol == "SPIKE"
    assert rankings[1].rank == 2

    # STEADY composite score: (0.40 - 0.5 * 0.0) / idio_vol > SPIKE: (0.40 - 0.5 * 0.40) / idio_vol
    assert rankings[0].score > rankings[1].score


def test_idiosyncratic_volatility_computation_and_positive_scaling() -> None:
    """Residual volatility is computed via CAPM and scales scores positively (low-noise > noisy)."""
    start = date(2025, 1, 1)
    n = 64

    # Baseline market: moderate 1% volatility around upward trend
    market_closes = [100.0 * (1.002**i) for i in range(n)]
    m_returns = [
        (market_closes[t] - market_closes[t - 1]) / market_closes[t - 1] for t in range(1, n)
    ]

    # LOW_NOISE stock: follows market closely with tiny residual noise
    low_noise_closes = [market_closes[i] * (1.0 + 0.0001 * math.sin(i)) for i in range(n)]
    low_noise_bars = _generate_bars("LOW_NOISE", start, low_noise_closes)
    as_of = low_noise_bars[-1].exchange_date

    # HIGH_NOISE stock: same overall return, but wild oscillation (+/- 5% swings)
    high_noise_closes = [market_closes[i] * (1.0 + 0.05 * ((-1) ** i)) for i in range(n)]
    high_noise_bars = _generate_bars("HIGH_NOISE", start, high_noise_closes)

    vol_low = compute_idiosyncratic_volatility(low_noise_bars, as_of, m_returns, window=63)
    vol_high = compute_idiosyncratic_volatility(high_noise_bars, as_of, m_returns, window=63)

    assert vol_low is not None and vol_high is not None
    idio_low, beta_low = vol_low
    idio_high, beta_high = vol_high

    assert idio_low > 0.0
    assert idio_high > 0.0
    assert idio_low < idio_high  # Low noise has lower residual volatility

    # Rank universe: LOW_NOISE must rank higher than HIGH_NOISE due to volatility scaling
    engine = MultiFactorRankingEngine(FactorConfig(scoring_method="ratio", dampening_lambda=0.0))
    bars_by_sym = {"LOW_NOISE": low_noise_bars, "HIGH_NOISE": high_noise_bars}
    rankings = engine.rank_universe(as_of, ["LOW_NOISE", "HIGH_NOISE"], bars_by_sym)

    assert len(rankings) == 2
    assert rankings[0].symbol == "LOW_NOISE"
    assert rankings[0].score > rankings[1].score


def test_strict_point_in_time_isolation() -> None:
    """Future bars (> as_of_date) are completely ignored or rejected (zero look-ahead)."""
    start = date(2025, 1, 1)
    n = 64
    closes = [100.0 + i for i in range(n)]
    bars = _generate_bars("PIT_TEST", start, closes)
    as_of = bars[-1].exchange_date

    # Baseline calculation with bars strictly <= as_of
    engine_permissive = MultiFactorRankingEngine(FactorConfig(reject_future_bars=False))
    comp_clean = engine_permissive.compute_factor_components("PIT_TEST", as_of, bars)
    assert comp_clean is not None

    # Inject corrupt future bars on as_of + 1, as_of + 2 with absurd prices (e.g. 100,000)
    future_date_1 = as_of + timedelta(days=1)
    future_date_2 = as_of + timedelta(days=2)
    corrupted_bars = list(bars) + [
        Bar(
            "PIT_TEST",
            future_date_1,
            Decimal("99999"),
            Decimal("99999"),
            Decimal("99999"),
            Decimal("99999"),
            1000,
        ),
        Bar(
            "PIT_TEST", future_date_2, Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1"), 1000
        ),
    ]

    # In permissive mode, future bars are strictly filtered out (result bit-for-bit identical)
    comp_with_future = engine_permissive.compute_factor_components(
        "PIT_TEST", as_of, corrupted_bars
    )
    assert comp_with_future is not None
    assert comp_clean.intermediate_momentum_21_63 == comp_with_future.intermediate_momentum_21_63
    assert comp_clean.short_reversion_3_5 == comp_with_future.short_reversion_3_5
    assert comp_clean.idiosyncratic_volatility_63 == comp_with_future.idiosyncratic_volatility_63
    assert comp_clean.composite_score == comp_with_future.composite_score

    # In strict mode, presence of future bars raises PointInTimeError
    engine_strict = MultiFactorRankingEngine(FactorConfig(reject_future_bars=True))
    with pytest.raises(PointInTimeError, match="Future bar detected"):
        engine_strict.compute_factor_components("PIT_TEST", as_of, corrupted_bars)

    with pytest.raises(PointInTimeError, match="Future bar detected"):
        engine_strict.rank_universe(as_of, ["PIT_TEST"], {"PIT_TEST": corrupted_bars})


def test_deterministic_tie_breaking_by_symbol() -> None:
    """Ties in composite score are broken deterministically by symbol lexicographically."""
    start = date(2025, 1, 1)
    n = 64
    closes = [100.0 + i for i in range(n)]

    symbols = ["ZEBRA", "ALPHA", "DELTA", "BETA"]
    bars_by_symbol = {sym: _generate_bars(sym, start, closes) for sym in symbols}
    as_of = bars_by_symbol["ALPHA"][-1].exchange_date

    engine = MultiFactorRankingEngine(FactorConfig(scoring_method="ratio"))

    # Test with random order of eligible symbols
    rankings_1 = engine.rank_universe(as_of, ["ZEBRA", "ALPHA", "DELTA", "BETA"], bars_by_symbol)
    rankings_2 = engine.rank_universe(as_of, ["BETA", "DELTA", "ALPHA", "ZEBRA"], bars_by_symbol)

    # Scores must all be equal
    scores = [r.score for r in rankings_1]
    assert len(scores) == 4
    assert all(math.isclose(s, scores[0], rel_tol=1e-7) for s in scores)

    # Ranks must be assigned 1, 2, 3, 4
    ranks = [r.rank for r in rankings_1]
    assert ranks == [1, 2, 3, 4]

    # Order must be strictly lexicographic: ALPHA, BETA, DELTA, ZEBRA
    ordered_symbols = [r.symbol for r in rankings_1]
    assert ordered_symbols == ["ALPHA", "BETA", "DELTA", "ZEBRA"]

    # Invariant across different input permutations
    assert [r.symbol for r in rankings_2] == ["ALPHA", "BETA", "DELTA", "ZEBRA"]


def test_missing_and_insufficient_history_fail_closed() -> None:
    """Insufficient history, missing as_of bar, or circuit locks fail closed."""
    start = date(2025, 1, 1)
    engine = MultiFactorRankingEngine(FactorConfig(filter_circuit_locked=True))

    # 1. Empty bars list
    assert engine.compute_factor_components("EMPTY", date(2025, 5, 1), []) is None

    # 2. Too few bars (< 64 bars)
    short_bars = _generate_bars("SHORT", start, [100.0 + i for i in range(50)])
    as_of = short_bars[-1].exchange_date
    assert engine.compute_factor_components("SHORT", as_of, short_bars) is None

    # 3. 63 bars (exactly one short of minimum 64)
    bars_63 = _generate_bars("BARS63", start, [100.0 + i for i in range(63)])
    assert engine.compute_factor_components("BARS63", bars_63[-1].exchange_date, bars_63) is None

    # 4. Valid 64 bars, but missing as_of_date bar (as_of is tomorrow)
    bars_64 = _generate_bars("VALID", start, [100.0 + i for i in range(64)])
    as_of_future = bars_64[-1].exchange_date + timedelta(days=5)
    assert engine.compute_factor_components("VALID", as_of_future, bars_64) is None

    # 5. Circuit-locked on decision date (volume == 0 and high == low)
    locked_bars = _generate_bars(
        "LOCKED", start, [100.0 + i for i in range(64)], locked_indices={63}
    )
    assert (
        engine.compute_factor_components("LOCKED", locked_bars[-1].exchange_date, locked_bars)
        is None
    )

    # 6. Non-positive price
    bad_price_bars = list(bars_64[:-1]) + [
        Bar(
            "VALID",
            bars_64[-1].exchange_date,
            Decimal("0.00"),
            Decimal("0.00"),
            Decimal("0.00"),
            Decimal("0.00"),
            1000,
        )
    ]
    assert (
        engine.compute_factor_components("VALID", bad_price_bars[-1].exchange_date, bad_price_bars)
        is None
    )

    # 7. Universe ranking with all invalid names returns empty list
    invalid_universe = engine.rank_universe(
        as_of,
        ["EMPTY", "SHORT", "BARS63"],
        {"EMPTY": [], "SHORT": short_bars, "BARS63": bars_63},
    )
    assert invalid_universe == []


def test_factor_components_and_ranked_symbol_dataclass_contracts() -> None:
    """FactorComponents and RankedSymbol adhere strictly to interface contracts."""
    comp = FactorComponents(
        intermediate_momentum_21_63=0.15,
        short_reversion_3_5=0.02,
        idiosyncratic_volatility_63=0.012,
        composite_score=11.67,
        market_beta=1.15,
        raw_momentum_63=0.15,
        raw_momentum_21=0.05,
        raw_reversion_5=0.02,
        raw_reversion_3=0.01,
    )

    # Verify properties
    assert comp.intermediate_return == 0.15
    assert comp.short_return == 0.02
    assert comp.idiosyncratic_vol == 0.012
    assert comp.score == 11.67
    assert comp.market_beta == 1.15

    # RankedSymbol via positional arguments
    r1 = RankedSymbol("INFY", 1, 11.67, comp)
    assert r1.symbol == "INFY"
    assert r1.rank == 1
    assert r1.score == 11.67
    assert r1.components == comp
    assert r1.factor_values == comp

    # RankedSymbol via keyword arguments with factor_values alias
    r2 = RankedSymbol(symbol="TCS", rank=2, score=9.85, factor_values=comp)
    assert r2.symbol == "TCS"
    assert r2.components == comp

    # PointInTimeBar alias
    assert PointInTimeBar is Bar


def test_scoring_method_variations() -> None:
    """Scoring methods (ratio, ratio_zscore, linear_zscore) execute and rank predictably."""
    start = date(2025, 1, 1)
    n = 64
    symbols = ["SYM_A", "SYM_B", "SYM_C"]
    # Distinct trajectories
    closes_a = [100.0 + (30.0 * i / (n - 1)) for i in range(n)]  # +30%
    closes_b = [100.0 + (10.0 * i / (n - 1)) for i in range(n)]  # +10%
    closes_c = [100.0 - (10.0 * i / (n - 1)) for i in range(n)]  # -10%

    bars_by_sym = {
        "SYM_A": _generate_bars("SYM_A", start, closes_a),
        "SYM_B": _generate_bars("SYM_B", start, closes_b),
        "SYM_C": _generate_bars("SYM_C", start, closes_c),
    }
    as_of = bars_by_sym["SYM_A"][-1].exchange_date

    for method in ("ratio", "ratio_zscore", "linear_zscore"):
        engine = MultiFactorRankingEngine(FactorConfig(scoring_method=method))
        rankings = engine.rank_universe(as_of, symbols, bars_by_sym)
        assert len(rankings) == 3
        # In all methods, highest momentum should rank #1
        assert rankings[0].symbol == "SYM_A"
        assert rankings[1].symbol == "SYM_B"
        assert rankings[2].symbol == "SYM_C"


def test_heterogeneous_history_lengths_capm_regression() -> None:
    """CAPM residual volatility is computed for all eligible symbols across heterogeneous histories."""
    start = date(2025, 1, 1)
    n_max = 120
    # Time varying market returns with non-zero variance
    m_rets_raw = [0.01 * math.sin(i / 3.0) for i in range(n_max)]
    all_dates: list[date] = []
    d = start
    while len(all_dates) < n_max:
        if d.weekday() < 5:
            all_dates.append(d)
        d += timedelta(days=1)
    as_of = all_dates[-1]

    def make_bars_with_returns(sym: str, n: int, beta: float, noise: float) -> list[Bar]:
        dates = all_dates[-n:]
        rets = m_rets_raw[-n:]
        bars: list[Bar] = []
        price = 100.0
        prices = [price]
        for i in range(1, n):
            r = beta * rets[i] + noise * math.cos(i)
            price = price * (1.0 + r)
            prices.append(price)
        for dt, p in zip(dates, prices, strict=True):
            close_d = Decimal(str(round(p, 4)))
            bars.append(
                Bar(
                    symbol=sym,
                    exchange_date=dt,
                    open=close_d,
                    high=close_d + Decimal("1.0"),
                    low=max(close_d - Decimal("1.0"), Decimal("0.01")),
                    close=close_d,
                    volume=100000,
                )
            )
        return bars

    bars_64 = make_bars_with_returns("SYM_64", 64, 1.6, 0.001)
    bars_100 = make_bars_with_returns("SYM_100", 100, 0.6, 0.001)
    bars_120 = make_bars_with_returns("SYM_120", 120, 1.1, 0.001)

    engine = MultiFactorRankingEngine(FactorConfig())
    bars_by_sym = {"SYM_64": bars_64, "SYM_100": bars_100, "SYM_120": bars_120}
    rankings = engine.rank_universe(as_of, ["SYM_64", "SYM_100", "SYM_120"], bars_by_sym)

    assert len(rankings) == 3
    # Check that none of the symbols fell back to beta = 1.0
    for r in rankings:
        assert r.components.market_beta != 1.0
        assert r.components.idiosyncratic_volatility_63 > 0.0
        if r.symbol == "SYM_64":
            assert pytest.approx(r.components.market_beta, abs=0.25) == 1.45
        elif r.symbol == "SYM_100":
            assert pytest.approx(r.components.market_beta, abs=0.25) == 0.54
        elif r.symbol == "SYM_120":
            assert pytest.approx(r.components.market_beta, abs=0.25) == 1.00


def test_insufficient_history_for_lagged_momentum_fails_closed() -> None:
    """Lagged momentum and reversion fail closed (return None) when history < window + lag + 1."""
    start = date(2025, 1, 1)
    # 70 bars generated
    bars_70 = _generate_bars("SYM_70", start, [100.0 + i for i in range(70)])
    as_of = bars_70[-1].exchange_date

    # Window 63, Lag 21 requires 63 + 21 + 1 = 85 bars. 70 bars must return None!
    res_mom = compute_intermediate_momentum(bars_70, as_of, window=63, lag=21)
    assert res_mom is None

    # Exactly 84 bars (one short of 85) must return None
    bars_84 = _generate_bars("SYM_84", start, [100.0 + i for i in range(84)])
    as_of_84 = bars_84[-1].exchange_date
    assert compute_intermediate_momentum(bars_84, as_of_84, window=63, lag=21) is None

    # Exactly 85 bars must succeed
    bars_85 = _generate_bars("SYM_85", start, [100.0 + i for i in range(85)])
    as_of_85 = bars_85[-1].exchange_date
    assert compute_intermediate_momentum(bars_85, as_of_85, window=63, lag=21) is not None

    # Reversion: window 5, lag 3 requires 5 + 3 + 1 = 9 bars. 8 bars must return None!
    bars_8 = _generate_bars("SYM_8", start, [100.0 + i for i in range(8)])
    as_of_8 = bars_8[-1].exchange_date
    assert compute_short_term_reversion(bars_8, as_of_8, window=5, lag=3) is None

    # 9 bars must succeed
    bars_9 = _generate_bars("SYM_9", start, [100.0 + i for i in range(9)])
    as_of_9 = bars_9[-1].exchange_date
    assert compute_short_term_reversion(bars_9, as_of_9, window=5, lag=3) is not None


def test_fail_closed_rejection_of_nan_and_infinite_prices() -> None:
    """Decimal('NaN'), Decimal('Inf'), and float('nan') fail closed without exceptions or inversion."""
    start = date(2025, 1, 1)
    n = 64
    normal_closes = [100.0 + i for i in range(n)]
    normal_bars = _generate_bars("NORMAL", start, normal_closes)
    as_of = normal_bars[-1].exchange_date

    engine = MultiFactorRankingEngine(FactorConfig())

    # 1. Decision bar with Decimal('NaN') close must return None without raising decimal.InvalidOperation
    nan_close_bars = list(normal_bars[:-1]) + [
        Bar("NAN_CLOSE", as_of, Decimal("100"), Decimal("101"), Decimal("99"), Decimal("NaN"), 1000)
    ]
    assert engine.compute_factor_components("NAN_CLOSE", as_of, nan_close_bars) is None

    # 2. Decision bar with Decimal('Infinity') close must return None
    inf_close_bars = list(normal_bars[:-1]) + [
        Bar(
            "INF_CLOSE",
            as_of,
            Decimal("100"),
            Decimal("101"),
            Decimal("99"),
            Decimal("Infinity"),
            1000,
        )
    ]
    assert engine.compute_factor_components("INF_CLOSE", as_of, inf_close_bars) is None

    # 3. Decision bar with high < low must return None
    crossed_bar = list(normal_bars[:-1]) + [
        Bar("CROSSED", as_of, Decimal("100"), Decimal("90"), Decimal("110"), Decimal("100"), 1000)
    ]
    assert engine.compute_factor_components("CROSSED", as_of, crossed_bar) is None

    # 4. Historical bar with Decimal('NaN') at start price fails closed in momentum
    nan_start_bars = [
        Bar(
            "NAN_START",
            b.exchange_date,
            b.open,
            b.high,
            b.low,
            Decimal("NaN") if i == 0 else b.close,
            b.volume,
        )
        for i, b in enumerate(normal_bars)
    ]
    assert compute_intermediate_momentum(nan_start_bars, as_of, window=63, lag=0) is None

    # 5. Historical bar with Decimal('NaN') in window fails closed in idio-vol and factor components
    hist_nan_bars = [
        Bar(
            "HIST_NAN",
            b.exchange_date,
            b.open,
            b.high,
            b.low,
            Decimal("NaN") if i == 10 else b.close,
            b.volume,
        )
        for i, b in enumerate(normal_bars)
    ]
    assert compute_idiosyncratic_volatility(hist_nan_bars, as_of, window=63) is None
    assert engine.compute_factor_components("HIST_NAN", as_of, hist_nan_bars) is None

    # 6. Historical NaN symbol does not corrupt universe market returns or invert ranking
    bars_by_sym = {
        "NORMAL": normal_bars,
        "NAN_SYM": hist_nan_bars,
    }
    rankings = engine.rank_universe(as_of, ["NORMAL", "NAN_SYM"], bars_by_sym)
    # NAN_SYM is filtered out, NORMAL ranks #1 with valid finite score
    assert len(rankings) == 1
    assert rankings[0].symbol == "NORMAL"
    assert rankings[0].rank == 1
    assert math.isfinite(rankings[0].score)
