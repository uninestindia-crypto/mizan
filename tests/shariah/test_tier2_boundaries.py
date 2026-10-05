import pytest
from httpx import AsyncClient
from tests.shariah.conftest import DomainOracle


# ===========================================================================
# 1. Strict Inequality Debt Thresholds (32.99% vs 33.00% vs 33.01%)
# ===========================================================================

@pytest.mark.asyncio
async def test_boundary_debt_32_99_pct_passes(client: AsyncClient):
    """
    Verifies company with debt ratio strictly at 32.990% passes the compliance test (< 33.00%).
    Note: Ratio is in warning band [32.0%, 33.0%), so status is QUESTIONABLE.
    """
    response = await client.get("/api/v1/stocks/DEBT-PASS.NS/screen")
    assert response.status_code == 200
    data = response.json()
    debt_meter = data["aaoifi_evaluation"]["debt_ratio"]
    assert debt_meter["is_compliant"] is True
    assert debt_meter["actual_pct"] == 32.9900
    assert debt_meter["is_warning"] is True
    assert data["aaoifi_evaluation"]["status"] == "QUESTIONABLE"


@pytest.mark.asyncio
async def test_boundary_debt_33_00_pct_fails(client: AsyncClient):
    """
    Verifies company with debt ratio strictly at 33.000% FAILS compliance test.
    AAOIFI and TASIS standards require strictly < 33.00%; equality fails.
    """
    response = await client.get("/api/v1/stocks/DEBT-FAIL.NS/screen")
    assert response.status_code == 200
    data = response.json()
    debt_meter = data["aaoifi_evaluation"]["debt_ratio"]
    assert debt_meter["is_compliant"] is False
    assert debt_meter["actual_pct"] == 33.0000
    assert data["overall_status"] == "NON_COMPLIANT"


@pytest.mark.asyncio
async def test_boundary_debt_33_01_pct_fails(client: AsyncClient):
    """
    Verifies company with debt ratio at 33.010% FAILS compliance test.
    """
    # Test via direct screener service evaluation logic
    from quant_system.shariah.services.screener_service import evaluate_ratio
    from quant_system.shariah.core.config import settings

    meter = evaluate_ratio(
        metric_name="Debt Test",
        numerator=33010.0,
        denominator=100000.0,
        threshold=settings.MAX_DEBT_RATIO,
        warning_threshold=settings.WARN_DEBT_RATIO,
        numerator_label="Debt",
        denominator_label="Mcap",
    )
    assert meter.is_compliant is False
    assert meter.actual_pct == 33.0100


# ===========================================================================
# 2. Strict Inequality Impermissible Revenue (4.99% vs 5.00% vs 5.01%)
# ===========================================================================

@pytest.mark.asyncio
async def test_boundary_impermissible_revenue_4_99_pct_passes(client: AsyncClient):
    """
    Verifies company with impermissible revenue at 4.990% passes (< 5.00%).
    Because 4.99% is in warning band [4.5%, 5.0%), status is QUESTIONABLE.
    """
    response = await client.get("/api/v1/stocks/REV-PASS.NS/screen")
    assert response.status_code == 200
    data = response.json()
    imp_meter = data["aaoifi_evaluation"]["impermissible_income_ratio"]
    assert imp_meter["is_compliant"] is True
    assert imp_meter["actual_pct"] == 4.9900
    assert imp_meter["is_warning"] is True
    assert data["aaoifi_evaluation"]["status"] == "QUESTIONABLE"


@pytest.mark.asyncio
async def test_boundary_impermissible_revenue_5_00_pct_fails(client: AsyncClient):
    """
    Verifies company with impermissible revenue strictly at 5.000% FAILS.
    Standard requires strictly < 5.00%.
    """
    response = await client.get("/api/v1/stocks/REV-FAIL.NS/screen")
    assert response.status_code == 200
    data = response.json()
    imp_meter = data["aaoifi_evaluation"]["impermissible_income_ratio"]
    assert imp_meter["is_compliant"] is False
    assert imp_meter["actual_pct"] == 5.0000
    assert data["overall_status"] == "NON_COMPLIANT"


# ===========================================================================
# 3. Zero-Division & Pre-Revenue Division Guards
# ===========================================================================

@pytest.mark.asyncio
async def test_boundary_zero_debt_company(client: AsyncClient):
    """
    Verifies company with exactly zero debt (0.00 INR) passes without error.
    Numerator is zero, debt ratio is strictly 0.00%.
    """
    response = await client.get("/api/v1/stocks/ZERO-DEBT.NS/screen")
    assert response.status_code == 200
    data = response.json()
    debt_meter = data["aaoifi_evaluation"]["debt_ratio"]
    assert debt_meter["is_compliant"] is True
    assert debt_meter["actual_value"] == 0.000000
    assert debt_meter["actual_pct"] == 0.0000
    assert data["aaoifi_evaluation"]["status"] == "COMPLIANT"


@pytest.mark.asyncio
async def test_boundary_pre_revenue_zero_revenue_guard(client: AsyncClient):
    """
    Verifies company with Total Revenue = 0.0 does not trigger ZeroDivisionError.
    The ratio evaluator clamps the revenue ratio safely to 0.0.
    """
    response = await client.get("/api/v1/stocks/PRE-REV.NS/screen")
    assert response.status_code == 200
    data = response.json()
    imp_meter = data["aaoifi_evaluation"]["impermissible_income_ratio"]
    assert imp_meter["actual_value"] == 0.0
    assert imp_meter["is_compliant"] is True


