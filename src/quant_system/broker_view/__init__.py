"""A view-only connection to the person's broker account (Upstox first).

QuantOS can look at the holdings, open positions and cash the broker shows, and say how fresh they are. Nothing in
this package can place, change or cancel an order, move money, or change an account setting: it has a closed list of
broker addresses (``endpoints.ALLOWED_CALLS``), reads through a GET-only transport, and keeps the one key it is given
in Windows Credential Manager under its own entry, never in the environment, a file, a log or an AI prompt.

Design and the rejected alternatives: ``agent_context/decisions/20261007-broker-view-only.md``.
"""

from __future__ import annotations

from quant_system.broker_view.model import Cash, HoldingRow, PositionRow, Snapshot
from quant_system.broker_view.service import BrokerView, BrokerViewError, KeyVault
from quant_system.broker_view.store import (
    InMemorySnapshotStore,
    SnapshotStore,
    SqliteSnapshotStore,
)

__all__ = [
    "BrokerView",
    "BrokerViewError",
    "Cash",
    "HoldingRow",
    "InMemorySnapshotStore",
    "KeyVault",
    "PositionRow",
    "Snapshot",
    "SnapshotStore",
    "SqliteSnapshotStore",
]
