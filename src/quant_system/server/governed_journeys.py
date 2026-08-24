"""Truthful server adapters over immutable governed evidence and runtime state."""

from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from quant_system.data.market_data import (
    BAR_RECORD_SCHEMA,
    BAR_RECORD_VERSION,
    DATASET_MANIFEST_SCHEMA,
    DATASET_MANIFEST_VERSION,
    UPSTOX_HISTORICAL_API_VERSION,
    UPSTOX_HISTORICAL_ENDPOINT,
    UPSTOX_HISTORICAL_SOURCE,
    UPSTOX_PROVIDER,
    DatasetStatus,
    SourceStatus,
)
from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.evidence import (
    EvidenceError,
    EvidenceIntegrityError,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
    VerifiedEvidence,
)
from quant_system.server.dataset_schemas import DatasetManifestResource, DatasetPageResponse

EVIDENCE_ROOT_ENV = "QUANTOS_EVIDENCE_ROOT"
_CURSOR_PREFIX = "dataset:v1:"
_DATASET_ID_PATTERN = re.compile(r"dset_[a-z0-9][a-z0-9_-]{0,95}")
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
        key=_cursor_key,
    )
    if start_after is not None and all(_cursor_key(item) != start_after for item in acquisitions):
        raise JourneyApiError(
            "INVALID_CURSOR",
            "The dataset cursor no longer identifies a verified catalog resource.",
            status_code=422,
        )
    remaining = [
        item for item in acquisitions if start_after is None or _cursor_key(item) > start_after
    ]
    selected = remaining[: limit + 1]
    has_more = len(selected) > limit
    page_items = selected[:limit]
    next_cursor = _encode_cursor(*_cursor_key(page_items[-1])) if has_more else None
    return DatasetPageResponse(
        items=[_dataset_resource(item) for item in page_items],
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


def _dataset_resource(evidence: VerifiedEvidence) -> DatasetManifestResource:
    manifest = evidence.manifest
    metadata = manifest.metadata
    _validate_dataset_identity(evidence)
    requested = _mapping(metadata, "requested_range")
    received = _mapping(metadata, "received_range")
    requested_start = _date_value(requested, "start")
    requested_end = _date_value(requested, "end")
    received_start = _date_value(received, "start")
    received_end = _date_value(received, "end")
    _validate_dataset_ranges(
        requested_start=requested_start,
        requested_end=requested_end,
        received_start=received_start,
        received_end=received_end,
    )
    return DatasetManifestResource(
        dataset_id=manifest.resource_id,
        symbol=_text(metadata, "symbol"),
        provider_instrument_id=_text(metadata, "provider_instrument_id"),
        requested_start=requested_start,
        requested_end=requested_end,
        received_start=received_start,
        received_end=received_end,
        row_count=manifest.row_count,
        manifest_hash=manifest.manifest_hash,
        canonical_content_hash=_hash_value(metadata, "canonical_content_hash"),
        provenance=_text(metadata, "source"),
        status=_text(metadata, "status"),
        source_status=_text(metadata, "source_status"),
        created_at=manifest.created_at,
    )


def _validate_dataset_identity(evidence: VerifiedEvidence) -> None:
    manifest = evidence.manifest
    metadata = manifest.metadata
    domain_manifest_hash = _hash_value(metadata, "manifest_hash")
    dataset_id = _text(metadata, "dataset_id")
    unsigned_metadata = dict(metadata)
    unsigned_metadata.pop("dataset_id", None)
    unsigned_metadata.pop("manifest_hash", None)
    expected_manifest_hash = canonical_sha256(unsigned_metadata)
    expected_dataset_id = f"dset_{expected_manifest_hash[:24]}"
    if (
        domain_manifest_hash != expected_manifest_hash
        or dataset_id != expected_dataset_id
        or dataset_id != manifest.resource_id
    ):
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains an invalid dataset domain identity.",
            status_code=409,
        )
    expected_content_hash = canonical_sha256(
        {
            "records": list(evidence.records),
            "schema_id": BAR_RECORD_SCHEMA,
            "schema_version": BAR_RECORD_VERSION,
        }
    )
    if _hash_value(metadata, "canonical_content_hash") != expected_content_hash:
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence does not match its dataset content identity.",
            status_code=409,
        )
    _validate_dataset_contract_fields(evidence)


