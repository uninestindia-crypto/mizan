"""Strict reading of what Upstox sends back for holdings, open positions and cash.

Only the few fields QuantOS shows are kept; everything else in a reply (company name, collateral, the instrument
token, and anything the broker may add later) is dropped on the spot. A row that does not pass every check is skipped
and counted, never guessed at, so the screen can say how many rows it could not read. Numbers stay exact decimals from
the moment they are read, and a reply that is not an object, or does not say it succeeded, is unreadable as a whole.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, NoReturn

from quant_system.broker_view.model import SHOWN_AS_WORDS, Cash, HoldingRow, PositionRow

_MAX_MONEY = Decimal("1e13")
_MAX_QUANTITY = 10**9
_HOLDING_SYMBOL = re.compile(r"[A-Z0-9&\-]{1,30}")
_POSITION_SYMBOL = re.compile(r"[A-Z0-9&\- ]{1,40}")
_EXCHANGE = re.compile(r"[A-Z_]{2,10}")
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


class ReplyUnreadable(ValueError):
    """The reply as a whole cannot be used: not an object, or it does not say it succeeded."""


@dataclass(frozen=True, slots=True)
class Parsed[T]:
    rows: tuple[T, ...]
    skipped: int


def _refuse_constant(_name: str) -> NoReturn:
    raise ValueError("not a number")


def load_reply(body: bytes) -> dict[str, Any]:
    """The reply's top-level object, with every number kept as an exact decimal."""
    try:
        payload = json.loads(body, parse_float=Decimal, parse_constant=_refuse_constant)
    except (ValueError, RecursionError) as error:
        raise ReplyUnreadable("not readable") from error
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ReplyUnreadable("not a success")
    return payload


def _decimal(value: object, minimum: Decimal | None = Decimal(0)) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError("not a number")
    number = Decimal(value)
    if not number.is_finite() or abs(number) > _MAX_MONEY:
        raise ValueError("not a usable number")
    if minimum is not None and number < minimum:
        raise ValueError("below the allowed range")
    return number


def _whole(value: object, minimum: int | None = 0) -> int:
    number = _decimal(value, None)
    if number != number.to_integral_value() or abs(number) > _MAX_QUANTITY:
        raise ValueError("not a whole number of shares")
    quantity = int(number)
    if minimum is not None and quantity < minimum:
        raise ValueError("below the allowed range")
    return quantity


def _text(value: object, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str):
        raise ValueError("not text")
    cleaned = value.strip().upper()
    if not pattern.fullmatch(cleaned):
        raise ValueError("not an expected value")
    return cleaned


def _optional(read: Any, value: object) -> Any:
    """Whatever ``read`` makes of ``value``, or None when it is absent or unusable."""
    if value is None:
        return None
    try:
        return read(value)
    except ValueError:
        return None


def _rows(payload: dict[str, Any]) -> list[Any]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise ReplyUnreadable("no list of rows")
    return data


def _holding(row: dict[str, Any]) -> HoldingRow:
    symbol = row.get("trading_symbol") or row.get("tradingsymbol")
    exchange = row.get("exchange")
    close = row.get("close_price")
    return HoldingRow(
        symbol=_text(symbol, _HOLDING_SYMBOL),
        exchange=None if exchange is None else _text(exchange, _EXCHANGE),
        isin=_optional(lambda v: _text(v, _ISIN), row.get("isin")),
        quantity=_whole(row.get("quantity")),
        t1_quantity=_optional(_whole, row.get("t1_quantity")) or 0,
        average_price=_decimal(row.get("average_price")),
        last_price=_decimal(row.get("last_price"), Decimal("0.0000001")),
        close_price=_optional(_decimal, close),
    )


def _position(row: dict[str, Any]) -> PositionRow:
    symbol = row.get("trading_symbol") or row.get("tradingsymbol")
    exchange = row.get("exchange")
    product = row.get("product")
    label = (
        SHOWN_AS_WORDS.get(product.strip().upper(), "Other")
        if isinstance(product, str)
        else "Other"
    )

    def any_number(value: object) -> Decimal:
        return _decimal(value, None)

    return PositionRow(
        symbol=_text(symbol, _POSITION_SYMBOL),
        exchange=None if exchange is None else _text(exchange, _EXCHANGE),
        product=label,
        quantity=_whole(row.get("quantity"), None),
        average_price=_optional(any_number, row.get("average_price")),
        last_price=_decimal(row.get("last_price")),
        pnl=_optional(any_number, row.get("pnl")),
        realised=_optional(any_number, row.get("realised")),
        unrealised=_optional(any_number, row.get("unrealised")),
    )


def _parse_rows[T](payload: dict[str, Any], build: Callable[[dict[str, Any]], T]) -> Parsed[T]:
    kept: list[T] = []
    skipped = 0
    for row in _rows(payload):
        try:
            if not isinstance(row, dict):
                raise ValueError("not a row")
            kept.append(build(row))
        except ValueError:
            skipped += 1
    return Parsed(tuple(kept), skipped)


def parse_holdings(body: bytes) -> Parsed[HoldingRow]:
    return _parse_rows(load_reply(body), _holding)


def parse_positions(body: bytes) -> Parsed[PositionRow]:
    return _parse_rows(load_reply(body), _position)


def parse_funds(body: bytes) -> Cash:
    """Available and used cash for the equity segment, from either shape Upstox may answer with."""
    data = load_reply(body).get("data")
    if not isinstance(data, dict):
        raise ReplyUnreadable("no cash figures")
    segment = data.get("equity")
    figures = segment if isinstance(segment, dict) else data
    available = _optional(lambda v: _decimal(v, None), figures.get("available_margin"))
    in_use = _optional(lambda v: _decimal(v, None), figures.get("used_margin"))
    if available is None and in_use is None:
        raise ReplyUnreadable("no cash figures")
    return Cash(available=available, in_use=in_use)
