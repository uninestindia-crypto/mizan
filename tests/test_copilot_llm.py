"""The Copilot's chat transport: request shapes, error mapping, and that a key never leaks."""

from __future__ import annotations

import email.message
import http.client
import io
import json
import logging
import ssl
import urllib.error
import urllib.request
from typing import Any

import pytest

from quant_system.copilot import llm
from quant_system.copilot.llm import (
    BAD_KEY_STATUS,
    ChatReply,
    LlmConfigurationError,
    ProviderChat,
    RawResponse,
    supported_providers,
    urllib_transport,
)
from quant_system.copilot.messages import explain_failure

CANARY = "canary-value-MARKER-1234"


class _Recorder:
    """A transport that records the request it was given and answers with a canned reply."""

    def __init__(self, status: int = 200, body: Any = None, headers: dict[str, str] | None = None):
        self.status = status
        self.body = body
        self.headers = headers or {}
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> RawResponse:
        self.requests.append(request)
        raw = self.body if isinstance(self.body, bytes) else json.dumps(self.body).encode("utf-8")
        return RawResponse(self.status, raw, self.headers)

    @property
    def sent(self) -> dict[str, Any]:
        data = self.requests[-1].data
        assert isinstance(data, bytes)
        return json.loads(data.decode("utf-8"))


def _chat(provider: str, transport: llm.Transport, model: str | None = "model-x") -> ProviderChat:
    return ProviderChat(
        provider=provider,
        api_key=CANARY,
        model=model,
        transport=transport,
        resolve_model=lambda _p, _k, _prefer: "resolved-model",
    )


def test_openai_style_request_has_a_real_system_message_and_no_temperature() -> None:
    transport = _Recorder(body={"choices": [{"message": {"content": "hello"}}]})
    reply = _chat("openai", transport).complete("be careful", "what is 2+2?")
    assert reply == ChatReply(text="hello", status=200, model="model-x")
    request = transport.requests[0]
    assert request.full_url == "https://api.openai.com/v1/chat/completions"
    assert request.get_header("Authorization") == f"Bearer {CANARY}"
    body = transport.sent
    assert body["model"] == "model-x"
    assert body["messages"] == [
        {"role": "system", "content": "be careful"},
        {"role": "user", "content": "what is 2+2?"},
    ]
    assert "temperature" not in body and "response_format" not in body


@pytest.mark.parametrize("provider", ["groq", "openrouter", "deepseek", "mistral", "lightning"])
def test_the_other_openai_compatible_providers_share_that_shape(provider: str) -> None:
    transport = _Recorder(body={"choices": [{"message": {"content": "ok"}}]})
    assert _chat(provider, transport).complete("s", "u").text == "ok"
    assert [m["role"] for m in transport.sent["messages"]] == ["system", "user"]


def test_anthropic_request_uses_the_system_field_and_requires_max_tokens() -> None:
    transport = _Recorder(
        body={"content": [{"type": "text", "text": "hi "}, {"type": "text", "text": "there"}]}
    )
    reply = _chat("anthropic", transport).complete("sys", "usr", max_tokens=321)
    assert reply.text == "hi there"
    request = transport.requests[0]
    assert request.full_url == "https://api.anthropic.com/v1/messages"
    assert request.get_header("X-api-key") == CANARY
    assert request.get_header("Anthropic-version")
    assert transport.sent["system"] == "sys"
    assert transport.sent["max_tokens"] == 321
    assert transport.sent["messages"] == [{"role": "user", "content": "usr"}]


def test_gemini_sends_the_key_in_a_header_never_the_url() -> None:
    transport = _Recorder(body={"candidates": [{"content": {"parts": [{"text": "yes"}]}}]})
    reply = _chat("gemini", transport).complete("sys", "usr")
    assert reply.text == "yes"
    request = transport.requests[0]
    assert CANARY not in request.full_url
    assert request.get_header("X-goog-api-key") == CANARY
    assert "model-x:generateContent" in request.full_url
    assert transport.sent["systemInstruction"] == {"parts": [{"text": "sys"}]}


def test_a_model_is_chosen_from_the_providers_own_list_when_none_is_given() -> None:
    transport = _Recorder(body={"choices": [{"message": {"content": "ok"}}]})
    reply = _chat("openai", transport, model=None).complete("s", "u")
    assert transport.sent["model"] == "resolved-model"
    assert reply.model == "resolved-model"


def test_rate_limits_report_retry_after_and_never_echo_the_key() -> None:
    transport = _Recorder(
        status=429, body=f"quota exceeded for {CANARY}".encode(), headers={"Retry-After": "7"}
    )
    reply = _chat("openai", transport).complete("s", "u")
    assert reply.text is None and reply.status == 429 and reply.retry_after == 7.0
    assert reply.error is not None and CANARY not in reply.error
    assert "***" in reply.error


