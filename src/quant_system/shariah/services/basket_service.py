"""The curated baskets: who is in them, at what weight, how each stock screens, and nothing invented.

A basket carries no return or risk figures and no rebalance history, because nobody has computed or recorded any.
Prices come only from the hand-entered sample, and are labelled as samples.
"""

import logging
from typing import Any

import aiosqlite

from quant_system.shariah.schemas.basket import (
    BasketConstituent,
    BasketDetail,
    BasketSummary,
    PriceStatus,
    SectorAllocation,
    TearSheetMetrics,
)
from quant_system.shariah.services.screener_service import evaluate_company_shariah
from quant_system.shariah.services.transparency import resolve_data_status

logger = logging.getLogger(__name__)

BASKET_DEFINITIONS: list[dict[str, Any]] = [
    {
        "id": "halal-tech-giants",
        "name": "Halal Tech Giants",
        "thesis": "World-leading Indian IT enterprises with zero net debt, export earnings, and superior ROE.",
        "category": "Information Technology & Software",
        "constituents": [
            {"ticker": "TCS.NS", "symbol": "TCS", "weight": 0.25},
            {"ticker": "INFY.NS", "symbol": "INFY", "weight": 0.25},
            {"ticker": "HCLTECH.NS", "symbol": "HCLTECH", "weight": 0.20},
            {"ticker": "TECHM.NS", "symbol": "TECHM", "weight": 0.15},
            {"ticker": "LTIM.NS", "symbol": "LTIM", "weight": 0.15},
        ],
    },
    {
        "id": "shariah-high-growth-champions",
        "name": "Shariah High-Growth Champions",
        "thesis": "High-growth Indian mid-cap leaders in specialty chemicals, engineering design, and automotive tech.",
        "category": "Mid-Cap Growth & Specialty Manufacturing",
        "constituents": [
            {"ticker": "PERSISTENT.NS", "symbol": "PERSISTENT", "weight": 0.20},
            {"ticker": "TATAELXSI.NS", "symbol": "TATAELXSI", "weight": 0.20},
            {"ticker": "DEEPAKNTR.NS", "symbol": "DEEPAKNTR", "weight": 0.20},
            {"ticker": "PIDILITIND.NS", "symbol": "PIDILITIND", "weight": 0.20},
            {"ticker": "MARICO.NS", "symbol": "MARICO", "weight": 0.20},
        ],
    },
    {
        "id": "green-ethical-infrastructure",
        "name": "Green & Ethical Infrastructure",
        "thesis": (
            "Enterprises accelerating India's clean energy, electric transmission, "
            "and environmental sustainability."
        ),
        "category": "Renewables, Clean Power & Smart Grid",
        "constituents": [
            {"ticker": "TATAPOWER.NS", "symbol": "TATAPOWER", "weight": 0.25},
            {"ticker": "THERMAX.NS", "symbol": "THERMAX", "weight": 0.20},
            {"ticker": "SIEMENS.NS", "symbol": "SIEMENS", "weight": 0.20},
            {"ticker": "ABB.NS", "symbol": "ABB", "weight": 0.20},
            {"ticker": "KEC.NS", "symbol": "KEC", "weight": 0.15},
        ],
    },
    {
        "id": "nifty-shariah-25",
        "name": "NIFTY Shariah 25 Index Basket",
        "thesis": "Core wealth compounding mirroring the top 25 Shariah-compliant large-cap leaders in NIFTY 100.",
        "category": "Large-Cap Shariah Index Compounding",
        "constituents": [
            {"ticker": "TCS.NS", "symbol": "TCS", "weight": 0.08},
            {"ticker": "INFY.NS", "symbol": "INFY", "weight": 0.08},
            {"ticker": "HINDUNILVR.NS", "symbol": "HINDUNILVR", "weight": 0.07},
            {"ticker": "SUNPHARMA.NS", "symbol": "SUNPHARMA", "weight": 0.06},
            {"ticker": "CIPLA.NS", "symbol": "CIPLA", "weight": 0.05},
            {"ticker": "DRREDDY.NS", "symbol": "DRREDDY", "weight": 0.04},
        ],
    },
]

UNKNOWN_SECTOR = "Not in the sample"


