"""The purification ledger's hash chain, in two versions.

Version 1 (every row written before versions existed) hashes the previous hash, the entry id and the payable
amount only. Version 2 (every new row) also hashes the ticker, the gross dividend, the purification ratio and
the time, so none of those can change without breaking the chain.

Each row says which version wrote it, and verification uses that row's own version, so an old ledger still
verifies and no old row is ever rewritten.

What the chain does and does not prove: it shows that a row was not edited after it was written. It is not a
signature, so someone who can rewrite every later row could recompute the whole chain.
"""

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

GENESIS_HASH = "0" * 64
HASH_VERSION_1 = 1
HASH_VERSION_2 = 2
CURRENT_HASH_VERSION = HASH_VERSION_2


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def _number(value: Any) -> str:
    """A number as text that changes whenever the stored number does."""
    return repr(float(value))


def _hash_version_1(prev_hash: str, row: Mapping[str, Any]) -> str:
    return _sha256(f"{prev_hash}|{row['entry_uuid']}|{float(row['purification_payable']):.2f}")


def _hash_version_2(prev_hash: str, row: Mapping[str, Any]) -> str:
    fields = [
        str(row["entry_uuid"]),
        str(row["ticker"]),
        _number(row["gross_dividend"]),
        _number(row["purification_ratio"]),
        _number(row["purification_payable"]),
        str(row["timestamp"]),
    ]
    if any("|" in field for field in fields):
        raise ValueError('A ledger entry cannot contain the "|" sign.')
    return _sha256("|".join([prev_hash, *fields]))


_HASHERS = {HASH_VERSION_1: _hash_version_1, HASH_VERSION_2: _hash_version_2}


def compute_entry_hash(version: int, prev_hash: str, row: Mapping[str, Any]) -> str:
    """The hash a row must carry under the given version. An unknown version is an error, never a pass."""
    hasher = _HASHERS.get(version)
    if hasher is None:
        raise ValueError(f"Unrecognised hash version {version}.")
    return hasher(prev_hash, row)


def hash_version_of(row: Mapping[str, Any]) -> int:
    """The row's own version. A row from before versions existed has none, which means version 1."""
    stored = row.get("hash_version")
    return HASH_VERSION_1 if stored is None else int(stored)


def _problem_with(row: Mapping[str, Any], expected_prev: str) -> str | None:
    """Why this row breaks the chain, or None if it holds."""
    entry_uuid = row["entry_uuid"]
    if row["prev_entry_hash"] != expected_prev:
        return f"Broken chain link at entry {entry_uuid}: stored prev_hash does not match preceding hash."
    try:
        computed = compute_entry_hash(hash_version_of(row), row["prev_entry_hash"], row)
    except (ValueError, TypeError) as error:
        return f"Entry {entry_uuid} cannot be checked: {error}"
    if computed != row["entry_hash"]:
        return f"Tampered entry payload at {entry_uuid}: computed hash does not match stored entry_hash."
    return None


def _report(
    rows: Sequence[Mapping[str, Any]], bad_row: Mapping[str, Any] | None, message: str
) -> dict[str, Any]:
    return {
        "is_valid": bad_row is None,
        "total_entries": len(rows),
        "tampered_entry_id": None if bad_row is None else bad_row["entry_uuid"],
        "message": message,
    }


def _first_problem(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], str] | None:
    """The first row that breaks the chain, with the reason."""
    expected_prev = GENESIS_HASH
    for row in rows:
        problem = _problem_with(row, expected_prev)
        if problem is not None:
            return row, problem
        expected_prev = row["entry_hash"]
    return None


def verify_ledger_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Walk the rows from the first one and report the first row that breaks the chain."""
    if not rows:
        return _report(rows, None, "Ledger is empty; genesis state verified.")
    found = _first_problem(rows)
    if found is not None:
        return _report(rows, found[0], found[1])
    return _report(
        rows, None, f"Cryptographic audit chain verified intact across {len(rows)} entries."
    )
