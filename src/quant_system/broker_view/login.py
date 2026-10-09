"""Signing in: the address to open in the person's browser, the one-time check on what comes back, and the key.

The password is typed on Upstox's own page and never reaches QuantOS. What comes back to the computer is a short,
single-use code and the random value QuantOS made for this one attempt (the ``state``). The code is swapped for a key
only if that value matches an attempt that is still open, and each attempt can be used once.
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from urllib.parse import urlencode

from quant_system.broker_view.endpoints import CALLBACK_ADDRESS, UPSTOX_AUTHORIZE_URL

LOGIN_SECONDS = 300
_MAX_KEY_CHARACTERS = 2000
_KEY_SHAPE = re.compile(
    r"[\x21-\x7e]+"
)  # visible characters only, no spaces: what the vault accepts


class LoginCheck(Enum):
    OK = "ok"
    NO_ATTEMPT = "no attempt"
    MISMATCH = "mismatch"
    EXPIRED = "expired"
    USED = "used"


@dataclass(slots=True)
class LoginAttempt:
    state: str
    expires_at: datetime
    used: bool = False


class LoginTracker:
    """The one sign-in that may be open at a time. A new attempt replaces the old one, which then stops working."""

    def __init__(self, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._clock = clock
        self._attempt: LoginAttempt | None = None

    def begin(self) -> LoginAttempt:
        self._attempt = LoginAttempt(
            state=secrets.token_urlsafe(32),
            expires_at=self._clock() + timedelta(seconds=LOGIN_SECONDS),
        )
        return self._attempt

    def cancel(self) -> None:
        self._attempt = None

    @property
    def waiting(self) -> bool:
        attempt = self._attempt
        return attempt is not None and not attempt.used and self._clock() < attempt.expires_at

    @property
    def timed_out(self) -> bool:
        attempt = self._attempt
        return attempt is not None and not attempt.used and self._clock() >= attempt.expires_at

    def check_and_consume(self, state: str | None) -> LoginCheck:
        """Whether ``state`` belongs to the open attempt. Only a match is consumed, so a stray request cannot end it."""
        attempt = self._attempt
        if attempt is None:
            return LoginCheck.NO_ATTEMPT
        if not state or not hmac.compare_digest(state.encode(), attempt.state.encode()):
            return LoginCheck.MISMATCH
        if attempt.used:
            return LoginCheck.USED
        if self._clock() >= attempt.expires_at:
            return LoginCheck.EXPIRED
        attempt.used = True
        return LoginCheck.OK


def authorize_address(client_id: str, state: str) -> str:
    """Upstox's own sign-in page, with the return address and this attempt's value. Opened by the person's browser."""
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": CALLBACK_ADDRESS,
            "state": state,
        }
    )
    return UPSTOX_AUTHORIZE_URL + "?" + query


def exchange_form(code: str, client_id: str, client_secret: str) -> dict[str, str]:
    """The five fields Upstox asks for when a sign-in code is swapped for a key, and nothing else."""
    return {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": CALLBACK_ADDRESS,
        "grant_type": "authorization_code",
    }


def read_exchange_reply(body: bytes) -> str | None:
    """The key from Upstox's reply, or None. Everything else in the reply, such as the person's name, is discarded."""
    try:
        payload = json.loads(body)
    except (ValueError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None
    key = payload.get("access_token")
    if not isinstance(key, str) or len(key) > _MAX_KEY_CHARACTERS:
        return None
    return key if _KEY_SHAPE.fullmatch(key) else None
