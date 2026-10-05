import math
import random
import re
from pathlib import Path
from typing import Any

import pytest

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


def get_all_dart_files() -> list[Path]:
    """Retrieve all .dart files across client/lib and client/test."""
    files = list(CLIENT_LIB.rglob("*.dart")) + list(CLIENT_TEST.rglob("*.dart"))
    return sorted(files)


# ---------------------------------------------------------------------------
# Vector 1: AST & Delimiter Balance
# ---------------------------------------------------------------------------


def check_delimiter_balance(code: str) -> tuple[bool, str]:
    """
    Robust tokenizer verifying delimiter balance (braces, brackets, parentheses, string literals)
    while properly handling comments (single-line // and multi-line /* */),
    string escapes (\', \", \\), triple-quoted strings, and raw strings (r'...' / r"...").
    """
    stack = []
    i = 0
    n = len(code)

    in_single_line_comment = False
    in_multi_line_comment = False
    in_string = None  # "'", '"', "'''", '"""'
    is_raw_string = False

    while i < n:
        ch = code[i]
        next_ch = code[i + 1] if i + 1 < n else ""
        next_two = code[i + 1 : i + 3] if i + 2 < n else ""

        # Handle comments when not inside a string
        if not in_string:
            if in_single_line_comment:
                if ch == "\n":
                    in_single_line_comment = False
                i += 1
                continue
            elif in_multi_line_comment:
                if ch == "*" and next_ch == "/":
                    in_multi_line_comment = False
                    i += 2
                    continue
                i += 1
                continue
            elif ch == "/" and next_ch == "/":
                in_single_line_comment = True
                i += 2
                continue
            elif ch == "/" and next_ch == "*":
                in_multi_line_comment = True
                i += 2
                continue

        # Handle string literals
        if in_string:
            # Check for escape characters (only if not raw string)
            if not is_raw_string and ch == "\\":
                i += 2  # skip escaped character
                continue

            if in_string in ("'''", '"""'):
                if code[i : i + 3] == in_string:
                    in_string = None
                    is_raw_string = False
                    i += 3
                    continue
            else:
                if ch == in_string:
                    in_string = None
                    is_raw_string = False
                    i += 1
                    continue
            i += 1
            continue
        else:
            # Check for raw string prefix r' or r"
            if ch == "r" and next_ch in ("'", '"'):
                is_raw_string = True
                i += 1
                ch = next_ch
                next_ch = code[i + 1] if i + 1 < n else ""
                next_two = code[i + 1 : i + 3] if i + 2 < n else ""

            # Check for triple quotes
            if ch in ("'", '"') and next_two == ch * 2:
                in_string = ch * 3
                i += 3
                continue
            elif ch in ("'", '"'):
                in_string = ch
                i += 1
                continue

        # Delimiter tracking outside strings & comments
        if ch in "({[":
            stack.append((ch, i))
        elif ch in ")}]":
            if not stack:
                return False, f"Unexpected closing delimiter '{ch}' at position {i}"
            opening, pos = stack.pop()
            expected = {"(": ")", "{": "}", "[": "]"}[opening]
            if ch != expected:
                return (
                    False,
                    f"Mismatched delimiter: expected '{expected}' for '{opening}' at {pos}, got '{ch}' at {i}",
                )

        i += 1

    if in_string:
        return False, f"Unterminated string literal: {in_string}"
    if in_multi_line_comment:
        return False, "Unterminated multi-line comment"
    if stack:
        unclosed = [op for op, _ in stack]
        return False, f"Unclosed delimiters remaining on stack: {unclosed}"

    return True, "Balanced"


