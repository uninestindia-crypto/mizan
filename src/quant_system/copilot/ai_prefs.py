"""How a person wants an AI to answer: which model, how hard it thinks, how fast, and how many helpers.

These are choices about the *manner* of an answer, never about what the Copilot may do. Every value that can end up on a
command line or in a request is checked here, in one place, so the settings, the chat request and the AI apps all agree
on what is allowed:

* a model name must start with a letter or digit, so it can never be read as an option, and holds no space or quote;
* a thinking level is one of a short fixed set. Whether a given model accepts it is the app's or the provider's answer,
  never a table kept here (the No Fabricated Model Law).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = [
    "DEFAULT_SPEED",
    "MAX_HELPERS",
    "SPEEDS",
    "THINKING_LEVELS",
    "AnswerPrefs",
    "SpeedPreset",
    "clean_model",
    "clean_thinking",
    "effective_thinking",
    "preset",
]

# Lowest to highest. "ultra" exists only for apps that report it; the apps that do not accept it ignore it.
THINKING_LEVELS: Final[tuple[str, ...]] = ("low", "medium", "high", "xhigh", "max", "ultra")
SPEEDS: Final[tuple[str, ...]] = ("quick", "balanced", "careful")
DEFAULT_SPEED: Final = "balanced"
MAX_HELPERS: Final = 3

_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\[\]-]{0,79}$")


@dataclass(frozen=True, slots=True)
class SpeedPreset:
    """What "quick", "balanced" and "careful" mean in numbers. A preset is a set of limits, not a model feature."""

    thinking: str | None  # used only when the person did not choose a level themselves
    chat_steps: int
    agent_steps: int
    call_timeout: float
    deadline: float


_PRESETS: Final[dict[str, SpeedPreset]] = {
    "quick": SpeedPreset("low", 3, 6, 45.0, 70.0),
    "balanced": SpeedPreset(None, 6, 12, 60.0, 150.0),
    "careful": SpeedPreset("high", 8, 18, 120.0, 280.0),
}


@dataclass(frozen=True, slots=True)
class AnswerPrefs:
    """What one message asks for, over the saved defaults. ``None`` everywhere means "as usual".

    When ``ai`` is set the chosen AI goes first and ``model`` and ``thinking`` are read as that AI's own choices, so
    "Automatic" in the picker really means automatic. With no ``ai`` they apply to whichever AI is first.
    """

    ai: str | None = None
    model: str | None = None
    thinking: str | None = None
    speed: str | None = None
    helpers: int | None = None
    # Who does the work of an agent run: None or "built_in" for the Copilot's own loop, else an AI app ("cli:claude").
    runner: str | None = None


def preset(speed: str | None) -> SpeedPreset:
    return _PRESETS.get(speed or DEFAULT_SPEED, _PRESETS[DEFAULT_SPEED])


def clean_model(text: str | None) -> str | None:
    """A model name that is safe to hand to an app or a provider, or ``None`` (the AI's own newest choice)."""
    if text is None:
        return None
    value = text.strip()
    if not value:
        return None
    if not _MODEL_ID.fullmatch(value):
        raise ValueError("That model name has a character that is not allowed.")
    return value


def clean_thinking(text: str | None) -> str | None:
    if text is None or not text.strip():
        return None
    value = text.strip().lower()
    if value not in THINKING_LEVELS:
        raise ValueError("Pick one of the thinking levels in the list.")
    return value


def effective_thinking(chosen: str | None, speed: str | None) -> str | None:
    """The level asked for: the person's own choice, else what the speed stands for, else the AI's usual."""
    return chosen or preset(speed).thinking
