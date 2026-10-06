"""One batched, read-only price request to Upstox, and the reading of its reply.

Only GET is ever sent, through the same transport the rest of QuantOS uses for market data, which
cannot express anything else. Replies are read with the data package's own strict helpers, so a price
is matched to its share the same way the rest of the product matches it: by the instrument inside the
entry, never by how the entry is labelled. Whatever goes wrong becomes a `Failure` carrying a
plain-language message; the text of the underlying error is never kept, because it can carry the
request headers.
"""

from __future__ import annotations

import json
import math
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from quant_system.data.market_data import AcquisitionFailureCode
from quant_system.data.upstox import UpstoxClient
from quant_system.data.upstox_failures import map_http_failure
from quant_system.data.upstox_http import (
    HttpResponse,
    HttpTransport,
    ResponseTooLarge,
    TransportConnectionError,
    TransportTimeout,
)

# The matcher and the strict number and time readers belong to the data package, which measured the
# real reply shape (agent_context/work/completed/20261005-1930Z-claude-upstox-quote-key-shape.md).
# They are private there, so this is a coupling to flag: a public name for them would be better.
from quant_system.data.upstox_parsing import _parse_decimal, _parse_timestamp, _select_quote_entry
from quant_system.live import messages
from quant_system.live.entries import RawQuote

QUOTES_URL = f"{UpstoxClient.BASE_URL}/v2/market-quote/quotes"
MAX_REQUESTS = 6  # one batch, and at most five more when it is refused and has to be split to find the share to blame
LONG_WAIT_SECONDS = 120  # a wait longer than this is described as "a few minutes", not "a minute"
_EPOCH_MS_DIGITS = 13  # an epoch time in milliseconds has thirteen digits from 2001 until 2286


@dataclass(frozen=True, slots=True)
class FetchSettings:
    transport: HttpTransport
    clock: Callable[[], datetime]
    timeout_seconds: float
    max_response_bytes: int


@dataclass(frozen=True, slots=True)
class Failure:
    """Why a request did not give prices. `reason` is for the log only and is never shown."""

    message: str
    reason: str
    key_rejected: bool = False
    transient: bool = False
    retry_after_seconds: int | None = None
    # Upstox refused the request itself (a 4xx), which one bad share in a batch can cause.
    bad_request: bool = False


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Prices by symbol, or the failure that stopped them."""

    quotes: dict[str, RawQuote]
    failure: Failure | None = None


def request_url(instrument_keys: list[str]) -> str:
    query = urlencode({"instrument_key": ",".join(instrument_keys)}, safe=",|")
    return f"{QUOTES_URL}?{query}"


def fetch_quotes(
    settings: FetchSettings, api_key: str, requested: Mapping[str, str]
) -> FetchResult:
    """Ask for every instrument in one call. `requested` maps each symbol to its instrument key.

    If Upstox refuses the whole batch as a bad request, one share in it may be to blame, so the batch is split
    to find out. That is bounded and cannot be checked against the real service, only against a stand-in.
    """
    first = _fetch_group(settings, api_key, requested)
    if first.failure is None or not first.failure.bad_request or len(requested) < 2:
        return first
    return _isolate(settings, api_key, requested, first.failure)


def _fetch_group(
    settings: FetchSettings, api_key: str, requested: Mapping[str, str]
) -> FetchResult:
    response = _send(settings, api_key, list(dict.fromkeys(requested.values())))
    if isinstance(response, Failure):
        return FetchResult({}, response)
    quotes = parse_reply(response.body, requested)
    if quotes is None:
        return FetchResult({}, Failure(messages.UNREADABLE, "reply unreadable", transient=True))
    return FetchResult(quotes)


def _halves(group: Mapping[str, str]) -> list[dict[str, str]]:
    items = list(group.items())
    middle = (len(items) + 1) // 2
    return [dict(items[:middle]), dict(items[middle:])]


def _isolate(
    settings: FetchSettings, api_key: str, requested: Mapping[str, str], refused: Failure
) -> FetchResult:
    """Price what can be priced when a batch was refused. Halves are tried before smaller pieces, and a share
    still refused on its own, or left in a piece the request limit stopped short of, simply has no price."""
    quotes: dict[str, RawQuote] = {}
    waiting = deque(_halves(requested))
    sent = 1
    while waiting and sent < MAX_REQUESTS:
        group = waiting.popleft()
        sent += 1
        result = _fetch_group(settings, api_key, group)
        quotes.update(result.quotes)
        if result.failure is not None and not result.failure.bad_request:
            return FetchResult(quotes, result.failure)
        if result.failure is not None and len(group) > 1:
            waiting.extend(_halves(group))
    return FetchResult(quotes) if quotes else FetchResult({}, refused)


def _send(
    settings: FetchSettings, api_key: str, instrument_keys: list[str]
) -> HttpResponse | Failure:
    headers = {
        "Accept": "application/json",
        "User-Agent": "QuantOS/1.0",
        "Authorization": f"Bearer {api_key}",
    }
    try:
        response = settings.transport.get(
            request_url(instrument_keys),
            headers=headers,
            timeout_seconds=settings.timeout_seconds,
            max_response_bytes=settings.max_response_bytes,
        )
    except TransportTimeout:
        return Failure(messages.TOO_SLOW, "timeout", transient=True)
    except ResponseTooLarge:
        return Failure(messages.TOO_LARGE, "reply too large", transient=True)
    except TransportConnectionError:
        return Failure(messages.UNREACHABLE, "connection failed", transient=True)
    except Exception:  # an injected transport may fail in any way; its text can hold the headers
        return Failure(messages.UNREACHABLE, "request failed", transient=True)
    if len(response.body) > settings.max_response_bytes:
        return Failure(messages.TOO_LARGE, "reply too large", transient=True)
    if response.status == 200:
        return response
    return _status_failure(response, settings.clock())


def _status_failure(response: HttpResponse, detected_at: datetime) -> Failure:
    """The data package's own reading of an HTTP status, put in words a person can act on."""
    failure = map_http_failure(response, detected_at)
    reason = f"status {response.status}"
    if failure.code is AcquisitionFailureCode.PROVIDER_UNAUTHORIZED:
        return Failure(messages.KEY_REJECTED, reason, key_rejected=True)
    wait = failure.retry_after_seconds
    long_wait = wait is not None and wait > LONG_WAIT_SECONDS
    if failure.code is AcquisitionFailureCode.PROVIDER_RATE_LIMITED:
        busy = messages.BUSY_LONGER if long_wait else messages.BUSY
        return Failure(busy, reason, transient=True, retry_after_seconds=wait)
    if failure.code is AcquisitionFailureCode.PROVIDER_TIMEOUT:
        return Failure(messages.TOO_SLOW, reason, transient=True)
    said = messages.UNAVAILABLE_LONGER if long_wait else messages.UNAVAILABLE_NOW
    client_error = 400 <= response.status < 500
    return Failure(said, reason, transient=True, retry_after_seconds=wait, bad_request=client_error)


