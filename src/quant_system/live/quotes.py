"""Read-only live prices for the app's screens and the Copilot.

`QuoteService.quotes` is the contract the Copilot already expects (`QuoteSource`): give it NSE symbols,
get one plain dictionary per symbol. `QuoteService.fetch` returns the same prices together with
whether Upstox is usable, which is what the screens need.

Every request goes out as a single batched GET. Each share's result is held for ten seconds so a screen
that refreshes often cannot trip Upstox's rate limit, and after Upstox says it is busy or cannot be
reached it is left alone for the same ten seconds. Held prices are labelled again each time they are
served, because "live" depends on the clock and not on when the price was fetched.
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from quant_system.data.upstox_http import HttpTransport, UrlLibHttpTransport
from quant_system.live import messages
from quant_system.live.entries import (
    QuoteBatch,
    QuoteEntry,
    RawQuote,
    entry_from_quote,
    refused_batch,
    unavailable,
)
from quant_system.live.market_hours import as_aware
from quant_system.live.upstox_fetch import Failure, FetchSettings, fetch_quotes
from quant_system.live.upstox_key import key_problem

logger = logging.getLogger(__name__)

CACHE_SECONDS = 10.0
TIMEOUT_SECONDS = 8.0
MAX_REPLY_BYTES = 512 * 1024
MAX_CACHED = 512


class BatchQuoteSource(Protocol):
    def fetch(self, symbols: Sequence[str]) -> QuoteBatch: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class QuoteServiceConfig:
    """Everything the service depends on, so a test can supply all of it and touch no network.

    `resolve_key` maps an NSE symbol to its Upstox instrument key (None when the symbol is unknown) and
    `key_provider` returns the current Upstox key (blank when there is none), asked afresh on every
    request so a key saved a moment ago works at once.
    """

    resolve_key: Callable[[str], str | None]
    key_provider: Callable[[], str]
    transport: HttpTransport = field(default_factory=UrlLibHttpTransport)
    clock: Callable[[], datetime] = _utc_now
    ttl_seconds: float = CACHE_SECONDS
    timeout_seconds: float = TIMEOUT_SECONDS
    max_response_bytes: int = MAX_REPLY_BYTES
    max_cached: int = MAX_CACHED


@dataclass(frozen=True, slots=True)
class _Held:
    raw: RawQuote | None  # None: Upstox answered but left this share out
    expires_at: datetime


class _ReplyCache:
    """Held results by symbol, bounded, safe to share between request threads."""

    def __init__(self, ttl: timedelta, capacity: int) -> None:
        self._ttl, self._capacity = ttl, capacity
        self._items: OrderedDict[str, _Held] = OrderedDict()
        self._blocked: tuple[datetime, Failure] | None = None
        self._lock = threading.Lock()

    def get(self, symbol: str, now: datetime) -> _Held | None:
        with self._lock:
            held = self._items.get(symbol)
            return held if held is not None and held.expires_at > now else None

    def keep(self, symbol: str, raw: RawQuote | None, now: datetime) -> None:
        with self._lock:
            self._items[symbol] = _Held(raw, now + self._ttl)
            self._items.move_to_end(symbol)
            while len(self._items) > self._capacity:
                self._items.popitem(last=False)  # the oldest is also the first to expire

    def block(self, failure: Failure, now: datetime) -> None:
        """Leave Upstox alone for the ttl, or for as long as it asked if that is longer."""
        asked = timedelta(seconds=failure.retry_after_seconds or 0)
        with self._lock:
            self._blocked = (now + max(self._ttl, asked), failure)

    def blocked(self, now: datetime) -> Failure | None:
        with self._lock:
            if self._blocked is not None and self._blocked[0] > now:
                return self._blocked[1]
            return None


class QuoteService:
    """Batched, cached, read-only prices from Upstox. Nothing here can place or change an order."""

    def __init__(self, config: QuoteServiceConfig) -> None:
        self._config = config
        self._settings = FetchSettings(
            config.transport, self._now, config.timeout_seconds, config.max_response_bytes
        )
        self._cache = _ReplyCache(timedelta(seconds=config.ttl_seconds), config.max_cached)

    def quotes(self, symbols: Sequence[str]) -> dict[str, Any]:
        """The Copilot's `QuoteSource` contract: one plain dictionary per symbol."""
        batch = self.fetch(symbols)
        return {symbol: entry.as_dict() for symbol, entry in batch.quotes.items()}

    def fetch(self, symbols: Sequence[str]) -> QuoteBatch:
        wanted = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
        api_key = self._config.key_provider().strip()
        problem = key_problem(api_key, self._now())
        if problem is not None:
            return refused_batch(wanted, problem)
        entries, pending = self._serve_held(wanted)
        failure = None
        if pending:
            fresh, failure = self._load(pending, api_key)
            entries.update(fresh)
        return QuoteBatch(
            connected=failure is None or not failure.key_rejected,
            message=failure.message if failure else None,
            quotes={symbol: entries[symbol] for symbol in wanted},
        )

    def _now(self) -> datetime:
        return as_aware(self._config.clock())

    def _serve_held(self, wanted: Sequence[str]) -> tuple[dict[str, QuoteEntry], dict[str, str]]:
        """Entries that need no request, and the instrument key of each share that does."""
        now = self._now()
        entries: dict[str, QuoteEntry] = {}
        pending: dict[str, str] = {}
        for symbol in wanted:
            held = self._cache.get(symbol, now)
            if held is not None:
                entries[symbol] = _entry_for(symbol, held.raw, now)
                continue
            instrument = self._instrument_key(symbol)
            if instrument is None:
                entries[symbol] = unavailable(messages.not_in_market_data(symbol))
            else:
                pending[symbol] = instrument
        return entries, pending

    def _instrument_key(self, symbol: str) -> str | None:
        try:
            key = self._config.resolve_key(symbol)
        except LookupError:  # the market index does not know the symbol
            return None
        return (key or "").strip() or None

    def _load(
        self, pending: dict[str, str], api_key: str
    ) -> tuple[dict[str, QuoteEntry], Failure | None]:
        blocked = self._cache.blocked(self._now())
        if blocked is not None:
            return _all_unavailable(pending, blocked), blocked
        result = fetch_quotes(self._settings, api_key, pending)
        if result.failure is not None:
            self._note(result.failure)
            return _all_unavailable(pending, result.failure), result.failure
        return self._keep(pending, result.quotes), None

    def _note(self, failure: Failure) -> None:
        logger.warning("Upstox price request did not succeed (%s).", failure.reason)
        if failure.transient:
            self._cache.block(failure, self._now())

    def _keep(self, pending: dict[str, str], quotes: dict[str, RawQuote]) -> dict[str, QuoteEntry]:
        """Hold each result, and label it by the clock at the moment the reply arrived."""
        now = self._now()
        entries: dict[str, QuoteEntry] = {}
        for symbol in pending:
            raw = quotes.get(symbol)
            self._cache.keep(symbol, raw, now)
            entries[symbol] = _entry_for(symbol, raw, now)
        return entries


def _entry_for(symbol: str, raw: RawQuote | None, now: datetime) -> QuoteEntry:
    if raw is None:
        return unavailable(messages.no_price(symbol))
    return entry_from_quote(raw, now)


def _all_unavailable(pending: dict[str, str], failure: Failure) -> dict[str, QuoteEntry]:
    return {symbol: unavailable(failure.message) for symbol in pending}
