import csv
import io
import logging
from typing import Any

import aiosqlite

from quant_system.shariah.schemas.basket import (
    BasketConstituent,
    BasketExportRequest,
    BasketExportResponse,
    BrokerOrder,
)
from quant_system.shariah.services.basket_service import get_basket_by_id

logger = logging.getLogger(__name__)

ANGEL_ONE_TOKENS: dict[str, str] = {
    "TCS": "11536",
    "INFY": "1594",
    "HCLTECH": "7229",
    "TECHM": "13538",
    "LTIM": "17818",
    "PERSISTENT": "18365",
    "TATAELXSI": "3412",
    "DEEPAKNTR": "19943",
    "PIDILITIND": "2664",
    "MARICO": "4067",
    "POLYCAB": "9590",
    "TATAPOWER": "3426",
    "THERMAX": "3477",
    "SIEMENS": "3150",
    "ABB": "13",
    "KEC": "1983",
    "HINDUNILVR": "1394",
    "SUNPHARMA": "3351",
    "CIPLA": "694",
    "DRREDDY": "881",
}


def allocate_capital_to_basket(
    constituents: list[BasketConstituent],
    capital: float,
    enforce_min_one_share: bool = True,
) -> tuple[list[dict[str, Any]], float, float, list[str]]:
    """
    Capital Allocation Engine:
    Converts target capital into constituent share quantities based on basket weights.
    Applies minimum 1 share floor when target allocation < share price, reporting warnings.
    """
    if capital <= 0.0:
        raise ValueError("Capital must be strictly positive (> 0).")

    orders_data: list[dict[str, Any]] = []
    warnings: list[str] = []
    total_cost = 0.0

    for c in constituents:
        sym = c.symbol
        price = float(c.current_price or 1000.0)
        weight = float(c.weight)
        alloc_amt = capital * weight
        shares = int(alloc_amt // price)

        if shares == 0 and enforce_min_one_share:
            shares = 1
            warnings.append(
                f"Capital adjustment warning: Allocating minimum 1 share of {sym} (INR {price:.2f}) "
                f"exceeds target allocation (INR {alloc_amt:.2f})."
            )

        cost = shares * price
        total_cost += cost
        orders_data.append(
            {
                "ticker": c.ticker,
                "symbol": sym,
                "shares": shares,
                "price": price,
                "weight": weight,
                "allocation_amount": round(alloc_amt, 2),
                "actual_cost": round(cost, 2),
            }
        )

    residual_cash = max(0.0, round(capital - total_cost, 2))
    return orders_data, round(total_cost, 2), residual_cash, warnings


def generate_zerodha_orders(
    orders_data: list[dict[str, Any]],
    order_type: str = "MARKET",
) -> tuple[list[BrokerOrder], str, str]:
    """
    Zerodha Kite Multi-Order Format:
    Instrument,Exchange,Transaction,Quantity,Order Type,Product,Price,Trigger Price
    Product strictly CNC.
    """
    orders: list[BrokerOrder] = []
    csv_rows = [
        [
            "Instrument",
            "Exchange",
            "Transaction",
            "Quantity",
            "Order Type",
            "Product",
            "Price",
            "Trigger Price",
        ]
    ]
    clipboard_lines = []

    for o in orders_data:
        sym = o["symbol"]
        shares = o["shares"]
        price_val = 0 if order_type.upper() == "MARKET" else round(o["price"], 2)
        trigger_price = 0

        row_str = f"{sym},NSE,BUY,{shares},{order_type.upper()},CNC,{price_val},{trigger_price}"
        orders.append(
            BrokerOrder(
                symbol=sym,
                ticker=o["ticker"],
                shares=shares,
                price=o["price"],
                allocation_amount=o["allocation_amount"],
                weight=o["weight"],
                order_type=order_type.upper(),
                product="CNC",
                order_line=row_str,
            )
        )
        csv_rows.append(
            [
                sym,
                "NSE",
                "BUY",
                str(shares),
                order_type.upper(),
                "CNC",
                str(price_val),
                str(trigger_price),
            ]
        )
        clipboard_lines.append(row_str)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(csv_rows)
    csv_content = output.getvalue()
    clipboard_payload = "\n".join(clipboard_lines)
    return orders, csv_content, clipboard_payload


def generate_upstox_orders(
    orders_data: list[dict[str, Any]],
    order_type: str = "MARKET",
) -> tuple[list[BrokerOrder], str, str]:
    """
    Upstox Pro Multi-Order Format:
    Trading Symbol,Exchange,Action,Quantity,Order Type,Validity,Product
    Trading Symbol: {symbol}-EQ, Product: DELIVERY.
    """
    orders: list[BrokerOrder] = []
    csv_rows = [
        ["Trading Symbol", "Exchange", "Action", "Quantity", "Order Type", "Validity", "Product"]
    ]
    clipboard_lines = []

    for o in orders_data:
        sym = o["symbol"]
        trading_sym = f"{sym}-EQ"
        shares = o["shares"]
        row_str = f"{trading_sym},NSE,BUY,{shares},{order_type.upper()},DAY,DELIVERY"
        orders.append(
            BrokerOrder(
                symbol=sym,
                ticker=o["ticker"],
                shares=shares,
                price=o["price"],
                allocation_amount=o["allocation_amount"],
                weight=o["weight"],
                order_type=order_type.upper(),
                product="DELIVERY",
                order_line=row_str,
            )
        )
        csv_rows.append(
            [trading_sym, "NSE", "BUY", str(shares), order_type.upper(), "DAY", "DELIVERY"]
        )
        clipboard_lines.append(row_str)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(csv_rows)
    csv_content = output.getvalue()
    clipboard_payload = "\n".join(clipboard_lines)
    return orders, csv_content, clipboard_payload


def generate_groww_orders(
    orders_data: list[dict[str, Any]],
    order_type: str = "MARKET",
) -> tuple[list[BrokerOrder], str, str]:
    """
    Groww Order Export Format:
    Symbol,Exchange,Segment,TransactionType,Quantity,OrderType,ProductType,Price
    Segment: CASH, ProductType: CNC, TransactionType: BUY.
    """
    orders: list[BrokerOrder] = []
    csv_rows = [
        [
            "Symbol",
            "Exchange",
            "Segment",
            "TransactionType",
            "Quantity",
            "OrderType",
            "ProductType",
            "Price",
        ]
    ]
    clipboard_lines = []

    for o in orders_data:
        sym = o["symbol"]
        shares = o["shares"]
        price_val = 0 if order_type.upper() == "MARKET" else round(o["price"], 2)
        row_str = f"{sym},NSE,CASH,BUY,{shares},{order_type.upper()},CNC,{price_val}"
        orders.append(
            BrokerOrder(
                symbol=sym,
                ticker=o["ticker"],
                shares=shares,
                price=o["price"],
                allocation_amount=o["allocation_amount"],
                weight=o["weight"],
                order_type=order_type.upper(),
                product="CNC",
                order_line=row_str,
            )
        )
        csv_rows.append(
            [sym, "NSE", "CASH", "BUY", str(shares), order_type.upper(), "CNC", str(price_val)]
        )
        clipboard_lines.append(row_str)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(csv_rows)
    csv_content = output.getvalue()
    clipboard_payload = "\n".join(clipboard_lines)
    return orders, csv_content, clipboard_payload


def generate_angelone_orders(
    orders_data: list[dict[str, Any]],
    order_type: str = "MARKET",
) -> tuple[list[BrokerOrder], str, str]:
    """
    AngelOne SmartAPI / SuperApp Format:
    Symbol,Token,Exchange,TransactionType,OrderType,ProductType,Quantity,Price
    Symbol: {symbol}-EQ, ProductType: DELIVERY.
    """
    orders: list[BrokerOrder] = []
    csv_rows = [
        [
            "Symbol",
            "Token",
            "Exchange",
            "TransactionType",
            "OrderType",
            "ProductType",
            "Quantity",
            "Price",
        ]
    ]
    clipboard_lines = []

    for o in orders_data:
        sym = o["symbol"]
        symbol_eq = f"{sym}-EQ"
        token = ANGEL_ONE_TOKENS.get(sym, str(abs(hash(sym)) % 90000 + 1000))
        shares = o["shares"]
        price_val = 0 if order_type.upper() == "MARKET" else round(o["price"], 2)
        row_str = f"{symbol_eq},{token},NSE,BUY,{order_type.upper()},DELIVERY,{shares},{price_val}"
        orders.append(
            BrokerOrder(
                symbol=sym,
                ticker=o["ticker"],
                shares=shares,
                price=o["price"],
                allocation_amount=o["allocation_amount"],
                weight=o["weight"],
                order_type=order_type.upper(),
                product="DELIVERY",
                order_line=row_str,
            )
        )
        csv_rows.append(
            [
                symbol_eq,
                token,
                "NSE",
                "BUY",
                order_type.upper(),
                "DELIVERY",
                str(shares),
                str(price_val),
            ]
        )
        clipboard_lines.append(row_str)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(csv_rows)
    csv_content = output.getvalue()
    clipboard_payload = "\n".join(clipboard_lines)
    return orders, csv_content, clipboard_payload


async def export_basket_orders(
    basket_id: str,
    request: BasketExportRequest,
    db: aiosqlite.Connection | None = None,
) -> BasketExportResponse | None:
    """
    Main broker export orchestrator:
    1. Loads basket constituents with live market prices.
    2. Runs capital allocation engine with minimum 1-share floor.
    3. Formats batch order sheets for Zerodha, Upstox, Groww, or AngelOne.
    """
    basket_detail = await get_basket_by_id(basket_id, db)
    if not basket_detail:
        return None

    orders_data, total_allocated, residual_cash, warnings = allocate_capital_to_basket(
        constituents=basket_detail.constituents,
        capital=request.capital,
        enforce_min_one_share=True,
    )

    broker_lower = request.broker.lower().strip()
    if broker_lower == "zerodha":
        orders, csv_content, clipboard_payload = generate_zerodha_orders(
            orders_data, request.order_type
        )
    elif broker_lower == "upstox":
        orders, csv_content, clipboard_payload = generate_upstox_orders(
            orders_data, request.order_type
        )
    elif broker_lower == "groww":
        orders, csv_content, clipboard_payload = generate_groww_orders(
            orders_data, request.order_type
        )
    elif broker_lower in ("angelone", "angel", "angel_one"):
        orders, csv_content, clipboard_payload = generate_angelone_orders(
            orders_data, request.order_type
        )
    else:
        # Default to Zerodha format
        orders, csv_content, clipboard_payload = generate_zerodha_orders(
            orders_data, request.order_type
        )
        warnings.append(f"Unrecognized broker '{request.broker}'. Defaulted to Zerodha CNC format.")

    return BasketExportResponse(
        basket_id=basket_detail.id,
        basket_name=basket_detail.name,
        broker=request.broker,
        target_capital=request.capital,
        total_allocated_capital=total_allocated,
        residual_cash=residual_cash,
        order_count=len(orders),
        orders=orders,
        csv_content=csv_content,
        clipboard_payload=clipboard_payload,
        warnings=warnings,
    )
