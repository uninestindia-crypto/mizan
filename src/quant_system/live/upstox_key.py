"""Which Upstox key to use, and whether it has already run out.

The key is a signed token that carries its own expiry time. Reading that time needs no network and no
signature check: a key that says it expired is not worth sending. Anything that does not look like
that is simply tried, because Upstox is the one that knows whether a key is good.

This module never stores, prints or returns the key in a message.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime

from quant_system.live import messages

#: In order of preference. The analytics key lasts about a year; the access key expires at 03:30 India
#: time the morning after it is issued. The pilot and the data client prefer them in the same order.
PREFERRED_SOURCES = ("UPSTOX_ANALYTICS_TOKEN", "UPSTOX_ACCESS_TOKEN")
_JWT_PARTS = 3


def pick_key(read: Callable[[str], str | None], now: datetime | None = None) -> str:
    """The first key that can be used right now, asking `read` for each source in order of preference.

    A key that says it has expired is passed over when a later one is still good. When none is usable the first
    key that was given is returned, so the reason it cannot be used is the one that gets told.
    """
    moment = now or datetime.now(UTC)
    given = [value for name in PREFERRED_SOURCES if (value := (read(name) or "").strip())]
    usable = [key for key in given if key_problem(key, moment) is None]
    return (usable or given or [""])[0]


def key_expiry(key: str) -> datetime | None:
    """When the key says it expires, or None when it does not say (or is not that kind of key)."""
    parts = key.split(".")
    if len(parts) != _JWT_PARTS:
        return None
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(padded))
        expires = claims["exp"]
        if isinstance(expires, bool):
            return None
        return datetime.fromtimestamp(int(expires), UTC)
    except (ValueError, KeyError, TypeError, OverflowError, OSError):
        return None


def key_problem(key: str, now: datetime) -> str | None:
    """A plain-language reason this key cannot be used right now, or None when it can be tried."""
    if not key:
        return messages.NO_KEY
    expires = key_expiry(key)
    if expires is not None and expires <= now:
        return messages.KEY_EXPIRED
    return None
