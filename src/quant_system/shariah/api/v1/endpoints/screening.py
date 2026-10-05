from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.schemas.company import ComplianceStatus
from quant_system.shariah.schemas.screening import (
    SAMPLE_DATA_NOTICE,
    ScreeningResponse,
    ShariahAuditResponse,
)
from quant_system.shariah.services.screener_service import (
    build_audit_evidence_lines,
    evaluate_company_shariah,
)

router = APIRouter()


async def fetch_company_by_ticker(db: aiosqlite.Connection, ticker: str) -> dict[str, Any]:
    """Helper to fetch raw company record from database by ticker or symbol."""
    clean_ticker = ticker.strip().upper()
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
            detail=f"Company with ticker or symbol '{ticker}' not found.",
        )
    return dict(row)


@router.get(
    "/stocks/{ticker}/screen",
    response_model=ScreeningResponse,
    summary="Dual-Standard Shariah Compliance Evaluation",
)
async def screen_stock(
    ticker: str,
    standard: str = Query(
        "both", description="Standard to screen against ('aaoifi', 'tasis', 'both')"
    ),
    db: aiosqlite.Connection = Depends(get_async_db),
) -> ScreeningResponse:
    """Evaluate company against AAOIFI and TASIS criteria with comparative divergence analysis."""
    company = await fetch_company_by_ticker(db, ticker)

    aaoifi_eval, tasis_eval, divergence, div_reason = evaluate_company_shariah(company)

    std_lower = standard.lower()
    if std_lower == "tasis":
        overall_status = tasis_eval.status
    elif std_lower == "aaoifi":
        overall_status = aaoifi_eval.status
    else:
        # Both standards: if either is NON_COMPLIANT, overall warning or non-compliant
        if (
            aaoifi_eval.status == ComplianceStatus.NON_COMPLIANT
            or tasis_eval.status == ComplianceStatus.NON_COMPLIANT
        ):
            overall_status = ComplianceStatus.NON_COMPLIANT
        elif (
            aaoifi_eval.status == ComplianceStatus.QUESTIONABLE
            or tasis_eval.status == ComplianceStatus.QUESTIONABLE
        ):
            overall_status = ComplianceStatus.QUESTIONABLE
        else:
            overall_status = ComplianceStatus.COMPLIANT

    return ScreeningResponse(
        ticker=company["ticker"],
        symbol=company["symbol"],
        company_name=company["company_name"],
        sector=company["sector"],
        standard_requested=standard.upper(),
        overall_status=overall_status,
        aaoifi_evaluation=aaoifi_eval,
        tasis_evaluation=tasis_eval,
        divergence=divergence,
        divergence_reason=div_reason,
        purification_ratio=float(company["purification_ratio"]),
    )


@router.get(
    "/stocks/{ticker}/audit",
    response_model=ShariahAuditResponse,
    summary="Line-Item Shariah Audit Evidence Trail",
)
async def get_shariah_audit(
    ticker: str,
    db: aiosqlite.Connection = Depends(get_async_db),
) -> ShariahAuditResponse:
    """Retrieve verified line-item audit trail with balance sheet schedules, note numbers, and filing citations."""
    company = await fetch_company_by_ticker(db, ticker)

    aaoifi_eval, tasis_eval, divergence, div_reason = evaluate_company_shariah(company)
    bs_lines, pl_lines = build_audit_evidence_lines(company)

    purif_pct = round(float(company["purification_ratio"]) * 100.0, 4)

    return ShariahAuditResponse(
        ticker=company["ticker"],
        symbol=company["symbol"],
        company_name=company["company_name"],
        isin=company["isin"],
        filing_date=company["filing_date"],
        reporting_period=company["reporting_period"],
        source_document=company.get("source_document", "Audited Financial Statements"),
        sector=company["sector"],
        sector_compliant=bool(company["sector_compliant"]),
        sector_failure_reason=company.get("sector_failure_reason"),
        aaoifi_evaluation=aaoifi_eval,
        tasis_evaluation=tasis_eval,
        divergence_noted=divergence,
        divergence_explanation=div_reason,
        purification_ratio_pct=purif_pct,
        zakatable_assets_per_share_inr=float(company["zakatable_assets_per_share"]),
        balance_sheet_lines=bs_lines,
        income_statement_lines=pl_lines,
        audit_notes=f"{SAMPLE_DATA_NOTICE} {company.get('audit_notes') or ''}".strip(),
    )
