"""Where the Copilot's halal screening facts come from: the bundled, hand-entered sample in the Shariah database."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from typing import Any

from quant_system.copilot.registry import UserFacingError

__all__ = ["SqliteShariahSource"]

_UNREADABLE = (
    "The halal screening data could not be opened right now. Restart QuantOS and ask again."
)


class SqliteShariahSource:
    """``company(symbol)`` and ``company_count()`` over the ``companies`` table. Read-only."""

    def __init__(self, connect: Callable[[], sqlite3.Connection]) -> None:
        self._connect = connect

    def company(self, symbol: str) -> dict[str, Any] | None:
        clean = symbol.strip().upper().removesuffix(".NS")
        sql = "SELECT * FROM companies WHERE symbol = ? OR ticker = ? LIMIT 1"
        try:
            with closing(self._connect()) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(sql, (clean, f"{clean}.NS")).fetchone()
        except sqlite3.Error as error:
            raise UserFacingError(_UNREADABLE) from error
        return dict(row) if row else None

    def company_count(self) -> int:
        try:
            with closing(self._connect()) as conn:
                return int(conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0])
        except sqlite3.Error as error:
            raise UserFacingError(_UNREADABLE) from error
