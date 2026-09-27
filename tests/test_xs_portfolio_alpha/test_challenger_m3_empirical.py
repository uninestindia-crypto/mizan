"""Empirical Challenger Verification Harness for Milestone 3 (R3 & R4).

Exhaustive empirical stress tests designed and executed by challenger_m3:
1. Empirical Deciles Stress Test:
   - 423-name universe clean partitioning into 10 disjoint deciles (~42 names/decile).
   - Invariant: 0 dropped, 0 duplicated symbols, bucket size diff <= 1.
   - Arbitrary universe size fuzzing (N from 10 to 1000).
   - Insufficient universe (<10) rejection.
   - Partial / missing forward return handling.
   - Monotonicity and dollar-neutral spread calculation.

2. Spearman Rank IC & t-Statistic Stress Test:
   - Verification against independent ground truth (scipy spearmanr and manual fractional rank Pearson).
   - Stress testing tie-breaking with dense ties, discrete rating scales, and constant arrays.
   - Time-series aggregation and Student's t-statistic formula precision.
   - Significance hurdle (t > 2.0) verification.

3. 30-Seed NOISE Control Empirical Test:
   - Deterministic repeatability across seeds 1..30 over multiple runs.
   - Statistical sanity of noise Sharpe distribution (median, spread, fee drag).
   - Empirical tranche ledger pipeline simulation under pseudo-random rankings.

4. Deflated Sharpe Ratio Stress Test:
   - Multiplicity penalty monotonic decay across varying trial counts (1 to 1000).
   - Sample size convergence and variance bounds.
   - Non-normality penalties (negative skewness and excess kurtosis).
   - passes_hurdle strict compound gate logic.

5. Trial Ledger Budget Enforcement:
   - Parsing of TRIAL-LEDGER.md budget and spent trials.
   - require_declared_trials fail-closed enforcement on mismatches.
   - Runtime trial budget consumption raising RuntimeError("TRIAL_BUDGET_EXCEEDED").
   - Zero-budget immediate fail-closed verification.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from scipy import stats  # type: ignore[import-untyped]

from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.diagnostics import (
    DecileDiagnosticEngine,
    DecileResults,
    ICSummary,
)
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
from quant_system.research_xs_monthly.ranking import FactorComponents, RankedSymbol


def _make_dummy_ranked(n: int, seed: int = 42) -> list[RankedSymbol]:
    """Helper to generate n RankedSymbols with unique scores."""
    rng = np.random.default_rng(seed)
    scores = rng.normal(0, 1, n)
    # Sort descending by score
    sorted_indices = np.argsort(-scores)
    symbols: list[RankedSymbol] = []
    for rank_idx, orig_idx in enumerate(sorted_indices, start=1):
        sym = f"SYM_{orig_idx:04d}"
        score = float(scores[orig_idx])
        comp = FactorComponents(
            intermediate_momentum_21_63=0.05,
            short_reversion_3_5=-0.01,
            idiosyncratic_volatility_63=0.20,
            composite_score=score,
        )
        symbols.append(RankedSymbol(sym, rank_idx, score, comp))
    return symbols


# =================================================================================================
# 1. Empirical Deciles Stress Tests
# =================================================================================================


class TestEmpiricalDecilesStress:
    """Empirical verification of 10-decile partitioning, coverage, and spread logic."""

    def test_423_universe_clean_partition_zero_dropped_zero_duplicated(self) -> None:
        """Verify 423-name universe partitions cleanly with 0 dropped and 0 duplicated symbols."""
        engine = DecileDiagnosticEngine()
        ranked = _make_dummy_ranked(423, seed=123)
        original_symbols = [s.symbol for s in ranked]
        assert len(original_symbols) == 423
        assert len(set(original_symbols)) == 423

        forward_returns = {
            s: Decimal(f"0.{i % 90 + 10:02d}") for i, s in enumerate(original_symbols)
        }
        res = engine.evaluate_deciles(ranked, forward_returns)
        assert isinstance(res, DecileResults)

        # 1. Exactly 10 deciles
        assert len(res.decile_returns) == 10
        assert set(res.decile_returns.keys()) == set(range(1, 11))
        assert res.decile_counts is not None

        # 2. Bucket counts verify: sizes are 42 or 43, diff <= 1, sum == 423
        counts = [res.decile_counts[d] for d in range(1, 11)]
        assert sum(counts) == 423
        assert max(counts) - min(counts) <= 1
        assert set(counts).issubset({42, 43})

        # 3. Disjoint and contiguous index verification
        bucket_size = 423 / 10.0
        collected_symbols: list[str] = []
        for d in range(1, 11):
            start_idx = int(round((d - 1) * bucket_size))
            end_idx = int(round(d * bucket_size))
            group_symbols = [s.symbol for s in ranked[start_idx:end_idx]]
            assert len(group_symbols) == res.decile_counts[d]
            collected_symbols.extend(group_symbols)

        # 0 dropped, 0 duplicated
        assert len(collected_symbols) == 423
        assert len(set(collected_symbols)) == 423
        assert collected_symbols == original_symbols

    @pytest.mark.parametrize(
        "universe_size",
        [10, 11, 19, 20, 21, 55, 99, 100, 101, 350, 423, 500, 1000],
    )
    def test_arbitrary_universe_sizes_partition_invariants(self, universe_size: int) -> None:
        """Verify for any universe size >= 10 that 0 symbols are dropped or duplicated."""
        engine = DecileDiagnosticEngine()
        ranked = _make_dummy_ranked(universe_size, seed=universe_size)
        forward_returns = {s.symbol: Decimal("0.02") for s in ranked}

        res = engine.evaluate_deciles(ranked, forward_returns)
        assert res.decile_counts is not None
        counts = [res.decile_counts[d] for d in range(1, 11)]

        # Total count must strictly match original universe
        assert sum(counts) == universe_size
        # No bucket should be empty
        assert min(counts) >= 1
        # Maximum imbalance across buckets is at most 1 item
        assert max(counts) - min(counts) <= 1

    def test_insufficient_universe_boundary_rejection(self) -> None:
        """Verify universe sizes < 10 fail closed with ValueError."""
        engine = DecileDiagnosticEngine()
        for size in [0, 1, 5, 9]:
            ranked = _make_dummy_ranked(size)
            with pytest.raises(ValueError, match="INSUFFICIENT_UNIVERSE"):
                engine.evaluate_deciles(ranked, {})

    def test_missing_forward_returns_graceful_handling(self) -> None:
        """Verify partial forward returns don't crash and decile counts reflect present symbols."""
        engine = DecileDiagnosticEngine()
        ranked = _make_dummy_ranked(423)
        # Only 50 symbols have forward returns recorded
        partial_returns = {s.symbol: Decimal("0.05") for s in ranked[:50]}

        res = engine.evaluate_deciles(ranked, partial_returns)
        assert res.decile_counts is not None
        # Q1 should have 42 names present
        assert res.decile_counts[1] == 42
        assert res.decile_returns[1] == Decimal("0.05")
        # Q2 should have 8 names present (50 - 42)
        assert res.decile_counts[2] == 8
        assert res.decile_returns[2] == Decimal("0.05")
        # Q3..Q10 should have 0 names present
        for d in range(3, 11):
            assert res.decile_counts[d] == 0
            assert res.decile_returns[d] == Decimal("0.0")

    def test_decile_spread_and_monotonicity_logic(self) -> None:
        """Verify exact Decimal arithmetic of Q1 - Q10 spread and monotonicity checks."""
        engine = DecileDiagnosticEngine()
        ranked = _make_dummy_ranked(20)
        # Create strictly descending returns: Q1 (+10%), ..., Q10 (-10%)
        returns_map: dict[str, Decimal] = {}
        for d in range(1, 11):
            s1 = ranked[(d - 1) * 2].symbol
            s2 = ranked[(d - 1) * 2 + 1].symbol
            ret = Decimal(str(11 - d)) / Decimal("100.0")
            returns_map[s1] = ret
            returns_map[s2] = ret

        res = engine.evaluate_deciles(ranked, returns_map)
        assert res.is_monotonic is True
        expected_spread = res.decile_returns[1] - res.decile_returns[10]
        assert res.top_bottom_spread == expected_spread
        assert expected_spread > Decimal("0.0")
        assert engine.check_pairwise_monotonicity(res.decile_returns) is True


