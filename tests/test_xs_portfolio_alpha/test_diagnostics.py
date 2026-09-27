"""Unit tests for DecileDiagnosticEngine, DecileResults, and Spearman rank IC (R3)."""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import numpy as np
import pytest

from quant_system.research_xs_monthly.diagnostics import (
    DecileDiagnosticEngine,
    DecileResults,
    ICSummary,
)
from quant_system.research_xs_monthly.ranking import FactorComponents, RankedSymbol


def _make_ranked_symbols(n: int, reverse_scores: bool = False) -> list[RankedSymbol]:
    """Helper to generate n RankedSymbols."""
    symbols: list[RankedSymbol] = []
    for i in range(n):
        sym = f"SYM_{i:03d}"
        rank = i + 1
        score = float(i) if reverse_scores else float(n - i)
        comp = FactorComponents(
            intermediate_momentum_21_63=0.05,
            short_reversion_3_5=-0.01,
            idiosyncratic_volatility_63=0.20,
            composite_score=score,
        )
        symbols.append(RankedSymbol(sym, rank, score, comp))
    return symbols


class TestDecilePartitioningAndSpread:
    """Tests for 10-decile partitioning, decile returns, and top-bottom spread."""

    def test_ten_disjoint_deciles_created(self) -> None:
        """Verify exactly 10 disjoint deciles 1..10 are created."""
        engine = DecileDiagnosticEngine()
        ranked = _make_ranked_symbols(100)
        rets = {s.symbol: Decimal("0.02") for s in ranked}

        res = engine.evaluate_deciles(ranked, rets)
        assert len(res.decile_returns) == 10
        assert set(res.decile_returns.keys()) == set(range(1, 11))
        assert isinstance(res, DecileResults)

    def test_423_universe_bucket_sizes(self) -> None:
        """Verify 423-name universe partitions into buckets differing by at most 1 name."""
        engine = DecileDiagnosticEngine()
        ranked = _make_ranked_symbols(423)
        rets = {s.symbol: Decimal("0.01") for s in ranked}

        res = engine.evaluate_deciles(ranked, rets)
        assert res.decile_counts is not None
        counts = list(res.decile_counts.values())
        assert sum(counts) == 423
        assert max(counts) - min(counts) <= 1
        # Each decile has either 42 or 43 names
        for c in counts:
            assert c in (42, 43)

    def test_top_decile_q1_highest_scores(self) -> None:
        """Verify Q1 holds the top-ranked names and Q10 holds the bottom-ranked names."""
        engine = DecileDiagnosticEngine()
        ranked = _make_ranked_symbols(50)
        # Give higher returns to high ranked symbols
        rets = {s.symbol: Decimal(str(50 - i)) for i, s in enumerate(ranked)}

        res = engine.evaluate_deciles(ranked, rets)
        assert res.decile_returns[1] > res.decile_returns[10]
        assert res.top_bottom_spread > Decimal("0.00")
        assert res.is_monotonic is True

    def test_decile_returns_calculation_accuracy(self) -> None:
        """Verify exact calculation of decile returns."""
        engine = DecileDiagnosticEngine()
        ranked = _make_ranked_symbols(10)
        # 10 names -> 1 name per decile
        rets = {f"SYM_{i:03d}": Decimal(str(10 - i)) for i in range(10)}

        res = engine.evaluate_deciles(ranked, rets)
        assert res.decile_returns[1] == Decimal("10.0")
        assert res.decile_returns[5] == Decimal("6.0")
        assert res.decile_returns[10] == Decimal("1.0")
        assert res.top_bottom_spread == Decimal("9.0")
        assert res.is_monotonic is True

    def test_inverted_factor_monotonicity_detection(self) -> None:
        """Verify inverted factor returns (Q10 > Q1) report is_monotonic=False and negative spread."""
        engine = DecileDiagnosticEngine()
        ranked = _make_ranked_symbols(20)
        # Inverted returns: worse ranks get higher returns
        rets = {s.symbol: Decimal(str(i * 2)) for i, s in enumerate(ranked)}

        res = engine.evaluate_deciles(ranked, rets)
        assert res.decile_returns[1] < res.decile_returns[10]
        assert res.top_bottom_spread < Decimal("0.00")
        assert res.is_monotonic is False

    def test_insufficient_universe_raises_error(self) -> None:
        """Verify universe smaller than 10 names raises ValueError."""
        engine = DecileDiagnosticEngine()
        ranked = _make_ranked_symbols(9)
        with pytest.raises(ValueError, match="INSUFFICIENT_UNIVERSE"):
            engine.evaluate_deciles(ranked, {})

    def test_missing_forward_returns_handled_gracefully(self) -> None:
        """Verify symbols missing from forward_returns dict do not crash and use Decimal('0.0')."""
        engine = DecileDiagnosticEngine()
        ranked = _make_ranked_symbols(20)
        # Only provide returns for Q1 symbols
        rets = {s.symbol: Decimal("0.05") for s in ranked[:2]}

        res = engine.evaluate_deciles(ranked, rets)
        assert res.decile_returns[1] == Decimal("0.05")
        assert res.decile_returns[10] == Decimal("0.0")
        assert res.top_bottom_spread == Decimal("0.05")

    def test_custom_as_of_date_recorded(self) -> None:
        """Verify explicit as_of_date is preserved in DecileResults."""
        engine = DecileDiagnosticEngine()
        ranked = _make_ranked_symbols(10)
        rets = {s.symbol: Decimal("0.01") for s in ranked}
        target_date = date(2025, 6, 15)

        res = engine.evaluate_deciles(ranked, rets, as_of_date=target_date)
        assert res.as_of_date == target_date

    def test_check_pairwise_monotonicity(self) -> None:
        """Verify check_pairwise_monotonicity validates non-increasing decile returns."""
        engine = DecileDiagnosticEngine()
        # Strictly descending
        rets_desc = {d: Decimal(str(11 - d)) for d in range(1, 11)}
        assert engine.check_pairwise_monotonicity(rets_desc) is True

        # Non-monotonic bump in middle
        rets_bump = dict(rets_desc)
        rets_bump[5] = Decimal("20.0")
        assert engine.check_pairwise_monotonicity(rets_bump) is False


