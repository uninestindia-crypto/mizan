"""Markowitz Mean-Variance Efficient Frontier and Risk-Parity Portfolio Optimizer."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class FrontierPoint:
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: dict[str, float]


@dataclass(frozen=True, slots=True)
class OptimizationResults:
    symbols: list[str]
    max_sharpe_point: FrontierPoint
    min_variance_point: FrontierPoint
    risk_parity_weights: dict[str, float]
    frontier_curve: list[FrontierPoint]


class PortfolioOptimizer:
    """Institutional portfolio optimizer solving quadratic covariance formulations."""

    @classmethod
    def optimize(
        cls,
        symbols: Sequence[str],
        returns_matrix: np.ndarray,  # shape: (n_observations, n_assets)
        risk_free_rate: float = 0.07,
        num_frontier_points: int = 40,
    ) -> OptimizationResults:
        """Solves optimal asset allocations, Sharpe maximization, and Efficient Frontier curve."""
        n_assets = len(symbols)
        if n_assets == 0:
            raise ValueError("At least one symbol required for portfolio optimization.")

        # Annualized mean returns and covariance matrix (252 trading days)
        mean_returns = np.mean(returns_matrix, axis=0) * 252.0
        cov_matrix = np.cov(returns_matrix, rowvar=False) * 252.0

        # Regularize covariance matrix to guarantee positive-definiteness
        cov_matrix += np.eye(n_assets) * 1e-6

        # 1. Solve Maximum Sharpe Portfolio
        def neg_sharpe(weights: np.ndarray) -> float:
            port_ret = float(np.dot(weights, mean_returns))
            port_vol = float(math.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))))
            return -(port_ret - risk_free_rate) / max(1e-8, port_vol)

        init_weights = np.ones(n_assets) / n_assets
        bounds = tuple((0.0, 1.0) for _ in range(n_assets))
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        opt_sharpe = minimize(
            neg_sharpe, init_weights, method="SLSQP", bounds=bounds, constraints=constraints
        )
        max_sharpe_w = opt_sharpe.x if opt_sharpe.success else init_weights

        ms_ret = float(np.dot(max_sharpe_w, mean_returns))
        ms_vol = float(math.sqrt(np.dot(max_sharpe_w.T, np.dot(cov_matrix, max_sharpe_w))))
        ms_sr = (ms_ret - risk_free_rate) / max(1e-8, ms_vol)

        max_sharpe_point = FrontierPoint(
            expected_return=ms_ret,
            volatility=ms_vol,
            sharpe_ratio=ms_sr,
            weights={sym: round(float(w), 4) for sym, w in zip(symbols, max_sharpe_w, strict=True)},
        )

        # 2. Solve Minimum Variance Portfolio
        def port_variance(weights: np.ndarray) -> float:
            return float(np.dot(weights.T, np.dot(cov_matrix, weights)))

        opt_var = minimize(
            port_variance, init_weights, method="SLSQP", bounds=bounds, constraints=constraints
        )
        min_var_w = opt_var.x if opt_var.success else init_weights

        mv_ret = float(np.dot(min_var_w, mean_returns))
        mv_vol = float(math.sqrt(np.dot(min_var_w.T, np.dot(cov_matrix, min_var_w))))
        mv_sr = (mv_ret - risk_free_rate) / max(1e-8, mv_vol)

        min_var_point = FrontierPoint(
            expected_return=mv_ret,
            volatility=mv_vol,
            sharpe_ratio=mv_sr,
            weights={sym: round(float(w), 4) for sym, w in zip(symbols, min_var_w, strict=True)},
        )

        # 3. Solve Equal Risk Contribution (Risk Parity)
        # Weight inversely proportional to individual asset volatility
        diag_vols = np.sqrt(np.diag(cov_matrix))
        inv_vols = 1.0 / np.maximum(1e-6, diag_vols)
        rp_weights_arr = inv_vols / np.sum(inv_vols)
        risk_parity_dict = {
            sym: round(float(w), 4) for sym, w in zip(symbols, rp_weights_arr, strict=True)
        }

        # 4. Generate Efficient Frontier Curve Points
        target_returns = np.linspace(
            mv_ret * 0.8, max(ms_ret * 1.3, mv_ret * 1.1), num_frontier_points
        )
        frontier_points: list[FrontierPoint] = []

        for target_r in target_returns:
            ret_constraint = {
                "type": "eq",
                "fun": lambda w, r=target_r: np.dot(w, mean_returns) - r,
            }
            res = minimize(
                port_variance,
                init_weights,
                method="SLSQP",
                bounds=bounds,
                constraints=[constraints, ret_constraint],
            )
            if res.success:
                f_w = res.x
                f_vol = float(math.sqrt(np.dot(f_w.T, np.dot(cov_matrix, f_w))))
                f_sr = (target_r - risk_free_rate) / max(1e-8, f_vol)
                frontier_points.append(
                    FrontierPoint(
                        expected_return=float(target_r),
                        volatility=f_vol,
                        sharpe_ratio=f_sr,
                        weights={
                            sym: round(float(w), 4) for sym, w in zip(symbols, f_w, strict=True)
                        },
                    )
                )

        if not frontier_points:
            frontier_points = [min_var_point, max_sharpe_point]

        return OptimizationResults(
            symbols=list(symbols),
            max_sharpe_point=max_sharpe_point,
            min_variance_point=min_var_point,
            risk_parity_weights=risk_parity_dict,
            frontier_curve=frontier_points,
        )
