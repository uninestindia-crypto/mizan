import logging

from quant_system.shariah.db.session import get_db_connection

logger = logging.getLogger(__name__)

CREATE_COMPANIES_TABLE = """
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    isin TEXT UNIQUE NOT NULL,
    bse_code TEXT,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    business_summary TEXT,

    current_price REAL NOT NULL,
    market_cap REAL NOT NULL,
    avg_36m_market_cap REAL NOT NULL,
    shares_outstanding INTEGER NOT NULL,
    pe_ratio REAL,
    pb_ratio REAL,
    dividend_yield REAL,
    last_dividend_per_share REAL DEFAULT 0.0,

    total_assets REAL NOT NULL,
    long_term_debt REAL NOT NULL DEFAULT 0.0,
    short_term_debt REAL NOT NULL DEFAULT 0.0,
    lease_liabilities REAL NOT NULL DEFAULT 0.0,
    total_debt REAL NOT NULL,
    cash_and_bank REAL NOT NULL,
    current_investments REAL NOT NULL DEFAULT 0.0,
    total_cash_and_investments REAL NOT NULL,
    total_receivables REAL NOT NULL,
    total_inventories REAL NOT NULL DEFAULT 0.0,
    current_liabilities REAL NOT NULL,

    operating_revenue REAL NOT NULL,
    other_income REAL NOT NULL DEFAULT 0.0,
    total_revenue REAL NOT NULL,
    interest_income REAL NOT NULL DEFAULT 0.0,
    prohibited_secondary_revenue REAL NOT NULL DEFAULT 0.0,
    total_impermissible_income REAL NOT NULL,

    sector_compliant INTEGER NOT NULL,
    sector_failure_reason TEXT,

    aaoifi_debt_ratio REAL NOT NULL,
    aaoifi_cash_ratio REAL NOT NULL,
    aaoifi_rec_ratio REAL NOT NULL,
    aaoifi_imp_ratio REAL NOT NULL,
    aaoifi_status TEXT NOT NULL,

    tasis_debt_ratio REAL NOT NULL,
    tasis_cash_ratio REAL NOT NULL,
    tasis_rec_ratio REAL NOT NULL,
    tasis_imp_ratio REAL NOT NULL,
    tasis_status TEXT NOT NULL,

    purification_ratio REAL NOT NULL,
    zakatable_assets_per_share REAL NOT NULL,

    filing_date TEXT NOT NULL,
    reporting_period TEXT NOT NULL,
    source_document TEXT,
    audit_notes TEXT,
    debt_note_ref TEXT,
    cash_note_ref TEXT,
    rec_note_ref TEXT,
    income_note_ref TEXT,
    is_nifty_50 INTEGER NOT NULL DEFAULT 0,
    is_nifty_500 INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_companies_symbol ON companies(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);",
    "CREATE INDEX IF NOT EXISTS idx_companies_aaoifi ON companies(aaoifi_status);",
    "CREATE INDEX IF NOT EXISTS idx_companies_tasis ON companies(tasis_status);",
    "CREATE INDEX IF NOT EXISTS idx_companies_mcap ON companies(market_cap DESC);",
]

CREATE_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS companies_fts USING fts5(
    ticker,
    symbol,
    company_name,
    isin,
    sector,
    industry,
    content='companies',
    content_rowid='rowid',
    tokenize='unicode61'
);
"""

CREATE_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS companies_ai AFTER INSERT ON companies BEGIN
    INSERT INTO companies_fts(rowid, ticker, symbol, company_name, isin, sector, industry)
    VALUES (new.rowid, new.ticker, new.symbol, new.company_name, new.isin, new.sector, new.industry);
END;

CREATE TRIGGER IF NOT EXISTS companies_ad AFTER DELETE ON companies BEGIN
    INSERT INTO companies_fts(companies_fts, rowid, ticker, symbol, company_name, isin, sector, industry)
    VALUES ('delete', old.rowid, old.ticker, old.symbol, old.company_name, old.isin, old.sector, old.industry);
END;

CREATE TRIGGER IF NOT EXISTS companies_au AFTER UPDATE ON companies BEGIN
    INSERT INTO companies_fts(companies_fts, rowid, ticker, symbol, company_name, isin, sector, industry)
    VALUES ('delete', old.rowid, old.ticker, old.symbol, old.company_name, old.isin, old.sector, old.industry);
    INSERT INTO companies_fts(rowid, ticker, symbol, company_name, isin, sector, industry)
    VALUES (new.rowid, new.ticker, new.symbol, new.company_name, new.isin, new.sector, new.industry);
END;
"""


CREATE_PURIFICATION_LEDGER_TABLE = """
CREATE TABLE IF NOT EXISTS purification_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_uuid TEXT NOT NULL UNIQUE,
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    record_date TEXT,
    payment_date TEXT,
    shares_held INTEGER NOT NULL,
    dps_inr REAL NOT NULL,
    gross_dividend REAL NOT NULL,
    purification_ratio REAL NOT NULL,
    purification_payable REAL NOT NULL,
    net_permissible_dividend REAL NOT NULL,
    charity_name TEXT,
    disbursement_status TEXT NOT NULL DEFAULT 'UNPURIFIED',
    notes TEXT,
    prev_entry_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_PURIFICATION_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_purification_ledger_ticker ON purification_ledger(ticker);",
    "CREATE INDEX IF NOT EXISTS idx_purification_ledger_status ON purification_ledger(disbursement_status);",
]


def init_db(db_path: str | None = None) -> None:
    """Initialize SQLite database tables, indexes, and FTS5 search structures."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(CREATE_COMPANIES_TABLE)
        for idx in CREATE_INDEXES:
            cursor.execute(idx)
        cursor.execute(CREATE_FTS_TABLE)
        cursor.executescript(CREATE_FTS_TRIGGERS)
        cursor.execute(CREATE_PURIFICATION_LEDGER_TABLE)
        for idx in CREATE_PURIFICATION_INDEXES:
            cursor.execute(idx)
        # Rebuild FTS index to ensure consistency with existing records
        cursor.execute("INSERT INTO companies_fts(companies_fts) VALUES('rebuild');")
        conn.commit()
        logger.info(
            "Database initialized successfully with FTS5, indexes, and purification ledger."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
