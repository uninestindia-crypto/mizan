"""Tests for technical indicators and factor transforms."""

from quant_system.alpha.technical import TechnicalIndicators
from quant_system.alpha.transform import FactorTransform
from quant_system.core.domain import PriceBar


def test_sma_and_ema(sample_bars: list[PriceBar]) -> None:
    closes = [b.close for b in sample_bars]
    sma20 = TechnicalIndicators.sma(closes, 20)
    ema20 = TechnicalIndicators.ema(closes, 20)

    assert len(sma20) == len(closes) - 19
    assert len(ema20) == len(closes) - 19
    # Smas and Emas should track closely
    assert abs(sma20[-1] - ema20[-1]) / sma20[-1] < 0.10


def test_rsi(sample_bars: list[PriceBar]) -> None:
    closes = [b.close for b in sample_bars]
    rsi14 = TechnicalIndicators.rsi(closes, 14)
    assert len(rsi14) == len(closes) - 14

    out_of_range = [value for value in rsi14 if not 0.0 <= value <= 100.0]
    assert out_of_range == [], f"RSI outside [0, 100]: {out_of_range[:5]}"


def test_rsi_flat_prices() -> None:
    flat_closes = [100.0] * 30
    rsi = TechnicalIndicators.rsi(flat_closes, 14)
    assert len(rsi) == 16

    not_neutral = [value for value in rsi if value != 50.0]
    assert not_neutral == [], f"flat prices must give a neutral RSI, got {not_neutral[:5]}"


def test_atr(sample_bars: list[PriceBar]) -> None:
    atr14 = TechnicalIndicators.atr(sample_bars, 14)
    assert len(atr14) == len(sample_bars) - 13

    non_positive = [value for value in atr14 if value <= 0.0]
    assert non_positive == [], f"ATR must be strictly positive, got {non_positive[:5]}"


def test_bollinger_bands(sample_bars: list[PriceBar]) -> None:
    closes = [b.close for b in sample_bars]
    upper, mid, lower = TechnicalIndicators.bollinger_bands(closes, 20, 2.0)
    assert len(upper) == len(mid) == len(lower) == len(closes) - 19

    bands = zip(upper, mid, lower, strict=True)
    unordered = [t for t in bands if not t[0] >= t[1] >= t[2]]
    assert unordered == [], f"bands must stay ordered upper >= mid >= lower, got {unordered[:3]}"


def test_momentum() -> None:
    vals = [100.0, 105.0, 110.0, 120.0]
    mom = TechnicalIndicators.momentum(vals, 2)
    assert len(mom) == 2
    assert abs(mom[0] - (110.0 - 100.0) / 100.0) < 1e-6
    assert abs(mom[1] - (120.0 - 105.0) / 105.0) < 1e-6

    # Test division by zero guard
    zero_vals = [0.0, 10.0, 20.0]
    mom_zero = TechnicalIndicators.momentum(zero_vals, 1)
    assert mom_zero[0] == 0.0


def test_factor_transforms() -> None:
    raw_scores = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0, "E": 1000.0}

    # Winsorize clips outlier E
    winsorized = FactorTransform.winsorize(raw_scores, (0.1, 0.9))
    assert winsorized["E"] < 1000.0

    # Zscore has zero mean
    z = FactorTransform.zscore(raw_scores)
    mean_z = sum(z.values()) / len(z)
    assert abs(mean_z) < 1e-6

    # Rank normalization maps to [-1.0, 1.0]
    ranks = FactorTransform.rank_normalize(raw_scores)
    assert ranks["A"] == -1.0
    assert ranks["E"] == 1.0

    # Edge cases
    assert FactorTransform.zscore({"A": 10.0}) == {"A": 0.0}
    assert FactorTransform.rank_normalize({}) == {}
    assert FactorTransform.winsorize({}) == {}