# =================================================================================================
# 2. Spearman Rank IC & t-Statistic Stress Tests
# =================================================================================================


class TestEmpiricalSpearmanICStress:
    """Empirical verification of Spearman rank IC and t-statistic against independent ground truth."""

    def _independent_spearman(self, x: list[float], y: list[float]) -> float:
        """Independent ground truth implementation of Spearman rank correlation."""
        if len(x) < 2 or len(y) < 2 or len(x) != len(y):
            return 0.0
        # Average ranks for ties
        rx = stats.rankdata(x, method="average")
        ry = stats.rankdata(y, method="average")
        std_x = np.std(rx, ddof=1)
        std_y = np.std(ry, ddof=1)
        if std_x < 1e-12 or std_y < 1e-12:
            return 0.0
        cov = np.cov(rx, ry, ddof=1)[0, 1]
        return float(cov / (std_x * std_y))

    def test_spearman_ic_matches_independent_ground_truth(self) -> None:
        """Verify spearman_rank_ic matches independent implementation across 50 random trials."""
        engine = DecileDiagnosticEngine()
        rng = np.random.default_rng(2026)

        for _trial in range(50):
            n = int(rng.integers(10, 423))
            scores = list(rng.normal(0, 1, n))
            # Correlate returns with scores plus noise
            alpha = float(rng.uniform(-0.8, 0.8))
            returns = [alpha * s + float(rng.normal(0, 1)) for s in scores]

            result_ic = engine.spearman_rank_ic(scores, returns)
            ground_truth = self._independent_spearman(scores, returns)
            scipy_stat = float(stats.spearmanr(scores, returns).statistic)

            assert math.isclose(result_ic, ground_truth, abs_tol=1e-10)
            assert math.isclose(result_ic, scipy_stat, abs_tol=1e-10)

    def test_spearman_ic_dense_ties_handling(self) -> None:
        """Verify tie-breaking with dense fractional ranks matches ground truth."""
        engine = DecileDiagnosticEngine()
        # Discrete 5-point rating scale with heavy ties
        scores = [1.0, 1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 4.0, 5.0, 5.0]
        returns = [0.01, 0.02, 0.02, 0.03, 0.01, 0.04, 0.05, 0.06, 0.05, 0.07]

        ic = engine.spearman_rank_ic(scores, returns)
        expected = self._independent_spearman(scores, returns)
        assert math.isclose(ic, expected, abs_tol=1e-10)
        assert 0.70 < ic < 1.0

    def test_spearman_ic_degenerate_inputs_fail_safe(self) -> None:
        """Verify degenerate inputs safely return 0.0 without throwing exceptions."""
        engine = DecileDiagnosticEngine()
        # Empty
        assert engine.spearman_rank_ic([], []) == 0.0
        # Single element
        assert engine.spearman_rank_ic([1.0], [0.05]) == 0.0
        # Mismatched lengths
        assert engine.spearman_rank_ic([1.0, 2.0], [0.05]) == 0.0
        # All scores identical (zero variance)
        assert engine.spearman_rank_ic([5.0] * 50, list(range(50))) == 0.0
        # All returns identical (zero variance)
        assert engine.spearman_rank_ic(list(range(50)), [0.02] * 50) == 0.0

    def test_ic_aggregation_and_student_t_stat(self) -> None:
        """Verify Student's t-statistic calculation against exact formula."""
        engine = DecileDiagnosticEngine()
        # 36 months of IC series
        ic_series = [0.04 + 0.01 * math.sin(i) for i in range(36)]
        mean_ic, std_ic, t_stat = engine.aggregate_ic(ic_series)

        # Independent formula
        n = len(ic_series)
        exp_mean = float(np.mean(ic_series))
        exp_std = float(np.std(ic_series, ddof=1))
        exp_t = exp_mean / (exp_std / math.sqrt(n))

        assert math.isclose(mean_ic, exp_mean, rel_tol=1e-7)
        assert math.isclose(std_ic, exp_std, rel_tol=1e-7)
        assert math.isclose(t_stat, exp_t, rel_tol=1e-7)

        summary = engine.summarize_ic(ic_series)
        assert isinstance(summary, ICSummary)
        assert summary.is_significant == (t_stat > 2.0)

    def test_ic_aggregation_zero_variance(self) -> None:
        """Verify constant IC series with std=0 returns t_stat=0.0 without ZeroDivisionError."""
        engine = DecileDiagnosticEngine()
        mean_ic, std_ic, t_stat = engine.aggregate_ic([0.05, 0.05, 0.05, 0.05])
        assert mean_ic == 0.05
        assert std_ic == 0.0
        assert t_stat == 0.0


