"""Accounts: one person often manages several (their own, a spouse's, a parent's, a HUF's), and every holding
belongs to one of them.

The rules live here and nowhere else, in plain words: a name, an owner, a kind of account and a broker, no two
accounts with the same name, at least one account always, and no account deleted while it still holds stocks unless
those stocks are told where to go.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import AbstractContextManager
from datetime import UTC, datetime

from pydantic import BaseModel

__all__ = [
    "ACCOUNT_KINDS",
    "ACCOUNT_SCHEMA",
    "Account",
    "AccountError",
    "AccountsMixin",
    "migrate_accounts",
]

ACCOUNT_KINDS = (
    "Demat account",
    "Trading account",
    "Mutual fund account",
    "Retirement account",
    "Child's account",
    "HUF account",
    "Company account",
    "Other",
)
DEFAULT_ACCOUNT = ("My account", "Me", "Demat account", "")
MAX_NAME = 60
MAX_OWNER = 40
MAX_BROKER = 40

ACCOUNT_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    owner TEXT NOT NULL,
    kind TEXT NOT NULL,
    broker TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


class AccountError(ValueError):
    """A refusal with a sentence a person can read as it is."""


class Account(BaseModel):
    id: int
    name: str
    owner: str
    kind: str
    broker: str = ""
    created_at: str = ""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _stocks(count: int) -> str:
    return f"{count} stock" if count == 1 else f"{count} stocks"


def migrate_accounts(conn: sqlite3.Connection) -> None:
    """Give an older database its accounts: a default one, with every existing holding in it. Nothing is lost."""
    columns = {str(r[1]) for r in conn.execute("PRAGMA table_info(holdings)")}
    if "account_id" not in columns:
        conn.execute("ALTER TABLE holdings ADD COLUMN account_id INTEGER NOT NULL DEFAULT 0")
    first = conn.execute("SELECT id FROM accounts ORDER BY id LIMIT 1").fetchone()
    if first is None:
        name, owner, kind, broker = DEFAULT_ACCOUNT
        cursor = conn.execute(
            "INSERT INTO accounts(name, owner, kind, broker, created_at) VALUES (?,?,?,?,?)",
            (name, owner, kind, broker, _now()),
        )
        default_id = int(cursor.lastrowid or 0)
    else:
        default_id = int(first[0])
    conn.execute(
        "UPDATE holdings SET account_id = ? WHERE account_id NOT IN (SELECT id FROM accounts)",
        (default_id,),
    )


def _row(r: sqlite3.Row) -> Account:
    return Account(
        id=int(r["id"]),
        name=str(r["name"]),
        owner=str(r["owner"]),
        kind=str(r["kind"]),
        broker=str(r["broker"]),
        created_at=str(r["created_at"]),
    )


class AccountsMixin:
    """Account methods for ``AppState``. It supplies the lock and the connection."""

    _lock: threading.Lock

    def _connect(self) -> AbstractContextManager[sqlite3.Connection]:  # supplied by AppState
        raise NotImplementedError

    def accounts(self) -> list[Account]:
        with self._connect() as conn:
            return [_row(r) for r in conn.execute("SELECT * FROM accounts ORDER BY id")]

    def account(self, account_id: int) -> Account | None:
        return next((a for a in self.accounts() if a.id == account_id), None)

    def default_account_id(self) -> int:
        return self.accounts()[0].id

    def require_account(self, account_id: int | None) -> int:
        """The id to store a holding under: the first account when none is named, else that account or a refusal."""
        if account_id is None:
            return self.default_account_id()
        if self.account(account_id) is None:
            raise AccountError("That account does not exist.")
        return account_id

    def _checked(
        self, name: str, owner: str, kind: str, broker: str, exclude: int | None
    ) -> tuple[str, str, str, str]:
        name, owner, broker = name.strip(), owner.strip(), broker.strip()
        if not 1 <= len(name) <= MAX_NAME:
            raise AccountError(f"Give the account a name of 1 to {MAX_NAME} characters.")
        if not 1 <= len(owner) <= MAX_OWNER:
            raise AccountError(f"The owner's name must be 1 to {MAX_OWNER} characters.")
        if len(broker) > MAX_BROKER:
            raise AccountError(f"The broker's name can be at most {MAX_BROKER} characters.")
        if kind not in ACCOUNT_KINDS:
            raise AccountError("Choose one of the offered kinds of account.")
        taken = {a.name.lower() for a in self.accounts() if a.id != exclude}
        if name.lower() in taken:
            raise AccountError(f"You already have an account called “{name}”. Choose another name.")
        return name, owner, kind, broker

    def add_account(self, name: str, owner: str, kind: str, broker: str) -> Account:
        name, owner, kind, broker = self._checked(name, owner, kind, broker, None)
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO accounts(name, owner, kind, broker, created_at) VALUES (?,?,?,?,?)",
                (name, owner, kind, broker, _now()),
            )
            new_id = int(cursor.lastrowid or 0)
        created = self.account(new_id)
        assert created is not None
        return created

    def update_account(
        self, account_id: int, name: str, owner: str, kind: str, broker: str
    ) -> Account | None:
        if self.account(account_id) is None:
            return None
        name, owner, kind, broker = self._checked(name, owner, kind, broker, account_id)
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE accounts SET name = ?, owner = ?, kind = ?, broker = ? WHERE id = ?",
                (name, owner, kind, broker, account_id),
            )
        return self.account(account_id)

    def holding_counts(self) -> dict[int, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT account_id, COUNT(*) AS n FROM holdings GROUP BY account_id"
            )
            return {int(r["account_id"]): int(r["n"]) for r in rows}

    def _refuse_unless_deletable(self, account_id: int, move_to: int | None) -> int:
        """Return how many stocks the account holds, or refuse in plain words."""
        if self.account(account_id) is None:
            raise AccountError("That account does not exist.")
        if len(self.accounts()) <= 1:
            raise AccountError("You need at least one account, so this one cannot be deleted.")
        count = self.holding_counts().get(account_id, 0)
        if count and move_to is None:
            raise AccountError(
                f"This account still holds {_stocks(count)}. Choose where to move them first."
            )
        if count and (move_to == account_id or self.account(move_to or 0) is None):
            raise AccountError("Choose a different account to move the stocks to.")
        return count

    def delete_account(self, account_id: int, move_to: int | None = None) -> int:
        """Delete an account and return how many stocks were moved out of it. Never the last account."""
        count = self._refuse_unless_deletable(account_id, move_to)
        with self._lock, self._connect() as conn:
            if count:
                conn.execute(
                    "UPDATE holdings SET account_id = ? WHERE account_id = ?", (move_to, account_id)
                )
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        return count
