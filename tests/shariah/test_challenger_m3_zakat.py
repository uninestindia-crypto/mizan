"""Adversarial stress-testing suite for Milestone 3 Equity Zakat Calculation Engine.

Authored by challenger_m3_1 to empirically probe:
1. Nisab boundary threshold tests (₹53,549.99, ₹53,550.00, ₹53,550.01, custom Nisab)
2. Boundary financial inputs (zero values, negative validation rejection, extreme HNI portfolios)
3. Dual-calendar rate accuracy (lunar 2.500% vs solar 2.577%, case/whitespace resilience)
4. Method divergence invariant (Long-Term <= Active Trader for operating companies)
5. Unseeded ticker fallback (conservative 25% proxy, missing metrics, custom overrides)
"""

import pytest
from httpx import AsyncClient

# ===========================================================================
# Vector 1: Nisab Boundary Threshold Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_vector1_nisab_strictly_below_silver_threshold(client: AsyncClient):
    """Base = ₹53,549.99 (strictly below Silver Nisab of ₹53,550.00).
    is_obligatory must be False, zakat_due must be 0.00, exemption_reason populated.
    """
    payload = {
        "method": "active",
        "portfolio_value": 50000.0,
        "cash_balance": 3549.99,
        "calendar": "lunar",
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["zakatable_base"] == 53549.99
    assert data["nisab_threshold"] == 53550.00
    assert data["is_obligatory"] is False
    assert data["zakat_due"] == 0.00
    assert data["exemption_reason"] is not None
    assert "below the Indian Silver Nisab threshold" in data["exemption_reason"]


@pytest.mark.asyncio
async def test_vector1_nisab_exact_silver_threshold(client: AsyncClient):
    """Base = ₹53,550.00 (exactly at Silver Nisab cutoff).
    is_obligatory must be True, zakat_due = 53550 * 0.025 = 1,338.75.
    """
    payload = {
        "method": "active",
        "portfolio_value": 50000.0,
        "cash_balance": 3550.00,
        "calendar": "lunar",
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["zakatable_base"] == 53550.00
    assert data["nisab_threshold"] == 53550.00
    assert data["is_obligatory"] is True
    assert data["zakat_due"] == 1338.75
    assert data["exemption_reason"] is None


@pytest.mark.asyncio
async def test_vector1_nisab_one_cent_above_threshold(client: AsyncClient):
    """Base = ₹53,550.01 (strictly above Silver Nisab cutoff).
    is_obligatory must be True, zakat_due = round(53550.01 * 0.025, 2) = 1,338.75.
    """
    payload = {
        "method": "active",
        "portfolio_value": 50000.0,
        "cash_balance": 3550.01,
        "calendar": "lunar",
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["zakatable_base"] == 53550.01
    assert data["nisab_threshold"] == 53550.00
    assert data["is_obligatory"] is True
    assert data["zakat_due"] == 1338.75
    assert data["exemption_reason"] is None


@pytest.mark.asyncio
async def test_vector1_custom_nisab_threshold_enforcement(client: AsyncClient):
    """Verifies that an explicitly supplied custom Nisab threshold (e.g. Gold Nisab or dynamic rate)
    is strictly respected over the default Silver Nisab.
    """
    custom_threshold = 850000.0  # e.g. Gold Nisab benchmark 8.5 Lakhs

    # Case A: Below custom threshold but above silver nisab
    payload_a = {
        "method": "active",
        "portfolio_value": 500000.0,
        "cash_balance": 100000.0,
        "custom_nisab_inr": custom_threshold,
    }
    res_a = await client.post("/api/v1/zakat/calculate", json=payload_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["zakatable_base"] == 600000.0
    assert data_a["nisab_threshold"] == 850000.0
    assert data_a["is_obligatory"] is False
    assert data_a["zakat_due"] == 0.0

    # Case B: At or above custom threshold
    payload_b = {
        "method": "active",
        "portfolio_value": 800000.0,
        "cash_balance": 50000.0,
        "custom_nisab_inr": custom_threshold,
    }
    res_b = await client.post("/api/v1/zakat/calculate", json=payload_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["zakatable_base"] == 850000.0
    assert data_b["is_obligatory"] is True
    assert data_b["zakat_due"] == round(850000.0 * 0.025, 2)


# ===========================================================================
# Vector 2: Boundary Financial Inputs
# ===========================================================================


@pytest.mark.asyncio
async def test_vector2_zero_cash_and_zero_portfolio(client: AsyncClient):
    """Zero cash, zero portfolio value. Must return 200 OK with zakatable_base=0.0, is_obligatory=False."""
    payload = {
        "method": "active",
        "portfolio_value": 0.0,
        "cash_balance": 0.0,
        "holdings": [],
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["zakatable_base"] == 0.0
    assert data["portfolio_value"] == 0.0
    assert data["cash_balance"] == 0.0
    assert data["is_obligatory"] is False
    assert data["zakat_due"] == 0.0
    assert data["breakdown"] == []


@pytest.mark.asyncio
async def test_vector2_negative_cash_rejected(client: AsyncClient):
    """Negative cash balance must be rejected by Pydantic validation (422 Unprocessable Entity)."""
    payload = {
        "method": "active",
        "portfolio_value": 100000.0,
        "cash_balance": -500.0,
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code in (422, 400)


@pytest.mark.asyncio
async def test_vector2_negative_portfolio_value_rejected(client: AsyncClient):
    """Negative portfolio value must be rejected by Pydantic validation (422 Unprocessable Entity)."""
    payload = {
        "method": "active",
        "portfolio_value": -100000.0,
        "cash_balance": 50000.0,
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code in (422, 400)


@pytest.mark.asyncio
async def test_vector2_negative_and_zero_shares_rejected(client: AsyncClient):
    """Holding with zero or negative shares must be rejected by validation (gt=0)."""
    for invalid_shares in [0, -10]:
        payload = {
            "method": "active",
            "holdings": [{"ticker": "TCS.NS", "shares": invalid_shares}],
        }
        response = await client.post("/api/v1/zakat/calculate", json=payload)
        assert response.status_code in (422, 400)


@pytest.mark.asyncio
async def test_vector2_extreme_hni_portfolio_precision(client: AsyncClient):
    """Extreme High-Net-Worth Individual (HNI) portfolio:
    ₹100 Crore (1,000,000,000 INR) portfolio + ₹5 Crore (50,000,000 INR) cash.
    Verify no float precision loss, overflow, or NaN.
    """
    portfolio_val = 1_000_000_000.00  # 100 Cr
    cash_val = 50_000_000.00  # 5 Cr
    expected_base = 1_050_000_000.00  # 105 Cr

    # Test Lunar rate (2.500%)
    res_lunar = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "active",
            "portfolio_value": portfolio_val,
            "cash_balance": cash_val,
            "calendar": "lunar",
        },
    )
    assert res_lunar.status_code == 200
    data_l = res_lunar.json()
    assert data_l["zakatable_base"] == expected_base
    assert data_l["is_obligatory"] is True
    # 1,050,000,000 * 0.025 = 26,250,000.00 INR (2.625 Cr)
    assert data_l["zakat_due"] == 26250000.00

    # Test Solar rate (2.577%)
    res_solar = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "active",
            "portfolio_value": portfolio_val,
            "cash_balance": cash_val,
            "calendar": "solar",
        },
    )
    assert res_solar.status_code == 200
    data_s = res_solar.json()
    assert data_s["zakatable_base"] == expected_base
    # 1,050,000,000 * 0.025770 = 27,058,500.00 INR
    assert data_s["zakat_due"] == 27058500.00

    # Extreme boundary: ₹1,000 Crore (10,000,000,000 INR)
    res_1000cr = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "active",
            "portfolio_value": 10_000_000_000.00,
            "cash_balance": 0.0,
            "calendar": "lunar",
        },
    )
    assert res_1000cr.status_code == 200
    assert res_1000cr.json()["zakat_due"] == 250000000.00


# ===========================================================================
# Vector 3: Dual-Calendar Rate Accuracy
# ===========================================================================


@pytest.mark.asyncio
async def test_vector3_dual_calendar_exact_rates_and_scaling(client: AsyncClient):
    """Verifies:
    1. Hijri Lunar rate is strictly 0.025000 (2.500%).
    2. Gregorian Solar rate is strictly 0.025770 (2.577%).
    3. Mathematical divergence matches solar/lunar astronomical year ratio (365.25 / 354).
    """
    base_amount = 10_000_000.00  # 1 Crore INR

    res_lunar = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "active",
            "portfolio_value": base_amount,
            "calendar": "lunar",
        },
    )
    assert res_lunar.status_code == 200
    data_l = res_lunar.json()
    assert data_l["rate"] == 0.025000
    assert data_l["rate_pct"] == 2.5
    assert data_l["zakat_due"] == 250000.00

    res_solar = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "active",
            "portfolio_value": base_amount,
            "calendar": "solar",
        },
    )
    assert res_solar.status_code == 200
    data_s = res_solar.json()
    assert data_s["rate"] == 0.025770
    assert data_s["rate_pct"] == 2.577
    assert data_s["zakat_due"] == 257700.00

    # Difference must be exactly 7,700 INR per 1 Crore (0.077%)
    diff = data_s["zakat_due"] - data_l["zakat_due"]
    assert diff == 7700.00