# =================================================================================================
# 3. 30-Seed NOISE Control Empirical Tests
# =================================================================================================


class TestEmpiricalNoiseControlStress:
    """Empirical verification of 30-seed pseudo-random NOISE control."""

    def test_30_seed_noise_deterministic_repeatability(self) -> None:
        """Verify 30-seed noise control generates strictly identical results across repeated runs."""
        bench = MultiplicityNoiseBenchmarker()
        run1 = bench.run_30_seed_noise_control(num_trials=30)
        run2 = bench.run_30_seed_noise_control(num_trials=30)
        run3 = bench.run_30_seed_noise_control(num_trials=30)

        assert len(run1) == 30
        assert run1 == run2 == run3
        # Ensure all 30 seeds produce distinct Sharpe values
        assert len(set(run1)) == 30

    def test_noise_sharpe_distribution_properties(self) -> None:
        """Verify statistical properties of 30-seed noise Sharpe distribution."""
        bench = MultiplicityNoiseBenchmarker()
        sharpes = bench.run_30_seed_noise_control(num_trials=30)

        mean_sr = float(np.mean(sharpes))
        median_sr = float(np.median(sharpes))
        std_sr = float(np.std(sharpes, ddof=1))
        min_sr = min(sharpes)
        max_sr = max(sharpes)

        # Under the null with slight negative drag (-5 bps monthly), median should be around -0.1 to +0.1
        assert -0.5 < mean_sr < 0.5
        assert -0.5 < median_sr < 0.5
        # Standard deviation of 5-year monthly Sharpe estimator is approximately 1/sqrt(5) ~ 0.45
        assert 0.2 < std_sr < 0.8
        # Boundaries within reasonable random bounds
        assert min_sr > -2.5
        assert max_sr < 2.5

    def test_empirical_noise_control_ledger_simulation(self) -> None:
        """Verify run_empirical_noise_control executes full StaggeredTrancheLedger pipeline."""
        bench = MultiplicityNoiseBenchmarker()
        universe = [f"SYM_{i:02d}" for i in range(20)]
        start_d = date(2024, 1, 1)
        calendar = [start_d + timedelta(days=i) for i in range(25)]

        bars_dict: dict[str, list[Bar]] = {}
        for sym in universe:
            bars_dict[sym] = [
                Bar(
                    symbol=sym,
                    exchange_date=d,
                    open=Decimal("100.00"),
                    high=Decimal("105.00"),
                    low=Decimal("95.00"),
                    close=Decimal("101.00"),
                    volume=50000,
                )
                for d in calendar
            ]

        noise_srs = bench.run_empirical_noise_control(
            universe=universe,
            calendar=calendar,
            bars_by_symbol=bars_dict,
            num_trials=3,
            holding_sessions=5,
        )
        assert len(noise_srs) == 3
        for sr in noise_srs:
            assert isinstance(sr, float)


