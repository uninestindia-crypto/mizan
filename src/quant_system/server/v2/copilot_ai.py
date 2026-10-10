"""Chooses and builds the AI the Copilot talks to, from what Settings says and what is on this computer.

The default is the AI app already signed in on this computer (Claude Code, Codex or Gemini CLI), so a person needs no
key. A saved key is the other source, and each backs the other up unless the person turns that off. Which AI
answered is always reported to the chat.
"""

from __future__ import annotations

from typing import Any

from quant_system.copilot.ai_choice import CLI_PREFIX, AiChoice, FallbackChat, plan_models
from quant_system.copilot.cli_chat import (
    CHAT_CLIS,
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
    "build_chat",
    "chat_model",
    "current_choice",
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
    return cli_bridge.installed_chat_clis(CHAT_CLIS)


def current_choice() -> AiChoice:
    """What the person picked in Settings. Unreadable settings mean the defaults."""
    from quant_system.server.v2.router import services

    try:
        saved = services().state.settings()
    except Exception:
        return AiChoice()
    return AiChoice(saved.ai_source, saved.ai_cli, saved.ai_api, saved.ai_fallback)


def _keyed() -> list[str]:
    return [p for p in PROVIDER_LABELS if (_lookup(p) or "").strip()]


def _one(model_id: str, apps: dict[str, str]) -> ChatModel | None:
    """One model by id: ``cli:claude`` for an app that is installed, a provider name for one with a saved key."""
    if model_id.startswith(CLI_PREFIX):
        name = model_id[len(CLI_PREFIX) :]
        return CliChat(name, apps[name], runner=_RUNNER) if name in apps else None
    key = (_lookup(model_id) or "").strip() if model_id in PROVIDER_LABELS else ""
    return _API(model_id, key) if key else None


def build_chat(choice: AiChoice) -> ChatModel | None:
    """The model the chat asks: every AI that is set up, in the person's order. None when nothing is."""
    apps = installed_apps()
    order = plan_models(choice, set(apps), set(_keyed()))
    models = [m for m in (_one(model_id, apps) for model_id in order) if m is not None]
    if not models:
        return None
    return models[0] if len(models) == 1 else FallbackChat(models)


def chat_model() -> ChatModel | None:
    return build_chat(current_choice())


def verify_models(ids: list[str]) -> list[ChatModel]:
    """The AIs a second opinion asked for, each by its own id. One that is not set up is left out."""
    apps = installed_apps()
    built = (_one(model_id, apps) for model_id in dict.fromkeys(ids))
    return [model for model in built if model is not None]


# ------------------------------------------------------------------------------ what Settings shows


def _app_row(row: dict[str, Any]) -> dict[str, Any]:
    state = str(row["state"])
    return {
        "id": row["id"],
        "name": row["name"],
        "label": CLI_LABELS[row["id"]],
        "state": state,
        "installed": bool(row["installed"]),
        "ready": state in _READY_STATES,
    }


def ai_overview() -> dict[str, Any]:
    """The apps that can chat, the saved keys, the person's choice, and whether anything is ready to answer."""
    apps = [_app_row(r) for r in cli_bridge.list_cli_status() if r["id"] in CHAT_CLIS]
    choice = current_choice()
    usable = [a for a in apps if a["ready"] or a["state"] in _UNKNOWN_STATES]
    return {
        "apps": apps,
        "ai": {
            "source": choice.source,
            "cli": choice.cli,
            "api": choice.api,
            "fallback": choice.fallback,
        },
        "ai_ready": bool(usable) or bool(_keyed()),
    }


def model_rows() -> list[dict[str, Any]]:
    """Every AI a second opinion can use: the apps and the key providers, each with an id and whether it is ready."""
    apps = {a["id"]: a for a in ai_overview()["apps"]}
    rows = [
        {
            "id": CLI_PREFIX + name,
            "label": CLI_LABELS[name],
            "ready": name in apps and apps[name]["ready"],
        }
        for name in CHAT_CLIS
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


def run_test(model_id: str | None) -> dict[str, Any]:
    """One tiny question to one AI (or to whatever the Copilot would use), answered in plain words."""
    apps = installed_apps()
    if model_id is None:
        model = build_chat(current_choice())
        message = _NOTHING_SET_UP
    else:
        model = _one(model_id, apps)
        message = explain_failure(CLI_NOT_FOUND) if model_id.startswith(CLI_PREFIX) else _NOT_SET_UP
    if model is None:
        return {"ok": False, "who": None, "message": message}
    reply = model.complete(_TEST_SYSTEM, _TEST_USER, max_tokens=20, timeout=_TEST_SECONDS)
    _remember(model_id, reply.status)
    who = _who(model)
    if reply.text is not None:
        return {"ok": True, "who": who, "message": f"{who} answered, so it is ready to use."}
    return {"ok": False, "who": who, "message": explain_failure(reply.status)}
