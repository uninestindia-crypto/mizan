"""Tests for Deterministic Paper Broker and order execution flows."""

from datetime import datetime
from decimal import Decimal

from quant_system.core.domain import Order, OrderStatus, OrderType, Quote, Side
from quant_system.execution.paper_broker import DeterministicPaperBroker


def test_paper_broker_order_execution() -> None:
    broker = DeterministicPaperBroker(initial_cash=Decimal("1000000.00"), slippage_bps=5.0)
    now = datetime(2025, 1, 1, 9, 15)

    order = Order(
        order_id="p1",
        symbol="INFY",
        side=Side.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    quote = Quote(
        symbol="INFY",
        timestamp=now,
        bid=Decimal("1500.00"),
        ask=Decimal("1500.50"),
        last_price=Decimal("1500.25"),
    )

    filled = broker.submit_order(order, quote)
    assert filled.status == OrderStatus.FILLED
    assert len(broker.fills) == 1
    assert broker.fills[0].symbol == "INFY"
    assert broker.positions["INFY"].quantity == 100
    assert broker.cash < Decimal("1000000.00")
    assert broker.ledger.reconcile() is True


def test_paper_broker_options_execution() -> None:
    from quant_system.risk.checks import RiskLimits
    from quant_system.risk.governor import PreTradeRiskGovernor

    risk_gov = PreTradeRiskGovernor(
        limits=RiskLimits(allow_naked_short=True, max_position_weight=0.50)
    )
    broker = DeterministicPaperBroker(initial_cash=Decimal("500000.00"), risk_governor=risk_gov)
    now = datetime(2025, 1, 1, 9, 20)

    order = Order(
        order_id="opt_1",
        symbol="NIFTY24500CE",
        side=Side.SELL,
        quantity=25,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    quote = Quote(
        symbol="NIFTY24500CE",
        timestamp=now,
        bid=Decimal("200.00"),
        ask=Decimal("201.00"),
        last_price=Decimal("200.50"),
    )

    filled = broker.submit_order(order, quote)
    assert filled.status == OrderStatus.FILLED
    assert len(broker.fills) == 1
    assert broker.fills[0].fee >= Decimal("20.00")  # Options flat brokerage
    assert broker.positions["NIFTY24500CE"].quantity == -25
    assert broker.ledger.reconcile() is True