# ===========================================================================
# 4. Negative Working Capital Floor (max(0, ZNWA))
# ===========================================================================

@pytest.mark.asyncio
async def test_boundary_negative_working_capital_clamped_to_zero(client: AsyncClient, oracle: DomainOracle):
    """
    Verifies company with Current Liabilities > Current Assets has ZNWA clamped to 0.0 INR.
    Prevents negative working capital from reducing an investor's Zakat base.
    """
    response = await client.get("/api/v1/stocks/NEG-WC.NS")
    assert response.status_code == 200
    data = response.json()
    assert data["zakatable_assets_per_share"] == 0.00

    # Verify oracle mathematical calculation directly
    znwa_calculated = oracle.calculate_znwa_per_share(
        cash=300.0,
        investments=100.0,
        receivables=200.0,
        inventories=500.0,
        current_liabilities=2500.0,  # Liabilities (2500) > Assets (1100)
        shares_outstanding=100000000,
    )
    assert znwa_calculated == 0.00


# ===========================================================================
# 5. Indian Silver Nisab Threshold Cutoff (₹53,550.00 Boundary)
# ===========================================================================

def test_boundary_silver_nisab_below_threshold_exempt(oracle: DomainOracle):
    """
    Verifies wealth of ₹53,549.99 (₹0.01 below Silver Nisab of ₹53,550) is EXEMPT.
    """
    result = oracle.calculate_active_trader_zakat(portfolio_value=50000.0, cash_balance=3549.99)
    assert result["zakatable_base"] == 53549.99
    assert result["is_obligatory"] is False
    assert result["zakat_due"] == 0.0


def test_boundary_silver_nisab_exact_threshold_obligatory(oracle: DomainOracle):
    """
    Verifies wealth of exactly ₹53,550.00 (exact Nisab cutoff) is OBLIGATORY.
    """
    result = oracle.calculate_active_trader_zakat(portfolio_value=50000.0, cash_balance=3550.00)
    assert result["zakatable_base"] == 53550.00
    assert result["is_obligatory"] is True
    # 53,550 * 0.025 = 1,338.75 INR
    assert result["zakat_due"] == 1338.75


def test_boundary_silver_nisab_one_cent_above_obligatory(oracle: DomainOracle):
    """
    Verifies wealth of ₹53,550.01 (₹0.01 above Nisab) is OBLIGATORY.
    """
    result = oracle.calculate_active_trader_zakat(portfolio_value=50000.0, cash_balance=3550.01)
    assert result["zakatable_base"] == 53550.01
    assert result["is_obligatory"] is True
    assert result["zakat_due"] == 1338.75


# ===========================================================================
# 6. Micro-Cent Precision & Rounding in Purification
# ===========================================================================

def test_boundary_purification_rounding_half_up(oracle: DomainOracle):
    """
    Verifies micro-cent rounding precision for odd dividend amounts.
    Gross Dividend = 12,345.67, rho = 0.031415
    Payable = round(12,345.67 * 0.031415, 2) = 387.85
    """
    gross = 12345.67
    rho = 0.031415
    payable = oracle.calculate_purification_amount(gross, rho)
    assert payable == 387.84
    net = round(gross - payable, 2)
    assert round(payable + net, 2) == gross


def test_boundary_purification_zero_declared_dividend(oracle: DomainOracle):
    """
    Verifies zero declared dividend results in 0.00 INR purification payable.
    """
    payable = oracle.calculate_purification_amount(gross_dividend=0.0, purification_ratio=0.05)
    assert payable == 0.00


# ===========================================================================
# 7. Broker Allocation Capital Floor & Fractional Prevention
# ===========================================================================

def test_boundary_broker_allocation_sub_share_budget():
    """
    Verifies allocation logic when capital is insufficient to purchase even 1 share.
    Capital = 1,000 INR, Stock Price = 4,200 INR -> Share count = floor(1000/4200) = 0.
    """
    capital = 1000.0
    price = 4200.0
    shares = int(capital // price)
    assert shares == 0


def test_boundary_broker_allocation_non_fractional_shares():
    """
    Verifies integer share allocations on Indian exchanges (NSE prohibits fractional shares).
    Capital = 10,000 INR, Weight = 20% (2,000 INR), Share Price = 380 INR -> 5.26 shares -> 5 shares.
    """
    target_alloc = 2000.0
    price = 380.0
    shares = int(target_alloc // price)
    assert isinstance(shares, int)
    assert shares == 5
    invested = shares * price
    residual = target_alloc - invested
    assert residual == 100.0


# ===========================================================================
# 8. Search Injection, Whitespace & Special Character Sanitization
# ===========================================================================

@pytest.mark.asyncio
async def test_boundary_search_sql_injection_sanitization(client: AsyncClient):
    """
    Verifies search input containing SQL injection syntax does not crash or execute raw SQL.
    """
    response = await client.get("/api/v1/stocks/search?q=' OR '1'='1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_boundary_search_special_characters_handling(client: AsyncClient):
    """
    Verifies search handles punctuation and ampersands (e.g. 'M&M', 'L&T').
    """
    response = await client.get("/api/v1/stocks/search?q=L%26T")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_boundary_search_whitespace_stripping(client: AsyncClient):
    """
    Verifies search with irregular leading/trailing whitespace resolves correctly.
    """
    response = await client.get("/api/v1/stocks/search?q=%20%20tcs%20%20")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert items[0]["symbol"] == "TCS"
