import aiosqlite
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path
from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.schemas.basket import (
    BasketSummary,
    BasketDetail,
    BasketExportRequest,
    BasketExportResponse,
)
from quant_system.shariah.services.basket_service import get_all_baskets, get_basket_by_id
from quant_system.shariah.services.broker_export_service import export_basket_orders

router = APIRouter(prefix="/baskets", tags=["Curated Thematic Baskets & Broker Export"])


@router.get(
    "",
    response_model=List[BasketSummary],
    summary="List Curated Thematic Baskets",
    description="Returns high-level metadata, constituent weights, and financial tear-sheet metrics for all 4 institutional baskets.",
)
async def list_baskets(
    db: aiosqlite.Connection = Depends(get_async_db),
):
    return await get_all_baskets(db)


@router.get(
    "/{basket_id}",
    response_model=BasketDetail,
    summary="Get Detailed Basket Tear-Sheet",
    description="Returns detailed financial tear-sheet, constituents with real-time valuation, sector allocation, and rebalancing logs.",
)
async def get_basket(
    basket_id: str = Path(..., description="Unique basket identifier (e.g. halal-tech-giants)"),
    db: aiosqlite.Connection = Depends(get_async_db),
):
    basket = await get_basket_by_id(basket_id, db)
    if not basket:
        raise HTTPException(
            status_code=404,
            detail=f"Basket '{basket_id}' not found. Available baskets: halal-tech-giants, shariah-high-growth-champions, green-ethical-infrastructure, nifty-shariah-25.",
        )
    return basket


@router.post(
    "/{basket_id}/export",
    response_model=BasketExportResponse,
    summary="Export 1-Click Indian Broker Order Sheet",
    description="Converts target investment capital into constituent share quantities and generates batch order sheets for Zerodha (CNC), Upstox (Delivery), Groww (Buy), or AngelOne.",
)
async def export_basket(
    basket_id: str = Path(..., description="Unique basket identifier"),
    request: BasketExportRequest = ...,
    db: aiosqlite.Connection = Depends(get_async_db),
):
    try:
        export_result = await export_basket_orders(basket_id, request, db)
        if not export_result:
            raise HTTPException(
                status_code=404,
                detail=f"Basket '{basket_id}' not found.",
            )
        return export_result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


from pydantic import BaseModel, Field

class TaxCalculationRequest(BaseModel):
    investment_amount: float = Field(..., gt=0, description="Gross investment capital in INR")
    broker: str = Field("Zerodha", description="Indian discount broker (Zerodha, Groww, Upstox, AngelOne)")
    exchange: str = Field("NSE", description="Stock exchange (NSE or BSE)")

class TaxCalculationResponse(BaseModel):
    investment_amount: float
    broker: str
    exchange: str
    brokerage: float
    stt_ctt: float
    exchange_charges: float
    sebi_charges: float
    stamp_duty: float
    gst: float
    total_statutory_charges: float
    estimated_dividend_purification_ratio: float
    net_effective_cost: float
    effective_tax_rate_pct: float

@router.post(
    "/tax-calculator",
    response_model=TaxCalculationResponse,
    summary="Indian Statutory Tax & Brokerage Calculator",
    description="Calculates exact SEBI turnover charges, STT, stamp duty, GST, and purification deductions for delivery CNC equity orders.",
)
async def calculate_statutory_taxes(payload: TaxCalculationRequest):
    turnover = payload.investment_amount
    brokerage = 0.0  # Zero brokerage on delivery CNC across major discount brokers
    stt = round(turnover * 0.001, 2)  # 0.1% on delivery
    ex_rate = 0.0000325 if payload.exchange.upper() == "NSE" else 0.0000375
    exchange_charges = round(turnover * ex_rate, 2)
    sebi_charges = round(turnover * 0.000001, 2)  # Rs 10 per crore
    stamp_duty = round(turnover * 0.00015, 2)  # 0.015% on buy
    gst = round((brokerage + exchange_charges + sebi_charges) * 0.18, 2)
    total_charges = round(stt + exchange_charges + sebi_charges + stamp_duty + gst, 2)
    net_cost = round(turnover + total_charges, 2)
    tax_rate = round((total_charges / turnover) * 100, 3)

    return TaxCalculationResponse(
        investment_amount=turnover,
        broker=payload.broker,
        exchange=payload.exchange.upper(),
        brokerage=brokerage,
        stt_ctt=stt,
        exchange_charges=exchange_charges,
        sebi_charges=sebi_charges,
        stamp_duty=stamp_duty,
        gst=gst,
        total_statutory_charges=total_charges,
        estimated_dividend_purification_ratio=0.0042,
        net_effective_cost=net_cost,
        effective_tax_rate_pct=tax_rate,
    )

