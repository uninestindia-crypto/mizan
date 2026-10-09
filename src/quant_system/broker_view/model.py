"""What the broker showed, as exact numbers, and the figures QuantOS works out from them.

Money is ``Decimal`` all the way through. It becomes a plain number only at the very edge, when the screen's reply is
built. QuantOS does its own sums (invested, value, profit or loss, today's move) from the prices and quantities the
broker sent; it never trusts the broker's own totals, whose units and timing are not the same for every account.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from quant_system.broker_view import messages

INDIA = timezone(timedelta(hours=5, minutes=30))
HUNDRED = Decimal(100)
# The same rule the hand-entered Portfolio uses (server/v2/portfolio.py); a test keeps the two equal.
CONCENTRATION_LIMIT = Decimal("0.25")
SHOWN_AS_WORDS = {"I": "Intraday", "D": "Delivery", "MTF": "Margin trading"}


def money(value: Decimal | None, places: int = 2) -> float | None:
    """A plain number for the screen's reply, rounded half up. A missing figure stays missing."""
    if value is None:
        return None
    return float(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def percent_points(part: Decimal, whole: Decimal) -> float | None:
    """``part`` as a share of ``whole`` in percent points (5.0 means 5%). None when there is no whole."""
    if whole == 0:
        return None
    return money(part / whole * HUNDRED)


@dataclass(frozen=True, slots=True)
class HoldingRow:
    symbol: str
    exchange: str | None
    isin: str | None
    quantity: int
    t1_quantity: int
    average_price: Decimal
    last_price: Decimal
    close_price: Decimal | None

    @property
    def invested(self) -> Decimal:
        return self.average_price * self.quantity

    @property
    def value(self) -> Decimal:
        return self.last_price * self.quantity

    @property
    def pnl(self) -> Decimal:
        return self.value - self.invested

    @property
    def today(self) -> Decimal | None:
        if self.close_price is None:
            return None
        return (self.last_price - self.close_price) * self.quantity

    @property
    def arriving_value(self) -> Decimal:
        return self.last_price * self.t1_quantity


@dataclass(frozen=True, slots=True)
class PositionRow:
    symbol: str
    exchange: str | None
    product: str
    quantity: int
    average_price: Decimal | None
    last_price: Decimal
    pnl: Decimal | None
    realised: Decimal | None
    unrealised: Decimal | None


@dataclass(frozen=True, slots=True)
class Cash:
    available: Decimal | None
    in_use: Decimal | None


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Everything fetched in one go, with the time it was fetched. Nothing here identifies the person."""

    broker: str
    fetched_at: datetime
    holdings: tuple[HoldingRow, ...]
    positions: tuple[PositionRow, ...]
    cash: Cash | None
    skipped_holdings: int = 0
    skipped_positions: int = 0
    notes: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        """The reply the Portfolio card shows, without the parts that depend on the moment it is read."""
        total_value = sum((h.value for h in self.holdings), Decimal(0))
        invested = sum((h.invested for h in self.holdings), Decimal(0))
        pnl = total_value - invested
        todays = [h.today for h in self.holdings if h.quantity]
        known = [t for t in todays if t is not None]
        # A day's move is only added up when every share has the close it is measured against.
        today = sum(known, Decimal(0)) if len(known) == len(todays) else None
        arriving = sum((h.t1_quantity for h in self.holdings), 0)
        rows = [_holding_dict(h, total_value) for h in self.holdings]
        rows.sort(key=lambda row: -(row["value"] or 0))
        return {
            "broker": self.broker,
            "fetched_at": self.fetched_at.astimezone(INDIA).isoformat(timespec="seconds"),
            "totals": {
                "value": money(total_value),
                "invested": money(invested),
                "pnl": money(pnl),
                "pnl_pct": percent_points(pnl, invested),
                "today": money(today),
                "arriving_value": money(sum((h.arriving_value for h in self.holdings), Decimal(0))),
                "arriving_note": messages.arriving(arriving) if arriving else None,
            },
            "cash": _cash_dict(self.cash),
            "holdings": rows,
            "positions": [_position_dict(p) for p in self.positions],
            "warnings": _warnings(self.holdings, total_value),
            "skipped": {"holdings": self.skipped_holdings, "positions": self.skipped_positions},
            "notes": list(self.notes),
        }


def _holding_dict(holding: HoldingRow, total_value: Decimal) -> dict[str, Any]:
    return {
        "symbol": holding.symbol,
        "exchange": holding.exchange,
        "isin": holding.isin,
        "quantity": holding.quantity,
        "t1_quantity": holding.t1_quantity,
        "average_price": money(holding.average_price),
        "last_price": money(holding.last_price),
        "close_price": money(holding.close_price),
        "value": money(holding.value),
        "invested": money(holding.invested),
        "pnl": money(holding.pnl),
        "pnl_pct": percent_points(holding.pnl, holding.invested),
        "today": money(holding.today),
        "weight_pct": percent_points(holding.value, total_value),
    }


def _position_dict(position: PositionRow) -> dict[str, Any]:
    return {
        "symbol": position.symbol,
        "exchange": position.exchange,
        "product": position.product,
        "quantity": position.quantity,
        "closed": position.quantity == 0,
        "average_price": money(position.average_price),
        "last_price": money(position.last_price),
        "pnl": money(position.pnl),
        "realised": money(position.realised),
        "unrealised": money(position.unrealised),
    }


def _cash_dict(cash: Cash | None) -> dict[str, Any]:
    if cash is None:
        return {"available": None, "in_use": None}
    return {"available": money(cash.available), "in_use": money(cash.in_use)}


def _warnings(holdings: tuple[HoldingRow, ...], total_value: Decimal) -> list[str]:
    if total_value <= 0:
        return []
    limit = f"{CONCENTRATION_LIMIT * HUNDRED:.0f}%"
    heavy = [h for h in holdings if h.value / total_value > CONCENTRATION_LIMIT]
    heavy.sort(key=lambda h: -h.value)
    return [
        f"{h.symbol} is {h.value / total_value * HUNDRED:.0f}% of your holdings (above {limit})."
        for h in heavy
    ]