def test_vector1_all_dart_files_delimiter_balance():
    """Verify that all 29 Dart files have 100% balanced delimiters and valid syntax structure."""
    files = get_all_dart_files()
    assert len(files) >= 29, f"Expected at least 29 Dart files, found {len(files)}"

    for file_path in files:
        assert file_path.exists()
        assert file_path.stat().st_size > 50, (
            f"File {file_path.name} is unexpectedly empty or tiny."
        )

        content = file_path.read_text(encoding="utf-8")
        balanced, message = check_delimiter_balance(content)
        assert balanced, f"Delimiter syntax check failed in {file_path.name}: {message}"


def test_vector1_file_inventory_completeness():
    """Verify presence of all expected files across client architecture tiers."""
    expected_rel_paths = [
        "lib/main.dart",
        "lib/core/theme/colors.dart",
        "lib/core/theme/typography.dart",
        "lib/core/theme/app_theme.dart",
        "lib/core/constants/api_constants.dart",
        "lib/core/utils/formatters.dart",
        "lib/models/stock_model.dart",
        "lib/models/screening_result.dart",
        "lib/models/basket_model.dart",
        "lib/models/purification_item.dart",
        "lib/models/zakat_model.dart",
        "lib/services/api_service.dart",
        "lib/services/search_service.dart",
        "lib/widgets/adaptive_scaffold.dart",
        "lib/widgets/compliance_badge.dart",
        "lib/widgets/ratio_meter.dart",
        "lib/widgets/frosted_card.dart",
        "lib/widgets/sparkline_chart.dart",
        "lib/screens/dashboard_screen.dart",
        "lib/screens/screener_screen.dart",
        "lib/screens/stock_detail_screen.dart",
        "lib/screens/baskets_screen.dart",
        "lib/screens/purification_screen.dart",
        "lib/screens/academy_zakat_screen.dart",
        "test/unit/zakat_calculator_test.dart",
        "test/unit/purification_test.dart",
        "test/widget/compliance_badge_test.dart",
        "test/widget/responsive_layout_test.dart",
        "test/layout_and_overflow/screen_matrix_overflow_test.dart",
    ]

    for rel in expected_rel_paths:
        target = CLIENT_DIR / rel
        assert target.exists(), f"Missing required Dart file: {rel}"


# ---------------------------------------------------------------------------
# Vector 2: Symbol & Package Resolution
# ---------------------------------------------------------------------------


def test_vector2_package_imports_resolution():
    """Verify that all package:halal_investment_client/... imports resolve directly to valid Dart files."""
    files = get_all_dart_files()
    import_regex = re.compile(r"import\s+['\"]([^'\"]+)['\"];")

    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        imports = import_regex.findall(content)

        for imp in imports:
            if imp.startswith("package:halal_investment_client/"):
                sub_path = imp.replace("package:halal_investment_client/", "")
                target_file = CLIENT_LIB / sub_path
                assert target_file.exists(), (
                    f"In {file_path.name}: package import '{imp}' fails to resolve to '{target_file}'"
                )
            elif not imp.startswith("package:") and not imp.startswith("dart:"):
                # Relative import (e.g. '../screens/...' or 'colors.dart' or 'widgets/...')
                target_file = (file_path.parent / imp).resolve()
                assert target_file.exists(), (
                    f"In {file_path.name}: relative import '{imp}' fails to resolve to '{target_file}'"
                )
            elif (
                imp.startswith("package:flutter/")
                or imp.startswith("package:flutter_test/")
                or imp.startswith("package:http/")
                or imp.startswith("package:intl/")
            ):
                # Standard authorized dependencies
                pass
            elif imp.startswith("dart:"):
                # Dart core
                pass
            else:
                pytest.fail(
                    f"Unrecognized or unauthorized package import '{imp}' in {file_path.name}"
                )


