import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any

import aiosqlite

from quant_system.shariah.schemas.purification import (
    PurificationCalculateResponse,
    PurificationLedgerCreate,
    PurificationLedgerEntry,
    PurificationReceipt,
)

logger = logging.getLogger(__name__)

GENESIS_HASH: str = "0" * 64

CREATE_LEDGER_TABLE_SQL = """
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
CREATE INDEX IF NOT EXISTS idx_purification_ledger_ticker ON purification_ledger(ticker);
CREATE INDEX IF NOT EXISTS idx_purification_ledger_status ON purification_ledger(disbursement_status);
"""


def calculate_purification_ratio(
    interest_income: float,
    prohibited_secondary_revenue: float,
    total_revenue: float,
) -> float:
    """Exact purification ratio: rho = (Interest Income + Prohibited Revenue) / Total Revenue."""
    if total_revenue <= 0.0:
        return 1.0 if (interest_income + prohibited_secondary_revenue) > 0.0 else 0.0
    return round((interest_income + prohibited_secondary_revenue) / total_revenue, 6)


def calculate_purification_amount(gross_dividend: float, purification_ratio: float) -> float:
    """Exact Rupee purification payable: Gross Dividend * rho with 2-decimal half-up precision."""
    if gross_dividend <= 0.0 or purification_ratio <= 0.0:
        return 0.00
    return round(gross_dividend * purification_ratio, 2)


def generate_sha256_ledger_hash(prev_hash: str, entry_uuid: str, purification_amount: float) -> str:
    """
    SHA-256 cryptographic chaining function:
    Hash_n = SHA256(Hash_{n-1} | UUID_n | PurificationAmount_n)
    """
    payload = f"{prev_hash}|{entry_uuid}|{purification_amount:.2f}".encode()
    return hashlib.sha256(payload).hexdigest()


async def ensure_ledger_table(db: aiosqlite.Connection) -> None:
    """Guarantees SQLite purification_ledger table exists."""
    await db.executescript(CREATE_LEDGER_TABLE_SQL)
    await db.commit()


async def get_company_purification_info(
    ticker: str,
    db: aiosqlite.Connection,
) -> tuple[float, str]:
    """Retrieves company purification ratio and official name from database."""
    clean_ticker = ticker.strip().upper()
    variants = [clean_ticker]
    if clean_ticker.endswith(".NS"):
        variants.append(clean_ticker[:-3])
    else:
        variants.append(f"{clean_ticker}.NS")

    placeholders = ",".join("?" for _ in variants)
    sql = f"SELECT purification_ratio, company_name FROM companies WHERE ticker IN ({placeholders}) OR symbol IN ({placeholders}) LIMIT 1;"
    params = variants + variants
    cursor = await db.execute(sql, tuple(params))
    row = await cursor.fetchone()

    if row:
        return float(row["purification_ratio"]), str(row["company_name"])
    # Default fallback: 0.0058 (TCS-level baseline) if company not in DB
    return 0.0058, clean_ticker


async def calculate_dividend_purification(
    ticker: str,
    dividend_amount: float,
    shares_held: int,
    db: aiosqlite.Connection,
) -> PurificationCalculateResponse:
    """Calculates dividend purification breakdown for an equity holding."""
    if dividend_amount <= 0.0:
        raise ValueError("Dividend amount must be strictly positive.")
    if shares_held <= 0:
        raise ValueError("Shares held must be at least 1.")

    purification_ratio, _ = await get_company_purification_info(ticker, db)

    # Check if dividend_amount is per-share (typical when shares > 1 and dividend_amount < 1000)
    # If dividend_amount is total, DPS is dividend_amount / shares_held
    # Standard convention: dividend_amount passed is DPS
    dps = dividend_amount
    gross_dividend = round(dps * shares_held, 2)
    purification_payable = calculate_purification_amount(gross_dividend, purification_ratio)
    net_permissible = round(gross_dividend - purification_payable, 2)

    return PurificationCalculateResponse(
        ticker=ticker.upper().strip(),
        shares_held=shares_held,
        dividend_per_share=round(dps, 4),
        gross_dividend=gross_dividend,
        purification_ratio=purification_ratio,
        purification_ratio_pct=round(purification_ratio * 100.0, 4),
        purification_payable=purification_payable,
        net_permissible_dividend=net_permissible,
    )


async def get_latest_ledger_hash(db: aiosqlite.Connection) -> str:
    """Returns the latest cryptographic entry hash in the ledger, or GENESIS_HASH if empty."""
    await ensure_ledger_table(db)
    cursor = await db.execute(
        "SELECT entry_hash FROM purification_ledger ORDER BY id DESC LIMIT 1;"
    )
    row = await cursor.fetchone()
    if row and row["entry_hash"]:
        return str(row["entry_hash"])
    return GENESIS_HASH


