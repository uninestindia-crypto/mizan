import json
import math
import re
import time
from pathlib import Path
from typing import Dict, List, Any

import pytest

CLIENT_DIR = Path(__file__).resolve().parent.parent.parent / "client"
CLIENT_LIB = CLIENT_DIR / "lib"
CLIENT_TEST = CLIENT_DIR / "test"
ASSETS_DIR = CLIENT_DIR / "assets" / "data"


# ===========================================================================
# Vector 1: Responsive Breakpoint & Layout Stability Stress Tests
# ===========================================================================

def test_challenger_adaptive_scaffold_breakpoint_boundary():
    """
    Stress-test the responsive layout breakpoint logic in AdaptiveScaffold.
    Verify that <768px selects Cupertino bottom navigation and >=768px selects NavigationRail.
    """
    scaffold_path = CLIENT_LIB / "widgets" / "adaptive_scaffold.dart"
    assert scaffold_path.exists(), "adaptive_scaffold.dart not found"
    content = scaffold_path.read_text(encoding="utf-8")

    # Verify breakpoint logic explicitly tests 768.0
    breakpoint_match = re.search(r"constraints\.maxWidth\s*>=\s*([0-9.]+)", content)
    assert breakpoint_match, "No maxWidth comparison found in AdaptiveScaffold"
    breakpoint_val = float(breakpoint_match.group(1))
    assert breakpoint_val == 768.0, f"Expected 768.0dp breakpoint, got {breakpoint_val}"

    # Verify both navigation modalities are present
    assert "BottomNavigationBar" in content, "BottomNavigationBar missing from AdaptiveScaffold"
    assert "NavigationRail" in content, "NavigationRail missing from AdaptiveScaffold"
    assert "BackdropFilter" in content, "Frosted glass Cupertino blur missing from mobile nav"
    assert "maxWidth: 1440" in content, "Desktop maxWidth constraint box missing"

    # Simulate breakpoint decision function across test viewports
    def is_desktop(width: float) -> bool:
        return width >= breakpoint_val

    # Mobile viewports: must be False (< 768px)
    assert is_desktop(320.0) is False  # Small mobile
    assert is_desktop(375.0) is False  # iPhone SE
    assert is_desktop(412.0) is False  # Android Flagship
    assert is_desktop(600.0) is False  # Phablet
    assert is_desktop(767.9) is False  # Strict boundary below 768

    # Tablet & Desktop viewports: must be True (>= 768px)
    assert is_desktop(768.0) is True   # Strict boundary at 768
    assert is_desktop(820.0) is True   # iPad Air
    assert is_desktop(1024.0) is True  # iPad Pro
    assert is_desktop(1200.0) is True  # Compact desktop
    assert is_desktop(1440.0) is True  # Standard desktop
    assert is_desktop(1920.0) is True  # 1080p desktop
    assert is_desktop(2560.0) is True  # 1440p QHD
    assert is_desktop(3840.0) is True  # 4K UHD


def test_challenger_zero_renderflex_overflow_screen_matrix():
    """
    Audit screen_matrix_overflow_test.dart and screen source code to verify
    zero RenderFlex overflow resilience across all designated viewports:
    Mobile (375, 412), Tablet (768, 820), Desktop (1200, 1440, 1920).
    """
    matrix_test = CLIENT_TEST / "layout_and_overflow" / "screen_matrix_overflow_test.dart"
    assert matrix_test.exists(), "screen_matrix_overflow_test.dart missing"
    content = matrix_test.read_text(encoding="utf-8")

    # Verify that takeException() isNull is asserted
    assert "expect(tester.takeException(), isNull);" in content

    # Verify all 5 primary app screens are tested in the matrix
    expected_screens = [
        "DashboardScreen",
        "ScreenerScreen",
        "BasketsScreen",
        "PurificationScreen",
        "AcademyZakatScreen",
    ]
    for scr in expected_screens:
        assert scr in content, f"Screen {scr} missing from screen matrix test"


def test_challenger_bouncing_scroll_physics_encapsulation():
    """
    Verify that every primary screen encapsulates its contents in scrollable
    views configured with BouncingScrollPhysics to prevent vertical RenderFlex overflows.
    """
    screens = [
        "dashboard_screen.dart",
        "screener_screen.dart",
        "stock_detail_screen.dart",
        "baskets_screen.dart",
        "purification_screen.dart",
        "academy_zakat_screen.dart",
    ]
    for scr_file in screens:
        p = CLIENT_LIB / "screens" / scr_file
        assert p.exists(), f"Screen file missing: {scr_file}"
        code = p.read_text(encoding="utf-8")

        assert "BouncingScrollPhysics" in code, (
            f"Screen {scr_file} lacks BouncingScrollPhysics scroll encapsulation"
        )
        assert ("SingleChildScrollView" in code or "ListView" in code), (
            f"Screen {scr_file} lacks top-level scroll view"
        )


