"""Deterministic Paper Broker bound to live/simulated market quotes and ledger accounting."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from quant_system.backtest.costs import IndianMarketCostModel
from quant_system.core.domain import (
    Fill,
    Order,
    OrderStatus,
    Position,
    Quote,
    Side,
)
from quant_system.core.ledger import DecimalLedger
from quant_system.execution.state_machine import OrderStateMachine
from quant_system.risk.governor import PreTradeRiskGovernor

_PAISA = Decimal("0.01")


class DeterministicPaperBroker:
    """Simulates realistic broker fills with deterministic execution rules and pre-trade risk gating."""

    def __init__(
        self,
        initial_cash: Decimal = Decimal("1000000.00"),
        risk_governor: PreTradeRiskGovernor | None = None,
        slippage_bps: float = 5.0,
    ) -> None:
        self.risk_governor = risk_governor or PreTradeRiskGovernor()
        self.ledger = DecimalLedger(
            initial_cash=initial_cash,
            allow_short=self.risk_governor.limits.allow_naked_short,
        )
        self.slippage_bps = slippage_bps
        self._orders: dict[str, Order] = {}
        self._fills: list[Fill] = []
        self._price_cache: dict[str, Decimal] = {}

    @property
    def cash(self) -> Decimal:
        return self.ledger.cash

    @property
    def positions(self) -> Mapping[str, Position]:
        return self.ledger.positions

    @property
    def fills(self) -> list[Fill]:
        return list(self._fills)

    def submit_order(self, order: Order, current_quote: Quote) -> Order:
        """Processes an incoming order: Risk check -> Validation -> Immediate fill if Market order."""
        submitted_order = OrderStateMachine.transition(order, OrderStatus.SUBMITTED)
        self._orders[order.order_id] = submitted_order
        self._price_cache[current_quote.symbol] = current_quote.mid_price

        # Full mark-to-market across all open portfolio positions
        current_equity = self.ledger.cash + sum(
            p.current_market_value(self._price_cache.get(p.symbol, p.average_price))
            for p in self.ledger.positions.values()
        )

        decision = self.risk_governor.evaluate_order(
            order=submitted_order,
            current_equity=current_equity,
            current_cash=self.ledger.cash,
            positions=self.ledger.positions,
            current_quote=current_quote,
        )

        if not decision.approved:
            rejected = OrderStateMachine.transition(
                submitted_order, OrderStatus.REJECTED, reason=decision.reason
            )
            self._orders[order.order_id] = rejected
            return rejected

        # Execute Market Order against Quote
        if order.side == Side.BUY:
            raw_price = current_quote.ask
            slip_adj = raw_price * Decimal(str(self.slippage_bps / 10000.0))
            exec_price = (raw_price + slip_adj).quantize(_PAISA)
        else:
            raw_price = current_quote.bid
            slip_adj = raw_price * Decimal(str(self.slippage_bps / 10000.0))
            exec_price = (raw_price - slip_adj).quantize(_PAISA)

        # Route to appropriate transaction friction model
        is_option = order.symbol.endswith("CE") or order.symbol.endswith("PE")
        if is_option:
            cost_breakdown = IndianMarketCostModel.calculate_options_friction(
                side=order.side,
                quantity=order.quantity,
                premium=exec_price,
                strike=exec_price,
                slippage_bps=0.0,
            )
        else:
            cost_breakdown = IndianMarketCostModel.calculate_equity_delivery(
                side=order.side,
                quantity=order.quantity,
                price=exec_price,
                slippage_bps=0.0,
            )

        fill = Fill(
            fill_id=f"paper_fill_{len(self._fills) + 1}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            fee=cost_breakdown.total_fee,
            timestamp=current_quote.timestamp,
        )

        try:
            self.ledger.process_fill(fill)
            self._fills.append(fill)
            filled_order = OrderStateMachine.transition(submitted_order, OrderStatus.FILLED)
            self._orders[order.order_id] = filled_order
            return filled_order
        except ValueError as err:
            rejected = OrderStateMachine.transition(
                submitted_order, OrderStatus.REJECTED, reason=str(err)
            )
            self._orders[order.order_id] = rejected
            return rejected
