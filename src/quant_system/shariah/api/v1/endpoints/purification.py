import aiosqlite
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.schemas.purification import (
    PurificationCalculateRequest,
    PurificationCalculateResponse,
    PurificationLedgerCreate,
    PurificationLedgerEntry,
    PurificationLedgerListResponse,
    PurificationReceipt,
)
from quant_system.shariah.services.purification_service import (
    calculate_dividend_purification,
    add_purification_ledger_entry,
    verify_ledger_chain,
    get_purification_receipt_by_id,
    ensure_ledger_table,
    get_latest_ledger_hash,
)

router = APIRouter(prefix="/purification", tags=["Dividend Purification & Cryptographic Ledger"])


@router.post(
    "/calculate",
    response_model=PurificationCalculateResponse,
    summary="Calculate Dividend Purification Breakdown",
    description="Calculates exact impermissible interest portion to be donated to charity based on company's non-operating income ratio.",
)
async def calculate_purification(
    request: PurificationCalculateRequest,
    db: aiosqlite.Connection = Depends(get_async_db),
):
    try:
        return await calculate_dividend_purification(
            ticker=request.ticker,
            dividend_amount=request.dividend_amount,
            shares_held=request.shares_held,
            db=db,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get(
    "/ledger",
    response_model=PurificationLedgerListResponse,
    summary="List Local Purification Ledger Entries",
    description="Returns recorded dividend purification events with SHA-256 cryptographic chain verification.",
)
async def list_ledger(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: aiosqlite.Connection = Depends(get_async_db),
):
    await ensure_ledger_table(db)
    
    # Check chain integrity
    audit = await verify_ledger_chain(db)
    latest_hash = await get_latest_ledger_hash(db)
    
    # Query rows
    count_cursor = await db.execute("SELECT COUNT(*) as total FROM purification_ledger;")
    count_row = await count_cursor.fetchone()
    total = count_row["total"] if count_row else 0
    
    sql = "SELECT * FROM purification_ledger ORDER BY id DESC LIMIT ? OFFSET ?;"
    cursor = await db.execute(sql, (limit, offset))
    rows = await cursor.fetchall()
    
    items = []
    for r in rows:
        items.append(
            PurificationLedgerEntry(
                id=r["id"],
                entry_uuid=r["entry_uuid"],
                ticker=r["ticker"],
                company_name=r["company_name"],
                record_date=r["record_date"],
                payment_date=r["payment_date"],
                shares_held=r["shares_held"],
                dps_inr=float(r["dps_inr"]),
                gross_dividend=float(r["gross_dividend"]),
                purification_ratio=float(r["purification_ratio"]),
                purification_payable=float(r["purification_payable"]),
                net_permissible_dividend=float(r["net_permissible_dividend"]),
                charity_name=r["charity_name"],
                disbursement_status=r["disbursement_status"],
                notes=r["notes"],
                prev_entry_hash=r["prev_entry_hash"],
                entry_hash=r["entry_hash"],
                timestamp=str(r["timestamp"]),
            )
        )
        
    return PurificationLedgerListResponse(
        total_entries=total,
        is_chain_valid=bool(audit["is_valid"]),
        latest_entry_hash=latest_hash,
        items=items,
    )


@router.post(
    "/ledger",
    response_model=PurificationLedgerEntry,
    status_code=201,
    summary="Record Entry into Immutable Purification Ledger",
    description="Records a declared dividend event into the local SQLite ledger, chained with an immutable SHA-256 cryptographic hash.",
)
async def create_ledger_entry(
    entry_data: PurificationLedgerCreate,
    db: aiosqlite.Connection = Depends(get_async_db),
):
    try:
        return await add_purification_ledger_entry(entry_data, db)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get(
    "/ledger/verify",
    summary="Cryptographic Chain Audit & Tamper Detection",
    description="Traverses the sequential SHA-256 hash chain from genesis to detect unauthorized modifications or data tampering.",
)
async def verify_chain(
    db: aiosqlite.Connection = Depends(get_async_db),
):
    return await verify_ledger_chain(db)


@router.get(
    "/receipt/{entry_id}",
    response_model=PurificationReceipt,
    summary="Generate Printable Charity & Tax Receipt",
    description="Retrieves a ledger entry by ID or UUID and generates a printable donation receipt with cryptographic verification hash.",
)
async def get_receipt(
    entry_id: str = Path(..., description="Ledger row ID or UUID string"),
    db: aiosqlite.Connection = Depends(get_async_db),
):
    receipt = await get_purification_receipt_by_id(entry_id, db)
    if not receipt:
        raise HTTPException(
            status_code=404,
            detail=f"Purification ledger entry '{entry_id}' not found.",
        )
    return receipt
