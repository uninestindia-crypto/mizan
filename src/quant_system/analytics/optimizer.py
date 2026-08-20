"""Parallel strategy parameter optimizer and walk-forward parameter search."""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from quant_system.analytics.metrics import PerformanceMetrics
from quant_system.backtest.engine import BacktestEngine
from quant_system.core.domain import PriceBar
from quant_system.risk.governor import PreTradeRiskGovernor
from quant_system.strategies.registry import StrategyRegistry


@dataclass(frozen=True, slots=True)
class ParamOptimizationResult:
    params: dict[str, Any]
    total_return_pct: float
    cagr_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int


class StrategyGridOptimizer:
    """Evaluates strategy parameter permutations to identify optimal parameter configurations."""

    @classmethod
    def run_grid_search(
        cls,
        strategy_name: str,
        param_grid: Mapping[str, Sequence[Any]],
        dataset: Mapping[str, Sequence[PriceBar]],
        initial_cash: Decimal = Decimal("1000000.00"),
        slippage_bps: float = 5.0,
        top_k: int = 10,
    ) -> list[ParamOptimizationResult]:
        """Runs combinatorial grid search across parameter space."""
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = [dict(zip(keys, prod, strict=True)) for prod in itertools.product(*values)]

        results: list[ParamOptimizationResult] = []

        for p_set in combinations:
            try:
                strategy = StrategyRegistry.create(strategy_name, params=p_set)
                engine = BacktestEngine(
                    strategy=strategy,
                    initial_cash=initial_cash,
                    risk_governor=PreTradeRiskGovernor(),
                    slippage_bps=slippage_bps,
                )
                res = engine.run(dataset)
                stats = PerformanceMetrics.calculate(res.equity_curve, res.fills)

                results.append(
                    ParamOptimizationResult(
                        params=p_set,
                        total_return_pct=stats.total_return_pct,
                        cagr_pct=stats.cagr_pct,
                        sharpe_ratio=stats.sharpe_ratio,
                        sortino_ratio=stats.sortino_ratio,
                        max_drawdown_pct=stats.max_drawdown_pct,
                        win_rate=stats.win_rate,
                        total_trades=stats.total_trades,
                    )
                )
            except Exception:
                continue

        # Sort descending by Sharpe ratio, then by total return
        results.sort(key=lambda r: (r.sharpe_ratio, r.total_return_pct), reverse=True)
        return results[:top_k]
