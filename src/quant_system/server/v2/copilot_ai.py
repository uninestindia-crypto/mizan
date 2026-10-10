"""Chooses and builds the AI the Copilot talks to, from what Settings says and what is on this computer.

The default is the AI app already signed in on this computer (Claude Code, Codex or Gemini CLI), so a person needs no
key. A saved key is the other source, and each backs the other up unless the person turns that off. Which AI
answered is always reported to the chat.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from quant_system.copilot.ai_choice import (
    CLI_PREFIX,
    AiChoice,
    FallbackChat,
    OrderEntry,
    plan_entries,
)
from quant_system.copilot.ai_prefs import DEFAULT_SPEED, AnswerPrefs, effective_thinking
from quant_system.copilot.cli_chat import (
    CLI_LABELS,
    CLI_NOT_FOUND,
    CLI_NOT_SIGNED_IN,
    CliChat,
    run_cli,
)
from quant_system.copilot.llm import ChatModel, ProviderChat
from quant_system.copilot.messages import explain_failure
from quant_system.copilot.providers import PROVIDER_LABELS
from quant_system.server.v2 import cli_bridge, copilot_wiring

__all__ = [
    "ai_overview",
    "build_chain",
    "build_chat",
    "chain_for",
    "chat_model",
    "chat_model_for",
    "current_choice",
    "current_defaults",
    "run_test",
    "verify_models",
]

_RUNNER = run_cli
_API = ProviderChat
_TEST_SYSTEM = "You are a connection check for the QuantOS investing app."
_TEST_USER = "Reply with exactly the single word OK."
_TEST_SECONDS = 120.0
_NOTHING_SET_UP = "No AI is set up yet. Open Settings, then AI assistants, and pick one."
_NOT_SET_UP = "That AI is not set up. Open Settings, then AI assistants, and pick one that is."
_READY_STATES = ("CONNECTED",)
_UNKNOWN_STATES = ("UNKNOWN",)


def _lookup(provider: str) -> str | None:
    return copilot_wiring.key_lookup(provider)


def installed_apps() -> dict[str, str]:
    """The apps on this computer that can answer a chat: id -> where they are."""
    return cli_bridge.installed_chat_clis(cli_bridge.all_chat_cli_ids())


def current_choice() -> AiChoice:
    """What the person picked in Settings. Unreadable settings mean the defaults."""
    from quant_system.server.v2.router import services

    try:
        saved = services().state.settings()
    except Exception:
        return AiChoice()
    return AiChoice(
        source=saved.ai_source,
        cli=saved.ai_cli,
        api=saved.ai_api,
        fallback=saved.ai_fallback,
        cli_priority=tuple(saved.cli_priority),
        order=tuple(OrderEntry(e.id, e.model, e.thinking) for e in saved.ai_order),
    )


def current_defaults() -> tuple[str, int]:
    """``(speed, helpers)`` the person likes answers made with. Unreadable settings mean the usual."""
    from quant_system.server.v2.router import services

    try:
        saved = services().state.settings().ai_defaults
    except Exception:
        return DEFAULT_SPEED, 1
    return saved.speed, saved.helpers


def _keyed() -> list[str]:
    return [p for p in PROVIDER_LABELS if (_lookup(p) or "").strip()]


def _one(
    model_id: str,
    apps: dict[str, str],
    *,
    model: str | None = None,
    thinking: str | None = None,
) -> ChatModel | None:
    """One AI by id: ``cli:claude`` for an app that is installed, a provider name for one with a saved key.

    ``model`` and ``thinking`` are the person's choices for it. They are passed on only when set, so an AI with nothing
    chosen is built exactly as it always was. A model name that is not safe to pass leaves the AI out.
    """
    chosen = bool(model or thinking)
    if model_id.startswith(CLI_PREFIX):
        name = model_id[len(CLI_PREFIX) :]
        if name not in apps:
            return None
        try:
            if chosen:
                return CliChat(name, apps[name], runner=_RUNNER, model=model, thinking=thinking)
            return CliChat(name, apps[name], runner=_RUNNER)
        except ValueError:
            return None
    key = (_lookup(model_id) or "").strip() if model_id in PROVIDER_LABELS else ""
    if not key:
        return None
    return _API(model_id, key, model=model, thinking=thinking) if chosen else _API(model_id, key)


def _first(
    entries: list[OrderEntry], prefs: AnswerPrefs, ready: set[str], fallback: bool
) -> list[OrderEntry]:
    """The order for one message: the AI it asked for goes first; the model and level it asked for go with it."""
    if prefs.ai:
        if prefs.ai not in ready:
            return entries  # an AI that is not set up cannot be asked for; the saved order stands
        rest = [e for e in entries if e.id != prefs.ai]
        return [OrderEntry(prefs.ai, prefs.model, prefs.thinking), *(rest if fallback else [])]
    if entries and (prefs.model or prefs.thinking):
        head = entries[0]
        return [
            OrderEntry(head.id, prefs.model or head.model, prefs.thinking or head.thinking),
            *entries[1:],
        ]
    return entries


def build_chain(choice: AiChoice, prefs: AnswerPrefs | None = None) -> list[ChatModel]:
    """Every AI that is set up, one by one, in the person's order. Empty when nothing is.

    ``prefs`` are what this one message asked for (which AI, which model, how hard to think, how fast).
    """
    apps = installed_apps()
    keyed = set(_keyed())
    entries = plan_entries(choice, set(apps), keyed)
    speed = prefs.speed if prefs else None
    if prefs is not None:
        ready = {CLI_PREFIX + name for name in apps} | keyed
        entries = _first(entries, prefs, ready, choice.fallback)
    built = (
        _one(e.id, apps, model=e.model, thinking=effective_thinking(e.thinking, speed))
        for e in entries
    )
    return [m for m in built if m is not None]


def build_chat(choice: AiChoice, prefs: AnswerPrefs | None = None) -> ChatModel | None:
    """The model the chat asks: every AI that is set up, in the person's order. None when nothing is."""
    models = build_chain(choice, prefs)
    if not models:
        return None
    return models[0] if len(models) == 1 else FallbackChat(models)


