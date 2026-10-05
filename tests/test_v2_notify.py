"""The orders reminder: a nudge to a webhook you configured, and nothing else.

It carries money-adjacent information off the machine, so the tests pin what it must never do: leak
the address, send over plain http, follow a redirect, say what to buy, repeat itself, or send when
there is nothing to place.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from quant_system.server.v2 import notify
from quant_system.server.v2.notify import (
    ENV_FORMAT,
    ENV_URL,
    NotifyConfigError,
    OrdersNotifier,
    Target,
    build_message,
    encode,
    target_from_environment,
)
from quant_system.server.v2.state import AppState

SECRET_URL = "https://hooks.example.com/services/T000/B000/s3cr3t-token"


# ---------------------------------------------------------------------------- configuration


def test_it_is_off_unless_an_address_is_set() -> None:
    assert target_from_environment({}) is None
    assert target_from_environment({ENV_URL: "   "}) is None


def test_an_https_address_is_accepted_and_only_its_host_is_exposed() -> None:
    target = target_from_environment({ENV_URL: SECRET_URL})
    assert target is not None and target.host == "hooks.example.com" and target.format == "slack"


@pytest.mark.parametrize("fmt", ["slack", "discord", "ntfy", "json", "NTFY"])
def test_every_documented_format_is_accepted(fmt: str) -> None:
    target = target_from_environment({ENV_URL: SECRET_URL, ENV_FORMAT: fmt})
    assert target is not None and target.format == fmt.lower()


def test_an_unknown_format_is_refused() -> None:
    with pytest.raises(NotifyConfigError, match="must be one of"):
        target_from_environment({ENV_URL: SECRET_URL, ENV_FORMAT: "carrier-pigeon"})


@pytest.mark.parametrize(
    "bad", ["not a url", "ftp://example.com/x", "https://", "javascript:alert(1)"]
)
def test_something_that_is_not_a_web_address_is_refused(bad: str) -> None:
    with pytest.raises(NotifyConfigError):
        target_from_environment({ENV_URL: bad})


def test_plain_http_is_refused_unless_it_points_at_this_computer() -> None:
    with pytest.raises(NotifyConfigError, match="https://"):
        target_from_environment({ENV_URL: "http://hooks.example.com/x"})
    for local in ("http://localhost:8080/topic", "http://127.0.0.1/topic"):
        assert target_from_environment({ENV_URL: local}) is not None


def test_a_configuration_error_never_contains_the_address() -> None:
    for bad in ("http://hooks.example.com/services/s3cr3t-token", "ftp://x/s3cr3t-token"):
        with pytest.raises(NotifyConfigError) as err:
            target_from_environment({ENV_URL: bad})
        assert "s3cr3t" not in str(err.value)


# ------------------------------------------------------------------------------- the message


BOOKS = [
    {"id": "b1", "name": "Momentum on three stocks", "as_of": "2026-10-05", "pending": 2},
    {"id": "b2", "name": "XS monthly", "as_of": "2026-10-05", "pending": 1},
]


def test_the_message_says_how_many_and_where_and_nothing_to_buy() -> None:
    text = build_message(BOOKS)
    assert "2 orders to place in Momentum on three stocks" in text
    assert "1 order to place in XS monthly" in text
    assert "5 Oct 2026" in text and "Nothing is placed for you" in text


def test_the_message_is_built_from_counts_and_names_alone() -> None:
    """A symbol, quantity or price in the input must never reach the output."""
    leaky = [{**BOOKS[0], "orders": [{"symbol": "TCS", "quantity": 64, "reference_price": 4210.5}]}]
    text = build_message(leaky)
    assert "TCS" not in text and "64" not in text and "4210" not in text


@pytest.mark.parametrize(
    ("fmt", "key"), [("slack", "text"), ("discord", "content"), ("json", "text")]
)
def test_json_formats_carry_the_text_under_the_key_each_service_reads(fmt: str, key: str) -> None:
    body, content_type = encode(fmt, "hello", 3)
    assert content_type == "application/json" and json.loads(body)[key] == "hello"


def test_ntfy_gets_plain_text() -> None:
    body, content_type = encode("ntfy", "hello", 3)
    assert body == b"hello" and content_type.startswith("text/plain")


def test_the_generic_json_format_also_carries_the_count() -> None:
    assert json.loads(encode("json", "hello", 3)[0])["pending"] == 3


# ------------------------------------------------------------------------------- the notifier


class FakePaper:
    def __init__(self, books: list[dict[str, Any]]) -> None:
        self.books = books

    def inbox(self, index: object) -> dict[str, Any]:
        return {"books": self.books, "pending": sum(b["pending"] for b in self.books)}


class FakeIndex:
    ready = True

    def is_ready(self) -> bool:
        return self.ready


def _book(
    id_: str = "b1", as_of: str = "2026-10-05", pending: int = 2, state: str = "CURRENT"
) -> dict[str, Any]:
    return {"id": id_, "name": f"Book {id_}", "as_of": as_of, "pending": pending, "state": state}


class Rig:
    def __init__(
        self, tmp_path: Path, books: list[dict[str, Any]], env: dict[str, str] | None = None
    ) -> None:
        self.sent: list[tuple[Target, bytes, str]] = []
        self.fail: OSError | None = None
        self.paper = FakePaper(books)
        self.index = FakeIndex()
        self.state = AppState(tmp_path / "app.sqlite")
        self.notifier = OrdersNotifier(
            self.state,
            self.paper,  # type: ignore[arg-type]
            self.index,  # type: ignore[arg-type]
            sender=self._send,
            environ={ENV_URL: SECRET_URL} if env is None else env,
        )

    def _send(self, target: Target, body: bytes, content_type: str) -> None:
        if self.fail:
            raise self.fail
        self.sent.append((target, body, content_type))


def test_nothing_is_sent_when_it_is_switched_off(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book()], env={})
    assert rig.notifier.tick() == 0 and rig.sent == []
    assert rig.notifier.settings()["enabled"] is False


def test_one_message_is_sent_when_orders_are_waiting(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book("b1", pending=2), _book("b2", pending=1)])
    assert rig.notifier.tick() == 2
    [(target, body, _)] = rig.sent
    assert target.host == "hooks.example.com"
    text = json.loads(body)["text"]
    assert "Book b1" in text and "Book b2" in text


def test_the_same_close_is_announced_once(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book()])
    assert rig.notifier.tick() == 1
    assert rig.notifier.tick() == 0
    assert len(rig.sent) == 1


def test_a_new_close_is_announced_again(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book(as_of="2026-10-05")])
    rig.notifier.tick()
    rig.paper.books = [_book(as_of="2026-10-06")]
    assert rig.notifier.tick() == 1 and len(rig.sent) == 2


def test_the_record_of_what_was_announced_survives_a_restart(tmp_path: Path) -> None:
    Rig(tmp_path, [_book()]).notifier.tick()
    again = Rig(tmp_path, [_book()])
    assert again.notifier.tick() == 0 and again.sent == []


def test_out_of_date_orders_are_never_announced(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book(state="STALE")])
    assert rig.notifier.tick() == 0 and rig.sent == []


def test_nothing_to_place_means_no_message(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book(pending=0)])
    assert rig.notifier.tick() == 0 and rig.sent == []


def test_nothing_is_sent_before_the_market_index_is_ready(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book()])
    rig.index.ready = False
    assert rig.notifier.tick() == 0 and rig.sent == []


def test_a_failed_send_is_retried_and_does_not_mark_the_close_as_announced(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book()])
    rig.fail = OSError("could not reach hooks.example.com: timed out")
    assert rig.notifier.tick() == 0
    assert "could not reach" in (rig.notifier.settings()["last_error"] or "")
    rig.fail = None
    assert rig.notifier.tick() == 1
    assert rig.notifier.settings()["last_error"] is None


def test_settings_never_expose_the_address(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book()])
    shown = json.dumps(rig.notifier.settings())
    assert "s3cr3t" not in shown and "hooks.example.com" in shown


def test_a_misconfigured_address_is_reported_in_words_and_sends_nothing(tmp_path: Path) -> None:
    rig = Rig(tmp_path, [_book()], env={ENV_URL: "http://hooks.example.com/s3cr3t"})
    settings = rig.notifier.settings()
    assert settings["enabled"] is False and "https://" in settings["problem"]
    assert "s3cr3t" not in json.dumps(settings)
    assert rig.notifier.tick() == 0 and rig.sent == []


# --------------------------------------------------------------------- the real HTTP sender


class _Recorder(BaseHTTPRequestHandler):
    received: list[tuple[str, bytes]] = []
    mode = "ok"

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        type(self).received.append((self.path, body))
        if type(self).mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.end_headers()
        elif type(self).mode == "error":
            self.send_response(500)
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()

    def log_message(self, *args: object) -> None:  # keep the test output quiet
        pass


@pytest.fixture()
def local_server() -> Any:
    _Recorder.received = []
    _Recorder.mode = "ok"
    server = HTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/topic"
    server.shutdown()


def test_the_real_sender_posts_the_message_body(local_server: str) -> None:
    target = Target(url=local_server, host="127.0.0.1", format="ntfy")
    notify.post(target, b"hello", "text/plain")
    assert _Recorder.received == [("/topic", b"hello")]


def test_the_real_sender_does_not_follow_a_redirect(local_server: str) -> None:
    _Recorder.mode = "redirect"
    target = Target(url=local_server, host="127.0.0.1", format="ntfy")
    with pytest.raises(OSError, match="HTTP 302"):
        notify.post(target, b"hello", "text/plain")


def test_the_real_sender_reports_a_server_error_without_the_address(local_server: str) -> None:
    _Recorder.mode = "error"
    target = Target(url=local_server + "/s3cr3t", host="127.0.0.1", format="ntfy")
    with pytest.raises(OSError) as err:
        notify.post(target, b"hello", "text/plain")
    assert "HTTP 500" in str(err.value) and "s3cr3t" not in str(err.value)


def test_the_real_sender_reports_an_unreachable_host_without_the_address() -> None:
    target = Target(url="http://127.0.0.1:1/s3cr3t", host="127.0.0.1", format="ntfy")
    with pytest.raises(OSError) as err:
        notify.post(target, b"hello", "text/plain")
    assert "could not reach 127.0.0.1" in str(err.value) and "s3cr3t" not in str(err.value)
