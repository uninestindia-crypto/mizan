"""Live model catalogue: ask each provider which models a key can reach.

Model names age within months, so nothing here (or anywhere that calls it) carries a model name in
code. The newest models are read from the provider's own ``/models`` endpoint with the user's key,
and cached briefly. If the provider cannot be reached the caller gets a :class:`ModelCatalogError`
with a plain reason; there is deliberately no built-in fallback list that would quietly go stale.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

PROVIDERS: tuple[str, ...] = (
    "anthropic",
    "openai",
    "gemini",
    "openrouter",
    "groq",
    "deepseek",
    "mistral",
    "lightning",
)

_CACHE_SECONDS = 1800.0
_TIMEOUT_SECONDS = 8.0
_USER_AGENT = "QuantOS/2.0"

_lock = threading.Lock()
_cache: dict[tuple[str, str], tuple[float, list[ModelEntry]]] = {}


class ModelCatalogError(RuntimeError):
    """The provider's model list could not be read."""


# The thinking levels a provider can report, lowest to highest.
EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True, slots=True)
class ModelEntry:
    id: str
    name: str
    created: float | None  # epoch seconds, when the provider reports it
    max_input_tokens: int | None = None  # how much it can read at once, when the provider says
    effort_levels: tuple[str, ...] = ()  # thinking levels the provider says this model accepts

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "name": self.name, "created": self.created}
        if self.max_input_tokens is not None:
            out["max_input_tokens"] = self.max_input_tokens
        if self.effort_levels:
            out["effort_levels"] = list(self.effort_levels)
        return out


def _http_get_json(url: str, headers: dict[str, str], timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, **headers})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


# Replaced in tests; production code always goes through this indirection.
_get_json: Callable[[str, dict[str, str], float], Any] = _http_get_json


