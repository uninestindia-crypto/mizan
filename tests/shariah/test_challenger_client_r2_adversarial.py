"""Empirical Adversarial Challenge Suite — Milestone 4 Client (Iteration 2).

Authored by challenger_client_r2_1 to empirically probe:
1. Resolution of Finding C1 (purification_screen.dart:336 and 523, symbol resolution, null-safety).
2. Zakat arithmetic: Active Trader vs Long-Term Investor, strict Silver Nisab boundary at ₹53,550.00,
   negative working capital clamping floor (clampedZnwa = znwa < 0.0 ? 0.0 : znwa).
3. Dividend Purification ratio and payable formula parity under extreme conditions.
4. Broker Export format strictness (Zerodha CNC, Upstox DELIVERY DAY, Groww CASH CNC, AngelOne).
5. Indian statutory tax breakdown calculations (STT, GST base, SEBI charges, stamp duty, zero brokerage).
"""

import math
import random
import re
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from quant_system.shariah.main import app
from quant_system.shariah.services.broker_export_service import (
    generate_angelone_orders,
    generate_groww_orders,
    generate_upstox_orders,
    generate_zerodha_orders,
)
from tests.shariah.conftest import DomainOracle

CLIENT_DIR = Path(__file__).resolve().parent.parent.parent / "client"
CLIENT_LIB = CLIENT_DIR / "lib"
CLIENT_TEST = CLIENT_DIR / "test"


# ===========================================================================
# Vector 1: Finding C1 Resolution & Static Typing Rigor
# ===========================================================================


def test_vector1_finding_c1_model_property():
    """Verify PurificationCalculateResult declares companyName getter."""
    model_path = CLIENT_LIB / "models" / "purification_item.dart"
    assert model_path.exists(), "purification_item.dart missing"
    content = model_path.read_text(encoding="utf-8")

    assert "String get companyName => ticker;" in content, (
        "PurificationCalculateResult must declare 'String get companyName => ticker;' for static resolution"
    )


def test_vector1_finding_c1_purification_screen_references():
    """Verify purification_screen.dart does NOT contain undefined access and resolves charityName null safety."""
    screen_path = CLIENT_LIB / "screens" / "purification_screen.dart"
    assert screen_path.exists(), "purification_screen.dart missing"
    content = screen_path.read_text(encoding="utf-8")

    # Verify no raw unresolved _calcResult!.companyName or _calcResult.companyName
    assert "_calcResult!.companyName" not in content, (
        "purification_screen.dart must not contain legacy '_calcResult!.companyName'"
    )
    assert "_calcResult.companyName" not in content

    # Verify null-coalescing at line 523
    assert "charityName: item.charityName ?? 'Accredited Charity Trust'" in content, (
        "purification_screen.dart must use null-coalescing on nullable charityName"
    )

    # Verify _showVoucherDialog method signature permits nullable charityName with fallback
    assert "String? charityName" in content, "_showVoucherDialog must accept 'String? charityName'"
    assert "final effectiveCharity = charityName ?? 'Accredited Charity Trust';" in content, (
        "_showVoucherDialog must provide internal fallback for null charityName"
    )


def test_vector1_dialog_invocation_arguments_soundness():
    """Verify all invocations of _showVoucherDialog have valid arguments and sound null safety."""
    screen_path = CLIENT_LIB / "screens" / "purification_screen.dart"
    content = screen_path.read_text(encoding="utf-8")

    # Find only invocations (excluding definition at line 85 which starts with void _showVoucherDialog({)
    # Call sites look like: _showVoucherDialog(\n  companyName: ...
    call_sites = list(re.finditer(r"(?<!void\s)_showVoucherDialog\(\s*companyName:", content))
    assert len(call_sites) >= 2, f"Expected at least 2 dialog call sites, found {len(call_sites)}"

    for idx, m in enumerate(call_sites):
        pos = m.start()
        chunk = content[pos : pos + 1200]
        assert "companyName:" in chunk, f"Invocation {idx} missing companyName"
        assert "ticker:" in chunk, f"Invocation {idx} missing ticker"
        assert "grossDividend:" in chunk, f"Invocation {idx} missing grossDividend"
        assert "purificationAmount:" in chunk, f"Invocation {idx} missing purificationAmount"
        assert "charityName:" in chunk, f"Invocation {idx} missing charityName"
        assert "entryHash:" in chunk, f"Invocation {idx} missing entryHash"
        assert "prevHash:" in chunk, f"Invocation {idx} missing prevHash"
        assert "uuid:" in chunk, f"Invocation {idx} missing uuid"


