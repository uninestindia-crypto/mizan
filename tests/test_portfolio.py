"""Tests for PortfolioAllocator and PositionSizer algorithms."""

from datetime import UTC, datetime
from decimal import Decimal

from quant_system.core.domain import OrderType, Position, Side
from quant_system.portfolio.allocation import PortfolioAllocator
from quant_system.portfolio.sizing import PositionSizer


def test_portfolio_allocator_deterministic_rebalance() -> None:
    now = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
    current_equity = Decimal("1000000.00")
    current_positions = {
        "INFY": Position(symbol="INFY", quantity=100, average_price=Decimal("1500.00")),
        "TCS": Position(symbol="TCS", quantity=50, average_price=Decimal("3500.00")),
    }
    current_prices = {
        "INFY": Decimal("1500.00"),
        "TCS": Decimal("3500.00"),
        "RELIANCE": Decimal("2500.00"),
    }
    target_weights = {
        "INFY": 0.10,  # 100k / 1500 = 66 shares (sell 34)
        "TCS": 0.00,  # 0k (sell 50)
        "RELIANCE": 0.20,  # 200k / 2500 = 80 shares (buy 80)
    }

    orders = PortfolioAllocator.compute_rebalance_orders(
        current_equity=current_equity,
        current_positions=current_positions,
        current_prices=current_prices,
        target_weights=target_weights,
        min_trade_value=Decimal("500.00"),
        timestamp=now,
    )

    assert len(orders) == 3
    sells = [o for o in orders if o.side == Side.SELL]
    buys = [o for o in orders if o.side == Side.BUY]

    assert len(sells) == 2  # INFY and TCS
    assert len(buys) == 1  # RELIANCE

    mistimed = [o for o in orders if o.created_at != now]
    assert mistimed == [], f"every rebalance order must carry the decision time, got {mistimed}"

    non_market = [o for o in orders if o.order_type != OrderType.MARKET]
    assert non_market == [], f"rebalance orders must be MARKET, got {non_market}"


def test_position_sizer_methods() -> None:
    equity = Decimal("1000000.00")
    price = Decimal("1000.00")

    # Fixed fractional
    qty_fixed = PositionSizer.fixed_fractional(equity, 0.20, price)
    assert qty_fixed == 200  # 200k / 1000 = 200

    # Volatility parity
    qty_vol = PositionSizer.volatility_parity(equity, 0.20, 0.02, price)
    assert qty_vol > 0

    # ATR risk budget
    qty_atr = PositionSizer.atr_risk_budget(equity, 20.0, 0.01, price, 2.0)
    assert qty_atr > 0

    # Kelly criterion
    f = PositionSizer.kelly_criterion(0.60, 1.5, 0.5)
    assert 0.0 < f < 1.0
