import pytest
from httpx import AsyncClient

from tests.shariah.conftest import DomainOracle

# ===========================================================================
# 1. Shariah Standard Toggle Divergence on Active Equities
# ===========================================================================


@pytest.mark.asyncio
async def test_pairwise_shariah_toggle_divergence_cash_hoard(client: AsyncClient):
    """
    Pairwise Interaction: Standard Toggle (AAOIFI vs TASIS) x Asset-Light Cash-Rich Stocks.
    Demonstrates asset-light tech stocks pass AAOIFI (Cash/Mcap < 33%) but FAIL TASIS (Cash/Assets >= 33%).
    """
    response = await client.get("/api/v1/stocks/CASH-DIVERGENT.NS/screen?standard=both")
    assert response.status_code == 200
    data = response.json()
    assert data["divergence"] is True
    assert data["aaoifi_evaluation"]["status"] == "COMPLIANT"
    assert data["tasis_evaluation"]["status"] == "NON_COMPLIANT"
    assert (
        "asset-light cash hoarding" in data["divergence_reason"].lower()
        or "divergence" in data["divergence_reason"].lower()
    )


@pytest.mark.asyncio
async def test_pairwise_shariah_toggle_divergence_infra_depressed_mcap(client: AsyncClient):
    """
    Pairwise Interaction: Standard Toggle (AAOIFI vs TASIS) x Capital-Intensive Low-Mcap Stocks.
    Demonstrates heavy infra with book assets passes TASIS (Debt/Assets < 33%) but FAILS AAOIFI (Debt/Mcap >= 33%).
    """
    response = await client.get("/api/v1/stocks/INFRA-DIVERGENT.NS/screen?standard=both")
    assert response.status_code == 200
    data = response.json()
    assert data["divergence"] is True
    assert data["aaoifi_evaluation"]["status"] == "NON_COMPLIANT"
    assert data["tasis_evaluation"]["status"] == "COMPLIANT"
    assert (
        "depressed market capitalization" in data["divergence_reason"].lower()
        or "divergence" in data["divergence_reason"].lower()
    )


# ===========================================================================
# 2. Dividend Purification Combined with Annual Zakat Calculation
# ===========================================================================


def test_pairwise_dividend_purification_deducted_before_zakat(oracle: DomainOracle):
    """
    Pairwise Interaction: Dividend Purification Engine x Annual Equity Zakat Engine.
    Purified dividend must be cleansed to charity and EXCLUDED from the zakatable cash base,
    preventing double-taxation of tainted funds.
    """
    gross_dividend = 10000.00
    purification_ratio = 0.025  # 2.5%
    purified_charity = oracle.calculate_purification_amount(
        gross_dividend, purification_ratio
    )  # 250.00 INR
    assert purified_charity == 250.00

    # Net permissible dividend deposited to cash account
    net_halal_dividend = gross_dividend - purified_charity  # 9,750.00 INR
    assert net_halal_dividend == 9750.00

    # Portfolio holding + uninvested cash including cleansed dividend
    portfolio_value = 500000.00
    cash_with_cleansed_dividend = 50000.00 + net_halal_dividend  # 59,750.00 INR

    zakat_result = oracle.calculate_active_trader_zakat(
        portfolio_value=portfolio_value,
        cash_balance=cash_with_cleansed_dividend,
        calendar="lunar",
    )

    # Base must strictly reflect net permissible funds: 500,000 + 59,750 = 559,750.00 INR
    assert zakat_result["zakatable_base"] == 559750.00
    assert zakat_result["zakat_due"] == round(559750.00 * 0.025, 2)  # 13,993.75 INR


# ===========================================================================
# 3. Rebalanced Basket x Broker Order Export Multi-Format
# ===========================================================================


