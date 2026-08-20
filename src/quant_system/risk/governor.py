"""Deterministic Pre-Trade Risk Governor protecting against fat-tails, excessive sizing, and drawdown."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from quant_system.core.domain import Order, Position, Quote, Side
from quant_system.risk.checks import RiskDecision, RiskLimits


class PreTradeRiskGovernor:
    """Evaluates proposed orders against strict capital, leverage, drawdown, and spread rules."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits: RiskLimits = limits or RiskLimits()
        self._is_killed: bool = False
        self._daily_peak_equity: Decimal = Decimal("0")
        self._all_time_peak_equity: Decimal = Decimal("0")

    @property
    def is_killed(self) -> bool:
        return self._is_killed

    def trigger_kill_switch(self, reason: str = "MANUAL_HALT") -> None:
        """Instantly halts all new risk taking across the entire system."""
        self._is_killed = True

    def reset_kill_switch(self) -> None:
        self._is_killed = False

    def update_peaks(self, current_equity: Decimal) -> None:
        if current_equity > self._daily_peak_equity:
            self._daily_peak_equity = current_equity
        if current_equity > self._all_time_peak_equity:
            self._all_time_peak_equity = current_equity

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

        # 1. Kill Switch Check
        if self._is_killed:
            return RiskDecision(
                approved=False,
                reason="KILL_SWITCH_ACTIVE",
                order_id=order.order_id,
                current_equity=current_equity,
                order_value=Decimal("0"),
                resulting_leverage=0.0,
            )

        # 2. Daily Drawdown Limit Check
        if self._daily_peak_equity > Decimal("0"):
            daily_dd = float((self._daily_peak_equity - current_equity) / self._daily_peak_equity)
            if daily_dd >= self.limits.max_daily_drawdown_pct:
                self._is_killed = True
                return RiskDecision(
                    approved=False,
                    reason=f"DAILY_DRAWDOWN_LIMIT_BREACHED: {daily_dd:.2%} >= {self.limits.max_daily_drawdown_pct:.2%}",
                    order_id=order.order_id,
                    current_equity=current_equity,
                    order_value=Decimal("0"),
                    resulting_leverage=0.0,
                )

        # 3. Trailing Max Drawdown Check
        if self._all_time_peak_equity > Decimal("0"):
            total_dd = float(
                (self._all_time_peak_equity - current_equity) / self._all_time_peak_equity
            )
            if total_dd >= self.limits.max_total_drawdown_pct:
                self._is_killed = True
                return RiskDecision(
                    approved=False,
                    reason=f"TOTAL_MAX_DRAWDOWN_BREACHED: {total_dd:.2%} >= {self.limits.max_total_drawdown_pct:.2%}",
                    order_id=order.order_id,
                    current_equity=current_equity,
                    order_value=Decimal("0"),
                    resulting_leverage=0.0,
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
                order_value=Decimal("0"),
                resulting_leverage=0.0,
            )

        order_value = est_price * Decimal(order.quantity)

        # 4. Bid-Ask Spread Check (Liquidity Gate)
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
            )

        # 5. Position Sizing & Concentration Check (for Buys)
        if order.side == Side.BUY:
            current_pos_val = (
                positions[order.symbol].current_market_value(est_price)
                if order.symbol in positions
                else Decimal("0")
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
                    )

            # 6. Cash and Minimum Buffer Check
            min_cash_required = current_equity * Decimal(str(self.limits.min_cash_buffer_pct))
            available_for_trade = current_cash - min_cash_required
            if order_value > available_for_trade:
                return RiskDecision(
                    approved=False,
                    reason=f"INSUFFICIENT_CASH: Need {order_value}, Available after buffer is {available_for_trade}",
                    order_id=order.order_id,
                    current_equity=current_equity,
                    order_value=order_value,
                    resulting_leverage=0.0,
                )

        # 7. Short Sale / Naked Short Check
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
                )

        return RiskDecision(
            approved=True,
            reason="RISK_APPROVED",
            order_id=order.order_id,
            current_equity=current_equity,
            order_value=order_value,
            resulting_leverage=1.0,
        )
