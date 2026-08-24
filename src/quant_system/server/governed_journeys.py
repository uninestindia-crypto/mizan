"""Truthful server adapters over immutable governed evidence and runtime state."""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from quant_system.data.market_data import BAR_RECORD_SCHEMA
from quant_system.evidence import (
    EvidenceError,
    EvidenceIntegrityError,
    EvidenceManifest,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
    VerifiedEvidence,
)
from quant_system.server.dataset_schemas import DatasetManifestResource, DatasetPageResponse

EVIDENCE_ROOT_ENV = "QUANTOS_EVIDENCE_ROOT"
_CURSOR_PREFIX = "dataset:"
_IDEMPOTENCY_KEY_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-"
)


class JourneyApiError(Exception):
    """Expected API failure with a stable public code and HTTP status."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int,
        retry_after_seconds: int | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.details = details or {}
        self.headers = headers or {}


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceConfig:
    """Operator-selected evidence location, never populated from an HTTP request."""

    root: Path


def runtime_evidence_config() -> RuntimeEvidenceConfig:
    """Resolve the configured evidence root without creating or disclosing it."""
    configured = os.getenv(EVIDENCE_ROOT_ENV, "").strip()
    if not configured:
        raise JourneyApiError(
            "EVIDENCE_ROOT_NOT_CONFIGURED",
            f"Set {EVIDENCE_ROOT_ENV} before using governed evidence endpoints.",
            status_code=503,
            retry_after_seconds=60,
        )
    return RuntimeEvidenceConfig(root=Path(configured).expanduser().resolve())


def require_idempotency_key(value: str | None) -> str:
    """Return one bounded canonical mutation key or fail with a stable public error."""
    key = value.strip() if value is not None else ""
    if not key:
        raise JourneyApiError(
            "IDEMPOTENCY_KEY_REQUIRED",
            "Idempotency-Key is required for this mutation.",
            status_code=422,
        )
    if len(key) > 128 or any(character not in _IDEMPOTENCY_KEY_CHARS for character in key):
        raise JourneyApiError(
            "IDEMPOTENCY_KEY_INVALID",
            "Idempotency-Key must use 1-128 letters, digits, dots, underscores, colons, or hyphens.",
            status_code=422,
        )
    return key


def dataset_page(*, limit: int, cursor: str | None) -> DatasetPageResponse:
    """Read one verified point-in-time acquisition page in a deterministic total order."""
    config = runtime_evidence_config()
    start_after = _decode_cursor(cursor) if cursor is not None else None
    if not config.root.exists():
        return DatasetPageResponse(items=[], next_cursor=None, has_more=False)
    if not config.root.is_dir():
        raise JourneyApiError(
            "EVIDENCE_ROOT_INVALID",
            "The configured evidence root is not a directory.",
            status_code=503,
            retry_after_seconds=60,
        )
    if not (config.root / EvidenceResourceType.DATASET.value).exists():
        return DatasetPageResponse(items=[], next_cursor=None, has_more=False)
    evidence = _verified_dataset_evidence(config.root)

    acquisitions = sorted(
        (item for item in evidence if item.manifest.schema_id == BAR_RECORD_SCHEMA),
        key=lambda item: item.manifest.resource_id,
    )
    remaining = [
        item
        for item in acquisitions
        if start_after is None or item.manifest.resource_id > start_after
    ]
    selected = remaining[: limit + 1]
    has_more = len(selected) > limit
    page_items = selected[:limit]
    next_cursor = _encode_cursor(page_items[-1].manifest.resource_id) if has_more else None
    return DatasetPageResponse(
        items=[_dataset_resource(item.manifest.metadata, item.manifest) for item in page_items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def _verified_dataset_evidence(root: Path) -> tuple[VerifiedEvidence, ...]:
    try:
        return EvidenceStore(EvidenceStoreConfig(root=root)).list_verified(
            EvidenceResourceType.DATASET
        )
    except EvidenceIntegrityError as error:
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "The configured evidence catalog failed verified readback.",
            status_code=409,
        ) from error
    except (EvidenceError, OSError) as error:
        raise JourneyApiError(
            "EVIDENCE_STORE_UNAVAILABLE",
            "The configured evidence store could not be read safely.",
            status_code=503,
            retry_after_seconds=30,
        ) from error


def _dataset_resource(
    metadata: dict[str, Any], manifest: EvidenceManifest
) -> DatasetManifestResource:
    requested = _mapping(metadata, "requested_range")
    received = _mapping(metadata, "received_range")
    return DatasetManifestResource(
        dataset_id=manifest.resource_id,
        symbol=_text(metadata, "symbol"),
        provider_instrument_id=_text(metadata, "provider_instrument_id"),
        requested_start=_date_value(requested, "start"),
        requested_end=_date_value(requested, "end"),
        received_start=_date_value(received, "start"),
        received_end=_date_value(received, "end"),
        row_count=manifest.row_count,
        manifest_hash=manifest.manifest_hash,
        canonical_content_hash=_hash_value(metadata, "canonical_content_hash"),
        provenance=_text(metadata, "source"),
        status=_text(metadata, "status"),
        source_status=_text(metadata, "source_status"),
        created_at=manifest.created_at,
    )


def _text(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence is missing a required dataset identity field.",
            status_code=409,
            details={"field": key},
        )
    return value


def _date_value(mapping: dict[str, Any], key: str) -> date:
    value = _text(mapping, key)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains an invalid dataset date.",
            status_code=409,
            details={"field": key},
        ) from error


def _hash_value(mapping: dict[str, Any], key: str) -> str:
    value = _text(mapping, key)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains an invalid dataset content hash.",
            status_code=409,
            details={"field": key},
        )
    return value


def _mapping(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence is missing a required dataset range.",
            status_code=409,
            details={"field": key},
        )
    return value


def _encode_cursor(resource_id: str) -> str:
    raw = f"{_CURSOR_PREFIX}{resource_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> str:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.b64decode(padded, altchars=b"-_", validate=True).decode()
    except (binascii.Error, UnicodeDecodeError) as error:
        raise JourneyApiError(
            "INVALID_CURSOR",
            "The dataset cursor is malformed.",
            status_code=422,
        ) from error
    if not decoded.startswith(_CURSOR_PREFIX):
        raise JourneyApiError(
            "INVALID_CURSOR",
            "The dataset cursor does not belong to this collection.",
            status_code=422,
        )
    resource_id = decoded.removeprefix(_CURSOR_PREFIX)
    if not resource_id.startswith("dset_"):
        raise JourneyApiError(
            "INVALID_CURSOR",
            "The dataset cursor does not contain a valid resource identity.",
            status_code=422,
        )
    return resource_id
