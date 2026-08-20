"""Tests for Markowitz Efficient Frontier and Risk-Parity portfolio optimizer."""

import numpy as np
import pytest

from quant_system.portfolio.optimization import PortfolioOptimizer


def test_portfolio_optimizer_max_sharpe_and_risk_parity() -> None:
    symbols = ["INFY", "TCS", "RELIANCE"]

    # Generate correlated synthetic return matrix: 250 days x 3 assets
    rng = np.random.default_rng(42)
    asset_1 = rng.normal(0.0008, 0.015, 250)
    asset_2 = rng.normal(0.0005, 0.010, 250)
    asset_3 = rng.normal(0.0010, 0.020, 250)

    matrix = np.column_stack([asset_1, asset_2, asset_3])

    res = PortfolioOptimizer.optimize(
        symbols=symbols,
        returns_matrix=matrix,
        risk_free_rate=0.07,
        num_frontier_points=15,
    )

    assert res.symbols == symbols

    # Weights sum to 1.0 within numerical tolerance
    ms_sum = sum(res.max_sharpe_point.weights.values())
    mv_sum = sum(res.min_variance_point.weights.values())
    rp_sum = sum(res.risk_parity_weights.values())

    assert pytest.approx(ms_sum, abs=1e-3) == 1.0
    assert pytest.approx(mv_sum, abs=1e-3) == 1.0
    assert pytest.approx(rp_sum, abs=1e-3) == 1.0

    # Minimum variance portfolio should have lower or equal volatility than max Sharpe
    assert res.min_variance_point.volatility <= res.max_sharpe_point.volatility + 1e-4

    # Efficient frontier curve points generated
    assert len(res.frontier_curve) > 0


def test_portfolio_optimizer_empty_symbols_error() -> None:
    matrix = np.zeros((10, 0))
    with pytest.raises(ValueError, match="At least one symbol"):
        PortfolioOptimizer.optimize(symbols=[], returns_matrix=matrix)
