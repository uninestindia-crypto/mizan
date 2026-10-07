import re
from typing import Any

import aiosqlite

from quant_system.shariah.schemas.company import ComplianceStatus, SearchSuggestion


def sanitize_fts_query(query: str) -> str:
    """Clean and sanitize search input to prevent FTS5 syntax errors and construct prefix match.
    Quotes each token to neutralize boolean operators (AND, OR, NOT, NEAR) and syntax characters.
    """
    if not query:
        return ""
    # Replace non-alphanumeric characters with spaces to avoid punctuation syntax errors
    clean = re.sub(r"[^\w\s]", " ", query).strip()
    if not clean:
        return ""
    words = clean.split()
    tokens = []
    for w in words:
        # Quote every token so reserved words (OR, AND, NOT, NEAR) are treated as literals
        # In FTS5, "token"* searches for prefix match on literal "token"
        safe_word = w.replace('"', '""')
        tokens.append(f'"{safe_word}"*')
    return " ".join(tokens)


async def search_companies_fts(
    db: aiosqlite.Connection,
    query: str,
    standard: str = "aaoifi",
    limit: int = 15,
) -> list[SearchSuggestion]:
    """Search by name or symbol using the SQLite full-text index with prefix matching."""
    fts_match = sanitize_fts_query(query)

    if not fts_match:
        # Fallback to top companies by market cap
        sql = """
            SELECT ticker, symbol, company_name, isin, sector, industry, current_price,
                   aaoifi_status, tasis_status
            FROM companies
            ORDER BY market_cap DESC
            LIMIT ?;
        """
        cursor = await db.execute(sql, (limit,))
        rows = await cursor.fetchall()
    else:
        # FTS5 query with rowid join for ultra-fast index lookup
        sql = """
            SELECT c.ticker, c.symbol, c.company_name, c.isin, c.sector, c.industry, c.current_price,
                   c.aaoifi_status, c.tasis_status
            FROM companies_fts f
            JOIN companies c ON f.rowid = c.rowid
            WHERE companies_fts MATCH ?
            ORDER BY rank
            LIMIT ?;
        """
        try:
            cursor = await db.execute(sql, (fts_match, limit))
            rows = await cursor.fetchall()
        except Exception:
            # Fallback to LIKE if FTS expression has any syntax conflict
            like_pat = f"%{query.strip()}%"
            fallback_sql = """
                SELECT ticker, symbol, company_name, isin, sector, industry, current_price,
                       aaoifi_status, tasis_status
                FROM companies
                WHERE ticker LIKE ? OR symbol LIKE ? OR company_name LIKE ?
                ORDER BY market_cap DESC
                LIMIT ?;
            """
            cursor = await db.execute(fallback_sql, (like_pat, like_pat, like_pat, limit))
            rows = await cursor.fetchall()

    results = []
    for r in rows:
        results.append(
            SearchSuggestion(
                ticker=r["ticker"],
                symbol=r["symbol"],
                company_name=r["company_name"],
                isin=r["isin"],
                sector=r["sector"],
                industry=r["industry"],
                current_price=float(r["current_price"]),
                aaoifi_status=ComplianceStatus(r["aaoifi_status"]),
                tasis_status=ComplianceStatus(r["tasis_status"]),
            )
        )
    return results


async def filter_companies(
    db: aiosqlite.Connection,
    query: str | None = None,
    sector: str | None = None,
    status: str | None = None,
    standard: str = "aaoifi",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Filter, search, and paginate the company universe."""
    where_clauses = []
    params = []

    use_fts = False
    fts_match = ""
    like_pat = ""

    if query and query.strip():
        fts_match = sanitize_fts_query(query)
        like_pat = f"%{query.strip()}%"
        if fts_match:
            use_fts = True
            where_clauses.append(
                "c.rowid IN (SELECT rowid FROM companies_fts WHERE companies_fts MATCH ?)"
            )
            params.append(fts_match)
        else:
            where_clauses.append("(c.ticker LIKE ? OR c.symbol LIKE ? OR c.company_name LIKE ?)")
            params.extend([like_pat, like_pat, like_pat])

    if sector and sector.strip() and sector.lower() != "all":
        where_clauses.append("LOWER(c.sector) = LOWER(?)")
        params.append(sector.strip())

    status_col = "tasis_status" if standard.lower() == "tasis" else "aaoifi_status"
    if status and status.strip() and status.upper() != "ALL":
        where_clauses.append(f"c.{status_col} = ?")
        params.append(status.upper().strip())

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    try:
        # Count total matching
        count_sql = f"SELECT COUNT(*) as total FROM companies c {where_sql};"
        cursor = await db.execute(count_sql, tuple(params))
        count_row = await cursor.fetchone()
        total = count_row["total"] if count_row else 0

        # Fetch paginated rows
        fetch_sql = f"""
            SELECT c.*
            FROM companies c
            {where_sql}
            ORDER BY c.market_cap DESC
            LIMIT ? OFFSET ?;
        """
        fetch_params = list(params) + [limit, offset]
        cursor = await db.execute(fetch_sql, tuple(fetch_params))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows], total
    except Exception:
        # Resilient fallback to standard SQL LIKE query if FTS expression encountered any unexpected operational issue
        if use_fts:
            fallback_where_clauses = []
            fallback_params = []
            fallback_where_clauses.append(
                "(c.ticker LIKE ? OR c.symbol LIKE ? OR c.company_name LIKE ?)"
            )
            fallback_params.extend([like_pat, like_pat, like_pat])
            if sector and sector.strip() and sector.lower() != "all":
                fallback_where_clauses.append("LOWER(c.sector) = LOWER(?)")
                fallback_params.append(sector.strip())
            if status and status.strip() and status.upper() != "ALL":
                fallback_where_clauses.append(f"c.{status_col} = ?")
                fallback_params.append(status.upper().strip())
            fb_where_sql = (
                f"WHERE {' AND '.join(fallback_where_clauses)}" if fallback_where_clauses else ""
            )
            count_sql = f"SELECT COUNT(*) as total FROM companies c {fb_where_sql};"
            cursor = await db.execute(count_sql, tuple(fallback_params))
            count_row = await cursor.fetchone()
            total = count_row["total"] if count_row else 0
            fetch_sql = f"""
                SELECT c.*
                FROM companies c
                {fb_where_sql}
                ORDER BY c.market_cap DESC
                LIMIT ? OFFSET ?;
            """
            fb_fetch_params = list(fallback_params) + [limit, offset]
            cursor = await db.execute(fetch_sql, tuple(fb_fetch_params))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows], total
        raise
