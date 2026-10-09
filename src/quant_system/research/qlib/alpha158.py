"""Point-in-time, zero-lookahead implementation of Qlib's Alpha158 factor expressions.

Learned directly from Microsoft Qlib's factor definitions:
- Local source: ``d:/Quant OS Project/qlib-main/qlib/contrib/data/handler.py`` (Alpha158 class)
- Upstream: ``https://github.com/microsoft/qlib/blob/main/qlib/contrib/data/handler.py``

Every factor here is strictly causal: bar ``i`` depends only on historical information
strictly available on or before the close of bar ``i``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Final

import numpy as np

from quant_system.data.market_data import PointInTimeBar

#: Fewest bars required to compute the longest lookback (60 periods + 5 buffer bars).
QLIB_ALPHA158_MINIMUM_BARS: Final = 65

#: Canonical trailing window consumed by the extractor for stable cross-sectional convergence.
QLIB_ALPHA158_CANONICAL_WINDOW_BARS: Final = 250

#: Canonical lookback windows used in Qlib Alpha158.
LOOKBACK_WINDOWS: Final = (5, 10, 20, 30, 60)

_EPSILON: Final = 1e-12


def _safe_div(numerator: float, denominator: float, fallback: float = 0.0) -> float:
    """Safe scalar division preventing zero-division or NaN."""
    if abs(denominator) < _EPSILON or math.isnan(denominator) or math.isnan(numerator):
        return fallback
    result = numerator / denominator
    return fallback if (math.isnan(result) or math.isinf(result)) else float(result)


def _safe_corr(x: np.ndarray, y: np.ndarray, fallback: float = 0.0) -> float:
    """Calculate Pearson correlation between two 1D series, returning fallback if variance is 0."""
    std_x = float(np.std(x))
    std_y = float(np.std(y))
    if std_x < _EPSILON or std_y < _EPSILON:
        return fallback
    cov = float(np.cov(x, y)[0, 1])
    return _safe_div(cov, std_x * std_y, fallback=fallback)


class QlibAlpha158Extractor:
    """Extracts causal Qlib Alpha158 factors from historical PointInTimeBar sequences."""

    def __init__(self, windows: Sequence[int] = LOOKBACK_WINDOWS) -> None:
        self.windows = tuple(windows)
        self.feature_names = self._build_feature_names()

    def _build_feature_names(self) -> tuple[str, ...]:
        names: list[str] = [
            "kmid",
            "klen",
            "kmid2",
            "kup",
            "kup2",
            "klow",
            "klow2",
            "ksft",
            "ksft2",
        ]
        for w in self.windows:
            names.extend(
                [
                    f"ma_{w}",
                    f"std_{w}",
                    f"roc_{w}",
                    f"max_{w}",
                    f"min_{w}",
                    f"qtlu_{w}",
                    f"qtld_{w}",
                    f"vma_{w}",
                    f"vstd_{w}",
                    f"vroc_{w}",
                    f"corr_{w}",
                ]
            )
        return tuple(names)

    def extract_features(self, bars: Sequence[Any]) -> dict[str, float]:
        """Compute the factor map for the latest bar in the sequence.

        Parameters
        ----------
        bars : Sequence[PointInTimeBar]
            Ascending sequence of daily bars up to and including the current decision session.

        Returns
        -------
        dict[str, float]
            Map of feature name to numeric value.
        """
        if len(bars) < QLIB_ALPHA158_MINIMUM_BARS:
            raise ValueError(
                f"Insufficient bars for Qlib Alpha158: requires at least "
                f"{QLIB_ALPHA158_MINIMUM_BARS}, got {len(bars)}"
            )

        # Slice to canonical maximum window to bound computation
        window_bars = bars[-QLIB_ALPHA158_CANONICAL_WINDOW_BARS:]
        opens = np.array([float(b.open) for b in window_bars], dtype=np.float64)
        highs = np.array([float(b.high) for b in window_bars], dtype=np.float64)
        lows = np.array([float(b.low) for b in window_bars], dtype=np.float64)
        closes = np.array([float(b.close) for b in window_bars], dtype=np.float64)
        volumes = np.array([float(b.volume) for b in window_bars], dtype=np.float64)

        curr_open = opens[-1]
        curr_high = highs[-1]
        curr_low = lows[-1]
        curr_close = closes[-1]
        curr_vol = volumes[-1]
        hl_range = curr_high - curr_low

        features: dict[str, float] = {}

        # 1. K-line intrinsic candlestick features
        features["kmid"] = _safe_div(curr_close - curr_open, curr_open)
        features["klen"] = _safe_div(curr_high - curr_low, curr_open)
        features["kmid2"] = _safe_div(curr_close - curr_open, hl_range)
        features["kup"] = _safe_div(curr_high - max(curr_open, curr_close), curr_open)
        features["kup2"] = _safe_div(curr_high - max(curr_open, curr_close), hl_range)
        features["klow"] = _safe_div(min(curr_open, curr_close) - curr_low, curr_open)
        features["klow2"] = _safe_div(min(curr_open, curr_close) - curr_low, hl_range)
        features["ksft"] = _safe_div(2 * curr_close - curr_high - curr_low, curr_open)
        features["ksft2"] = _safe_div(2 * curr_close - curr_high - curr_low, hl_range)

        # 2. Multi-horizon rolling statistics
        for w in self.windows:
            w_closes = closes[-w:]
            w_highs = highs[-w:]
            w_lows = lows[-w:]
            w_vols = volumes[-w:]

            # Price momentum & distributions
            mean_c = float(np.mean(w_closes))
            std_c = float(np.std(w_closes))
            features[f"ma_{w}"] = _safe_div(mean_c, curr_close) - 1.0
            features[f"std_{w}"] = _safe_div(std_c, curr_close)

            # Rate of change relative to bar w sessions ago
            ref_c = closes[-w - 1] if len(closes) > w else closes[0]
            features[f"roc_{w}"] = _safe_div(curr_close, ref_c) - 1.0

            # Channel extremes
            features[f"max_{w}"] = _safe_div(float(np.max(w_highs)), curr_close) - 1.0
            features[f"min_{w}"] = _safe_div(float(np.min(w_lows)), curr_close) - 1.0

            # Quantiles
            features[f"qtlu_{w}"] = _safe_div(float(np.quantile(w_closes, 0.8)), curr_close) - 1.0
            features[f"qtld_{w}"] = _safe_div(float(np.quantile(w_closes, 0.2)), curr_close) - 1.0

            # Volume dynamics
            mean_v = float(np.mean(w_vols))
            std_v = float(np.std(w_vols))
            features[f"vma_{w}"] = _safe_div(mean_v, curr_vol) - 1.0
            features[f"vstd_{w}"] = _safe_div(std_v, curr_vol)
            ref_v = volumes[-w - 1] if len(volumes) > w else volumes[0]
            features[f"vroc_{w}"] = _safe_div(curr_vol, ref_v) - 1.0

            # Price-volume interaction
            features[f"corr_{w}"] = _safe_corr(w_closes, w_vols)

        return features


_GLOBAL_EXTRACTOR = QlibAlpha158Extractor()


def compute_qlib_alpha_features(bars: Sequence[PointInTimeBar]) -> dict[str, float]:
    """Convenience functional wrapper around default QlibAlpha158Extractor."""
    return _GLOBAL_EXTRACTOR.extract_features(bars)
