"""The portfolio seen by account: a line per account, and one line per stock across the accounts being viewed."""

from __future__ import annotations

from typing import Any

from quant_system.server.v2.accounts import ACCOUNT_KINDS, Account
from quant_system.server.v2.holding_periods import HOLDING_PERIOD_NOTE

__all__ = ["ACCOUNT_KINDS", "account_rows", "positions"]


def _sum(rows: list[dict[str, Any]], key: str) -> float:
    return float(sum(r[key] for r in rows if "value" in r))


def _account_line(account: Account, rows: list[dict[str, Any]], total: float) -> dict[str, Any]:
    mine = [r for r in rows if r["account_id"] == account.id]
    value, cost = _sum(mine, "value"), _sum(mine, "cost")
    identity = account.model_dump(include={"id", "name", "owner", "kind", "broker"})
    return {
        **identity,
        "holdings": len(mine),
        "value": value,
        "cost": cost,
        "pnl": value - cost,
        "pnl_pct": value / cost - 1.0 if cost else None,
        "weight": value / total if total else 0.0,
    }


def account_rows(accounts: list[Account], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One line per account: what it holds, what that is worth, and its share of everything held."""
    total = _sum(rows, "value")
    return [_account_line(account, rows, total) for account in accounts]


def _where(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "account_id": row["account_id"],
        "account_name": row.get("account_name"),
        "quantity": row["quantity"],
        "value": row.get("value"),
    }


def _worth(valued: list[dict[str, Any]], cost: float, total: float) -> dict[str, Any]:
    value = _sum(valued, "value")
    return {
        "close": valued[0]["close"],
        "value": value,
        "pnl": value - cost,
        "pnl_pct": value / cost - 1.0 if cost else None,
        "weight": value / total if total else 0.0,
    }


def _lot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "holding_id": row.get("id"),
        "account_id": row["account_id"],
        "account_name": row.get("account_name"),
        "quantity": row["quantity"],
        **row["lot"],
    }


def _lots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each buy lot with its holding period, oldest first. Facts only: no tax rates or amounts."""
    held = [_lot(row) for row in rows if row.get("lot")]
    return sorted(held, key=lambda lot: (lot["buy_date"], lot["holding_id"] or 0))


def _position(symbol: str, rows: list[dict[str, Any]], total: float) -> dict[str, Any]:
    valued = [r for r in rows if "value" in r]
    quantity = sum(r["quantity"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    position: dict[str, Any] = {
        "symbol": symbol,
        "name": next((r["name"] for r in valued), None),
        "quantity": quantity,
        "avg_price": cost / quantity if quantity else 0.0,
        "cost": cost,
        "accounts": [_where(r) for r in rows],
        "lots": _lots(rows),
        "lots_note": HOLDING_PERIOD_NOTE,
    }
    if valued and len(valued) == len(rows):
        return {**position, **_worth(valued, cost, total)}
    return {**position, "error": "Not in the market data"}


def positions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One line per stock across the accounts in view, with the average price weighted by shares."""
    total = _sum(rows, "value")
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_symbol.setdefault(str(row["symbol"]), []).append(row)
    return [_position(symbol, group, total) for symbol, group in by_symbol.items()]
