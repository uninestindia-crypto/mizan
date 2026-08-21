"""Order lifecycle state machine and deterministic transition rules."""

from __future__ import annotations

from quant_system.core.domain import Order, OrderStatus


class OrderStateMachine:
    """Enforces strict, valid state transitions for trading orders."""

    _ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
        OrderStatus.PENDING: {OrderStatus.SUBMITTED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
        OrderStatus.SUBMITTED: {
            OrderStatus.FILLED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        },
        OrderStatus.PARTIALLY_FILLED: {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.PARTIALLY_FILLED,
        },
        OrderStatus.FILLED: set(),  # Terminal state
        OrderStatus.CANCELLED: set(),  # Terminal state
        OrderStatus.REJECTED: set(),  # Terminal state
    }

    @classmethod
    def can_transition(cls, current_status: OrderStatus, target_status: OrderStatus) -> bool:
        return target_status in cls._ALLOWED_TRANSITIONS.get(current_status, set())

    @classmethod
    def transition(cls, order: Order, new_status: OrderStatus, reason: str | None = None) -> Order:
        if not cls.can_transition(order.status, new_status):
            raise ValueError(
                f"Illegal order transition from {order.status} to {new_status} for order {order.order_id}"
            )

        return Order(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            created_at=order.created_at,
            limit_price=order.limit_price,
            status=new_status,
            strategy_name=order.strategy_name,
            rejection_reason=reason or order.rejection_reason,
        )
