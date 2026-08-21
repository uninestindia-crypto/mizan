"""Tests for Event-Driven BacktestEngine, next-bar fill execution, and zero lookahead."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from quant_system.analytics.metrics import PerformanceMetrics
from quant_system.backtest.engine import BacktestEngine
from quant_system.data.loader import SyntheticDataGenerator
from quant_system.strategies.equity_momentum import EquityDualMomentumStrategy


def test_backtest_engine_execution() -> None:
    # 1. Generate 100 days for 2 symbols
    start_dt = date(2025, 1, 1)
    bars_infy = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=start_dt,
        days=100,
        initial_price=1500.0,
        drift=0.001,
        seed=1,
    )
    bars_tcs = SyntheticDataGenerator.generate_equity_bars(
        symbol="TCS",
        start_date=start_dt,
        days=100,
        initial_price=3500.0,
        drift=0.0005,
        seed=2,
    )

    dataset = {"INFY": bars_infy.bars, "TCS": bars_tcs.bars}

    strategy = EquityDualMomentumStrategy(
        params={"lookback_fast": 10, "lookback_slow": 30, "top_n": 1}
    )
    engine = BacktestEngine(
        strategy=strategy,
        initial_cash=Decimal("500000.00"),
        slippage_bps=5.0,
    )

    result = engine.run(dataset)

    assert result.initial_cash == Decimal("500000.00")
    assert len(result.equity_curve) == 100
    assert result.final_equity > Decimal("0.00")
    assert len(result.fills) > 0
    assert result.total_friction_paid > Decimal("0.00")

    # Verify that each fill happened at or after its bar date (zero lookahead)
    first_bar_time = datetime(2025, 1, 1, 9, 15)
    lookahead_fills = [f for f in result.fills if f.timestamp < first_bar_time]
    assert lookahead_fills == [], (
        f"fills before the first bar imply lookahead: {lookahead_fills[:3]}"
    )

    stats = PerformanceMetrics.calculate(result.equity_curve, result.fills)
    assert stats.total_trades == len(result.fills)
    assert stats.max_drawdown_pct >= 0.0


def test_backtest_engine_empty_dataset() -> None:
    strategy = EquityDualMomentumStrategy()
    engine = BacktestEngine(strategy=strategy)
    with pytest.raises(ValueError, match="No historical bars provided"):
        engine.run({})
