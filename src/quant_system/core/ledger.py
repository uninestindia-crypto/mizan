"""Exact Decimal double-entry cash and position ledger for zero penny-leak accounting.

Implements pure single-path event processing with stable idempotency keys, FIFO lot tracking,
rejection of binary floats, atomic validation-before-mutation, and SHA-256 state reconciliation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from quant_system.core.domain import Fill, PortfolioSnapshot, Position, Side

_PAISA = Decimal("0.01")


class IdempotencyConflictError(ValueError):
    """Raised when an event is submitted with an existing idempotency key but differing payload."""


class LedgerInvariantViolation(ValueError):
    """Raised when an operation would violate fundamental accounting identities or constraints."""


def _assert_no_float(val: Any, name: str) -> None:
    """Strictly rejects binary floats in the exact accounting kernel."""
    if isinstance(val, float):
        raise TypeError(
            f"Binary float forbidden in exact accounting kernel: {name}={val}. Use exact Decimal or integer."
        )


@dataclass(frozen=True, slots=True)
class PositionLot:
    """Immutable record of an individual inventory lot."""

    lot_id: str
    symbol: str
    side: Side  # BUY for long lot, SELL for short lot
    quantity: int
    entry_price: Decimal
    entry_fee: Decimal
    timestamp: datetime
    fill_id: str

    def __post_init__(self) -> None:
        _assert_no_float(self.entry_price, "entry_price")
        _assert_no_float(self.entry_fee, "entry_fee")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, int)
            or self.quantity <= 0
        ):
            raise ValueError(f"Lot quantity must be a positive integer, got {self.quantity}")
        if self.entry_price <= Decimal("0"):
            raise ValueError(f"Lot entry price must be strictly positive, got {self.entry_price}")
        if self.entry_fee < Decimal("0"):
            raise ValueError(f"Lot entry fee cannot be negative, got {self.entry_fee}")

    @property
    def cost_basis(self) -> Decimal:
        return (self.entry_price * Decimal(self.quantity)).quantize(_PAISA)


@dataclass(frozen=True, slots=True)
class LedgerTransaction:
    """Immutable single transaction record in the ledger."""

    tx_id: str
    timestamp: datetime
    description: str
    cash_delta: Decimal
    symbol: str | None = None
    quantity_delta: int = 0
    resulting_cash: Decimal = Decimal("0.00")
    idempotency_key: str = ""
    tx_hash: str = ""

    def __post_init__(self) -> None:
        _assert_no_float(self.cash_delta, "cash_delta")
        _assert_no_float(self.resulting_cash, "resulting_cash")
        if not self.tx_hash:
            payload = {
                "tx_id": self.tx_id,
                "timestamp": self.timestamp.isoformat(),
                "description": self.description,
                "cash_delta": str(self.cash_delta),
                "symbol": self.symbol,
                "quantity_delta": self.quantity_delta,
                "resulting_cash": str(self.resulting_cash),
                "idempotency_key": self.idempotency_key,
            }
            computed = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            object.__setattr__(self, "tx_hash", computed)


@dataclass(frozen=True, slots=True)
class CashFlowEvent:
    """External deposit or withdrawal event."""

    event_id: str
    amount: Decimal
    timestamp: datetime
    description: str = ""

    def __post_init__(self) -> None:
        _assert_no_float(self.amount, "amount")
        if self.amount == Decimal("0"):
            raise ValueError("Cash flow amount cannot be zero")


class DecimalLedger:
    """Exact Decimal double-entry accounting kernel with FIFO lots, idempotency, and SHA-256 state verification."""

    def __init__(self, initial_cash: Decimal, allow_short: bool = False) -> None:
        _assert_no_float(initial_cash, "initial_cash")
        if initial_cash < Decimal("0"):
            raise ValueError(f"Initial cash cannot be negative: {initial_cash}")

        self._initial_cash: Decimal = initial_cash.quantize(_PAISA)
        self._cash: Decimal = self._initial_cash
        self._allow_short: bool = allow_short
        self._positions: dict[str, Position] = {}
        self._lots: dict[str, list[PositionLot]] = {}
        self._transactions: list[LedgerTransaction] = []
        self._realized_pnl: Decimal = Decimal("0.00")
        self._processed_events: dict[str, dict[str, Any]] = {}
        self._next_lot_id: int = 1

    @property
    def cash(self) -> Decimal:
        return self._cash

    @property
    def initial_cash(self) -> Decimal:
        return self._initial_cash

    @property
    def allow_short(self) -> bool:
        return self._allow_short

    @property
    def positions(self) -> Mapping[str, Position]:
        return dict(self._positions)

    @property
    def lots(self) -> Mapping[str, list[PositionLot]]:
        return {sym: list(lot_list) for sym, lot_list in self._lots.items()}

    @property
    def realized_pnl(self) -> Decimal:
        return self._realized_pnl

    @property
    def transactions(self) -> list[LedgerTransaction]:
        return list(self._transactions)

    @property
    def state_hash(self) -> str:
        """Computes deterministic SHA-256 reconciliation hash over the entire ledger state."""
        pos_repr = [
            {
                "symbol": sym,
                "quantity": pos.quantity,
                "average_price": str(pos.average_price),
                "realized_pnl": str(pos.realized_pnl),
            }
            for sym, pos in sorted(self._positions.items())
        ]
        lot_repr = [
            {
                "symbol": sym,
                "lots": [
                    {
                        "lot_id": lot.lot_id,
                        "side": lot.side.value,
                        "quantity": lot.quantity,
                        "entry_price": str(lot.entry_price),
                        "entry_fee": str(lot.entry_fee),
                        "timestamp": lot.timestamp.isoformat(),
                        "fill_id": lot.fill_id,
                    }
                    for lot in lots
                ],
            }
            for sym, lots in sorted(self._lots.items())
        ]
        tx_hashes = [tx.tx_hash for tx in self._transactions]
        payload = {
            "initial_cash": str(self._initial_cash),
            "cash": str(self._cash),
            "allow_short": self._allow_short,
            "realized_pnl": str(self._realized_pnl),
            "positions": pos_repr,
            "lots": lot_repr,
            "tx_hashes": tx_hashes,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def process_cash_flow(self, event: CashFlowEvent) -> LedgerTransaction:
        """Processes an external deposit (positive amount) or withdrawal (negative amount)."""
        _assert_no_float(event.amount, "amount")
        key = f"cash_flow_{event.event_id}"
        cached = self._processed_events.get(key)
        if cached is not None:
            expected_payload = {
                "event_id": event.event_id,
                "amount": str(event.amount),
                "timestamp": event.timestamp.isoformat(),
            }
            if cached["payload"] == expected_payload:
                return cast(LedgerTransaction, cached["transaction"])
            raise IdempotencyConflictError(
                f"CashFlowEvent {event.event_id} already exists with conflicting payload"
            )

        amount_quantized = event.amount.quantize(_PAISA)
        new_cash = self._cash + amount_quantized
        if new_cash < Decimal("0"):
            raise LedgerInvariantViolation(
                f"Withdrawal of {event.amount} would cause cash balance to drop below zero (current cash {self._cash})"
            )

        self._cash = new_cash
        tx = LedgerTransaction(
            tx_id=f"tx_{len(self._transactions) + 1}",
            timestamp=event.timestamp,
            description=event.description or f"External Cash Flow: {amount_quantized}",
            cash_delta=amount_quantized,
            symbol=None,
            quantity_delta=0,
            resulting_cash=self._cash,
            idempotency_key=key,
        )
        self._transactions.append(tx)
        self._processed_events[key] = {
            "payload": {
                "event_id": event.event_id,
                "amount": str(event.amount),
                "timestamp": event.timestamp.isoformat(),
            },
            "transaction": tx,
        }
        return tx

    def process_fill(self, fill: Fill) -> LedgerTransaction:
        """Processes an executed trade fill atomically with FIFO lot accounting and idempotency verification."""
        _assert_no_float(fill.price, "fill.price")
        _assert_no_float(fill.fee, "fill.fee")
        if isinstance(fill.quantity, bool) or not isinstance(fill.quantity, int):
            raise TypeError(f"Fill quantity must be an integer, got {type(fill.quantity)}")

        # 1. Check Idempotency Key
        idemp_key = f"fill_{fill.fill_id}"
        cached = self._processed_events.get(idemp_key)
        if cached is not None:
            expected_payload = {
                "fill_id": fill.fill_id,
                "order_id": fill.order_id,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.quantity,
                "price": str(fill.price),
                "fee": str(fill.fee),
                "timestamp": fill.timestamp.isoformat(),
            }
            if cached["payload"] == expected_payload:
                return cast(LedgerTransaction, cached["transaction"])
            raise IdempotencyConflictError(
                f"Fill {fill.fill_id} already processed with differing payload: "
                f"existing={cached['payload']} vs new={expected_payload}"
            )

        # 2. Pre-validate Cash Invariant
        cash_delta = fill.net_cash_delta.quantize(_PAISA)
        new_cash = self._cash + cash_delta
        if new_cash < Decimal("0"):
            raise ValueError(
                f"Ledger invariant violation: cash would drop below zero ({new_cash}) on fill {fill.fill_id}"
            )

        symbol = fill.symbol
        current_pos = self._positions.get(symbol)
        cur_qty = current_pos.quantity if current_pos is not None else 0

        # Pre-validate Short Selling Policy
        if fill.side == Side.SELL and not self._allow_short:
            if cur_qty < fill.quantity:
                raise ValueError(
                    f"Cannot sell {fill.quantity} of {symbol}; only have {cur_qty} and short selling is disabled"
                )

        # 3. State Preparation (Dry-run / atomic compute before applying mutations)
        symbol_lots = list(self._lots.get(symbol, []))
        total_realized_pnl_delta = Decimal("0.00")
        new_lots: list[PositionLot] = []

        if fill.side == Side.BUY:
            qty_to_fill = fill.quantity
            qty_delta = fill.quantity

            if cur_qty < 0:
                # Covering short position (FIFO)
                short_qty_to_cover = min(abs(cur_qty), qty_to_fill)
                remaining_to_cover = short_qty_to_cover
                buy_remaining_lots: list[PositionLot] = []

                for lot in symbol_lots:
                    if remaining_to_cover == 0:
                        buy_remaining_lots.append(lot)
                        continue
                    if lot.quantity <= remaining_to_cover:
                        # Fully close this short lot
                        lot_pnl = (lot.entry_price - fill.price) * Decimal(
                            lot.quantity
                        ) - lot.entry_fee
                        total_realized_pnl_delta += lot_pnl
                        remaining_to_cover -= lot.quantity
                    else:
                        # Partially close this short lot
                        closed_qty = remaining_to_cover
                        pro_rata_entry_fee = (
                            lot.entry_fee * Decimal(closed_qty) / Decimal(lot.quantity)
                        ).quantize(_PAISA)
                        lot_pnl = (lot.entry_price - fill.price) * Decimal(
                            closed_qty
                        ) - pro_rata_entry_fee
                        total_realized_pnl_delta += lot_pnl
                        buy_remaining_lots.append(
                            PositionLot(
                                lot_id=lot.lot_id,
                                symbol=lot.symbol,
                                side=lot.side,
                                quantity=lot.quantity - closed_qty,
                                entry_price=lot.entry_price,
                                entry_fee=lot.entry_fee - pro_rata_entry_fee,
                                timestamp=lot.timestamp,
                                fill_id=lot.fill_id,
                            )
                        )
                        remaining_to_cover = 0

                # Subtract execution fee from realized P&L
                total_realized_pnl_delta -= fill.fee
                total_realized_pnl_delta = total_realized_pnl_delta.quantize(_PAISA)

                # Remaining buy quantity opens new long lot if any (Position Flip)
                remaining_buy = qty_to_fill - short_qty_to_cover
                if remaining_buy > 0:
                    lot_id = f"lot_{self._next_lot_id}"
                    buy_remaining_lots.append(
                        PositionLot(
                            lot_id=lot_id,
                            symbol=symbol,
                            side=Side.BUY,
                            quantity=remaining_buy,
                            entry_price=fill.price,
                            entry_fee=fill.fee if short_qty_to_cover == 0 else Decimal("0.00"),
                            timestamp=fill.timestamp,
                            fill_id=fill.fill_id,
                        )
                    )
                new_lots = buy_remaining_lots
            else:
                # Adding to long position
                new_lots = list(symbol_lots)
                lot_id = f"lot_{self._next_lot_id}"
                new_lots.append(
                    PositionLot(
                        lot_id=lot_id,
                        symbol=symbol,
                        side=Side.BUY,
                        quantity=qty_to_fill,
                        entry_price=fill.price,
                        entry_fee=fill.fee,
                        timestamp=fill.timestamp,
                        fill_id=fill.fill_id,
                    )
                )

        else:  # Side.SELL
            qty_to_fill = fill.quantity
            qty_delta = -fill.quantity

            if cur_qty > 0:
                # Selling from long position (FIFO)
                long_qty_to_sell = min(cur_qty, qty_to_fill)
                remaining_to_sell = long_qty_to_sell
                sell_remaining_lots: list[PositionLot] = []

                for lot in symbol_lots:
                    if remaining_to_sell == 0:
                        sell_remaining_lots.append(lot)
                        continue
                    if lot.quantity <= remaining_to_sell:
                        # Fully close this long lot
                        lot_pnl = (fill.price - lot.entry_price) * Decimal(
                            lot.quantity
                        ) - lot.entry_fee
                        total_realized_pnl_delta += lot_pnl
                        remaining_to_sell -= lot.quantity
                    else:
                        # Partially close this long lot
                        closed_qty = remaining_to_sell
                        pro_rata_entry_fee = (
                            lot.entry_fee * Decimal(closed_qty) / Decimal(lot.quantity)
                        ).quantize(_PAISA)
                        lot_pnl = (fill.price - lot.entry_price) * Decimal(
                            closed_qty
                        ) - pro_rata_entry_fee
                        total_realized_pnl_delta += lot_pnl
                        sell_remaining_lots.append(
                            PositionLot(
                                lot_id=lot.lot_id,
                                symbol=lot.symbol,
                                side=lot.side,
                                quantity=lot.quantity - closed_qty,
                                entry_price=lot.entry_price,
                                entry_fee=lot.entry_fee - pro_rata_entry_fee,
                                timestamp=lot.timestamp,
                                fill_id=lot.fill_id,
                            )
                        )
                        remaining_to_sell = 0

                # Subtract execution fee
                total_realized_pnl_delta -= fill.fee
                total_realized_pnl_delta = total_realized_pnl_delta.quantize(_PAISA)

                # Remaining sell quantity opens short lot if allow_short (Position Flip)
                remaining_sell = qty_to_fill - long_qty_to_sell
                if remaining_sell > 0:
                    if not self._allow_short:
                        raise ValueError(
                            f"Cannot short {remaining_sell} of {symbol}; short selling is disabled"
                        )
                    lot_id = f"lot_{self._next_lot_id}"
                    sell_remaining_lots.append(
                        PositionLot(
                            lot_id=lot_id,
                            symbol=symbol,
                            side=Side.SELL,
                            quantity=remaining_sell,
                            entry_price=fill.price,
                            entry_fee=fill.fee if long_qty_to_sell == 0 else Decimal("0.00"),
                            timestamp=fill.timestamp,
                            fill_id=fill.fill_id,
                        )
                    )
                new_lots = sell_remaining_lots
            else:
                # Opening/Adding to short position
                if not self._allow_short:
                    raise ValueError(
                        f"Cannot sell {fill.quantity} of {symbol}; short selling is disabled"
                    )
                new_lots = list(symbol_lots)
                lot_id = f"lot_{self._next_lot_id}"
                new_lots.append(
                    PositionLot(
                        lot_id=lot_id,
                        symbol=symbol,
                        side=Side.SELL,
                        quantity=qty_to_fill,
                        entry_price=fill.price,
                        entry_fee=fill.fee,
                        timestamp=fill.timestamp,
                        fill_id=fill.fill_id,
                    )
                )

        # 4. Commit Mutations Atomically
        self._cash = new_cash
        self._realized_pnl = (self._realized_pnl + total_realized_pnl_delta).quantize(_PAISA)

        if not new_lots:
            self._lots.pop(symbol, None)
            self._positions.pop(symbol, None)
        else:
            self._lots[symbol] = new_lots
            # Compute new aggregated position
            total_qty = sum(
                lot.quantity if lot.side == Side.BUY else -lot.quantity for lot in new_lots
            )
            if total_qty == 0:
                self._positions.pop(symbol, None)
            else:
                total_cost = sum(lot.entry_price * Decimal(lot.quantity) for lot in new_lots)
                avg_price = (total_cost / Decimal(abs(total_qty))).quantize(_PAISA)
                prev_pos_realized = (
                    current_pos.realized_pnl if current_pos is not None else Decimal("0.00")
                )
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=total_qty,
                    average_price=avg_price,
                    realized_pnl=(prev_pos_realized + total_realized_pnl_delta).quantize(_PAISA),
                )

        self._next_lot_id += 1

        tx = LedgerTransaction(
            tx_id=f"tx_{len(self._transactions) + 1}",
            timestamp=fill.timestamp,
            description=f"{fill.side.value} {fill.quantity} {symbol} @ {fill.price}",
            cash_delta=cash_delta,
            symbol=symbol,
            quantity_delta=qty_delta,
            resulting_cash=self._cash,
            idempotency_key=idemp_key,
        )
        self._transactions.append(tx)

        # Record idempotency record
        self._processed_events[idemp_key] = {
            "payload": {
                "fill_id": fill.fill_id,
                "order_id": fill.order_id,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.quantity,
                "price": str(fill.price),
                "fee": str(fill.fee),
                "timestamp": fill.timestamp.isoformat(),
            },
            "transaction": tx,
        }
        return tx

    def get_portfolio_snapshot(
        self,
        current_prices: Mapping[str, Decimal],
        timestamp: datetime,
    ) -> PortfolioSnapshot:
        """Computes exact mark-to-market portfolio snapshot given current asset prices."""
        total_market_val = Decimal("0.00")
        unrealized = Decimal("0.00")

        for sym, pos in self._positions.items():
            price = current_prices.get(sym, pos.average_price)
            _assert_no_float(price, f"current_prices[{sym}]")
            total_market_val += pos.current_market_value(price)
            unrealized += pos.unrealized_pnl(price)

        return PortfolioSnapshot(
            timestamp=timestamp,
            cash=self._cash,
            positions=dict(self._positions),
            total_market_value=total_market_val.quantize(_PAISA),
            unrealized_pnl=unrealized.quantize(_PAISA),
            realized_pnl=self._realized_pnl,
        )

    def reconcile(self) -> bool:
        """Independently verifies all ledger accounting identities to the exact paisa."""
        # 1. Sum of cash deltas
        computed_cash = self._initial_cash + sum(tx.cash_delta for tx in self._transactions)
        if computed_cash.quantize(_PAISA) != self._cash.quantize(_PAISA):
            raise RuntimeError(
                f"Ledger reconciliation mismatch: Computed cash {computed_cash} != Stored cash {self._cash}"
            )

        # 2. Position quantity sum vs lot quantity sum
        for sym, pos in self._positions.items():
            lots = self._lots.get(sym, [])
            lot_qty_sum = sum(
                lot.quantity if lot.side == Side.BUY else -lot.quantity for lot in lots
            )
            if pos.quantity != lot_qty_sum:
                raise RuntimeError(
                    f"Position lot quantity mismatch for {sym}: Position {pos.quantity} != Lots sum {lot_qty_sum}"
                )

        # 3. Realized PnL sanity
        if not self._transactions and self._realized_pnl != Decimal("0.00"):
            raise RuntimeError(
                f"Realized P&L non-zero ({self._realized_pnl}) with empty transactions"
            )

        return True
