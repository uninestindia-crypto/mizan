"""The hand-entered sample rows, read without ever writing to the database.

The sample is what QuantOS screened from before it read real filings. It is still used as the fallback for a stock
with no filing and as the comparison for one that has a filing. A database that cannot be read is the same as no
sample: the proof then rests on the filing alone.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any, Protocol

__all__ = ["SampleRows", "SampleSource"]

logger = logging.getLogger(__name__)


class SampleSource(Protocol):
    def company(self, symbol: str) -> dict[str, Any] | None: ...


class SampleRows:
    """``company(symbol)`` over the ``companies`` table of the bundled Shariah database. Read only."""

    def __init__(self, path: Callable[[], Path]) -> None:
        self._path = path

    def company(self, symbol: str) -> dict[str, Any] | None:
        clean = symbol.strip().upper().removesuffix(".NS")
        try:
            location = Path(self._path()).resolve()
            with closing(sqlite3.connect(f"{location.as_uri()}?mode=ro", uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                sql = "SELECT * FROM companies WHERE symbol = ? OR ticker = ? LIMIT 1"
                row = conn.execute(sql, (clean, f"{clean}.NS")).fetchone()
        except (sqlite3.Error, OSError):
            logger.warning("the halal sample could not be read", exc_info=True)
            return None
        return dict(row) if row else None
