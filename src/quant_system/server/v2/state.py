"""Local app state for QuantOS 2.0: settings, watchlist, holdings and the lab's run history.

One SQLite file (``app.sqlite``) beside the market index. Lab runs cannot be deleted: every run is
a look at the same history, and the verdict's multiplicity adjustment depends on counting them all.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS watchlist(symbol TEXT PRIMARY KEY, added_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS holdings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    avg_price TEXT NOT NULL,
    buy_date TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_runs(
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    template_id TEXT NOT NULL,
    template_name TEXT NOT NULL,
    scope_label TEXT NOT NULL,
    verdict_level TEXT NOT NULL,
    verdict_title TEXT NOT NULL,
    strategy_return REAL NOT NULL,
    benchmark_return REAL NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_books(
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    broker_json TEXT NOT NULL,
    stopped_session TEXT,
    stopped_at TEXT
);
CREATE TABLE IF NOT EXISTS paper_snapshots(
    book_id TEXT NOT NULL,
    session TEXT NOT NULL,
    equity REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY(book_id, session)
);
"""


class MoneyRules(BaseModel):
    capital: Decimal = Field(
        default=Decimal("1000000"), ge=Decimal("1000"), le=Decimal("10000000000")
    )
    risk_per_trade_pct: Decimal = Field(default=Decimal("1"), gt=Decimal("0"), le=Decimal("10"))
    daily_loss_limit_pct: Decimal = Field(default=Decimal("2"), gt=Decimal("0"), le=Decimal("20"))


class BrokerSettings(BaseModel):
    delivery_per_order: Decimal = Field(default=Decimal("0"), ge=0, le=1000)
    intraday_per_order: Decimal = Field(default=Decimal("20"), ge=0, le=1000)
    fno_per_order: Decimal = Field(default=Decimal("20"), ge=0, le=1000)
    dp_charge_per_sell: Decimal = Field(default=Decimal("0"), ge=0, le=1000)


class Settings(BaseModel):
    style: Literal["investor", "swing", "both"] | None = None
    money: MoneyRules = Field(default_factory=MoneyRules)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    theme: Literal["system", "light", "dark"] = "system"
    data_folder: str | None = None
    onboarding_complete: bool = False
    disclaimer_accepted_at: str | None = None


