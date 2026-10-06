"""What the Copilot says when an AI service fails. Plain words, and each one names the next click."""

from __future__ import annotations


def explain_failure(status: int) -> str:
    """A person-readable reason for an AI provider's failure status. Never contains a code, key or raw error."""
    if status in (401, 403):
        return "That AI service did not accept your key. Open Settings, then Accounts and keys, and check it."
    if status == 404:
        return (
            "That AI model is not available to your key. "
            "Open Settings, then Accounts and keys, and check the provider."
        )
    if status == 413:
        return "That was too long to send to the AI service. Try a shorter question."
    if status == 429:
        return (
            "That AI service is busy or you have reached its limit. "
            "Wait a minute and try again, or add another provider in Settings."
        )
    if status in (408, 502, 503, 504):
        return "I could not reach that AI service. Check your internet connection and try again."
    return (
        "Something went wrong with the AI service. "
        "Try again, or add another provider in Settings, then Accounts and keys."
    )
