"""GET-only HTTP transport and retry configuration for Upstox market data."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class TransportTimeout(Exception):
    """The provider did not finish within the configured deadline."""


class TransportConnectionError(Exception):
    """The provider connection failed before a response was available."""


class ResponseTooLarge(Exception):
    """The provider response exceeded the configured body limit."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Owned HTTP response shape at the provider boundary."""

    status: int
    body: bytes
    headers: Mapping[str, str]


class HttpTransport(Protocol):
    """Narrow GET-only transport contract; broker writes cannot be expressed."""

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse: ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        _msg: str,
        headers: Any,
        _newurl: str,
    ) -> None:
        return None


class UrlLibHttpTransport:
    """Standard-library HTTPS transport that refuses redirects and caps bodies."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                return HttpResponse(
                    status=response.status,
                    body=_read_limited(response, max_response_bytes),
                    headers=_normalize_headers(response.headers),
                )
        except urllib.error.HTTPError as error:
            with error:
                return HttpResponse(
                    status=error.code,
                    body=_read_limited(error, max_response_bytes),
                    headers=_normalize_headers(error.headers),
                )
        except TimeoutError as error:
            raise TransportTimeout("Upstox request exceeded its deadline") from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TransportTimeout("Upstox request exceeded its deadline") from error
            raise TransportConnectionError("Upstox connection failed") from error


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry policy for idempotent provider GET requests."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be positive")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds cannot be below base_delay_seconds")

    def delay_seconds(
        self,
        attempt_number: int,
        *,
        retry_after_seconds: int | None,
        jitter: float,
    ) -> float:
        if retry_after_seconds is not None:
            return min(float(retry_after_seconds), self.max_delay_seconds)
        exponential = self.base_delay_seconds * (2 ** max(0, attempt_number - 1))
        return float(min(exponential * (0.5 + (0.5 * jitter)), self.max_delay_seconds))


@dataclass(frozen=True, slots=True)
class UpstoxClientConfig:
    """Non-secret transport limits for the read-only adapter."""

    timeout_seconds: float = 10.0
    max_response_bytes: int = 2 * 1024 * 1024
    retry_policy: RetryPolicy = RetryPolicy()

    def __post_init__(self) -> None:
        if not 0 < self.timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be in (0, 30]")
        if not 1024 <= self.max_response_bytes <= 16 * 1024 * 1024:
            raise ValueError("max_response_bytes must be between 1 KiB and 16 MiB")


def _read_limited(response: Any, max_response_bytes: int) -> bytes:
    body = response.read(max_response_bytes + 1)
    if len(body) > max_response_bytes:
        raise ResponseTooLarge("provider response exceeded the configured size")
    return bytes(body)


def _normalize_headers(headers: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}
