"""Which AI providers the person has a saved key for, and the chat models built from those keys.

The key lookup is supplied by the caller (it reads the app's saved keys), so nothing here knows where a key is
stored and no key value is ever returned, logged or placed in a result.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from quant_system.copilot.llm import ChatModel, ProviderChat

__all__ = ["PROVIDER_LABELS", "KeyLookup", "build_models", "default_model", "provider_status"]

KeyLookup = Callable[[str], str | None]  # provider id -> its saved key, or None

# In the order the chat prefers them when several keys exist.
PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "groq": "Groq",
    "deepseek": "DeepSeek",
    "mistral": "Mistral",
    "openrouter": "OpenRouter",
}


def _has_key(lookup: KeyLookup, provider: str) -> bool:
    return bool((lookup(provider) or "").strip())


def provider_status(lookup: KeyLookup) -> list[dict[str, Any]]:
    return [
        {"id": provider, "label": label, "ready": _has_key(lookup, provider)}
        for provider, label in PROVIDER_LABELS.items()
    ]


def build_models(lookup: KeyLookup, providers: Sequence[str]) -> list[ChatModel]:
    """One chat model per requested provider that has a key. Unknown or keyless providers are skipped."""
    models: list[ChatModel] = []
    for provider in dict.fromkeys(providers):
        key = (lookup(provider) or "").strip() if provider in PROVIDER_LABELS else ""
        if key:
            models.append(ProviderChat(provider, key))
    return models


def default_model(lookup: KeyLookup) -> ChatModel | None:
    """The model the chat uses: the first provider in the preferred order that has a key."""
    models = build_models(lookup, [p for p in PROVIDER_LABELS if _has_key(lookup, p)][:1])
    return models[0] if models else None