def test_an_empty_reply_is_an_error_not_an_empty_answer() -> None:
    transport = _Recorder(body={"choices": [{"message": {"content": ""}}]})
    reply = _chat("openai", transport).complete("s", "u")
    assert reply.text is None and reply.error


def test_a_model_list_failure_is_reported_without_a_secret() -> None:
    def boom(_p: str, _k: str, _prefer: tuple[str, ...]) -> str:
        raise RuntimeError(f"could not reach the list with {CANARY}")

    chat = ProviderChat(
        provider="openai",
        api_key=CANARY,
        model=None,
        transport=_Recorder(body={}),
        resolve_model=boom,
    )
    reply = chat.complete("s", "u")
    assert reply.text is None and reply.status == 503
    assert reply.error is not None and CANARY not in reply.error


def test_an_unknown_provider_is_refused_up_front() -> None:
    with pytest.raises(LlmConfigurationError):
        ProviderChat(provider="nope", api_key=CANARY, model=None)


def test_the_key_is_not_in_the_repr() -> None:
    assert CANARY not in repr(_chat("openai", _Recorder(body={})))


def test_every_catalogue_provider_is_supported() -> None:
    assert set(supported_providers()) == {
        "openai",
        "groq",
        "openrouter",
        "deepseek",
        "mistral",
        "lightning",
        "anthropic",
        "gemini",
    }


def test_an_oversized_prompt_is_refused_before_any_request() -> None:
    transport = _Recorder(body={})
    reply = _chat("openai", transport).complete("s", "x" * 200_000)
    assert reply.text is None and reply.error and not transport.requests


# ------------------------------------------------------------------------------------- a provider that fails


class _Raises:
    """A transport that raises instead of answering."""

    def __init__(self, error: BaseException) -> None:
        self.error = error
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> RawResponse:
        self.requests.append(request)
        raise self.error


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (TimeoutError("read timed out"), 408),
        (ConnectionResetError("reset by peer"), 503),
        (http.client.IncompleteRead(b"{", 900), 503),
        (ssl.SSLError("handshake failed"), 503),
        (OSError("network is unreachable"), 503),
        (RuntimeError("something nobody planned for"), 503),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, BaseException) else str(value),
)
def test_a_provider_that_stalls_or_drops_becomes_a_plain_reply_and_never_an_exception(
    error: BaseException, status: int
) -> None:
    reply = _chat("openai", _Raises(error)).complete("s", "u")
    assert reply.text is None and reply.status == status
    assert reply.error and "something nobody planned for" not in reply.error


class _Body:
    """What a provider sent back: a status, headers, and a body that may break while it is being read."""

    def __init__(self, error: BaseException | None = None, body: bytes = b"{}") -> None:
        self.status = 200
        self.headers = {"Content-Type": "application/json"}
        self._error = error
        self._body = body

    def __enter__(self) -> _Body:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        if self._error is not None:
            raise self._error
        return self._body