def _validate_dataset_contract_fields(evidence: VerifiedEvidence) -> None:
    manifest = evidence.manifest
    metadata = manifest.metadata
    expected_text = {
        "provider": UPSTOX_PROVIDER,
        "provider_api_version": UPSTOX_HISTORICAL_API_VERSION,
        "provider_endpoint_id": UPSTOX_HISTORICAL_ENDPOINT,
        "schema_id": DATASET_MANIFEST_SCHEMA,
        "source": UPSTOX_HISTORICAL_SOURCE,
    }
    if any(_text(metadata, key) != value for key, value in expected_text.items()):
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains an unsupported dataset contract.",
            status_code=409,
        )
    if metadata.get("schema_version") != DATASET_MANIFEST_VERSION:
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains an unsupported dataset manifest version.",
            status_code=409,
        )
    record_schema = _mapping(metadata, "record_schema")
    if record_schema != {"id": BAR_RECORD_SCHEMA, "version": BAR_RECORD_VERSION}:
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains an unsupported point-in-time record schema.",
            status_code=409,
        )
    _validate_dataset_status_and_count(evidence)


def _validate_dataset_status_and_count(evidence: VerifiedEvidence) -> None:
    manifest = evidence.manifest
    metadata = manifest.metadata
    status = _text(metadata, "status")
    source_status = _text(metadata, "source_status")
    if status not in {item.value for item in DatasetStatus} or source_status not in {
        item.value for item in SourceStatus
    }:
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains an invalid dataset status.",
            status_code=409,
        )
    row_count = metadata.get("row_count")
    if isinstance(row_count, bool) or not isinstance(row_count, int):
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains an invalid dataset row count.",
            status_code=409,
        )
    if row_count != manifest.row_count or row_count != len(evidence.records):
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence dataset row counts do not agree.",
            status_code=409,
        )
    _validate_dataset_record_identity(evidence)


def _validate_dataset_record_identity(evidence: VerifiedEvidence) -> None:
    metadata = evidence.manifest.metadata
    instrument_id = _text(metadata, "provider_instrument_id")
    symbol = _text(metadata, "symbol")
    if any(
        _text(record, "provider_instrument_id") != instrument_id
        or _text(record, "symbol") != symbol
        or _text(record, "schema_id") != BAR_RECORD_SCHEMA
        or record.get("schema_version") != BAR_RECORD_VERSION
        for record in evidence.records
    ):
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence record identity does not match its dataset manifest.",
            status_code=409,
        )


def _validate_dataset_ranges(
    *,
    requested_start: date,
    requested_end: date,
    received_start: date,
    received_end: date,
) -> None:
    if (
        requested_start > requested_end
        or received_start > received_end
        or received_start < requested_start
        or received_end > requested_end
    ):
        raise JourneyApiError(
            "EVIDENCE_INTEGRITY_INVALID",
            "Verified evidence contains inconsistent requested and received ranges.",
            status_code=409,
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


def _cursor_key(evidence: VerifiedEvidence) -> tuple[datetime, str]:
    return (
        evidence.manifest.created_at.astimezone(UTC),
        evidence.manifest.resource_id,
    )


def _encode_cursor(created_at: datetime, resource_id: str) -> str:
    timestamp = created_at.astimezone(UTC).isoformat()
    raw = f"{_CURSOR_PREFIX}{timestamp}|{resource_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
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
    timestamp_text, separator, resource_id = decoded.removeprefix(_CURSOR_PREFIX).partition("|")
    if not separator or _DATASET_ID_PATTERN.fullmatch(resource_id) is None:
        raise JourneyApiError(
            "INVALID_CURSOR",
            "The dataset cursor does not contain a valid resource identity.",
            status_code=422,
        )
    try:
        created_at = datetime.fromisoformat(timestamp_text)
    except ValueError as error:
        raise JourneyApiError(
            "INVALID_CURSOR",
            "The dataset cursor does not contain a valid creation time.",
            status_code=422,
        ) from error
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise JourneyApiError(
            "INVALID_CURSOR",
            "The dataset cursor creation time must include a UTC offset.",
            status_code=422,
        )
    return created_at.astimezone(UTC), resource_id