def chain_for(prefs: AnswerPrefs | None) -> list[ChatModel]:
    """The AIs for one run, one by one: as set up, at the speed the person likes unless the run asked for another."""
    speed, _helpers = current_defaults()
    if prefs is None:
        return build_chain(
            current_choice(), None if speed == DEFAULT_SPEED else AnswerPrefs(speed=speed)
        )
    return build_chain(current_choice(), replace(prefs, speed=prefs.speed or speed))


def chat_model() -> ChatModel | None:
    """The model the Copilot asks, as the person has set it up, at the speed they like by default."""
    speed, _helpers = current_defaults()
    return build_chat(
        current_choice(), None if speed == DEFAULT_SPEED else AnswerPrefs(speed=speed)
    )


def chat_model_for(prefs: AnswerPrefs) -> ChatModel | None:
    """The model for one message that asked for something other than the saved defaults."""
    speed, _helpers = current_defaults()
    return build_chat(current_choice(), replace(prefs, speed=prefs.speed or speed))


def verify_models(ids: list[str]) -> list[ChatModel]:
    """The AIs a second opinion asked for, each by its own id. One that is not set up is left out."""
    apps = installed_apps()
    built = (_one(model_id, apps) for model_id in dict.fromkeys(ids))
    return [model for model in built if model is not None]


# ------------------------------------------------------------------------------ what Settings shows


def _app_row(row: dict[str, Any]) -> dict[str, Any]:
    state = str(row["state"])
    row_id = str(row["id"])
    label = CLI_LABELS.get(row_id) or f"{row.get('name', row_id)} ({row.get('maker', 'Company')})"
    return {
        "id": row_id,
        "name": row["name"],
        "label": label,
        "state": state,
        "installed": bool(row["installed"]),
        "ready": state in _READY_STATES,
        "is_custom": bool(row.get("is_custom")),
    }


def ai_overview() -> dict[str, Any]:
    """The apps that can chat, the saved keys, the person's choice, and whether anything is ready to answer."""
    chat_ids = set(cli_bridge.all_chat_cli_ids())
    apps = [_app_row(r) for r in cli_bridge.list_cli_status() if r["id"] in chat_ids]
    choice = current_choice()
    usable = [a for a in apps if a["ready"] or a["state"] in _UNKNOWN_STATES]
    return {
        "apps": apps,
        "ai": {
            "source": choice.source,
            "cli": choice.cli,
            "api": choice.api,
            "fallback": choice.fallback,
            "cli_priority": list(choice.cli_priority),
            "order": [{"id": e.id, "model": e.model, "thinking": e.thinking} for e in choice.order],
        },
        "defaults": dict(zip(("speed", "helpers"), current_defaults(), strict=True)),
        "ai_ready": bool(usable) or bool(_keyed()),
    }


def model_rows() -> list[dict[str, Any]]:
    """Every AI a second opinion can use: the apps and the key providers, each with an id and whether it is ready."""
    apps = {a["id"]: a for a in ai_overview()["apps"]}
    chat_ids = cli_bridge.all_chat_cli_ids()
    rows = [
        {
            "id": CLI_PREFIX + name,
            "label": apps[name]["label"] if name in apps else CLI_LABELS.get(name, name.title()),
            "ready": name in apps and apps[name]["ready"],
        }
        for name in chat_ids
    ]
    keyed = set(_keyed())
    return rows + [
        {"id": p, "label": label, "ready": p in keyed} for p, label in PROVIDER_LABELS.items()
    ]


# ------------------------------------------------------------------------------ "Test this AI"


def _who(model: ChatModel) -> str:
    if model.provider.startswith(CLI_PREFIX):
        return CLI_LABELS.get(model.provider[len(CLI_PREFIX) :], model.provider)
    return PROVIDER_LABELS.get(model.provider, model.provider)


def _remember(model_id: str | None, status: int) -> None:
    """What a real test showed about an app's sign-in, so Settings can say so."""
    if (
        model_id is None
        or not model_id.startswith(CLI_PREFIX)
        or status not in (200, CLI_NOT_SIGNED_IN)
    ):
        return
    cli_bridge.record_probe(model_id[len(CLI_PREFIX) :], status == 200)


def run_test(
    model_id: str | None, chosen_model: str | None = None, thinking: str | None = None
) -> dict[str, Any]:
    """One tiny question to one AI (or to whatever the Copilot would use), answered in plain words.

    ``chosen_model`` and ``thinking`` test an AI exactly as the person set it up, so a setting it refuses shows here.
    """
    apps = installed_apps()
    if model_id is None:
        model = build_chat(current_choice())
        message = _NOTHING_SET_UP
    else:
        model = _one(model_id, apps, model=chosen_model, thinking=thinking)
        message = explain_failure(CLI_NOT_FOUND) if model_id.startswith(CLI_PREFIX) else _NOT_SET_UP
    if model is None:
        return {"ok": False, "who": None, "message": message}
    reply = model.complete(_TEST_SYSTEM, _TEST_USER, max_tokens=20, timeout=_TEST_SECONDS)
    _remember(model_id, reply.status)
    who = _who(model)
    if reply.text is not None:
        return {"ok": True, "who": who, "message": f"{who} answered, so it is ready to use."}
    return {"ok": False, "who": who, "message": explain_failure(reply.status)}
