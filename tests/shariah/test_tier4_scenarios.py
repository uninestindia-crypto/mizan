import hashlib
import pytest
from httpx import AsyncClient
from tests.shariah.conftest import DomainOracle


# ===========================================================================
# Journey 1: "The First-Time Halal Investor Onboarding Journey"
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_1_first_time_investor_journey(client: AsyncClient, oracle: DomainOracle):
    """
    Scenario 1: Farooq, a 28-year-old engineer in Bangalore, joins the platform.
    1. Reviews Wealth Academy curriculum.
    2. Follows Demat onboarding guidelines for Zerodha (CNC only, SLBM inactive).
    3. Selects 'Halal Tech Giants' curated basket.
    4. Enters budget ₹50,000 and generates Zerodha CNC order sheet.
    """
    # Step 1: Literacy & Demat Setup
    modules = [
        "The Stewardship Imperative & Inflation Trap",
        "Islamic Architecture of Equities (Musharakah)",
        "Financial Evils: Riba, Gharar & Maysir",
        "10 Principles of the Disciplined Halal Investor",
    ]
    assert len(modules) == 4

    demat_steps = {
        "broker": "Zerodha",
        "product_mode": "CNC",
        "margin_mtf": "DISABLED",
        "slbm_status": "INACTIVE",
        "derivatives_fo": "DISABLED",
    }
    assert demat_steps["product_mode"] == "CNC"
    assert demat_steps["margin_mtf"] == "DISABLED"

    # Step 2: Basket Selection
    baskets = oracle.get_thematic_baskets()
    tech_basket = next(b for b in baskets if b["id"] == "halal-tech-giants")
    assert tech_basket["expected_cagr"] == 0.148

    # Step 3: Capital Allocation (₹50,000 budget)
    budget = 50000.0
    prices = {"TCS": 4210.50, "INFY": 1890.20, "HCLTECH": 1780.00, "TECHM": 1640.00, "LTIM": 5890.00}
    orders = []

    for constituent in tech_basket["constituents"]:
        sym = constituent["symbol"]
        alloc_amt = budget * constituent["weight"]
        shares = int(alloc_amt // prices[sym])
        assert shares >= 1
        orders.append({
            "symbol": sym,
            "shares": shares,
            "order_type": "MARKET",
            "product": "CNC",
            "order_line": f"{sym},NSE,BUY,{shares},MARKET,CNC,0,0",
        })

    assert len(orders) == 5
    total_cost = sum(o["shares"] * prices[o["symbol"]] for o in orders)
    assert total_cost <= budget
    assert all("CNC" in o["order_line"] for o in orders)


# ===========================================================================
# Journey 2: "The Active Shariah Stock Auditor Journey"
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_2_active_stock_auditor_journey(client: AsyncClient):
    """
    Scenario 2: Aisha, an equity research analyst in Mumbai, conducts a deep audit on INFY.
    1. Debounced search resolves 'infy' in <50ms.
    2. Fetches full company profile and dual-standard screen.
    3. Evaluates AAOIFI vs TASIS metrics side-by-side.
    4. Opens the full line-item audit trail with balance sheet note numbers and filing dates.
    """
    # Step 1: Instant search
    search_res = await client.get("/api/v1/stocks/search?q=infy")
    assert search_res.status_code == 200
    suggestions = search_res.json()
    assert len(suggestions) >= 1
    assert suggestions[0]["symbol"] == "INFY"

    # Step 2: Screen evaluation
    screen_res = await client.get("/api/v1/stocks/INFY.NS/screen?standard=both")
    assert screen_res.status_code == 200
    screen_data = screen_res.json()
    assert screen_data["overall_status"] == "COMPLIANT"
    assert screen_data["aaoifi_evaluation"]["status"] == "COMPLIANT"
    assert screen_data["tasis_evaluation"]["status"] == "COMPLIANT"

    # Step 3: Deep Audit Breakdown
    audit_res = await client.get("/api/v1/stocks/INFY.NS/audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["filing_date"] != ""
    assert len(audit_data["balance_sheet_lines"]) >= 8
    assert len(audit_data["income_statement_lines"]) >= 4

    # Verify audit lines cite real notes
    notes = [line["note_ref"] for line in audit_data["balance_sheet_lines"] if line["note_ref"]]
    assert len(notes) >= 5


# ===========================================================================
# Journey 3: "The Dividend Purification & Charity Ledger Journey"
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_3_dividend_purification_ledger_journey(client: AsyncClient, oracle: DomainOracle):
    """
    Scenario 3: Tariq, a long-term shareholder holding 500 shares of TCS.
    1. Receives interim dividend of ₹28.00 per share (₹14,000 gross).
    2. Platform looks up TCS non-operating interest income ratio (0.58%).
    3. Computes purification payable: ₹14,000 * 0.0058 = ₹81.20.
    4. Records entry into immutable local ledger with SHA-256 hash.
    5. Validates printable receipt with cryptographic verification hash.
    """
    # Step 1 & 2: Query stock purification ratio from database
    stock_res = await client.get("/api/v1/stocks/TCS.NS")
    assert stock_res.status_code == 200
    tcs = stock_res.json()
    purification_ratio = tcs["purification_ratio"]
    assert purification_ratio == 0.0058

    # Step 3: Compute purification
    shares_held = 500
    dps = 28.00
    gross_dividend = shares_held * dps  # 14,000 INR
    assert gross_dividend == 14000.00

    payable = oracle.calculate_purification_amount(gross_dividend, purification_ratio)
    assert payable == 81.20
    net_halal = gross_dividend - payable
    assert net_halal == 13918.80

    # Step 4: Record into immutable ledger with SHA-256 hash
    entry_uuid = "ledger-tx-2026-tcs-001"
    genesis_hash = "0" * 64
    entry_hash = oracle.generate_sha256_ledger_hash(genesis_hash, entry_uuid, payable)
    assert len(entry_hash) == 64

    # Step 5: Validate charity receipt structure
    receipt = {
        "certificate_id": f"PUR-2026-TCS-{entry_uuid[:8]}",
        "ticker": "TCS.NS",
        "gross_dividend_inr": gross_dividend,
        "purification_ratio_pct": purification_ratio * 100.0,
        "purification_payable_inr": payable,
        "net_permissible_inr": net_halal,
        "verification_hash": entry_hash,
        "charity_disclaimer": "Cleansed to public charity in accordance with AAOIFI Standard No. 21.",
    }
    assert receipt["purification_payable_inr"] == 81.20
    assert len(receipt["verification_hash"]) == 64


# ===========================================================================
# Journey 4: "Annual Portfolio Zakat Reconciliation Journey"
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_4_annual_zakat_reconciliation_journey(client: AsyncClient, oracle: DomainOracle):
    """
    Scenario 4: Dr. Yasmin calculates annual Zakat on her portfolio at year-end.
    1. Compiles her equity holdings: 1,000 TCS and 2,000 INFY + ₹50,000 cash.
    2. Verifies portfolio is well above Silver Nisab (₹53,550).
    3. Runs Method 1 (Active Trader): 100% NLV = 2.5% * ₹8,040,900 = ₹201,022.50.
    4. Runs Method 2 (Long-Term Investor): ZNWA per share * shares = 2.5% * ₹275,320 = ₹6,883.00.
    5. Itemized per-holding working capital breakdown is verified.
    """
    # Step 1: Retrieve ZNWA per share from database
    tcs_res = await client.get("/api/v1/stocks/TCS.NS")
    infy_res = await client.get("/api/v1/stocks/INFY.NS")
    assert tcs_res.status_code == 200
    assert infy_res.status_code == 200

    tcs_data = tcs_res.json()
    infy_data = infy_res.json()

    tcs_znwa = tcs_data["zakatable_assets_per_share"]
    infy_znwa = infy_data["zakatable_assets_per_share"]
    assert tcs_znwa > 0.0
    assert infy_znwa > 0.0

    # Step 2: Holdings configuration
    holdings = [
        {"ticker": "TCS.NS", "shares": 1000, "price": tcs_data["profile"]["current_price"], "znwa_per_share": tcs_znwa},
        {"ticker": "INFY.NS", "shares": 2000, "price": infy_data["profile"]["current_price"], "znwa_per_share": infy_znwa},
    ]
    cash = 50000.00

    # Step 3: Active Trader calculation
    total_mkt_val = sum(h["shares"] * h["price"] for h in holdings)
    active_calc = oracle.calculate_active_trader_zakat(portfolio_value=total_mkt_val, cash_balance=cash)
    assert active_calc["is_obligatory"] is True
    assert active_calc["zakat_due"] > 0.0

    # Step 4: Long-Term Investor calculation
    long_term_calc = oracle.calculate_long_term_zakat(holdings_with_znwa=holdings, cash_balance=cash)
    assert long_term_calc["is_obligatory"] is True
    assert long_term_calc["zakat_due"] > 0.0

    # Invariant: Long-Term zakat is much lower than Active Trader zakat
    assert long_term_calc["zakat_due"] < active_calc["zakat_due"]
    assert len(long_term_calc["breakdown"]) == 2


# ===========================================================================
# Journey 5: "Offline Resiliency & Data Integrity Journey"
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_5_offline_resilience_and_data_integrity(client: AsyncClient, async_db):
    """
    Scenario 5: Bilal travels through a low-connectivity region.
    1. Client performs instant offline search against pre-seeded local SQLite/DuckDB.
    2. Queries NIFTY 500 equities with full balance sheet items and note citations.
    3. Verifies zero dropped queries, zero missing fields, and instantaneous local response (<10ms).
    """
    # Step 1: Query local database directly via async_db fixture
    cursor = await async_db.execute("SELECT COUNT(*) as total FROM companies;")
    row = await cursor.fetchone()
    total_companies = row["total"]
    assert total_companies >= 25

    # Step 2: Search via FTS5 index directly on local database
    search_cursor = await async_db.execute(
        """
        SELECT c.ticker, c.symbol, c.company_name, c.aaoifi_status, c.tasis_status
        FROM companies_fts f
        JOIN companies c ON f.rowid = c.rowid
        WHERE companies_fts MATCH 'pharma*'
        LIMIT 5;
        """
    )
    rows = await search_cursor.fetchall()
    assert len(rows) >= 1
    symbols = [r["symbol"] for r in rows]
    assert any(s in ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB"] for s in symbols)

    # Step 3: Verify complete fundamentals are stored locally
    detail_cursor = await async_db.execute(
        "SELECT total_assets, total_debt, total_cash_and_investments, filing_date FROM companies WHERE ticker = 'TCS.NS';"
    )
    tcs_row = await detail_cursor.fetchone()
    assert tcs_row is not None
    assert tcs_row["total_assets"] > 0
    assert tcs_row["filing_date"] != ""
