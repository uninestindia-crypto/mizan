"""``GET /api/v2/live/quotes``: read-only live prices from Upstox.

This route reads prices and nothing else; it offers no way to place, change or cancel an order.

The module is wired into the v2 router by the coordinator (``include_router(router, prefix="/api/v2")``).
It imports nothing from ``router.py`` at the top of the file, so it can be imported from there without a
cycle: ``V2Error`` and ``services()`` are fetched inside the functions that need them.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from quant_system.data.upstox_http import HttpTransport, UrlLibHttpTransport
from quant_system.live import BatchQuoteSource, QuoteService, QuoteServiceConfig
from quant_system.live.upstox_key import pick_key
from quant_system.market import MarketIndex, SymbolNotFoundError
from quant_system.market.index import IndexNotReadyError
from quant_system.server.v2.credentials import CredentialError, CredentialStore

if TYPE_CHECKING:
    from quant_system.server.v2.router import Services

router = APIRouter(prefix="/live", tags=["Live prices"])

MAX_SYMBOLS = 20
_SYMBOL_PATTERN = r"^[A-Z0-9&-]{1,15}$"
_SHOWN_CHARACTERS = 20

_built: tuple[object, QuoteService] | None = None
_built_lock = threading.Lock()


def index_resolver(index: MarketIndex) -> Callable[[str], str | None]:
    """Symbol to Upstox instrument key, from the market index. Anything it cannot say is None."""

    def resolve(symbol: str) -> str | None:
        try:
            info = index.symbol_info(symbol)
        except (SymbolNotFoundError, IndexNotReadyError, sqlite3.Error):
            return None
        return str(info.get("instrument_key") or "").strip() or None

    return resolve


def key_provider(
    store: CredentialStore, environ: Mapping[str, str] | None = None
) -> Callable[[], str]:
    """The current Upstox key: the app's environment first, then the saved keys, analytics first."""
    source = os.environ if environ is None else environ

    def read(name: str) -> str | None:
        value = source.get(name, "").strip()
        if value:
            return value
        try:
            return store.get(name)
        except (CredentialError, OSError):
            return None

    return lambda: pick_key(read)


def _transport() -> HttpTransport:
    return UrlLibHttpTransport()


def _build(svc: Services) -> QuoteService:
    config = QuoteServiceConfig(
        resolve_key=index_resolver(svc.index),
        key_provider=key_provider(svc.credentials),
        transport=_transport(),
    )
    return QuoteService(config)


def quote_service() -> QuoteService:
    """The one price service for the running app, so its ten-second cache is shared by every request.

    Rebuilt only if the app's services are reset. ``services()`` is imported here, not at the top of
    the file, because ``router.py`` is where this module gets wired in.
    """
    global _built
    from quant_system.server.v2.router import services

    svc = services()
    with _built_lock:
        if _built is None or _built[0] is not svc:
            _built = (svc, _build(svc))
        return _built[1]


def _refusal(code: str, message: str) -> Exception:
    from quant_system.server.v2.router import V2Error

    return V2Error(422, code, message)


def parse_symbols(raw: str) -> list[str]:
    """The distinct, upper-cased symbols asked for, or a 422 in the API's usual error style."""
    pieces = [piece.strip() for piece in raw.split(",") if piece.strip()]
    if not pieces:
        raise _refusal("NO_SYMBOLS", "Choose at least one share to price.")
    for piece in pieces:
        if not (piece.isascii() and re.fullmatch(_SYMBOL_PATTERN, piece.upper())):
            shown = piece[:_SHOWN_CHARACTERS].upper()
            raise _refusal("INVALID_SYMBOL", f"{shown} is not a valid share symbol.")
    wanted = list(dict.fromkeys(piece.upper() for piece in pieces))
    if len(wanted) > MAX_SYMBOLS:
        raise _refusal("TOO_MANY_SYMBOLS", f"Ask for at most {MAX_SYMBOLS} shares at a time.")
    return wanted


@router.get("/quotes")
def live_quotes(
    symbols: str = Query("", description="NSE symbols separated by commas, at most 20."),
    service: BatchQuoteSource = Depends(quote_service),
) -> dict[str, Any]:
    """Prices for up to 20 shares in one call, each labelled live, delayed, last close or unavailable."""
    return service.fetch(parse_symbols(symbols)).as_dict()