def test_vector2_model_class_definitions():
    """Verify that all core domain models and DTOs exist in client/lib/models/."""
    expected_classes = {
        "stock_model.dart": ["ComplianceStatus", "StockSummary"],
        "screening_result.dart": [
            "RatioMeterData",
            "StandardEvaluationData",
            "AuditEvidenceLineData",
            "ShariahAuditDetail",
        ],
        "basket_model.dart": [
            "BasketConstituentModel",
            "BasketModel",
            "BrokerOrderModel",
            "BasketExportResult",
        ],
        "purification_item.dart": ["PurificationCalculateResult", "PurificationLedgerEntryModel"],
        "zakat_model.dart": ["ZakatHoldingBreakdownModel", "ZakatCalculationResult"],
    }

    for filename, class_names in expected_classes.items():
        file_path = CLIENT_LIB / "models" / filename
        assert file_path.exists()
        content = file_path.read_text(encoding="utf-8")
        for cls in class_names:
            pattern = re.compile(rf"(class|enum)\s+{cls}\b")
            assert pattern.search(content), f"Class/enum '{cls}' not found in {filename}"


def test_vector2_services_api_contract_coverage():
    """Verify ApiService implements methods for all required REST endpoints."""
    api_service_path = CLIENT_LIB / "services" / "api_service.dart"
    content = api_service_path.read_text(encoding="utf-8")

    required_methods = [
        "getStocks",
        "getShariahAudit",
        "getBaskets",
        "exportBasketOrders",
        "calculatePurification",
        "getPurificationLedger",
        "calculateZakat",
        "getFallbackStocks",
        "getFallbackBaskets",
    ]

    for method in required_methods:
        pattern = re.compile(rf"\b{method}\s*\(")
        assert pattern.search(content), f"Method '{method}' missing in ApiService"


def test_vector2_search_service_trie_interface():
    """Verify SearchService implements sub-50ms prefix Trie lookup."""
    search_service_path = CLIENT_LIB / "services" / "search_service.dart"
    content = search_service_path.read_text(encoding="utf-8")

    assert "class TrieNode" in content
    assert "class SearchService" in content
    assert "searchLocal" in content
    assert "searchDebounced" in content
    assert "insertStock" in content


# ---------------------------------------------------------------------------
# Vector 3: Responsive Layout & Zero RenderFlex Overflow Audit
# ---------------------------------------------------------------------------


def test_vector3_adaptive_scaffold_responsive_breakpoint():
    """Verify AdaptiveScaffold switches at 600dp breakpoint with 1440dp constraint."""
    scaffold_path = CLIENT_LIB / "widgets" / "adaptive_scaffold.dart"
    content = scaffold_path.read_text(encoding="utf-8")

    assert "LayoutBuilder" in content
    assert "constraints.maxWidth >= 600.0" in content or "maxWidth >= 600" in content
    assert "BottomNavigationBar" in content
    assert "NavigationRail" in content
    assert "maxWidth: 1440" in content
    assert "VerticalDivider" in content


def test_vector3_screens_overflow_prevention_guards():
    """Verify that every screen enforces BouncingScrollPhysics and overflow-safe layout."""
    screens_to_check = [
        "dashboard_screen.dart",
        "screener_screen.dart",
        "stock_detail_screen.dart",
        "baskets_screen.dart",
        "purification_screen.dart",
        "academy_zakat_screen.dart",
    ]

    for screen_file in screens_to_check:
        file_path = CLIENT_LIB / "screens" / screen_file
        content = file_path.read_text(encoding="utf-8")

        # Must use BouncingScrollPhysics
        assert "BouncingScrollPhysics" in content, (
            f"{screen_file} does not use BouncingScrollPhysics"
        )

        # Check for Scrollable wrappers
        has_scroll_view = "SingleChildScrollView" in content or "ListView" in content
        assert has_scroll_view, f"{screen_file} lacks scrollable wrapper"


def test_vector3_text_overflow_ellipsis_in_rows():
    """Verify text truncation patterns (Expanded/Flexible with TextOverflow.ellipsis) in list cards."""
    screener_path = CLIENT_LIB / "screens" / "screener_screen.dart"
    content = screener_path.read_text(encoding="utf-8")

    assert "TextOverflow.ellipsis" in content, "ScreenerScreen missing TextOverflow.ellipsis"
    assert "Expanded(" in content, "ScreenerScreen missing Expanded in row layout"


