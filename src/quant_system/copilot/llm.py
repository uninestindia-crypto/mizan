"""One chat call, any of eight providers: a system prompt plus a user message in, text out.

``alpha/direct_providers.py`` serves the advisory panel: it pins a system prompt per provider, a five
second timeout and a short output. An agent needs a real system/user split and a longer wait, so this
module has its own thin transport and reuses what is genuinely shared: each provider's endpoint and the
live model choice (:mod:`quant_system.alpha.model_catalog`), so no model name is pinned in code.

Three wire shapes cover all eight providers (OpenAI-style, Anthropic, Gemini). No sampling temperature
is sent: some reasoning models refuse anything but their default, and a refusal costs a call.

A key is held in a field excluded from ``repr`` and is stripped from every error text before it can leave
this module. A key that cannot be sent as it is (a space or line break inside it) is refused before any request is
built, and a chat call never follows a redirect, so the key is sent to the provider's own address only.

``ProviderChat.complete`` never raises: a provider that stalls, drops the connection or sends half a reply is a
status and a plain sentence, so the Copilot always has something to say.
"""

from __future__ import annotations

import http.client
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Final, Protocol

from quant_system.alpha.direct_providers import (
    AnthropicClient,
    DeepSeekClient,
    GeminiClient,
    GroqClient,
    LightningClient,
    MistralClient,
    OpenAIClient,
    OpenRouterClient,
)
from quant_system.alpha.model_catalog import latest_model_id

__all__ = [
    "BAD_KEY_MESSAGE",
    "BAD_KEY_STATUS",
    "ChatModel",
    "ChatReply",
    "LlmConfigurationError",
    "ProviderChat",
    "RawResponse",
    "supported_providers",
]

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS: Final = 120_000
MAX_RESPONSE_BYTES: Final = 2_000_000
_ERROR_CHARS: Final = 300
# Never sent or received: the status of a reply made here when the saved key could not be sent as it is.
BAD_KEY_STATUS: Final = 499
BAD_KEY_MESSAGE: Final = (
    "That AI key has a space, line break or unusual character in it. "
    "Open Settings, then Accounts and keys, and paste it again."
)

# provider -> (wire style, endpoint, model-preference hints), read from the existing clients.
_PROVIDERS: Final[dict[str, tuple[str, str, tuple[str, ...]]]] = {
    "openai": ("openai", OpenAIClient.ENDPOINT, OpenAIClient.PREFER),
    "groq": ("openai", GroqClient.ENDPOINT, GroqClient.PREFER),
    "openrouter": ("openai", OpenRouterClient.ENDPOINT, OpenRouterClient.PREFER),
    "deepseek": ("openai", DeepSeekClient.ENDPOINT, DeepSeekClient.PREFER),
    "mistral": ("openai", MistralClient.ENDPOINT, MistralClient.PREFER),
    "lightning": ("openai", LightningClient.ENDPOINT, LightningClient.PREFER),
    "anthropic": ("anthropic", AnthropicClient.ENDPOINT, AnthropicClient.PREFER),
    "gemini": ("gemini", GeminiClient.ENDPOINT, GeminiClient.PREFER),
}


class LlmConfigurationError(ValueError):
    """The provider is not one this transport can talk to."""


def supported_providers() -> tuple[str, ...]:
    return tuple(_PROVIDERS)


@dataclass(frozen=True, slots=True)
class RawResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ChatReply:
    """``text`` is None whenever ``error`` is set. ``model`` is the model that was actually asked."""

    text: str | None
    status: int
    error: str | None = None
    retry_after: float | None = None
    model: str | None = None


class ChatModel(Protocol):
    """What the agent, the verifier and the news reader need from a model. Tests substitute a fake."""

    provider: str
    model: str | None

    def complete(
        self, system: str, user: str, *, max_tokens: int = 900, timeout: float = 60.0
    ) -> ChatReply: ...


