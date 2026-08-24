"""Security module for QuantOS API server.

Enforces local trust boundary:
- Loopback binding and Host header validation (defense against DNS rebinding).
- Client address verification.
- Strict CORS validation (loopback origins only, hostile origins rejected).
- Anti-CSRF ephemeral session token management and verification.
- Standard security headers and request ID tracing.
- Unified error response formatting.
"""

from __future__ import annotations

import re
import secrets
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Allowed loopback Host patterns (with or without port)
ALLOWED_HOST_REGEX = re.compile(
    r"^(localhost|127\.0\.0\.1|\[::1\]|testclient|testserver)(:\d+)?$",
    re.IGNORECASE,
)

# Allowed loopback client addresses
ALLOWED_CLIENT_HOSTS = {
    "127.0.0.1",
    "::1",
    "localhost",
    "testclient",
    "testserver",
}

# Allowed CORS origins (only loopback HTTP/HTTPS)
ALLOWED_ORIGIN_REGEX = re.compile(
    r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
    re.IGNORECASE,
)

REQUEST_ID_REGEX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")

# Standard security headers
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none';"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
}


def is_valid_loopback_host(host: str | None) -> bool:
    """Checks if the Host header matches allowed local loopback identifiers."""
    if not host:
        return False
    return bool(ALLOWED_HOST_REGEX.match(host.strip()))


def is_valid_loopback_client(client_ip: str | None) -> bool:
    """Checks if the client IP is on the local loopback interface."""
    if not client_ip:
        return True  # Internal / direct test client
    return client_ip.strip() in ALLOWED_CLIENT_HOSTS


def is_allowed_origin(origin: str | None) -> bool:
    """Checks if the Origin header is an allowed local loopback origin."""
    if not origin:
        return True  # Non-browser / same-origin CLI request
    return bool(ALLOWED_ORIGIN_REGEX.match(origin.strip()))


def trusted_request_id(candidate: str | None) -> str:
    """Return a bounded safe correlation ID, replacing untrusted header values."""
    if candidate is not None and REQUEST_ID_REGEX.fullmatch(candidate) is not None:
        return candidate
    return f"req-{uuid.uuid4().hex[:12]}"


def format_error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Generates standard unified error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id or f"req-{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    }


class CSRFManager:
    """Thread-safe ephemeral Anti-CSRF token manager."""

    def __init__(self, ttl_seconds: float = 3600.0) -> None:
        self._ttl_seconds = ttl_seconds
        self._tokens: dict[str, float] = {}
        self._lock = threading.Lock()

    def generate_token(self) -> str:
        """Generates a cryptographically secure token and registers it."""
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._prune_locked(now)
            self._tokens[token] = now + self._ttl_seconds
        return token

    def validate_token(self, token: str | None) -> bool:
        """Validates that a token exists and is not expired."""
        if not token:
            return False
        now = time.monotonic()
        with self._lock:
            self._prune_locked(now)
            expires_at = self._tokens.get(token)
            if expires_at is None:
                return False
            return expires_at >= now

    def revoke_token(self, token: str) -> None:
        """Revokes an active token."""
        with self._lock:
            self._tokens.pop(token, None)

    def _prune_locked(self, now: float) -> None:
        expired = [t for t, exp in self._tokens.items() if exp < now]
        for t in expired:
            self._tokens.pop(t, None)


# Global CSRF manager singleton
csrf_manager = CSRFManager()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing Host checks, CORS, CSRF, and Security Headers."""

    # Paths exempt from CSRF token verification (e.g. bootstrap/diagnostics/public reads)
    CSRF_EXEMPT_PATHS: set[str] = {
        "/api/v1/auth/csrf",
        "/api/v1/csrf-token",
        "/api/auth/csrf",
        "/api/csrf-token",
    }

    # State-mutating HTTP methods
    MUTATING_METHODS: set[str] = {"POST", "PUT", "DELETE", "PATCH"}

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        # 1. Generate or extract Request ID
        request_id = trusted_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id

        # 2. Strict Host Header Check (DNS Rebinding Defense)
        host_header = request.headers.get("Host")
        if not is_valid_loopback_host(host_header):
            return JSONResponse(
                status_code=400,
                content=format_error_response(
                    code="INVALID_HOST",
                    message=(
                        f"Host '{host_header}' is not allowed. QuantOS binds exclusively "
                        "to local loopback (localhost, 127.0.0.1, [::1])."
                    ),
                    request_id=request_id,
                ),
                headers={"X-Request-ID": request_id, **SECURITY_HEADERS},
            )

        # 3. Client IP Verification
        client_host = request.client.host if request.client else None
        if not is_valid_loopback_client(client_host):
            return JSONResponse(
                status_code=403,
                content=format_error_response(
                    code="NON_LOOPBACK_REQUEST",
                    message="Requests from non-loopback IP addresses are forbidden.",
                    request_id=request_id,
                ),
                headers={"X-Request-ID": request_id, **SECURITY_HEADERS},
            )

        # 4. Strict CORS & Hostile Origin Check
        origin = request.headers.get("Origin")
        if origin and not is_allowed_origin(origin):
            return JSONResponse(
                status_code=403,
                content=format_error_response(
                    code="FORBIDDEN_ORIGIN",
                    message=f"Cross-origin requests from origin '{origin}' are forbidden.",
                    request_id=request_id,
                ),
                headers={"X-Request-ID": request_id, **SECURITY_HEADERS},
            )

        # 5. Handle CORS Preflight (OPTIONS)
        if request.method == "OPTIONS":
            cors_headers: dict[str, str] = {
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD",
                "Access-Control-Allow-Headers": (
                    "Content-Type, X-CSRF-Token, X-Request-ID, Idempotency-Key, Authorization"
                ),
                "Access-Control-Max-Age": "600",
                "X-Request-ID": request_id,
                **SECURITY_HEADERS,
            }
            if origin and is_allowed_origin(origin):
                cors_headers["Access-Control-Allow-Origin"] = origin
                cors_headers["Access-Control-Allow-Credentials"] = "true"
            return Response(status_code=204, headers=cors_headers)

        # 6. Anti-CSRF Token Verification for State-Mutating Endpoints
        if (
            request.method in self.MUTATING_METHODS
            and request.url.path not in self.CSRF_EXEMPT_PATHS
        ):
            csrf_token = request.headers.get("X-CSRF-Token")
            if not csrf_token:
                return JSONResponse(
                    status_code=403,
                    content=format_error_response(
                        code="CSRF_TOKEN_MISSING",
                        message="Anti-CSRF token is required in 'X-CSRF-Token' header for state-mutating requests.",
                        request_id=request_id,
                    ),
                    headers={"X-Request-ID": request_id, **SECURITY_HEADERS},
                )
            if not csrf_manager.validate_token(csrf_token):
                return JSONResponse(
                    status_code=403,
                    content=format_error_response(
                        code="CSRF_TOKEN_INVALID",
                        message="Anti-CSRF token is invalid or expired.",
                        request_id=request_id,
                    ),
                    headers={"X-Request-ID": request_id, **SECURITY_HEADERS},
                )

        # 7. Execute inner request handler
        response: Response = await call_next(request)

        # 8. Attach Security and Tracing Headers
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        response.headers["X-Request-ID"] = request_id

        if origin and is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response
