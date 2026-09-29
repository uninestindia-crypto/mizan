"""Pure price-series metrics used by the screener, stock page and lab.

Every function takes plain float arrays ordered oldest first and never looks past the last element,
so a value computed at index ``t`` uses only data up to ``t``. Periods are counted in trading
sessions, not calendar days.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

SESSIONS_PER_YEAR = 252
SESSIONS_1M = 21
SESSIONS_6M = 126
SESSIONS_1Y = 252


def period_return(close: FloatArray, sessions: int) -> float | None:
    """Simple return over the last ``sessions`` sessions, or None without enough history."""
    if close.size <= sessions:
        return None
    start = close[-sessions - 1]
    return float(close[-1] / start - 1.0) if start > 0 else None


def annualized_volatility(close: FloatArray, sessions: int = SESSIONS_1Y) -> float | None:
    """Standard deviation of daily log returns over the window, annualized."""
    if close.size < 21:
        return None
    window = close[-(sessions + 1) :]
    log_returns = np.diff(np.log(window))
    if log_returns.size < 20:
        return None
    return float(np.std(log_returns, ddof=1) * math.sqrt(SESSIONS_PER_YEAR))


def max_drawdown(values: FloatArray) -> float:
    """Largest peak-to-trough fall as a negative fraction (0.0 when the series never falls)."""
    if values.size == 0:
        return 0.0
    peaks = np.maximum.accumulate(values)
    drawdowns = values / peaks - 1.0
    return float(drawdowns.min())


def drawdown_series(values: FloatArray) -> FloatArray:
    if values.size == 0:
        return values
    peaks = np.maximum.accumulate(values)
    out: FloatArray = values / peaks - 1.0
    return out


def rolling_mean(values: FloatArray, window: int) -> FloatArray:
    """Trailing simple moving average; NaN until ``window`` values exist."""
    out = np.full(values.shape, np.nan, dtype=np.float64)
    if window <= 0 or values.size < window:
        return out
    cumsum = np.cumsum(np.insert(values, 0, 0.0))
    out[window - 1 :] = (cumsum[window:] - cumsum[:-window]) / window
    return out


def rolling_max(values: FloatArray, window: int) -> FloatArray:
    out = np.full(values.shape, np.nan, dtype=np.float64)
    if window <= 0 or values.size < window:
        return out
    view = np.lib.stride_tricks.sliding_window_view(values, window)
    out[window - 1 :] = view.max(axis=1)
    return out


def rolling_min(values: FloatArray, window: int) -> FloatArray:
    out = np.full(values.shape, np.nan, dtype=np.float64)
    if window <= 0 or values.size < window:
        return out
    view = np.lib.stride_tricks.sliding_window_view(values, window)
    out[window - 1 :] = view.min(axis=1)
    return out


def rsi(close: FloatArray, period: int = 14) -> FloatArray:
    """Wilder's RSI, NaN until ``period`` changes exist. Uses only past and current closes."""
    out = np.full(close.shape, np.nan, dtype=np.float64)
    if period <= 0 or close.size <= period:
        return out
    change = np.diff(close)
    gains = np.clip(change, 0.0, None)
    losses = np.clip(-change, 0.0, None)
    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period, change.size):
        avg_gain = (avg_gain * (period - 1) + float(gains[i])) / period
        avg_loss = (avg_loss * (period - 1) + float(losses[i])) / period
        out[i + 1] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def beta(asset_close: FloatArray, bench_close: FloatArray) -> float | None:
    """Beta of daily simple returns on aligned closes; None with fewer than 60 overlapping returns."""
    if asset_close.size != bench_close.size or asset_close.size < 61:
        return None
    a = np.diff(asset_close) / asset_close[:-1]
    b = np.diff(bench_close) / bench_close[:-1]
    variance = float(np.var(b, ddof=1))
    if variance <= 0.0:
        return None
    return float(np.cov(a, b, ddof=1)[0, 1] / variance)


def median_turnover_crore(
    close: FloatArray, volume: FloatArray, sessions: int = 60
) -> float | None:
    """Median daily traded value over the window, in ₹ crore (1 crore = 1e7)."""
    if close.size == 0:
        return None
    window_value = close[-sessions:] * volume[-sessions:]
    return float(np.median(window_value) / 1e7)


def finite_or_none(value: float) -> float | None:
    return value if math.isfinite(value) else None
