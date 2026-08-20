"""Deflated Sharpe Ratio (DSR) and statistical overfitting corrections (Bailey & Lopez de Prado)."""

from __future__ import annotations

import math


class OverfittingDiagnostics:
    """Corrects for multiple testing / data mining bias when testing N strategy variations."""

    @staticmethod
    def deflated_sharpe_ratio(
        estimated_sharpe: float,
        num_trials: int,
        sample_length_bars: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
    ) -> float:
        """Calculates the probability that the estimated Sharpe Ratio is false discovery given N trials."""
        if num_trials <= 1:
            return 1.0 if estimated_sharpe > 0 else 0.0

        # Euler-Mascheroni constant
        euler = 0.5772156649

        # Expected maximum Sharpe under null hypothesis (independent trials)
        z = math.sqrt(2.0 * math.log(num_trials))
        expected_max_sr = (1.0 - euler / (z**2)) / z + z if z > 0 else 0.0

        # Variance of Sharpe ratio estimator
        sr_variance = (
            1.0 - (skewness * estimated_sharpe) + (((kurtosis - 1.0) / 4.0) * (estimated_sharpe**2))
        ) / max(1, sample_length_bars)

        sr_std = math.sqrt(max(1e-8, sr_variance))

        # Z-test statistic against expected max Sharpe
        test_stat = (estimated_sharpe - expected_max_sr) / sr_std

        # Standard normal CDF
        dsr_prob = (1.0 + math.erf(test_stat / math.sqrt(2.0))) / 2.0
        return max(0.0, min(1.0, dsr_prob))
