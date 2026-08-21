"""Tests for Pre-Trade Risk Governor limits, circuit breakers, peak tracking, and kill switches."""

from datetime import datetime
from decimal import Decimal

from quant_system.core.domain import Order, OrderType, Quote, Side
from quant_system.risk.checks import RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor


def test_risk_governor_approval_flow() -> None:
    """Verifies normal order approval within configured risk limits."""
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

    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("500000.00"),
        current_cash=Decimal("500000.00"),
        positions={},
        current_quote=quote,
    )
    assert decision.approved is True
    assert decision.reason == "RISK_APPROVED"
    assert decision.limits_id == limits.limits_id
    assert len(decision.decision_hash) == 64


def test_risk_governor_rejects_oversized_position() -> None:
    """Verifies rejection when proposed order breaches maximum position concentration."""
    limits = RiskLimits(max_position_weight=0.20)
    gov = PreTradeRiskGovernor(limits=limits)
    now = datetime(2025, 1, 1, 9, 15)

    # 250 shares @ 1000 = 250,000 (50% of 500k equity > 20% limit)
    order = Order(
        order_id="o_over",
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


def test_risk_governor_cash_buffer_enforcement() -> None:
    """Verifies that available cash must exceed order value PLUS the required minimum cash buffer."""
    limits = RiskLimits(min_cash_buffer_pct=0.10)  # 10% buffer = 50,000 on 500,000 equity
    gov = PreTradeRiskGovernor(limits=limits)
    now = datetime(2025, 1, 1, 9, 15)

    # Cash = 100,000. Min buffer needed = 50,000. Available for trade = 50,000.
    # Trying to buy 60,000 worth (60 shares @ 1000)
    order = Order(
        order_id="o_cash",
        symbol="INFY",
        side=Side.BUY,
        quantity=60,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    quote = Quote(symbol="INFY", timestamp=now, bid=Decimal("1000.00"), ask=Decimal("1000.00"))

    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("500000.00"),
        current_cash=Decimal("100000.00"),
        positions={},
        current_quote=quote,
    )
    assert decision.approved is False
    assert "INSUFFICIENT_CASH" in decision.reason


def test_risk_governor_daily_drawdown_kill_switch() -> None:
    """Verifies that daily drawdown breach triggers the automatic kill switch."""
    limits = RiskLimits(max_daily_drawdown_pct=0.03)  # 3% daily drawdown
    gov = PreTradeRiskGovernor(limits=limits, initial_equity=Decimal("1000000.00"))
    now = datetime(2025, 1, 1, 11, 0)

    # Peak equity is 1,000,000. Equity drops to 960,000 (4% drawdown > 3% limit)
    order = Order(
        order_id="o_dd",
        symbol="TCS",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    quote = Quote(symbol="TCS", timestamp=now, bid=Decimal("3500.00"), ask=Decimal("3500.00"))

    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("960000.00"),
        current_cash=Decimal("500000.00"),
        positions={},
        current_quote=quote,
    )
    assert decision.approved is False
    assert "DAILY_DRAWDOWN_LIMIT_BREACHED" in decision.reason
    assert gov.is_killed is True
    assert len(gov.kill_events) == 1
    assert gov.kill_events[0].trigger_source == "AUTOMATIC_BREACH"


def test_risk_governor_trailing_max_drawdown_kill_switch() -> None:
    """Verifies trailing all-time max drawdown breaker."""
    limits = RiskLimits(
        max_daily_drawdown_pct=0.20, max_total_drawdown_pct=0.10
    )  # 10% max total DD
    gov = PreTradeRiskGovernor(limits=limits, initial_equity=Decimal("2000000.00"))
    now = datetime(2025, 1, 1, 12, 0)

    # Equity drops to 1,750,000 (12.5% drawdown from 2M peak)
    order = Order(
        order_id="o_tdd",
        symbol="TCS",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    quote = Quote(symbol="TCS", timestamp=now, bid=Decimal("3500.00"), ask=Decimal("3500.00"))

    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("1750000.00"),
        current_cash=Decimal("500000.00"),
        positions={},
        current_quote=quote,
    )
    assert decision.approved is False
    assert "TOTAL_MAX_DRAWDOWN_BREACHED" in decision.reason
    assert gov.is_killed is True


def test_risk_governor_spread_and_missing_price_checks() -> None:
    """Verifies spread gate and missing price rejections."""
    gov = PreTradeRiskGovernor(limits=RiskLimits(max_allowed_spread_pct=0.01))
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
    wide_quote = Quote(symbol="INFY", timestamp=now, bid=Decimal("100.00"), ask=Decimal("105.00"))

    decision = gov.evaluate_order(
        order=order,
        current_equity=Decimal("100000.00"),
        current_cash=Decimal("100000.00"),
        positions={},
        current_quote=wide_quote,
    )
    assert decision.approved is False
    assert "SPREAD_TOO_WIDE" in decision.reason

    # Missing quote and missing limit price
    decision_no_price = gov.evaluate_order(
        order=order,
        current_equity=Decimal("100000.00"),
        current_cash=Decimal("100000.00"),
        positions={},
        current_quote=None,
    )
    assert decision_no_price.approved is False
    assert decision_no_price.reason == "MISSING_PRICE_FOR_RISK_VALUATION"


def test_risk_governor_state_persistence_and_recovery() -> None:
    """Verifies that governor peaks and kill state persist and restore cleanly across restarts."""
    gov = PreTradeRiskGovernor(initial_equity=Decimal("1000000.00"))
    gov.update_peaks(Decimal("1200000.00"))
    gov.trigger_kill_switch(reason="EMERGENCY_HALT")

    state = gov.get_state()
    assert state["is_killed"] is True
    assert state["all_time_peak_equity"] == "1200000.00"

    # Restore in fresh instance
    new_gov = PreTradeRiskGovernor()
    new_gov.restore_state(state)

    assert new_gov.is_killed is True
    assert new_gov.all_time_peak_equity == Decimal("1200000.00")