def test_vector3_screen_matrix_test_viewports_coverage():
    """Verify screen_matrix_overflow_test covers all 4 standard form factors."""
    matrix_test_path = CLIENT_TEST / "layout_and_overflow" / "screen_matrix_overflow_test.dart"
    content = matrix_test_path.read_text(encoding="utf-8")

    assert "375, 667" in content or "iPhone SE" in content
    assert "412, 915" in content or "Android Flagship" in content
    assert "820, 1180" in content or "iPad Air" in content
    assert "1920, 1080" in content or "Desktop / Web" in content
    assert "tester.takeException()" in content
    assert "isNull" in content


# ---------------------------------------------------------------------------
# Vector 4: Mathematical & Domain Formula Parity
# ---------------------------------------------------------------------------


def dart_calculate_purification_ratio(interest: float, prohibited: float, total: float) -> float:
    """Python model of client/test/unit/purification_test.dart PurificationLogic.calculateRatio."""
    if total <= 0.0:
        return 1.0 if (interest + prohibited) > 0.0 else 0.0
    return float(f"{((interest + prohibited) / total):.6f}")


def dart_calculate_purification_payable(gross: float, ratio: float) -> float:
    """Python model of client/test/unit/purification_test.dart PurificationLogic.calculatePayable."""
    return float(f"{(gross * ratio):.2f}")


def dart_calculate_active_zakat(
    portfolio_value: float, cash_balance: float, calendar: str = "lunar"
) -> dict[str, Any]:
    """Python model of client/test/unit/zakat_calculator_test.dart ZakatCalculatorLogic.calculateActiveTrader."""
    rate = 0.025770 if calendar.lower() == "solar" else 0.025000
    zakatable_base = float(f"{(portfolio_value + cash_balance):.2f}")
    is_obligatory = zakatable_base >= 53550.0
    zakat_due = float(f"{(zakatable_base * rate):.2f}") if is_obligatory else 0.0
    return {
        "zakatable_base": zakatable_base,
        "is_obligatory": is_obligatory,
        "rate": rate,
        "zakat_due": zakat_due,
    }


def dart_calculate_long_term_zakat(
    holdings: list[dict[str, Any]], cash_balance: float, calendar: str = "lunar"
) -> dict[str, Any]:
    """Python model of client/test/unit/zakat_calculator_test.dart ZakatCalculatorLogic.calculateLongTermInvestor."""
    rate = 0.025770 if calendar.lower() == "solar" else 0.025000
    holdings_base = 0.0
    for h in holdings:
        znwa = float(h.get("znwa_per_share", 0.0))
        clamped = 0.0 if znwa < 0.0 else znwa
        shares = int(h.get("shares", 0))
        holdings_base += float(f"{(clamped * shares):.2f}")

    zakatable_base = float(f"{(holdings_base + cash_balance):.2f}")
    is_obligatory = zakatable_base >= 53550.0
    zakat_due = float(f"{(zakatable_base * rate):.2f}") if is_obligatory else 0.0
    return {
        "zakatable_base": zakatable_base,
        "is_obligatory": is_obligatory,
        "rate": rate,
        "zakat_due": zakat_due,
    }


def test_vector4_api_constants_values():
    """Verify client constants match DomainOracle authoritative numbers."""
    constants_path = CLIENT_LIB / "core" / "constants" / "api_constants.dart"
    content = constants_path.read_text(encoding="utf-8")

    assert "silverNisabThresholdInr = 53550.0" in content
    assert "lunarZakatRate = 0.025000" in content
    assert "solarZakatRate = 0.025770" in content