# =================================================================================================
# 4. Deflated Sharpe Ratio Stress Tests
# =================================================================================================


class TestEmpiricalDeflatedSharpeRatioStress:
    """Empirical verification of Deflated Sharpe Ratio (DSR) mathematical and statistical properties."""

    def test_dsr_multiplicity_penalty_strictly_monotonic(self) -> None:
        """Verify DSR strictly decays as number of trials increases (multiplicity burden)."""
        bench = MultiplicityNoiseBenchmarker()
        cand_sr = 1.5

        trials = [1, 2, 5, 10, 25, 50, 100, 500, 1000]
        dsr_values = [bench.evaluate_dsr(candidate_sharpe=cand_sr, num_trials=k) for k in trials]

        # Verify strict monotonic decrease: DSR(k_1) > DSR(k_2) for k_1 < k_2
        for i in range(len(dsr_values) - 1):
            assert dsr_values[i] > dsr_values[i + 1], (
                f"Failed at trial {trials[i]} vs {trials[i + 1]}"
            )

    def test_dsr_sample_size_confidence_scaling(self) -> None:
        """Verify DSR increases as sample length T increases for a winning candidate."""
        bench = MultiplicityNoiseBenchmarker()
        # Candidate Sharpe higher than expected max for 5 trials
        cand_sr = 2.0
        dsr_12m = bench.evaluate_dsr(cand_sr, num_trials=5, n_periods=12)
        dsr_60m = bench.evaluate_dsr(cand_sr, num_trials=5, n_periods=60)
        dsr_120m = bench.evaluate_dsr(cand_sr, num_trials=5, n_periods=120)

        assert dsr_12m < dsr_60m < dsr_120m

    def test_dsr_skewness_and_kurtosis_penalties(self) -> None:
        """Verify return non-normality penalties for a winning strategy (SR > E[max])."""
        bench = MultiplicityNoiseBenchmarker()
        # For num_trials=10, E[max] ~ 1.88. Use cand_sr = 2.5 > E[max]
        cand_sr = 2.5
        trials = 10

        # Negative skewness penalty (left-tail crash risk increases variance, deflating positive z-score)
        dsr_sym = bench.evaluate_dsr(cand_sr, num_trials=trials, skewness=0.0)
        dsr_neg_skew = bench.evaluate_dsr(cand_sr, num_trials=trials, skewness=-1.2)
        dsr_pos_skew = bench.evaluate_dsr(cand_sr, num_trials=trials, skewness=1.2)
        assert dsr_neg_skew < dsr_sym < dsr_pos_skew

        # Excess kurtosis penalty (fat tails inflate estimator variance, deflating positive z-score)
        dsr_mesokurtic = bench.evaluate_dsr(cand_sr, num_trials=trials, kurtosis=3.0)
        dsr_leptokurtic = bench.evaluate_dsr(cand_sr, num_trials=trials, kurtosis=8.0)
        assert dsr_leptokurtic < dsr_mesokurtic

    def test_dsr_boundary_extremes(self) -> None:
        """Verify DSR remains strictly bounded in [0.0, 1.0] under extreme values."""
        bench = MultiplicityNoiseBenchmarker()
        dsr_neg = bench.evaluate_dsr(candidate_sharpe=-20.0, num_trials=30)
        assert 0.0 <= dsr_neg < 1e-15
        assert math.isclose(
            bench.evaluate_dsr(candidate_sharpe=20.0, num_trials=5), 1.0, abs_tol=1e-5
        )

    def test_passes_hurdle_exhaustive_logic(self) -> None:
        """Verify passes_hurdle evaluates all 3 conjunctive conditions strictly."""
        bench = MultiplicityNoiseBenchmarker()

        # 1. Clear winner: Sharpe > noise median, DSR > noise DSR, Sharpe > 0
        res_win = bench.run_benchmark(candidate_sharpe=2.0, num_trials=30)
        assert isinstance(res_win, NoiseBenchmarkResults)
        assert res_win.passes_hurdle is True

        # Test compute_governed_dsr directly
        gov_dsr = compute_governed_dsr(
            estimated_sharpe=2.0,
            num_trials=30,
            sample_length_bars=60,
        )
        assert 0.0 <= gov_dsr <= 1.0

        # 2. Negative Sharpe: fails
        res_loss = bench.run_benchmark(candidate_sharpe=-0.5, num_trials=30)
        assert res_loss.passes_hurdle is False

        # 3. Zero Sharpe (cash level): fails
        res_cash = bench.run_benchmark(candidate_sharpe=0.0, num_trials=30)
        assert res_cash.passes_hurdle is False

        # 4. Positive Sharpe but below noise median: fails
        median_noise = res_win.median_noise_sharpe
        res_below_noise = bench.run_benchmark(candidate_sharpe=median_noise - 0.05, num_trials=30)
        assert res_below_noise.passes_hurdle is False


