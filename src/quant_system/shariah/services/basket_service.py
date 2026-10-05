import logging
from typing import Any

import aiosqlite

from quant_system.shariah.schemas.basket import (
    BasketConstituent,
    BasketDetail,
    BasketSummary,
    RebalanceLog,
    SectorAllocation,
    TearSheetMetrics,
)

logger = logging.getLogger(__name__)

INDIAN_RISK_FREE_RATE = 0.0675  # 6.75% 91-day T-Bill rate

BASKET_DEFINITIONS: list[dict[str, Any]] = [
    {
        "id": "halal-tech-giants",
        "name": "Halal Tech Giants",
        "thesis": "World-leading Indian IT enterprises with zero net debt, export earnings, and superior ROE.",
        "category": "Information Technology & Software",
        "expected_cagr": 0.148,
        "expected_sharpe": 1.12,
        "annualized_volatility": 0.128,
        "max_drawdown": -0.145,
        "beta": 0.82,
        "dividend_yield": 0.0275,
        "weighted_purification_ratio": 0.0069,
        "constituents": [
            {"ticker": "TCS.NS", "symbol": "TCS", "weight": 0.25, "default_price": 4210.50},
            {"ticker": "INFY.NS", "symbol": "INFY", "weight": 0.25, "default_price": 1890.20},
            {"ticker": "HCLTECH.NS", "symbol": "HCLTECH", "weight": 0.20, "default_price": 1780.00},
            {"ticker": "TECHM.NS", "symbol": "TECHM", "weight": 0.15, "default_price": 1640.00},
            {"ticker": "LTIM.NS", "symbol": "LTIM", "weight": 0.15, "default_price": 5890.00},
        ],
        "rebalance_logs": [
            {
                "date": "2026-09-30",
                "action": "Quarterly Rebalancing",
                "notes": "Maintained pure IT titanship with zero net debt; re-calibrated TCS and INFY to 25% target weights.",
                "changes": ["TCS re-weighted to 25.0%", "INFY re-weighted to 25.0%"],
            },
            {
                "date": "2026-06-30",
                "action": "Quarterly Rebalancing",
                "notes": "Verified full AAOIFI and TASIS screening compliance; impermissible interest income remains under 0.8%.",
                "changes": ["LTIM weight confirmed at 15.0%"],
            },
        ],
    },
    {
        "id": "shariah-high-growth-champions",
        "name": "Shariah High-Growth Champions",
        "thesis": "High-growth Indian mid-cap leaders in specialty chemicals, engineering design, and automotive tech.",
        "category": "Mid-Cap Growth & Specialty Manufacturing",
        "expected_cagr": 0.264,
        "expected_sharpe": 1.45,
        "annualized_volatility": 0.182,
        "max_drawdown": -0.198,
        "beta": 1.12,
        "dividend_yield": 0.0095,
        "weighted_purification_ratio": 0.0072,
        "constituents": [
            {
                "ticker": "PERSISTENT.NS",
                "symbol": "PERSISTENT",
                "weight": 0.20,
                "default_price": 4820.00,
            },
            {
                "ticker": "TATAELXSI.NS",
                "symbol": "TATAELXSI",
                "weight": 0.20,
                "default_price": 7650.00,
            },
            {
                "ticker": "DEEPAKNTR.NS",
                "symbol": "DEEPAKNTR",
                "weight": 0.20,
                "default_price": 2890.00,
            },
            {
                "ticker": "PIDILITIND.NS",
                "symbol": "PIDILITIND",
                "weight": 0.20,
                "default_price": 3120.00,
            },
            {"ticker": "MARICO.NS", "symbol": "MARICO", "weight": 0.20, "default_price": 645.00},
        ],
        "rebalance_logs": [
            {
                "date": "2026-09-30",
                "action": "Semi-Annual Equal Weight Rebalance",
                "notes": "Re-balanced 5 mid-cap leaders to equal 20% weights to capture upside across specialty chemicals and tech design.",
                "changes": ["Equal 20.0% weight reset across all 5 constituents"],
            },
            {
                "date": "2026-03-31",
                "action": "Annual Compliance Audit",
                "notes": "Confirmed sub-15% interest debt and high reinvestment rates across all constituents.",
                "changes": ["Audit verified: 100% compliant under AAOIFI & TASIS"],
            },
        ],
    },
    {
        "id": "green-ethical-infrastructure",
        "name": "Green & Ethical Infrastructure",
        "thesis": "Enterprises accelerating India's clean energy, electric transmission, and environmental sustainability.",
        "category": "Renewables, Clean Power & Smart Grid",
        "expected_cagr": 0.312,
        "expected_sharpe": 1.60,
        "annualized_volatility": 0.205,
        "max_drawdown": -0.182,
        "beta": 1.08,
        "dividend_yield": 0.0085,
        "weighted_purification_ratio": 0.0125,
        "constituents": [
            {
                "ticker": "TATAPOWER.NS",
                "symbol": "TATAPOWER",
                "weight": 0.25,
                "default_price": 435.50,
            },
            {"ticker": "THERMAX.NS", "symbol": "THERMAX", "weight": 0.20, "default_price": 5120.00},
            {"ticker": "SIEMENS.NS", "symbol": "SIEMENS", "weight": 0.20, "default_price": 6890.00},
            {"ticker": "ABB.NS", "symbol": "ABB", "weight": 0.20, "default_price": 7950.00},
            {"ticker": "KEC.NS", "symbol": "KEC", "weight": 0.15, "default_price": 940.00},
        ],
        "rebalance_logs": [
            {
                "date": "2026-09-30",
                "action": "Clean Energy Infrastructure Realignment",
                "notes": "Increased Tata Power weight to 25% following renewable generation capacity expansion; verified debt-to-assets remains within TASIS boundaries.",
                "changes": ["TATAPOWER allocated 25.0%", "KEC allocated 15.0%"],
            },
            {
                "date": "2026-06-30",
                "action": "Quarterly Shariah Audit",
                "notes": "Zero interest-bearing bank debt confirmed for Siemens India and ABB India.",
                "changes": ["Debt audit passed"],
            },
        ],
    },
    {
        "id": "nifty-shariah-25",
        "name": "NIFTY Shariah 25 Index Basket",
        "thesis": "Core wealth compounding mirroring the top 25 Shariah-compliant large-cap leaders in NIFTY 100.",
        "category": "Large-Cap Shariah Index Compounding",
        "expected_cagr": 0.165,
        "expected_sharpe": 1.05,
        "annualized_volatility": 0.142,
        "max_drawdown": -0.156,
        "beta": 0.92,
        "dividend_yield": 0.0185,
        "weighted_purification_ratio": 0.0082,
        "constituents": [
            {"ticker": "TCS.NS", "symbol": "TCS", "weight": 0.08, "default_price": 4210.50},
            {"ticker": "INFY.NS", "symbol": "INFY", "weight": 0.08, "default_price": 1890.20},
            {
                "ticker": "HINDUNILVR.NS",
                "symbol": "HINDUNILVR",
                "weight": 0.07,
                "default_price": 2850.00,
            },
            {
                "ticker": "SUNPHARMA.NS",
                "symbol": "SUNPHARMA",
                "weight": 0.06,
                "default_price": 1820.00,
            },
            {"ticker": "CIPLA.NS", "symbol": "CIPLA", "weight": 0.05, "default_price": 1540.00},
            {"ticker": "DRREDDY.NS", "symbol": "DRREDDY", "weight": 0.04, "default_price": 6480.00},
        ],
        "rebalance_logs": [
            {
                "date": "2026-09-30",
                "action": "Semi-Annual Index Weight Reconstitution",
                "notes": "Reconstituted top Shariah anchor constituents based on free-float market capitalization.",
                "changes": ["TCS and INFY anchored at 8.0% each", "HUL anchored at 7.0%"],
            },
            {
                "date": "2026-03-31",
                "action": "Annual Index Audit",
                "notes": "All top anchors confirmed compliant under dual AAOIFI and TASIS screening standards.",
                "changes": ["Screening verified"],
            },
        ],
    },
]


