import sqlite3
from collections.abc import AsyncGenerator

import aiosqlite
import duckdb

from quant_system.shariah.core.config import settings

SQLITE_PRAGMAS = [
    "PRAGMA journal_mode = WAL;",
    "PRAGMA synchronous = NORMAL;",
    "PRAGMA cache_size = -64000;",
    "PRAGMA temp_store = MEMORY;",
    "PRAGMA mmap_size = 268435456;",
    "PRAGMA foreign_keys = ON;",
]


def get_db_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Synchronous SQLite connection configured with WAL mode and high performance pragmas."""
    path = db_path if db_path is not None else str(settings.SQLITE_DB_PATH)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    for pragma in SQLITE_PRAGMAS:
        try:
            cursor.execute(pragma)
        except Exception:
            pass
    cursor.close()
    return conn


async def get_async_db(db_path: str | None = None) -> AsyncGenerator[aiosqlite.Connection, None]:
    """FastAPI async dependency yielding an aiosqlite connection with WAL mode configured."""
    path = db_path if db_path is not None else str(settings.SQLITE_DB_PATH)
    async with aiosqlite.connect(path, timeout=30.0) as conn:
        conn.row_factory = aiosqlite.Row
        for pragma in SQLITE_PRAGMAS:
            try:
                await conn.execute(pragma)
            except Exception:
                pass
        yield conn


def get_duckdb_connection(
    duckdb_path: str | None = None, attach_sqlite: bool = True
) -> duckdb.DuckDBPyConnection:
    """DuckDB connection helper for fast vectorized in-process analytical aggregations."""
    path = duckdb_path if duckdb_path is not None else str(settings.DUCKDB_PATH)
    conn = duckdb.connect(path)
    if attach_sqlite:
        sqlite_file = str(settings.SQLITE_DB_PATH).replace("\\", "/")
        try:
            # Attach SQLite database if not already attached
            conn.execute(f"ATTACH IF NOT EXISTS '{sqlite_file}' AS sqlite_db (TYPE SQLITE);")
        except Exception:
            pass
    return conn
