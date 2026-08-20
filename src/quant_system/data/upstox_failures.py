"""Typed failure mapping for the Upstox provider boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime

from quant_system.data.market_data import (
    AcquisitionFailureCode,
    HistoricalAcquisitionFailure,
    QualityFinding,
)
from quant_system.data.upstox_http import HttpResponse


def create_failure(
    code: AcquisitionFailureCode,
    detected_at: datetime,
    *,
    retryable: bool,
    recovery_action: str,
    provider_status: int | None = None,
    provider_code: str | None = None,
    retry_after_seconds: int | None = None,
    quality_findings: tuple[QualityFinding, ...] = (),
) -> HistoricalAcquisitionFailure:
    return HistoricalAcquisitionFailure(
        code=code,
        detected_at=detected_at,
        retryable=retryable,
        recovery_action=recovery_action,
        provider_status=provider_status,
        provider_code=provider_code,
        retry_after_seconds=retry_after_seconds,
        quality_findings=quality_findings,
    )


def map_http_failure(
    response: HttpResponse,
    detected_at: datetime,
) -> HistoricalAcquisitionFailure:
    retry_after_seconds = get_retry_after(response.headers)
    provider_code = _provider_error_code(response.body)
    if response.status in {401, 403}:
        return create_failure(
            AcquisitionFailureCode.PROVIDER_UNAUTHORIZED,
            detected_at,
            retryable=False,
            recovery_action="Refresh the Upstox access token and retry.",
            provider_status=response.status,
            provider_code=provider_code,
        )
    if response.status == 429:
        return create_failure(
            AcquisitionFailureCode.PROVIDER_RATE_LIMITED,
            detected_at,
            retryable=True,
            recovery_action="Wait for the provider retry window before retrying.",
            provider_status=response.status,
            provider_code=provider_code,
            retry_after_seconds=retry_after_seconds,
        )
    if response.status == 408:
        return create_failure(
            AcquisitionFailureCode.PROVIDER_TIMEOUT,
            detected_at,
            retryable=True,
            recovery_action="Retry after provider connectivity recovers.",
            provider_status=response.status,
            provider_code=provider_code,
        )
    if response.status in {400, 404, 422}:
        return create_failure(
            AcquisitionFailureCode.PROVIDER_REJECTED,
            detected_at,
            retryable=False,
            recovery_action="Verify the instrument, interval, and requested date range.",
            provider_status=response.status,
            provider_code=provider_code,
        )
    return create_failure(
        AcquisitionFailureCode.PROVIDER_UNAVAILABLE,
        detected_at,
        retryable=response.status >= 500,
        recovery_action="Retry only after provider availability recovers.",
        provider_status=response.status,
        provider_code=provider_code,
        retry_after_seconds=retry_after_seconds,
    )


def get_retry_after(headers: Mapping[str, str]) -> int | None:
    value = get_header(headers, "retry-after")
    if value is None:
        return None
    try:
        seconds = int(value)
    except ValueError:
        return None
    return seconds if 0 <= seconds <= 3600 else None


def get_header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def is_transient_status(status: int) -> bool:
    return status in {408, 429, 500, 502, 503, 504}


def require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(UTC)


def unauthorized_failure(detected_at: datetime) -> HistoricalAcquisitionFailure:
    return create_failure(
        AcquisitionFailureCode.PROVIDER_UNAUTHORIZED,
        detected_at,
        retryable=False,
        recovery_action="Configure a valid UPSTOX_ACCESS_TOKEN and retry.",
    )


def malformed_failure(detected_at: datetime) -> HistoricalAcquisitionFailure:
    return create_failure(
        AcquisitionFailureCode.PROVIDER_MALFORMED,
        detected_at,
        retryable=False,
        recovery_action="Inspect provider availability or update the response contract.",
    )


def schema_drift_failure(detected_at: datetime) -> HistoricalAcquisitionFailure:
    return create_failure(
        AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT,
        detected_at,
        retryable=False,
        recovery_action="Update the recorded provider contract before using this response.",
    )


def empty_failure(detected_at: datetime) -> HistoricalAcquisitionFailure:
    return create_failure(
        AcquisitionFailureCode.DATASET_EMPTY,
        detected_at,
        retryable=False,
        recovery_action="Verify the instrument and range; no data was accepted.",
    )


def quality_failure(
    detected_at: datetime,
    findings: tuple[QualityFinding, ...],
) -> HistoricalAcquisitionFailure:
    return create_failure(
        AcquisitionFailureCode.DATA_QUALITY_BLOCKED,
        detected_at,
        retryable=False,
        recovery_action="Inspect the findings; provider rows were not accepted.",
        quality_findings=findings,
    )


def _provider_error_code(body: bytes) -> str | None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None
    errors = payload.get("errors")
    if not isinstance(errors, list) or not errors or not isinstance(errors[0], dict):
        return None
    value = errors[0].get("errorCode") or errors[0].get("error_code") or errors[0].get("code")
    return str(value)[:128] if value is not None else None
