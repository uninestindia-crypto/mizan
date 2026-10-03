"""Direct REST API clients for OpenRouter, Groq, OpenAI, Anthropic, Gemini, DeepSeek and Mistral."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from quant_system.alpha.key_pool import ManagedKey, ProviderType
from quant_system.alpha.model_catalog import ModelCatalogError, latest_model_id

logger = logging.getLogger(__name__)


def parse_json_from_llm_response(text: str) -> dict[str, Any] | None:
    """Extract and parse a JSON dictionary from LLM output (including code blocks)."""
    cleaned = text.strip()
    # Check if wrapped in markdown code blocks
    if "```json" in cleaned:
        start = cleaned.find("```json") + 7
        end = cleaned.find("```", start)
        if end != -1:
            cleaned = cleaned[start:end].strip()
    elif "```" in cleaned:
        start = cleaned.find("```") + 3
        end = cleaned.find("```", start)
        if end != -1:
            cleaned = cleaned[start:end].strip()

    # Fallback to brace boundaries
    start_brace = cleaned.find("{")
    end_brace = cleaned.rfind("}")
    if start_brace != -1 and end_brace != -1 and start_brace < end_brace:
        candidate = cleaned[start_brace : end_brace + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return None


class BaseDirectAPIClient(ABC):
    """Abstract direct REST client with standard HTTP POST and rate-limit detection.

    A client with no ``default_model`` asks the provider which model is newest for the key being
    used (see :mod:`quant_system.alpha.model_catalog`), so no model name is pinned in code.
    """

    PROVIDER: str = ""
    PREFER: tuple[str, ...] = ()

    def __init__(self, default_model: str | None = None, timeout_seconds: float = 5.0) -> None:
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    def resolve_model(self, key: ManagedKey, model: str | None = None) -> str:
        """An explicit model wins, then the configured default, then the provider's newest."""
        explicit = model or self.default_model
        if explicit:
            return explicit
        return latest_model_id(self.PROVIDER, key.secret_value, prefer=self.PREFER)

    @abstractmethod
    def build_request(
        self, prompt: str, key: ManagedKey, model: str | None = None
    ) -> urllib.request.Request:
        """Construct the urllib Request object with endpoint and auth headers."""
        raise NotImplementedError

    @abstractmethod
    def parse_response_content(self, response_body: bytes) -> str:
        """Extract the model response text from the provider JSON payload."""
        raise NotImplementedError

    def execute(
        self,
        prompt: str,
        key: ManagedKey,
        model: str | None = None,
    ) -> tuple[str | None, int, float | None, str | None]:
        """Execute request returning (response_text, status_code, retry_after_seconds, error_msg)."""
        try:
            req = self.build_request(prompt, key, model=model)
        except ModelCatalogError as error:
            return None, 503, None, f"Could not choose a model: {error}"
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read()
                content = self.parse_response_content(body)
                return content, resp.status, None, None
        except urllib.error.HTTPError as error:
            retry_after: float | None = None
            if "Retry-After" in error.headers:
                try:
                    retry_after = float(error.headers["Retry-After"])
                except ValueError:
                    pass
            err_body = ""
            try:
                err_body = error.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return None, error.code, retry_after, f"HTTP {error.code}: {err_body[:200]}"
        except TimeoutError:
            return None, 408, None, "Request timed out"
        except urllib.error.URLError as error:
            return None, 503, None, f"Network error: {error.reason}"
        except Exception as error:
            return None, 500, None, f"Unexpected transport error: {error}"


