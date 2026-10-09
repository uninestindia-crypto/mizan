"""The three reads: holdings, open positions and cash.

Every request is a GET through the same GET-only transport the rest of QuantOS uses for market data, which has no way
to send anything else. Each address is checked against ``ALLOWED_CALLS`` immediately before it is used. Whatever goes
wrong becomes a ``Failure`` carrying a plain sentence; the text of an underlying error is never kept, because it can
carry the request headers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

from quant_system.broker_view import messages
from quant_system.broker_view.endpoints import (
    ALLOWED_CALLS,
    FUNDS_QUERY,
    UPSTOX_FUNDS_URL,
    UPSTOX_HOLDINGS_URL,
    UPSTOX_POSITIONS_URL,
)
from quant_system.broker_view.model import Cash, HoldingRow, PositionRow
from quant_system.broker_view.upstox_parse import (
    Parsed,
    ReplyUnreadable,
    parse_funds,
    parse_holdings,
    parse_positions,
)
from quant_system.data.market_data import AcquisitionFailureCode
from quant_system.data.upstox_failures import map_http_failure
from quant_system.data.upstox_http import (
    HttpResponse,
    HttpTransport,
    ResponseTooLarge,
    TransportConnectionError,
    TransportTimeout,
)

# Upstox's reply when an account asks for its holdings from an address that is not registered. Measured on
# 2026-08-31 with the one-year analytics key; it is a different problem from a key that has stopped working.
STATIC_IP_CODE = "UDAPI1221"


@dataclass(frozen=True, slots=True)
class ReaderSettings:
    timeout_seconds: float = 10.0
    max_response_bytes: int = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Failure:
    """Why a read did not give figures. ``reason`` is for the log only and is never shown."""

    message: str
    reason: str
    key_rejected: bool = False
    static_ip: bool = False


@dataclass(frozen=True, slots=True)
class Read[T]:
    value: T | None = None
    failure: Failure | None = None


class UpstoxReader:
    def __init__(
        self,
        transport: HttpTransport,
        clock: Callable[[], datetime],
        settings: ReaderSettings = ReaderSettings(),
    ) -> None:
        self._transport = transport
        self._clock = clock
        self._settings = settings

    def holdings(self, key: str) -> Read[Parsed[HoldingRow]]:
        return self._read(key, UPSTOX_HOLDINGS_URL, (), parse_holdings)

    def positions(self, key: str) -> Read[Parsed[PositionRow]]:
        return self._read(key, UPSTOX_POSITIONS_URL, (), parse_positions)

    def funds(self, key: str) -> Read[Cash]:
        return self._read(key, UPSTOX_FUNDS_URL, FUNDS_QUERY, parse_funds)

    def _read[T](
        self,
        key: str,
        url: str,
        query: tuple[tuple[str, str], ...],
        parse: Callable[[bytes], T],
    ) -> Read[T]:
        response = self._get(key, url, query)
        if isinstance(response, Failure):
            return Read(failure=response)
        try:
            return Read(value=parse(response.body))
        except ReplyUnreadable:
            return Read(failure=Failure(messages.UNREADABLE, "reply unreadable"))

    def _get(
        self, key: str, url: str, query: tuple[tuple[str, str], ...]
    ) -> HttpResponse | Failure:
        if ("GET", url) not in ALLOWED_CALLS:
            return Failure(messages.UNAVAILABLE, "address not allowed")
        address = f"{url}?{urlencode(query)}" if query else url
        headers = {
            "Accept": "application/json",
            "User-Agent": "QuantOS/1.0",
            "Authorization": f"Bearer {key}",
        }
        try:
            response = self._transport.get(
                address,
                headers=headers,
                timeout_seconds=self._settings.timeout_seconds,
                max_response_bytes=self._settings.max_response_bytes,
            )
        except TransportTimeout:
            return Failure(messages.TOO_SLOW, "timeout")
        except ResponseTooLarge:
            return Failure(messages.TOO_LARGE, "reply too large")
        except TransportConnectionError:
            return Failure(messages.UNREACHABLE, "connection failed")
        except (
            Exception
        ):  # an injected transport may fail in any way; its text can hold the headers
            return Failure(messages.UNREACHABLE, "request failed")
        if len(response.body) > self._settings.max_response_bytes:
            return Failure(messages.TOO_LARGE, "reply too large")
        if response.status == 200:
            return response
        return self._status_failure(response)

    def _status_failure(self, response: HttpResponse) -> Failure:
        failure = map_http_failure(response, self._clock())
        reason = f"status {response.status}"
        if failure.code is AcquisitionFailureCode.PROVIDER_UNAUTHORIZED:
            if failure.provider_code == STATIC_IP_CODE:
                return Failure(messages.STATIC_IP_REQUIRED, reason, static_ip=True)
            return Failure(messages.KEY_REJECTED, reason, key_rejected=True)
        if failure.code is AcquisitionFailureCode.PROVIDER_RATE_LIMITED:
            return Failure(messages.BUSY, reason)
        if failure.code is AcquisitionFailureCode.PROVIDER_TIMEOUT:
            return Failure(messages.TOO_SLOW, reason)
        return Failure(messages.UNAVAILABLE, reason)
