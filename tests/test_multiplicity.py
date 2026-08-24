"""Tests for OverfittingDiagnostics and Deflated Sharpe Ratio (DSR)."""

import math

import pytest

from quant_system.analytics.errors import MultiplicityError, MultiplicityFailureCode
from quant_system.analytics.multiplicity import OverfittingDiagnostics


def _population_moments(values: tuple[float, ...]) -> tuple[float, float]:
    """Independently derive population moments for a hand-defined return series."""
    mean = sum(values) / len(values)
    deviations = tuple(value - mean for value in values)
    variance = sum(value**2 for value in deviations) / len(values)
    skewness = (sum(value**3 for value in deviations) / len(values)) / variance**1.5
    kurtosis = (sum(value**4 for value in deviations) / len(values)) / variance**2
    return skewness, kurtosis


def test_single_trial_dsr_retains_sampling_uncertainty() -> None:
    short = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=0.1,
        num_trials=1,
        sample_length_bars=2,
    )
    long = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=0.1,
        num_trials=1,
        sample_length_bars=252,
    )
    tiny = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=1e-12,
        num_trials=1,
        sample_length_bars=252,
    )

    assert 0.5 < short < long < 1.0
    assert 0.5 < tiny < 0.50000000001


def test_more_trials_reduce_dsr_under_same_null_dispersion() -> None:
    single = OverfittingDiagnostics.deflated_sharpe_ratio(1.2, 1, 252)
    hundred = OverfittingDiagnostics.deflated_sharpe_ratio(1.2, 100, 252)

    assert 0.0 <= hundred < single <= 1.0


@pytest.mark.parametrize(
    ("num_trials", "sample_length", "periods"),
    ((True, 252, 252), (1, False, 252), (1, 252, True), (0, 252, 252), (1, 1, 252)),
)
def test_dsr_rejects_wrong_type_and_invalid_counts(
    num_trials: int,
    sample_length: int,
    periods: int,
) -> None:
    with pytest.raises(ValueError) as captured:
        OverfittingDiagnostics.deflated_sharpe_ratio(
            estimated_sharpe=1.0,
            num_trials=num_trials,
            sample_length_bars=sample_length,
            periods_per_year=periods,
        )

    assert type(captured.value) is ValueError


def test_dsr_uses_return_moments() -> None:
    normal = OverfittingDiagnostics.deflated_sharpe_ratio(1.0, 2, 252)
    asymmetric = OverfittingDiagnostics.deflated_sharpe_ratio(
        1.0,
        2,
        252,
        skewness=-1.0,
        kurtosis=6.0,
    )

    assert asymmetric < normal


@pytest.mark.parametrize(
    ("sample_size", "high_count", "low", "high"),
    (
        (30, 1, 0.0, 0.05),
        (100, 30, -2.5, 7.25),
        (63, 1, 0.0, 0.0123),
        (40, 13, 5.0, -3.0),
        (1000, 440, 0.001, -0.002),
    ),
)
def test_two_point_moment_equality_is_not_rejected_by_binary_rounding(
    sample_size: int,
    high_count: int,
    low: float,
    high: float,
) -> None:
    """Pearson's bound is equality for every two-point distribution.

    The table varies sample size, probability, sign, and outcome magnitude. The first case
    reproduces the live failure: binary64 puts kurtosis 7.105e-15 below the equal bound.
    """
    returns = (low,) * (sample_size - high_count) + (high,) * high_count
    skewness, kurtosis = _population_moments(returns)

    probability = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=0.5,
        num_trials=2,
        sample_length_bars=len(returns),
        skewness=skewness,
        kurtosis=kurtosis,
    )

    assert 0.0 <= probability <= 1.0


def test_impossible_moment_pair_has_a_stable_failure_code() -> None:
    """A real violation still fails; callers need a code rather than a message."""
    with pytest.raises(MultiplicityError) as captured:
        OverfittingDiagnostics.deflated_sharpe_ratio(
            estimated_sharpe=0.5,
            num_trials=2,
            sample_length_bars=30,
            skewness=2.0,
            kurtosis=4.0,
        )

    assert captured.value.code is MultiplicityFailureCode.MOMENT_CONSTRAINT_INVALID


def test_one_ulp_pearson_shortfall_is_treated_as_boundary_equality() -> None:
    pearson_bound = 5.0  # skewness=2 -> 1 + skewness**2
    one_ulp_below = math.nextafter(pearson_bound, -math.inf)

    probability = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=0.5,
        num_trials=2,
        sample_length_bars=30,
        skewness=2.0,
        kurtosis=one_ulp_below,
    )

    assert 0.0 <= probability <= 1.0