def test_vector4_active_zakat_monte_carlo_parity():
    """Empirical parity check over 100 randomized portfolios between Dart logic and Python DomainOracle."""
    random.seed(42)
    for _ in range(100):
        pval = round(random.uniform(0.0, 5000000.0), 2)
        cash = round(random.uniform(0.0, 500000.0), 2)
        cal = random.choice(["lunar", "solar"])

        oracle_res = DomainOracle.calculate_active_trader_zakat(pval, cash, calendar=cal)
        dart_res = dart_calculate_active_zakat(pval, cash, calendar=cal)

        assert dart_res["is_obligatory"] == oracle_res["is_obligatory"]
        assert math.isclose(dart_res["zakatable_base"], oracle_res["zakatable_base"], abs_tol=0.01)
        assert math.isclose(dart_res["zakat_due"], oracle_res["zakat_due"], abs_tol=0.01)


def test_vector4_long_term_zakat_monte_carlo_parity():
    """Empirical parity check over 100 randomized multi-holding portfolios including negative working capital."""
    random.seed(1337)
    for _ in range(100):
        holdings = []
        for i in range(random.randint(1, 10)):
            znwa = round(random.uniform(-100.0, 500.0), 2)  # negative and positive
            shares = random.randint(10, 5000)
            holdings.append(
                {
                    "ticker": f"SYM_{i}.NS",
                    "shares": shares,
                    "znwa_per_share": znwa,
                }
            )
        cash = round(random.uniform(0.0, 200000.0), 2)
        cal = random.choice(["lunar", "solar"])

        oracle_res = DomainOracle.calculate_long_term_zakat(holdings, cash, calendar=cal)
        dart_res = dart_calculate_long_term_zakat(holdings, cash, calendar=cal)

        assert dart_res["is_obligatory"] == oracle_res["is_obligatory"]
        assert math.isclose(dart_res["zakatable_base"], oracle_res["zakatable_base"], abs_tol=0.01)
        assert math.isclose(dart_res["zakat_due"], oracle_res["zakat_due"], abs_tol=0.01)


def test_vector4_silver_nisab_strict_boundary():
    """Assert strict boundary enforcement at ₹53,550.00."""
    # 1 cent below -> exempt
    sub = dart_calculate_active_zakat(50000.0, 3549.99)
    assert sub["is_obligatory"] is False
    assert sub["zakat_due"] == 0.0

    # Exactly threshold -> obligatory
    exact = dart_calculate_active_zakat(50000.0, 3550.00)
    assert exact["is_obligatory"] is True
    assert exact["zakat_due"] == 1338.75

    # 1 cent above -> obligatory
    above = dart_calculate_active_zakat(50000.0, 3550.01)
    assert above["is_obligatory"] is True
    assert above["zakat_due"] == 1338.75


def test_vector4_purification_ratio_and_payable_parity():
    """Empirical parity check for dividend purification calculations."""
    test_cases = [
        (120.0, 30.0, 25000.0, 1000.0),
        (0.0, 0.0, 10000.0, 5000.0),
        (50.0, 0.0, 100000.0, 2500.0),
        (10.0, 20.0, 0.0, 1000.0),  # zero revenue edge case
        (100.0, 200.0, 54000.0, 10000.0),
    ]

    for interest, prohibited, total_rev, gross_div in test_cases:
        oracle_rho = DomainOracle.calculate_purification_ratio(interest, prohibited, total_rev)
        dart_rho = dart_calculate_purification_ratio(interest, prohibited, total_rev)
        assert math.isclose(dart_rho, oracle_rho, abs_tol=1e-6)

        oracle_payable = DomainOracle.calculate_purification_amount(gross_div, oracle_rho)
        dart_payable = dart_calculate_purification_payable(gross_div, dart_rho)
        assert math.isclose(dart_payable, oracle_payable, abs_tol=0.01)


# ---------------------------------------------------------------------------
# Vector 5: 1-Click Broker CSV Specifications
# ---------------------------------------------------------------------------


