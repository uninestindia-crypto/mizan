"""Which models each AI app on this computer can use, and how hard each can think. Read live, never typed in.

Model names age within months, so nothing here carries a model name. Each answer comes from the app itself or from the
person's own account, and an app that cannot be asked says so in a plain sentence instead of showing a made-up list
(the No Fabricated Model Law):

* Antigravity lists its models with ``agy models``; a thinking tier (low, medium, high) is part of each name.
* Codex describes every model, with the thinking levels it accepts, in ``codex debug models``. If that cannot be run,
  the list Codex keeps for itself on this computer is read instead and the answer says how old it is.
* Claude Code has no list command. It documents newest-name choices in its own help, and a saved Anthropic key lists
  the exact models (with release date, size and thinking levels) through :mod:`quant_system.alpha.model_catalog`.
* A company app added by hand tells us nothing about its models, so none are shown.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_system.alpha.model_catalog import (
    EFFORT_LEVELS,
    ModelCatalogError,
    ModelEntry,
    fetch_models,
    newest_models,
)
from quant_system.server.v2 import cli_bridge

logger = logging.getLogger("quantos.cli_models")

_CACHE_SECONDS = 600.0
_LISTING_SECONDS = 25.0
_HELP_SECONDS = 15.0

# Thinking levels in plain words, lowest to highest.
LEVEL_WORDS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "xhigh": "Extra high",
    "max": "Maximum",
    "ultra": "Ultra",
}

# Antigravity bakes the thinking tier into the model name (gemini-x-flash-high).
_TIER_ORDER = ("low", "medium", "high")
_TIER_SUFFIX = re.compile(r"^(?P<base>.+)-(?P<tier>low|medium|high)$")
_TIER_LABEL = re.compile(r"\s*\((?:low|medium|high)\)\s*$", re.IGNORECASE)
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\[\]:/-]{0,79}$")

_lock = threading.Lock()
_cache: dict[tuple[str, str, bool], tuple[float, dict[str, Any]]] = {}


@dataclass(slots=True)
class _Found:
    models: list[dict[str, Any]] = field(default_factory=list)
    source: str = "none"  # app | app_saved | account | app_and_account | none
    levels: list[str] = field(default_factory=list)
    note: str | None = None
    checked: str | None = None  # when the app's own saved list was last refreshed


def clear_cache() -> None:
    with _lock:
        _cache.clear()


# ----------------------------------------------------------------------------------------- running the apps


def _capture(args: list[str], timeout: float, *, merge: bool = False) -> tuple[int, str]:
    """Run an app without a window. ``(exit code, standard output)``; ``merge`` adds what it printed as errors."""
    try:
        done = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=cli_bridge._NO_WINDOW,
            env=cli_bridge._environment(),
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)
    out = done.stdout or ""
    return done.returncode, out + (done.stderr or "") if merge else out


def _executable(agent_id: str) -> str | None:
    agent = cli_bridge.get_agent(agent_id)
    if agent is None:
        return None
    return next((found for command in agent.commands if (found := cli_bridge._find(command))), None)


# ------------------------------------------------------------------------------------------------- helpers


def _released(created: float | None) -> str | None:
    if created is None:
        return None
    try:
        return datetime.fromtimestamp(created, UTC).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _model(
    model_id: str,
    name: str,
    *,
    description: str = "",
    context_window: int | None = None,
    released: str | None = None,
    levels: list[str] | None = None,
    default_level: str | None = None,
    variants: dict[str, str] | None = None,
    recommended: bool = False,
    newest: bool = False,
) -> dict[str, Any]:
    return {
        "id": model_id,
        "name": name,
        "description": description,
        "context_window": context_window,
        "released": released,
        "newest": newest,
        "recommended": recommended,
        "thinking": {"levels": levels, "default": default_level} if levels else None,
        "variants": variants or None,
    }


def _family(model_id: str) -> str:
    base = _TIER_SUFFIX.sub(lambda m: m["base"], model_id)
    return re.sub(r"-{2,}", "-", re.sub(r"\d+(?:\.\d+)*", "", base)).strip("-")


def _version(model_id: str) -> tuple[int, ...]:
    base = _TIER_SUFFIX.sub(lambda m: m["base"], model_id)
    return tuple(int(part) for part in re.findall(r"\d+", base))


def _mark_newest(models: list[dict[str, Any]]) -> None:
    """Mark the highest version of each kind of model (flash, pro, ...), but only where there is a newer and an
    older one to tell apart. A model that stands alone is not "the newest" of anything."""
    kinds: dict[str, list[dict[str, Any]]] = {}
    for item in models:
        kinds.setdefault(_family(str(item["id"])), []).append(item)
    for members in kinds.values():
        if len(members) > 1:
            max(members, key=lambda m: _version(str(m["id"])))["newest"] = True


# ------------------------------------------------------------------------------------------- Antigravity


def parse_antigravity_models(text: str) -> list[dict[str, Any]]:
    """``agy models`` prints ``id<TAB>label`` lines. Names that differ only by a thinking tier become one model."""
    groups: dict[str, dict[str, Any]] = {}
    for raw in text.splitlines():
        parts = [p.strip() for p in re.split(r"\t+|\s{2,}", raw.strip()) if p.strip()]
        if len(parts) < 2 or not _MODEL_ID.match(parts[0]):
            continue
        model_id, label = parts[0], parts[1]
        tier = _TIER_SUFFIX.match(model_id)
        if tier is None:
            groups.setdefault(model_id, {"id": model_id, "name": label, "variants": {}})
            continue
        group = groups.setdefault(
            tier["base"],
            {"id": tier["base"], "name": _TIER_LABEL.sub("", label), "variants": {}},
        )
        group["variants"][tier["tier"]] = model_id
    models: list[dict[str, Any]] = []
    for group in groups.values():
        variants = {t: group["variants"][t] for t in _TIER_ORDER if t in group["variants"]}
        models.append(
            _model(
                group["id"],
                group["name"],
                levels=list(variants) or None,
                variants=variants or None,
            )
        )
    _mark_newest(models)
    return models


def _antigravity() -> _Found:
    executable = _executable("antigravity")
    if executable is None:
        return _Found(note="Install this app first.")
    code, text = _capture([executable, "models"], _LISTING_SECONDS)
    models = parse_antigravity_models(text) if code == 0 else []
    if not models:
        return _Found(
            note="The app did not list its models. Make sure you are signed in, then refresh."
        )
    levels = [t for t in _TIER_ORDER if any(t in (m["variants"] or {}) for m in models)]
    return _Found(models, "app", levels)


# ------------------------------------------------------------------------------------------------ Codex


def parse_codex_models(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    shown = [r for r in rows if isinstance(r, dict) and r.get("visibility", "list") == "list"]

    def rank(item: dict[str, Any]) -> int:
        priority = item.get("priority")
        return priority if isinstance(priority, int) and not isinstance(priority, bool) else 10**6

    models: list[dict[str, Any]] = []
    for item in sorted(shown, key=rank):
        slug = item.get("slug")
        if not isinstance(slug, str) or not _MODEL_ID.match(slug):
            continue
        efforts = item.get("supported_reasoning_levels")
        levels = [
            str(e["effort"])
            for e in efforts or []
            if isinstance(e, dict) and isinstance(e.get("effort"), str)
        ]
        window = item.get("context_window")
        default = item.get("default_reasoning_level")
        models.append(
            _model(
                slug,
                str(item.get("display_name") or slug),
                description=str(item.get("description") or ""),
                context_window=window if isinstance(window, int) else None,
                levels=levels or None,
                default_level=default if isinstance(default, str) else None,
            )
        )
    if models:
        models[0]["recommended"] = True  # the app lists its own first choice first
    _mark_newest(models)
    return models


def _json_from(text: str) -> Any:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return None


def _codex_saved_list() -> tuple[list[dict[str, Any]], str | None]:
    """The list Codex keeps on this computer, and when it last refreshed it."""
    path = Path.home() / ".codex" / "models_cache.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], None
    fetched = payload.get("fetched_at") if isinstance(payload, dict) else None
    return parse_codex_models(payload), fetched if isinstance(fetched, str) else None


def _codex() -> _Found:
    executable = _executable("codex")
    if executable is None:
        return _Found(note="Install this app first.")
    code, text = _capture([executable, "debug", "models"], _LISTING_SECONDS)
    live = parse_codex_models(_json_from(text)) if code == 0 else []
    if live:
        return _Found(live, "app", _all_levels(live))
    saved, fetched = _codex_saved_list()
    if saved:
        return _Found(
            saved,
            "app_saved",
            _all_levels(saved),
            "The app could not be asked just now, so this is the list it saved earlier.",
            fetched,
        )
    return _Found(
        note="The app did not list its models. Make sure you are signed in, then refresh."
    )


def _all_levels(models: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    for item in models:
        for level in (item["thinking"] or {}).get("levels", []):
            if level not in found:
                found.append(level)
    return found


# ------------------------------------------------------------------------------------------- Claude Code


def parse_claude_help(text: str) -> tuple[list[str], list[str]]:
    """``(newest-name choices, thinking levels)`` as the app's own help text states them."""
    flat = re.sub(r"\s+", " ", text)
    alias_part = re.search(r"alias for the latest model \(e\.g\. ([^)]*)\)", flat)
    aliases = re.findall(r"'([a-z0-9][a-z0-9-]*)'", alias_part[1]) if alias_part else []
    level_part = re.search(r"--effort <level>[^(]*\(([^)]*)\)", flat)
    levels = [lv.strip() for lv in level_part[1].split(",")] if level_part else []
    return aliases, [lv for lv in EFFORT_LEVELS if lv in levels]


