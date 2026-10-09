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

__all__ = ["CLI_PREFIX", "AiChoice", "FallbackChat", "plan_models"]

logger = logging.getLogger(__name__)
CLI_PREFIX = "cli:"
_TOO_LONG = 413


@dataclass(frozen=True, slots=True)
class AiChoice:
    """What the person picked. ``cli`` and ``api`` name a favourite within their kind; None means the first ready."""

    source: Literal["cli", "api"] = "cli"
    cli: str | None = None
    api: str | None = None
    fallback: bool = True


def _ordered(ready: Collection[str], order: Sequence[str], favourite: str | None) -> list[str]:
    present = [name for name in order if name in ready]
    if favourite in present:
        present.remove(str(favourite))
        present.insert(0, str(favourite))
    return present


def plan_models(
    choice: AiChoice, cli_ready: Collection[str], api_ready: Collection[str]
) -> list[str]:
    """Model ids in the order to ask them: ``cli:claude`` for an app, a provider name for a saved key.

    An id the person once chose that is no longer set up is simply left out.
    """
    apps = [CLI_PREFIX + name for name in _ordered(cli_ready, CHAT_CLIS, choice.cli)]
    keys = _ordered(api_ready, tuple(PROVIDER_LABELS), choice.api)
    first, second = (apps, keys) if choice.source == "cli" else (keys, apps)
    return first + second if choice.fallback else first


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
