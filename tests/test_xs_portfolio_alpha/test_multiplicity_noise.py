"""Unit tests for MultiplicityNoiseBenchmarker, trial budget, and DSR (R4)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quant_system.research_xs_monthly.noise_benchmarker import (
    MultiplicityNoiseBenchmarker,
    NoiseBenchmarkResults,
    SpentTrial,
    compute_governed_dsr,
    declared_spent_trials,
    default_ledger_path,
    read_spent_trials,
    read_trial_budget,
    require_declared_trials,
)


class TestTrialLedgerBudget:
    """Tests for TRIAL-LEDGER.md parsing and runtime trial budget enforcement."""

    def test_default_ledger_path_exists(self) -> None:
        """Verify the pre-declared trial ledger exists at default repository path."""
        path = default_ledger_path()
        assert path.is_file(), f"TRIAL-LEDGER.md must exist at {path}"

    def test_read_spent_trials(self) -> None:
        """Verify SPENT trials are correctly parsed from the frozen ledger."""
        trials = read_spent_trials()
        assert len(trials) >= 1
        assert isinstance(trials[0], SpentTrial)
        assert trials[0].number == 1
        assert trials[0].status == "SPENT"
        assert "xs_multi_factor" in trials[0].family

    def test_declared_spent_trials_count(self) -> None:
        """Verify declared_spent_trials matches length of SPENT rows."""
        count = declared_spent_trials()
        assert count >= 1

    def test_read_trial_budget(self) -> None:
        """Verify read_trial_budget reads the declared budget of 5."""
        budget = read_trial_budget()
        assert budget == 5

    def test_require_declared_trials_success(self) -> None:
        """Verify require_declared_trials passes when matching spent count or budget."""
        # Check against spent count (1) and declared budget (5)
        spent = declared_spent_trials()
        budget = read_trial_budget()
        assert require_declared_trials(spent) == spent
        assert require_declared_trials(budget) == budget

    def test_require_declared_trials_mismatch_raises_error(self) -> None:
        """Verify require_declared_trials fails closed when declared count disagrees."""
        with pytest.raises(ValueError, match="disagrees with"):
            require_declared_trials(999)

    def test_missing_ledger_raises_file_not_found(self, tmp_path: Path) -> None:
        """Verify reading a missing ledger raises FileNotFoundError."""
        missing = tmp_path / "NON_EXISTENT_LEDGER.md"
        with pytest.raises(FileNotFoundError):
            read_spent_trials(missing)


class TestMultiplicityBudgetConsumption:
    """Tests for MultiplicityNoiseBenchmarker trial budget consumption."""

    def test_budget_consumption_within_limit(self) -> None:
        """Verify consuming trials up to budget succeeds."""
        bench = MultiplicityNoiseBenchmarker(declared_budget=3)
        assert bench.declared_budget == 3
        assert bench.consumed_trials == 0

        bench.check_and_consume_budget()
        bench.check_and_consume_budget()
        bench.check_and_consume_budget()
        assert bench.consumed_trials == 3

    def test_budget_exceeded_fails_closed(self) -> None:
        """Verify attempting to consume beyond budget raises RuntimeError."""
        bench = MultiplicityNoiseBenchmarker(declared_budget=2)
        bench.check_and_consume_budget()
        bench.check_and_consume_budget()

        with pytest.raises(RuntimeError, match="TRIAL_BUDGET_EXCEEDED"):
            bench.check_and_consume_budget()


class TestBaselinesAndNoiseControl:
    """Tests for CASH baseline, ALWAYS_TRADE baseline, and 30-seed NOISE control."""

    def test_cash_baseline_zero_sharpe(self) -> None:
        """Verify CASH baseline produces exactly zero Sharpe ratio."""
        bench = MultiplicityNoiseBenchmarker()
        assert bench.evaluate_cash_baseline() == 0.0

    def test_always_trade_baseline_fee_drag(self) -> None:
        """Verify ALWAYS_TRADE incurs statutory 0.224% fee drag, reducing Sharpe."""
        bench = MultiplicityNoiseBenchmarker()
        gross_rets = [0.010 + 0.005 * (i % 3) for i in range(24)]  # Non-zero variance returns
        sharpe_gross = bench.evaluate_always_trade_baseline(gross_rets, statutory_fee=0.0)
        sharpe_net = bench.evaluate_always_trade_baseline(gross_rets, statutory_fee=0.00224)
        assert sharpe_gross > 0.0
        assert sharpe_net < sharpe_gross

    def test_noise_control_30_distinct_seeds(self) -> None:
        """Verify NOISE control produces exactly 30 distinct seed results."""
        bench = MultiplicityNoiseBenchmarker()
        sharpes = bench.run_30_seed_noise_control(num_trials=30)
        assert len(sharpes) == 30
        assert len(set(sharpes)) == 30

    def test_noise_control_seed_reproducibility(self) -> None:
        """Verify noise runs are deterministic and reproducible given fixed seeds."""
        bench = MultiplicityNoiseBenchmarker()
        run1 = bench.run_30_seed_noise_control(num_trials=15)
        run2 = bench.run_30_seed_noise_control(num_trials=15)
        assert run1 == run2

    def test_noise_control_distribution_median(self) -> None:
        """Verify median noise Sharpe is computed correctly."""
        bench = MultiplicityNoiseBenchmarker()
        sharpes = bench.run_30_seed_noise_control(30)
        median_sr = float(np.median(sharpes))
        assert isinstance(median_sr, float)
        # Random noise with negative fee drag should have near-zero or slightly negative median
        assert -1.0 < median_sr < 1.0


class TestDeflatedSharpeRatio:
    """Tests for Deflated Sharpe Ratio (DSR) mathematical properties."""

    def test_dsr_bounded_probability(self) -> None:
        """Verify DSR outputs a probability strictly in [0.0, 1.0]."""
        bench = MultiplicityNoiseBenchmarker()
        for sr in [-1.5, 0.0, 0.5, 1.5, 3.0]:
            dsr = bench.evaluate_dsr(candidate_sharpe=sr, num_trials=30)
            assert 0.0 <= dsr <= 1.0

    def test_dsr_penalizes_multiple_trials(self) -> None:
        """Verify DSR decreases monotonically as number of trials increases."""
        bench = MultiplicityNoiseBenchmarker()
        dsr_1 = bench.evaluate_dsr(candidate_sharpe=1.5, num_trials=1)
        dsr_5 = bench.evaluate_dsr(candidate_sharpe=1.5, num_trials=5)
        dsr_20 = bench.evaluate_dsr(candidate_sharpe=1.5, num_trials=20)
        dsr_100 = bench.evaluate_dsr(candidate_sharpe=1.5, num_trials=100)
        assert dsr_1 > dsr_5 > dsr_20 > dsr_100

    def test_dsr_penalizes_negative_skewness(self) -> None:
        """Verify negative return skewness penalizes DSR for a winning strategy."""
        bench = MultiplicityNoiseBenchmarker()
        dsr_normal = bench.evaluate_dsr(candidate_sharpe=2.0, num_trials=10, skewness=0.0)
        dsr_neg_skew = bench.evaluate_dsr(candidate_sharpe=2.0, num_trials=10, skewness=-1.5)
        assert dsr_neg_skew < dsr_normal

    def test_dsr_penalizes_excess_kurtosis(self) -> None:
        """Verify excess kurtosis (fat tails) penalizes DSR for a winning strategy."""
        bench = MultiplicityNoiseBenchmarker()
        dsr_meso = bench.evaluate_dsr(candidate_sharpe=2.0, num_trials=10, kurtosis=3.0)
        dsr_lepto = bench.evaluate_dsr(candidate_sharpe=2.0, num_trials=10, kurtosis=8.0)
        assert dsr_lepto < dsr_meso

    def test_candidate_exceeds_median_noise_dsr(self) -> None:
        """Verify a strong candidate exceeds the median noise DSR hurdle."""
        bench = MultiplicityNoiseBenchmarker()
        noise_sharpes = bench.run_30_seed_noise_control(30)
        median_noise_sr = float(np.median(noise_sharpes))
        noise_dsr = bench.evaluate_dsr(candidate_sharpe=median_noise_sr, num_trials=30)

        candidate_dsr = bench.evaluate_dsr(candidate_sharpe=1.8, num_trials=30)
        assert candidate_dsr > noise_dsr

    def test_compute_governed_dsr_integration(self) -> None:
        """Verify compute_governed_dsr integrates with OverfittingDiagnostics."""
        prob = compute_governed_dsr(
            estimated_sharpe=1.5,
            num_trials=5,
            sample_length_bars=60,
            skewness=0.0,
            kurtosis=3.0,
            periods_per_year=12,
        )
        assert 0.0 <= prob <= 1.0


class TestFullBenchmarkSuite:
    """Tests for run_benchmark and NoiseBenchmarkResults."""

    def test_run_benchmark_winning_candidate(self) -> None:
        """Verify run_benchmark produces NoiseBenchmarkResults and passes hurdle for winning candidate."""
        bench = MultiplicityNoiseBenchmarker()
        results = bench.run_benchmark(candidate_sharpe=1.8, num_trials=30)

        assert isinstance(results, NoiseBenchmarkResults)
        assert results.cash_sharpe == 0.0
        assert len(results.noise_sharpes) == 30
        assert len(results.noise_dsrs) == 30
        assert results.candidate_sharpe == 1.8
        assert results.candidate_dsr > results.median_noise_dsr
        assert results.passes_hurdle is True

    def test_run_benchmark_losing_candidate_fails_hurdle(self) -> None:
        """Verify run_benchmark fails hurdle when candidate has negative or inferior Sharpe."""
        bench = MultiplicityNoiseBenchmarker()
        results = bench.run_benchmark(candidate_sharpe=-0.5, num_trials=30)
        assert results.passes_hurdle is False