class TestSpearmanRankIC:
    """Tests for cross-sectional Spearman rank correlation."""

    def test_perfect_positive_correlation(self) -> None:
        """Verify IC is exactly 1.0 for perfectly monotonic relationship."""
        engine = DecileDiagnosticEngine()
        scores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        returns = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]

        ic = engine.spearman_rank_ic(scores, returns)
        assert math.isclose(ic, 1.0, abs_tol=1e-5)

    def test_perfect_negative_correlation(self) -> None:
        """Verify IC is exactly -1.0 for inverted relationship."""
        engine = DecileDiagnosticEngine()
        scores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        returns = [0.06, 0.05, 0.04, 0.03, 0.02, 0.01]

        ic = engine.spearman_rank_ic(scores, returns)
        assert math.isclose(ic, -1.0, abs_tol=1e-5)

    def test_ties_handled_with_fractional_ranks(self) -> None:
        """Verify tied scores receive fractional ranks and compute correct correlation."""
        engine = DecileDiagnosticEngine()
        scores = [1.0, 2.0, 2.0, 4.0]
        returns = [0.01, 0.02, 0.03, 0.04]

        ic = engine.spearman_rank_ic(scores, returns)
        assert 0.90 < ic < 1.0

    def test_independent_random_series_near_zero(self) -> None:
        """Verify IC is near zero for independent random variables."""
        engine = DecileDiagnosticEngine()
        rng = np.random.default_rng(42)
        scores = list(rng.normal(0, 1, 1000))
        returns = list(rng.normal(0, 1, 1000))

        ic = engine.spearman_rank_ic(scores, returns)
        assert abs(ic) < 0.10

    def test_degenerate_inputs_return_zero(self) -> None:
        """Verify degenerate inputs (<2 items, mismatched lengths, constant arrays) return 0.0."""
        engine = DecileDiagnosticEngine()
        assert engine.spearman_rank_ic([], []) == 0.0
        assert engine.spearman_rank_ic([1.0], [0.01]) == 0.0
        assert engine.spearman_rank_ic([1.0, 2.0], [0.01]) == 0.0
        # Constant scores (zero variance)
        assert engine.spearman_rank_ic([2.0, 2.0, 2.0], [0.01, 0.02, 0.03]) == 0.0
        # Constant returns
        assert engine.spearman_rank_ic([1.0, 2.0, 3.0], [0.05, 0.05, 0.05]) == 0.0


class TestICAggregationAndTStatistic:
    """Tests for aggregate_ic, Student's t-statistic, and ICSummary."""

    def test_empty_ic_series(self) -> None:
        """Verify empty series returns (0.0, 0.0, 0.0)."""
        engine = DecileDiagnosticEngine()
        mean_ic, std_ic, t_stat = engine.aggregate_ic([])
        assert mean_ic == 0.0
        assert std_ic == 0.0
        assert t_stat == 0.0

    def test_single_element_ic_series(self) -> None:
        """Verify single element returns that mean with 0.0 std and t-stat."""
        engine = DecileDiagnosticEngine()
        mean_ic, std_ic, t_stat = engine.aggregate_ic([0.05])
        assert mean_ic == 0.05
        assert std_ic == 0.0
        assert t_stat == 0.0

    def test_t_stat_formula_exact_match(self) -> None:
        """Verify t-statistic matches mean / (std / sqrt(N))."""
        engine = DecileDiagnosticEngine()
        ic_series = [0.04, 0.06, 0.05, 0.07, 0.03, 0.05]
        mean_ic, std_ic, t_stat = engine.aggregate_ic(ic_series)

        expected_mean = float(np.mean(ic_series))
        expected_std = float(np.std(ic_series, ddof=1))
        expected_t = expected_mean / (expected_std / math.sqrt(len(ic_series)))

        assert math.isclose(mean_ic, expected_mean, rel_tol=1e-5)
        assert math.isclose(std_ic, expected_std, rel_tol=1e-5)
        assert math.isclose(t_stat, expected_t, rel_tol=1e-5)

    def test_statistical_significance_hurdle(self) -> None:
        """Verify evaluation of t > 2.0 hurdle."""
        engine = DecileDiagnosticEngine()
        # Significant positive IC series
        rng = np.random.default_rng(101)
        sig_ic = list(rng.normal(loc=0.06, scale=0.03, size=36))
        _, _, t_sig = engine.aggregate_ic(sig_ic)
        assert t_sig > 2.0

        # Weak insignificant IC series
        weak_ic = list(rng.normal(loc=0.005, scale=0.05, size=36))
        _, _, t_weak = engine.aggregate_ic(weak_ic)
        assert t_weak < 2.0

    def test_summarize_ic(self) -> None:
        """Verify summarize_ic produces a valid ICSummary dataclass."""
        engine = DecileDiagnosticEngine()
        rng = np.random.default_rng(202)
        ic_series = list(rng.normal(loc=0.05, scale=0.02, size=36))

        summary = engine.summarize_ic(ic_series)
        assert isinstance(summary, ICSummary)
        assert summary.n_periods == 36
        assert summary.mean_ic > 0.0
        assert summary.t_statistic > 2.0
        assert summary.is_significant is True