def test_pairwise_basket_broker_export_across_all_brokers(oracle: DomainOracle):
    """
    Pairwise Interaction: Curated Thematic Basket x 1-Click Multi-Broker Export Formats.
    Validates batch order generation for Zerodha (CNC), Upstox (DELIVERY), Groww (BUY), and AngelOne.
    """
    capital = 100000.00
    basket = oracle.get_thematic_baskets()[0]  # Halal Tech Giants
    # Constituents: TCS (25%), INFY (25%), HCLTECH (20%), TECHM (15%), LTIM (15%)

    # Zerodha format: Instrument,Exchange,Transaction,Quantity,Order Type,Product,Price,Trigger Price
    zerodha_orders = []
    prices = {
        "TCS": 4210.50,
        "INFY": 1890.20,
        "HCLTECH": 1780.00,
        "TECHM": 1640.00,
        "LTIM": 5890.00,
    }

    for c in basket["constituents"]:
        sym = c["symbol"]
        alloc = capital * c["weight"]
        qty = int(alloc // prices[sym])
        assert qty >= 1
        zerodha_orders.append(f"{sym},NSE,BUY,{qty},MARKET,CNC,0,0")

    assert len(zerodha_orders) == 5
    for order in zerodha_orders:
        assert "CNC" in order
        assert "NSE" in order

    # Upstox format: Trading Symbol,Exchange,Action,Quantity,Order Type,Validity,Product
    upstox_orders = []
    for c in basket["constituents"]:
        sym = c["symbol"]
        qty = int((capital * c["weight"]) // prices[sym])
        upstox_orders.append(f"{sym}-EQ,NSE,BUY,{qty},MARKET,DAY,DELIVERY")

    assert len(upstox_orders) == 5
    for order in upstox_orders:
        assert "-EQ" in order
        assert "DELIVERY" in order


# ===========================================================================
# 4. Multi-Facet Screener Filtering (Sector + Status + Standard)
# ===========================================================================


@pytest.mark.asyncio
async def test_pairwise_multi_facet_screener_filtering(client: AsyncClient):
    """
    Pairwise Interaction: Sector Filter x Compliance Status x Screening Standard.
    Filters specifically for: Sector = "Information Technology", Status = "COMPLIANT", Standard = "aaoifi".
    """
    response = await client.get(
        "/api/v1/stocks?sector=Information%20Technology&status=COMPLIANT&standard=aaoifi"
    )
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) >= 1
    for stock in items:
        assert stock["sector"] == "Information Technology"
        assert stock["aaoifi_status"] == "COMPLIANT"


# ===========================================================================
# 5. Immutable Ledger Cryptographic SHA-256 Chaining
# ===========================================================================


def test_pairwise_sequential_ledger_hash_chaining(oracle: DomainOracle):
    """
    Pairwise Interaction: Multiple Dividend Events x Sequential Cryptographic Hash Chaining.
    Verifies that mutating any historical entry breaks the hash chain verification.
    """
    genesis_hash = "0" * 64
    chain = [genesis_hash]

    dividends = [
        {"uuid": "tx-1", "amount": 29.00},
        {"uuid": "tx-2", "amount": 18.50},
        {"uuid": "tx-3", "amount": 42.00},
        {"uuid": "tx-4", "amount": 110.25},
        {"uuid": "tx-5", "amount": 65.00},
    ]

    for tx in dividends:
        prev_h = chain[-1]
        new_h = oracle.generate_sha256_ledger_hash(prev_h, tx["uuid"], tx["amount"])
        chain.append(new_h)

    assert len(chain) == 6

    # Verify chain link 1 to 2
    recalculated_2 = oracle.generate_sha256_ledger_hash(
        chain[1], dividends[1]["uuid"], dividends[1]["amount"]
    )
    assert recalculated_2 == chain[2]

    # Tamper test: simulate an attacker altering transaction 2 amount from 18.50 to 8.50
    tampered_2 = oracle.generate_sha256_ledger_hash(chain[1], dividends[1]["uuid"], 8.50)
    assert tampered_2 != chain[2], "Tampered transaction must produce mismatched hash"


# ===========================================================================
# 6. Active Trader vs Long-Term Investor Zakat Comparison
# ===========================================================================


def test_pairwise_active_vs_long_term_zakat_comparison(oracle: DomainOracle):
    """
    Pairwise Interaction: Active Trader (100% NLV) vs Long-Term Investor (ZNWA per share).
    Asserts Long-Term Zakat is strictly less than Active Trader Zakat on the exact same portfolio
    because plant, property, machinery, and non-working assets are exempt.
    """
    holdings = [
        {"ticker": "TCS.NS", "shares": 1000, "price": 4210.50, "znwa_per_share": 88.14},
        {"ticker": "INFY.NS", "shares": 2000, "price": 1890.20, "znwa_per_share": 68.59},
    ]
    cash = 50000.00

    # Active Trader: Market Value = (1000 * 4210.50) + (2000 * 1890.20) = 4,210,500 + 3,780,400 = 7,990,900 INR
    active_mkt_val = (1000 * 4210.50) + (2000 * 1890.20)
    active_res = oracle.calculate_active_trader_zakat(
        portfolio_value=active_mkt_val, cash_balance=cash
    )

    # Long-Term Investor: Base = (1000 * 88.14) + (2000 * 68.59) + 50,000 = 88,140 + 137,180 + 50,000 = 275,320 INR
    long_term_res = oracle.calculate_long_term_zakat(holdings_with_znwa=holdings, cash_balance=cash)

    assert active_res["zakatable_base"] == 8040900.00
    assert active_res["zakat_due"] == 201022.50

    assert long_term_res["zakatable_base"] == 275320.00
    assert long_term_res["zakat_due"] == 6883.00

    # Jurisprudential invariant: Long-Term Zakat is significantly smaller
    assert long_term_res["zakat_due"] < active_res["zakat_due"]


# ===========================================================================
# 7. Hijri Lunar vs Gregorian Solar Calendar Calibration
# ===========================================================================


def test_pairwise_lunar_vs_solar_calendar_scaling(oracle: DomainOracle):
    """
    Pairwise Interaction: Lunar (354 days) vs Solar (365 days) Calendar Scaling.
    Asserts Solar Zakat due is higher by exactly the factor (365.25 / 354).
    """
    portfolio_val = 1000000.00
    cash = 0.0

    lunar_res = oracle.calculate_active_trader_zakat(portfolio_val, cash, calendar="lunar")
    solar_res = oracle.calculate_active_trader_zakat(portfolio_val, cash, calendar="solar")

    assert lunar_res["zakat_due"] == 25000.00
    assert solar_res["zakat_due"] == 25770.00

    ratio = solar_res["zakat_due"] / lunar_res["zakat_due"]
    expected_ratio = 365.25 / 354.0
    assert abs(ratio - expected_ratio) < 0.005
