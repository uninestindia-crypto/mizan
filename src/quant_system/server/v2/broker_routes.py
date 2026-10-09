"""``/api/v2/broker``: the view-only connection to the person's broker.

These routes read an account and nothing else. There is no route to place, change or cancel an order, and the code
behind them has no broker address that could. The sign-in key is kept in its own Windows Credential Manager entry and
is never returned by a route.

Like ``live_routes.py`` this module imports nothing from ``router.py`` at the top of the file, so ``router.py`` can wire
it in without a cycle: ``V2Error`` and ``services()`` are fetched inside the functions that need them.
"""

from __future__ import annotations

import os
import threading
import webbrowser
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from quant_system.broker_view import BrokerView, BrokerViewError, SqliteSnapshotStore
from quant_system.broker_view.loopback import CallbackListener
from quant_system.broker_view.session_http import UrlLibSessionTransport
from quant_system.broker_view.upstox_read import UpstoxReader
from quant_system.data.upstox_http import UrlLibHttpTransport
from quant_system.server.v2 import paths
from quant_system.server.v2.credentials import (
    BROKER_VIEW_KEY,
    CredentialError,
    CredentialStore,
    ScopedCredentialStore,
)
from quant_system.server.v2.portfolio_risk import RiskHolding, portfolio_risk, unavailable

if TYPE_CHECKING:
    from quant_system.server.v2.router import Services

router = APIRouter(prefix="/broker", tags=["Broker view"])

_built: tuple[object, BrokerView] | None = None
_built_lock = threading.Lock()


class AssistantAccess(BaseModel):
    allowed: bool


class _StoreVault:
    """The broker view's view of its one entry in Windows Credential Manager."""

    def __init__(self, store: ScopedCredentialStore) -> None:
        self._store = store

    @property
    def available(self) -> bool:
        return self._store.available

    def load(self) -> str | None:
        return self._store.get(BROKER_VIEW_KEY)

    def save(self, key: str) -> None:
        self._store.set(BROKER_VIEW_KEY, key)

    def forget(self) -> None:
        self._store.delete(BROKER_VIEW_KEY)


def _saved(store: CredentialStore, name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        return (store.get(name) or "").strip()
    except (CredentialError, OSError):
        return ""


def _app_keys(store: CredentialStore) -> tuple[str, str] | None:
    """The person's own Upstox app key and secret, saved in Settings, then Accounts and keys."""
    key, secret = _saved(store, "UPSTOX_API_KEY"), _saved(store, "UPSTOX_API_SECRET")
    return (key, secret) if key and secret else None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _open_in_browser(address: str) -> bool:
    return webbrowser.open(address, new=2)


def _build(svc: Services) -> BrokerView:
    return BrokerView(
        vault=_StoreVault(ScopedCredentialStore(frozenset({BROKER_VIEW_KEY}))),
        store=SqliteSnapshotStore(paths.state_dir() / "broker_view.sqlite"),
        reader=UpstoxReader(UrlLibHttpTransport(), _utc_now),
        session=UrlLibSessionTransport(),
        app_keys=lambda: _app_keys(svc.credentials),
        open_page=_open_in_browser,
        make_listener=CallbackListener,
        clock=_utc_now,
    )


def broker_view_service() -> BrokerView:
    """The one broker view for the running app. Rebuilt only if the app's services are reset."""
    global _built
    from quant_system.server.v2.router import services

    svc = services()
    with _built_lock:
        if _built is None or _built[0] is not svc:
            _built = (svc, _build(svc))
        return _built[1]


def _refusal(error: BrokerViewError) -> Exception:
    from quant_system.server.v2.router import V2Error

    return V2Error(error.status, error.code, error.message)


@router.get("/status")
def broker_status(view: BrokerView = Depends(broker_view_service)) -> dict[str, Any]:
    """Whether the Upstox app keys are saved, whether a sign-in is open or in force, and when it ends."""
    return view.status()


@router.post("/upstox/connect")
def connect_upstox(view: BrokerView = Depends(broker_view_service)) -> dict[str, Any]:
    """Open Upstox's own sign-in page in the person's browser. The password is never typed into QuantOS."""
    try:
        return view.begin_login()
    except BrokerViewError as error:
        raise _refusal(error) from error


@router.delete("/upstox/connect")
def cancel_upstox_sign_in(view: BrokerView = Depends(broker_view_service)) -> dict[str, Any]:
    return view.cancel_login()


@router.get("/snapshot")
def broker_snapshot(view: BrokerView = Depends(broker_view_service)) -> dict[str, Any]:
    """The last figures with the time they were fetched. Reading this never asks Upstox for anything."""
    return view.snapshot()


@router.get("/risk")
def broker_risk(view: BrokerView = Depends(broker_view_service)) -> dict[str, Any]:
    """How the broker's holdings have moved together over the last year. Reads the stored figures; asks Upstox for nothing."""
    from quant_system.server.v2.router import V2Error, services

    holdings = [
        RiskHolding(str(row["symbol"]), float(row["value"] or 0.0))
        for row in view.snapshot()["holdings"]
        if row.get("value")
    ]
    if not holdings:
        return unavailable("There are no broker holdings to look at yet.")
    index = services().index
    if not index.is_ready():
        raise V2Error(
            409,
            "INDEX_NOT_READY",
            "Market data is not connected yet. Open Settings, then Market data.",
        )
    return portfolio_risk(index, holdings)


@router.post("/refresh")
def broker_refresh(view: BrokerView = Depends(broker_view_service)) -> dict[str, Any]:
    """Ask Upstox again (at most once every 30 seconds) and answer with the figures."""
    view.refresh()
    return view.snapshot()


@router.delete("/connection")
def disconnect_broker(view: BrokerView = Depends(broker_view_service)) -> dict[str, Any]:
    """Sign out, forget the key and delete the stored figures."""
    return view.disconnect()


@router.put("/assistant-access")
def set_assistant_access(
    body: AssistantAccess, view: BrokerView = Depends(broker_view_service)
) -> dict[str, Any]:
    return view.set_assistant_access(body.allowed)
