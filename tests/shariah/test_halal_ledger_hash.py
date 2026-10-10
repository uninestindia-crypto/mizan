"""The purification ledger's chain: old rows still verify, new rows cover every listed figure."""

import hashlib
import shutil
import sqlite3
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from quant_system.shariah.db.session import get_async_db
from quant_system.shariah.main import app
from quant_system.shariah.schemas.purification import PurificationLedgerCreate
from quant_system.shariah.services.purification_service import (
    add_purification_ledger_entry,
    get_purification_receipt_by_id,
    verify_ledger_chain,
)

GENESIS = "0" * 64
SEED_DB = Path(__file__).resolve().parents[2] / "data" / "shariah" / "halal_stocks.db"

# The table as it was before hash versions existed.
OLD_LEDGER_TABLE = """
CREATE TABLE purification_ledger (
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
COMPANIES = """
CREATE TABLE companies (ticker TEXT, symbol TEXT, company_name TEXT, purification_ratio REAL);
INSERT INTO companies VALUES ('TCS.NS', 'TCS', 'Tata Consultancy Services', 0.0058);
INSERT INTO companies VALUES ('INFY.NS', 'INFY', 'Infosys', 0.007394);
"""


def old_hash(prev: str, entry_uuid: str, payable: float) -> str:
    """The version 1 rule, written out independently of the code under test."""
    return hashlib.sha256(f"{prev}|{entry_uuid}|{payable:.2f}".encode()).hexdigest()


def new_hash(prev: str, row: dict[str, Any]) -> str:
    """The version 2 rule, written out independently of the code under test."""
    parts = [
        prev,
        row["entry_uuid"],
        row["ticker"],
        repr(float(row["gross_dividend"])),
        repr(float(row["purification_ratio"])),
        repr(float(row["purification_payable"])),
        row["timestamp"],
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def open_database(path: Path) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    return conn


@pytest_asyncio.fixture
async def new_db(tmp_path: Path) -> AsyncGenerator[aiosqlite.Connection, None]:
    path = tmp_path / "fresh.db"
    raw = sqlite3.connect(path)
    raw.executescript(COMPANIES)
    raw.close()
    conn = await open_database(path)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def old_db(tmp_path: Path) -> AsyncGenerator[aiosqlite.Connection, None]:
    """A database whose ledger has three rows written by the old code, and no hash version column."""
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.executescript(COMPANIES + OLD_LEDGER_TABLE)
    prev = GENESIS
    for number in range(1, 4):
        entry_uuid = f"pur-old-{number}"
        payable = round(number * 1.37, 2)
        entry_hash = old_hash(prev, entry_uuid, payable)
        raw.execute(
            "INSERT INTO purification_ledger (entry_uuid, ticker, company_name, shares_held, dps_inr,"
            " gross_dividend, purification_ratio, purification_payable, net_permissible_dividend,"
            " prev_entry_hash, entry_hash) VALUES (?, 'TCS.NS', 'Tata', 10, 5.0, 50.0, 0.0058, ?, 49.0, ?, ?)",
            (entry_uuid, payable, prev, entry_hash),
        )
        prev = entry_hash
    raw.commit()
    raw.close()
    conn = await open_database(path)
    yield conn
    await conn.close()


async def record(conn: aiosqlite.Connection, ticker: str = "TCS.NS", shares: int = 100) -> Any:
    return await add_purification_ledger_entry(
        PurificationLedgerCreate(ticker=ticker, shares_held=shares, dps=12.5), conn
    )


async def rows(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    cursor = await conn.execute("SELECT * FROM purification_ledger ORDER BY id")
    return [dict(row) for row in await cursor.fetchall()]


@pytest.mark.asyncio
async def test_a_new_entry_is_written_as_hash_version_2(new_db: aiosqlite.Connection) -> None:
    entry = await record(new_db)

    assert entry.hash_version == 2
    assert (await rows(new_db))[0]["hash_version"] == 2


@pytest.mark.asyncio
async def test_a_new_entry_hash_covers_the_listed_figures(new_db: aiosqlite.Connection) -> None:
    await record(new_db)

    row = (await rows(new_db))[0]

    assert row["entry_hash"] == new_hash(GENESIS, row)


@pytest.mark.asyncio
async def test_a_chain_of_new_entries_verifies(new_db: aiosqlite.Connection) -> None:
    await record(new_db)
    await record(new_db, "INFY.NS", 40)
    await record(new_db)

    result = await verify_ledger_chain(new_db)

    assert (result["is_valid"], result["total_entries"], result["tampered_entry_id"]) == (
        True,
        3,
        None,
    )


@pytest.mark.asyncio
async def test_the_timestamp_is_kept_exactly_as_it_was_hashed(new_db: aiosqlite.Connection) -> None:
    entry = await record(new_db)

    row = (await rows(new_db))[0]

    assert entry.timestamp == row["timestamp"]
    assert len(row["timestamp"]) == len("2026-10-07 12:30:45")


@pytest.mark.asyncio
async def test_an_old_ledger_without_the_column_still_verifies(
    old_db: aiosqlite.Connection,
) -> None:
    result = await verify_ledger_chain(old_db)

    assert (result["is_valid"], result["total_entries"]) == (True, 3)


@pytest.mark.asyncio
async def test_opening_an_old_ledger_adds_the_column_and_rewrites_no_row(
    old_db: aiosqlite.Connection,
) -> None:
    before = await rows(old_db)

    await verify_ledger_chain(old_db)
    after = await rows(old_db)

    assert set(after[0]) - set(before[0]) == {"hash_version"}
    assert [{k: v for k, v in row.items() if k != "hash_version"} for row in after] == before
    assert [row["hash_version"] for row in after] == [1, 1, 1]


@pytest.mark.asyncio
async def test_opening_the_ledger_twice_does_not_fail(old_db: aiosqlite.Connection) -> None:
    await verify_ledger_chain(old_db)

    result = await verify_ledger_chain(old_db)

    assert result["is_valid"] is True


@pytest.mark.asyncio
async def test_a_mixed_chain_of_old_and_new_rows_verifies(old_db: aiosqlite.Connection) -> None:
    await record(old_db)
    await record(old_db, "INFY.NS", 7)

    result = await verify_ledger_chain(old_db)

    assert (result["is_valid"], result["total_entries"]) == (True, 5)
    assert [row["hash_version"] for row in await rows(old_db)] == [1, 1, 1, 2, 2]


@pytest.mark.asyncio
async def test_an_altered_old_row_is_still_caught(old_db: aiosqlite.Connection) -> None:
    await record(old_db)
    await old_db.execute("UPDATE purification_ledger SET purification_payable = 99.99 WHERE id = 2")
    await old_db.commit()

    result = await verify_ledger_chain(old_db)

    assert (result["is_valid"], result["tampered_entry_id"]) == (False, "pur-old-2")


@pytest.mark.parametrize(
    ("column", "altered"),
    [
        ("entry_uuid", "pur-forged-id"),
        ("ticker", "WIPRO.NS"),
        ("gross_dividend", 1250.01),
        ("purification_ratio", 0.0059),
        ("purification_payable", 7.0),
        ("timestamp", "2020-01-01 00:00:00"),
    ],
)
@pytest.mark.asyncio
async def test_altering_any_one_listed_field_of_a_new_row_breaks_the_chain(
    new_db: aiosqlite.Connection, column: str, altered: Any
) -> None:
    await record(new_db)
    middle = await record(new_db, "INFY.NS", 40)
    await record(new_db)
    await new_db.execute(
        f"UPDATE purification_ledger SET {column} = ? WHERE id = ?", (altered, middle.id)
    )
    await new_db.commit()

    result = await verify_ledger_chain(new_db)

    assert result["is_valid"] is False
    assert "Tampered entry payload" in result["message"]
    assert result["tampered_entry_id"] == (await rows(new_db))[1]["entry_uuid"]


@pytest.mark.asyncio
async def test_a_hash_version_nobody_wrote_fails_instead_of_passing(
    new_db: aiosqlite.Connection,
) -> None:
    entry = await record(new_db)
    await new_db.execute(
        "UPDATE purification_ledger SET hash_version = 3 WHERE id = ?", (entry.id,)
    )
    await new_db.commit()

    result = await verify_ledger_chain(new_db)

    assert (result["is_valid"], result["tampered_entry_id"]) == (False, entry.entry_uuid)
    assert "hash version" in result["message"]


@pytest.mark.asyncio
async def test_lowering_a_new_rows_version_to_dodge_the_wider_check_is_caught(
    new_db: aiosqlite.Connection,
) -> None:
    entry = await record(new_db)
    await new_db.execute(
        "UPDATE purification_ledger SET hash_version = 1 WHERE id = ?", (entry.id,)
    )
    await new_db.commit()

    result = await verify_ledger_chain(new_db)

    assert result["is_valid"] is False


@pytest.mark.asyncio
async def test_a_receipt_says_which_hash_version_protects_it(new_db: aiosqlite.Connection) -> None:
    entry = await record(new_db)

    receipt = await get_purification_receipt_by_id(entry.entry_uuid, new_db)

    assert receipt is not None
    assert receipt.hash_version == 2
    assert receipt.verification_hash == entry.entry_hash


@pytest.mark.asyncio
async def test_the_ledger_that_ships_in_the_sample_database_still_verifies(tmp_path: Path) -> None:
    copy = tmp_path / "seed_copy.db"
    shutil.copyfile(SEED_DB, copy)
    conn = await open_database(copy)

    result = await verify_ledger_chain(conn)
    await conn.close()

    assert result["is_valid"] is True
    assert result["total_entries"] > 0


@pytest_asyncio.fixture
async def ledger_client(new_db: aiosqlite.Connection) -> AsyncGenerator[AsyncClient, None]:
    async def override() -> AsyncGenerator[aiosqlite.Connection, None]:
        yield new_db

    app.dependency_overrides[get_async_db] = override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as http:
        yield http
    app.dependency_overrides.pop(get_async_db, None)


@pytest.mark.asyncio
async def test_the_ledger_pages_show_each_rows_hash_version_and_the_chain_verdict(
    ledger_client: AsyncClient,
) -> None:
    created = await ledger_client.post(
        "/api/v1/purification/ledger", json={"ticker": "TCS.NS", "shares_held": 10, "dps": 5.0}
    )
    listed = (await ledger_client.get("/api/v1/purification/ledger")).json()
    verified = (await ledger_client.get("/api/v1/purification/ledger/verify")).json()

    assert created.status_code == 201
    assert created.json()["hash_version"] == 2
    assert [item["hash_version"] for item in listed["items"]] == [2]
    assert listed["is_chain_valid"] is True
    assert verified["is_valid"] is True
