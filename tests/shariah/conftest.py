import asyncio
import json
import os
import tempfile
import sqlite3
import hashlib
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List

import pytest
import pytest_asyncio
import aiosqlite
from httpx import AsyncClient, ASGITransport

from quant_system.shariah.main import app
from quant_system.shariah.core.config import settings
from quant_system.shariah.db.session import get_async_db, SQLITE_PRAGMAS
from quant_system.shariah.db.init_db import (
    CREATE_COMPANIES_TABLE,
    CREATE_INDEXES,
    CREATE_FTS_TABLE,
    CREATE_FTS_TRIGGERS,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_NIFTY500_PATH = FIXTURES_DIR / "sample_nifty500.json"


@pytest.fixture(scope="session")
def sample_companies() -> List[Dict[str, Any]]:
    """Load the authoritative 40-company deterministic fixture."""
    with open(SAMPLE_NIFTY500_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def test_db_path(sample_companies) -> str:
    """
    Session-scoped isolated SQLite database seeded with sample_nifty500.json fixture.
    Configured with WAL mode and memory pragmas for <5ms query execution.
    """
    temp_dir = tempfile.mkdtemp(prefix="halal_test_")
    db_file = os.path.join(temp_dir, "test_halal_stocks.db")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    for pragma in SQLITE_PRAGMAS:
        try:
            cursor.execute(pragma)
        except Exception:
            pass

    cursor.execute(CREATE_COMPANIES_TABLE)
    for idx in CREATE_INDEXES:
        cursor.execute(idx)
    cursor.execute(CREATE_FTS_TABLE)
    cursor.executescript(CREATE_FTS_TRIGGERS)

    insert_sql = """
        INSERT OR REPLACE INTO companies (
            ticker, symbol, isin, bse_code, company_name, sector, industry, business_summary,
            current_price, market_cap, avg_36m_market_cap, shares_outstanding, pe_ratio, pb_ratio,
            dividend_yield, last_dividend_per_share, total_assets, long_term_debt, short_term_debt,
            lease_liabilities, total_debt, cash_and_bank, current_investments, total_cash_and_investments,
            total_receivables, total_inventories, current_liabilities, operating_revenue, other_income,
            total_revenue, interest_income, prohibited_secondary_revenue, total_impermissible_income,
            sector_compliant, sector_failure_reason, aaoifi_debt_ratio, aaoifi_cash_ratio, aaoifi_rec_ratio,
            aaoifi_imp_ratio, aaoifi_status, tasis_debt_ratio, tasis_cash_ratio, tasis_rec_ratio,
            tasis_imp_ratio, tasis_status, purification_ratio, zakatable_assets_per_share, filing_date,
            reporting_period, source_document, audit_notes, debt_note_ref, cash_note_ref, rec_note_ref,
            income_note_ref, is_nifty_50, is_nifty_500
        ) VALUES (
            :ticker, :symbol, :isin, :bse_code, :company_name, :sector, :industry, :business_summary,
            :current_price, :market_cap, :avg_36m_market_cap, :shares_outstanding, :pe_ratio, :pb_ratio,
            :dividend_yield, :last_dividend_per_share, :total_assets, :long_term_debt, :short_term_debt,
            :lease_liabilities, :total_debt, :cash_and_bank, :current_investments, :total_cash_and_investments,
            :total_receivables, :total_inventories, :current_liabilities, :operating_revenue, :other_income,
            :total_revenue, :interest_income, :prohibited_secondary_revenue, :total_impermissible_income,
            :sector_compliant, :sector_failure_reason, :aaoifi_debt_ratio, :aaoifi_cash_ratio, :aaoifi_rec_ratio,
            :aaoifi_imp_ratio, :aaoifi_status, :tasis_debt_ratio, :tasis_cash_ratio, :tasis_rec_ratio,
            :tasis_imp_ratio, :tasis_status, :purification_ratio, :zakatable_assets_per_share, :filing_date,
            :reporting_period, :source_document, :audit_notes, :debt_note_ref, :cash_note_ref, :rec_note_ref,
            :income_note_ref, :is_nifty_50, :is_nifty_500
        );
    """

    cursor.executemany(insert_sql, sample_companies)
    cursor.execute("INSERT INTO companies_fts(companies_fts) VALUES('rebuild');")
    conn.commit()
    conn.close()

    yield db_file

    # Cleanup temp directory on session exit
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
    except Exception:
        pass


@pytest_asyncio.fixture
async def async_db(test_db_path: str) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yields an aiosqlite connection pointing directly to the test database."""
    async with aiosqlite.connect(test_db_path, timeout=30.0) as conn:
        conn.row_factory = aiosqlite.Row
        for pragma in SQLITE_PRAGMAS:
            try:
                await conn.execute(pragma)
            except Exception:
                pass
        yield conn


@pytest_asyncio.fixture
async def client(test_db_path: str) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP client wrapping the FastAPI application with test database dependency override.
    """
    async def override_get_async_db():
        async with aiosqlite.connect(test_db_path, timeout=30.0) as conn:
            conn.row_factory = aiosqlite.Row
            for pragma in SQLITE_PRAGMAS:
                try:
                    await conn.execute(pragma)
                except Exception:
                    pass
            yield conn

    app.dependency_overrides[get_async_db] = override_get_async_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.pop(get_async_db, None)


# ---------------------------------------------------------------------------
# Authoritative Domain Mathematical Reference Oracles (R1 - R6 Specifications)
# Derived from ORIGINAL_REQUEST.md & survey_explorer_2/report.md
# ---------------------------------------------------------------------------

class DomainOracle:
    """Deterministic mathematical reference oracle for Shariah rules and wealth formulas."""

    SILVER_NISAB_INR = 53550.0  # 595 grams * 90 INR/g
    LUNAR_ZAKAT_RATE = 0.025000  # 2.500%
    SOLAR_ZAKAT_RATE = 0.025770  # 2.577% (2.5% * 365.25 / 354)

    @staticmethod
    def calculate_purification_ratio(interest_income: float, prohibited_secondary_revenue: float, total_revenue: float) -> float:
        """rho = (Interest Income + Prohibited Secondary Revenue) / Total Revenue"""
        if total_revenue <= 0.0:
            return 1.0 if (interest_income + prohibited_secondary_revenue) > 0.0 else 0.0
        return round((interest_income + prohibited_secondary_revenue) / total_revenue, 6)

    @staticmethod
    def calculate_purification_amount(gross_dividend: float, purification_ratio: float) -> float:
        """Purification Payable = Gross Dividend * rho, rounded to 2 decimal places"""
        return round(gross_dividend * purification_ratio, 2)

    @staticmethod
    def calculate_znwa_per_share(cash: float, investments: float, receivables: float, inventories: float, current_liabilities: float, shares_outstanding: int) -> float:
        """
        Zakatable Net Working Assets per share:
        ZNWA = Cash + Investments + Receivables + Inventories - Current Liabilities
        Per share = max(0, ZNWA / shares_outstanding)
        """
        if shares_outstanding <= 0:
            return 0.0
        znwa_total_cr = (cash + investments + receivables + inventories) - current_liabilities
        if znwa_total_cr <= 0.0:
            return 0.0
        # Convert Crores to INR (1 Cr = 10,000,000 INR)
        znwa_inr = znwa_total_cr * 10_000_000.0
        return round(znwa_inr / shares_outstanding, 2)

    @staticmethod
    def calculate_active_trader_zakat(portfolio_value: float, cash_balance: float, calendar: str = "lunar") -> Dict[str, Any]:
        """Method 1: Active Trader (100% Net Liquidation Value)."""
        rate = DomainOracle.SOLAR_ZAKAT_RATE if calendar.lower() == "solar" else DomainOracle.LUNAR_ZAKAT_RATE
        zakatable_base = round(portfolio_value + cash_balance, 2)
        is_obligatory = zakatable_base >= DomainOracle.SILVER_NISAB_INR
        zakat_due = round(zakatable_base * rate, 2) if is_obligatory else 0.0
        return {
            "method": "active",
            "calendar": calendar,
            "zakatable_base": zakatable_base,
            "nisab_threshold": DomainOracle.SILVER_NISAB_INR,
            "is_obligatory": is_obligatory,
            "rate": rate,
            "zakat_due": zakat_due,
        }

    @staticmethod
    def calculate_long_term_zakat(holdings_with_znwa: List[Dict[str, Any]], cash_balance: float, calendar: str = "lunar") -> Dict[str, Any]:
        """Method 2: Long-Term Investor (Zakatable Net Working Assets per share)."""
        rate = DomainOracle.SOLAR_ZAKAT_RATE if calendar.lower() == "solar" else DomainOracle.LUNAR_ZAKAT_RATE
        holdings_base = 0.0
        breakdown = []
        for h in holdings_with_znwa:
            znwa_ps = max(0.0, float(h.get("znwa_per_share", 0.0)))
            shares = int(h.get("shares", 0))
            holding_val = round(znwa_ps * shares, 2)
            holdings_base += holding_val
            breakdown.append({
                "ticker": h.get("ticker"),
                "shares": shares,
                "znwa_per_share": znwa_ps,
                "zakatable_amount": holding_val,
            })
        zakatable_base = round(holdings_base + cash_balance, 2)
        is_obligatory = zakatable_base >= DomainOracle.SILVER_NISAB_INR
        zakat_due = round(zakatable_base * rate, 2) if is_obligatory else 0.0
        return {
            "method": "long_term",
            "calendar": calendar,
            "zakatable_base": zakatable_base,
            "nisab_threshold": DomainOracle.SILVER_NISAB_INR,
            "is_obligatory": is_obligatory,
            "rate": rate,
            "zakat_due": zakat_due,
            "breakdown": breakdown,
        }

    @staticmethod
    def generate_sha256_ledger_hash(prev_hash: str, entry_uuid: str, purification_amount: float) -> str:
        """SHA-256 cryptographic chain link for immutable purification ledger."""
        payload = f"{prev_hash}|{entry_uuid}|{purification_amount:.2f}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def get_thematic_baskets() -> List[Dict[str, Any]]:
        """The 4 Curated Baskets specification from PROJECT.md."""
        return [
            {
                "id": "halal-tech-giants",
                "name": "Halal Tech Giants",
                "thesis": "World-leading Indian IT enterprises with zero net debt, export earnings, and superior ROE.",
                "constituents": [
                    {"ticker": "TCS.NS", "symbol": "TCS", "weight": 0.25},
                    {"ticker": "INFY.NS", "symbol": "INFY", "weight": 0.25},
                    {"ticker": "HCLTECH.NS", "symbol": "HCLTECH", "weight": 0.20},
                    {"ticker": "TECHM.NS", "symbol": "TECHM", "weight": 0.15},
                    {"ticker": "LTIM.NS", "symbol": "LTIM", "weight": 0.15},
                ],
                "expected_cagr": 0.148,
                "expected_sharpe": 1.12,
            },
            {
                "id": "shariah-high-growth-champions",
                "name": "Shariah High-Growth Champions",
                "thesis": "High-growth Indian mid-cap leaders in specialty chemicals, engineering design, and automotive tech.",
                "constituents": [
                    {"ticker": "PERSISTENT.NS", "symbol": "PERSISTENT", "weight": 0.20},
                    {"ticker": "TATAELXSI.NS", "symbol": "TATAELXSI", "weight": 0.20},
                    {"ticker": "DEEPAKNTR.NS", "symbol": "DEEPAKNTR", "weight": 0.20},
                    {"ticker": "PIDILITIND.NS", "symbol": "PIDILITIND", "weight": 0.20},
                    {"ticker": "MARICO.NS", "symbol": "MARICO", "weight": 0.20},
                ],
                "expected_cagr": 0.264,
                "expected_sharpe": 1.45,
            },
            {
                "id": "green-ethical-infrastructure",
                "name": "Green & Ethical Infrastructure",
                "thesis": "Enterprises accelerating India's clean energy, electric transmission, and environmental sustainability.",
                "constituents": [
                    {"ticker": "TATAPOWER.NS", "symbol": "TATAPOWER", "weight": 0.25},
                    {"ticker": "THERMAX.NS", "symbol": "THERMAX", "weight": 0.20},
                    {"ticker": "SIEMENS.NS", "symbol": "SIEMENS", "weight": 0.20},
                    {"ticker": "ABB.NS", "symbol": "ABB", "weight": 0.20},
                    {"ticker": "KEC.NS", "symbol": "KEC", "weight": 0.15},
                ],
                "expected_cagr": 0.312,
                "expected_sharpe": 1.60,
            },
            {
                "id": "nifty-shariah-25",
                "name": "NIFTY Shariah 25 Index Basket",
                "thesis": "Core wealth compounding mirroring the top 25 Shariah-compliant large-cap leaders in NIFTY 100.",
                "constituents": [
                    {"ticker": "TCS.NS", "symbol": "TCS", "weight": 0.08},
                    {"ticker": "INFY.NS", "symbol": "INFY", "weight": 0.08},
                    {"ticker": "HINDUNILVR.NS", "symbol": "HINDUNILVR", "weight": 0.07},
                    {"ticker": "SUNPHARMA.NS", "symbol": "SUNPHARMA", "weight": 0.06},
                    {"ticker": "CIPLA.NS", "symbol": "CIPLA", "weight": 0.05},
                    {"ticker": "DRREDDY.NS", "symbol": "DRREDDY", "weight": 0.04},
                ],
                "expected_cagr": 0.165,
                "expected_sharpe": 1.05,
            },
        ]


@pytest.fixture(scope="session")
def oracle() -> DomainOracle:
    """Fixture providing the authoritative domain calculation reference oracle."""
    return DomainOracle()
