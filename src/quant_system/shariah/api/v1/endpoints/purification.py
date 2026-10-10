from typing import Any

import aiosqlite
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
    add_purification_ledger_entry,
    calculate_dividend_purification,
    ensure_ledger_table,
    get_latest_ledger_hash,
    get_purification_receipt_by_id,
    ledger_entry_from_row,
    verify_ledger_chain,
)

router = APIRouter(prefix="/purification", tags=["Dividend Purification & Cryptographic Ledger"])


@router.post(
    "/calculate",
    response_model=PurificationCalculateResponse,
    summary="Calculate Dividend Purification Breakdown",
    description=(
        "Works out the part of a dividend that comes from impermissible income and is to be given away, "
        "using the company's ratio from the sample."
    ),
)
async def calculate_purification(
    request: PurificationCalculateRequest,
    db: aiosqlite.Connection = Depends(get_async_db),
) -> PurificationCalculateResponse:
    try:
        return await calculate_dividend_purification(
            ticker=request.ticker,
            dividend_amount=request.dividend_amount,
            shares_held=request.shares_held,
            db=db,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve


@router.get(
    "/ledger",
    response_model=PurificationLedgerListResponse,
    summary="List Local Purification Ledger Entries",
    description="Returns the recorded purification entries and whether their SHA-256 chain still checks out.",
)
async def list_ledger(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: aiosqlite.Connection = Depends(get_async_db),
) -> PurificationLedgerListResponse:
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

    items = [ledger_entry_from_row(dict(r)) for r in rows]

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
    summary="Record Entry in the Purification Ledger",
    description=(
        "Records a declared dividend event in the local ledger, chained to the entry before it with a "
        "SHA-256 hash (hash version 2), so a later edit to it is detected."
    ),
)
async def create_ledger_entry(
    entry_data: PurificationLedgerCreate,
    db: aiosqlite.Connection = Depends(get_async_db),
) -> PurificationLedgerEntry:
    try:
        return await add_purification_ledger_entry(entry_data, db)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve


@router.get(
    "/ledger/verify",
    summary="Check the Ledger Chain for Later Edits",
    description=(
        "Walks the hash chain from the first entry and reports the first entry that was edited after it was "
        "written. Each entry is checked with the hash version that wrote it."
    ),
)
async def verify_chain(
    db: aiosqlite.Connection = Depends(get_async_db),
) -> dict[str, Any]:
    return await verify_ledger_chain(db)


@router.get(
    "/receipt/{entry_id}",
    response_model=PurificationReceipt,
    summary="Generate Printable Charity & Tax Receipt",
    description=(
        "Retrieves a ledger entry by ID or UUID and writes a printable donation receipt that shows its hash "
        "and hash version."
    ),
)
async def get_receipt(
    entry_id: str = Path(..., description="Ledger row ID or UUID string"),
    db: aiosqlite.Connection = Depends(get_async_db),
) -> PurificationReceipt:
    receipt = await get_purification_receipt_by_id(entry_id, db)
    if not receipt:
        raise HTTPException(
            status_code=404,
            detail=f"Purification ledger entry '{entry_id}' not found.",
        )
    return receipt
