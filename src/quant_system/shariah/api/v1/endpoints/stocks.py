from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.schemas.company import (
    BalanceSheetEvidence,
    CompanyDetail,
    CompanyProfile,
    CompanySummary,
    ComplianceStatus,
    IncomeStatementEvidence,
    SearchSuggestion,
)
from quant_system.shariah.services.search_service import filter_companies, search_companies_fts

router = APIRouter()


@router.get(
    "/stocks/search",
    response_model=list[SearchSuggestion],
    summary="Instant Search Autocomplete (<50ms)",
)
async def search_stocks(
    q: str = Query(..., min_length=1, description="Search token (e.g. 'tcs', 'tata', 'pharma')"),
    standard: str = Query(
        "aaoifi", description="Standard for compliance status ('aaoifi' or 'tasis')"
    ),
    limit: int = Query(15, ge=1, le=50),
    db: aiosqlite.Connection = Depends(get_async_db),
) -> list[SearchSuggestion]:
    """Sub-50ms instant stock search powered by SQLite FTS5 prefix matching."""
    return await search_companies_fts(db=db, query=q, standard=standard, limit=limit)


@router.get("/stocks", summary="List and Filter Stocks Universe")
async def list_stocks(
    query: str | None = Query(None, alias="q", description="Optional text search query"),
    sector: str | None = Query(None, description="Filter by sector"),
    status: str | None = Query(
        None,
        description="Filter by compliance status ('COMPLIANT', 'QUESTIONABLE', 'NON_COMPLIANT')",
    ),
    standard: str = Query(
        "aaoifi", description="Compliance standard to filter by ('aaoifi' or 'tasis')"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_async_db),
) -> dict[str, Any]:
    """List stocks with optional full-text search, sector filtering, and compliance classification."""
    rows, total = await filter_companies(
        db=db,
        query=query,
        sector=sector,
        status=status,
        standard=standard,
        limit=limit,
        offset=offset,
    )

    items = []
    for r in rows:
        items.append(
            CompanySummary(
                ticker=r["ticker"],
                symbol=r["symbol"],
                isin=r["isin"],
                bse_code=r["bse_code"],
                company_name=r["company_name"],
                sector=r["sector"],
                industry=r["industry"],
                current_price=float(r["current_price"]),
                market_cap=float(r["market_cap"]),
                avg_36m_market_cap=float(r["avg_36m_market_cap"]),
                aaoifi_status=ComplianceStatus(r["aaoifi_status"]),
                tasis_status=ComplianceStatus(r["tasis_status"]),
                purification_ratio=float(r["purification_ratio"]),
                is_nifty_50=bool(r["is_nifty_50"]),
                is_nifty_500=bool(r["is_nifty_500"]),
                aaoifi_debt_ratio=float(r["aaoifi_debt_ratio"])
                if r.get("aaoifi_debt_ratio") is not None
                else 0.0,
                aaoifi_cash_ratio=float(r["aaoifi_cash_ratio"])
                if r.get("aaoifi_cash_ratio") is not None
                else 0.0,
                tasis_debt_ratio=float(r["tasis_debt_ratio"])
                if r.get("tasis_debt_ratio") is not None
                else 0.0,
                tasis_cash_ratio=float(r["tasis_cash_ratio"])
                if r.get("tasis_cash_ratio") is not None
                else 0.0,
            )
        )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "standard_applied": standard.upper(),
        "items": items,
    }


