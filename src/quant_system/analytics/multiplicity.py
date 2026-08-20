"""Deflated Sharpe Ratio (DSR) and statistical overfitting corrections (Bailey & Lopez de Prado)."""

from __future__ import annotations

import math
from statistics import NormalDist

_EULER_MASCHERONI = 0.5772156649015329
_STANDARD_NORMAL = NormalDist()


class OverfittingDiagnostics:
    """Corrects for multiple testing / data mining bias when testing N strategy variations."""

    @staticmethod
    def deflated_sharpe_ratio(
        estimated_sharpe: float,
        num_trials: int,
        sample_length_bars: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0,
        periods_per_year: int = 252,
        trial_sharpe_std: float | None = None,
    ) -> float:
        """Return sampling- and multiplicity-aware DSR probability.

        The input Sharpe and optional cross-trial dispersion are annualized. When empirical
        cross-trial dispersion is unavailable, the null sampling error is used explicitly rather
        than inventing unit Sharpe dispersion. For one trial, the selection benchmark is zero and
        this reduces to the Probabilistic Sharpe Ratio.
        """
        _validate_dsr_inputs(
            estimated_sharpe,
            num_trials,
            sample_length_bars,
            skewness,
            kurtosis,
            periods_per_year,
            trial_sharpe_std,
        )
        annualization = math.sqrt(periods_per_year)
        periodic_sharpe = estimated_sharpe / annualization
        if trial_sharpe_std is None:
            null_trial_std = 1.0 / math.sqrt(sample_length_bars - 1)
        else:
            null_trial_std = trial_sharpe_std / annualization
        benchmark = null_trial_std * _expected_max_standard_normal(num_trials)
        variance_term = (
            1.0 - skewness * periodic_sharpe + ((kurtosis - 1.0) / 4.0) * periodic_sharpe**2
        )
        if variance_term <= 0.0:
            raise ValueError("Sharpe sampling variance must be positive")
        test_stat = (
            (periodic_sharpe - benchmark)
            * math.sqrt(sample_length_bars - 1)
            / math.sqrt(variance_term)
        )
        dsr_prob = _STANDARD_NORMAL.cdf(test_stat)
        return max(0.0, min(1.0, dsr_prob))


def _expected_max_standard_normal(num_trials: int) -> float:
    if num_trials == 1:
        return 0.0
    first = _STANDARD_NORMAL.inv_cdf(1.0 - 1.0 / num_trials)
    second = _STANDARD_NORMAL.inv_cdf(1.0 - 1.0 / (num_trials * math.e))
    return (1.0 - _EULER_MASCHERONI) * first + _EULER_MASCHERONI * second


def _validate_dsr_inputs(
    estimated_sharpe: float,
    num_trials: int,
    sample_length_bars: int,
    skewness: float,
    kurtosis: float,
    periods_per_year: int,
    trial_sharpe_std: float | None,
) -> None:
    if (
        type(num_trials) is not int
        or type(sample_length_bars) is not int
        or type(periods_per_year) is not int
        or num_trials < 1
        or sample_length_bars < 2
        or periods_per_year < 1
    ):
        raise ValueError("DSR counts must be exact positive integers and need at least two bars")
    numeric = (estimated_sharpe, skewness, kurtosis)
    if any(isinstance(value, bool) or not math.isfinite(value) for value in numeric):
        raise ValueError("DSR numeric inputs must be finite numbers")
    if kurtosis < 1.0 + skewness**2:
        raise ValueError("kurtosis is inconsistent with the supplied skewness")
    if trial_sharpe_std is not None and (
        isinstance(trial_sharpe_std, bool)
        or not math.isfinite(trial_sharpe_std)
        or trial_sharpe_std < 0.0
    ):
        raise ValueError("cross-trial Sharpe dispersion must be finite and nonnegative")
