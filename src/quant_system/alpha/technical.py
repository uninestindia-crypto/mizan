"""Technical indicators and momentum/volatility alpha factors."""

from __future__ import annotations

import math
from collections.abc import Sequence
from decimal import Decimal

from quant_system.core.domain import PriceBar


class TechnicalIndicators:
    """Computes technical indicator factors over historical price series."""

    @staticmethod
    def sma(values: Sequence[Decimal | float], period: int) -> list[float]:
        """Simple Moving Average."""
        if len(values) < period or period <= 0:
            return []
        float_vals = [float(v) for v in values]
        result = []
        curr_sum = sum(float_vals[:period])
        result.append(curr_sum / period)

        for i in range(period, len(float_vals)):
            curr_sum += float_vals[i] - float_vals[i - period]
            result.append(curr_sum / period)
        return result

    @staticmethod
    def ema(values: Sequence[Decimal | float], period: int) -> list[float]:
        """Exponential Moving Average."""
        if len(values) < period or period <= 0:
            return []
        float_vals = [float(v) for v in values]
        k = 2.0 / (period + 1.0)
        ema_val = sum(float_vals[:period]) / period
        result = [ema_val]

        for val in float_vals[period:]:
            ema_val = (val * k) + (ema_val * (1.0 - k))
            result.append(ema_val)
        return result

    @staticmethod
    def rsi(values: Sequence[Decimal | float], period: int = 14) -> list[float]:
        """Relative Strength Index (Wilder's RSI)."""
        if len(values) <= period:
            return []
        float_vals = [float(v) for v in values]
        deltas = [float_vals[i] - float_vals[i - 1] for i in range(1, len(float_vals))]

        gains = [max(0.0, d) for d in deltas]
        losses = [max(0.0, -d) for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        result = []
        if avg_loss == 0:
            result.append(50.0 if avg_gain == 0 else 100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - (100.0 / (1.0 + rs)))

        for i in range(period, len(deltas)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

            if avg_loss == 0:
                result.append(50.0 if avg_gain == 0 else 100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100.0 - (100.0 / (1.0 + rs)))

        return result

    @staticmethod
    def atr(bars: Sequence[PriceBar], period: int = 14) -> list[float]:
        """Average True Range (volatility measure)."""
        if len(bars) <= period or period <= 0:
            return []

        tr_list = []
        for i in range(len(bars)):
            high_val = float(bars[i].high)
            low_val = float(bars[i].low)
            if i == 0:
                tr_list.append(high_val - low_val)
            else:
                prev_c = float(bars[i - 1].close)
                tr = max(high_val - low_val, abs(high_val - prev_c), abs(low_val - prev_c))
                tr_list.append(tr)

        atr_val = sum(tr_list[:period]) / period
        result = [atr_val]

        for i in range(period, len(tr_list)):
            atr_val = ((atr_val * (period - 1)) + tr_list[i]) / period
            result.append(atr_val)

        return result

    @staticmethod
    def bollinger_bands(
        values: Sequence[Decimal | float],
        period: int = 20,
        num_std: float = 2.0,
    ) -> tuple[list[float], list[float], list[float]]:
        """Bollinger Bands (Upper, Middle, Lower)."""
        if len(values) < period or period <= 0:
            return [], [], []

        float_vals = [float(v) for v in values]
        upper, mid, lower = [], [], []

        for i in range(period, len(float_vals) + 1):
            window = float_vals[i - period : i]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = math.sqrt(variance)

            mid.append(mean)
            upper.append(mean + (num_std * std))
            lower.append(mean - (num_std * std))

        return upper, mid, lower

    @staticmethod
    def momentum(values: Sequence[Decimal | float], lookback: int) -> list[float]:
        """Rate of Return momentum over lookback periods."""
        if len(values) <= lookback or lookback <= 0:
            return []
        float_vals = [float(v) for v in values]
        result = []
        for i in range(lookback, len(float_vals)):
            prev = float_vals[i - lookback]
            if prev != 0.0:
                result.append((float_vals[i] - prev) / prev)
            else:
                result.append(0.0)
        return result
