"""Deterministic Pre-Trade Risk Governor protecting against fat-tails, excessive sizing, and drawdown."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from quant_system.core.domain import Fill, Order, Position, Quote, Side
from quant_system.risk.checks import KillSwitchEvent, RiskDecision, RiskLimits

_PAISA = Decimal("0.01")


class PreTradeRiskGovernor:
    """Evaluates proposed orders and executed fills against strict capital, leverage, drawdown, and spread rules."""

    def __init__(
        self,
        limits: RiskLimits | None = None,
        initial_equity: Decimal | None = None,
    ) -> None:
        self.limits: RiskLimits = limits or RiskLimits()
        self._is_killed: bool = False
        init_eq = initial_equity if initial_equity is not None else Decimal("0.00")
        self._daily_peak_equity: Decimal = init_eq
        self._all_time_peak_equity: Decimal = init_eq
        self._kill_events: list[KillSwitchEvent] = []

    @property
    def is_killed(self) -> bool:
        return self._is_killed

    @property
    def daily_peak_equity(self) -> Decimal:
        return self._daily_peak_equity

    @property
    def all_time_peak_equity(self) -> Decimal:
        return self._all_time_peak_equity

    @property
    def kill_events(self) -> list[KillSwitchEvent]:
        return list(self._kill_events)

    def trigger_kill_switch(
        self,
        reason: str = "MANUAL_HALT",
        trigger_source: str = "MANUAL",
        current_equity: Decimal | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Instantly halts all new risk taking across the entire system."""
        self._is_killed = True
        event = KillSwitchEvent(
            timestamp=timestamp or datetime.now(UTC),
            reason=reason,
            trigger_source=trigger_source,
            equity_at_halt=current_equity
            if current_equity is not None
            else self._daily_peak_equity,
        )
        self._kill_events.append(event)

    def reset_kill_switch(self) -> None:
        """Resets the kill switch allowing subsequent orders to be evaluated."""
        self._is_killed = False

    def reset_session_peak(self, new_session_equity: Decimal) -> None:
        """Explicitly resets the daily session peak at market open or new trading day."""
        self._daily_peak_equity = new_session_equity
        if new_session_equity > self._all_time_peak_equity:
            self._all_time_peak_equity = new_session_equity

    def update_peaks(self, current_equity: Decimal) -> None:
        """Monotonically updates daily and all-time equity peaks."""
        if current_equity > self._daily_peak_equity:
            self._daily_peak_equity = current_equity
        if current_equity > self._all_time_peak_equity:
            self._all_time_peak_equity = current_equity

    def get_state(self) -> dict[str, Any]:
        """Serializes governor state for persistence and recovery across restarts."""
        return {
            "limits_id": self.limits.limits_id,
            "limits": {
                "limits_id": self.limits.limits_id,
                "max_position_weight": self.limits.max_position_weight,
                "max_daily_drawdown_pct": self.limits.max_daily_drawdown_pct,
                "max_total_drawdown_pct": self.limits.max_total_drawdown_pct,
                "max_portfolio_leverage": self.limits.max_portfolio_leverage,
                "min_cash_buffer_pct": self.limits.min_cash_buffer_pct,
                "max_allowed_spread_pct": self.limits.max_allowed_spread_pct,
                "allow_naked_short": self.limits.allow_naked_short,
                "max_order_value": str(self.limits.max_order_value)
                if self.limits.max_order_value is not None
                else None,
            },
            "is_killed": self._is_killed,
            "daily_peak_equity": str(self._daily_peak_equity),
            "all_time_peak_equity": str(self._all_time_peak_equity),
            "kill_events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "reason": e.reason,
                    "trigger_source": e.trigger_source,
                    "equity_at_halt": str(e.equity_at_halt),
                }
                for e in self._kill_events
            ],
            "kill_events_count": len(self._kill_events),
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restores governor state from persisted snapshot."""
        self._is_killed = bool(state.get("is_killed", False))
        self._daily_peak_equity = Decimal(str(state.get("daily_peak_equity", "0.00")))
        self._all_time_peak_equity = Decimal(str(state.get("all_time_peak_equity", "0.00")))
        if "limits" in state and isinstance(state["limits"], dict):
            lim_dict = state["limits"]
            self.limits = RiskLimits(
                limits_id=lim_dict.get("limits_id", self.limits.limits_id),
                max_position_weight=float(
                    lim_dict.get("max_position_weight", self.limits.max_position_weight)
                ),
                max_daily_drawdown_pct=float(
                    lim_dict.get("max_daily_drawdown_pct", self.limits.max_daily_drawdown_pct)
                ),
                max_total_drawdown_pct=float(
                    lim_dict.get("max_total_drawdown_pct", self.limits.max_total_drawdown_pct)
                ),
                max_portfolio_leverage=float(
                    lim_dict.get("max_portfolio_leverage", self.limits.max_portfolio_leverage)
                ),
                min_cash_buffer_pct=float(
                    lim_dict.get("min_cash_buffer_pct", self.limits.min_cash_buffer_pct)
                ),
                max_allowed_spread_pct=float(
                    lim_dict.get("max_allowed_spread_pct", self.limits.max_allowed_spread_pct)
                ),
                allow_naked_short=bool(
                    lim_dict.get("allow_naked_short", self.limits.allow_naked_short)
                ),
                max_order_value=Decimal(str(lim_dict["max_order_value"]))
                if lim_dict.get("max_order_value") is not None
                else None,
            )
        if "kill_events" in state and isinstance(state["kill_events"], list):
            self._kill_events = [
                KillSwitchEvent(
                    timestamp=datetime.fromisoformat(ev["timestamp"]),
                    reason=ev["reason"],
                    trigger_source=ev.get("trigger_source", "MANUAL"),
                    equity_at_halt=Decimal(str(ev["equity_at_halt"])),
                )
                for ev in state["kill_events"]
            ]

    def evaluate_order(
        self,
        order: Order,
        current_equity: Decimal,
        current_cash: Decimal,
        positions: Mapping[str, Position],
        current_quote: Quote | None,
    ) -> RiskDecision:
        """Deterministic pre-trade verification. Returns approved=True only if ALL limits pass."""
        self.update_peaks(current_equity)
        now = order.created_at

        # 1. Kill Switch Check
        if self._is_killed:
            return RiskDecision(
                approved=False,
                reason="KILL_SWITCH_ACTIVE",
                order_id=order.order_id,
                current_equity=current_equity,
                order_value=Decimal("0.00"),
                resulting_leverage=0.0,
                limits_id=self.limits.limits_id,
                decision_timestamp=now,
            )

        # 2. Daily Drawdown Limit Check
        daily_dd = 0.0
        if self._daily_peak_equity > Decimal("0"):
            daily_dd = float((self._daily_peak_equity - current_equity) / self._daily_peak_equity)
            if daily_dd >= self.limits.max_daily_drawdown_pct:
                self.trigger_kill_switch(
                    reason=f"DAILY_DRAWDOWN_LIMIT_BREACHED: {daily_dd:.2%} >= {self.limits.max_daily_drawdown_pct:.2%}",
                    trigger_source="AUTOMATIC_BREACH",
                    current_equity=current_equity,
                )
                return RiskDecision(
                    approved=False,
                    reason=f"DAILY_DRAWDOWN_LIMIT_BREACHED: {daily_dd:.2%} >= {self.limits.max_daily_drawdown_pct:.2%}",
                    order_id=order.order_id,
                    current_equity=current_equity,
                    order_value=Decimal("0.00"),
                    resulting_leverage=0.0,
                    limits_id=self.limits.limits_id,
                    decision_timestamp=now,
                    daily_drawdown_pct=daily_dd,
                )

        # 3. Trailing Max Drawdown Check
        total_dd = 0.0
        if self._all_time_peak_equity > Decimal("0"):
            total_dd = float(
                (self._all_time_peak_equity - current_equity) / self._all_time_peak_equity
            )
            if total_dd >= self.limits.max_total_drawdown_pct:
                self.trigger_kill_switch(
                    reason=f"TOTAL_MAX_DRAWDOWN_BREACHED: {total_dd:.2%} >= {self.limits.max_total_drawdown_pct:.2%}",
                    trigger_source="AUTOMATIC_BREACH",
                    current_equity=current_equity,
                )
                return RiskDecision(
                    approved=False,
                    reason=f"TOTAL_MAX_DRAWDOWN_BREACHED: {total_dd:.2%} >= {self.limits.max_total_drawdown_pct:.2%}",
                    order_id=order.order_id,
                    current_equity=current_equity,
                    order_value=Decimal("0.00"),
                    resulting_leverage=0.0,
                    limits_id=self.limits.limits_id,
                    decision_timestamp=now,
                    total_drawdown_pct=total_dd,
                )

        # Determine price to value the order
        est_price = order.limit_price
        if est_price is None and current_quote is not None:
            est_price = current_quote.ask if order.side == Side.BUY else current_quote.bid

        if est_price is None or est_price <= Decimal("0"):
            return RiskDecision(
                approved=False,
                reason="MISSING_PRICE_FOR_RISK_VALUATION",
                order_id=order.order_id,
                current_equity=current_equity,
                order_value=Decimal("0.00"),
                resulting_leverage=0.0,
                limits_id=self.limits.limits_id,
                decision_timestamp=now,
            )

        order_value = (est_price * Decimal(order.quantity)).quantize(_PAISA)

        # 4. Max Order Value Check
        if self.limits.max_order_value is not None and order_value > self.limits.max_order_value:
            return RiskDecision(
                approved=False,
                reason=f"MAX_ORDER_VALUE_EXCEEDED: {order_value} > {self.limits.max_order_value}",
                order_id=order.order_id,
                current_equity=current_equity,
                order_value=order_value,
                resulting_leverage=0.0,
                limits_id=self.limits.limits_id,
                decision_timestamp=now,
            )

        # 5. Bid-Ask Spread Check (Liquidity Gate)
        if current_quote is not None and current_quote.spread_pct > Decimal(
            str(self.limits.max_allowed_spread_pct)
        ):
            return RiskDecision(
                approved=False,
                reason=f"SPREAD_TOO_WIDE: {current_quote.spread_pct:.2%} > {self.limits.max_allowed_spread_pct:.2%}",
                order_id=order.order_id,
                current_equity=current_equity,
                order_value=order_value,
                resulting_leverage=0.0,
                limits_id=self.limits.limits_id,
                decision_timestamp=now,
            )

        # 6. Position Sizing & Concentration Check (for Buys)
        resulting_weight = 0.0
        if order.side == Side.BUY:
            current_pos_val = (
                positions[order.symbol].current_market_value(est_price)
                if order.symbol in positions
                else Decimal("0.00")
            )
            resulting_pos_val = current_pos_val + order_value
            if current_equity > Decimal("0"):
                resulting_weight = float(resulting_pos_val / current_equity)
                if resulting_weight > self.limits.max_position_weight:
                    return RiskDecision(
                        approved=False,
                        reason=f"POSITION_WEIGHT_LIMIT_EXCEEDED: {resulting_weight:.2%} > {self.limits.max_position_weight:.2%}",
                        order_id=order.order_id,
                        current_equity=current_equity,
                        order_value=order_value,
                        resulting_leverage=0.0,
                        limits_id=self.limits.limits_id,
                        decision_timestamp=now,
                        position_weight_pct=resulting_weight,
                    )

            # 7. Cash and Minimum Buffer Check
            min_cash_required = (
                current_equity * Decimal(str(self.limits.min_cash_buffer_pct))
            ).quantize(_PAISA)
            available_for_trade = current_cash - min_cash_required
            if order_value > available_for_trade:
                return RiskDecision(
                    approved=False,
                    reason=f"INSUFFICIENT_CASH: Need {order_value}, Available after buffer is {available_for_trade}",
                    order_id=order.order_id,
                    current_equity=current_equity,
                    order_value=order_value,
                    resulting_leverage=0.0,
                    limits_id=self.limits.limits_id,
                    decision_timestamp=now,
                )

        # 8. Short Sale / Naked Short Check
        if order.side == Side.SELL and not self.limits.allow_naked_short:
            current_held = positions[order.symbol].quantity if order.symbol in positions else 0
            if order.quantity > current_held:
                return RiskDecision(
                    approved=False,
                    reason=f"NAKED_SHORT_FORBIDDEN: Selling {order.quantity} but only hold {current_held}",
                    order_id=order.order_id,
                    current_equity=current_equity,
                    order_value=order_value,
                    resulting_leverage=0.0,
                    limits_id=self.limits.limits_id,
                    decision_timestamp=now,
                )

        # 9. Portfolio Leverage Check
        gross_pos_val = sum(
            abs(p.quantity) * (p.average_price if order.symbol != sym else est_price)
            for sym, p in positions.items()
        )
        if order.side == Side.BUY:
            resulting_gross = gross_pos_val + order_value
        else:
            resulting_gross = max(Decimal("0.00"), gross_pos_val - order_value)

        resulting_leverage = (
            float(resulting_gross / current_equity) if current_equity > Decimal("0") else 0.0
        )
        if resulting_leverage > self.limits.max_portfolio_leverage:
            return RiskDecision(
                approved=False,
                reason=f"LEVERAGE_LIMIT_EXCEEDED: {resulting_leverage:.2f} > {self.limits.max_portfolio_leverage:.2f}",
                order_id=order.order_id,
                current_equity=current_equity,
                order_value=order_value,
                resulting_leverage=resulting_leverage,
                limits_id=self.limits.limits_id,
                decision_timestamp=now,
            )

        return RiskDecision(
            approved=True,
            reason="RISK_APPROVED",
            order_id=order.order_id,
            current_equity=current_equity,
            order_value=order_value,
            resulting_leverage=resulting_leverage,
            limits_id=self.limits.limits_id,
            decision_timestamp=now,
            daily_drawdown_pct=daily_dd,
            total_drawdown_pct=total_dd,
            position_weight_pct=resulting_weight,
        )

    def evaluate_fill(
        self,
        fill: Fill,
        current_equity: Decimal,
        current_cash: Decimal,
        positions: Mapping[str, Position],
    ) -> RiskDecision:
        """Re-evaluates post-fill execution against leverage and cash constraints."""
        fill_val = (fill.price * Decimal(fill.quantity)).quantize(_PAISA)
        if self._is_killed:
            return RiskDecision(
                approved=False,
                reason="KILL_SWITCH_ACTIVE",
                order_id=fill.order_id,
                current_equity=current_equity,
                order_value=fill_val,
                resulting_leverage=0.0,
                limits_id=self.limits.limits_id,
                decision_timestamp=fill.timestamp,
            )

        if self.limits.max_order_value is not None and fill_val > self.limits.max_order_value:
            return RiskDecision(
                approved=False,
                reason=f"MAX_ORDER_VALUE_EXCEEDED: Rs {fill_val} > Rs {self.limits.max_order_value}",
                order_id=fill.order_id,
                current_equity=current_equity,
                order_value=fill_val,
                resulting_leverage=0.0,
                limits_id=self.limits.limits_id,
                decision_timestamp=fill.timestamp,
            )

        resulting_weight = 0.0
        if fill.side == Side.BUY:
            min_cash_required = (
                current_equity * Decimal(str(self.limits.min_cash_buffer_pct))
            ).quantize(_PAISA)
            if fill_val > (current_cash - min_cash_required + fill.gross_value):
                return RiskDecision(
                    approved=False,
                    reason=f"INSUFFICIENT_CASH_BUFFER: Need Rs {fill_val + min_cash_required}, available Rs {current_cash}",
                    order_id=fill.order_id,
                    current_equity=current_equity,
                    order_value=fill_val,
                    resulting_leverage=0.0,
                    limits_id=self.limits.limits_id,
                    decision_timestamp=fill.timestamp,
                )

            current_held = positions[fill.symbol].quantity if fill.symbol in positions else 0
            new_qty = current_held + fill.quantity
            pos_val = (Decimal(new_qty) * fill.price).quantize(_PAISA)
            resulting_weight = (
                float(pos_val / current_equity) if current_equity > Decimal("0") else 1.0
            )
            if resulting_weight > self.limits.max_position_weight:
                return RiskDecision(
                    approved=False,
                    reason=f"POSITION_WEIGHT_LIMIT_EXCEEDED: {resulting_weight:.2%} > {self.limits.max_position_weight:.2%}",
                    order_id=fill.order_id,
                    current_equity=current_equity,
                    order_value=fill_val,
                    resulting_leverage=0.0,
                    limits_id=self.limits.limits_id,
                    decision_timestamp=fill.timestamp,
                    position_weight_pct=resulting_weight,
                )

        gross_pos_val = sum(
            abs(p.quantity) * p.average_price for sym, p in positions.items() if sym != fill.symbol
        ) + (
            abs(
                (positions[fill.symbol].quantity if fill.symbol in positions else 0)
                + (fill.quantity if fill.side == Side.BUY else -fill.quantity)
            )
            * fill.price
        )
        resulting_leverage = (
            float(gross_pos_val / current_equity) if current_equity > Decimal("0") else 0.0
        )
        if resulting_leverage > self.limits.max_portfolio_leverage:
            return RiskDecision(
                approved=False,
                reason=f"LEVERAGE_LIMIT_EXCEEDED: {resulting_leverage:.2f} > {self.limits.max_portfolio_leverage:.2f}",
                order_id=fill.order_id,
                current_equity=current_equity,
                order_value=fill_val,
                resulting_leverage=resulting_leverage,
                limits_id=self.limits.limits_id,
                decision_timestamp=fill.timestamp,
            )

        return RiskDecision(
            approved=True,
            reason="FILL_VERIFIED",
            order_id=fill.order_id,
            current_equity=current_equity,
            order_value=fill_val,
            resulting_leverage=resulting_leverage,
            limits_id=self.limits.limits_id,
            decision_timestamp=fill.timestamp,
            position_weight_pct=resulting_weight,
        )
