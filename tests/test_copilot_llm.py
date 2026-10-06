"""The Copilot's chat transport: request shapes, error mapping, and that a key never leaks."""

from __future__ import annotations

import json
import urllib.request
from typing import Any

import pytest

from quant_system.copilot.llm import (
    ChatReply,
    LlmConfigurationError,
    ProviderChat,
    RawResponse,
    supported_providers,
)

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


def _chat(provider: str, transport: _Recorder, model: str | None = "model-x") -> ProviderChat:
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
