"""Tests for Pre-Trade Risk Governor limits, circuit breakers, and kill switch."""

from datetime import datetime
from decimal import Decimal

from quant_system.core.domain import Order, OrderType, Quote, Side
from quant_system.risk.checks import RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor


def test_risk_governor_approval_flow() -> None:
    limits = RiskLimits(
        max_position_weight=0.30,
        max_daily_drawdown_pct=0.03,
        min_cash_buffer_pct=0.05,
    )
    gov = PreTradeRiskGovernor(limits=limits)

    now = datetime(2025, 1, 1, 9, 15)
    order = Order(
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=50,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    quote = Quote(symbol="INFY", timestamp=now, bid=Decimal("1000.00"), ask=Decimal("1000.00"))

    # Portfolio with 500,000 cash
    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("500000.00"),
        current_cash=Decimal("500000.00"),
        positions={},
        current_quote=quote,
    )
    # Order value = 50 * 1000 = 50,000 (10% of 500k <= 30% max weight)
    assert decision.approved is True
    assert decision.reason == "RISK_APPROVED"


def test_risk_governor_rejects_oversized_position() -> None:
    limits = RiskLimits(max_position_weight=0.20)
    gov = PreTradeRiskGovernor(limits=limits)

    now = datetime(2025, 1, 1, 9, 15)
    # Trying to buy 250,000 worth (50% of 500k equity)
    order = Order(
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=250,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    quote = Quote(symbol="INFY", timestamp=now, bid=Decimal("1000.00"), ask=Decimal("1000.00"))

    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("500000.00"),
        current_cash=Decimal("500000.00"),
        positions={},
        current_quote=quote,
    )
    assert decision.approved is False
    assert "POSITION_WEIGHT_LIMIT_EXCEEDED" in decision.reason


def test_risk_governor_null_quote_regression() -> None:
    gov = PreTradeRiskGovernor()
    now = datetime(2025, 1, 1, 9, 15)
    order = Order(
        order_id="o_no_price",
        symbol="INFY",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    # Both limit_price and quote are None
    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("100000.00"),
        current_cash=Decimal("100000.00"),
        positions={},
        current_quote=None,
    )
    assert decision.approved is False
    assert decision.reason == "MISSING_PRICE_FOR_RISK_VALUATION"


def test_risk_governor_wide_spread_rejection() -> None:
    gov = PreTradeRiskGovernor(limits=RiskLimits(max_allowed_spread_pct=0.01))  # 1% max spread
    now = datetime(2025, 1, 1, 9, 15)
    order = Order(
        order_id="o_spread",
        symbol="INFY",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    # 5% spread: bid 100, ask 105
    wide_quote = Quote(
        symbol="INFY",
        timestamp=now,
        bid=Decimal("100.00"),
        ask=Decimal("105.00"),
    )
    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("100000.00"),
        current_cash=Decimal("100000.00"),
        positions={},
        current_quote=wide_quote,
    )
    assert decision.approved is False
    assert "SPREAD_TOO_WIDE" in decision.reason


def test_risk_governor_kill_switch() -> None:
    gov = PreTradeRiskGovernor()
    gov.trigger_kill_switch("EMERGENCY")
    assert gov.is_killed is True

    now = datetime(2025, 1, 1, 9, 15)
    order = Order(
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    quote = Quote(symbol="INFY", timestamp=now, bid=Decimal("1000.00"), ask=Decimal("1000.00"))

    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("500000.00"),
        current_cash=Decimal("500000.00"),
        positions={},
        current_quote=quote,
    )
    assert decision.approved is False
    assert decision.reason == "KILL_SWITCH_ACTIVE"
