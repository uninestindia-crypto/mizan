"""What the Copilot says when an AI service fails. Plain words, and each one names the next click."""

from __future__ import annotations

from quant_system.copilot.llm import BAD_KEY_MESSAGE, BAD_KEY_STATUS

CANCELLED_TEXT = "You stopped this check."

# Statuses made by the AI apps on this computer (see ``cli_chat``). Written here as numbers because that module
# imports this one's neighbours, and a message must not depend on it.
_CLI_MESSAGES = {
    491: (
        "The AI app you chose is not installed on this computer. "
        "Open Settings, then AI assistants, to install it or pick another."
    ),
    492: "The AI app you chose is not signed in. Open Settings, then AI assistants, and choose Sign in.",
    493: (
        "The AI app you chose is too old to be used safely. "
        "Open Settings, then AI assistants, and update it, or pick another AI."
    ),
    494: "The AI app you chose could not answer. Open Settings, then AI assistants, and choose Test this AI.",
}


def explain_failure(status: int) -> str:
    """A person-readable reason for an AI service's failure status. Never contains a code, key or raw error."""
    if status == BAD_KEY_STATUS:
        return BAD_KEY_MESSAGE
    if status in _CLI_MESSAGES:
        return _CLI_MESSAGES[status]
    if status in (401, 403):
        return "That AI service did not accept your key. Open Settings, then Accounts and keys, and check it."
    if status == 404:
        return (
            "That AI model is not available with your key. "
            "Open Settings, then Accounts and keys, and check that key."
        )
    if status == 413:
        return "That was too long to send to the AI service. Try a shorter question."
    if status == 429:
        return (
            "That AI service is busy or you have reached its limit. "
            "Wait a minute and try again, or add a key for another AI service: "
            "open Settings, then Accounts and keys."
        )
    if status in (408, 502, 503, 504):
        return "I could not reach that AI service. Check your internet connection and try again."
    return (
        "Something went wrong with the AI service. "
        "Try again, or add a key for another AI service in Settings, then Accounts and keys."
    )
