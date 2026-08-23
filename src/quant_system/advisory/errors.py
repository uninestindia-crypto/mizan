"""Typed fail-closed outcomes for the non-authoritative advisory journal."""

from __future__ import annotations

from enum import StrEnum


class AdvisoryFailureCode(StrEnum):
    """Stable failure codes callers may match on."""

    PROVENANCE_INCOMPLETE = "PROVENANCE_INCOMPLETE"
    MODEL_IDENTITY_INVALID = "MODEL_IDENTITY_INVALID"
    TIMESTAMP_NOT_UTC = "TIMESTAMP_NOT_UTC"
    CONFIDENCE_OUT_OF_RANGE = "CONFIDENCE_OUT_OF_RANGE"
    WEIGHT_MULTIPLIER_INVALID = "WEIGHT_MULTIPLIER_INVALID"
    NON_FINITE_VALUE = "NON_FINITE_VALUE"
    HASH_INVALID = "HASH_INVALID"
    JOURNAL_CHAIN_BROKEN = "JOURNAL_CHAIN_BROKEN"
    JOURNAL_RECORD_MALFORMED = "JOURNAL_RECORD_MALFORMED"
    # A hash chain cannot detect its own truncation: drop the last row and rows 0..n-2 are still
    # internally consistent and correctly linked. These two codes cover the external witness that
    # makes truncation visible.
    JOURNAL_TRUNCATED = "JOURNAL_TRUNCATED"
    JOURNAL_WITNESS_MISSING = "JOURNAL_WITNESS_MISSING"
    SECRET_MATERIAL_PRESENT = "SECRET_MATERIAL_PRESENT"
    HYPOTHESIS_NOT_REGISTERED = "HYPOTHESIS_NOT_REGISTERED"
    HYPOTHESIS_ALREADY_REGISTERED = "HYPOTHESIS_ALREADY_REGISTERED"
    TRIAL_ORDINAL_INVALID = "TRIAL_ORDINAL_INVALID"
    AUTHORITY_ESCALATION_ATTEMPTED = "AUTHORITY_ESCALATION_ATTEMPTED"


class AdvisoryError(RuntimeError):
    """A stable advisory failure with an optional exact offending field."""

    def __init__(
        self,
        code: AdvisoryFailureCode,
        message: str,
        *,
        offending_field: str | None = None,
    ) -> None:
        self.code = code
        self.offending_field = offending_field
        detail = f"{code.value}: {message}"
        if offending_field is not None:
            detail = f"{detail}; offending_field={offending_field}"
        super().__init__(detail)
