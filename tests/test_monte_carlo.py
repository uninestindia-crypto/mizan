"""Tests for vectorized Monte Carlo simulation engine."""

import numpy as np

from quant_system.analytics.monte_carlo import MonteCarloSimulator


def test_monte_carlo_simulation_statistical_properties() -> None:
    # 100 days of mock daily returns with positive drift
    rng = np.random.default_rng(42)
    daily_returns = rng.normal(loc=0.001, scale=0.015, size=150).tolist()

    res = MonteCarloSimulator.simulate(
        daily_returns=daily_returns,
        num_simulations=2000,
        horizon_days=100,
        initial_capital=1000000.0,
        seed=42,
    )

    assert res.num_simulations == 2000
    assert res.horizon_days == 100
    assert len(res.percentile_5th) == 101
    assert len(res.percentile_50th) == 101
    assert len(res.percentile_95th) == 101

    # Invariant: 5th <= 25th <= 50th <= 75th <= 95th at final horizon
    assert res.percentile_5th[-1] <= res.percentile_25th[-1]
    assert res.percentile_25th[-1] <= res.percentile_50th[-1]
    assert res.percentile_50th[-1] <= res.percentile_75th[-1]
    assert res.percentile_75th[-1] <= res.percentile_95th[-1]

    # VaR and CVaR bounds
    assert 0.0 <= res.var_95_pct <= 1.0
    assert 0.0 <= res.var_99_pct <= 1.0
    assert res.cvar_95_pct >= res.var_95_pct
    assert res.cvar_99_pct >= res.var_99_pct

    # Probability bounds
    assert 0.0 <= res.prob_profit_pct <= 1.0
    assert 0.0 <= res.prob_drawdown_gt_10pct <= 1.0
    assert 0.0 <= res.prob_drawdown_gt_20pct <= 1.0
    assert 0.0 <= res.max_simulated_drawdown_pct <= 1.0


def test_monte_carlo_empty_returns_fallback() -> None:
    res = MonteCarloSimulator.simulate(
        daily_returns=[],
        num_simulations=500,
        horizon_days=50,
        initial_capital=500000.0,
    )
    assert res.num_simulations == 500
    assert len(res.percentile_50th) == 51