# ------------------------------------------------------------------------------ the reply


def parse_reply(body: bytes, requested: Mapping[str, str]) -> dict[str, RawQuote] | None:
    """A price for each requested symbol Upstox answered for, or None if the reply is unreadable.

    A symbol Upstox left out, or whose entry is not provably that instrument, is simply absent from
    the result: it is the share that is unavailable, not the whole reply.
    """
    try:
        payload = json.loads(body)
    except (ValueError, RecursionError):
        return None
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    found: dict[str, RawQuote] = {}
    for symbol, instrument in requested.items():
        raw = _quote_for(data, instrument, symbol)
        if raw is not None:
            found[symbol] = raw
    return found


def _quote_for(data: dict[str, Any], instrument: str, symbol: str) -> RawQuote | None:
    try:
        entry = _select_quote_entry(data, instrument_key=instrument, symbol=symbol)
        price = float(_parse_decimal(entry.get("last_price"), "last_price"))
    except (ValueError, OverflowError):  # drift is a ValueError: absent, or not this instrument
        return None
    if not (math.isfinite(price) and price > 0):
        return None
    return RawQuote(price, _change_pct(price, entry), _quoted_at(entry), _last_traded_at(entry))


def _last_traded_at(entry: dict[str, Any]) -> datetime | None:
    """When the share last changed hands, from `last_trade_time` (epoch milliseconds). A bad value is ignored."""
    value = entry.get("last_trade_time")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if not (text.isascii() and text.isdigit() and len(text) == _EPOCH_MS_DIGITS):
        return None
    try:
        return datetime.fromtimestamp(int(text) / 1000, UTC)
    except (ValueError, OverflowError, OSError):
        return None


def _quoted_at(entry: dict[str, Any]) -> datetime | None:
    """When Upstox says the price was set. A time without a zone is not trusted: it may be anywhere."""
    try:
        return _parse_timestamp(entry.get("timestamp"))
    except ValueError:
        return None


def _change_pct(price: float, entry: dict[str, Any]) -> float | None:
    """The move since the previous close, when the entry gives the change in rupees."""
    try:
        change = float(_parse_decimal(entry.get("net_change"), "net_change"))
    except (ValueError, OverflowError):
        return None
    previous = price - change
    if not math.isfinite(previous) or previous <= 0:
        return None
    return round(change / previous * 100, 2)
