"""One company's run of quarters, on one basis, with gaps marked.

Consolidated figures are preferred; standalone figures are used only when the newest quarter has no usable
consolidated filing. The two are never mixed: a quarter on the other basis is not used to fill a gap.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

from quant_system.fundamentals.models import QuarterFigures, ReadStatus

MAX_QUARTERS: Final = 16
MONTH_KEY = tuple[int, int]
OTHER_BASIS: Final = (
    "The newest consolidated filing could not be used, "
    "so the company's own (standalone) figures are shown."
)


@dataclass(frozen=True)
class Slot:
    """One quarter of the run: the filing, or None when no usable filing is held for it."""

    period_end: date
    quarter: QuarterFigures | None


@dataclass(frozen=True)
class Series:
    symbol: str
    company_name: str
    consolidated: bool | None
    slots: tuple[Slot, ...]
    excluded: tuple[QuarterFigures, ...]
    unread: QuarterFigures | None
    notes: tuple[str, ...]

    @property
    def latest(self) -> QuarterFigures | None:
        return self.slots[-1].quarter if self.slots else None

    @property
    def gaps(self) -> tuple[date, ...]:
        return tuple(slot.period_end for slot in self.slots if slot.quarter is None)

    def at(self, offset: int) -> QuarterFigures | None:
        """The quarter `offset` quarters before the latest (0 is the latest), or None for a gap or no such quarter."""
        index = len(self.slots) - 1 - offset
        return self.slots[index].quarter if 0 <= index < len(self.slots) else None

    def run(self, offset: int, count: int) -> list[QuarterFigures] | None:
        """`count` quarters in a row, starting `offset` back from the latest, oldest first; None if any is missing."""
        found = [self.at(offset + step) for step in range(count)]
        if any(item is None for item in found):
            return None
        return [item for item in reversed(found) if item is not None]


def month_key(day: date) -> MONTH_KEY:
    return day.year, day.month


def months_back(day: date, months: int) -> MONTH_KEY:
    index = day.year * 12 + day.month - 1 - months
    return index // 12, index % 12 + 1


def month_end(key: MONTH_KEY) -> date:
    return date(key[0], key[1], calendar.monthrange(*key)[1])


def _preferred(first: QuarterFigures, second: QuarterFigures) -> QuarterFigures:
    """The later filing replaces the earlier one. On a tie an audited filing, then a usable one, wins."""

    def rank(item: QuarterFigures) -> tuple[date, bool, bool]:
        return item.filed_on or date.min, item.audited, item.usable

    return first if rank(first) >= rank(second) else second


def _deduped(quarters: Sequence[QuarterFigures]) -> list[QuarterFigures]:
    best: dict[tuple[MONTH_KEY, bool], QuarterFigures] = {}
    for item in quarters:
        key = (month_key(item.period_end), item.consolidated)
        best[key] = _preferred(best[key], item) if key in best else item
    return list(best.values())


def _basis(usable: list[QuarterFigures]) -> bool:
    latest = max(item.period_end for item in usable)
    return any(
        item.consolidated for item in usable if month_key(item.period_end) == month_key(latest)
    )


def _slots(chosen: list[QuarterFigures]) -> tuple[Slot, ...]:
    by_month = {month_key(item.period_end): item for item in chosen}
    latest = max(item.period_end for item in chosen)
    earliest = min(item.period_end for item in chosen)
    span = (latest.year * 12 + latest.month) - (earliest.year * 12 + earliest.month)
    count = min(MAX_QUARTERS, span // 3 + 1)
    keys = [months_back(latest, 3 * step) for step in range(count)]
    return tuple(Slot(month_end(key), by_month.get(key)) for key in reversed(keys))


def _unread(unusable: list[QuarterFigures]) -> QuarterFigures | None:
    if not unusable:
        return None
    return max(
        unusable, key=lambda item: (item.period_end, item.status is ReadStatus.FORMAT_NOT_READ)
    )


def build_series(quarters: Sequence[QuarterFigures], max_quarters: int = MAX_QUARTERS) -> Series:
    """The company's run of quarters. Pure: it only arranges what is held."""
    held = _deduped(quarters)
    usable = [item for item in held if item.usable]
    name = max(held, key=lambda item: item.period_end).company_name if held else ""
    symbol = held[0].symbol if held else ""
    if not usable:
        return Series(symbol, name, None, (), tuple(held), _unread(held), ())
    basis = _basis(usable)
    chosen = [item for item in usable if item.consolidated == basis]
    slots = _slots(chosen)[-max_quarters:]
    window = {month_key(slot.period_end) for slot in slots}
    excluded = [item for item in held if not item.usable and month_key(item.period_end) in window]
    excluded = [item for item in excluded if item.consolidated == basis]
    return Series(
        symbol,
        name,
        basis,
        slots,
        tuple(sorted(excluded, key=lambda i: i.period_end)),
        None,
        _notes(held, basis),
    )


def _notes(held: list[QuarterFigures], basis: bool) -> tuple[str, ...]:
    if basis:
        return ()
    newest = max(item.period_end for item in held)
    failed = [
        i
        for i in held
        if i.consolidated and not i.usable and month_key(i.period_end) == month_key(newest)
    ]
    return (OTHER_BASIS,) if failed else ()