class _Opener:
    def __init__(self, outcome: _Body | BaseException) -> None:
        self.outcome = outcome

    def open(self, _request: urllib.request.Request, timeout: float) -> _Body:
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _sent(opener: _Opener, monkeypatch: pytest.MonkeyPatch) -> RawResponse:
    monkeypatch.setattr(llm, "_OPENER", opener)
    request = urllib.request.Request("https://provider.test/v1", data=b"{}", method="POST")
    return urllib_transport(request, 1.0)


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (TimeoutError("timed out"), 408),
        (http.client.IncompleteRead(b"{", 900), 503),
        (ConnectionResetError("reset"), 503),
        (ssl.SSLError("bad record"), 503),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, BaseException) else str(value),
)
def test_a_body_that_stalls_while_it_is_being_read_is_a_status_not_a_crash(
    error: BaseException, status: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _sent(_Opener(_Body(error)), monkeypatch).status == status


def test_a_connection_that_times_out_inside_a_url_error_is_a_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _sent(_Opener(urllib.error.URLError(TimeoutError("timed out"))), monkeypatch)
    assert raw.status == 408


def test_a_good_body_comes_back_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _sent(_Opener(_Body(body=b'{"ok": true}')), monkeypatch)
    assert raw.status == 200 and raw.body == b'{"ok": true}'


def test_an_error_page_that_stalls_is_a_status_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Stalled(io.BytesIO):
        def read(self, _size: int | None = -1) -> bytes:
            raise TimeoutError("timed out")

    error = urllib.error.HTTPError(
        "https://p.test", 500, "Server Error", email.message.Message(), _Stalled()
    )
    assert _sent(_Opener(error), monkeypatch).status == 408


class _Redirector(urllib.request.HTTPHandler):
    """A pretend provider that answers every request with a redirect to another host."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[tuple[str, str]] = []

    def http_open(self, req: urllib.request.Request) -> Any:
        self.seen.append((req.get_method(), req.full_url))
        headers = email.message.Message()
        headers["Location"] = "http://elsewhere.test/collect"
        return self.parent.error("http", req, io.BytesIO(b""), 302, "Found", headers)


def test_a_redirect_is_never_followed_so_the_key_never_travels_to_another_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("no_proxy", "*")
    redirector = _Redirector()
    monkeypatch.setattr(llm, "_OPENER", llm.build_opener(redirector))
    headers = {"Authorization": f"Bearer {CANARY}"}
    request = urllib.request.Request(
        "http://provider.test/v1", data=b"{}", headers=headers, method="POST"
    )
    raw = urllib_transport(request, 1.0)
    assert raw.status == 302 and redirector.seen == [("POST", "http://provider.test/v1")]


# ------------------------------------------------------------------------------------- a key that cannot be sent


@pytest.mark.parametrize(
    "key",
    [
        "canary-AAA\ncanary-BBB",
        "canary-AAA\r\ncanary-BBB",
        "canary-AAA\tcanary-BBB",
        "canary-AAA canary-BBB",
        "canary-AAA\x00canary-BBB",
        "canary-AAA\u2019canary-BBB",
        "canary-AAA\\canary-BBB",
        'canary-AAA"canary-BBB',
    ],
    ids=["newline", "crlf", "tab", "space", "nul", "curly-quote", "backslash", "quote"],
)
def test_a_key_with_a_space_or_line_break_is_refused_and_no_part_of_it_is_repeated(
    key: str, caplog: pytest.LogCaptureFixture
) -> None:
    transport = _Recorder(body={})
    chat = ProviderChat("openai", key, model="m", transport=transport)
    with caplog.at_level(logging.DEBUG):
        reply = chat.complete("s", "u")
    shown = f"{reply.error} {reply!r} {caplog.text}"
    assert reply.text is None and reply.status == BAD_KEY_STATUS and not transport.requests
    assert "canary-AAA" not in shown and "canary-BBB" not in shown
    assert reply.error is not None and "Settings, then Accounts and keys" in reply.error


def test_a_key_that_breaks_the_send_itself_is_still_a_plain_reply_with_no_key_in_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failure = ValueError(f"Invalid header value b'Bearer {CANARY}'")
    with caplog.at_level(logging.DEBUG):
        reply = _chat("openai", _Raises(failure)).complete("s", "u")
    assert reply.text is None and reply.status == BAD_KEY_STATUS
    assert CANARY not in f"{reply.error} {caplog.text}"


def test_no_failure_text_from_the_transport_reaches_a_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        _chat("openai", _Raises(OSError(f"refused for {CANARY}"))).complete("s", "u")
    assert CANARY not in caplog.text


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
@pytest.mark.parametrize(
    "body", [[], "text", 5, {"choices": 5}, {"content": 5}, {"candidates": 5}, {"candidates": [5]}]
)
def test_a_reply_shaped_like_nothing_we_know_is_an_error_not_a_crash(
    provider: str, body: Any
) -> None:
    reply = _chat(provider, _Recorder(body=body)).complete("s", "u")
    assert reply.text is None and reply.status == 502 and reply.error


# ------------------------------------------------------------------------------------- what a person is told


FAILURE_STATUSES = [BAD_KEY_STATUS, 401, 403, 404, 408, 413, 429, 500, 502, 503, 504]


@pytest.mark.parametrize("status", FAILURE_STATUSES)
def test_no_failure_message_uses_the_word_provider_or_a_plural_in_brackets(status: int) -> None:
    message = explain_failure(status)
    assert "provider" not in message.lower() and "(s)" not in message


@pytest.mark.parametrize("status", [BAD_KEY_STATUS, 401, 403, 404, 429, 500])
def test_a_failure_that_the_person_can_fix_names_where_to_click(status: int) -> None:
    assert "Settings, then Accounts and keys" in explain_failure(status)


@pytest.mark.parametrize(
    ("status", "sentence"),
    [
        (
            404,
            "That AI model is not available with your key. "
            "Open Settings, then Accounts and keys, and check that key.",
        ),
        (
            429,
            "That AI service is busy or you have reached its limit. Wait a minute and try again, "
            "or add a key for another AI service: open Settings, then Accounts and keys.",
        ),
        (
            500,
            "Something went wrong with the AI service. "
            "Try again, or add a key for another AI service in Settings, then Accounts and keys.",
        ),
    ],
)
def test_the_failure_messages_say_ai_service_and_name_the_next_click(
    status: int, sentence: str
) -> None:
    assert explain_failure(status) == sentence
