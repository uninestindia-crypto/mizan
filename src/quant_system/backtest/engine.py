"""Deterministic, event-driven backtesting engine with next-bar open execution and zero lookahead."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from quant_system.backtest.costs import IndianMarketCostModel
from quant_system.core.domain import (
    Fill,
    Order,
    OrderType,
    PortfolioSnapshot,
    PriceBar,
    Quote,
    Side,
)
from quant_system.core.ledger import DecimalLedger
from quant_system.risk.governor import PreTradeRiskGovernor
from quant_system.strategies.base import BaseStrategy, MarketContext

_PAISA = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    initial_cash: Decimal
    final_equity: Decimal
    total_return_pct: float
    total_trades: int
    fills: Sequence[Fill]
    equity_curve: Sequence[PortfolioSnapshot]
    total_friction_paid: Decimal


class BacktestEngine:
    """Simulates trading strategies chronologically through market history with zero lookahead bias."""

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_cash: Decimal = Decimal("1000000.00"),  # Default ₹10 Lakhs
        risk_governor: PreTradeRiskGovernor | None = None,
        slippage_bps: float = 5.0,
    ) -> None:
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.risk_governor = risk_governor or PreTradeRiskGovernor()
        self.slippage_bps = slippage_bps
        self.ledger = DecimalLedger(initial_cash=self.initial_cash)
        self.fills: list[Fill] = []
        self.equity_curve: list[PortfolioSnapshot] = []

    def run(self, symbol_bars: Mapping[str, Sequence[PriceBar]]) -> BacktestResult:
        """Executes the backtest across all timestamps in the dataset."""
        # Align all unique chronological timestamps
        all_timestamps = sorted({b.timestamp for bars in symbol_bars.values() for b in bars})

        if not all_timestamps:
            raise ValueError("No historical bars provided to backtest engine.")

        # Build symbol lookup by timestamp
        bars_by_time: dict[datetime, dict[str, PriceBar]] = {}
        for sym, bars in symbol_bars.items():
            for b in bars:
                if b.timestamp not in bars_by_time:
                    bars_by_time[b.timestamp] = {}
                bars_by_time[b.timestamp][sym] = b

        pending_orders: list[Order] = []
        history_so_far: dict[str, list[PriceBar]] = {sym: [] for sym in symbol_bars.keys()}
        total_friction = Decimal("0.00")

        for t in all_timestamps:
            current_bars = bars_by_time.get(t, {})

            # 1. Execute any PENDING orders generated from the previous bar's signals at current OPEN
            if pending_orders:
                remaining_orders = []
                for order in pending_orders:
                    bar = current_bars.get(order.symbol)
                    if not bar:
                        remaining_orders.append(order)
                        continue

                    # Fill at Next-Bar Open with Slippage
                    fill_price = bar.open
                    if order.side == Side.BUY:
                        slippage_adj = fill_price * Decimal(str(self.slippage_bps / 10000.0))
                        fill_price = (fill_price + slippage_adj).quantize(_PAISA)
                    else:
                        slippage_adj = fill_price * Decimal(str(self.slippage_bps / 10000.0))
                        fill_price = (fill_price - slippage_adj).quantize(_PAISA)

                    # Calculate Costs
                    cost_breakdown = IndianMarketCostModel.calculate_equity_delivery(
                        side=order.side,
                        quantity=order.quantity,
                        price=fill_price,
                        slippage_bps=0.0,  # Slippage already baked into fill_price
                    )

                    fill = Fill(
                        fill_id=f"fill_{len(self.fills) + 1}",
                        order_id=order.order_id,
                        symbol=order.symbol,
                        side=order.side,
                        quantity=order.quantity,
                        price=fill_price,
                        fee=cost_breakdown.total_fee,
                        timestamp=t,
                    )
                    try:
                        self.ledger.process_fill(fill)
                        self.fills.append(fill)
                        total_friction += cost_breakdown.total_fee + slippage_adj * Decimal(
                            order.quantity
                        )
                    except ValueError:
                        # Order rejected due to cash/position violation
                        pass

                pending_orders = remaining_orders

            # Update historical seen bars
            for sym, bar in current_bars.items():
                history_so_far[sym].append(bar)

            # 2. Mark Portfolio to Market at current bar Close
            positions = self.ledger.positions
            total_mkt_val = Decimal("0.00")
            unrealized = Decimal("0.00")

            for sym, pos in positions.items():
                bar = current_bars.get(sym)
                c_price = bar.close if bar else pos.average_price
                total_mkt_val += pos.current_market_value(c_price)
                unrealized += pos.unrealized_pnl(c_price)

            snapshot = PortfolioSnapshot(
                timestamp=t,
                cash=self.ledger.cash,
                positions=dict(positions),
                total_market_value=total_mkt_val,
                unrealized_pnl=unrealized,
                realized_pnl=self.ledger.realized_pnl,
            )
            self.equity_curve.append(snapshot)

            # 3. Strategy generates signals at current bar CLOSE
            ctx = MarketContext(
                current_time=t,
                current_bars=current_bars,
                historical_bars=history_so_far,
                current_positions=positions,
                available_cash=self.ledger.cash,
                extra_data={},
            )
            signals = self.strategy.generate_signals(ctx)

            # 4. Convert Signals to Orders & Validate through Risk Governor
            for sig in signals:
                curr_bar = current_bars.get(sig.symbol)
                if not curr_bar:
                    continue

                if sig.side == Side.BUY:
                    # Determine target quantity capped by risk governor position limit
                    raw_w = sig.target_weight or 0.20
                    target_w = min(raw_w, self.risk_governor.limits.max_position_weight * 0.98)
                    allocated_cash = snapshot.total_equity * Decimal(str(target_w))
                    target_qty = int(allocated_cash / curr_bar.close)
                    current_qty = positions[sig.symbol].quantity if sig.symbol in positions else 0
                    qty_to_buy = target_qty - current_qty

                    if qty_to_buy > 0:
                        order = Order(
                            order_id=f"ord_{len(pending_orders) + len(self.fills) + 1}",
                            symbol=sig.symbol,
                            side=Side.BUY,
                            quantity=qty_to_buy,
                            order_type=OrderType.MARKET,
                            created_at=t,
                            strategy_name=self.strategy.name,
                        )
                        # Risk Check
                        fake_quote = Quote(
                            symbol=sig.symbol,
                            timestamp=t,
                            bid=curr_bar.close,
                            ask=curr_bar.close,
                            last_price=curr_bar.close,
                        )
                        decision = self.risk_governor.evaluate_order(
                            order=order,
                            current_equity=snapshot.total_equity,
                            current_cash=self.ledger.cash,
                            positions=positions,
                            current_quote=fake_quote,
                        )
                        if decision.approved:
                            pending_orders.append(order)

                elif sig.side is None or sig.side == Side.SELL:
                    # Exit held position
                    if sig.symbol in positions and positions[sig.symbol].quantity > 0:
                        order = Order(
                            order_id=f"ord_{len(pending_orders) + len(self.fills) + 1}",
                            symbol=sig.symbol,
                            side=Side.SELL,
                            quantity=positions[sig.symbol].quantity,
                            order_type=OrderType.MARKET,
                            created_at=t,
                            strategy_name=self.strategy.name,
                        )
                        pending_orders.append(order)

        # Reconcile final ledger
        self.ledger.reconcile()

        final_equity = (
            self.equity_curve[-1].total_equity if self.equity_curve else self.initial_cash
        )
        ret_pct = float((final_equity - self.initial_cash) / self.initial_cash)

        return BacktestResult(
            initial_cash=self.initial_cash,
            final_equity=final_equity,
            total_return_pct=ret_pct,
            total_trades=len(self.fills),
            fills=self.fills,
            equity_curve=self.equity_curve,
            total_friction_paid=total_friction,
        )