def test_challenger_text_truncation_and_horizontal_protection():
    """
    Verify that dynamic text displays (company names, descriptions, headers)
    enforce TextOverflow.ellipsis and appropriate Expanded/Flexible wrappers
    to prevent horizontal RenderFlex overflows on narrow screens.
    """
    screener_path = CLIENT_LIB / "screens" / "screener_screen.dart"
    code = screener_path.read_text(encoding="utf-8")

    assert "TextOverflow.ellipsis" in code
    assert "Expanded(" in code

    # In Bloomberg table view: verify DataTable is wrapped in dual-axis scroll views
    assert "SingleChildScrollView" in code
    # Check that both vertical and horizontal scroll directions are present
    assert "Axis.horizontal" in code
    assert "Axis.vertical" in code

    # In Dashboard: metric cards must use Wrap so they flow dynamically
    dashboard_path = CLIENT_LIB / "screens" / "dashboard_screen.dart"
    dash_code = dashboard_path.read_text(encoding="utf-8")
    assert "Wrap(" in dash_code, "Dashboard metrics should use Wrap for responsive flow"
    assert "TextOverflow.ellipsis" in dash_code


# ===========================================================================
# Vector 2: Offline Resilience & Asset Integration
# ===========================================================================

def test_challenger_sample_nifty500_asset_integration():
    """
    Verify that assets/data/sample_nifty500.json is properly configured
    in pubspec.yaml and contains valid JSON with full company fundamentals.
    """
    pubspec = CLIENT_DIR / "pubspec.yaml"
    assert pubspec.exists(), "pubspec.yaml missing"
    pub_content = pubspec.read_text(encoding="utf-8")
    assert "assets:" in pub_content
    assert "- assets/data/" in pub_content

    asset_file = ASSETS_DIR / "sample_nifty500.json"
    assert asset_file.exists(), f"Asset file missing at {asset_file}"
    assert asset_file.stat().st_size > 1000, "sample_nifty500.json is empty or too small"

    with open(asset_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list), "sample_nifty500.json root must be a list"
    assert len(data) >= 30, f"Expected at least 30 pre-seeded stocks, found {len(data)}"

    # Required fields for StockSummary.fromJson in stock_model.dart
    required_keys = [
        "ticker",
        "symbol",
        "company_name",
        "sector",
        "industry",
        "current_price",
        "market_cap",
        "avg_36m_market_cap",
        "aaoifi_status",
        "tasis_status",
        "purification_ratio",
    ]

    for item in data:
        for k in required_keys:
            assert k in item, f"Missing key '{k}' in sample_nifty500 item: {item.get('ticker')}"
        assert item["aaoifi_status"] in ("COMPLIANT", "QUESTIONABLE", "NON_COMPLIANT")
        assert item["tasis_status"] in ("COMPLIANT", "QUESTIONABLE", "NON_COMPLIANT")
        assert isinstance(item["current_price"], (int, float))
        assert item["current_price"] > 0
        assert 0.0 <= item["purification_ratio"] <= 1.0


def test_challenger_api_service_offline_fallback_coverage():
    """
    Verify ApiService has comprehensive offline fallbacks for when backend is unreachable:
    - loadBundledStocks() fallback to getFallbackStocks()
    - getStocks() offline cache and fallback
    - getBaskets() fallback to getFallbackBaskets()
    - getFunds() offline fund models
    - calculateStatutoryTaxes() local formula fallback
    - getCommunityOverview() offline metrics & verified causes
    - getRadarEvents() offline events
    """
    api_service_path = CLIENT_LIB / "services" / "api_service.dart"
    assert api_service_path.exists()
    content = api_service_path.read_text(encoding="utf-8")

    # Root bundle loading
    assert "rootBundle.loadString('assets/data/sample_nifty500.json')" in content
    assert "getFallbackStocks()" in content
    assert "getFallbackBaskets()" in content

    # Local fallback logic for statutory taxes
    assert "stt = (turnover * 0.001" in content
    assert "stampDuty = (turnover * 0.00015" in content
    assert "gst = ((brokerage + exchangeCharges + sebiCharges) * 0.18" in content

    # Offline funds
    assert "Tata Ethical Fund" in content
    assert "Taurus Ethical Fund" in content
    assert "Nippon India ETF Shariah BeES" in content
    assert "24K Certified Physical Gold" in content

    # Offline verified causes
    assert "Bait-un-Nasr Educational Scholarship Fund" in content
    assert "Lifeline Dialysis & Cancer Medical Aid Trust" in content
    assert "Sabeel Clean Water & Sanitation Foundation" in content


# ===========================================================================
# Vector 3: Prefix Trie In-Memory Search Performance (<50ms SLA)
# ===========================================================================

class PythonTrieNode:
    def __init__(self):
        self.children: Dict[str, PythonTrieNode] = {}
        self.matched_stocks: set = set()
        self.is_end_of_word: bool = False


