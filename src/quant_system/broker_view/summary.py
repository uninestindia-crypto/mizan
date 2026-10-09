"""The short summary of the person's account that the assistant may read, and nothing beyond it.

It holds symbols, quantities, prices, profit or loss and shares of the whole, the totals, and when the figures were
fetched. It holds no key, no name, no email, no user or client number, and no instrument identifier. It exists only if the
person has switched the assistant's access on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quant_system.broker_view.model import INDIA

MAX_HOLDINGS = 30
MAX_POSITIONS = 20
SUMMARY_KEYS = frozenset(
    {
        "source",
        "totals",
        "cash_available",
        "holdings",
        "holdings_not_shown",
        "positions",
        "positions_not_shown",
        "could_not_read",
        "warnings",
        "risk",
        "note",
    }
)
_TOTAL_KEYS = ("value", "invested", "pnl", "pnl_pct", "today")
_HOLDING_KEYS = (
    "symbol",
    "quantity",
    "average_price",
    "last_price",
    "pnl",
    "pnl_pct",
    "weight_pct",
)
_POSITION_KEYS = ("symbol", "product", "quantity", "pnl")
_NOTE = (
    "This is a view-only copy of the person's broker account. Nothing can be bought, sold or changed "
    "through QuantOS, so never suggest otherwise. Always say when the figures were fetched. "
    "Percentages are in percent points."
)
_MINUTE = 60
_HOUR = 3600
_DAY = 86400


def age_in_words(seconds: float) -> str:
    if seconds < _MINUTE:
        return "a moment ago"
    if seconds < _HOUR:
        minutes = int(seconds // _MINUTE)
        return f"{minutes} {'minute' if minutes == 1 else 'minutes'} ago"
    if seconds < _DAY:
        hours = int(seconds // _HOUR)
        return f"{hours} {'hour' if hours == 1 else 'hours'} ago"
    days = int(seconds // _DAY)
    return f"{days} {'day' if days == 1 else 'days'} ago"


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: row.get(key) for key in keys}


def assistant_summary(
    payload: dict[str, Any], fetched_at: datetime, now: datetime, *, key_ended: bool
) -> dict[str, Any]:
    local = fetched_at.astimezone(INDIA)
    source = (
        f"Fetched from the person's Upstox account at {local:%H:%M} on {local:%d %b %Y} "
        f"(India time), {age_in_words((now - fetched_at).total_seconds())}."
    )
    if key_ended:
        source += " The sign-in has since ended, so these figures may be out of date."
    holdings = list(payload.get("holdings") or [])
    positions = list(payload.get("positions") or [])
    totals = payload.get("totals") or {}
    cash = payload.get("cash") or {}
    return {
        "source": source,
        "totals": _pick(totals, _TOTAL_KEYS),
        "cash_available": cash.get("available"),
        "holdings": [_pick(row, _HOLDING_KEYS) for row in holdings[:MAX_HOLDINGS]],
        "holdings_not_shown": max(0, len(holdings) - MAX_HOLDINGS),
        "positions": [_pick(row, _POSITION_KEYS) for row in positions[:MAX_POSITIONS]],
        "positions_not_shown": max(0, len(positions) - MAX_POSITIONS),
        "could_not_read": dict(payload.get("skipped") or {}),
        "warnings": list(payload.get("warnings") or []),
        "note": _NOTE,
    }