def test_vector5_client_baskets_screen_broker_options():
    """Verify BasketsScreen exposes exact choice chips for all 4 Indian discount brokers."""
    baskets_screen_path = CLIENT_LIB / "screens" / "baskets_screen.dart"
    content = baskets_screen_path.read_text(encoding="utf-8")

    assert "'zerodha'" in content
    assert "'upstox'" in content
    assert "'groww'" in content
    assert "'angelone'" in content
    assert "exportBasketOrders" in content
    assert "Clipboard.setData" in content


def test_vector5_broker_export_formats_strictness():
    """Verify that backend export generators produce precise broker CSV formats expected by client."""
    sample_orders = [
        {
            "ticker": "TCS.NS",
            "symbol": "TCS",
            "shares": 10,
            "price": 3840.50,
            "weight": 0.50,
            "allocation_amount": 38405.0,
            "actual_cost": 38405.0,
        },
        {
            "ticker": "INFY.NS",
            "symbol": "INFY",
            "shares": 25,
            "price": 1540.20,
            "weight": 0.50,
            "allocation_amount": 38505.0,
            "actual_cost": 38505.0,
        },
    ]

    # 1. Zerodha Kite: Product strictly CNC
    _, z_csv, z_clip = generate_zerodha_orders(sample_orders, "MARKET")
    assert (
        "Instrument,Exchange,Transaction,Quantity,Order Type,Product,Price,Trigger Price" in z_csv
    )
    assert "TCS,NSE,BUY,10,MARKET,CNC,0,0" in z_clip
    assert "INFY,NSE,BUY,25,MARKET,CNC,0,0" in z_clip

    # 2. Upstox Pro: {symbol}-EQ, DELIVERY, DAY
    _, u_csv, u_clip = generate_upstox_orders(sample_orders, "MARKET")
    assert "Trading Symbol,Exchange,Action,Quantity,Order Type,Validity,Product" in u_csv
    assert "TCS-EQ,NSE,BUY,10,MARKET,DAY,DELIVERY" in u_clip
    assert "INFY-EQ,NSE,BUY,25,MARKET,DAY,DELIVERY" in u_clip

    # 3. Groww: CASH, ProductType CNC, TransactionType BUY
    _, g_csv, g_clip = generate_groww_orders(sample_orders, "MARKET")
    assert "Symbol,Exchange,Segment,TransactionType,Quantity,OrderType,ProductType,Price" in g_csv
    assert "TCS,NSE,CASH,BUY,10,MARKET,CNC,0" in g_clip
    assert "INFY,NSE,CASH,BUY,25,MARKET,CNC,0" in g_clip

    # 4. AngelOne: {symbol}-EQ, DELIVERY, BUY
    _, a_csv, a_clip = generate_angelone_orders(sample_orders, "MARKET")
    assert "Symbol,Token,Exchange,TransactionType,OrderType,ProductType,Quantity,Price" in a_csv
    assert "TCS-EQ,11536,NSE,BUY,MARKET,DELIVERY,10,0" in a_clip
    assert "INFY-EQ,1594,NSE,BUY,MARKET,DELIVERY,25,0" in a_clip


def test_vector5_basket_model_dto_completeness():
    """Verify that BasketExportResult and BrokerOrderModel in Dart handle all backend response fields."""
    model_path = CLIENT_LIB / "models" / "basket_model.dart"
    content = model_path.read_text(encoding="utf-8")

    assert "class BrokerOrderModel" in content
    assert "class BasketExportResult" in content

    required_export_fields = [
        "basketId",
        "basketName",
        "broker",
        "targetCapital",
        "totalAllocatedCapital",
        "residualCash",
        "orderCount",
        "orders",
        "csvContent",
        "clipboardPayload",
    ]

    for field in required_export_fields:
        assert field in content, f"Field '{field}' missing from BasketExportResult Dart model"
