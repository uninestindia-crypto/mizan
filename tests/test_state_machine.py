"""Tests for OrderStateMachine lifecycle rules and illegal transition prevention."""

from datetime import UTC, datetime

import pytest

from quant_system.core.domain import Order, OrderStatus, OrderType, Side
from quant_system.execution.state_machine import OrderStateMachine


def test_order_state_machine_valid_transitions() -> None:
    now = datetime(2025, 1, 1, 9, 15, tzinfo=UTC)
    order = Order(
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        created_at=now,
    )
    assert order.status == OrderStatus.PENDING

    # PENDING -> SUBMITTED
    submitted = OrderStateMachine.transition(order, OrderStatus.SUBMITTED)
    assert submitted.status == OrderStatus.SUBMITTED

    # SUBMITTED -> FILLED
    filled = OrderStateMachine.transition(submitted, OrderStatus.FILLED)
    assert filled.status == OrderStatus.FILLED


def test_order_state_machine_illegal_transition() -> None:
    now = datetime(2025, 1, 1, 9, 15, tzinfo=UTC)
    order = Order(
        order_id="o1",
        symbol="INFY",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        created_at=now,
        status=OrderStatus.FILLED,  # Terminal state
    )

    # Attempt to transition FILLED -> CANCELLED
    with pytest.raises(ValueError, match="Illegal order transition"):
        OrderStateMachine.transition(order, OrderStatus.CANCELLED)
