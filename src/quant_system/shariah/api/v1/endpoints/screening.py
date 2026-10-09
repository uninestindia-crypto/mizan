from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query, status

from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.schemas.company import ComplianceStatus
from quant_system.shariah.schemas.screening import (
    SAMPLE_DATA_NOTICE,
    ScreeningResponse,
    ShariahAuditResponse,
    StandardEvaluation,
)
from quant_system.shariah.services.screener_service import (
    build_audit_evidence_lines,
    evaluate_company_shariah,
)
from quant_system.shariah.services.transparency import build_screening_transparency
from quant_system.shariah.services.verdict_overlay import (
    evaluations_from,
    evidence_lines,
    proofs_for,
    transparency_overrides,
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


async def filing_proof_of(company: dict[str, Any]) -> dict[str, Any] | None:
    """The proof for this company when it rests on a filing, so the screen can prefer it to the sample."""
    return (await proofs_for([company["symbol"]]))[company["symbol"]]


def evaluate_preferring_filing(
    company: dict[str, Any], proof: dict[str, Any] | None
) -> tuple[StandardEvaluation, StandardEvaluation, bool, str | None]:
    """Both standards from the filing's proof when there is one, else from the sample row exactly as before."""
    return evaluations_from(proof) if proof else evaluate_company_shariah(company)


def transparency_of(company: dict[str, Any], proof: dict[str, Any] | None) -> dict[str, Any]:
    """What the screening says about itself: the sample's defaults, replaced by the filing's where it has one."""
    fields = build_screening_transparency(company).model_dump()
    return {**fields, **transparency_overrides(proof)} if proof else fields


def audit_source(company: dict[str, Any], proof: dict[str, Any] | None) -> dict[str, Any]:
    """Where an audit's figures came from: the filing's own details, or the sample row's as before."""
    if proof is None:
        return {
            "filing_date": company["filing_date"],
            "reporting_period": company["reporting_period"],
            "source_document": company.get("source_document", "Not recorded"),
            "sector_compliant": bool(company["sector_compliant"]),
            "sector_failure_reason": company.get("sector_failure_reason"),
            "audit_notes": f"{SAMPLE_DATA_NOTICE} {company.get('audit_notes') or ''}".strip(),
        }
    filing, sector = proof["filing"], proof["sector"]
    return {
        "filing_date": filing["filed_on"] or "",
        "reporting_period": filing["period_label"],
        "source_document": filing["source_url"],
        "sector_compliant": sector["status"] != "FAIL",
        "sector_failure_reason": sector.get("reason"),
        "audit_notes": proof["data_notice"],
    }


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
    proof = await filing_proof_of(company)

    aaoifi_eval, tasis_eval, divergence, div_reason = evaluate_preferring_filing(company, proof)

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

    if proof and std_lower not in ("aaoifi", "tasis"):
        # The proof's own verdict stands: when the two standards disagree it says "questionable", not "worst of".
        overall_status = ComplianceStatus(proof["verdict"])

    return ScreeningResponse(
        **transparency_of(company, proof),
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
    """Retrieve the line items behind a verdict. Each one is marked as an unverified sample."""
    company = await fetch_company_by_ticker(db, ticker)
    proof = await filing_proof_of(company)

    aaoifi_eval, tasis_eval, divergence, div_reason = evaluate_preferring_filing(company, proof)
    bs_lines, pl_lines = evidence_lines(proof) if proof else build_audit_evidence_lines(company)

    purif_pct = round(float(company["purification_ratio"]) * 100.0, 4)

    return ShariahAuditResponse(
        **transparency_of(company, proof),
        ticker=company["ticker"],
        symbol=company["symbol"],
        company_name=company["company_name"],
        isin=company["isin"],
        **audit_source(company, proof),
        sector=company["sector"],
        aaoifi_evaluation=aaoifi_eval,
        tasis_evaluation=tasis_eval,
        divergence_noted=divergence,
        divergence_explanation=div_reason,
        purification_ratio_pct=purif_pct,
        zakatable_assets_per_share_inr=float(company["zakatable_assets_per_share"]),
        balance_sheet_lines=bs_lines,
        income_statement_lines=pl_lines,
    )
