"""Event loop for lab backtests.

Semantics match :class:`quant_system.backtest.engine.BacktestEngine` (see the parity test):

1. Orders created at session ``t`` close execute at the next session where the symbol has a bar,
   at that session's **open**, with slippage built into the fill price.
2. Fees are charged by a date-aware function and booked through :class:`DecimalLedger`.
3. The portfolio is marked to market at each close.
4. The strategy decides at the close; its targets become orders for the next open.

Differences, each deliberate: sells execute before buys in the same session; a buy that no longer
fits the cash (the open gapped up) is shrunk rather than dropped; buys keep a small cash buffer; a
held symbol without a bar is marked at its last close rather than its average cost.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from quant_system.core.domain import Fill, Position, Side
from quant_system.core.ledger import DecimalLedger
from quant_system.lab.strategies import LabStrategy, Panel, Targets

FeeFn = Callable[[Side, int, Decimal, date], Decimal]

_PAISA = Decimal("0.01")
_IST = timezone(timedelta(hours=5, minutes=30))
_MARKET_OPEN = time(9, 15)


@dataclass(frozen=True, slots=True)
class SimConfig:
    capital: Decimal
    slippage_bps: Decimal = Decimal("5")
    cash_buffer: Decimal = Decimal("0.005")

    def __post_init__(self) -> None:
        if self.capital <= 0:
            raise ValueError("Capital must be positive")
        if not Decimal("0") <= self.slippage_bps <= Decimal("200"):
            raise ValueError("Slippage must be between 0 and 200 basis points")
        if not Decimal("0") <= self.cash_buffer < Decimal("0.5"):
            raise ValueError("Cash buffer must be between 0 and 0.5")


@dataclass(frozen=True, slots=True)
class FillRecord:
    date: str
    symbol: str
    side: str
    quantity: int
    price: Decimal
    fee: Decimal
    slippage: Decimal


@dataclass(frozen=True, slots=True)
class RoundTrip:
    symbol: str
    entry_date: str
    exit_date: str
    quantity: int
    entry_price: Decimal
    exit_price: Decimal
    pnl: Decimal
    return_pct: float
    sessions: int


@dataclass(frozen=True, slots=True)
class OpenPosition:
    symbol: str
    quantity: int
    average_price: Decimal
    last_close: Decimal
    unrealized_pnl: Decimal


@dataclass(slots=True)
class SimResult:
    dates: list[str] = field(default_factory=list)
    equity: list[Decimal] = field(default_factory=list)
    invested: list[Decimal] = field(default_factory=list)
    fills: list[FillRecord] = field(default_factory=list)
    round_trips: list[RoundTrip] = field(default_factory=list)
    open_positions: list[OpenPosition] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def charges(self) -> Decimal:
        return sum((f.fee for f in self.fills), Decimal("0.00"))

    @property
    def slippage(self) -> Decimal:
        return sum((f.slippage for f in self.fills), Decimal("0.00"))


@dataclass(slots=True)
class _Order:
    symbol: str
    side: Side
    quantity: int


@dataclass(slots=True)
class _Lot:
    date: str
    session: int
    quantity: int
    price: Decimal
    fee: Decimal


def to_decimal(value: float) -> Decimal:
    """Exact decimal for a stored price: ``repr`` round-trips the provider's decimal string."""
    return Decimal(repr(float(value)))


def simulate(
    panel: Panel,
    strategy: LabStrategy,
    first_trade: int,
    fee_fn: FeeFn,
    config: SimConfig,
) -> SimResult:
    if not 0 <= first_trade < len(panel.dates):
        raise ValueError("The first trading session is outside the price data")
    strategy.prepare(panel)
    ledger = DecimalLedger(initial_cash=config.capital)
    slip = config.slippage_bps / Decimal("10000")
    result = SimResult()
    pending: list[_Order] = []
    last_close: dict[str, Decimal] = {}
    lots: dict[str, list[_Lot]] = {}
    last_index = len(panel.dates) - 1
    sequence = 0

    for t in range(first_trade, len(panel.dates)):
        day = panel.dates[t]
        trade_date = date.fromisoformat(day)
        stamp = datetime.combine(trade_date, _MARKET_OPEN, tzinfo=_IST)

        # 1. Execute pending orders at this session's open (sells first).
        if pending:
            remaining: list[_Order] = []
            for order in sorted(pending, key=lambda o: 0 if o.side == Side.SELL else 1):
                open_price = panel.open[order.symbol][t]
                if math.isnan(open_price):
                    remaining.append(order)
                    continue
                sequence += 1
                _execute(
                    order,
                    to_decimal(open_price),
                    slip,
                    trade_date,
                    stamp,
                    day,
                    t,
                    sequence,
                    fee_fn,
                    ledger,
                    lots,
                    result,
                )
            pending = remaining

        # 2. Mark to market at the close.
        positions = ledger.positions
        invested = Decimal("0.00")
        for symbol, position in positions.items():
            close = panel.close[symbol][t]
            if not math.isnan(close):
                last_close[symbol] = to_decimal(close)
            mark = last_close.get(symbol, position.average_price)
            invested += mark * Decimal(position.quantity)
        equity = ledger.cash + invested
        result.dates.append(day)
        result.equity.append(equity)
        result.invested.append(invested)

        # 3. Decide at the close; targets become orders for the next open.
        if t < last_index:
            held = frozenset(s for s, p in positions.items() if p.quantity > 0)
            targets = strategy.decide(t, held)
            if targets is not None:
                pending = _orders_for(
                    targets, positions, equity, panel, t, last_close, config, result
                )

    for symbol, position in ledger.positions.items():
        if position.quantity <= 0:
            continue
        mark = last_close.get(symbol, position.average_price)
        result.open_positions.append(
            OpenPosition(
                symbol=symbol,
                quantity=position.quantity,
                average_price=position.average_price,
                last_close=mark,
                unrealized_pnl=(
                    (mark - position.average_price) * Decimal(position.quantity)
                ).quantize(_PAISA),
            )
        )
    return result