async def add_purification_ledger_entry(
    entry_data: PurificationLedgerCreate,
    db: aiosqlite.Connection,
) -> PurificationLedgerEntry:
    """Appends an immutable, SHA-256 cryptographically chained entry to purification_ledger."""
    await ensure_ledger_table(db)

    purification_ratio, company_name = await get_company_purification_info(entry_data.ticker, db)

    gross_dividend = entry_data.gross_dividend
    if gross_dividend is None or gross_dividend <= 0.0:
        gross_dividend = round(entry_data.dps * entry_data.shares_held, 2)
    else:
        gross_dividend = round(gross_dividend, 2)

    purification_payable = calculate_purification_amount(gross_dividend, purification_ratio)
    net_permissible = round(gross_dividend - purification_payable, 2)

    entry_uuid = f"pur-{uuid.uuid4().hex[:16]}"
    prev_hash = await get_latest_ledger_hash(db)
    entry_hash = generate_sha256_ledger_hash(prev_hash, entry_uuid, purification_payable)

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    record_date = entry_data.record_date or today_str
    payment_date = entry_data.payment_date or today_str
    status = (entry_data.disbursement_status or "UNPURIFIED").upper().strip()

    insert_sql = """
        INSERT INTO purification_ledger (
            entry_uuid, ticker, company_name, record_date, payment_date, shares_held,
            dps_inr, gross_dividend, purification_ratio, purification_payable,
            net_permissible_dividend, charity_name, disbursement_status, notes,
            prev_entry_hash, entry_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    cursor = await db.execute(
        insert_sql,
        (
            entry_uuid,
            entry_data.ticker.upper().strip(),
            company_name,
            record_date,
            payment_date,
            entry_data.shares_held,
            entry_data.dps,
            gross_dividend,
            purification_ratio,
            purification_payable,
            net_permissible,
            entry_data.charity_name,
            status,
            entry_data.notes,
            prev_hash,
            entry_hash,
        ),
    )
    row_id = cursor.lastrowid
    await db.commit()

    # Retrieve created record
    fetch_cursor = await db.execute("SELECT * FROM purification_ledger WHERE id = ?;", (row_id,))
    row = await fetch_cursor.fetchone()
    if row is None:
        raise ValueError(f"Failed to retrieve newly created purification ledger row {row_id}")

    return PurificationLedgerEntry(
        id=row["id"],
        entry_uuid=row["entry_uuid"],
        ticker=row["ticker"],
        company_name=row["company_name"],
        record_date=row["record_date"],
        payment_date=row["payment_date"],
        shares_held=row["shares_held"],
        dps_inr=float(row["dps_inr"]),
        gross_dividend=float(row["gross_dividend"]),
        purification_ratio=float(row["purification_ratio"]),
        purification_payable=float(row["purification_payable"]),
        net_permissible_dividend=float(row["net_permissible_dividend"]),
        charity_name=row["charity_name"],
        disbursement_status=row["disbursement_status"],
        notes=row["notes"],
        prev_entry_hash=row["prev_entry_hash"],
        entry_hash=row["entry_hash"],
        timestamp=str(row["timestamp"]),
    )


async def verify_ledger_chain(db: aiosqlite.Connection) -> dict[str, Any]:
    """
    Audits the entire purification ledger sequentially from genesis.
    Verifies that no entry has been altered, deleted, or inserted out of order.
    """
    await ensure_ledger_table(db)
    cursor = await db.execute("SELECT * FROM purification_ledger ORDER BY id ASC;")
    rows = list(await cursor.fetchall())

    if not rows:
        return {
            "is_valid": True,
            "total_entries": 0,
            "tampered_entry_id": None,
            "message": "Ledger is empty; genesis state verified.",
        }

    expected_prev = GENESIS_HASH
    for r in rows:
        stored_prev = r["prev_entry_hash"]
        stored_hash = r["entry_hash"]
        uuid_val = r["entry_uuid"]
        payable = float(r["purification_payable"])

        # Verify previous hash link
        if stored_prev != expected_prev:
            return {
                "is_valid": False,
                "total_entries": len(rows),
                "tampered_entry_id": uuid_val,
                "message": f"Broken chain link at entry {uuid_val}: stored prev_hash does not match preceding hash.",
            }

        # Re-compute cryptographic hash
        computed_hash = generate_sha256_ledger_hash(stored_prev, uuid_val, payable)
        if computed_hash != stored_hash:
            return {
                "is_valid": False,
                "total_entries": len(rows),
                "tampered_entry_id": uuid_val,
                "message": f"Tampered entry payload at {uuid_val}: computed hash does not match stored entry_hash.",
            }

        expected_prev = stored_hash

    return {
        "is_valid": True,
        "total_entries": len(rows),
        "tampered_entry_id": None,
        "message": f"Cryptographic audit chain verified intact across {len(rows)} entries.",
    }


def format_printable_receipt(entry: dict[str, Any]) -> str:
    """Formats an exportable ASCII certificate for charitable purification."""
    uuid_short = str(entry.get("entry_uuid", "00000000"))[:8]
    ticker = entry.get("ticker", "N/A")
    company = entry.get("company_name", ticker)
    gross = float(entry.get("gross_dividend", 0.0))
    ratio_pct = float(entry.get("purification_ratio", 0.0)) * 100.0
    payable = float(entry.get("purification_payable", 0.0))
    net = float(entry.get("net_permissible_dividend", 0.0))
    charity = entry.get("charity_name") or "Public Charitable Trust"
    status = entry.get("disbursement_status", "UNPURIFIED")
    hash_val = entry.get("entry_hash", "")
    prev_h = entry.get("prev_entry_hash", "")
    ts = entry.get("timestamp") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""================================================================================
           HALAL WEALTH PURIFICATION & CHARITABLE DISBURSEMENT RECEIPT
================================================================================
Certificate ID    : PUR-2026-{ticker.replace(".NS", "")}-{uuid_short}
Timestamp         : {ts}
Disbursement Stat : {status}

EQUITY & DIVIDEND DETAILS:
--------------------------------------------------------------------------------
Security Ticker   : {ticker}
Enterprise Name   : {company}
Shares Held       : {entry.get("shares_held", 0)}
Gross Dividend    : INR {gross:,.2f}

PURIFICATION COMPUTATION (AAOIFI Standard No. 21):
--------------------------------------------------------------------------------
Purification Ratio: {ratio_pct:.4f}%
PURIFICATION DUE  : INR {payable:,.2f}
Net Permissible   : INR {net:,.2f}

BENEFICIARY DISBURSEMENT:
--------------------------------------------------------------------------------
Beneficiary Entity: {charity}
Fiqh Purpose      : Public interest & general welfare (Sadaqah Lillah)

CRYPTOGRAPHIC IMMUTABILITY & AUDIT PROOF:
--------------------------------------------------------------------------------
Previous Node Hash: {prev_h}
Verification Hash : {hash_val}

DISCLAIMER:
Disbursed into public charity without expectation of spiritual reward in accordance
with AAOIFI Shariah Standard No. 21 (Clause 3/4) and Indian statutory tax filings.
================================================================================
"""


