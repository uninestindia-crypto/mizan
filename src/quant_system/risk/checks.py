"""Risk parameters, decision objects, and policy limits."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Pre-trade limits enforced on all outgoing orders."""

    max_position_weight: float = 0.25  # 25% max in one stock
    max_daily_drawdown_pct: float = 0.03  # 3% max daily loss
    max_total_drawdown_pct: float = 0.10  # 10% max trailing drawdown
    max_portfolio_leverage: float = 1.0  # 1.0 = cash only
    min_cash_buffer_pct: float = 0.05  # 5% cash buffer
    max_allowed_spread_pct: float = 0.02  # 2% max spread
    allow_naked_short: bool = False


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Decision output from the pre-trade risk evaluation."""

    approved: bool
    reason: str
    order_id: str
    current_equity: Decimal
    order_value: Decimal
    resulting_leverage: float
