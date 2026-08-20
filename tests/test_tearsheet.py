"""Tests for TearsheetGenerator rendering."""

from decimal import Decimal

from quant_system.analytics.metrics import QuantStats
from quant_system.analytics.tearsheet import TearsheetGenerator
from quant_system.backtest.engine import BacktestResult


def test_tearsheet_generator() -> None:
    result = BacktestResult(
        initial_cash=Decimal("1000000.00"),
        final_equity=Decimal("1150000.00"),
        total_return_pct=0.15,
        total_trades=10,
        fills=[],
        equity_curve=[],
        total_friction_paid=Decimal("1500.00"),
    )
    stats = QuantStats(
        total_return_pct=0.15,
        cagr_pct=0.15,
        annualized_volatility=0.12,
        sharpe_ratio=1.25,
        sortino_ratio=1.60,
        calmar_ratio=1.50,
        max_drawdown_pct=0.10,
        max_drawdown_duration_bars=20,
        win_rate=0.60,
        profit_factor=1.80,
        total_trades=10,
        avg_trade_pnl=15000.0,
    )

    md = TearsheetGenerator.generate_markdown(result, stats, "TestStrategy")
    assert "# Quant Performance Tearsheet: TestStrategy" in md
    assert "Rs. 1,000,000.00" in md
    assert "Rs. 1,150,000.00" in md
    assert "15.00%" in md
    assert "1.25" in md