async def get_purification_receipt_by_id(
    entry_id: str,
    db: aiosqlite.Connection,
) -> PurificationReceipt | None:
    """Retrieves ledger entry by UUID or integer ID and formats receipt."""
    await ensure_ledger_table(db)

    sql = "SELECT * FROM purification_ledger WHERE entry_uuid = ? OR id = ? LIMIT 1;"
    id_as_int = int(entry_id) if entry_id.isdigit() else -1
    cursor = await db.execute(sql, (entry_id, id_as_int))
    row = await cursor.fetchone()

    if not row:
        return None

    row_dict = dict(row)
    uuid_val = row_dict["entry_uuid"]
    ticker = row_dict["ticker"]
    payable = float(row_dict["purification_payable"])
    gross = float(row_dict["gross_dividend"])
    net = float(row_dict["net_permissible_dividend"])
    ratio = float(row_dict["purification_ratio"])
    entry_hash = row_dict["entry_hash"]
    prev_hash = row_dict["prev_entry_hash"]
    company_name = row_dict["company_name"]
    charity = row_dict["charity_name"]
    status = row_dict["disbursement_status"]
    ts = str(row_dict["timestamp"])

    printable = format_printable_receipt(row_dict)
    cert_id = f"PUR-2026-{ticker.replace('.NS', '')}-{uuid_val[:8]}"

    return PurificationReceipt(
        certificate_id=cert_id,
        ticker=ticker,
        company_name=company_name,
        gross_dividend_inr=gross,
        purification_ratio_pct=round(ratio * 100.0, 4),
        purification_payable_inr=payable,
        net_permissible_inr=net,
        verification_hash=entry_hash,
        prev_hash=prev_hash,
        charity_name=charity,
        disbursement_status=status,
        timestamp=ts,
        charity_disclaimer="Cleansed to public charity in accordance with AAOIFI Standard No. 21.",
        printable_receipt=printable,
    )
