"""FastAPI endpoint for the Equity Zakat Calculator (R6)."""

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.schemas.zakat import (
    ZakatCalculateRequest,
    ZakatCalculateResponse,
)
from quant_system.shariah.services.zakat_service import calculate_equity_zakat

router = APIRouter(prefix="/zakat", tags=["Equity Zakat Calculator"])


@router.post(
    "/calculate",
    response_model=ZakatCalculateResponse,
    summary="Calculate Equity Portfolio Zakat",
    description=(
        "Calculates exact Zakat on stock portfolios using either Method 1: Active Trader (100% Net Liquidation Value) "
        "or Method 2: Long-Term Investor (Zakatable Net Working Assets per share). "
        "Calibrated against the Indian Silver Nisab threshold (₹53,550.00) with Hijri Lunar (2.500%) and Gregorian Solar (2.577%) rates."
    ),
)
async def calculate_zakat(
    request: ZakatCalculateRequest,
    db: aiosqlite.Connection = Depends(get_async_db),
) -> ZakatCalculateResponse:
    try:
        return await calculate_equity_zakat(request, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