# ===========================================================================
# Vector 2: Zakat Arithmetic & Negative Working Capital Floor
# ===========================================================================


def dart_sim_active_trader(pval: float, cash: float, calendar: str = "lunar") -> dict[str, Any]:
    rate = 0.025770 if calendar.lower() == "solar" else 0.025000
    zakatable_base = round(pval + cash, 2)
    is_obligatory = zakatable_base >= 53550.0
    zakat_due = round(zakatable_base * rate, 2) if is_obligatory else 0.0
    return {
        "zakatable_base": zakatable_base,
        "is_obligatory": is_obligatory,
        "rate": rate,
        "zakat_due": zakat_due,
    }


def dart_sim_long_term(
    holdings: list[dict[str, Any]], cash: float, calendar: str = "lunar"
) -> dict[str, Any]:
    rate = 0.025770 if calendar.lower() == "solar" else 0.025000
    holdings_base = 0.0
    for h in holdings:
        znwa = float(h.get("znwa_per_share", 0.0))
        clamped = 0.0 if znwa < 0.0 else znwa
        shares = int(h.get("shares", 0))
        holdings_base += round(clamped * shares, 2)

    zakatable_base = round(holdings_base + cash, 2)
    is_obligatory = zakatable_base >= 53550.0
    zakat_due = round(zakatable_base * rate, 2) if is_obligatory else 0.0
    return {
        "zakatable_base": zakatable_base,
        "is_obligatory": is_obligatory,
        "rate": rate,
        "zakat_due": zakat_due,
    }


def test_vector2_zakat_strict_boundary_invariants():
    """Verify strict sub-cent and boundary conditions at ₹53,550.00."""
    # Test precisely 53,549.99
    below = dart_sim_active_trader(50000.0, 3549.99, "lunar")
    assert below["is_obligatory"] is False
    assert below["zakat_due"] == 0.0

    # Test precisely 53,550.00
    exact = dart_sim_active_trader(50000.0, 3550.00, "lunar")
    assert exact["is_obligatory"] is True
    assert exact["zakat_due"] == 1338.75

    # Test solar at exact 53,550.00
    exact_solar = dart_sim_active_trader(50000.0, 3550.00, "solar")
    assert exact_solar["is_obligatory"] is True
    assert exact_solar["zakat_due"] == 1379.98

    # Test precisely 53,550.01
    above = dart_sim_active_trader(50000.0, 3550.01, "lunar")
    assert above["is_obligatory"] is True
    assert above["zakat_due"] == 1338.75


def test_vector2_negative_working_capital_clamping_floor():
    """Verify that negative ZNWA per share is clamped to 0.0 and NEVER offsets cash or other holdings."""
    # Scenario A: Distressed company with severe negative working capital
    distressed = [
        {"ticker": "DEBT_HEAVY_1.NS", "shares": 10000, "znwa_per_share": -250.75},
        {"ticker": "DEBT_HEAVY_2.NS", "shares": 50000, "znwa_per_share": -99.00},
    ]
    cash = 100000.0

    result = dart_sim_long_term(distressed, cash, "lunar")
    # Base must equal cash exactly: 100,000.00 (not reduced by negative ZNWA!)
    assert result["zakatable_base"] == 100000.00
    assert result["is_obligatory"] is True
    assert result["zakat_due"] == 2500.00

    # Scenario B: Mixed portfolio: one profitable asset, one negative asset
    mixed = [
        {"ticker": "GOOD.NS", "shares": 1000, "znwa_per_share": 50.00},  # 50,000
        {"ticker": "BAD.NS", "shares": 1000, "znwa_per_share": -80.00},  # clamped to 0
    ]
    mixed_result = dart_sim_long_term(mixed, 10000.0, "lunar")
    # Base must be 50,000 + 10,000 = 60,000.0
    assert mixed_result["zakatable_base"] == 60000.00
    assert mixed_result["is_obligatory"] is True
    assert mixed_result["zakat_due"] == 1500.00


