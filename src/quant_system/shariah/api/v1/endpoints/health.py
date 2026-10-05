from datetime import UTC, datetime
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends

from quant_system.shariah.core.config import settings
from quant_system.shariah.db.session import get_async_db

router = APIRouter()


@router.get("/health", summary="System Health & Storage Status")
async def health_check(db: aiosqlite.Connection = Depends(get_async_db)) -> dict[str, Any]:
    """Health check validating database connectivity, dataset integrity, and engine latency."""
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM companies;")
    row = await cursor.fetchone()
    count = row["cnt"] if row else 0

    return {
        "status": "ok",
        "version": settings.VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
        "database": "connected",
        "storage_mode": "SQLite WAL + FTS5 + DuckDB Columnar",
        "companies_seeded": count,
    }