@pytest.mark.asyncio
async def test_vector3_calendar_case_and_whitespace_resilience(client: AsyncClient):
    """Calendar parameter must handle whitespace and mixed casing (' SOLAR ', 'Lunar')."""
    res1 = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "active",
            "portfolio_value": 100000.0,
            "calendar": " SOLAR ",
        },
    )
    assert res1.status_code == 200
    assert res1.json()["rate"] == 0.025770

    res2 = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "active",
            "portfolio_value": 100000.0,
            "calendar": "LuNaR",
        },
    )
    assert res2.status_code == 200
    assert res2.json()["rate"] == 0.025000


# ===========================================================================
# Vector 4: Method Divergence Invariant
# ===========================================================================


@pytest.mark.asyncio
async def test_vector4_method_divergence_operating_companies_tcs_and_infy(client: AsyncClient):
    """Method divergence invariant:
    For any non-financial operating company with physical capital/fixed assets,
    Long-Term Investor Zakat must be strictly LESS than Active Trader Zakat
    because fixed assets, property, plant, and machinery are exempt under Mustathmir fiqh.
    """
    holdings = [
        {"ticker": "TCS.NS", "shares": 1000},
        {"ticker": "INFY.NS", "shares": 2000},
    ]
    cash = 100000.00

    # 1. Active Trader (100% Market Value)
    res_active = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "active",
            "holdings": holdings,
            "cash_balance": cash,
            "calendar": "lunar",
        },
    )
    assert res_active.status_code == 200
    active_data = res_active.json()

    # 2. Long-Term Investor (ZNWA per share)
    res_lt = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "long_term",
            "holdings": holdings,
            "cash_balance": cash,
            "calendar": "lunar",
        },
    )
    assert res_lt.status_code == 200
    lt_data = res_lt.json()

    # Active market value: 1000 * 4180.50 + 2000 * 1890.20 = 4,180,500 + 3,780,400 = 7,960,900 INR
    assert active_data["zakatable_base"] == round(7960900.00 + cash, 2)
    assert active_data["zakat_due"] == round(active_data["zakatable_base"] * 0.025, 2)

    # Long-term ZNWA: 1000 * 88.14 + 2000 * 68.59 = 88,140 + 137,180 = 225,320 INR
    assert lt_data["zakatable_base"] == round(225320.00 + cash, 2)
    assert lt_data["zakat_due"] == round(lt_data["zakatable_base"] * 0.025, 2)

    # Core Invariants
    assert lt_data["zakatable_base"] < active_data["zakatable_base"]
    assert lt_data["zakat_due"] < active_data["zakat_due"]

    # Verify per-holding breakdown reflects proper method applied
    for item in lt_data["breakdown"]:
        assert item["method_applied"] == "Long-Term (Zakatable Net Working Assets)"
        assert item["zakatable_amount"] < item["market_value"]

    for item in active_data["breakdown"]:
        assert item["method_applied"] == "Active Trader (100% Market Value)"
        assert item["zakatable_amount"] == item["market_value"]


