"""Tests for Indian regulatory charges, STT, turnover, GST, and slippage."""

from decimal import Decimal

from quant_system.backtest.costs import IndianMarketCostModel
from quant_system.core.domain import Side


def test_equity_delivery_costs() -> None:
    # Buy 100 shares @ 1000 = 100,000 turnover
    buy_costs = IndianMarketCostModel.calculate_equity_delivery(
        side=Side.BUY,
        quantity=100,
        price=Decimal("1000.00"),
        slippage_bps=5.0,
    )
    # STT = 0.1% of 100k = 100
    assert buy_costs.stt == Decimal("100.00")
    # Stamp duty on Buy = 0.015% = 15
    assert buy_costs.stamp_duty == Decimal("15.00")
    # Total fee > 0
    assert buy_costs.total_fee > Decimal("115.00")
    assert buy_costs.slippage == Decimal("50.00")  # 5 bps of 100k = 50


def test_options_friction_costs() -> None:
    # Sell 25 option contracts @ 200 premium = 5,000 turnover
    sell_costs = IndianMarketCostModel.calculate_options_friction(
        side=Side.SELL,
        quantity=25,
        premium=Decimal("200.00"),
        strike=Decimal("24500.00"),
        slippage_bps=20.0,
    )
    # Brokerage = 20
    assert sell_costs.brokerage == Decimal("20.00")
    # STT on sell option premium = 0.1% of 5,000 = 5.00
    assert sell_costs.stt == Decimal("5.00")
    assert sell_costs.gst > Decimal("3.00")
    assert sell_costs.total_fee > Decimal("28.00")
