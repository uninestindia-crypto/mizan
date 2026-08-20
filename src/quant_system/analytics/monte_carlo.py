"""Vectorized, high-performance Monte Carlo simulation and tail-risk stress testing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class MonteCarloResults:
    num_simulations: int
    horizon_days: int
    initial_capital: float
    expected_final_median: float
    percentile_5th: list[float]
    percentile_25th: list[float]
    percentile_50th: list[float]
    percentile_75th: list[float]
    percentile_95th: list[float]
    var_95_pct: float
    var_99_pct: float
    cvar_95_pct: float
    cvar_99_pct: float
    prob_profit_pct: float
    prob_drawdown_gt_10pct: float
    prob_drawdown_gt_20pct: float
    max_simulated_drawdown_pct: float


class MonteCarloSimulator:
    """High-throughput vectorized Monte Carlo engine for simulating portfolio paths and tail-risk."""

    @classmethod
    def simulate(
        cls,
        daily_returns: Sequence[float],
        num_simulations: int = 10000,
        horizon_days: int = 252,
        initial_capital: float = 1000000.0,
        seed: int | None = 42,
    ) -> MonteCarloResults:
        """Runs vectorized bootstrap Monte Carlo simulations in parallel across NumPy arrays."""
        if len(daily_returns) < 2:
            # Fallback baseline returns
            returns_arr = np.array([0.0005, -0.0003, 0.0008, -0.0002, 0.0004], dtype=np.float64)
        else:
            returns_arr = np.array(daily_returns, dtype=np.float64)

        rng = np.random.default_rng(seed)

        # Draw random bootstrap return matrices: shape (num_simulations, horizon_days)
        simulated_returns = rng.choice(
            returns_arr, size=(num_simulations, horizon_days), replace=True
        )

        # Compound growth paths: (1 + r) cumulative product along horizon axis
        growth_factors = np.cumprod(1.0 + simulated_returns, axis=1)

        # Prepend initial 1.0 at day 0
        ones_col = np.ones((num_simulations, 1), dtype=np.float64)
        equity_multipliers = np.hstack([ones_col, growth_factors])
        simulated_equity_paths = (
            initial_capital * equity_multipliers
        )  # shape (num_sims, horizon_days + 1)

        # 1. Percentile Trajectories (5th, 25th, 50th, 75th, 95th)
        p5 = np.percentile(simulated_equity_paths, 5, axis=0).tolist()
        p25 = np.percentile(simulated_equity_paths, 25, axis=0).tolist()
        p50 = np.percentile(simulated_equity_paths, 50, axis=0).tolist()
        p75 = np.percentile(simulated_equity_paths, 75, axis=0).tolist()
        p95 = np.percentile(simulated_equity_paths, 95, axis=0).tolist()

        # 2. Final Return Distribution
        final_equities = simulated_equity_paths[:, -1]
        total_returns = (final_equities - initial_capital) / initial_capital

        # Value at Risk (VaR) & Conditional VaR (CVaR)
        # VaR_alpha is the loss threshold at confidence level (e.g. 5th percentile return for 95% confidence)
        p5_ret = float(np.percentile(total_returns, 5))
        p1_ret = float(np.percentile(total_returns, 1))

        var_95 = max(0.0, -p5_ret)
        var_99 = max(0.0, -p1_ret)

        tail_95 = total_returns[total_returns <= p5_ret]
        tail_99 = total_returns[total_returns <= p1_ret]

        cvar_95 = max(0.0, float(-np.mean(tail_95))) if len(tail_95) > 0 else var_95
        cvar_99 = max(0.0, float(-np.mean(tail_99))) if len(tail_99) > 0 else var_99

        # Probability of overall profit
        prob_profit = float(np.mean(final_equities > initial_capital))

        # 3. Path-dependent Drawdowns
        # Running peaks per path
        running_peaks = np.maximum.accumulate(simulated_equity_paths, axis=1)
        drawdown_matrices = (running_peaks - simulated_equity_paths) / running_peaks
        max_drawdowns_per_path = np.max(drawdown_matrices, axis=1)

        prob_dd_10 = float(np.mean(max_drawdowns_per_path >= 0.10))
        prob_dd_20 = float(np.mean(max_drawdowns_per_path >= 0.20))
        max_sim_dd = float(np.max(max_drawdowns_per_path))

        return MonteCarloResults(
            num_simulations=num_simulations,
            horizon_days=horizon_days,
            initial_capital=initial_capital,
            expected_final_median=float(p50[-1]),
            percentile_5th=p5,
            percentile_25th=p25,
            percentile_50th=p50,
            percentile_75th=p75,
            percentile_95th=p95,
            var_95_pct=var_95,
            var_99_pct=var_99,
            cvar_95_pct=cvar_95,
            cvar_99_pct=cvar_99,
            prob_profit_pct=prob_profit,
            prob_drawdown_gt_10pct=prob_dd_10,
            prob_drawdown_gt_20pct=prob_dd_20,
            max_simulated_drawdown_pct=max_sim_dd,
        )
