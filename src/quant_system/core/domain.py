"""Immutable, typed financial domain models for the Quant System."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class InstrumentType(StrEnum):
    EQUITY = "EQUITY"
    OPTION_CALL = "OPTION_CALL"
    OPTION_PUT = "OPTION_PUT"
    FUTURE = "FUTURE"


@dataclass(frozen=True, slots=True)
class PriceBar:
    """Standard OHLCV bar representation with timestamp precision."""

    symbol: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    def __post_init__(self) -> None:
        if (
            self.open <= Decimal("0")
            or self.close <= Decimal("0")
            or self.high <= Decimal("0")
            or self.low <= Decimal("0")
        ):
            raise ValueError(f"OHLC prices must be strictly positive for {self.symbol}")
        if self.high < self.low:
            raise ValueError(
                f"High {self.high} cannot be less than Low {self.low} for {self.symbol}"
            )
        if self.high < self.open or self.high < self.close:
            raise ValueError(
                f"High {self.high} must be >= open ({self.open}) and close ({self.close}) for {self.symbol}"
            )
        if self.low > self.open or self.low > self.close:
            raise ValueError(
                f"Low {self.low} must be <= open ({self.open}) and close ({self.close}) for {self.symbol}"
            )
        if self.volume < 0:
            raise ValueError(f"Volume {self.volume} cannot be negative for {self.symbol}")


@dataclass(frozen=True, slots=True)
class Quote:
    """Best bid/ask quote for an instrument."""

    symbol: str
    timestamp: datetime
    bid: Decimal
    ask: Decimal
    bid_size: int = 0
    ask_size: int = 0
    last_price: Decimal | None = None

    def __post_init__(self) -> None:
        if self.bid < Decimal("0") or self.ask < Decimal("0"):
            raise ValueError(f"Quote bid and ask must be non-negative for {self.symbol}")
        if self.ask < self.bid:
            raise ValueError(
                f"Quote ask {self.ask} cannot be less than bid {self.bid} for {self.symbol}"
            )

    @property
    def mid_price(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> Decimal:
        if self.mid_price <= Decimal("0"):
            return Decimal("0")
        return self.spread / self.mid_price


@dataclass(frozen=True, slots=True)
class Signal:
    """Signal produced by a strategy or alpha factor."""

    symbol: str
    side: Side | None  # None indicates flat/exit
    strength: float  # Signal confidence in [0.0, 1.0] or continuous factor score
    timestamp: datetime
    strategy_name: str
    target_weight: float | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Order:
    """An execution order submitted to the paper broker or exchange."""

    order_id: str
    symbol: str
    side: Side
    quantity: int
    order_type: OrderType
    created_at: datetime
    limit_price: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING
    strategy_name: str = ""
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(
                f"Order quantity must be positive, got {self.quantity} for {self.symbol}"
            )


@dataclass(frozen=True, slots=True)
class Fill:
    """Executed trade fill with exact fee and price."""

    fill_id: str
    order_id: str
    symbol: str
    side: Side
    quantity: int
    price: Decimal
    fee: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(
                f"Fill quantity must be positive, got {self.quantity} for {self.symbol}"
            )
        if self.price <= Decimal("0"):
            raise ValueError(
                f"Fill price must be strictly positive, got {self.price} for {self.symbol}"
            )
        if self.fee < Decimal("0"):
            raise ValueError(f"Fill fee cannot be negative, got {self.fee} for {self.symbol}")

    @property
    def gross_value(self) -> Decimal:
        return self.price * Decimal(self.quantity)

    @property
    def net_cash_delta(self) -> Decimal:
        """Cash impact: negative when buying (outflow), positive when selling (inflow minus fees)."""
        if self.side == Side.BUY:
            return -(self.gross_value + self.fee)
        return self.gross_value - self.fee


@dataclass(frozen=True, slots=True)
class Position:
    """Current open position in an instrument."""

    symbol: str
    quantity: int
    average_price: Decimal
    realized_pnl: Decimal = Decimal("0.00")

    def current_market_value(self, current_price: Decimal) -> Decimal:
        return current_price * Decimal(self.quantity)

    def unrealized_pnl(self, current_price: Decimal) -> Decimal:
        return (current_price - self.average_price) * Decimal(self.quantity)


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Point-in-time snapshot of the entire portfolio state."""

    timestamp: datetime
    cash: Decimal
    positions: Mapping[str, Position]
    total_market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal

    @property
    def total_equity(self) -> Decimal:
        return self.cash + self.total_market_value