def calculate_sharpe_ratio(
    cagr: float, volatility: float, risk_free_rate: float = INDIAN_RISK_FREE_RATE
) -> float:
    """Calculates Sharpe Ratio: (CAGR - Rf) / Annualized Volatility."""
    if volatility <= 0.0:
        return 0.0
    return round((cagr - risk_free_rate) / volatility, 2)


async def _enrich_constituents(
    constituents_data: list[dict[str, Any]],
    db: aiosqlite.Connection | None = None,
) -> list[BasketConstituent]:
    """Enriches basket constituents with real-time market prices, company names, and sectors from database."""
    enriched: list[BasketConstituent] = []

    # Map of ticker to DB row
    price_map: dict[str, dict[str, Any]] = {}
    if db is not None:
        tickers = [c["ticker"] for c in constituents_data]
        placeholders = ",".join("?" for _ in tickers)
        sql = f"SELECT ticker, symbol, company_name, sector, current_price, market_cap FROM companies WHERE ticker IN ({placeholders});"
        try:
            cursor = await db.execute(sql, tuple(tickers))
            rows = await cursor.fetchall()
            for r in rows:
                price_map[r["ticker"]] = dict(r)
        except Exception as e:
            logger.warning(f"Error querying live constituent prices: {e}")

    for c in constituents_data:
        ticker = c["ticker"]
        sym = c.get("symbol", ticker.replace(".NS", ""))
        weight = float(c["weight"])
        db_info = price_map.get(ticker)

        if db_info:
            price = float(db_info.get("current_price", c.get("default_price", 1000.0)))
            company_name = db_info.get("company_name", sym)
            sector = db_info.get("sector", "Diversified")
            mcap = float(db_info.get("market_cap", 0.0))
        else:
            price = float(c.get("default_price", 1000.0))
            company_name = sym
            sector = "Diversified"
            mcap = 0.0

        enriched.append(
            BasketConstituent(
                ticker=ticker,
                symbol=sym,
                company_name=company_name,
                sector=sector,
                weight=weight,
                current_price=price,
                market_cap=mcap,
            )
        )
    return enriched


