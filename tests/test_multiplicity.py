"""Tests for OverfittingDiagnostics and Deflated Sharpe Ratio (DSR)."""

import pytest

from quant_system.analytics.multiplicity import OverfittingDiagnostics


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
) -> None:  # test-allow: no-assertion - pytest.raises is the behavioral assertion.
    with pytest.raises(ValueError):
        OverfittingDiagnostics.deflated_sharpe_ratio(
            estimated_sharpe=1.0,
            num_trials=num_trials,
            sample_length_bars=sample_length,
            periods_per_year=periods,
        )


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