def _orders_for(
    targets: Targets,
    positions: Mapping[str, Position],
    equity: Decimal,
    panel: Panel,
    t: int,
    last_close: dict[str, Decimal],
    config: SimConfig,
    result: SimResult,
) -> list[_Order]:
    held = {s: p.quantity for s, p in positions.items() if p.quantity > 0}
    orders = [
        _Order(symbol, Side.SELL, quantity)
        for symbol, quantity in sorted(held.items())
        if symbol not in targets
    ]
    budget_factor = Decimal("1") - config.cash_buffer
    for symbol, weight in sorted(targets.items()):
        if symbol in held or weight <= 0:
            continue
        close = panel.close[symbol][t]
        reference = to_decimal(close) if not math.isnan(close) else last_close.get(symbol)
        if reference is None or reference <= 0:
            result.skipped.append(f"{panel.dates[t]} {symbol}: no price to size the order")
            continue
        value = equity * Decimal(repr(weight)) * budget_factor
        quantity = int((value / reference).to_integral_value(rounding=ROUND_DOWN))
        if quantity > 0:
            orders.append(_Order(symbol, Side.BUY, quantity))
    return orders


def _execute(
    order: _Order,
    open_price: Decimal,
    slip: Decimal,
    trade_date: date,
    stamp: datetime,
    day: str,
    session: int,
    sequence: int,
    fee_fn: FeeFn,
    ledger: DecimalLedger,
    lots: dict[str, list[_Lot]],
    result: SimResult,
) -> bool:
    if order.side == Side.SELL:
        position = ledger.positions.get(order.symbol)
        quantity = min(order.quantity, position.quantity if position else 0)
        if quantity <= 0:
            return False
        price = (open_price * (Decimal("1") - slip)).quantize(_PAISA, rounding=ROUND_HALF_UP)
    else:
        quantity = order.quantity
        price = (open_price * (Decimal("1") + slip)).quantize(_PAISA, rounding=ROUND_HALF_UP)
    if price <= 0:
        return False
    fee = fee_fn(order.side, quantity, price, trade_date)
    if order.side == Side.BUY:
        while quantity > 0 and price * Decimal(quantity) + fee > ledger.cash:
            affordable = int(((ledger.cash - fee) / price).to_integral_value(rounding=ROUND_DOWN))
            quantity = min(quantity - 1, max(affordable, 0))
            if quantity > 0:
                fee = fee_fn(order.side, quantity, price, trade_date)
        if quantity <= 0:
            result.skipped.append(f"{day} {order.symbol}: not enough cash for one share")
            return False
    fill = Fill(
        fill_id=f"fill_{sequence}",
        order_id=f"ord_{sequence}",
        symbol=order.symbol,
        side=order.side,
        quantity=quantity,
        price=price,
        fee=fee,
        timestamp=stamp,
    )
    ledger.process_fill(fill)
    slippage_cost = (abs(price - open_price) * Decimal(quantity)).quantize(_PAISA)
    result.fills.append(
        FillRecord(day, order.symbol, order.side.value, quantity, price, fee, slippage_cost)
    )
    if order.side == Side.BUY:
        lots.setdefault(order.symbol, []).append(_Lot(day, session, quantity, price, fee))
    else:
        result.round_trips.append(
            _close_lots(order.symbol, quantity, price, fee, day, session, lots)
        )
    return True


def _close_lots(
    symbol: str,
    quantity: int,
    price: Decimal,
    fee: Decimal,
    day: str,
    session: int,
    lots: dict[str, list[_Lot]],
) -> RoundTrip:
    queue = lots.get(symbol, [])
    first_date, first_session = (queue[0].date, queue[0].session) if queue else (day, session)
    remaining = quantity
    cost = Decimal("0")
    price_paid = Decimal("0")
    while remaining > 0 and queue:
        lot = queue[0]
        take = min(remaining, lot.quantity)
        fee_share = lot.fee * Decimal(take) / Decimal(lot.quantity)
        cost += lot.price * Decimal(take) + fee_share
        price_paid += lot.price * Decimal(take)
        if take == lot.quantity:
            queue.pop(0)
        else:
            queue[0] = _Lot(
                lot.date, lot.session, lot.quantity - take, lot.price, lot.fee - fee_share
            )
        remaining -= take
    proceeds = price * Decimal(quantity) - fee
    pnl = (proceeds - cost).quantize(_PAISA)
    entry_price = (price_paid / Decimal(quantity)).quantize(_PAISA) if quantity else Decimal("0")
    return RoundTrip(
        symbol=symbol,
        entry_date=first_date,
        exit_date=day,
        quantity=quantity,
        entry_price=entry_price,
        exit_price=price,
        pnl=pnl,
        return_pct=float(pnl / cost) if cost else 0.0,
        sessions=session - first_session,
    )
