"""Which AI answers the Copilot, and in what order, when more than one is set up.

The person chooses a source in Settings: the AI app already signed in on this computer (the default), or a saved
key. The other kind stays behind it as a backup unless the person turns that off, so one AI that is down or signed
out does not leave the chat silent. The chat always says which AI answered.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal

from quant_system.copilot.cli_chat import CHAT_CLIS
from quant_system.copilot.llm import ChatModel, ChatReply
from quant_system.copilot.providers import PROVIDER_LABELS

__all__ = [
    "CLI_PREFIX",
    "AiChoice",
    "FallbackChat",
    "OrderEntry",
    "plan_entries",
    "plan_models",
]

logger = logging.getLogger(__name__)
CLI_PREFIX = "cli:"
_TOO_LONG = 413


@dataclass(frozen=True, slots=True)
class OrderEntry:
    """One AI to ask, with the model and thinking level the person chose for it (None: the AI's own usual)."""

    id: str
    model: str | None = None
    thinking: str | None = None


@dataclass(frozen=True, slots=True)
class AiChoice:
    """What the person picked. ``cli`` and ``api`` name a favourite within their kind; None means the first ready.

    ``order`` is the person's own list of AIs, apps and saved keys together. When it is empty the older choices above
    (a kind first, a favourite, an app priority) decide, exactly as before.
    """

    source: Literal["cli", "api"] = "cli"
    cli: str | None = None
    api: str | None = None
    fallback: bool = True
    cli_priority: tuple[str, ...] = ()
    api_priority: tuple[str, ...] = ()
    order: tuple[OrderEntry, ...] = ()


def _ordered(
    ready: Collection[str],
    default_order: Sequence[str],
    favourite: str | None,
    priority: Sequence[str] = (),
) -> list[str]:
    valid_names = set(default_order) | set(priority)
    ordered: list[str] = []
    seen: set[str] = set()

    for name in priority:
        if name in ready and name not in seen:
            ordered.append(name)
            seen.add(name)

    if favourite and favourite in ready and favourite in valid_names and favourite not in seen:
        ordered.insert(0, str(favourite))
        seen.add(str(favourite))

    for name in default_order:
        if name in ready and name not in seen:
            ordered.append(name)
            seen.add(name)

    return ordered


def plan_entries(
    choice: AiChoice, cli_ready: Collection[str], api_ready: Collection[str]
) -> list[OrderEntry]:
    """The AIs to ask, in order, each with its chosen model and level.

    With the person's own list, exactly the AIs on it that are set up, in that order (with the backup off, only the first
    of them). Without one, the older rules decide and no model or level is chosen.
    """
    if choice.order:
        ready = {CLI_PREFIX + name for name in cli_ready} | set(api_ready)
        listed: list[OrderEntry] = []
        for entry in choice.order:
            if entry.id in ready and all(entry.id != seen.id for seen in listed):
                listed.append(entry)
        return listed if choice.fallback else listed[:1]
    apps = [
        CLI_PREFIX + name
        for name in _ordered(cli_ready, CHAT_CLIS, choice.cli, choice.cli_priority)
    ]
    keys = _ordered(api_ready, tuple(PROVIDER_LABELS), choice.api, choice.api_priority)
    first, second = (apps, keys) if choice.source == "cli" else (keys, apps)
    return [OrderEntry(model_id) for model_id in (first + second if choice.fallback else first)]


def plan_models(
    choice: AiChoice, cli_ready: Collection[str], api_ready: Collection[str]
) -> list[str]:
    """Model ids in the order to ask them: ``cli:claude`` for an app, a provider name for a saved key.

    An id the person once chose that is no longer set up is simply left out.
    """
    return [entry.id for entry in plan_entries(choice, cli_ready, api_ready)]


class FallbackChat:
    """Asks each model in turn until one answers. ``provider`` and ``model`` name the one that did."""

    def __init__(self, models: Sequence[ChatModel]) -> None:
        if not models:
            raise ValueError("A chat needs at least one model to ask.")
        self._models = list(models)
        self.provider = self._models[0].provider
        self.model = self._models[0].model

    def complete(
        self, system: str, user: str, *, max_tokens: int = 900, timeout: float = 60.0
    ) -> ChatReply:
        first_failure: ChatReply | None = None
        for model in self._models:
            reply = self._ask(model, system, user, max_tokens, timeout)
            if reply.text is not None:
                self.provider, self.model = model.provider, reply.model or model.model
                return reply
            first_failure = first_failure or reply
            if reply.status == _TOO_LONG:
                break
        assert first_failure is not None
        return first_failure

    @staticmethod
    def _ask(
        model: ChatModel, system: str, user: str, max_tokens: int, timeout: float
    ) -> ChatReply:
        try:
            return model.complete(system, user, max_tokens=max_tokens, timeout=timeout)
        except Exception as error:  # one model failing must not stop the next from being tried
            logger.warning("An AI failed to answer (%s).", type(error).__name__)
            return ChatReply(None, 503, "The AI could not be reached.")