class OpenRouterClient(BaseDirectAPIClient):
    """Direct REST client for OpenRouter (https://openrouter.ai)."""

    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
    PROVIDER = "openrouter"
    PREFER = ("anthropic/claude-sonnet", "claude-sonnet")

    def __init__(
        self,
        default_model: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(default_model=default_model, timeout_seconds=timeout_seconds)

    def build_request(
        self, prompt: str, key: ManagedKey, model: str | None = None
    ) -> urllib.request.Request:
        payload = {
            "model": self.resolve_model(key, model),
            "messages": [
                {"role": "system", "content": "You are a quantitative trading advisory assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key.secret_value}",
            "HTTP-Referer": "https://github.com/uninestindia-crypto/quant-system",
            "X-Title": "QuantOS",
        }
        return urllib.request.Request(self.ENDPOINT, data=data, headers=headers, method="POST")

    def parse_response_content(self, response_body: bytes) -> str:
        data = json.loads(response_body.decode("utf-8"))
        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            return str(choices[0]["message"].get("content", ""))
        return ""


class GroqClient(BaseDirectAPIClient):
    """Direct REST client for Groq high-speed LPU inference (https://groq.com)."""

    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
    PROVIDER = "groq"
    PREFER = ("llama",)

    def __init__(
        self,
        default_model: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(default_model=default_model, timeout_seconds=timeout_seconds)

    def build_request(
        self, prompt: str, key: ManagedKey, model: str | None = None
    ) -> urllib.request.Request:
        payload = {
            "model": self.resolve_model(key, model),
            "messages": [
                {
                    "role": "system",
                    "content": "You are an institutional quant macro & risk advisor.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key.secret_value}",
            "User-Agent": "QuantOS/1.0",
        }
        return urllib.request.Request(self.ENDPOINT, data=data, headers=headers, method="POST")

    def parse_response_content(self, response_body: bytes) -> str:
        data = json.loads(response_body.decode("utf-8"))
        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            return str(choices[0]["message"].get("content", ""))
        return ""


class OpenAIClient(BaseDirectAPIClient):
    """Direct REST client for OpenAI (https://api.openai.com)."""

    ENDPOINT = "https://api.openai.com/v1/chat/completions"
    PROVIDER = "openai"
    PREFER = ("gpt-",)

    def __init__(
        self,
        default_model: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(default_model=default_model, timeout_seconds=timeout_seconds)

    def build_request(
        self, prompt: str, key: ManagedKey, model: str | None = None
    ) -> urllib.request.Request:
        payload = {
            "model": self.resolve_model(key, model),
            "messages": [
                {
                    "role": "system",
                    "content": "You are a quantitative model sanity & invariant auditor.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key.secret_value}",
        }
        return urllib.request.Request(self.ENDPOINT, data=data, headers=headers, method="POST")

    def parse_response_content(self, response_body: bytes) -> str:
        data = json.loads(response_body.decode("utf-8"))
        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            return str(choices[0]["message"].get("content", ""))
        return ""


class AnthropicClient(BaseDirectAPIClient):
    """Direct REST client for Anthropic Messages API (https://api.anthropic.com)."""

    ENDPOINT = "https://api.anthropic.com/v1/messages"
    PROVIDER = "anthropic"
    PREFER = ("sonnet",)

    def __init__(
        self,
        default_model: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        super().__init__(default_model=default_model, timeout_seconds=timeout_seconds)

    def build_request(
        self, prompt: str, key: ManagedKey, model: str | None = None
    ) -> urllib.request.Request:
        payload = {
            "model": self.resolve_model(key, model),
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": key.secret_value,
            "anthropic-version": "2023-06-01",
        }
        return urllib.request.Request(self.ENDPOINT, data=data, headers=headers, method="POST")

    def parse_response_content(self, response_body: bytes) -> str:
        data = json.loads(response_body.decode("utf-8"))
        content = data.get("content", [])
        if content and isinstance(content, list):
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            return "".join(texts)
        return ""


class OpenAICompatibleClient(BaseDirectAPIClient):
    """Chat-completions clients that speak OpenAI's wire format (DeepSeek, Mistral).

    Plain text in, plain text out: no JSON mode is forced, because this client also answers
    conversational questions. Callers that need JSON parse it tolerantly with
    :func:`parse_json_from_llm_response`.
    """

    ENDPOINT = ""
    SYSTEM_PROMPT = "You are a quantitative trading advisory assistant."

    def build_request(
        self, prompt: str, key: ManagedKey, model: str | None = None
    ) -> urllib.request.Request:
        payload = {
            "model": self.resolve_model(key, model),
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key.secret_value}",
            "User-Agent": "QuantOS/2.0",
        }
        return urllib.request.Request(
            self.ENDPOINT, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )

    def parse_response_content(self, response_body: bytes) -> str:
        data = json.loads(response_body.decode("utf-8"))
        choices = data.get("choices", [])
        if choices and "message" in choices[0]:
            return str(choices[0]["message"].get("content", ""))
        return ""


class DeepSeekClient(OpenAICompatibleClient):
    """Direct REST client for DeepSeek (https://api.deepseek.com)."""

    ENDPOINT = "https://api.deepseek.com/chat/completions"
    PROVIDER = "deepseek"
    PREFER = ("chat",)


class MistralClient(OpenAICompatibleClient):
    """Direct REST client for Mistral (https://api.mistral.ai)."""

    ENDPOINT = "https://api.mistral.ai/v1/chat/completions"
    PROVIDER = "mistral"
    PREFER = ("large",)


class GeminiClient(BaseDirectAPIClient):
    """Direct REST client for the Gemini API (https://generativelanguage.googleapis.com)."""

    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    PROVIDER = "gemini"
    PREFER = ("flash",)  # the assistant favours a fast model; the newest Flash is chosen live

    def build_request(
        self, prompt: str, key: ManagedKey, model: str | None = None
    ) -> urllib.request.Request:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }
        headers = {
            "Content-Type": "application/json",
            # In a header, not the URL, so the key never lands in a log or an error message.
            "x-goog-api-key": key.secret_value,
            "User-Agent": "QuantOS/2.0",
        }
        url = self.ENDPOINT.format(model=self.resolve_model(key, model))
        return urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )

    def parse_response_content(self, response_body: bytes) -> str:
        data = json.loads(response_body.decode("utf-8"))
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            return "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
        return ""


def get_direct_client_for_provider(provider: ProviderType) -> BaseDirectAPIClient | None:
    """Factory helper returning appropriate direct API client."""
    if provider == ProviderType.OPENROUTER:
        return OpenRouterClient()
    if provider == ProviderType.GROQ:
        return GroqClient()
    if provider == ProviderType.OPENAI:
        return OpenAIClient()
    if provider == ProviderType.ANTHROPIC:
        return AnthropicClient()
    if provider == ProviderType.GEMINI:
        return GeminiClient()
    if provider == ProviderType.DEEPSEEK:
        return DeepSeekClient()
    if provider == ProviderType.MISTRAL:
        return MistralClient()
    return None
