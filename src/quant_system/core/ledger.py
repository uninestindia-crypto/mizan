"""Exact Decimal double-entry cash and position ledger for zero penny-leak accounting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from quant_system.core.domain import Fill, PortfolioSnapshot, Position, Side

_PAISA = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class LedgerTransaction:
    """Immutable single transaction record in the ledger."""

    tx_id: str
    timestamp: datetime
    description: str
    cash_delta: Decimal
    symbol: str | None = None
    quantity_delta: int = 0
    resulting_cash: Decimal = Decimal("0")


class DecimalLedger:
    """Maintains exact Decimal double-entry records for portfolio cash and asset balances."""

    def __init__(self, initial_cash: Decimal, allow_short: bool = False) -> None:
        if initial_cash < Decimal("0"):
            raise ValueError(f"Initial cash cannot be negative: {initial_cash}")
        self._initial_cash: Decimal = initial_cash.quantize(_PAISA)
        self._cash: Decimal = self._initial_cash
        self._allow_short: bool = allow_short
        self._positions: dict[str, Position] = {}
        self._transactions: list[LedgerTransaction] = []
        self._realized_pnl: Decimal = Decimal("0.00")

    @property
    def cash(self) -> Decimal:
        return self._cash

    @property
    def initial_cash(self) -> Decimal:
        return self._initial_cash

    @property
    def positions(self) -> Mapping[str, Position]:
        return dict(self._positions)

    @property
    def realized_pnl(self) -> Decimal:
        return self._realized_pnl

    @property
    def transactions(self) -> list[LedgerTransaction]:
        return list(self._transactions)

    def process_fill(self, fill: Fill) -> LedgerTransaction:
        """Processes an executed trade fill, updating cash, position and recording a ledger entry."""
        cash_delta = fill.net_cash_delta.quantize(_PAISA)
        new_cash = self._cash + cash_delta

        if new_cash < Decimal("0"):
            raise ValueError(
                f"Ledger invariant violation: cash would drop below zero ({new_cash}) on fill {fill.fill_id}"
            )

        self._cash = new_cash

        # Update position
        symbol = fill.symbol
        current_pos = self._positions.get(symbol)

        if fill.side == Side.BUY:
            if current_pos is None or current_pos.quantity == 0:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=fill.quantity,
                    average_price=fill.price,
                    realized_pnl=Decimal("0.00"),
                )
            elif current_pos.quantity < 0:
                # Covering short position
                covered_qty = min(abs(current_pos.quantity), fill.quantity)
                # Realized P&L = (Short Entry Price - Buy Cover Price) * Qty - Fee
                pnl = (
                    (current_pos.average_price - fill.price) * Decimal(covered_qty) - fill.fee
                ).quantize(_PAISA)
                self._realized_pnl += pnl
                remaining_qty = current_pos.quantity + fill.quantity
                if remaining_qty == 0:
                    del self._positions[symbol]
                else:
                    self._positions[symbol] = Position(
                        symbol=symbol,
                        quantity=remaining_qty,
                        average_price=current_pos.average_price
                        if remaining_qty < 0
                        else fill.price,
                        realized_pnl=current_pos.realized_pnl + pnl,
                    )
            else:
                # Adding to long position
                total_qty = current_pos.quantity + fill.quantity
                total_cost = (current_pos.average_price * Decimal(current_pos.quantity)) + (
                    fill.price * Decimal(fill.quantity)
                )
                avg_price = (total_cost / Decimal(total_qty)).quantize(_PAISA)
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=total_qty,
                    average_price=avg_price,
                    realized_pnl=current_pos.realized_pnl,
                )
            qty_delta = fill.quantity

        else:  # Side.SELL
            if current_pos is None or current_pos.quantity == 0:
                if not self._allow_short:
                    raise ValueError(
                        f"Cannot sell {fill.quantity} of {symbol}; short selling is disabled"
                    )
                # Open short position
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=-fill.quantity,
                    average_price=fill.price,
                    realized_pnl=Decimal("0.00"),
                )
            elif current_pos.quantity < 0:
                if not self._allow_short:
                    raise ValueError(
                        f"Cannot sell {fill.quantity} of {symbol}; short selling is disabled"
                    )
                # Add to existing short position
                total_short = abs(current_pos.quantity) + fill.quantity
                total_credit = (current_pos.average_price * Decimal(abs(current_pos.quantity))) + (
                    fill.price * Decimal(fill.quantity)
                )
                avg_short_price = (total_credit / Decimal(total_short)).quantize(_PAISA)
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=-total_short,
                    average_price=avg_short_price,
                    realized_pnl=current_pos.realized_pnl,
                )
            else:
                # Selling from long position
                if current_pos.quantity < fill.quantity and not self._allow_short:
                    raise ValueError(
                        f"Cannot sell {fill.quantity} of {symbol}; only have {current_pos.quantity}"
                    )

                sell_from_long = min(current_pos.quantity, fill.quantity)
                sell_revenue = fill.price * Decimal(sell_from_long)
                buy_cost = current_pos.average_price * Decimal(sell_from_long)
                pnl = (sell_revenue - buy_cost - fill.fee).quantize(_PAISA)
                self._realized_pnl += pnl

                remaining_qty = current_pos.quantity - fill.quantity
                if remaining_qty == 0:
                    del self._positions[symbol]
                else:
                    self._positions[symbol] = Position(
                        symbol=symbol,
                        quantity=remaining_qty,
                        average_price=current_pos.average_price
                        if remaining_qty > 0
                        else fill.price,
                        realized_pnl=current_pos.realized_pnl + pnl,
                    )
            qty_delta = -fill.quantity

        tx = LedgerTransaction(
            tx_id=f"tx_{len(self._transactions) + 1}",
            timestamp=fill.timestamp,
            description=f"{fill.side.value} {fill.quantity} {symbol} @ {fill.price}",
            cash_delta=cash_delta,
            symbol=symbol,
            quantity_delta=qty_delta,
            resulting_cash=self._cash,
        )
        self._transactions.append(tx)
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
            total_market_val += pos.current_market_value(price)
            unrealized += pos.unrealized_pnl(price)

        return PortfolioSnapshot(
            timestamp=timestamp,
            cash=self._cash,
            positions=dict(self._positions),
            total_market_value=total_market_val,
            unrealized_pnl=unrealized,
            realized_pnl=self._realized_pnl,
        )

    def reconcile(self) -> bool:
        """Verifies that initial cash + sum of all cash deltas equals current cash exactly to the paisa."""
        computed_cash = self._initial_cash + sum(tx.cash_delta for tx in self._transactions)
        if computed_cash.quantize(_PAISA) != self._cash.quantize(_PAISA):
            raise RuntimeError(
                f"Ledger reconciliation mismatch: Computed {computed_cash} != Stored {self._cash}"
            )
        return True