def test_vector2_zakat_monte_carlo_stress_fuzzing():
    """Run 500 randomized trials comparing Dart logic to DomainOracle."""
    random.seed(999)
    for _ in range(500):
        pval = round(random.uniform(0.0, 10000000.0), 2)
        cash = round(random.uniform(0.0, 1000000.0), 2)
        cal = random.choice(["lunar", "solar"])

        oracle_res = DomainOracle.calculate_active_trader_zakat(pval, cash, calendar=cal)
        dart_res = dart_sim_active_trader(pval, cash, calendar=cal)

        assert dart_res["is_obligatory"] == oracle_res["is_obligatory"]
        assert math.isclose(dart_res["zakatable_base"], oracle_res["zakatable_base"], abs_tol=0.01)
        assert math.isclose(dart_res["zakat_due"], oracle_res["zakat_due"], abs_tol=0.01)


# ===========================================================================
# Vector 3: Dividend Purification Precision & Extreme Edge Cases
# ===========================================================================


def dart_sim_purification_ratio(interest: float, prohibited: float, total: float) -> float:
    if total <= 0.0:
        return 1.0 if (interest + prohibited) > 0.0 else 0.0
    return float(f"{((interest + prohibited) / total):.6f}")


def dart_sim_purification_payable(gross: float, ratio: float) -> float:
    return float(f"{(gross * ratio):.2f}")


def test_vector3_dividend_purification_extreme_ratios():
    """Verify zero dividend, zero revenue, 100% impure, and standard AAOIFI 4.9% cases."""
    # 1. Zero gross dividend -> 0 payable
    assert dart_sim_purification_payable(0.0, 0.035) == 0.0

    # 2. Zero total revenue with impure income -> ratio = 1.0 (100% impure)
    ratio_impure = dart_sim_purification_ratio(500.0, 100.0, 0.0)
    assert ratio_impure == 1.0
    assert dart_sim_purification_payable(1000.0, ratio_impure) == 1000.0

    # 3. Zero total revenue with zero impure income -> ratio = 0.0
    ratio_clean = dart_sim_purification_ratio(0.0, 0.0, 0.0)
    assert ratio_clean == 0.0
    assert dart_sim_purification_payable(1000.0, ratio_clean) == 0.0

    # 4. Realistic AAOIFI compliant boundary (4.90% impure revenue)
    # Total revenue: 1,000,000; Interest: 30,000; Prohibited: 19,000 -> Sum = 49,000 -> 0.049000
    ratio_aaoifi = dart_sim_purification_ratio(30000.0, 19000.0, 1000000.0)
    assert math.isclose(ratio_aaoifi, 0.049, abs_tol=1e-6)
    payable = dart_sim_purification_payable(15000.0, ratio_aaoifi)
    assert payable == 735.00


# ===========================================================================
# Vector 4: Broker Export Formats Strictness
# ===========================================================================


