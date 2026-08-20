"""Position sizing algorithms: Volatility Parity, Kelly Criterion, Fixed Risk %."""

from __future__ import annotations

from decimal import Decimal


class PositionSizer:
    """Calculates optimal share/contract quantities subject to risk budgets."""

    @staticmethod
    def fixed_fractional(
        portfolio_equity: Decimal,
        target_weight: float,
        price: Decimal,
    ) -> int:
        """Sizes position as a fixed fraction of total portfolio equity."""
        if price <= Decimal("0") or target_weight <= 0:
            return 0
        allocated_cash = portfolio_equity * Decimal(str(target_weight))
        qty = int(allocated_cash / price)
        return max(0, qty)

    @staticmethod
    def volatility_parity(
        portfolio_equity: Decimal,
        asset_volatility: float,
        target_risk_budget: float,
        price: Decimal,
    ) -> int:
        """Sizes position inversely proportional to asset volatility to maintain constant risk contribution."""
        if asset_volatility <= 1e-6 or price <= Decimal("0"):
            return 0
        # Weight = target_risk / asset_volatility
        raw_weight = target_risk_budget / asset_volatility
        clamped_weight = min(0.30, max(0.01, raw_weight))  # Cap at 30% max position
        allocated_cash = portfolio_equity * Decimal(str(clamped_weight))
        return max(0, int(allocated_cash / price))

    @staticmethod
    def atr_risk_budget(
        portfolio_equity: Decimal,
        atr: float,
        risk_per_trade_pct: float,
        price: Decimal,
        atr_multiplier: float = 2.0,
    ) -> int:
        """Sizes quantity such that a stop-loss at N * ATR risks exactly risk_per_trade_pct of total equity."""
        if atr <= 1e-6 or price <= Decimal("0") or risk_per_trade_pct <= 0:
            return 0

        risk_amount = portfolio_equity * Decimal(str(risk_per_trade_pct))
        stop_distance = Decimal(str(atr * atr_multiplier))

        if stop_distance <= Decimal("0"):
            return 0

        qty = int(risk_amount / stop_distance)
        # Cap total position value to not exceed available equity
        max_affordable = int(portfolio_equity / price)
        return max(0, min(qty, max_affordable))

    @staticmethod
    def kelly_criterion(
        win_rate: float,
        win_loss_ratio: float,
        fraction: float = 0.5,  # Half-Kelly for conservatism
    ) -> float:
        """Computes optimal continuous Kelly capital allocation fraction."""
        if win_loss_ratio <= 0:
            return 0.0
        q = 1.0 - win_rate
        f_star = (win_rate * win_loss_ratio - q) / win_loss_ratio
        return max(0.0, min(1.0, f_star * fraction))
