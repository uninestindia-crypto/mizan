"""Cross-sectional statistical factor transformations, winsorization, and ranking."""

from __future__ import annotations

import math
from collections.abc import Mapping


class FactorTransform:
    """Transforms raw alpha factor scores into standardized, market-neutral weights."""

    @staticmethod
    def winsorize(
        scores: Mapping[str, float], limits: tuple[float, float] = (0.05, 0.95)
    ) -> dict[str, float]:
        """Clips extreme outlier values to the percentile limits."""
        if not scores:
            return {}
        vals = sorted(scores.values())
        n = len(vals)
        low_lim = max(0.0, min(1.0, limits[0]))
        high_lim = max(0.0, min(1.0, limits[1]))
        low_idx = max(0, min(n - 1, int(n * low_lim)))
        high_idx = max(0, min(n - 1, int(n * high_lim) - 1))

        low_val = vals[low_idx]
        high_val = vals[high_idx]
        if low_val > high_val:
            low_val, high_val = high_val, low_val

        return {sym: max(low_val, min(high_val, score)) for sym, score in scores.items()}

    @staticmethod
    def zscore(scores: Mapping[str, float]) -> dict[str, float]:
        """Normalizes scores to mean 0 and standard deviation 1."""
        if not scores or len(scores) < 2:
            return dict.fromkeys(scores, 0.0)

        vals = list(scores.values())
        mean = sum(vals) / len(vals)
        variance = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
        std = math.sqrt(variance)

        if std < 1e-12:
            return dict.fromkeys(scores, 0.0)

        return {sym: (score - mean) / std for sym, score in scores.items()}

    @staticmethod
    def rank_normalize(scores: Mapping[str, float]) -> dict[str, float]:
        """Converts raw scores into uniform ranks in range [-1.0, 1.0] with zero mean."""
        if not scores:
            return {}
        sorted_pairs = sorted(scores.items(), key=lambda item: item[1])
        n = len(sorted_pairs)
        if n == 1:
            return {sorted_pairs[0][0]: 0.0}

        ranked: dict[str, float] = {}
        for rank_idx, (sym, _) in enumerate(sorted_pairs):
            # Map 0..n-1 to -1.0 .. +1.0
            norm_val = 2.0 * (rank_idx / (n - 1)) - 1.0
            ranked[sym] = norm_val
        return ranked