@pytest.mark.asyncio
async def test_vector4_negative_working_capital_company_floor(client: AsyncClient):
    """Company with negative working capital (NEG-WC.NS):
    ZNWA is clamped to 0.0 INR (non-negative floor), ensuring negative working capital
    does not subtract from other holdings or cash.
    """
    holdings = [
        {"ticker": "NEG-WC.NS", "shares": 1000},
    ]
    cash = 60000.00

    res = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "method": "long_term",
            "holdings": holdings,
            "cash_balance": cash,
            "calendar": "lunar",
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert len(data["breakdown"]) == 1
    item = data["breakdown"][0]
    assert item["znwa_per_share"] == 0.0
    assert item["zakatable_amount"] == 0.0
    # Zakatable base is strictly the cash balance
    assert data["zakatable_base"] == cash
    assert data["is_obligatory"] is True
    assert data["zakat_due"] == round(cash * 0.025, 2)


# ===========================================================================
# Vector 5: Unseeded Ticker Fallback
# ===========================================================================


@pytest.mark.asyncio
async def test_vector5_unseeded_ticker_conservative_25_pct_proxy(client: AsyncClient):
    """When an unseeded ticker (e.g. UNKNOWN.NS) is provided with current_price
    and without znwa_per_share in long_term mode:
    System must apply conservative 25% proxy of current market price without crashing.
    """
    price = 600.00
    shares = 200
    expected_mkt_val = round(price * shares, 2)  # 120,000 INR
    expected_znwa_ps = round(price * 0.25, 2)  # 150.00 INR
    expected_zakatable = round(expected_znwa_ps * shares, 2)  # 30,000 INR

    payload = {
        "method": "long_term",
        "holdings": [
            {
                "ticker": "UNKNOWN_EQUITY.NS",
                "shares": shares,
                "current_price": price,
            }
        ],
        "cash_balance": 30000.00,
        "calendar": "lunar",
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert len(data["breakdown"]) == 1
    bd = data["breakdown"][0]
    assert bd["ticker"] == "UNKNOWN_EQUITY.NS"
    assert bd["current_price"] == price
    assert bd["market_value"] == expected_mkt_val
    assert bd["znwa_per_share"] == expected_znwa_ps
    assert bd["zakatable_amount"] == expected_zakatable
    assert bd["method_applied"] == "Long-Term (Zakatable Net Working Assets)"

    # Total zakatable base = 30,000 (holding) + 30,000 (cash) = 60,000 INR
    assert data["zakatable_base"] == 60000.00
    assert data["is_obligatory"] is True
    assert data["zakat_due"] == 1500.00


@pytest.mark.asyncio
async def test_vector5_unseeded_ticker_with_explicit_znwa_override(client: AsyncClient):
    """When an unseeded ticker is provided with an explicit znwa_per_share,
    the engine should respect the user-supplied ZNWA instead of the 25% proxy.
    """
    payload = {
        "method": "long_term",
        "holdings": [
            {
                "ticker": "CUSTOM_ASSET.NS",
                "shares": 100,
                "current_price": 1000.0,
                "znwa_per_share": 312.50,  # Explicit custom ZNWA
            }
        ],
        "cash_balance": 0.0,
        "calendar": "lunar",
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()

    bd = data["breakdown"][0]
    assert bd["znwa_per_share"] == 312.50
    assert bd["zakatable_amount"] == 31250.00
    assert data["zakatable_base"] == 31250.00
    # 31250 < 53550 -> exempt
    assert data["is_obligatory"] is False
    assert data["zakat_due"] == 0.0


@pytest.mark.asyncio
async def test_vector5_unseeded_ticker_missing_both_price_and_znwa_does_not_crash(
    client: AsyncClient,
):
    """Unseeded ticker with neither price nor znwa in DB or request.
    System must handle gracefully without 500 error or crash.
    """
    payload = {
        "method": "long_term",
        "holdings": [
            {
                "ticker": "GHOST_TICKER.NS",
                "shares": 500,
            }
        ],
        "cash_balance": 100000.0,
        "calendar": "lunar",
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()

    bd = data["breakdown"][0]
    assert bd["current_price"] == 0.0
    assert bd["znwa_per_share"] == 0.0
    assert bd["zakatable_amount"] == 0.0
    assert data["zakatable_base"] == 100000.0
    assert data["is_obligatory"] is True
    assert data["zakat_due"] == 2500.00


@pytest.mark.asyncio
async def test_vector5_long_term_aggregate_portfolio_value_proxy(client: AsyncClient):
    """When a user supplies only aggregate portfolio_value without individual holdings
    under long-term method, the system applies the conservative 25% proxy to the portfolio value.
    """
    payload = {
        "method": "long_term",
        "portfolio_value": 400000.0,  # 4 Lakhs
        "cash_balance": 20000.0,  # 20k
        "calendar": "lunar",
    }
    response = await client.post("/api/v1/zakat/calculate", json=payload)
    assert response.status_code == 200
    data = response.json()

    # 25% of 400,000 = 100,000 + 20,000 cash = 120,000 INR
    assert data["zakatable_base"] == 120000.00
    assert data["is_obligatory"] is True
    assert data["zakat_due"] == 3000.00


# ===========================================================================
# Benchmark: Zakat Endpoints Sub-50ms p95 Latency SLA Verification
# ===========================================================================


@pytest.mark.asyncio
async def test_zakat_endpoint_sub_50ms_latency_sla(client: AsyncClient):
    """Verifies that POST /api/v1/zakat/calculate strictly meets the sub-50ms p95 SLA
    for both Active Trader and Long-Term Investor (with DB lookups) methods.
    """
    import statistics
    import time

    payloads = [
        (
            "Active Trader Zakat",
            {
                "method": "active",
                "portfolio_value": 1000000.0,
                "cash_balance": 50000.0,
                "calendar": "lunar",
            },
        ),
        (
            "Long-Term Investor Zakat (with SQLite Lookups)",
            {
                "method": "long_term",
                "holdings": [
                    {"ticker": "TCS.NS", "shares": 500},
                    {"ticker": "INFY.NS", "shares": 1000},
                ],
                "cash_balance": 25000.0,
                "calendar": "lunar",
            },
        ),
    ]

    for name, payload in payloads:
        # Warm-up (5 requests)
        for _ in range(5):
            res = await client.post("/api/v1/zakat/calculate", json=payload)
            assert res.status_code == 200

        # Benchmark (50 iterations)
        latencies_ms = []
        for _ in range(50):
            t0 = time.perf_counter_ns()
            res = await client.post("/api/v1/zakat/calculate", json=payload)
            t1 = time.perf_counter_ns()
            assert res.status_code == 200
            latencies_ms.append((t1 - t0) / 1_000_000.0)

        p95 = sorted(latencies_ms)[int(0.95 * len(latencies_ms))]
        avg = statistics.mean(latencies_ms)
        min_lat = min(latencies_ms)
        max_lat = max(latencies_ms)

        print(
            f"\n[BENCHMARK] {name} -> Avg: {avg:.2f}ms | Min: {min_lat:.2f}ms | Max: {max_lat:.2f}ms | p95: {p95:.2f}ms"
        )
        assert p95 < 50.0, f"p95 latency {p95:.2f}ms breached sub-50ms SLA for {name}"
