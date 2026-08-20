"""Tests for OverfittingDiagnostics and Deflated Sharpe Ratio (DSR)."""

from quant_system.analytics.multiplicity import OverfittingDiagnostics


def test_deflated_sharpe_ratio() -> None:
    # Single trial
    dsr_single = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=1.5,
        num_trials=1,
        sample_length_bars=252,
    )
    assert dsr_single == 1.0

    # Negative Sharpe with single trial
    dsr_neg = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=-0.5,
        num_trials=1,
        sample_length_bars=252,
    )
    assert dsr_neg == 0.0

    # 100 trials, sample length 252 bars
    dsr_100 = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=1.2,
        num_trials=100,
        sample_length_bars=252,
    )
    assert 0.0 <= dsr_100 <= 1.0
