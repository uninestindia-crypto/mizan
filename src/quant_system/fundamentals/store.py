"""Where figures live: the bundled snapshot (read only) and a per-user database (written from the app).

A newer filing replaces an older one. The store works with neither file present: it is simply empty, and the
service says "no filings held for this company yet".
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.snapshot import (
    FundamentalsStoreError,
    Snapshot,
    normalize_symbol,
    read_snapshot,
)

__all__ = ["FundamentalsStore", "FundamentalsStoreError", "should_replace"]

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS quarters ("
    "symbol TEXT NOT NULL, month TEXT NOT NULL, consolidated INTEGER NOT NULL, payload TEXT NOT NULL, "
    "PRIMARY KEY (symbol, month, consolidated))",
    "CREATE TABLE IF NOT EXISTS industry_groups ("
    "symbol TEXT PRIMARY KEY, industry TEXT NOT NULL, read_on TEXT NOT NULL)",
)
CANNOT_SAVE = (
    "QuantOS could not save this on this computer. Check that its data folder can be written to."
)
BAD_SYMBOL = "That is not a valid company symbol, so nothing was saved."
NOWHERE_TO_SAVE = "QuantOS has no place to save company results on this computer."
Key = tuple[str, bool]


def should_replace(old: QuarterFigures, new: QuarterFigures) -> bool:
    """A later filing replaces an earlier one. For the same filing, a clean read is never swapped for a worse one."""
    old_on, new_on = old.filed_on or date.min, new.filed_on or date.min
    if new_on != old_on:
        return new_on > old_on
    return not old.usable


def _key(item: QuarterFigures) -> Key:
    return item.period_end.strftime("%Y-%m"), item.consolidated


def _parse(payload: object) -> QuarterFigures | None:
    try:
        document = json.loads(payload) if isinstance(payload, str) else payload
        return QuarterFigures.from_json_dict(document) if isinstance(document, dict) else None
    except ValueError:
        return None


def _company_rows(symbol: str, raw: object) -> dict[Key, QuarterFigures]:
    """A company's bundled rows, one per quarter and basis. Invalid rows, or another company's, are dropped."""
    parsed = [_parse(entry) for entry in raw] if isinstance(raw, list) else []
    held: dict[Key, QuarterFigures] = {}
    for item in (p for p in parsed if p is not None and p.symbol == symbol):
        _best(held, item)
    return held


def _best(held: dict[Key, QuarterFigures], item: QuarterFigures) -> None:
    key = _key(item)
    if key not in held or should_replace(held[key], item):
        held[key] = item


class FundamentalsStore:
    def __init__(self, snapshot_path: Path | None = None, user_db_path: Path | None = None) -> None:
        self._snapshot_path = snapshot_path
        self._user_path = user_db_path
        self._snapshot: Snapshot | None = None
        self._loaded = False
        self._parsed: dict[str, dict[Key, QuarterFigures]] = {}

    # -- reading ---------------------------------------------------------------------------------
    def quarters(self, symbol: str) -> list[QuarterFigures]:
        wanted = normalize_symbol(symbol)
        if wanted is None:
            return []
        return self._merge(self._snapshot_rows(wanted), self._user_rows(wanted))

    def all_quarters(self) -> dict[str, list[QuarterFigures]]:
        """Every company held, read once. Used by screens that look at the whole set."""
        users = self._user_all()
        names = set(self._snapshot_symbols()) | set(users)
        merged = {s: self._merge(self._snapshot_rows(s), users.get(s, [])) for s in sorted(names)}
        return {symbol: rows for symbol, rows in merged.items() if rows}

    def symbols(self) -> list[str]:
        return sorted(self.all_quarters())

    def coverage(self) -> dict[str, Any]:
        everything = self.all_quarters()
        usable = [q for rows in everything.values() for q in rows if q.usable]
        snapshot = self._loaded_snapshot()
        newest = max((q.period_end for q in usable), default=None)
        return {
            "companies": len({q.symbol for q in usable}),
            "newest_filing": newest.isoformat() if newest else None,
            "snapshot_built_on": snapshot.built_on if snapshot else None,
        }

    def industry(self, symbol: str) -> str | None:
        wanted = normalize_symbol(symbol)
        if wanted is None:
            return None
        snapshot = self._loaded_snapshot()
        bundled = (
            (snapshot.industry_groups.get(wanted), snapshot.industry_read_on)
            if snapshot
            else (None, "")
        )
        rows = self._read(
            "SELECT industry, read_on FROM industry_groups WHERE symbol = ?", (wanted,)
        )
        saved = (str(rows[0][0]), str(rows[0][1])) if rows else None
        if saved is not None and (bundled[0] is None or saved[1] >= bundled[1]):
            return saved[0]
        return bundled[0]

    # -- writing ---------------------------------------------------------------------------------
    def put(self, quarters: Sequence[QuarterFigures]) -> int:
        """Save filings for the user. Returns how many were saved; what is already held as new or better is kept."""
        if any(normalize_symbol(item.symbol) != item.symbol for item in quarters):
            raise FundamentalsStoreError(BAD_SYMBOL)
        saved = 0
        with self._writer() as connection:
            for item in quarters:
                saved += self._put_one(connection, item)
        return saved

    def put_industry(self, groups: Mapping[str, str], read_on: str) -> int:
        """Save industry groups (symbol -> group) read on `read_on`. Returns how many were saved."""
        try:
            date.fromisoformat(read_on)
        except ValueError:
            raise FundamentalsStoreError(
                "The date for these industry groups is not valid."
            ) from None
        rows = [
            (s, g.strip()[:80], read_on)
            for sym, g in groups.items()
            if (s := normalize_symbol(sym)) and g.strip()
        ]
        with self._writer() as connection:
            connection.executemany(
                "INSERT INTO industry_groups (symbol, industry, read_on) VALUES (?, ?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET industry = excluded.industry, read_on = excluded.read_on "
                "WHERE excluded.read_on >= industry_groups.read_on",
                rows,
            )
        return len(rows)

    # -- internals -------------------------------------------------------------------------------
    def _put_one(self, connection: sqlite3.Connection, item: QuarterFigures) -> int:
        month, consolidated = _key(item)
        row = connection.execute(
            "SELECT payload FROM quarters WHERE symbol = ? AND month = ? AND consolidated = ?",
            (item.symbol, month, int(consolidated)),
        ).fetchone()
        held = _parse(row[0]) if row else None
        bundled = self._snapshot_rows(item.symbol).get(_key(item))
        for old in (held, bundled):
            if old is not None and not should_replace(old, item):
                return 0
        connection.execute(
            "INSERT INTO quarters (symbol, month, consolidated, payload) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(symbol, month, consolidated) DO UPDATE SET payload = excluded.payload",
            (item.symbol, month, int(consolidated), json.dumps(item.to_json_dict())),
        )
        return 1

    @staticmethod
    def _merge(
        bundled: dict[Key, QuarterFigures], saved: list[QuarterFigures]
    ) -> list[QuarterFigures]:
        held = dict(bundled)
        for item in saved:
            _best(held, item)
        return sorted(held.values(), key=lambda q: (q.period_end, q.consolidated))

    def _loaded_snapshot(self) -> Snapshot | None:
        if not self._loaded:
            self._snapshot = read_snapshot(self._snapshot_path) if self._snapshot_path else None
            self._loaded = True
        return self._snapshot

    def _snapshot_symbols(self) -> list[str]:
        snapshot = self._loaded_snapshot()
        return list(snapshot.companies) if snapshot else []

    def _snapshot_rows(self, symbol: str) -> dict[Key, QuarterFigures]:
        if symbol not in self._parsed:
            snapshot = self._loaded_snapshot()
            raw = snapshot.companies.get(symbol, []) if snapshot else []
            self._parsed[symbol] = _company_rows(symbol, raw)
        return self._parsed[symbol]

    def _read(self, sql: str, args: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        """Rows from the user database, or nothing when it is missing, unreadable or damaged."""
        if self._user_path is None or not self._user_path.is_file():
            return []
        uri = self._user_path.resolve().as_uri() + "?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=5)) as connection:
                return [tuple(row) for row in connection.execute(sql, args)]
        except sqlite3.Error:
            return []

    def _user_rows(self, symbol: str) -> list[QuarterFigures]:
        rows = self._read("SELECT payload FROM quarters WHERE symbol = ?", (symbol,))
        return [
            item
            for item in (_parse(r[0]) for r in rows)
            if item is not None and item.symbol == symbol
        ]

    def _user_all(self) -> dict[str, list[QuarterFigures]]:
        found: dict[str, list[QuarterFigures]] = {}
        for symbol, payload in self._read("SELECT symbol, payload FROM quarters"):
            item = _parse(payload)
            if item is not None and item.symbol == symbol:
                found.setdefault(symbol, []).append(item)
        return found

    @contextmanager
    def _writer(self) -> Iterator[sqlite3.Connection]:
        if self._user_path is None:
            raise FundamentalsStoreError(NOWHERE_TO_SAVE)
        try:
            connection = self._open_for_writing(self._user_path)
        except (OSError, sqlite3.Error):
            raise FundamentalsStoreError(CANNOT_SAVE) from None
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except sqlite3.Error:
            raise FundamentalsStoreError(CANNOT_SAVE) from None
        finally:
            connection.close()

    def _open_for_writing(self, path: Path) -> sqlite3.Connection:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return self._prepare(path)
        except sqlite3.DatabaseError as error:
            if "not a database" not in str(error) and "malformed" not in str(error):
                raise
            # A damaged file. Keep it aside rather than deleting it, and start fresh.
            os.replace(path, path.with_name(path.name + ".corrupt"))
            return self._prepare(path)

    @staticmethod
    def _prepare(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path, timeout=10, isolation_level=None)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            for statement in SCHEMA:
                connection.execute(statement)
        except sqlite3.Error:
            connection.close()
            raise
        return connection
