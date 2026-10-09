"""Where figures live: the bundled snapshot (read only) and a per-user database (written from the app)."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from quant_system.shariah.filings.models import (
    FilingFigures,
    ReadStatus,
    clean_text,
    normalize_symbol,
)
from quant_system.shariah.filings.snapshot import (
    FilingsStoreError,
    IndustrySnapshot,
    Snapshot,
    read_snapshot,
    write_snapshot,
)

__all__ = ["FilingsStore", "FilingsStoreError", "IndustrySnapshot", "write_snapshot"]

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS filings ("
    "symbol TEXT PRIMARY KEY, period_end TEXT NOT NULL, payload TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS industry_groups ("
    "symbol TEXT PRIMARY KEY, industry TEXT NOT NULL, read_on TEXT NOT NULL)",
)
CANNOT_SAVE = (
    "QuantOS could not save this on this computer. Check that its data folder can be written to."
)
NOWHERE_TO_SAVE = "QuantOS has no place to save filings on this computer."


def should_replace(old: FilingFigures, new: FilingFigures) -> bool:
    """A newer period replaces an older one. For the same period, never swap a clean read for a worse one."""
    if new.proof.period_end != old.proof.period_end:
        return new.proof.period_end > old.proof.period_end
    if old.read_status is ReadStatus.READ_OK:
        return new.read_status is ReadStatus.READ_OK and (
            new.proof.consolidated or not old.proof.consolidated
        )
    return True


def _parse(payload: object) -> FilingFigures | None:
    """Figures from a stored JSON text or document, or None when it is not a valid filing."""
    try:
        document = json.loads(payload) if isinstance(payload, str) else payload
        return FilingFigures.from_json_dict(document) if isinstance(document, dict) else None
    except ValueError:
        return None


class FilingsStore:
    def __init__(self, snapshot_path: Path | None = None, user_db_path: Path | None = None) -> None:
        self._snapshot_path = snapshot_path
        self._user_path = user_db_path
        self._snapshot: Snapshot | None = None
        self._snapshot_rows: dict[str, FilingFigures] | None = None

    # -- reading ---------------------------------------------------------------------------------
    def get(self, symbol: str) -> FilingFigures | None:
        wanted = normalize_symbol(symbol)
        if wanted is None:
            return None
        return self._effective(self._user_figures(wanted), self._snapshot_figures().get(wanted))

    def symbols(self) -> list[str]:
        return sorted(self._all())

    def coverage(self) -> dict[str, Any]:
        everything = self._all().values()
        snapshot = self._loaded_snapshot()
        newest = max((f.proof.period_end for f in everything), default=None)
        return {
            "screened": sum(1 for f in everything if f.read_status is ReadStatus.READ_OK),
            "newest_filing": newest.isoformat() if newest else None,
            "snapshot_built_on": snapshot.built_on if snapshot else None,
        }

    def industry_group(self, symbol: str) -> str | None:
        wanted = normalize_symbol(symbol)
        if wanted is None:
            return None
        snapshot = self._loaded_snapshot()
        found = (
            (snapshot.industry_groups.get(wanted), snapshot.industry_read_on)
            if snapshot
            else (None, "")
        )
        saved = self._user_industry(wanted)
        if saved is not None and (found[0] is None or saved[1] >= found[1]):
            return saved[0]
        return found[0]

    # -- writing ---------------------------------------------------------------------------------
    def put(self, figures: FilingFigures) -> bool:
        """Save a filing for the user. False when what is already held is as new or better."""
        symbol = normalize_symbol(figures.symbol)
        if symbol is None or symbol != figures.symbol:
            raise FilingsStoreError("That is not a valid company symbol, so nothing was saved.")
        with self._writer() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT payload FROM filings WHERE symbol = ?", (symbol,)
            ).fetchone()
            held = self._effective(
                _parse(row[0]) if row else None, self._snapshot_figures().get(symbol)
            )
            if held is not None and not should_replace(held, figures):
                connection.execute("ROLLBACK")
                return False
            connection.execute(
                "INSERT INTO filings (symbol, period_end, payload) VALUES (?, ?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET period_end = excluded.period_end, "
                "payload = excluded.payload",
                (symbol, figures.proof.period_end.isoformat(), json.dumps(figures.to_json_dict())),
            )
            connection.execute("COMMIT")
        return True

    def put_industry_groups(self, groups: Mapping[str, str], read_on: str) -> int:
        """Save NSE industry groups (symbol -> group) read on `read_on`. Returns how many were saved."""
        try:
            date.fromisoformat(read_on)
        except ValueError:
            raise FilingsStoreError("The date for these industry groups is not valid.") from None
        rows = []
        for symbol, industry in groups.items():
            wanted, text = normalize_symbol(symbol), clean_text(industry, 80)
            if wanted is not None and text:
                rows.append((wanted, text, read_on))
        with self._writer() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                "INSERT INTO industry_groups (symbol, industry, read_on) VALUES (?, ?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET industry = excluded.industry, read_on = excluded.read_on",
                rows,
            )
            connection.execute("COMMIT")
        return len(rows)

    # -- internals -------------------------------------------------------------------------------
    @staticmethod
    def _effective(
        user: FilingFigures | None, bundled: FilingFigures | None
    ) -> FilingFigures | None:
        if user is None or bundled is None:
            return user or bundled
        return bundled if bundled.proof.period_end > user.proof.period_end else user

    def _loaded_snapshot(self) -> Snapshot | None:
        if self._snapshot is None and self._snapshot_path is not None:
            self._snapshot = read_snapshot(self._snapshot_path)
        return self._snapshot

    def _snapshot_figures(self) -> dict[str, FilingFigures]:
        if self._snapshot_rows is None:
            snapshot = self._loaded_snapshot()
            parsed = {s: _parse(raw) for s, raw in (snapshot.filings if snapshot else {}).items()}
            self._snapshot_rows = {
                s: f for s, f in parsed.items() if f is not None and f.symbol == s
            }
        return self._snapshot_rows

    def _all(self) -> dict[str, FilingFigures]:
        merged = dict(self._snapshot_figures())
        for symbol, figures in self._user_figures_all().items():
            merged[symbol] = self._effective(figures, merged.get(symbol)) or figures
        return merged

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

    def _user_figures(self, symbol: str) -> FilingFigures | None:
        rows = self._read("SELECT payload FROM filings WHERE symbol = ?", (symbol,))
        return _parse(rows[0][0]) if rows else None

    def _user_figures_all(self) -> dict[str, FilingFigures]:
        parsed = {s: _parse(p) for s, p in self._read("SELECT symbol, payload FROM filings")}
        return {s: f for s, f in parsed.items() if f is not None and f.symbol == s}

    def _user_industry(self, symbol: str) -> tuple[str, str] | None:
        rows = self._read(
            "SELECT industry, read_on FROM industry_groups WHERE symbol = ?", (symbol,)
        )
        return (str(rows[0][0]), str(rows[0][1])) if rows else None

    @contextmanager
    def _writer(self) -> Iterator[sqlite3.Connection]:
        if self._user_path is None:
            raise FilingsStoreError(NOWHERE_TO_SAVE)
        try:
            connection = self._open_for_writing(self._user_path)
        except (OSError, sqlite3.Error):
            raise FilingsStoreError(CANNOT_SAVE) from None
        try:
            yield connection
        except sqlite3.Error:
            raise FilingsStoreError(CANNOT_SAVE) from None
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
