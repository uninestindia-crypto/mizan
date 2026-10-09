"""The small, short-lived listener that catches the person's browser coming back from Upstox's sign-in page.

It lives only while a sign-in is open, listens on this computer alone (127.0.0.1), answers one address and nothing
else, and writes nothing to any log, because the request line it receives holds the single-use sign-in code. The page
it shows never repeats anything it was sent.
"""

from __future__ import annotations

import socket
import sys
import threading
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import TCPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from quant_system.broker_view import messages
from quant_system.broker_view.endpoints import CALLBACK_HOST, CALLBACK_PATH, CALLBACK_PORT
from quant_system.broker_view.login import LOGIN_SECONDS

CONNECTED = "connected"
FAILED = "failed"
IGNORED = "ignored"
_MAX_PARAMETERS = 20
_MAX_VALUE_CHARACTERS = 2000
_REQUEST_SECONDS = 5


def _page(message: str) -> bytes:
    body = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>QuantOS</title></head>'
        f"<body><p>{message}</p></body></html>"
    )
    return body.encode("utf-8")


PAGES: dict[str, bytes] = {
    CONNECTED: _page(
        "QuantOS is connected to your Upstox account (view only). You can close this tab."
    ),
    FAILED: _page("QuantOS could not finish connecting. Go back to QuantOS to see why."),
    IGNORED: _page(messages.STATE_MISMATCH),
}
NOT_FOUND = _page("Nothing here.")
NOT_ALLOWED = _page("Not allowed.")


class PortBusy(OSError):
    """Something else on this computer is already using the sign-in return address."""


class _Server(HTTPServer):
    allow_reuse_address = False

    def server_bind(self) -> None:
        if sys.platform == "win32":
            # Without this, another program on this computer could bind the same port and catch the code.
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        TCPServer.server_bind(
            self
        )  # not HTTPServer's: it looks up this computer's name, which can be slow
        self.server_name = CALLBACK_HOST
        self.server_port = self.socket.getsockname()[1]


def first_values(query: str) -> dict[str, str]:
    """The first value of each field in a query, with the number and size of fields limited."""
    try:
        parsed = parse_qs(query, max_num_fields=_MAX_PARAMETERS)
    except ValueError:
        return {}
    return {name: values[0][:_MAX_VALUE_CHARACTERS] for name, values in parsed.items() if values}


class CallbackListener:
    def __init__(
        self,
        on_callback: Callable[[Mapping[str, str]], str],
        *,
        host: str = CALLBACK_HOST,
        port: int = CALLBACK_PORT,
        path: str = CALLBACK_PATH,
        timeout_seconds: float = LOGIN_SECONDS,
    ) -> None:
        self._on_callback = on_callback
        self._host, self._port, self._path = host, port, path
        self._timeout = timeout_seconds
        self._server: _Server | None = None
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    @property
    def port(self) -> int:
        server = self._server
        return int(server.server_address[1]) if server is not None else self._port

    def start(self) -> None:
        listener = self

        class Handler(BaseHTTPRequestHandler):
            timeout = _REQUEST_SECONDS
            server_version = "QuantOS"
            sys_version = ""

            def log_message(self, format: str, *args: Any) -> None:
                return None  # the request line holds the sign-in code

            def _send(self, status: int, body: bytes) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Connection", "close")
                if status == 405:
                    self.send_header("Allow", "GET")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                parts = urlsplit(self.path)
                if parts.path != listener._path:
                    self._send(404, NOT_FOUND)
                    return
                try:
                    outcome = listener._on_callback(first_values(parts.query))
                except Exception:
                    outcome = FAILED
                self._send(200, PAGES.get(outcome, PAGES[FAILED]))
                if outcome != IGNORED:
                    # shutdown() waits for this very loop to end, so it has to be asked from another thread
                    threading.Thread(target=listener.stop, daemon=True).start()

            def _refuse(self) -> None:
                self._send(405, NOT_ALLOWED)

            do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _refuse

        with self._lock:
            if self._server is not None:
                return
            try:
                server = _Server((self._host, self._port), Handler)
            except OSError as error:
                raise PortBusy("the sign-in return address is in use") from error
            self._server = server
            threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True
            ).start()
            self._timer = threading.Timer(self._timeout, self.stop)
            self._timer.daemon = True
            self._timer.start()

    def stop(self) -> None:
        with self._lock:
            server, timer = self._server, self._timer
            self._server = self._timer = None
        if timer is not None:
            timer.cancel()
        if server is not None:
            server.shutdown()
            server.server_close()