def _claude_key() -> str | None:
    from quant_system.server.v2.credentials import AI_KEY_NAMES

    return os.environ.get(AI_KEY_NAMES["anthropic"], "").strip() or None


def _account_models(entries: list[ModelEntry]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for entry in entries:
        models.append(
            _model(
                entry.id,
                entry.name,
                context_window=entry.max_input_tokens,
                released=_released(entry.created),
                levels=list(entry.effort_levels) or None,
                newest=True,
            )
        )
    return models


def _claude(refresh: bool) -> _Found:
    executable = _executable("claude")
    if executable is None:
        return _Found(note="Install this app first.")
    code, text = _capture([executable, "--help"], _HELP_SECONDS, merge=True)
    aliases, levels = parse_claude_help(text) if code == 0 else ([], [])
    models = [
        _model(
            alias,
            alias.capitalize(),
            description=f"Always the newest {alias.capitalize()} your account can use.",
            levels=levels or None,
            newest=True,
        )
        for alias in aliases
    ]
    key = _claude_key()
    if key is None:
        note = (
            "Save your Anthropic key under Accounts & keys to also see the exact models and when they came out."
            if models
            else "The app did not say which models it offers. Save your Anthropic key under Accounts & keys to list them."
        )
        return _Found(models, "app" if models else "none", levels, note)
    try:
        entries = newest_models("anthropic", fetch_models("anthropic", key, refresh=refresh), 8)
    except ModelCatalogError as error:
        return _Found(
            models,
            "app" if models else "none",
            levels,
            f"Your account's list could not be read: {error}",
        )
    models += _account_models(entries)
    for item in models:
        for level in (item["thinking"] or {}).get("levels", []):
            if level not in levels:
                levels.append(level)
    levels = [lv for lv in EFFORT_LEVELS if lv in levels]
    return _Found(models, "app_and_account" if aliases else "account", levels)


# --------------------------------------------------------------------------------------------- the answer

_SOURCES = {
    "app": "Read from the app on this computer just now.",
    "app_saved": "Read from the list the app saved on this computer.",
    "account": "Read from your Anthropic account just now.",
    "app_and_account": "Read from the app and your Anthropic account just now.",
    "none": "No models could be read.",
}


def _facts(found: _Found) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    if found.models:
        newest = next((m for m in found.models if m["newest"]), found.models[0])
        facts.append(
            {
                "name": "Models",
                "description": f"{len(found.models)} found. The newest is {newest['name']}.",
            }
        )
    if found.levels:
        words = ", ".join(LEVEL_WORDS.get(level, level.capitalize()) for level in found.levels)
        facts.append({"name": "Thinking level", "description": f"You can choose: {words}."})
    elif found.models:
        facts.append(
            {"name": "Thinking level", "description": "This app does not offer a choice of levels."}
        )
    return facts


def _cache_key(agent_id: str, version: str, has_key: bool) -> tuple[str, str, bool]:
    return agent_id, version, has_key


def fetch_cli_capabilities(agent_id: str, force_refresh: bool = False) -> dict[str, Any]:
    """The live models and thinking levels of one AI app. Raises ``ValueError`` for an app that does not exist."""
    agent = cli_bridge.get_agent(agent_id)
    if agent is None:
        raise ValueError(f"Unknown AI app: {agent_id}")
    info = next(
        (s for s in cli_bridge.list_cli_status(force=force_refresh) if s["id"] == agent_id), None
    )
    installed = bool(info and info.get("installed"))
    version = str((info or {}).get("version") or "")
    custom = cli_bridge.is_custom_agent(agent_id)
    base = {
        "agent_id": agent_id,
        "name": agent.name,
        "maker": agent.maker,
        "installed": installed,
        "authenticated": bool(info and info.get("authenticated")),
        "version": version or None,
        "is_custom": custom,
    }
    if custom:
        return _answer(base, _Found(note="This app chooses its own model."))
    if not installed:
        return _answer(base, _Found(note="Install this app first."))

    key = _cache_key(agent_id, version, agent_id == "claude" and _claude_key() is not None)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit is not None and not force_refresh and now - hit[0] < _CACHE_SECONDS:
            return {**base, **hit[1]}
    if agent_id == "antigravity":
        found = _antigravity()
    elif agent_id == "codex":
        found = _codex()
    elif agent_id == "claude":
        found = _claude(force_refresh)
    else:
        found = _Found(note="This app chooses its own model.")
    answer = _answer(base, found)
    if found.models:  # a failed read is never remembered, so the next look tries again
        with _lock:
            _cache[key] = (now, {k: v for k, v in answer.items() if k not in base})
    return answer


def _answer(base: dict[str, Any], found: _Found) -> dict[str, Any]:
    return {
        **base,
        "models": found.models,
        "thinking_levels": found.levels,
        "features": _facts(found),
        "source": found.source,
        "source_note": _SOURCES[found.source],
        "saved_list_checked": found.checked,
        "note": found.note,
        "last_fetched": datetime.now(UTC).isoformat(),
    }