def _epoch(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


_NON_CHAT = (
    "embed",
    "whisper",
    "tts",
    "dall-e",
    "image",
    "audio",
    "realtime",
    "transcribe",
    "moderation",
    "guard",
    "safeguard",
    "rerank",
    "ocr",
    "speech",
    "sora",
    "video",
    "vision-preview",
    "live",
    "robotics",
    "aqa",
    "davinci",
    "babbage",
    "instruct",
    "computer-use",
    "search",
)
# OpenAI lists dated snapshots (gpt-x-2025-01-31, gpt-x-0613) beside the plain name of the same
# model; show the plain name. Anthropic's list has only dated ids, so this is OpenAI-only.
_SNAPSHOT = re.compile(r"-(\d{4}-\d{2}-\d{2}|\d{4})$")


def _is_chat_model(provider: str, model_id: str) -> bool:
    lowered = model_id.lower()
    if lowered.startswith("ft:") or any(token in lowered for token in _NON_CHAT):
        return False
    return not (provider == "openai" and _SNAPSHOT.search(lowered))


def _anthropic_entry(item: dict[str, Any]) -> ModelEntry:
    """One Anthropic model with what its own listing says it can do (never a guess from its name)."""
    capabilities = item.get("capabilities")
    effort = capabilities.get("effort") if isinstance(capabilities, dict) else None
    levels: tuple[str, ...] = ()
    if isinstance(effort, dict):
        levels = tuple(
            level
            for level in EFFORT_LEVELS
            if isinstance(effort.get(level), dict) and effort[level].get("supported") is True
        )
    window = item.get("max_input_tokens")
    tokens = window if isinstance(window, int) and not isinstance(window, bool) else None
    return ModelEntry(
        str(item["id"]),
        str(item.get("display_name") or item["id"]),
        _epoch(item.get("created_at")),
        tokens,
        levels,
    )


def _openai_style(payload: Any) -> list[ModelEntry]:
    out: list[ModelEntry] = []
    for item in payload.get("data", []) if isinstance(payload, dict) else []:
        model_id = str(item.get("id", "")).strip()
        if model_id:
            out.append(ModelEntry(model_id, model_id, _epoch(item.get("created"))))
    return out


def _fetch(provider: str, api_key: str | None) -> list[ModelEntry]:
    key = (api_key or "").strip()
    timeout = _TIMEOUT_SECONDS
    if provider == "openrouter":
        # The public catalogue needs no key.
        payload = _get_json("https://openrouter.ai/api/v1/models", {}, timeout)
        return [
            ModelEntry(str(i["id"]), str(i.get("name") or i["id"]), _epoch(i.get("created")))
            for i in payload.get("data", [])
            if i.get("id")
        ]
    if not key:
        raise ModelCatalogError("Add an API key first; the model list comes from your account.")
    if provider == "anthropic":
        payload = _get_json(
            "https://api.anthropic.com/v1/models?limit=1000",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout,
        )
        return [_anthropic_entry(i) for i in payload.get("data", []) if i.get("id")]
    if provider == "gemini":
        # The key goes in a header, not the URL, so it never appears in an error message or a log.
        payload = _get_json(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
            {"x-goog-api-key": key},
            timeout,
        )
        out: list[ModelEntry] = []
        for item in payload.get("models", []):
            methods = item.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            model_id = str(item.get("name", "")).removeprefix("models/")
            if model_id.startswith("gemini"):
                out.append(ModelEntry(model_id, str(item.get("displayName") or model_id), None))
        return out
    auth = {"Authorization": f"Bearer {key}", "x-api-key": key}
    urls = {
        "openai": "https://api.openai.com/v1/models",
        "groq": "https://api.groq.com/openai/v1/models",
        "deepseek": "https://api.deepseek.com/models",
        "mistral": "https://api.mistral.ai/v1/models",
        "lightning": "https://lightning.ai/v1/models",
    }
    if provider not in urls:
        raise ModelCatalogError(f"{provider} has no model list.")
    return _openai_style(_get_json(urls[provider], auth, timeout))


def _explain(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        if error.code in (401, 403):
            return "The provider rejected this key."
        return f"The provider answered HTTP {error.code}."
    if isinstance(error, urllib.error.URLError):
        return "Could not reach the provider. Check your internet connection."
    if isinstance(error, TimeoutError):
        return "The provider took too long to answer."
    return "The provider's answer was not a model list."


def fetch_models(provider: str, api_key: str | None, *, refresh: bool = False) -> list[ModelEntry]:
    """Every chat model the key can use, newest first. Cached for 30 minutes."""
    name = provider.lower().strip()
    if name not in PROVIDERS:
        raise ModelCatalogError(f"Unknown provider: {provider}")
    fingerprint = hashlib.sha256((api_key or "").encode("utf-8")).hexdigest()[:16]
    cache_key = (name, fingerprint)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(cache_key)
        if hit is not None and not refresh and now - hit[0] < _CACHE_SECONDS:
            return hit[1]
    try:
        raw = _fetch(name, api_key)
    except ModelCatalogError:
        raise
    except (OSError, ValueError, KeyError, AttributeError, TypeError) as error:
        raise ModelCatalogError(_explain(error)) from error
    chat = [m for m in raw if _is_chat_model(name, m.id)]
    ordered = sorted(chat, key=_newest_first(name))
    with _lock:
        _cache[cache_key] = (now, ordered)
    return ordered


def _version_tuple(model_id: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", model_id.split("/")[-1])[:3])


def _tier(model_id: str) -> int:
    lowered = model_id.lower()
    for rank, token in enumerate(("pro", "flash", "lite")):
        if token in lowered:
            return rank
    return 3


def _newest_first(provider: str) -> Callable[[ModelEntry], tuple[Any, ...]]:
    if provider == "gemini":
        # Gemini reports no creation date: newest version first, then pro before flash before lite.
        return lambda m: (tuple(-v for v in _version_tuple(m.id)) or (0,), _tier(m.id), m.id)
    return lambda m: (-(m.created or 0.0), m.id)


def _family(provider: str, model_id: str) -> str:
    lowered = model_id.lower().split("/")[-1]
    if provider == "anthropic":
        match = re.match(r"claude-([a-z]+)", lowered)
        return match.group(1) if match else lowered
    if provider == "gemini":
        return str(_tier(lowered))
    if provider == "openrouter":
        return model_id.lower().split("/")[0]
    return lowered


_OPENROUTER_MAKERS = frozenset(
    {"anthropic", "openai", "google", "x-ai", "meta-llama", "mistralai", "deepseek", "qwen"}
)


def newest_models(provider: str, models: list[ModelEntry], limit: int = 4) -> list[ModelEntry]:
    """The newest model of each family (Opus, Sonnet ... / Pro, Flash ... / each maker on a gateway)."""
    name = provider.lower().strip()
    if name in ("anthropic", "gemini", "openrouter"):
        seen: set[str] = set()
        picked: list[ModelEntry] = []
        for entry in models:
            family = _family(name, entry.id)
            if name == "openrouter" and family not in _OPENROUTER_MAKERS:
                continue  # a gateway lists hundreds of makers; show the well-known ones
            if family not in seen:
                seen.add(family)
                picked.append(entry)
        return picked[:limit]
    return models[:limit]


def latest_model_id(provider: str, api_key: str | None, *, prefer: tuple[str, ...] = ()) -> str:
    """The id of the newest model for a provider, optionally the newest whose id has a ``prefer`` word.

    ``prefer`` is matched in order, so ``("sonnet",)`` means "the newest Sonnet, otherwise the newest
    model of any kind".
    """
    models = fetch_models(provider, api_key)
    if not models:
        raise ModelCatalogError("The provider listed no chat models for this key.")
    for word in prefer:
        for entry in models:
            if word.lower() in entry.id.lower():
                return entry.id
    return models[0].id


def clear_cache() -> None:
    with _lock:
        _cache.clear()
