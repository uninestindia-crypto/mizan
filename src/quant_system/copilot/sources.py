"""Where the Copilot's halal screening facts come from: the bundled, hand-entered sample in the Shariah database."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from typing import Any

from quant_system.copilot.registry import ShariahSource, UserFacingError

__all__ = ["ProofBackedShariahSource", "SqliteShariahSource"]

_UNREADABLE = "The halal screening data could not be opened right now. Close QuantOS, open it again and ask once more."


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


class ProofBackedShariahSource:
    """The sample rows, plus ``proof(symbol)``: the Shariah engine's proof from the company's own filing.

    The sample methods pass straight through. ``proof`` is asked first by the halal screening tool; when it cannot
    answer, the tool falls back to the sample, so a missing filing never leaves a stock unscreened by accident.
    """

    def __init__(self, sample: ShariahSource, proof: Callable[[str], dict[str, Any]]) -> None:
        self._sample = sample
        self._proof = proof

    def company(self, symbol: str) -> dict[str, Any] | None:
        return self._sample.company(symbol)

    def company_count(self) -> int:
        return self._sample.company_count()

    def proof(self, symbol: str) -> dict[str, Any]:
        return self._proof(symbol)