Transport = Callable[[urllib.request.Request, float], RawResponse]
ModelResolver = Callable[[str, str, tuple[str, ...]], str]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A provider never needs to send the call somewhere else, and a redirect would carry the key along."""

    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def build_opener(*extra: urllib.request.BaseHandler) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect, *extra)


_OPENER = build_opener()


def _read_error_body(error: urllib.error.HTTPError) -> bytes:
    return error.read(MAX_RESPONSE_BYTES) if error.fp else b""


def _send(request: urllib.request.Request, timeout: float) -> RawResponse:
    try:
        response = _OPENER.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        return RawResponse(error.code, _read_error_body(error), dict(error.headers or {}))
    with response:
        return RawResponse(
            response.status, response.read(MAX_RESPONSE_BYTES), dict(response.headers)
        )


def urllib_transport(request: urllib.request.Request, timeout: float) -> RawResponse:
    """One call to a provider. Whatever goes wrong on the way is a status, never an exception."""
    try:
        return _send(request, timeout)
    except TimeoutError:
        return RawResponse(408, b"", {})
    except urllib.error.URLError as error:
        status = 408 if isinstance(error.reason, TimeoutError) else 503
        return RawResponse(status, str(error.reason).encode("utf-8", "replace"), {})
    except (OSError, http.client.HTTPException):
        return RawResponse(503, b"", {})


def _sendable(key: str) -> bool:
    """A key goes into a header as it is, so it must be one run of plain visible characters.

    Quotes and backslashes are refused too: no real key has one, and with none the key reads the same however an
    error message writes it down, so stripping it from that message is complete.
    """
    plain = key.isascii() and key.isprintable() and not any(ch.isspace() for ch in key)
    return plain and not any(ch in "\\'\"" for ch in key)


def _default_resolver(provider: str, api_key: str, prefer: tuple[str, ...]) -> str:
    return latest_model_id(provider, api_key, prefer=prefer)


# The thinking levels each wire style takes. A level outside its list is not sent at all.
_LEVELS: Final[dict[str, tuple[str, ...]]] = {
    "anthropic": ("low", "medium", "high", "xhigh", "max"),
    "openai": ("low", "medium", "high", "xhigh"),
    "groq": ("low", "medium", "high"),
    "openrouter": ("low", "medium", "high"),
    "gemini": ("low", "medium", "high"),
}
# Thinking is paid for out of the same allowance as the answer, so a chosen level needs room beyond the usual 900.
_THINKING_MIN_TOKENS: Final = 8000


def _level_for(provider: str, level: str | None) -> str | None:
    """The thinking level to send to this provider, or ``None`` when it takes none or none was chosen."""
    return level if level and level in _LEVELS.get(provider, ()) else None


@dataclass(slots=True)
class ProviderChat:
    provider: str
    api_key: str = field(repr=False)
    model: str | None = None
    transport: Transport = urllib_transport
    resolve_model: ModelResolver = _default_resolver
    thinking: str | None = None  # a level the person chose; sent only to a provider that takes one

    def __post_init__(self) -> None:
        if self.provider not in _PROVIDERS:
            raise LlmConfigurationError(f"{self.provider} is not an AI provider QuantOS supports.")

    def complete(
        self, system: str, user: str, *, max_tokens: int = 900, timeout: float = 60.0
    ) -> ChatReply:
        if len(system) + len(user) > MAX_PROMPT_CHARS:
            return ChatReply(None, 413, "The question is too long to send to a model.")
        if not _sendable(self.api_key):
            return ChatReply(None, BAD_KEY_STATUS, BAD_KEY_MESSAGE)
        style, endpoint, prefer = _PROVIDERS[self.provider]
        try:
            model = self.model or self.resolve_model(self.provider, self.api_key, prefer)
        except Exception as error:  # a catalogue failure is a plain reason, never a stack trace
            return ChatReply(None, 503, f"Could not choose a model: {self._clean(str(error))}")
        level = _level_for(self.provider, self.thinking)
        tokens = max(max_tokens, _THINKING_MIN_TOKENS) if level else max_tokens
        raw = self._call(
            self._request(style, endpoint, model, system, user, tokens, level), timeout
        )
        if level and isinstance(raw, RawResponse) and raw.status == 400:
            # This model does not take that setting. It is asked once more without it, so a question still gets an
            # answer; the setting is the person's wish, not a reason to leave them without one.
            raw = self._call(
                self._request(style, endpoint, model, system, user, max_tokens, None), timeout
            )
        if isinstance(raw, ChatReply):
            return replace(raw, model=model)
        if raw.status != 200:
            return ChatReply(
                None,
                raw.status,
                self._clean(f"HTTP {raw.status}: {raw.body.decode('utf-8', 'replace')}"),
                _retry_after(raw.headers),
                model,
            )
        text = self._text(style, raw.body)
        if not text:
            return ChatReply(None, 502, "The model returned no text.", None, model)
        return ChatReply(text, 200, None, None, model)

    # ------------------------------------------------------------------------------------------

    def _call(self, request: urllib.request.Request, timeout: float) -> RawResponse | ChatReply:
        """The transport's answer, or a plain reply when it fails. Nothing the transport raises is repeated."""
        try:
            return self.transport(request, timeout)
        except TimeoutError:
            return ChatReply(None, 408, "The AI service did not answer in time.")
        except ValueError:  # the key could not go into a header; its text may be in the message
            return ChatReply(None, BAD_KEY_STATUS, BAD_KEY_MESSAGE)
        except Exception as error:
            logger.warning("An AI service call failed (%s).", type(error).__name__)
            return ChatReply(None, 503, "The AI service could not be reached.")

    def _request(
        self,
        style: str,
        endpoint: str,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        level: str | None = None,
    ) -> urllib.request.Request:
        headers = {"Content-Type": "application/json", "User-Agent": "QuantOS/2.0"}
        if style == "anthropic":
            headers.update({"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
            payload = _anthropic_payload(model, system, user, max_tokens, level)
            url = endpoint
        elif style == "gemini":
            # In a header, not the URL, so the key never lands in a log or an error message.
            headers["x-goog-api-key"] = self.api_key
            payload = _gemini_payload(system, user, max_tokens, level)
            url = endpoint.format(model=model)
        else:
            headers.update(self._openai_headers())
            payload = _openai_payload(model, system, user, self.provider, level)
            url = endpoint
        return urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )

    def _openai_headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.provider == "openrouter":
            headers["X-Title"] = "QuantOS"
        if self.provider == "lightning":
            headers["x-api-key"] = self.api_key
        return headers

    @staticmethod
    def _text(style: str, body: bytes) -> str:
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError:
            return ""
        parse = {"anthropic": _anthropic_text, "gemini": _gemini_text}.get(style, _openai_text)
        try:
            return parse(data)
        except (AttributeError, TypeError, IndexError, KeyError):
            return ""  # a reply shaped like nothing we know

    def _clean(self, text: str) -> str:
        return text.replace(self.api_key, "***")[:_ERROR_CHARS]


def _openai_payload(
    model: str, system: str, user: str, provider: str = "openai", level: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if level:
        # A gateway names the same setting differently from the provider that made the model.
        if provider == "openrouter":
            payload["reasoning"] = {"effort": level}
        else:
            payload["reasoning_effort"] = level
    return payload


def _anthropic_payload(
    model: str, system: str, user: str, max_tokens: int, level: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if level:
        payload["thinking"] = {"type": "adaptive"}
        payload["output_config"] = {"effort": level}
    return payload


def _gemini_payload(
    system: str, user: str, max_tokens: int, level: str | None = None
) -> dict[str, Any]:
    config: dict[str, Any] = {"maxOutputTokens": max_tokens}
    if level:
        config["thinkingConfig"] = {"thinkingLevel": level}
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": config,
    }


def _openai_text(data: Mapping[str, Any]) -> str:
    choices = data.get("choices") or []
    first = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = first.get("message")
    return str(message.get("content") or "") if isinstance(message, dict) else ""


def _anthropic_text(data: Mapping[str, Any]) -> str:
    blocks = [
        b for b in (data.get("content") or []) if isinstance(b, dict) and b.get("type") == "text"
    ]
    return "".join(str(b.get("text", "")) for b in blocks)


def _gemini_text(data: Mapping[str, Any]) -> str:
    candidates = data.get("candidates") or []
    content = (
        candidates[0].get("content") if candidates and isinstance(candidates[0], dict) else None
    )
    parts = (content or {}).get("parts", [])
    return "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))


def _retry_after(headers: Mapping[str, str]) -> float | None:
    values = [value for name, value in headers.items() if name.lower() == "retry-after"]
    try:
        return float(values[0]) if values else None
    except ValueError:
        return None
