"""A nudge when a paper book has orders waiting: one short message to a webhook *you* configured.

Copying a paper book by hand only works if you know there is something to copy. This sends a plain
message ("2 orders to place in Momentum, decided at the close of 5 Oct 2026") to an address you set in
the environment, once per book per close. It is off unless ``QUANTOS_ORDERS_WEBHOOK_URL`` is set.

What it will not do: it never sends a quantity, a symbol or a price, only a count and a book name; it
never logs or displays the address (webhook URLs are secrets), only its host; it refuses a plain
``http`` address that is not on this machine; and it never follows a redirect, so an address cannot
bounce the message somewhere else. The message is a reminder. Nothing is placed for you.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlparse

from quant_system.market import MarketIndex
from quant_system.server.v2.paper_books import PaperBooks
from quant_system.server.v2.state import AppState

logger = logging.getLogger(__name__)

ENV_URL = "QUANTOS_ORDERS_WEBHOOK_URL"
ENV_FORMAT = "QUANTOS_ORDERS_WEBHOOK_FORMAT"
FORMATS = ("slack", "discord", "ntfy", "json")
DEFAULT_FORMAT = "slack"
POLL_SECONDS = 300.0
FIRST_LOOK_SECONDS = 45.0
SEND_TIMEOUT_SECONDS = 10.0
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class Target:
    """A validated destination. ``url`` is secret: show ``host`` only."""

    url: str
    host: str
    format: str


class NotifyConfigError(ValueError):
    """The configured address or format cannot be used, said in words that do not leak the address."""


def target_from_environment(environ: Mapping[str, str]) -> Target | None:
    """The configured destination, None when unset, or NotifyConfigError when it is unusable."""
    raw = environ.get(ENV_URL, "").strip()
    if not raw:
        return None
    fmt = environ.get(ENV_FORMAT, DEFAULT_FORMAT).strip().lower() or DEFAULT_FORMAT
    if fmt not in FORMATS:
        raise NotifyConfigError(f"{ENV_FORMAT} must be one of {', '.join(FORMATS)}.")
    parsed = urlparse(raw)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise NotifyConfigError(f"{ENV_URL} must be a web address that starts with https://.")
    if parsed.scheme == "http" and parsed.hostname not in _LOCAL_HOSTS:
        raise NotifyConfigError(
            f"{ENV_URL} must use https:// unless it points at this computer, so the message is "
            "not sent in the clear."
        )
    return Target(url=raw, host=parsed.hostname, format=fmt)


def build_message(books: list[dict[str, Any]]) -> str:
    """One line per book: a count and a name. Never a symbol, quantity or price."""
    lines = []
    for book in books:
        n = int(book["pending"])
        decided = date.fromisoformat(str(book["as_of"])[:10])
        lines.append(
            f"{n} order{'s' if n != 1 else ''} to place in {book['name']} "
            f"(decided at the close of {decided.day} {decided:%b} {decided.year})."
        )
    return "QuantOS: " + " ".join(lines) + " Open QuantOS to see them. Nothing is placed for you."


def encode(fmt: str, text: str, pending: int) -> tuple[bytes, str]:
    if fmt == "ntfy":
        return text.encode("utf-8"), "text/plain; charset=utf-8"
    body: dict[str, Any]
    if fmt == "discord":
        body = {"content": text}
    elif fmt == "json":
        body = {"text": text, "source": "quantos", "pending": pending}
    else:
        body = {"text": text}
    return json.dumps(body).encode("utf-8"), "application/json"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def post(target: Target, body: bytes, content_type: str) -> None:
    """Send one message. Raises on any failure; the caller decides to retry."""
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(
        target.url, data=body, headers={"Content-Type": content_type}, method="POST"
    )
    try:
        with opener.open(request, timeout=SEND_TIMEOUT_SECONDS) as response:
            if not 200 <= response.status < 300:
                raise OSError(f"{target.host} answered HTTP {response.status}")
    except urllib.error.HTTPError as err:
        raise OSError(f"{target.host} answered HTTP {err.code}") from None
    except urllib.error.URLError as err:
        raise OSError(f"could not reach {target.host}: {err.reason}") from None


Sender = Callable[[Target, bytes, str], None]


class OrdersNotifier:
    def __init__(
        self,
        state: AppState,
        paper: PaperBooks,
        index: MarketIndex,
        *,
        sender: Sender = post,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._state = state
        self._paper = paper
        self._index = index
        self._sender = sender
        self._environ = environ if environ is not None else os.environ
        self._lock = threading.Lock()
        self._last_error: str | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def settings(self) -> dict[str, Any]:
        """What the Settings page shows. Never the address itself."""
        try:
            target = target_from_environment(self._environ)
        except NotifyConfigError as err:
            return {"enabled": False, "host": None, "problem": str(err), "last_error": None}
        return {
            "enabled": target is not None,
            "host": target.host if target else None,
            "problem": None,
            "last_error": self._last_error,
        }

    def tick(self) -> int:
        """Look once and send at most one message. Returns how many books it announced."""
        try:
            target = target_from_environment(self._environ)
        except NotifyConfigError:
            return 0
        if target is None or not self._index.is_ready():
            return 0
        with self._lock:
            waiting = [
                b
                for b in self._paper.inbox(self._index)["books"]
                if b["state"] == "CURRENT"
                and b["pending"] > 0
                and not self._state.orders_notified(str(b["id"]), str(b["as_of"]))
            ]
            if not waiting:
                return 0
            body, content_type = encode(
                target.format, build_message(waiting), sum(int(b["pending"]) for b in waiting)
            )
            try:
                self._sender(target, body, content_type)
            except OSError as err:
                self._last_error = str(err)
                logger.warning("Orders reminder not sent: %s", err)
                return 0
            self._last_error = None
            for b in waiting:
                self._state.mark_orders_notified(str(b["id"]), str(b["as_of"]))
            return len(waiting)

    # ---------------------------------------------------------------------------- worker

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="orders-reminder", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)

    def _loop(self) -> None:
        wait = FIRST_LOOK_SECONDS
        while not self._stop.wait(wait):
            wait = POLL_SECONDS
            try:
                self.tick()
            except Exception:  # a reminder must never take the app down
                logger.exception("Orders reminder check failed")
