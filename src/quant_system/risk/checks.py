"""Risk parameters, decision objects, and policy limits."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Immutable pre-trade limits enforced on all outgoing orders and fills."""

    limits_id: str = "DEFAULT_LIMITS_V1"
    max_position_weight: float = 0.25  # 25% max in one stock
    max_daily_drawdown_pct: float = 0.03  # 3% max daily loss
    max_total_drawdown_pct: float = 0.10  # 10% max trailing drawdown
    max_portfolio_leverage: float = 1.0  # 1.0 = cash only
    min_cash_buffer_pct: float = 0.05  # 5% cash buffer
    max_allowed_spread_pct: float = 0.02  # 2% max spread
    allow_naked_short: bool = False
    max_order_value: Decimal | None = None
    limits_hash: str = ""

    def __post_init__(self) -> None:
        if self.max_position_weight <= 0.0 or self.max_position_weight > 1.0:
            raise ValueError(
                f"max_position_weight must be in (0, 1], got {self.max_position_weight}"
            )
        if self.max_daily_drawdown_pct <= 0.0 or self.max_daily_drawdown_pct > 1.0:
            raise ValueError(
                f"max_daily_drawdown_pct must be in (0, 1], got {self.max_daily_drawdown_pct}"
            )
        if self.max_total_drawdown_pct <= 0.0 or self.max_total_drawdown_pct > 1.0:
            raise ValueError(
                f"max_total_drawdown_pct must be in (0, 1], got {self.max_total_drawdown_pct}"
            )
        if self.min_cash_buffer_pct < 0.0 or self.min_cash_buffer_pct >= 1.0:
            raise ValueError(
                f"min_cash_buffer_pct must be in [0, 1), got {self.min_cash_buffer_pct}"
            )

        if not self.limits_hash:
            payload = {
                "limits_id": self.limits_id,
                "max_position_weight": str(self.max_position_weight),
                "max_daily_drawdown_pct": str(self.max_daily_drawdown_pct),
                "max_total_drawdown_pct": str(self.max_total_drawdown_pct),
                "max_portfolio_leverage": str(self.max_portfolio_leverage),
                "min_cash_buffer_pct": str(self.min_cash_buffer_pct),
                "max_allowed_spread_pct": str(self.max_allowed_spread_pct),
                "allow_naked_short": self.allow_naked_short,
                "max_order_value": str(self.max_order_value)
                if self.max_order_value is not None
                else None,
            }
            computed = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            object.__setattr__(self, "limits_hash", computed)


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Immutable pre-trade and post-fill evaluation verdict."""

    approved: bool
    reason: str
    order_id: str
    current_equity: Decimal
    order_value: Decimal
    resulting_leverage: float
    limits_id: str = "DEFAULT_LIMITS_V1"
    decision_timestamp: datetime | None = None
    daily_drawdown_pct: float = 0.0
    total_drawdown_pct: float = 0.0
    position_weight_pct: float = 0.0
    decision_hash: str = ""

    def __post_init__(self) -> None:
        if not self.decision_hash:
            payload = {
                "approved": self.approved,
                "reason": self.reason,
                "order_id": self.order_id,
                "current_equity": str(self.current_equity),
                "order_value": str(self.order_value),
                "resulting_leverage": str(self.resulting_leverage),
                "limits_id": self.limits_id,
                "decision_timestamp": self.decision_timestamp.isoformat()
                if self.decision_timestamp
                else None,
                "daily_drawdown_pct": str(self.daily_drawdown_pct),
                "total_drawdown_pct": str(self.total_drawdown_pct),
                "position_weight_pct": str(self.position_weight_pct),
            }
            computed = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            object.__setattr__(self, "decision_hash", computed)


@dataclass(frozen=True, slots=True)
class KillSwitchEvent:
    """Immutable audit record of a risk governor kill-switch activation."""

    timestamp: datetime
    reason: str
    trigger_source: str  # MANUAL or AUTOMATIC_BREACH
    equity_at_halt: Decimal