class Holding(BaseModel):
    id: int
    symbol: str
    quantity: int
    avg_price: Decimal
    buy_date: str
    note: str = ""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class AppState:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------------ settings

    def settings(self) -> Settings:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'settings'").fetchone()
        return Settings.model_validate_json(row["value"]) if row else Settings()

    def save_settings(self, settings: Settings) -> Settings:
        validated = Settings.model_validate(settings.model_dump())
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES ('settings', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (validated.model_dump_json(),),
            )
        return validated

    def update_settings(self, patch: dict[str, Any]) -> Settings:
        current = self.settings().model_dump(mode="json")
        merged = _deep_merge(current, patch)
        return self.save_settings(Settings.model_validate(merged))

    # ----------------------------------------------------------------------- watchlist

    def watchlist(self) -> list[str]:
        with self._connect() as conn:
            return [
                str(r["symbol"])
                for r in conn.execute("SELECT symbol FROM watchlist ORDER BY added_at")
            ]

    def add_to_watchlist(self, symbol: str) -> list[str]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist(symbol, added_at) VALUES (?, ?)",
                (symbol.strip().upper(), _now()),
            )
        return self.watchlist()

    def remove_from_watchlist(self, symbol: str) -> list[str]:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol.strip().upper(),))
        return self.watchlist()

    # ------------------------------------------------------------------------ holdings

    def holdings(self) -> list[Holding]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM holdings ORDER BY symbol, buy_date, id").fetchall()
        return [
            Holding(
                id=int(r["id"]),
                symbol=str(r["symbol"]),
                quantity=int(r["quantity"]),
                avg_price=Decimal(str(r["avg_price"])),
                buy_date=str(r["buy_date"]),
                note=str(r["note"]),
            )
            for r in rows
        ]

    def add_holding(
        self, symbol: str, quantity: int, avg_price: Decimal, buy_date: str, note: str
    ) -> Holding:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO holdings(symbol, quantity, avg_price, buy_date, note, created_at) VALUES (?,?,?,?,?,?)",
                (symbol.strip().upper(), quantity, str(avg_price), buy_date, note, _now()),
            )
            holding_id = int(cursor.lastrowid or 0)
        return next(h for h in self.holdings() if h.id == holding_id)

    def update_holding(
        self, holding_id: int, quantity: int, avg_price: Decimal, buy_date: str, note: str
    ) -> Holding | None:
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "UPDATE holdings SET quantity = ?, avg_price = ?, buy_date = ?, note = ? WHERE id = ?",
                (quantity, str(avg_price), buy_date, note, holding_id),
            ).rowcount
        if not changed:
            return None
        return next(h for h in self.holdings() if h.id == holding_id)

    def delete_holding(self, holding_id: int) -> bool:
        with self._lock, self._connect() as conn:
            return conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,)).rowcount > 0

    # ------------------------------------------------------------------------ lab runs

    def lab_run_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM lab_runs").fetchone()[0])

    def save_lab_run(self, result: dict[str, Any]) -> str:
        run_id = uuid.uuid4().hex[:12]
        scope = result["scope"]
        if scope["kind"] == "universe":
            scope_label = str(scope.get("universe_label") or scope.get("universe"))
        else:
            scope_label = ", ".join(scope.get("requested") or [])
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO lab_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    _now(),
                    result["template"]["id"],
                    result["template"]["name"],
                    scope_label,
                    result["verdict"]["level"],
                    result["verdict"]["title"],
                    float(result["strategy"]["total_return"]),
                    float(result["benchmark"]["total_return"]),
                    result["period"]["start"],
                    result["period"]["end"],
                    json.dumps(result, separators=(",", ":")),
                ),
            )
        return run_id

    def lab_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, template_id, template_name, scope_label, verdict_level, "
                "verdict_title, strategy_return, benchmark_return, period_start, period_end "
                "FROM lab_runs ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def lab_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, created_at, result_json FROM lab_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        result: dict[str, Any] = json.loads(row["result_json"])
        result["id"] = row["id"]
        result["created_at"] = row["created_at"]
        return result

    # ---------------------------------------------------------------------- paper books
    #
    # Paper books are stopped, never deleted, and the equity recorded for each session is written once
    # and never replaced: if the provider later re-adjusts history, the book can say its past moved.

    def create_paper_book(self, name: str, spec: dict[str, Any], broker: dict[str, Any]) -> str:
        book_id = uuid.uuid4().hex[:12]
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO paper_books(id, name, created_at, spec_json, broker_json) "
                "VALUES (?,?,?,?,?)",
                (
                    book_id,
                    name,
                    _now(),
                    json.dumps(spec, separators=(",", ":")),
                    json.dumps(broker, separators=(",", ":")),
                ),
            )
        return book_id

    def paper_books(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_books ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
        return [self._paper_row(r) for r in rows]

    def paper_book(self, book_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM paper_books WHERE id = ?", (book_id,)).fetchone()
        return self._paper_row(row) if row is not None else None

    @staticmethod
    def _paper_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "spec": json.loads(row["spec_json"]),
            "broker": json.loads(row["broker_json"]),
            "stopped_session": row["stopped_session"],
            "stopped_at": row["stopped_at"],
        }

    def stop_paper_book(self, book_id: str, session: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE paper_books SET stopped_session = ?, stopped_at = ? "
                "WHERE id = ? AND stopped_session IS NULL",
                (session, _now(), book_id),
            )
        return cursor.rowcount > 0

    def paper_snapshots(self, book_id: str) -> dict[str, float]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session, equity FROM paper_snapshots WHERE book_id = ?", (book_id,)
            ).fetchall()
        return {str(r["session"]): float(r["equity"]) for r in rows}

    def record_paper_snapshots(self, book_id: str, equity_by_session: dict[str, float]) -> None:
        """Record each session's equity the first time it is seen. Existing rows are never replaced."""
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO paper_snapshots VALUES (?,?,?,?)",
                [(book_id, d, e, _now()) for d, e in sorted(equity_by_session.items())],
            )


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