@router.get(
    "/stocks/{ticker}",
    response_model=CompanyDetail,
    summary="Get Full Company Profile & Balance Sheet",
)
async def get_stock_detail(
    ticker: str,
    db: aiosqlite.Connection = Depends(get_async_db),
) -> CompanyDetail:
    """Retrieve full company profile, balance sheet items, income statement lines, and compliance ratings."""
    clean_ticker = ticker.strip().upper()
    # Support ticker with or without .NS
    variations = [clean_ticker, f"{clean_ticker}.NS", clean_ticker.replace(".NS", "")]
    placeholders = ", ".join("?" for _ in variations)

    sql = f"""
        SELECT * FROM companies
        WHERE UPPER(ticker) IN ({placeholders}) OR UPPER(symbol) IN ({placeholders})
        LIMIT 1;
    """
    cursor = await db.execute(sql, (*variations, *variations))
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with ticker or symbol '{ticker}' not found in universe.",
        )

    r = dict(row)

    profile = CompanyProfile(
        ticker=r["ticker"],
        symbol=r["symbol"],
        isin=r["isin"],
        bse_code=r["bse_code"],
        company_name=r["company_name"],
        sector=r["sector"],
        industry=r["industry"],
        business_summary=r["business_summary"],
        current_price=float(r["current_price"]),
        market_cap=float(r["market_cap"]),
        avg_36m_market_cap=float(r["avg_36m_market_cap"]),
        shares_outstanding=int(r["shares_outstanding"]),
        pe_ratio=float(r["pe_ratio"]) if r["pe_ratio"] is not None else None,
        pb_ratio=float(r["pb_ratio"]) if r["pb_ratio"] is not None else None,
        dividend_yield=float(r["dividend_yield"]) if r["dividend_yield"] is not None else None,
        last_dividend_per_share=float(r["last_dividend_per_share"])
        if r["last_dividend_per_share"] is not None
        else 0.0,
        filing_date=r["filing_date"],
        reporting_period=r["reporting_period"],
        source_document=r["source_document"],
        is_nifty_50=bool(r["is_nifty_50"]),
        is_nifty_500=bool(r["is_nifty_500"]),
    )

    balance_sheet = BalanceSheetEvidence(
        total_assets=float(r["total_assets"]),
        long_term_debt=float(r["long_term_debt"]),
        short_term_debt=float(r["short_term_debt"]),
        lease_liabilities=float(r["lease_liabilities"]),
        total_debt=float(r["total_debt"]),
        cash_and_bank=float(r["cash_and_bank"]),
        current_investments=float(r["current_investments"]),
        total_cash_and_investments=float(r["total_cash_and_investments"]),
        total_receivables=float(r["total_receivables"]),
        total_inventories=float(r["total_inventories"]),
        current_liabilities=float(r["current_liabilities"]),
        debt_note_ref=r["debt_note_ref"],
        cash_note_ref=r["cash_note_ref"],
        rec_note_ref=r["rec_note_ref"],
    )

    income_statement = IncomeStatementEvidence(
        operating_revenue=float(r["operating_revenue"]),
        other_income=float(r["other_income"]),
        total_revenue=float(r["total_revenue"]),
        interest_income=float(r["interest_income"]),
        prohibited_secondary_revenue=float(r["prohibited_secondary_revenue"]),
        total_impermissible_income=float(r["total_impermissible_income"]),
        income_note_ref=r["income_note_ref"],
    )

    return CompanyDetail(
        profile=profile,
        balance_sheet=balance_sheet,
        income_statement=income_statement,
        sector_compliant=bool(r["sector_compliant"]),
        sector_failure_reason=r["sector_failure_reason"],
        aaoifi_status=ComplianceStatus(r["aaoifi_status"]),
        aaoifi_debt_ratio=float(r["aaoifi_debt_ratio"]),
        aaoifi_cash_ratio=float(r["aaoifi_cash_ratio"]),
        aaoifi_rec_ratio=float(r["aaoifi_rec_ratio"]),
        aaoifi_imp_ratio=float(r["aaoifi_imp_ratio"]),
        tasis_status=ComplianceStatus(r["tasis_status"]),
        tasis_debt_ratio=float(r["tasis_debt_ratio"]),
        tasis_cash_ratio=float(r["tasis_cash_ratio"]),
        tasis_rec_ratio=float(r["tasis_rec_ratio"]),
        tasis_imp_ratio=float(r["tasis_imp_ratio"]),
        purification_ratio=float(r["purification_ratio"]),
        zakatable_assets_per_share=float(r["zakatable_assets_per_share"]),
        audit_notes=r["audit_notes"],
    )