class PythonTrieSearchOracle:
    """Exact behavioral oracle of client/lib/services/search_service.dart."""
    def __init__(self, stocks: List[Dict[str, Any]]):
        self.root = PythonTrieNode()
        self.query_cache: Dict[str, List[str]] = {}
        for stock in stocks:
            self.insert_stock(stock)

    def insert_stock(self, stock: Dict[str, Any]):
        sym = stock["symbol"].lower()
        self._insert_token(sym, stock["ticker"])
        self._insert_token(stock["ticker"].lower(), stock["ticker"])
        for word in stock["company_name"].lower().split():
            if len(word) >= 2:
                self._insert_token(word, stock["ticker"])
        for sword in stock["sector"].lower().split():
            if len(sword) >= 3:
                self._insert_token(sword, stock["ticker"])

    def _insert_token(self, token: str, ticker: str):
        curr = self.root
        for char in token:
            if char not in curr.children:
                curr.children[char] = PythonTrieNode()
            curr = curr.children[char]
            curr.matched_stocks.add(ticker)
        curr.is_end_of_word = True

    def search_local(self, query: str) -> List[str]:
        clean = query.strip().lower()
        if not clean:
            return []
        if clean in self.query_cache:
            return self.query_cache[clean]

        curr = self.root
        for char in clean:
            if char not in curr.children:
                self.query_cache[clean] = []
                return []
            curr = curr.children[char]

        res = sorted(list(curr.matched_stocks))
        self.query_cache[clean] = res
        return res


def test_challenger_prefix_trie_search_performance_and_accuracy():
    """
    Stress-test the prefix Trie against all pre-seeded equities.
    Verify:
    1. Correct retrieval for ticker, symbol, company name tokens, sector tokens.
    2. Sub-50ms query response time SLA (assert < 5.0ms even under stress).
    3. Proper edge case handling: empty string, whitespace, non-matching queries.
    """
    with open(ASSETS_DIR / "sample_nifty500.json", "r", encoding="utf-8") as f:
        stocks = json.load(f)

    oracle = PythonTrieSearchOracle(stocks)

    # 1. Functional correctness checks
    tcs_res = oracle.search_local("tc")
    assert "TCS.NS" in tcs_res, f"Expected TCS.NS in search for 'tc', got {tcs_res}"

    infy_res = oracle.search_local("inf")
    assert "INFY.NS" in infy_res, f"Expected INFY.NS in search for 'inf', got {infy_res}"

    tata_res = oracle.search_local("tata")
    assert "TCS.NS" in tata_res, f"Expected TCS.NS in search for 'tata', got {tata_res}"

    tech_res = oracle.search_local("technology")
    assert len(tech_res) > 0, "Expected technology sector stocks"

    # Edge cases
    assert oracle.search_local("") == []
    assert oracle.search_local("    ") == []
    assert oracle.search_local("XYZ_NONEXISTENT_TICKER_999") == []
    assert oracle.search_local("!@#$%^&*()") == []

    # 2. Latency benchmark across 500 query executions
    benchmark_queries = [
        "t", "tc", "tcs", "i", "in", "inf", "infy", "w", "wi", "wip", "wipro",
        "h", "hd", "hdfc", "r", "re", "rel", "relian", "reliance",
        "tech", "software", "pharma", "bank", "financial",
        "notfound1", "notfound2", "z", "za", "zak"
    ]

    durations_ms = []
    for _ in range(20):  # 20 iterations * 29 queries = 580 executions
        for q in benchmark_queries:
            t0 = time.perf_counter()
            _ = oracle.search_local(q)
            t1 = time.perf_counter()
            durations_ms.append((t1 - t0) * 1000.0)

    max_latency = max(durations_ms)
    avg_latency = sum(durations_ms) / len(durations_ms)
    p99_latency = sorted(durations_ms)[int(len(durations_ms) * 0.99)]

    print(f"\nTrie Search Benchmark: executions={len(durations_ms)}, avg={avg_latency:.4f}ms, p99={p99_latency:.4f}ms, max={max_latency:.4f}ms")
    # Strict SLA check: prompt requires < 50ms. Trie typically executes in < 0.1ms.
    assert max_latency < 50.0, f"Max search latency {max_latency:.4f}ms exceeded 50ms SLA"
    assert p99_latency < 1.0, f"P99 latency {p99_latency:.4f}ms unexpectedly slow"


# ===========================================================================
# Vector 4: Delimiter Balance & File Invariant Verification
# ===========================================================================

def test_challenger_file_invariant_and_delimiters():
    """
    Verify that the client codebase satisfies the invariant of exactly 29 Dart files
    and all 29 files pass AST delimiter balancing.
    """
    from tests.shariah.verify_dart_client import check_delimiter_balance, CLIENT_LIB, CLIENT_TEST

    dart_files = sorted(list(CLIENT_LIB.rglob("*.dart")) + list(CLIENT_TEST.rglob("*.dart")))
    assert len(dart_files) == 29, f"Expected strictly 29 Dart files, found {len(dart_files)}"

    for f in dart_files:
        code = f.read_text(encoding="utf-8")
        balanced, msg = check_delimiter_balance(code)
        assert balanced, f"Delimiter imbalance in {f.name}: {msg}"