# =================================================================================================
# 5. Trial Ledger Budget Enforcement Tests
# =================================================================================================


class TestEmpiricalTrialBudgetStress:
    """Empirical verification of TRIAL-LEDGER.md parsing and fail-closed budget enforcement."""

    def test_frozen_ledger_content_and_invariants(self) -> None:
        """Verify TRIAL-LEDGER.md exists, parses budget of 5, and records 1 SPENT trial."""
        ledger = default_ledger_path()
        assert ledger.is_file(), f"Trial ledger missing at {ledger}"

        budget = read_trial_budget()
        assert budget == 5

        spent_count = declared_spent_trials()
        assert spent_count == 1

        trials = read_spent_trials()
        assert len(trials) == 1
        t1 = trials[0]
        assert isinstance(t1, SpentTrial)
        assert t1.number == 1
        assert t1.status == "SPENT"
        assert t1.family.strip("`") == "xs_multi_factor_v1"

    def test_require_declared_trials_enforces_budget_and_fails_closed(self) -> None:
        """Verify require_declared_trials strictly accepts only 1 or 5, failing on all others."""
        # Accepted values
        assert require_declared_trials(1) == 1
        assert require_declared_trials(5) == 5

        # Refused values
        for invalid in [-10, 0, 2, 3, 4, 6, 10, 999]:
            with pytest.raises(ValueError, match="disagrees with"):
                require_declared_trials(invalid)

    def test_benchmarker_budget_consumption_raises_when_exceeded(self) -> None:
        """Verify MultiplicityNoiseBenchmarker strictly enforces budget and raises RuntimeError."""
        bench = MultiplicityNoiseBenchmarker(declared_budget=4)
        assert bench.declared_budget == 4
        assert bench.consumed_trials == 0

        # Consume 4 trials
        for i in range(1, 5):
            bench.check_and_consume_budget()
            assert bench.consumed_trials == i

        # 5th attempt must raise RuntimeError
        with pytest.raises(RuntimeError, match="TRIAL_BUDGET_EXCEEDED"):
            bench.check_and_consume_budget()

    def test_benchmarker_zero_budget_fails_closed_immediately(self) -> None:
        """Verify a declared budget of 0 immediately fails closed on the first attempt."""
        bench = MultiplicityNoiseBenchmarker(declared_budget=0)
        with pytest.raises(RuntimeError, match="TRIAL_BUDGET_EXCEEDED"):
            bench.check_and_consume_budget()

    def test_missing_ledger_fails_closed(self, tmp_path: Path) -> None:
        """Verify non-existent ledger raises FileNotFoundError."""
        bogus_path = tmp_path / "NON_EXISTENT_LEDGER.md"
        with pytest.raises(FileNotFoundError, match="Frozen trial ledger not found"):
            read_spent_trials(bogus_path)
