"""High-fidelity Top-of-Book and L2 Orderbook execution simulator.

Provides realistic quote validation, conservative adverse slippage, queue priority
delay, partial fill allocation against displayed depth, and spread cost deduction.
Conforms strictly to QuantOS financial-model-craft and nse-execution-craft standards.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_UP, Decimal

from quant_system.core.domain import (
    Order,
    OrderStatus,
    OrderType,
    Quote,
    Side,
)

_PAISA = Decimal("0.01")
_DEFAULT_TICK_SIZE = Decimal("0.05")


@dataclass(frozen=True, slots=True)
class DepthLevel:
    """Represents a single price level in the market depth."""

    price: Decimal
    quantity: int
    orders_count: int = 1

    def __post_init__(self) -> None:
        if self.price <= Decimal("0"):
            raise ValueError(f"Depth price must be positive, got {self.price}")
        if self.quantity <= 0:
            raise ValueError(f"Depth quantity must be positive, got {self.quantity}")
        if self.orders_count < 0:
            raise ValueError(f"Orders count cannot be negative, got {self.orders_count}")


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    """Full L2 market depth snapshot containing ordered bid and ask books."""

    symbol: str
    timestamp: datetime
    bids: tuple[DepthLevel, ...] = ()  # Sorted descending by price
    asks: tuple[DepthLevel, ...] = ()  # Sorted ascending by price
    last_price: Decimal | None = None

    def __post_init__(self) -> None:
        # Validate bid order (descending)
        for i in range(len(self.bids) - 1):
            if self.bids[i].price < self.bids[i + 1].price:
                raise ValueError(
                    f"Bids must be sorted descending by price: {self.bids[i].price} < {self.bids[i + 1].price}"
                )
        # Validate ask order (ascending)
        for i in range(len(self.asks) - 1):
            if self.asks[i].price > self.asks[i + 1].price:
                raise ValueError(
                    f"Asks must be sorted ascending by price: {self.asks[i].price} > {self.asks[i + 1].price}"
                )

    @classmethod
    def from_quote(cls, quote: Quote) -> OrderBookSnapshot:
        """Constructs an OrderBookSnapshot from a top-of-book Quote."""
        bids: list[DepthLevel] = []
        asks: list[DepthLevel] = []

        if quote.bid > Decimal("0") and quote.bid_size > 0:
            bids.append(DepthLevel(price=quote.bid, quantity=quote.bid_size))
        if quote.ask > Decimal("0") and quote.ask_size > 0:
            asks.append(DepthLevel(price=quote.ask, quantity=quote.ask_size))

        return cls(
            symbol=quote.symbol,
            timestamp=quote.timestamp,
            bids=tuple(bids),
            asks=tuple(asks),
            last_price=quote.last_price,
        )

    @classmethod
    def from_levels(
        cls,
        symbol: str,
        timestamp: datetime,
        bids: Sequence[tuple[Decimal | str, int]],
        asks: Sequence[tuple[Decimal | str, int]],
        last_price: Decimal | str | None = None,
    ) -> OrderBookSnapshot:
        """Constructs an OrderBookSnapshot from sequence of (price, quantity) pairs."""
        bid_levels = tuple(DepthLevel(price=Decimal(str(p)), quantity=q) for p, q in bids if q > 0)
        ask_levels = tuple(DepthLevel(price=Decimal(str(p)), quantity=q) for p, q in asks if q > 0)
        lp = Decimal(str(last_price)) if last_price is not None else None
        return cls(
            symbol=symbol,
            timestamp=timestamp,
            bids=bid_levels,
            asks=ask_levels,
            last_price=lp,
        )

    @property
    def top_bid(self) -> DepthLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def top_ask(self) -> DepthLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def best_bid_price(self) -> Decimal | None:
        return self.top_bid.price if self.top_bid else None

    @property
    def best_ask_price(self) -> Decimal | None:
        return self.top_ask.price if self.top_ask else None

    @property
    def spread(self) -> Decimal | None:
        if self.best_ask_price is not None and self.best_bid_price is not None:
            return self.best_ask_price - self.best_bid_price
        return None

    @property
    def spread_pct(self) -> Decimal | None:
        if self.mid_price is not None and self.mid_price > Decimal("0") and self.spread is not None:
            return self.spread / self.mid_price
        return None

    @property
    def mid_price(self) -> Decimal | None:
        if self.best_ask_price is not None and self.best_bid_price is not None:
            return (self.best_ask_price + self.best_bid_price) / Decimal("2")
        return self.last_price

    @property
    def total_bid_depth(self) -> int:
        return sum(level.quantity for level in self.bids)

    @property
    def total_ask_depth(self) -> int:
        return sum(level.quantity for level in self.asks)

    @property
    def is_crossed(self) -> bool:
        if self.best_bid_price is not None and self.best_ask_price is not None:
            return self.best_bid_price > self.best_ask_price
        return False

    @property
    def is_locked(self) -> bool:
        if self.best_bid_price is not None and self.best_ask_price is not None:
            return self.best_bid_price == self.best_ask_price
        return False


@dataclass(frozen=True, slots=True)
class FillAllocation:
    """Granular allocation of an order against a single depth level."""

    level_index: int
    book_price: Decimal
    matched_quantity: int
    slippage_per_unit: Decimal
    effective_price: Decimal
    gross_value: Decimal


@dataclass(frozen=True, slots=True)
class FillSimulationResult:
    """Result of attempting to simulate execution against the orderbook."""

    is_executable: bool
    status: OrderStatus
    rejection_reason: str | None = None
    filled_quantity: int = 0
    unfilled_quantity: int = 0
    vwap_price: Decimal = Decimal("0.00")
    total_slippage: Decimal = Decimal("0.00")
    effective_spread: Decimal = Decimal("0.00")
    allocations: tuple[FillAllocation, ...] = ()
    quote_timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class OrderBookSimConfig:
    """Configuration governing realistic fill simulation and adverse friction."""

    slippage_bps: Decimal = Decimal("5.0")  # 5 basis points adverse slippage
    conservative_adverse_slippage: bool = True
    max_spread_pct: Decimal = Decimal("0.02")  # 2.0% maximum allowed spread
    max_quote_age_seconds: float = 5.0  # Max 5 seconds quote age (AC-62)
    tick_size: Decimal = _DEFAULT_TICK_SIZE  # ₹0.05 default tick size
    lot_size: int = 1  # 1 for cash equity, contract specific for derivatives
    allow_depth_walking: bool = True  # Walk across multi-level L2 depth
    queue_priority_fraction: Decimal = Decimal(
        "1.0"
    )  # Fraction of level executable (queue simulation)


class OrderBookSimulator:
    """Deterministic orderbook execution simulator with market depth matching and adverse friction."""

    def __init__(self, config: OrderBookSimConfig | None = None) -> None:
        self.config: OrderBookSimConfig = config or OrderBookSimConfig()

    def validate_quote(
        self,
        order: Order,
        book: OrderBookSnapshot,
        current_time: datetime | None = None,
    ) -> str | None:
        """Validates market data against exchange rules and returns typed rejection reason if invalid."""
        # 1. Point-in-time invariant: quote must be strictly later than order creation (AC-62)
        if book.timestamp <= order.created_at:
            return "QUOTE_NOT_LATER_THAN_ORDER_CREATION"

        # 2. Quote freshness / staleness check (AC-62, AC-65)
        eval_time = current_time or book.timestamp
        quote_age = (eval_time - book.timestamp).total_seconds()
        if quote_age > self.config.max_quote_age_seconds:
            return f"STALE_QUOTE_AGE_{quote_age:.1f}S_EXCEEDS_{self.config.max_quote_age_seconds}S"

        # 3. Lot size check (AC-65)
        if self.config.lot_size > 1 and (order.quantity % self.config.lot_size != 0):
            return f"INVALID_LOT_SIZE: quantity {order.quantity} not multiple of lot {self.config.lot_size}"

        # 4. Tick size check for limit orders (AC-65)
        if order.limit_price is not None:
            remainder = (order.limit_price / self.config.tick_size) % Decimal("1")
            if remainder != Decimal("0"):
                return f"INVALID_TICK_SIZE: limit price {order.limit_price} not on tick {self.config.tick_size}"

        # 5. Crossed book check (AC-65)
        if book.is_crossed:
            return f"CROSSED_BOOK: best_bid {book.best_bid_price} > best_ask {book.best_ask_price}"

        # 6. Locked book check with zero liquidity (AC-65)
        if book.is_locked:
            top_bid_qty = book.top_bid.quantity if book.top_bid else 0
            top_ask_qty = book.top_ask.quantity if book.top_ask else 0
            if top_bid_qty == 0 or top_ask_qty == 0:
                return "LOCKED_BOOK_ZERO_QUANTITY"

        # 7. Spread check (AC-65)
        if book.spread_pct is not None and book.spread_pct > self.config.max_spread_pct:
            return f"SPREAD_TOO_WIDE: {book.spread_pct:.4f} > max {self.config.max_spread_pct:.4f}"

        # 8. Liquidity availability check (AC-65)
        if order.side == Side.BUY:
            if not book.asks or book.total_ask_depth == 0:
                return "ZERO_LIQUIDITY_ASK_DEPTH_EMPTY"
        else:
            if not book.bids or book.total_bid_depth == 0:
                return "ZERO_LIQUIDITY_BID_DEPTH_EMPTY"

        return None

    def simulate_fill(
        self,
        order: Order,
        book: OrderBookSnapshot,
        current_time: datetime | None = None,
        remaining_quantity: int | None = None,
    ) -> FillSimulationResult:
        """Simulates realistic fill against displayed market depth with conservative adverse slippage."""
        qty_to_fill = remaining_quantity if remaining_quantity is not None else order.quantity

        if qty_to_fill <= 0:
            return FillSimulationResult(
                is_executable=False,
                status=OrderStatus.FILLED,
                rejection_reason="ORDER_ALREADY_COMPLETED",
                filled_quantity=0,
                unfilled_quantity=0,
                quote_timestamp=book.timestamp,
            )

        # Pre-execution quote validation
        rejection_reason = self.validate_quote(order, book, current_time)
        if rejection_reason is not None:
            # If quote is not yet later than order, order remains pending (not rejected)
            if rejection_reason == "QUOTE_NOT_LATER_THAN_ORDER_CREATION":
                return FillSimulationResult(
                    is_executable=False,
                    status=order.status,
                    rejection_reason=rejection_reason,
                    filled_quantity=0,
                    unfilled_quantity=qty_to_fill,
                    quote_timestamp=book.timestamp,
                )
            # True market violation -> mark rejected
            return FillSimulationResult(
                is_executable=False,
                status=OrderStatus.REJECTED,
                rejection_reason=rejection_reason,
                filled_quantity=0,
                unfilled_quantity=qty_to_fill,
                quote_timestamp=book.timestamp,
            )

        allocations: list[FillAllocation] = []
        unallocated_qty = qty_to_fill

        if order.side == Side.BUY:
            # Match against ASKS in ascending price order
            for idx, level in enumerate(book.asks):
                if unallocated_qty <= 0:
                    break

                # Limit order price gating
                if order.order_type == OrderType.LIMIT and order.limit_price is not None:
                    if level.price > order.limit_price:
                        # Cannot match at or above this level
                        break

                # Queue priority fraction of displayed level quantity
                available_level_qty = int(
                    Decimal(str(level.quantity)) * self.config.queue_priority_fraction
                )
                if available_level_qty <= 0:
                    continue

                matched_qty = min(unallocated_qty, available_level_qty)

                # Conservative adverse slippage: BUY fills higher than displayed ask
                slippage_per_unit = (
                    level.price * (self.config.slippage_bps / Decimal("10000.0"))
                ).quantize(_PAISA, rounding=ROUND_UP)

                effective_price = (level.price + slippage_per_unit).quantize(_PAISA)
                if order.order_type == OrderType.LIMIT and order.limit_price is not None:
                    effective_price = min(order.limit_price, effective_price)
                gross_val = effective_price * Decimal(matched_qty)

                allocations.append(
                    FillAllocation(
                        level_index=idx,
                        book_price=level.price,
                        matched_quantity=matched_qty,
                        slippage_per_unit=slippage_per_unit,
                        effective_price=effective_price,
                        gross_value=gross_val,
                    )
                )
                unallocated_qty -= matched_qty

                if not self.config.allow_depth_walking:
                    break

        else:  # Side.SELL
            # Match against BIDS in descending price order
            for idx, level in enumerate(book.bids):
                if unallocated_qty <= 0:
                    break

                # Limit order price gating
                if order.order_type == OrderType.LIMIT and order.limit_price is not None:
                    if level.price < order.limit_price:
                        # Cannot match at or below this level
                        break

                # Queue priority fraction of displayed level quantity
                available_level_qty = int(
                    Decimal(str(level.quantity)) * self.config.queue_priority_fraction
                )
                if available_level_qty <= 0:
                    continue

                matched_qty = min(unallocated_qty, available_level_qty)

                # Conservative adverse slippage: SELL fills lower than displayed bid
                slippage_per_unit = (
                    level.price * (self.config.slippage_bps / Decimal("10000.0"))
                ).quantize(_PAISA, rounding=ROUND_UP)

                effective_price = max(_PAISA, (level.price - slippage_per_unit).quantize(_PAISA))
                if order.order_type == OrderType.LIMIT and order.limit_price is not None:
                    effective_price = max(order.limit_price, effective_price)
                gross_val = effective_price * Decimal(matched_qty)

                allocations.append(
                    FillAllocation(
                        level_index=idx,
                        book_price=level.price,
                        matched_quantity=matched_qty,
                        slippage_per_unit=slippage_per_unit,
                        effective_price=effective_price,
                        gross_value=gross_val,
                    )
                )
                unallocated_qty -= matched_qty

                if not self.config.allow_depth_walking:
                    break

        total_filled = sum(a.matched_quantity for a in allocations)

        if total_filled == 0:
            # Order could not match at all (e.g. limit price not crossed or zero executable depth)
            return FillSimulationResult(
                is_executable=False,
                status=order.status,
                rejection_reason="LIMIT_PRICE_NOT_MET_OR_ZERO_DEPTH",
                filled_quantity=0,
                unfilled_quantity=qty_to_fill,
                quote_timestamp=book.timestamp,
            )

        # VWAP calculation across filled levels
        total_gross = sum(a.gross_value for a in allocations)
        vwap_price = (total_gross / Decimal(total_filled)).quantize(_PAISA)
        total_slippage = sum(
            (a.slippage_per_unit * Decimal(a.matched_quantity) for a in allocations),
            Decimal("0.00"),
        )
        effective_spread = book.spread if book.spread is not None else Decimal("0.00")

        # Determine resulting status
        if unallocated_qty == 0:
            new_status = OrderStatus.FILLED
        else:
            new_status = OrderStatus.PARTIALLY_FILLED

        return FillSimulationResult(
            is_executable=True,
            status=new_status,
            rejection_reason=None,
            filled_quantity=total_filled,
            unfilled_quantity=unallocated_qty,
            vwap_price=vwap_price,
            total_slippage=total_slippage,
            effective_spread=effective_spread,
            allocations=tuple(allocations),
            quote_timestamp=book.timestamp,
        )
