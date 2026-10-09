"""What the broker view remembers between starts, and nothing more.

It keeps the last set of figures with the time they were fetched, the time the broker will end the sign-in, and one
switch: whether the assistant may read a summary. It never holds a key, a name or any account identifier; the key lives
only in Windows Credential Manager, under its own entry.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class StoredSnapshot:
    fetched_at: datetime
    payload: dict[str, Any]


class SnapshotStore(Protocol):
    def load(self, broker: str) -> StoredSnapshot | None: ...
    def save(self, broker: str, fetched_at: datetime, payload: dict[str, Any]) -> None: ...
    def delete(self, broker: str) -> None: ...
    def assistant_access(self) -> bool: ...
    def set_assistant_access(self, allowed: bool) -> None: ...
    def key_ends_at(self, broker: str) -> datetime | None: ...
    def set_key_ends_at(self, broker: str, when: datetime | None) -> None: ...


class InMemorySnapshotStore:
    """For tests and for computers where nothing can be saved."""

    def __init__(self) -> None:
        self._snapshots: dict[str, StoredSnapshot] = {}
        self._ends: dict[str, datetime] = {}
        self._assistant = False

    def load(self, broker: str) -> StoredSnapshot | None:
        return self._snapshots.get(broker)

    def save(self, broker: str, fetched_at: datetime, payload: dict[str, Any]) -> None:
        self._snapshots[broker] = StoredSnapshot(fetched_at, json.loads(json.dumps(payload)))

    def delete(self, broker: str) -> None:
        self._snapshots.pop(broker, None)

    def assistant_access(self) -> bool:
        return self._assistant

    def set_assistant_access(self, allowed: bool) -> None:
        self._assistant = bool(allowed)

    def key_ends_at(self, broker: str) -> datetime | None:
        return self._ends.get(broker)

    def set_key_ends_at(self, broker: str, when: datetime | None) -> None:
        if when is None:
            self._ends.pop(broker, None)
        else:
            self._ends[broker] = when


class SqliteSnapshotStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS snapshot "
                "(broker TEXT PRIMARY KEY, fetched_at TEXT NOT NULL, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            db = sqlite3.connect(self._path, timeout=10)
            try:
                with db:
                    yield db
            finally:
                db.close()

    def load(self, broker: str) -> StoredSnapshot | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT fetched_at, body FROM snapshot WHERE broker = ?", (broker,)
            ).fetchone()
        if row is None:
            return None
        try:
            return StoredSnapshot(datetime.fromisoformat(row[0]), json.loads(row[1]))
        except (ValueError, TypeError):
            return None

    def save(self, broker: str, fetched_at: datetime, payload: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO snapshot (broker, fetched_at, body) VALUES (?, ?, ?)",
                (broker, fetched_at.isoformat(), json.dumps(payload)),
            )

    def delete(self, broker: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM snapshot WHERE broker = ?", (broker,))

    def _meta(self, name: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT value FROM meta WHERE name = ?", (name,)).fetchone()
        return None if row is None else str(row[0])

    def _set_meta(self, name: str, value: str | None) -> None:
        with self._connect() as db:
            if value is None:
                db.execute("DELETE FROM meta WHERE name = ?", (name,))
            else:
                db.execute("INSERT OR REPLACE INTO meta (name, value) VALUES (?, ?)", (name, value))

    def assistant_access(self) -> bool:
        return self._meta("assistant_access") == "1"

    def set_assistant_access(self, allowed: bool) -> None:
        self._set_meta("assistant_access", "1" if allowed else "0")

    def key_ends_at(self, broker: str) -> datetime | None:
        value = self._meta(f"key_ends_at:{broker}")
        try:
            return None if value is None else datetime.fromisoformat(value)
        except ValueError:
            return None

    def set_key_ends_at(self, broker: str, when: datetime | None) -> None:
        self._set_meta(f"key_ends_at:{broker}", None if when is None else when.isoformat())
