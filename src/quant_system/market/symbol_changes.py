"""NSE symbol changes parser and historical lineage resolver.

Parses symbol change CSV files published by the National Stock Exchange of India (NSE)
and provides historical tracking across renames, preventing false corporate-action misses
when a ticker is renamed.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class SymbolChange:
    """A single symbol change record."""

    company: str
    old: str
    new: str
    effective: date


def parse_symbol_changes(text: str) -> tuple[SymbolChange, ...]:
    """Parse CSV text of symbol changes.

    Skips invalid rows without raising:
    - Rows without exactly 4 columns
    - Rows with empty old or new symbol
    - Rows where old == new
    - Rows with unparseable date (format must be %d-%b-%Y)
    - Blank lines

    Tolerates leading UTF-8 BOM. Normalises company name (stripped, collapsed whitespace),
    old/new symbols (stripped, upper-case).
    Returns deduplicated changes sorted by (effective, old, new).
    """
    clean_text = text.removeprefix("\ufeff")
    reader = csv.reader(io.StringIO(clean_text))

    changes: list[SymbolChange] = []
    for row in reader:
        if len(row) != 4:
            continue
        raw_company, raw_old, raw_new, raw_date = row
        old = raw_old.strip().upper()
        new = raw_new.strip().upper()
        if not old or not new or old == new:
            continue
        try:
            effective = datetime.strptime(raw_date.strip(), "%d-%b-%Y").date()
        except ValueError:
            continue
        company = " ".join(raw_company.split())
        changes.append(
            SymbolChange(
                company=company,
                old=old,
                new=new,
                effective=effective,
            )
        )

    unique_changes = dict.fromkeys(changes)
    sorted_changes = sorted(unique_changes, key=lambda c: (c.effective, c.old, c.new))
    return tuple(sorted_changes)


class SymbolHistory:
    """Historical lineage of stock symbol renames."""

    def __init__(self, changes: Iterable[SymbolChange]) -> None:
        """Initialise history with an iterable of SymbolChange objects."""
        unique_changes = dict.fromkeys(changes)
        sorted_changes = sorted(unique_changes, key=lambda c: (c.effective, c.old, c.new))

        self._outgoing: dict[str, list[SymbolChange]] = {}
        self._incoming: dict[str, list[SymbolChange]] = {}
        self._latest_change: dict[str, SymbolChange] = {}
        self._known_symbols: set[str] = set()

        for c in sorted_changes:
            old = c.old.strip().upper()
            new = c.new.strip().upper()
            if not old or not new or old == new:
                continue

            normalized_change = (
                c
                if c.old == old and c.new == new
                else SymbolChange(
                    company=" ".join(c.company.split()),
                    old=old,
                    new=new,
                    effective=c.effective,
                )
            )

            self._known_symbols.add(old)
            self._known_symbols.add(new)
            self._outgoing.setdefault(old, []).append(normalized_change)
            self._incoming.setdefault(new, []).append(normalized_change)
            self._latest_change[old] = normalized_change
            self._latest_change[new] = normalized_change

        # For incoming chains (predecessors), sort descending by effective date (most recent first).
        # On same effective date, sort ascending by old symbol for determinism.
        for inc_list in self._incoming.values():
            inc_list.sort(key=lambda c: (-c.effective.toordinal(), c.old))

    def successors(self, symbol: str) -> tuple[str, ...]:
        """Return the symbols S became, nearest first, following chains forward in time.

        A link S -> N applies only if its effective date is on or after the date of the link
        that led into S (non-decreasing dates). Cycle-safe (a symbol never appears twice;
        S itself is never included). Outgoing changes on different dates are followed in
        date order.
        """
        s = symbol.strip().upper()
        if s not in self._known_symbols:
            return ()

        result: list[str] = []
        visited: set[str] = {s}

        def _traverse(current_sym: str, min_date: date | None) -> None:
            for c in self._outgoing.get(current_sym, ()):
                if min_date is not None and c.effective < min_date:
                    continue
                nxt = c.new
                if nxt not in visited:
                    visited.add(nxt)
                    result.append(nxt)
                    _traverse(nxt, c.effective)

        _traverse(s, None)
        return tuple(result)

    def predecessors(self, symbol: str) -> tuple[str, ...]:
        """Return the symbols that became S, most recent first, following chains backward.

        Each earlier link must be on or before the date of the link that follows it
        (non-increasing dates backward). Cycle-safe (never includes S).
        """
        s = symbol.strip().upper()
        if s not in self._known_symbols:
            return ()

        result: list[str] = []
        visited: set[str] = {s}

        def _traverse(current_sym: str, max_date: date | None) -> None:
            for c in self._incoming.get(current_sym, ()):
                if max_date is not None and c.effective > max_date:
                    continue
                prev = c.old
                if prev not in visited:
                    visited.add(prev)
                    result.append(prev)
                    _traverse(prev, c.effective)

        _traverse(s, None)
        return tuple(result)

    def current(self, symbol: str) -> str:
        """Return the current symbol for S (last element of successors(S), or S if none)."""
        s = symbol.strip().upper()
        succ = self.successors(s)
        return succ[-1] if succ else s

    def former_symbols(self, symbol: str) -> tuple[str, ...]:
        """Return former symbols that became S (alias for predecessors)."""
        return self.predecessors(symbol)

    def company_for(self, symbol: str) -> str | None:
        """Return the company name on the latest change in which S appears, else None."""
        s = symbol.strip().upper()
        change = self._latest_change.get(s)
        return change.company if change is not None else None
