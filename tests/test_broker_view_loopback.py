"""The sign-in return listener: this computer only, one address, no log, no echo, and it closes when it is done."""

from __future__ import annotations

import http.client
import socket
import threading
import time
from collections.abc import Callable, Iterator, Mapping

import pytest

from quant_system.broker_view import messages
from quant_system.broker_view.endpoints import CALLBACK_HOST, CALLBACK_PATH
from quant_system.broker_view.loopback import (
    CONNECTED,
    FAILED,
    IGNORED,
    PAGES,
    CallbackListener,
    PortBusy,
    first_values,
)


class Recorder:
    def __init__(self, outcome: str = CONNECTED) -> None:
        self.outcome = outcome
        self.seen: list[Mapping[str, str]] = []

    def __call__(self, params: Mapping[str, str]) -> str:
        self.seen.append(dict(params))
        return self.outcome


def listening(recorder: Callable[[Mapping[str, str]], str], **kwargs: float) -> CallbackListener:
    listener = CallbackListener(recorder, port=0, **kwargs)
    listener.start()
    return listener


@pytest.fixture
def started() -> Iterator[Callable[..., CallbackListener]]:
    made: list[CallbackListener] = []

    def make(recorder: Callable[[Mapping[str, str]], str], **kwargs: float) -> CallbackListener:
        listener = listening(recorder, **kwargs)
        made.append(listener)
        return listener

    yield make
    for listener in made:
        listener.stop()


def request(
    listener: CallbackListener, method: str, target: str
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection(CALLBACK_HOST, listener.port, timeout=5)
    try:
        connection.request(method, target)
        response = connection.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    finally:
        connection.close()


def refused(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex((CALLBACK_HOST, port)) != 0


def wait_until_closed(port: int) -> bool:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if refused(port):
            return True
        time.sleep(0.05)
    return False


def test_it_listens_on_this_computer_only(started: Callable[..., CallbackListener]) -> None:
    listener = started(Recorder())
    assert listener._server is not None
    assert listener._server.server_address[0] == CALLBACK_HOST


def test_the_return_address_gets_the_fields_and_a_page_that_repeats_none_of_them(
    started: Callable[..., CallbackListener],
) -> None:
    recorder = Recorder(CONNECTED)
    listener = started(recorder)
    status, headers, body = request(
        listener, "GET", f"{CALLBACK_PATH}?code=SECRETCODE&state=SECRETSTATE"
    )
    assert status == 200 and recorder.seen == [{"code": "SECRETCODE", "state": "SECRETSTATE"}]
    assert body == PAGES[CONNECTED]
    assert b"SECRETCODE" not in body and b"SECRETSTATE" not in body
    assert headers["cache-control"] == "no-store"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["content-security-policy"] == "default-src 'none'"


def test_any_other_address_is_not_found_and_does_not_reach_the_service(
    started: Callable[..., CallbackListener],
) -> None:
    recorder = Recorder()
    listener = started(recorder)
    for target in ("/", "/upstox", "/upstox/callback/extra", "/etc/passwd?code=x&state=y"):
        assert request(listener, "GET", target)[0] == 404
    assert recorder.seen == []


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
def test_any_other_kind_of_request_is_not_allowed(
    started: Callable[..., CallbackListener], method: str
) -> None:
    recorder = Recorder()
    listener = started(recorder)
    status, headers, _ = request(listener, method, f"{CALLBACK_PATH}?code=x&state=y")
    assert status == 405 and headers["allow"] == "GET" and recorder.seen == []


def test_it_writes_nothing_anywhere_because_the_request_line_holds_the_code(
    started: Callable[..., CallbackListener], capsys: pytest.CaptureFixture[str]
) -> None:
    listener = started(
        Recorder(IGNORED)
    )  # an ignored return leaves the listener open for a second request
    request(listener, "GET", f"{CALLBACK_PATH}?code=SECRETCODE&state=SECRETSTATE")
    request(listener, "GET", "/nothing")
    captured = capsys.readouterr()
    assert captured.err == "" and captured.out == ""


def test_it_closes_after_the_first_return_that_belongs_to_a_sign_in(
    started: Callable[..., CallbackListener],
) -> None:
    listener = started(Recorder(CONNECTED))
    port = listener.port
    request(listener, "GET", f"{CALLBACK_PATH}?code=a&state=b")
    assert wait_until_closed(port)


def test_it_closes_after_a_failed_return_too(started: Callable[..., CallbackListener]) -> None:
    listener = started(Recorder(FAILED))
    port = listener.port
    assert request(listener, "GET", f"{CALLBACK_PATH}?error=access_denied&state=b")[0] == 200
    assert wait_until_closed(port)


def test_a_stray_return_is_ignored_and_the_listener_stays_open_for_the_real_one(
    started: Callable[..., CallbackListener],
) -> None:
    recorder = Recorder(IGNORED)
    listener = started(recorder)
    _, _, body = request(listener, "GET", f"{CALLBACK_PATH}?code=a&state=wrong")
    assert body == PAGES[IGNORED] and messages.STATE_MISMATCH.encode() in body
    recorder.outcome = CONNECTED
    assert request(listener, "GET", f"{CALLBACK_PATH}?code=a&state=right")[0] == 200
    assert len(recorder.seen) == 2


def test_a_service_that_fails_shows_the_failed_page_not_a_stack_trace(
    started: Callable[..., CallbackListener],
) -> None:
    def explodes(_: Mapping[str, str]) -> str:
        raise RuntimeError("secret detail")

    listener = started(explodes)
    status, _, body = request(listener, "GET", f"{CALLBACK_PATH}?code=a&state=b")
    assert status == 200 and body == PAGES[FAILED] and b"secret detail" not in body


def test_it_closes_by_itself_when_nobody_comes_back(
    started: Callable[..., CallbackListener],
) -> None:
    listener = started(Recorder(), timeout_seconds=0.2)
    assert wait_until_closed(listener.port)


def test_stopping_twice_is_harmless_and_frees_the_address(
    started: Callable[..., CallbackListener],
) -> None:
    listener = started(Recorder())
    port = listener.port
    listener.stop()
    listener.stop()
    assert wait_until_closed(port)


def test_an_address_already_in_use_is_reported_as_busy() -> None:
    with socket.socket() as taken:
        taken.bind((CALLBACK_HOST, 0))
        taken.listen()
        listener = CallbackListener(Recorder(), port=taken.getsockname()[1])
        with pytest.raises(PortBusy):
            listener.start()


def test_a_listener_can_be_started_in_several_threads_without_two_servers() -> None:
    listener = CallbackListener(Recorder(), port=0)
    threads = [threading.Thread(target=listener.start) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    try:
        assert listener._server is not None
    finally:
        listener.stop()


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("code=a&state=b", {"code": "a", "state": "b"}),
        ("code=a&code=b", {"code": "a"}),
        ("", {}),
        ("&".join(f"k{i}=v" for i in range(30)), {}),
        ("code=" + "x" * 5000, {"code": "x" * 2000}),
    ],
)
def test_the_query_is_read_with_limits(query: str, expected: dict[str, str]) -> None:
    assert first_values(query) == expected
