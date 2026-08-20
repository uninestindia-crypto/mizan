"""Tests for FIFO trade matching for Long, Short, Partial, and Flip positions in Performance Analytics."""

from datetime import datetime
from decimal import Decimal

from quant_system.analytics.metrics import PerformanceMetrics
from quant_system.core.domain import Fill, PortfolioSnapshot, Side


def test_trade_stats_long_trades() -> None:
    now = datetime(2025, 1, 1, 10, 0)
    # Buy 100 INFY @ 1500, fee = 20
    f1 = Fill(
        fill_id="f1",
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=100,
        price=Decimal("1500.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    # Sell 100 INFY @ 1600, fee = 20
    f2 = Fill(
        fill_id="f2",
        order_id="o2",
        symbol="INFY",
        side=Side.SELL,
        quantity=100,
        price=Decimal("1600.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )

    win_rate, profit_factor, avg_pnl = PerformanceMetrics._calculate_trade_stats([f1, f2])
    assert win_rate == 1.0
    assert profit_factor == 999.0  # Zero losses
    # PnL = (1600 - 1500)*100 - 40 fee = 10,000 - 40 = 9960
    assert abs(avg_pnl - 9960.0) < 1e-4


def test_trade_stats_short_trades() -> None:
    now = datetime(2025, 1, 1, 10, 0)
    # Sell 50 NIFTY24500CE @ 200, fee = 20
    f1 = Fill(
        fill_id="f1",
        order_id="o1",
        symbol="NIFTY24500CE",
        side=Side.SELL,
        quantity=50,
        price=Decimal("200.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    # Buy 50 NIFTY24500CE @ 150 (Cover), fee = 20
    f2 = Fill(
        fill_id="f2",
        order_id="o2",
        symbol="NIFTY24500CE",
        side=Side.BUY,
        quantity=50,
        price=Decimal("150.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )

    win_rate, profit_factor, avg_pnl = PerformanceMetrics._calculate_trade_stats([f1, f2])
    assert win_rate == 1.0
    assert profit_factor == 999.0
    # PnL = (200 - 150)*50 - 40 fee = 2500 - 40 = 2460
    assert abs(avg_pnl - 2460.0) < 1e-4


def test_trade_stats_partial_fills() -> None:
    now = datetime(2025, 1, 1, 10, 0)
    # Buy 100 INFY @ 1000, fee = 20
    f1 = Fill(
        fill_id="f1",
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=100,
        price=Decimal("1000.00"),
        fee=Decimal("20.00"),
        timestamp=now,
    )
    # Sell 50 INFY @ 1100, fee = 10 (Win)
    f2 = Fill(
        fill_id="f2",
        order_id="o2",
        symbol="INFY",
        side=Side.SELL,
        quantity=50,
        price=Decimal("1100.00"),
        fee=Decimal("10.00"),
        timestamp=now,
    )
    # Sell 50 INFY @ 900, fee = 10 (Loss)
    f3 = Fill(
        fill_id="f3",
        order_id="o3",
        symbol="INFY",
        side=Side.SELL,
        quantity=50,
        price=Decimal("900.00"),
        fee=Decimal("10.00"),
        timestamp=now,
    )

    win_rate, profit_factor, avg_pnl = PerformanceMetrics._calculate_trade_stats([f1, f2, f3])
    assert win_rate == 0.5  # 1 win, 1 loss out of 2 closed trades
    assert profit_factor > 0.0


def test_performance_metrics_full_stats() -> None:
    now1 = datetime(2025, 1, 1, 15, 30)
    now2 = datetime(2025, 1, 2, 15, 30)

    snap1 = PortfolioSnapshot(
        timestamp=now1,
        cash=Decimal("1000000.00"),
        positions={},
        total_market_value=Decimal("0.00"),
        unrealized_pnl=Decimal("0.00"),
        realized_pnl=Decimal("0.00"),
    )
    snap2 = PortfolioSnapshot(
        timestamp=now2,
        cash=Decimal("1020000.00"),
        positions={},
        total_market_value=Decimal("0.00"),
        unrealized_pnl=Decimal("0.00"),
        realized_pnl=Decimal("20000.00"),
    )

    stats = PerformanceMetrics.calculate([snap1, snap2], [])
    assert stats.total_return_pct == 0.02
    assert stats.max_drawdown_pct == 0.0
