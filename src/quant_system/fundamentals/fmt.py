"""Plain wording for amounts and percentages. Indian grouping (lakh, crore), no jargon."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

CRORE: Final = Decimal(10_000_000)
LAKH: Final = Decimal(100_000)
MONTHS: Final = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def group_indian(whole: int) -> str:
    """12345678 as "1,23,45,678"."""
    digits = str(abs(whole))
    if len(digits) <= 3:
        head = digits
    else:
        rest, tail = digits[:-3], digits[-3:]
        pairs: list[str] = []
        while len(rest) > 2:
            pairs.insert(0, rest[-2:])
            rest = rest[:-2]
        head = ",".join([rest, *pairs, tail])
    return ("-" if whole < 0 else "") + head


def _rounded(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def inr(value: Decimal) -> str:
    """An amount in rupees in the unit people read it in: crore, lakh, or plain rupees."""
    sign = "-" if value < 0 else ""
    size = abs(value)
    if size >= CRORE:
        places = 0 if size >= CRORE * 1000 else 1
        number = _rounded(size / CRORE, places)
        unit = " crore"
    elif size >= LAKH:
        number, unit = _rounded(size / LAKH, 1), " lakh"
    else:
        number, unit = _rounded(size, 0), ""
    whole, _, fraction = f"{number:f}".partition(".")
    text = group_indian(int(whole)) + (f".{fraction}" if fraction and int(fraction) else "")
    return f"{sign}Rs {text}{unit}"


def per_share(value: Decimal) -> str:
    return f"Rs {_rounded(value, 2):f}"


def percent(value: Decimal, places: int = 0, signed: bool = False) -> str:
    number = _rounded(value, places)
    sign = "+" if signed and number > 0 else ""
    return f"{sign}{number:f}%"


def times(value: Decimal, places: int = 1) -> str:
    return f"{_rounded(value, places):f}"


def day(when: date) -> str:
    """A date as "30 Sep 2024"."""
    return f"{when.day} {MONTHS[when.month - 1]} {when.year}"
