"""The only module in this package that may open an internet connection of its own, and it can do exactly two things.

It swaps the single-use sign-in code for a key (a POST to the sign-in service) and it ends the session at sign-out (a
DELETE to the log-out address). Neither takes an address as a parameter, so neither can be pointed anywhere else. Reads
of holdings, positions and cash go through the GET-only transport the rest of QuantOS shares, not through this one.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any, Protocol

from quant_system.broker_view.endpoints import UPSTOX_LOGOUT_URL, UPSTOX_TOKEN_URL
from quant_system.data.upstox_http import (
    HttpResponse,
    ResponseTooLarge,
    TransportConnectionError,
    TransportTimeout,
)


class SessionTransport(Protocol):
    def exchange_code(
        self, form: Mapping[str, str], *, timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse: ...

    def end_session(
        self, key: str, *, timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class UrlLibSessionTransport:
    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirect())

    def exchange_code(
        self, form: Mapping[str, str], *, timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse:
        request = urllib.request.Request(
            UPSTOX_TOKEN_URL,
            data=urllib.parse.urlencode(dict(form)).encode("ascii"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "QuantOS/1.0",
            },
            method="POST",
        )
        return self._send(request, timeout_seconds, max_response_bytes)

    def end_session(
        self, key: str, *, timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse:
        request = urllib.request.Request(
            UPSTOX_LOGOUT_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "QuantOS/1.0",
            },
            method="DELETE",
        )
        return self._send(request, timeout_seconds, max_response_bytes)

    def _send(
        self, request: urllib.request.Request, timeout_seconds: float, max_response_bytes: int
    ) -> HttpResponse:
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                return _response(response.status, response, response.headers, max_response_bytes)
        except urllib.error.HTTPError as error:
            with error:
                return _response(error.code, error, error.headers, max_response_bytes)
        except TimeoutError as error:
            raise TransportTimeout("Upstox request exceeded its deadline") from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise TransportTimeout("Upstox request exceeded its deadline") from error
            raise TransportConnectionError("Upstox connection failed") from error


def _response(status: int, body: Any, headers: Any, max_response_bytes: int) -> HttpResponse:
    data = body.read(max_response_bytes + 1)
    if len(data) > max_response_bytes:
        raise ResponseTooLarge("provider response exceeded the configured size")
    return HttpResponse(
        status=status,
        body=bytes(data),
        headers={str(k).lower(): str(v) for k, v in headers.items()},
    )