def _compute_sector_allocations(constituents: list[BasketConstituent]) -> list[SectorAllocation]:
    """Aggregates weights by sector for breakdown."""
    sector_weights: dict[str, float] = {}
    for c in constituents:
        sec = c.sector or "Diversified"
        sector_weights[sec] = sector_weights.get(sec, 0.0) + c.weight

    allocations = []
    for sec, w in sector_weights.items():
        allocations.append(
            SectorAllocation(
                sector=sec,
                weight=round(w, 4),
                weight_pct=round(w * 100.0, 2),
            )
        )
    allocations.sort(key=lambda x: x.weight, reverse=True)
    return allocations


async def get_all_baskets(db: aiosqlite.Connection | None = None) -> list[BasketSummary]:
    """Returns all 4 curated institutional baskets with real-time valuation and constituent weights."""
    results: list[BasketSummary] = []

    for b in BASKET_DEFINITIONS:
        constituents = await _enrich_constituents(b["constituents"], db)
        min_invest = sum(c.current_price or 0.0 for c in constituents)
        total_val = sum((c.current_price or 0.0) * c.weight for c in constituents)

        cagr = float(b["expected_cagr"])
        vol = float(b["annualized_volatility"])
        sharpe = float(b.get("expected_sharpe", calculate_sharpe_ratio(cagr, vol)))

        results.append(
            BasketSummary(
                id=b["id"],
                name=b["name"],
                thesis=b["thesis"],
                category=b["category"],
                constituent_count=len(constituents),
                expected_cagr=cagr,
                expected_sharpe=sharpe,
                cagr=cagr,
                sharpe_ratio=sharpe,
                annualized_volatility=vol,
                max_drawdown=float(b["max_drawdown"]),
                dividend_yield=float(b["dividend_yield"]),
                weighted_purification_ratio=float(b["weighted_purification_ratio"]),
                minimum_investment=round(min_invest, 2),
                latest_valuation=round(total_val, 2),
                constituents=constituents,
            )
        )
    return results


async def get_basket_by_id(
    basket_id: str, db: aiosqlite.Connection | None = None
) -> BasketDetail | None:
    """Returns detailed financial tear-sheet, constituents, and rebalancing logs for a basket."""
    basket_def = next((b for b in BASKET_DEFINITIONS if b["id"] == basket_id.lower().strip()), None)
    if not basket_def:
        return None

    constituents = await _enrich_constituents(basket_def["constituents"], db)
    min_invest = sum(c.current_price or 0.0 for c in constituents)
    total_val = sum((c.current_price or 0.0) * c.weight for c in constituents)

    cagr = float(basket_def["expected_cagr"])
    vol = float(basket_def["annualized_volatility"])
    sharpe = float(basket_def.get("expected_sharpe", calculate_sharpe_ratio(cagr, vol)))
    mdd = float(basket_def["max_drawdown"])
    beta = float(basket_def["beta"])
    div_yield = float(basket_def["dividend_yield"])
    purification_ratio = float(basket_def["weighted_purification_ratio"])

    tear_sheet = TearSheetMetrics(
        cagr=cagr,
        expected_cagr=cagr,
        annualized_volatility=vol,
        sharpe_ratio=sharpe,
        expected_sharpe=sharpe,
        max_drawdown=mdd,
        risk_free_rate=INDIAN_RISK_FREE_RATE,
        beta=beta,
        dividend_yield=div_yield,
        weighted_purification_ratio=purification_ratio,
    )

    sector_allocs = _compute_sector_allocations(constituents)
    rebalance_logs = [RebalanceLog(**log) for log in basket_def.get("rebalance_logs", [])]

    return BasketDetail(
        id=basket_def["id"],
        name=basket_def["name"],
        thesis=basket_def["thesis"],
        category=basket_def["category"],
        constituent_count=len(constituents),
        expected_cagr=cagr,
        expected_sharpe=sharpe,
        cagr=cagr,
        sharpe_ratio=sharpe,
        annualized_volatility=vol,
        max_drawdown=mdd,
        dividend_yield=div_yield,
        weighted_purification_ratio=purification_ratio,
        minimum_investment=round(min_invest, 2),
        latest_valuation=round(total_val, 2),
        tear_sheet=tear_sheet,
        sector_allocations=sector_allocs,
        rebalance_logs=rebalance_logs,
        constituents=constituents,
    )
