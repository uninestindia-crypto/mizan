"""Portfolio target allocation, multi-strategy capital budgeting, and rebalancing."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from quant_system.core.domain import Order, OrderType, Position, Side


class PortfolioAllocator:
    """Computes order diffs to rebalance current portfolio positions to target weights."""

    @staticmethod
    def compute_rebalance_orders(
        current_equity: Decimal,
        current_positions: Mapping[str, Position],
        current_prices: Mapping[str, Decimal],
        target_weights: Mapping[str, float],
        min_trade_value: Decimal = Decimal("500.00"),
        timestamp: datetime | None = None,
    ) -> list[Order]:
        """Calculates BUY and SELL orders required to match target asset weights."""
        order_time = timestamp if timestamp is not None else datetime.now(UTC)
        orders: list[Order] = []

        all_symbols = sorted(set(current_positions.keys()) | set(target_weights.keys()))

        # First pass: Sells (to free up cash)
        for idx, sym in enumerate(all_symbols, start=1):
            price = current_prices.get(sym)
            if not price or price <= Decimal("0"):
                continue

            current_qty = current_positions[sym].quantity if sym in current_positions else 0
            target_weight = target_weights.get(sym, 0.0)
            target_val = current_equity * Decimal(str(target_weight))
            target_qty = int(target_val / price)

            qty_diff = target_qty - current_qty

            if qty_diff < 0:  # Need to SELL
                sell_qty = abs(qty_diff)
                trade_val = Decimal(sell_qty) * price
                if trade_val >= min_trade_value:
                    orders.append(
                        Order(
                            order_id=f"rebal_sell_{sym}_{idx}",
                            symbol=sym,
                            side=Side.SELL,
                            quantity=sell_qty,
                            order_type=OrderType.MARKET,
                            created_at=order_time,
                        )
                    )

        # Second pass: Buys
        for idx, sym in enumerate(all_symbols, start=1):
            price = current_prices.get(sym)
            if not price or price <= Decimal("0"):
                continue

            current_qty = current_positions[sym].quantity if sym in current_positions else 0
            target_weight = target_weights.get(sym, 0.0)
            target_val = current_equity * Decimal(str(target_weight))
            target_qty = int(target_val / price)

            qty_diff = target_qty - current_qty

            if qty_diff > 0:  # Need to BUY
                buy_qty = qty_diff
                trade_val = Decimal(buy_qty) * price
                if trade_val >= min_trade_value:
                    orders.append(
                        Order(
                            order_id=f"rebal_buy_{sym}_{idx}",
                            symbol=sym,
                            side=Side.BUY,
                            quantity=buy_qty,
                            order_type=OrderType.MARKET,
                            created_at=order_time,
                        )
                    )

        return orders
