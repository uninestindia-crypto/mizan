"""Typed failures for statistical overfitting diagnostics."""

from __future__ import annotations

from enum import StrEnum


class MultiplicityFailureCode(StrEnum):
    """Stable failure codes emitted by multiplicity and DSR calculations."""

    MOMENT_CONSTRAINT_INVALID = "MOMENT_CONSTRAINT_INVALID"


class MultiplicityError(ValueError):
    """A machine-readable invalid-input failure from multiplicity diagnostics.

    This remains a ``ValueError`` for compatibility with numeric callers while exposing a stable
    code that governed adapters can translate without matching human-readable text.
    """

    def __init__(self, code: MultiplicityFailureCode, message: str) -> None:
        self.code = code
        super().__init__(f"{code.value}: {message}")
