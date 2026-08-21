"""Quote-Driven Paper Pilot execution engine for QuantOS.

Provides deterministic top-of-book and L2 market depth matching, conservative adverse slippage,
queue priority delay, partial fill allocation against displayed depth, pre-trade risk gating,
atomic Decimal ledger mutation with stable idempotency keys, clean session-end order cancellation,
and daily penny-exact reconciliation.

Enforces financial-model-craft and nse-execution-craft standards.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from quant_system.backtest.costs import IndianMarketCostModel, TransactionCostBreakdown
from quant_system.core.domain import (
    Fill,
    Order,
    OrderStatus,
    OrderType,
    PortfolioSnapshot,
    Position,
    Quote,
    Side,
)
from quant_system.core.ledger import DecimalLedger
from quant_system.execution.orderbook_sim import (
    FillSimulationResult,
    OrderBookSimConfig,
    OrderBookSimulator,
    OrderBookSnapshot,
)
from quant_system.execution.state_machine import OrderStateMachine
from quant_system.risk.checks import RiskDecision, RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor

_PAISA = Decimal("0.01")


class SessionStatus(StrEnum):
    """Lifecycle status of a Paper Pilot trading session."""

    INITIALIZED = "INITIALIZED"
    ACTIVE = "ACTIVE"
    HALTED = "HALTED"
    CLOSED = "CLOSED"
    OFFLINE = "OFFLINE"
    UNAUTHORIZED = "UNAUTHORIZED"


@dataclass(frozen=True, slots=True)
class PaperProposal:
    """Trading proposal submitted by a strategy/model to the Paper Pilot."""

    proposal_id: str  # Stable idempotency key
    symbol: str
    side: Side
    quantity: int
    order_type: OrderType
    decision_at: datetime
    limit_price: Decimal | None = None
    strategy_name: str = "PAPER_PILOT"
    model_artifact_id: str = ""
    risk_policy_version: str = "v1.0"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise ValueError("proposal_id cannot be empty (required for idempotency)")
        if self.quantity <= 0:
            raise ValueError(f"Proposal quantity must be positive, got {self.quantity}")
        if self.limit_price is not None and self.limit_price <= Decimal("0"):
            raise ValueError(f"Limit price must be positive, got {self.limit_price}")


@dataclass(frozen=True, slots=True)
class PaperAuditRecord:
    """Immutable audit trail entry for every execution event in the Paper Pilot."""

    event_id: str
    timestamp: datetime
    event_type: str
    proposal_id: str | None = None
    order_id: str | None = None
    fill_id: str | None = None
    symbol: str | None = None
    side: Side | None = None
    quantity: int = 0
    price: Decimal | None = None
    fee: Decimal | None = None
    slippage: Decimal | None = None
    reason: str | None = None
    idempotency_key: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SessionReconciliationReport:
    """Penny-exact independent reconciliation report emitted at session close."""

    session_id: str
    session_date: date
    reconciled: bool
    initial_cash: Decimal
    final_cash: Decimal
    total_cash_delta: Decimal
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_fees_paid: Decimal
    total_slippage_cost: Decimal
    total_trades_count: int
    total_fills_count: int
    orders_submitted: int
    orders_filled: int
    orders_partially_filled: int
    orders_cancelled: int
    orders_rejected: int
    open_orders_remaining: int
    open_positions: Mapping[str, int]
    total_equity: Decimal
    discrepancy_paisa: Decimal = Decimal("0.00")
    reconciliation_errors: tuple[str, ...] = ()


class PaperPilotEngine:
    """Deterministic Quote-Driven Paper Pilot execution engine."""

    def __init__(
        self,
        initial_cash: Decimal = Decimal("1000000.00"),
        risk_governor: PreTradeRiskGovernor | None = None,
        sim_config: OrderBookSimConfig | None = None,
        allow_short: bool = False,
        session_id: str = "paper_session_1",
    ) -> None:
        self.session_id: str = session_id
        self.risk_governor: PreTradeRiskGovernor = risk_governor or PreTradeRiskGovernor(
            limits=RiskLimits(allow_naked_short=allow_short)
        )
        self.sim_config: OrderBookSimConfig = sim_config or OrderBookSimConfig()
        self.orderbook_sim: OrderBookSimulator = OrderBookSimulator(self.sim_config)
        self.ledger: DecimalLedger = DecimalLedger(
            initial_cash=initial_cash,
            allow_short=allow_short,
        )

        self._session_status: SessionStatus = SessionStatus.INITIALIZED
        self._session_date: date | None = None
        self._opened_at: datetime | None = None
        self._closed_at: datetime | None = None
        self._halt_reason: str | None = None

        # Idempotency & proposal storage
        self._proposals: dict[str, PaperProposal] = {}
        self._proposal_orders: dict[str, Order] = {}
        self._proposal_risk_decisions: dict[str, RiskDecision] = {}

        # Orders & fills tracking
        self._orders: dict[str, Order] = {}
        self._order_remaining_qty: dict[str, int] = {}
        self._open_orders: dict[str, list[str]] = defaultdict(list)  # symbol -> list of order_ids
        self._fills: list[Fill] = []
        self._order_fills: dict[str, list[Fill]] = defaultdict(list)
        self._fill_by_id: dict[str, Fill] = {}
        self._fill_cost_breakdowns: dict[str, TransactionCostBreakdown] = {}

        # Market data & clock cache
        self._price_cache: dict[str, Decimal] = {}
        self._last_quote_timestamp: dict[str, datetime] = {}
        self._audit_log: list[PaperAuditRecord] = []
        self._event_counter: int = 0

    @property
    def session_status(self) -> SessionStatus:
        return self._session_status

    @property
    def cash(self) -> Decimal:
        return self.ledger.cash

    @property
    def initial_cash(self) -> Decimal:
        return self.ledger.initial_cash

    @property
    def positions(self) -> Mapping[str, Position]:
        return self.ledger.positions

    @property
    def fills(self) -> list[Fill]:
        return list(self._fills)

    @property
    def orders(self) -> Mapping[str, Order]:
        return dict(self._orders)

    @property
    def audit_log(self) -> list[PaperAuditRecord]:
        return list(self._audit_log)

    def _next_event_id(self) -> str:
        self._event_counter += 1
        return f"evt_{self.session_id}_{self._event_counter:06d}"

    def _log_audit(
        self,
        event_type: str,
        timestamp: datetime,
        proposal_id: str | None = None,
        order_id: str | None = None,
        fill_id: str | None = None,
        symbol: str | None = None,
        side: Side | None = None,
        quantity: int = 0,
        price: Decimal | None = None,
        fee: Decimal | None = None,
        slippage: Decimal | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        record = PaperAuditRecord(
            event_id=self._next_event_id(),
            timestamp=timestamp,
            event_type=event_type,
            proposal_id=proposal_id,
            order_id=order_id,
            fill_id=fill_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            slippage=slippage,
            reason=reason,
            idempotency_key=idempotency_key,
            details=details or {},
        )
        self._audit_log.append(record)

    def start_session(self, session_date: date, timestamp: datetime) -> None:
        """Starts a new active trading session."""
        if self._session_status == SessionStatus.ACTIVE:
            raise RuntimeError(f"Session {self.session_id} is already active")
        self._session_date = session_date
        self._opened_at = timestamp
        self._session_status = SessionStatus.ACTIVE
        self._halt_reason = None
        self._log_audit(
            event_type="SESSION_STARTED",
            timestamp=timestamp,
            details={"session_date": str(session_date), "initial_cash": str(self.cash)},
        )

    def halt_session(self, reason: str, timestamp: datetime) -> None:
        """Halts the active trading session and triggers pre-trade kill switch."""
        self._session_status = SessionStatus.HALTED
        self._halt_reason = reason
        self.risk_governor.trigger_kill_switch(reason=reason)
        # Cancel all open orders on halt
        self.cancel_all_open_orders(reason=f"SESSION_HALTED_{reason}", timestamp=timestamp)
        self._log_audit(
            event_type="SESSION_HALTED",
            timestamp=timestamp,
            reason=reason,
        )

    def resume_session(self, timestamp: datetime) -> None:
        """Resumes a halted session after resolving risk halt."""
        if self._session_status != SessionStatus.HALTED:
            raise RuntimeError(f"Cannot resume session with status {self._session_status}")
        self.risk_governor.reset_kill_switch()
        self._session_status = SessionStatus.ACTIVE
        self._halt_reason = None
        self._log_audit(
            event_type="SESSION_RESUMED",
            timestamp=timestamp,
        )

    def submit_proposal(self, proposal: PaperProposal) -> tuple[Order, RiskDecision]:
        """Submits a trading proposal with strict idempotency and pre-trade risk checks."""
        # 1. Check idempotency (AC-64)
        if proposal.proposal_id in self._proposals:
            existing_proposal = self._proposals[proposal.proposal_id]
            # Verify field equality
            if (
                existing_proposal.symbol != proposal.symbol
                or existing_proposal.side != proposal.side
                or existing_proposal.quantity != proposal.quantity
                or existing_proposal.order_type != proposal.order_type
                or existing_proposal.limit_price != proposal.limit_price
            ):
                raise ValueError(
                    f"Idempotency conflict: proposal {proposal.proposal_id} already exists with different parameters"
                )
            # Idempotent replay: return cached order and decision without mutating ledger
            return (
                self._proposal_orders[proposal.proposal_id],
                self._proposal_risk_decisions[proposal.proposal_id],
            )

        # 2. Check session state
        if self._session_status != SessionStatus.ACTIVE:
            order_id = f"ord_{proposal.proposal_id}"
            rejected_order = Order(
                order_id=order_id,
                symbol=proposal.symbol,
                side=proposal.side,
                quantity=proposal.quantity,
                order_type=proposal.order_type,
                created_at=proposal.decision_at,
                limit_price=proposal.limit_price,
                status=OrderStatus.REJECTED,
                strategy_name=proposal.strategy_name,
                rejection_reason=f"SESSION_NOT_ACTIVE_{self._session_status}",
            )
            decision = RiskDecision(
                approved=False,
                reason=f"SESSION_NOT_ACTIVE_{self._session_status}",
                order_id=order_id,
                current_equity=self.cash,
                order_value=Decimal("0.00"),
                resulting_leverage=0.0,
            )
            self._proposals[proposal.proposal_id] = proposal
            self._proposal_orders[proposal.proposal_id] = rejected_order
            self._proposal_risk_decisions[proposal.proposal_id] = decision
            self._orders[order_id] = rejected_order
            self._log_audit(
                event_type="PROPOSAL_REJECTED",
                timestamp=proposal.decision_at,
                proposal_id=proposal.proposal_id,
                order_id=order_id,
                reason=decision.reason,
            )
            return rejected_order, decision

        # 3. Create initial order in PENDING status
        order_id = f"ord_{proposal.proposal_id}"
        order = Order(
            order_id=order_id,
            symbol=proposal.symbol,
            side=proposal.side,
            quantity=proposal.quantity,
            order_type=proposal.order_type,
            created_at=proposal.decision_at,
            limit_price=proposal.limit_price,
            status=OrderStatus.PENDING,
            strategy_name=proposal.strategy_name,
        )

        # 4. Pre-trade Risk Evaluation
        current_equity = self.ledger.cash + sum(
            p.current_market_value(self._price_cache.get(p.symbol, p.average_price))
            for p in self.ledger.positions.values()
        )

        cached_price = self._price_cache.get(proposal.symbol)
        quote_for_risk: Quote | None = None
        if cached_price is not None:
            quote_for_risk = Quote(
                symbol=proposal.symbol,
                timestamp=proposal.decision_at,
                bid=cached_price,
                ask=cached_price,
            )

        if quote_for_risk is not None or order.limit_price is not None:
            decision = self.risk_governor.evaluate_order(
                order=order,
                current_equity=current_equity,
                current_cash=self.ledger.cash,
                positions=self.ledger.positions,
                current_quote=quote_for_risk,
            )
        else:
            # Staged valuation: check non-price rules (kill switch, naked shorts)
            if self.risk_governor.is_killed:
                decision = RiskDecision(
                    approved=False,
                    reason="KILL_SWITCH_ACTIVE",
                    order_id=order_id,
                    current_equity=current_equity,
                    order_value=Decimal("0.00"),
                    resulting_leverage=0.0,
                )
            elif proposal.side == Side.SELL and not self.risk_governor.limits.allow_naked_short:
                current_held = (
                    self.ledger.positions[proposal.symbol].quantity
                    if proposal.symbol in self.ledger.positions
                    else 0
                )
                if proposal.quantity > current_held:
                    decision = RiskDecision(
                        approved=False,
                        reason=f"NAKED_SHORT_FORBIDDEN: Selling {proposal.quantity} but only hold {current_held}",
                        order_id=order_id,
                        current_equity=current_equity,
                        order_value=Decimal("0.00"),
                        resulting_leverage=0.0,
                    )
                else:
                    decision = RiskDecision(
                        approved=True,
                        reason="RISK_APPROVED",
                        order_id=order_id,
                        current_equity=current_equity,
                        order_value=Decimal("0.00"),
                        resulting_leverage=1.0,
                    )
            else:
                decision = RiskDecision(
                    approved=True,
                    reason="RISK_APPROVED",
                    order_id=order_id,
                    current_equity=current_equity,
                    order_value=Decimal("0.00"),
                    resulting_leverage=1.0,
                )

        if not decision.approved:
            rejected_order = OrderStateMachine.transition(
                order, OrderStatus.REJECTED, reason=decision.reason
            )
            self._proposals[proposal.proposal_id] = proposal
            self._proposal_orders[proposal.proposal_id] = rejected_order
            self._proposal_risk_decisions[proposal.proposal_id] = decision
            self._orders[order_id] = rejected_order
            self._log_audit(
                event_type="RISK_REJECTED",
                timestamp=proposal.decision_at,
                proposal_id=proposal.proposal_id,
                order_id=order_id,
                reason=decision.reason,
                details={"observed_equity": str(current_equity)},
            )
            return rejected_order, decision

        # 5. Transition to SUBMITTED and stage in order queue
        submitted_order = OrderStateMachine.transition(order, OrderStatus.SUBMITTED)
        self._proposals[proposal.proposal_id] = proposal
        self._proposal_orders[proposal.proposal_id] = submitted_order
        self._proposal_risk_decisions[proposal.proposal_id] = decision
        self._orders[order_id] = submitted_order
        self._order_remaining_qty[order_id] = proposal.quantity
        self._open_orders[proposal.symbol].append(order_id)

        self._log_audit(
            event_type="ORDER_SUBMITTED",
            timestamp=proposal.decision_at,
            proposal_id=proposal.proposal_id,
            order_id=order_id,
            symbol=proposal.symbol,
            side=proposal.side,
            quantity=proposal.quantity,
            idempotency_key=proposal.proposal_id,
        )

        return submitted_order, decision

    def process_quote(
        self,
        quote_or_book: Quote | OrderBookSnapshot,
        current_time: datetime | None = None,
    ) -> list[Fill]:
        """Processes an incoming market quote / depth snapshot against pending orders."""
        if isinstance(quote_or_book, Quote):
            book = OrderBookSnapshot.from_quote(quote_or_book)
        else:
            book = quote_or_book

        symbol = book.symbol
        eval_time = current_time or book.timestamp

        # Check out-of-order quotes (AC-65)
        last_ts = self._last_quote_timestamp.get(symbol)
        if last_ts is not None and book.timestamp <= last_ts:
            self._log_audit(
                event_type="OUT_OF_ORDER_QUOTE_DROPPED",
                timestamp=eval_time,
                symbol=symbol,
                reason=f"Quote timestamp {book.timestamp} <= last seen {last_ts}",
            )
            return []

        self._last_quote_timestamp[symbol] = book.timestamp

        # Update price cache for mark-to-market
        if book.mid_price is not None:
            self._price_cache[symbol] = book.mid_price
        elif book.last_price is not None:
            self._price_cache[symbol] = book.last_price

        # If session not active, do not execute fills
        if self._session_status != SessionStatus.ACTIVE:
            return []

        # Retrieve active orders for this symbol
        active_order_ids = list(self._open_orders.get(symbol, []))
        if not active_order_ids:
            return []

        executed_fills: list[Fill] = []

        for order_id in active_order_ids:
            order = self._orders[order_id]
            remaining_qty = self._order_remaining_qty.get(order_id, 0)
            if remaining_qty <= 0:
                continue

            sim_result: FillSimulationResult = self.orderbook_sim.simulate_fill(
                order=order,
                book=book,
                current_time=eval_time,
                remaining_quantity=remaining_qty,
            )

            if sim_result.is_executable and sim_result.filled_quantity > 0:
                # Calculate exact transaction costs
                is_option = symbol.endswith("CE") or symbol.endswith("PE")
                if is_option:
                    cost_breakdown = IndianMarketCostModel.calculate_options_friction(
                        side=order.side,
                        quantity=sim_result.filled_quantity,
                        premium=sim_result.vwap_price,
                        strike=sim_result.vwap_price,
                        slippage_bps=0.0,  # Slippage already factored in vwap_price
                    )
                else:
                    cost_breakdown = IndianMarketCostModel.calculate_equity_delivery(
                        side=order.side,
                        quantity=sim_result.filled_quantity,
                        price=sim_result.vwap_price,
                        slippage_bps=0.0,  # Slippage already factored in vwap_price
                    )

                fill_index = len(self._order_fills[order_id]) + 1
                fill_id = f"fill_{order_id}_{fill_index}"
                fill = Fill(
                    fill_id=fill_id,
                    order_id=order_id,
                    symbol=symbol,
                    side=order.side,
                    quantity=sim_result.filled_quantity,
                    price=sim_result.vwap_price,
                    fee=cost_breakdown.total_fee,
                    timestamp=book.timestamp,
                )

                # Atomic mutation of ledger
                try:
                    self.ledger.process_fill(fill)
                    self._fills.append(fill)
                    self._order_fills[order_id].append(fill)
                    self._fill_by_id[fill_id] = fill
                    self._fill_cost_breakdowns[fill_id] = cost_breakdown
                    executed_fills.append(fill)

                    new_remaining = remaining_qty - sim_result.filled_quantity
                    self._order_remaining_qty[order_id] = new_remaining

                    if new_remaining == 0:
                        updated_order = OrderStateMachine.transition(order, OrderStatus.FILLED)
                        self._orders[order_id] = updated_order
                        self._open_orders[symbol].remove(order_id)
                        self._log_audit(
                            event_type="ORDER_FILLED",
                            timestamp=book.timestamp,
                            order_id=order_id,
                            fill_id=fill_id,
                            symbol=symbol,
                            side=order.side,
                            quantity=sim_result.filled_quantity,
                            price=sim_result.vwap_price,
                            fee=cost_breakdown.total_fee,
                            slippage=sim_result.total_slippage,
                        )
                    else:
                        updated_order = OrderStateMachine.transition(
                            order, OrderStatus.PARTIALLY_FILLED
                        )
                        self._orders[order_id] = updated_order
                        self._log_audit(
                            event_type="ORDER_PARTIALLY_FILLED",
                            timestamp=book.timestamp,
                            order_id=order_id,
                            fill_id=fill_id,
                            symbol=symbol,
                            side=order.side,
                            quantity=sim_result.filled_quantity,
                            price=sim_result.vwap_price,
                            fee=cost_breakdown.total_fee,
                            slippage=sim_result.total_slippage,
                            details={"remaining_quantity": new_remaining},
                        )

                except ValueError as err:
                    # Ledger rejected fill (e.g. insufficient cash) -> Atomic no-op on ledger, cancel remainder
                    self._log_audit(
                        event_type="FILL_LEDGER_REJECTED",
                        timestamp=book.timestamp,
                        order_id=order_id,
                        reason=str(err),
                    )
                    self.cancel_order(
                        order_id=order_id,
                        reason=f"LEDGER_REJECTED_{err}",
                        timestamp=book.timestamp,
                    )

            elif sim_result.status == OrderStatus.REJECTED:
                # Quote violation caused rejection of order
                rejected_order = OrderStateMachine.transition(
                    order, OrderStatus.REJECTED, reason=sim_result.rejection_reason
                )
                self._orders[order_id] = rejected_order
                if order_id in self._open_orders[symbol]:
                    self._open_orders[symbol].remove(order_id)
                self._log_audit(
                    event_type="ORDER_REJECTED_BY_MARKET",
                    timestamp=book.timestamp,
                    order_id=order_id,
                    symbol=symbol,
                    reason=sim_result.rejection_reason,
                )

        return executed_fills

    def cancel_order(
        self,
        order_id: str,
        reason: str = "USER_CANCELLED",
        timestamp: datetime | None = None,
    ) -> Order:
        """Cancels an active or partially filled order cleanly."""
        if order_id not in self._orders:
            raise KeyError(f"Order {order_id} not found")

        order = self._orders[order_id]
        if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            # Already terminal state
            return order

        cancelled_order = OrderStateMachine.transition(order, OrderStatus.CANCELLED, reason=reason)
        self._orders[order_id] = cancelled_order
        if order_id in self._open_orders.get(order.symbol, []):
            self._open_orders[order.symbol].remove(order_id)

        ts = timestamp or order.created_at
        self._log_audit(
            event_type="ORDER_CANCELLED",
            timestamp=ts,
            order_id=order_id,
            symbol=order.symbol,
            reason=reason,
            details={"remaining_quantity": self._order_remaining_qty.get(order_id, 0)},
        )
        return cancelled_order

    def cancel_all_open_orders(
        self,
        reason: str = "SESSION_END_CANCELLED",
        timestamp: datetime | None = None,
    ) -> list[Order]:
        """Cancels all remaining open and partially filled orders across all instruments."""
        cancelled_list: list[Order] = []
        for symbol in list(self._open_orders.keys()):
            for order_id in list(self._open_orders[symbol]):
                cancelled = self.cancel_order(order_id=order_id, reason=reason, timestamp=timestamp)
                cancelled_list.append(cancelled)
        return cancelled_list

    def get_portfolio_snapshot(
        self,
        timestamp: datetime,
        current_prices: Mapping[str, Decimal] | None = None,
    ) -> PortfolioSnapshot:
        """Computes exact mark-to-market snapshot of portfolio state."""
        prices = dict(self._price_cache)
        if current_prices:
            prices.update(current_prices)
        return self.ledger.get_portfolio_snapshot(current_prices=prices, timestamp=timestamp)

    def end_session(
        self,
        timestamp: datetime,
        close_prices: Mapping[str, Decimal] | None = None,
    ) -> SessionReconciliationReport:
        """Closes session, cleanly cancels open orders, runs independent penny-exact reconciliation."""
        if self._session_status == SessionStatus.CLOSED:
            raise RuntimeError(f"Session {self.session_id} is already closed")

        self._closed_at = timestamp

        # 1. Clean session-end cancellation of open orders (AC-63, AC-72)
        self.cancel_all_open_orders(reason="SESSION_END_CANCELLED", timestamp=timestamp)

        # 2. Update closing prices
        if close_prices:
            self._price_cache.update(close_prices)

        self._session_status = SessionStatus.CLOSED

        # 3. Independent Ledger & Position Reconciliation (financial-model-craft non-negotiable invariant)
        errors: list[str] = []

        # (a) Cash integrity
        computed_cash = self.ledger.initial_cash + sum(
            tx.cash_delta for tx in self.ledger.transactions
        )
        discrepancy = (computed_cash - self.ledger.cash).quantize(_PAISA)
        if discrepancy != Decimal("0.00"):
            errors.append(
                f"CASH_MISMATCH: Computed {computed_cash} != Stored {self.ledger.cash} (diff {discrepancy})"
            )

        # (b) Position balance integrity
        for sym, pos in self.ledger.positions.items():
            net_filled_qty = sum(
                f.quantity if f.side == Side.BUY else -f.quantity
                for f in self._fills
                if f.symbol == sym
            )
            if pos.quantity != net_filled_qty:
                errors.append(
                    f"POSITION_MISMATCH for {sym}: Ledger {pos.quantity} != Net Fills {net_filled_qty}"
                )

        # (c) Open orders integrity
        remaining_open_count = sum(len(orders) for orders in self._open_orders.values())
        if remaining_open_count > 0:
            errors.append(
                f"OPEN_ORDERS_REMAINING: {remaining_open_count} orders not cancelled at session end"
            )

        # Counts
        submitted_count = sum(1 for o in self._orders.values() if o.status != OrderStatus.PENDING)
        filled_count = sum(1 for o in self._orders.values() if o.status == OrderStatus.FILLED)
        partially_filled_count = sum(
            1 for o in self._orders.values() if o.status == OrderStatus.PARTIALLY_FILLED
        )
        cancelled_count = sum(1 for o in self._orders.values() if o.status == OrderStatus.CANCELLED)
        rejected_count = sum(1 for o in self._orders.values() if o.status == OrderStatus.REJECTED)

        total_fees = sum((f.fee for f in self._fills), Decimal("0.00"))
        total_slippage = sum(
            (breakdown.slippage for breakdown in self._fill_cost_breakdowns.values()),
            Decimal("0.00"),
        )

        snapshot = self.get_portfolio_snapshot(timestamp=timestamp, current_prices=close_prices)

        reconciled = len(errors) == 0

        report = SessionReconciliationReport(
            session_id=self.session_id,
            session_date=self._session_date or timestamp.date(),
            reconciled=reconciled,
            initial_cash=self.ledger.initial_cash,
            final_cash=self.ledger.cash,
            total_cash_delta=(self.ledger.cash - self.ledger.initial_cash).quantize(_PAISA),
            total_realized_pnl=self.ledger.realized_pnl,
            total_unrealized_pnl=snapshot.unrealized_pnl,
            total_fees_paid=total_fees,
            total_slippage_cost=total_slippage,
            total_trades_count=len(self._fills),
            total_fills_count=len(self._fills),
            orders_submitted=submitted_count,
            orders_filled=filled_count,
            orders_partially_filled=partially_filled_count,
            orders_cancelled=cancelled_count,
            orders_rejected=rejected_count,
            open_orders_remaining=remaining_open_count,
            open_positions={s: p.quantity for s, p in self.ledger.positions.items()},
            total_equity=snapshot.total_equity,
            discrepancy_paisa=discrepancy,
            reconciliation_errors=tuple(errors),
        )

        self._log_audit(
            event_type="SESSION_CLOSED",
            timestamp=timestamp,
            details={
                "reconciled": reconciled,
                "final_cash": str(self.ledger.cash),
                "total_equity": str(snapshot.total_equity),
                "errors": errors,
            },
        )

        return report