async def _load_rows(
    entries: list[dict[str, Any]], db: aiosqlite.Connection | None
) -> dict[str, dict[str, Any]]:
    """The screening rows of the basket's stocks that are in the sample, by ticker."""
    if db is None:
        return {}
    tickers = [entry["ticker"] for entry in entries]
    placeholders = ",".join("?" for _ in tickers)
    try:
        cursor = await db.execute(
            f"SELECT * FROM companies WHERE ticker IN ({placeholders});", tuple(tickers)
        )
        return {row["ticker"]: dict(row) for row in await cursor.fetchall()}
    except Exception as error:
        logger.warning("Could not read the sample rows for a basket: %s", error)
        return {}


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _constituent(entry: dict[str, Any], row: dict[str, Any] | None) -> BasketConstituent:
    ticker = entry["ticker"]
    symbol = entry.get("symbol") or ticker.replace(".NS", "")
    weight = float(entry["weight"])
    if row is None:
        return BasketConstituent(ticker=ticker, symbol=symbol, company_name=symbol, weight=weight)
    aaoifi, tasis, _, _ = evaluate_company_shariah(row)
    return BasketConstituent(
        ticker=ticker,
        symbol=symbol,
        company_name=row["company_name"],
        sector=row["sector"],
        weight=weight,
        current_price=_optional_float(row["current_price"]),
        market_cap=_optional_float(row["market_cap"]),
        price_status=PriceStatus.SAMPLE,
        aaoifi_status=aaoifi.status,
        tasis_status=tasis.status,
        data_status=resolve_data_status(row),
    )


def _weighted_average(
    entries: list[dict[str, Any]], rows: dict[str, dict[str, Any]], column: str
) -> float | None:
    """The basket's weighted figure from the screening rows, or None if any stock has no row."""
    pairs = [
        (float(e["weight"]), _optional_float((rows.get(e["ticker"]) or {}).get(column)))
        for e in entries
    ]
    known = [(weight, value) for weight, value in pairs if value is not None]
    total_weight = sum(weight for weight, _ in known)
    if not known or len(known) != len(pairs) or total_weight <= 0.0:
        return None
    return round(sum(weight * value for weight, value in known) / total_weight, 10)


def _sample_totals(constituents: list[BasketConstituent]) -> tuple[float | None, float | None]:
    """One share of each stock, and the weighted sum of the prices, or None if any price is missing."""
    priced = [(c.weight, c.current_price) for c in constituents if c.current_price is not None]
    if not priced or len(priced) != len(constituents):
        return None, None
    return round(sum(price for _, price in priced), 2), round(sum(w * p for w, p in priced), 2)


def _compute_sector_allocations(constituents: list[BasketConstituent]) -> list[SectorAllocation]:
    """Aggregates weights by sector for breakdown."""
    sector_weights: dict[str, float] = {}
    for c in constituents:
        sector = c.sector or UNKNOWN_SECTOR
        sector_weights[sector] = sector_weights.get(sector, 0.0) + c.weight
    allocations = [
        SectorAllocation(sector=sector, weight=round(w, 4), weight_pct=round(w * 100.0, 2))
        for sector, w in sector_weights.items()
    ]
    allocations.sort(key=lambda allocation: allocation.weight, reverse=True)
    return allocations


async def _basket_fields(
    definition: dict[str, Any], db: aiosqlite.Connection | None
) -> dict[str, Any]:
    entries = definition["constituents"]
    rows = await _load_rows(entries, db)
    constituents = [_constituent(entry, rows.get(entry["ticker"])) for entry in entries]
    minimum_investment, latest_valuation = _sample_totals(constituents)
    return {
        "id": definition["id"],
        "name": definition["name"],
        "thesis": definition["thesis"],
        "category": definition["category"],
        "constituent_count": len(constituents),
        "dividend_yield": _weighted_average(entries, rows, "dividend_yield"),
        "weighted_purification_ratio": _weighted_average(entries, rows, "purification_ratio"),
        "minimum_investment": minimum_investment,
        "latest_valuation": latest_valuation,
        "constituents": constituents,
    }


async def get_all_baskets(db: aiosqlite.Connection | None = None) -> list[BasketSummary]:
    """Returns all 4 curated baskets with their constituents, weights and sample screening."""
    return [BasketSummary(**await _basket_fields(d, db)) for d in BASKET_DEFINITIONS]


async def get_basket_by_id(
    basket_id: str, db: aiosqlite.Connection | None = None
) -> BasketDetail | None:
    """Returns one basket with its constituents, sector split and an honest empty tear sheet and history."""
    definition = next((b for b in BASKET_DEFINITIONS if b["id"] == basket_id.lower().strip()), None)
    if definition is None:
        return None
    fields = await _basket_fields(definition, db)
    tear_sheet = TearSheetMetrics(
        dividend_yield=fields["dividend_yield"],
        weighted_purification_ratio=fields["weighted_purification_ratio"],
    )
    return BasketDetail(
        **fields,
        tear_sheet=tear_sheet,
        sector_allocations=_compute_sector_allocations(fields["constituents"]),
    )
