import aiosqlite
from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.schemas.basket import (
    BasketDetail,
    BasketExportRequest,
    BasketExportResponse,
    BasketSummary,
)
from quant_system.shariah.services.basket_service import get_all_baskets, get_basket_by_id
from quant_system.shariah.services.broker_export_service import export_basket_orders

router = APIRouter(prefix="/baskets", tags=["Curated Thematic Baskets & Broker Export"])


@router.get(
    "",
    response_model=list[BasketSummary],
    summary="List Curated Thematic Baskets",
    description=(
        "Returns each curated basket with its constituents, weights, sample prices and screening. "
        "No return or risk figure is shown because none has been computed."
    ),
)
async def list_baskets(
    db: aiosqlite.Connection = Depends(get_async_db),
) -> list[BasketSummary]:
    return await get_all_baskets(db)


@router.get(
    "/{basket_id}",
    response_model=BasketDetail,
    summary="Get Detailed Basket Tear-Sheet",
    description=(
        "Returns one basket with its constituents, sample prices, screening and sector split. "
        "The tear sheet and the rebalance history are empty until real figures exist."
    ),
)
async def get_basket(
    basket_id: str = Path(..., description="Unique basket identifier (e.g. halal-tech-giants)"),
    db: aiosqlite.Connection = Depends(get_async_db),
) -> BasketDetail:
    basket = await get_basket_by_id(basket_id, db)
    if not basket:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Basket '{basket_id}' not found. Available baskets: halal-tech-giants, "
                "shariah-high-growth-champions, green-ethical-infrastructure, nifty-shariah-25."
            ),
        )
    return basket


@router.post(
    "/{basket_id}/export",
    response_model=BasketExportResponse,
    summary="Order-sheet export (QuantOS does not place orders)",
    description=(
        "Turns an amount of capital into share counts for each stock and writes an order sheet for "
        "Zerodha (CNC), Upstox (Delivery), Groww (Buy) or AngelOne. Nothing is sent to a broker. "
        "A stock with no price is refused instead of guessed."
    ),
)
async def export_basket(
    basket_id: str = Path(..., description="Unique basket identifier"),
    request: BasketExportRequest = Body(...),
    db: aiosqlite.Connection = Depends(get_async_db),
) -> BasketExportResponse:
    try:
        export_result = await export_basket_orders(basket_id, request, db)
        if not export_result:
            raise HTTPException(
                status_code=404,
                detail=f"Basket '{basket_id}' not found.",
            )
        return export_result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve


class TaxCalculationRequest(BaseModel):
    investment_amount: float = Field(..., gt=0, description="Gross investment capital in INR")
    broker: str = Field(
        "Zerodha", description="Indian discount broker (Zerodha, Groww, Upstox, AngelOne)"
    )
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
    estimated_dividend_purification_ratio: float | None = Field(
        default=None,
        description="Not estimated: it depends on the stock, so no single figure is given",
    )
    net_effective_cost: float
    effective_tax_rate_pct: float


@router.post(
    "/tax-calculator",
    response_model=TaxCalculationResponse,
    summary="Indian Statutory Tax & Brokerage Calculator",
    description="Works out SEBI turnover charges, STT, stamp duty and GST for a delivery (CNC) equity order.",
)
async def calculate_statutory_taxes(payload: TaxCalculationRequest) -> TaxCalculationResponse:
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
        net_effective_cost=net_cost,
        effective_tax_rate_pct=tax_rate,
    )