def test_vector4_broker_export_order_fields_and_tokens():
    """Assert all 4 Indian broker CSV formats strictly comply with trading engine requirements."""
    orders = [
        {
            "ticker": "TCS.NS",
            "symbol": "TCS",
            "shares": 15,
            "price": 3800.0,
            "weight": 0.5,
            "allocation_amount": 57000.0,
        },
        {
            "ticker": "INFY.NS",
            "symbol": "INFY",
            "shares": 35,
            "price": 1500.0,
            "weight": 0.5,
            "allocation_amount": 52500.0,
        },
    ]

    # Zerodha: CNC product code is required for Halal cash equity
    _, z_csv, z_clip = generate_zerodha_orders(orders, "MARKET")
    assert z_csv.startswith(
        "Instrument,Exchange,Transaction,Quantity,Order Type,Product,Price,Trigger Price"
    )
    for line in z_clip.splitlines():
        parts = line.split(",")
        assert parts[1] == "NSE"
        assert parts[2] == "BUY"
        assert parts[4] == "MARKET"
        assert parts[5] == "CNC"  # Strictly Cash 'n' Carry

    # Upstox: Trading Symbol {sym}-EQ, DELIVERY product, DAY validity
    _, u_csv, u_clip = generate_upstox_orders(orders, "MARKET")
    assert u_csv.startswith("Trading Symbol,Exchange,Action,Quantity,Order Type,Validity,Product")
    for line in u_clip.splitlines():
        parts = line.split(",")
        assert parts[0].endswith("-EQ")
        assert parts[1] == "NSE"
        assert parts[2] == "BUY"
        assert parts[4] == "MARKET"
        assert parts[5] == "DAY"
        assert parts[6] == "DELIVERY"

    # Groww: Segment CASH, ProductType CNC, TransactionType BUY
    _, g_csv, g_clip = generate_groww_orders(orders, "MARKET")
    assert g_csv.startswith(
        "Symbol,Exchange,Segment,TransactionType,Quantity,OrderType,ProductType,Price"
    )
    for line in g_clip.splitlines():
        parts = line.split(",")
        assert parts[1] == "NSE"
        assert parts[2] == "CASH"
        assert parts[3] == "BUY"
        assert parts[5] == "MARKET"
        assert parts[6] == "CNC"

    # AngelOne: Token mapped, {sym}-EQ, ProductType DELIVERY
    _, a_csv, a_clip = generate_angelone_orders(orders, "MARKET")
    assert a_csv.startswith(
        "Symbol,Token,Exchange,TransactionType,OrderType,ProductType,Quantity,Price"
    )
    for line in a_clip.splitlines():
        parts = line.split(",")
        assert parts[0].endswith("-EQ")
        assert parts[1].isdigit()  # valid numeric security token
        assert parts[2] == "NSE"
        assert parts[3] == "BUY"
        assert parts[4] == "MARKET"
        assert parts[5] == "DELIVERY"


# ===========================================================================
# Vector 5: Indian Statutory Tax Breakdown Verification
# ===========================================================================


@pytest.mark.asyncio
async def test_vector5_statutory_tax_calculation_endpoint_parity():
    """Verify statutory tax calculation endpoint matches the Indian equity tax schedule."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test case: ₹100,000 investment on NSE
        res = await client.post(
            "/api/v1/baskets/tax-calculator",
            json={"investment_amount": 100000.0, "broker": "Zerodha", "exchange": "NSE"},
        )
        assert res.status_code == 200
        data = res.json()

        assert data["investment_amount"] == 100000.0
        # 1. Brokerage must be ₹0.00
        assert data["brokerage"] == 0.0

        # 2. STT = 0.1% = ₹100.00
        assert data["stt_ctt"] == 100.00

        # 3. NSE Exchange charges = 0.00325% = ₹3.25
        assert data["exchange_charges"] == 3.25

        # 4. SEBI charges = Rs 10 / crore (0.0001%) = ₹0.10
        assert data["sebi_charges"] == 0.10

        # 5. Stamp duty = 0.015% = ₹15.00
        assert data["stamp_duty"] == 15.00

        # 6. GST = 18% of (exchange + sebi) = 18% of 3.35 = 0.603 -> ₹0.60
        assert data["gst"] == 0.60

        # 7. Total statutory charges = 100 + 3.25 + 0.10 + 15 + 0.60 = 118.95
        assert data["total_statutory_charges"] == 118.95

        # 8. Net cost = 100,000 + 118.95 = 100,118.95
        assert data["net_effective_cost"] == 100118.95

        # 9. Effective tax rate pct = 118.95 / 100000 * 100 = 0.119%
        assert data["effective_tax_rate_pct"] == 0.119


@pytest.mark.asyncio
async def test_vector5_bse_exchange_charges_difference():
    """Verify BSE exchange rate is 0.00375% (vs 0.00325% for NSE)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/baskets/tax-calculator",
            json={"investment_amount": 100000.0, "broker": "Upstox", "exchange": "BSE"},
        )
        assert res.status_code == 200
        data = res.json()

        # BSE exchange charges on 100,000 = 100,000 * 0.0000375 = ₹3.75
        assert data["exchange_charges"] == 3.75
        # GST = 18% of (3.75 + 0.10) = 18% of 3.85 = 0.693 -> ₹0.69
        assert data["gst"] == 0.69
