"""Immutable contracts for content-addressed evidence."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from quant_system.evidence.errors import EvidenceIntegrityError

_RESOURCE_ID_PATTERN = re.compile(r"[a-z]+_[a-z0-9][a-z0-9_-]{0,95}")
_PURPOSE_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,63}")
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")


class EvidenceResourceType(StrEnum):
    DATASET = "datasets"
    TRIAL = "trials"
    MODEL = "models"
    OPERATION = "operations"
    SESSION = "sessions"
    BUNDLE = "bundles"


class CommitPhase(StrEnum):
    STAGING_CREATED = "STAGING_CREATED"
    BLOBS_STAGED = "BLOBS_STAGED"
    BLOBS_PUBLISHED = "BLOBS_PUBLISHED"
    MANIFEST_STAGED = "MANIFEST_STAGED"
    COMMIT_MARKER_STAGED = "COMMIT_MARKER_STAGED"
    RESOURCE_PUBLISHED = "RESOURCE_PUBLISHED"


@dataclass(frozen=True, slots=True)
class EvidenceStoreConfig:
    root: Path
    chunk_uncompressed_bytes: int = 16 * 1024 * 1024
    max_bundle_bytes: int = 100 * 1024 * 1024
    min_free_bytes: int = 1024 * 1024 * 1024
    max_manifest_bytes: int = 1024 * 1024
    lease_wait_seconds: float = 2.0
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def __post_init__(self) -> None:
        if not 64 <= self.chunk_uncompressed_bytes <= 16 * 1024 * 1024:
            raise ValueError("chunk_uncompressed_bytes must be between 64 bytes and 16 MiB")
        if not 1 <= self.max_bundle_bytes <= 100 * 1024 * 1024:
            raise ValueError("max_bundle_bytes must be between 1 byte and 100 MiB")
        if self.chunk_uncompressed_bytes > self.max_bundle_bytes:
            raise ValueError("chunk size cannot exceed the bundle size limit")
        if self.min_free_bytes < 0:
            raise ValueError("min_free_bytes cannot be negative")
        if not 1024 <= self.max_manifest_bytes <= 4 * 1024 * 1024:
            raise ValueError("max_manifest_bytes must be between 1 KiB and 4 MiB")
        if not 0 <= self.lease_wait_seconds <= 60:
            raise ValueError("lease_wait_seconds must be between 0 and 60 seconds")


@dataclass(frozen=True, slots=True)
class EvidenceDraft:
    resource_type: EvidenceResourceType
    resource_id: str
    schema_id: str
    schema_version: int
    metadata: Mapping[str, Any]
    records: tuple[Mapping[str, Any], ...]
    total_order: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_resource_id(self.resource_type, self.resource_id)
        if not 1 <= len(self.schema_id) <= 128:
            raise ValueError("schema_id must contain 1-128 characters")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("only evidence schema version 1 is writable")
        if not self.records:
            raise ValueError("evidence records cannot be empty")
        if not self.total_order or len(set(self.total_order)) != len(self.total_order):
            raise ValueError("total_order must contain unique field names")


@dataclass(frozen=True, slots=True)
class EvidenceIdentity:
    resource_type: EvidenceResourceType
    resource_id: str
    manifest_hash: str

    def __post_init__(self) -> None:
        _validate_resource_id(self.resource_type, self.resource_id)
        if _HASH_PATTERN.fullmatch(self.manifest_hash) is None:
            raise ValueError("manifest_hash must be a SHA-256 hash")


@dataclass(frozen=True, slots=True)
class BlobDescriptor:
    ordinal: int
    row_count: int
    canonical_bytes: int
    stored_bytes: int
    canonical_hash: str
    stored_hash: str
    relative_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_bytes": self.canonical_bytes,
            "canonical_hash": self.canonical_hash,
            "encoding": "CANONICAL_JSONL_GZIP",
            "ordinal": self.ordinal,
            "relative_path": self.relative_path,
            "row_count": self.row_count,
            "stored_bytes": self.stored_bytes,
            "stored_hash": self.stored_hash,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> BlobDescriptor:
        _require_exact_keys(payload, _BLOB_KEYS, "blob descriptor")
        if payload["encoding"] != "CANONICAL_JSONL_GZIP":
            raise EvidenceIntegrityError("unsupported blob encoding")
        descriptor = cls(
            ordinal=_required_int(payload, "ordinal"),
            row_count=_required_int(payload, "row_count"),
            canonical_bytes=_required_int(payload, "canonical_bytes"),
            stored_bytes=_required_int(payload, "stored_bytes"),
            canonical_hash=_required_hash(payload, "canonical_hash"),
            stored_hash=_required_hash(payload, "stored_hash"),
            relative_path=_required_text(payload, "relative_path"),
        )
        if (
            min(
                descriptor.ordinal,
                descriptor.row_count,
                descriptor.canonical_bytes,
                descriptor.stored_bytes,
            )
            < 0
        ):
            raise EvidenceIntegrityError("blob descriptor counts cannot be negative")
        return descriptor


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    resource_type: EvidenceResourceType
    resource_id: str
    created_at: datetime
    schema_id: str
    schema_version: int
    metadata: dict[str, Any]
    total_order: tuple[str, ...]
    row_count: int
    canonical_bytes: int
    stored_bytes: int
    canonical_records_hash: str
    blobs: tuple[BlobDescriptor, ...]
    manifest_hash: str

    @property
    def identity(self) -> EvidenceIdentity:
        return EvidenceIdentity(self.resource_type, self.resource_id, self.manifest_hash)

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "blobs": [blob.to_dict() for blob in self.blobs],
            "canonical_bytes": self.canonical_bytes,
            "canonical_records_hash": self.canonical_records_hash,
            "created_at": _utc_text(self.created_at),
            "evidence_schema_id": "quantos.evidence_manifest",
            "evidence_schema_version": 1,
            "metadata": self.metadata,
            "record_schema": {"id": self.schema_id, "version": self.schema_version},
            "resource_id": self.resource_id,
            "resource_type": self.resource_type.value,
            "row_count": self.row_count,
            "stored_bytes": self.stored_bytes,
            "total_order": list(self.total_order),
        }
        if include_hash:
            payload["manifest_hash"] = self.manifest_hash
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> EvidenceManifest:
        _require_exact_keys(payload, _MANIFEST_KEYS, "evidence manifest")
        _validate_manifest_schema(payload)
        metadata, total_order, blobs_payload = _manifest_collections(payload)
        resource_type, resource_id, created_at = _manifest_identity(payload)
        schema_id, schema_version = _manifest_record_schema(payload)
        row_count, canonical_bytes, stored_bytes = _manifest_counts(payload)
        return cls(
            resource_type=resource_type,
            resource_id=resource_id,
            created_at=created_at,
            schema_id=schema_id,
            schema_version=schema_version,
            metadata=metadata,
            total_order=tuple(total_order),
            row_count=row_count,
            canonical_bytes=canonical_bytes,
            stored_bytes=stored_bytes,
            canonical_records_hash=_required_hash(payload, "canonical_records_hash"),
            blobs=tuple(BlobDescriptor.from_dict(item) for item in blobs_payload),
            manifest_hash=_required_hash(payload, "manifest_hash"),
        )


@dataclass(frozen=True, slots=True)
class CommitResult:
    manifest: EvidenceManifest
    published: bool
    deduplicated: bool


@dataclass(frozen=True, slots=True)
class VerifiedEvidence:
    manifest: EvidenceManifest
    records: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    quarantined_staging_count: int
    quarantined_lease_count: int


@dataclass(frozen=True, slots=True)
class ActiveReference:
    purpose: str
    target: EvidenceIdentity
    updated_at: datetime
    reference_hash: str

    def __post_init__(self) -> None:
        if _PURPOSE_PATTERN.fullmatch(self.purpose) is None:
            raise ValueError("active-reference purpose is invalid")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("active-reference timestamp must be timezone-aware")
        if self.reference_hash and _HASH_PATTERN.fullmatch(self.reference_hash) is None:
            raise ValueError("reference_hash must be a SHA-256 hash")

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "purpose": self.purpose,
            "schema_id": "quantos.active_reference",
            "schema_version": 1,
            "target": {
                "manifest_hash": self.target.manifest_hash,
                "resource_id": self.target.resource_id,
                "resource_type": self.target.resource_type.value,
            },
            "updated_at": _utc_text(self.updated_at),
        }
        if include_hash:
            payload["reference_hash"] = self.reference_hash
        return payload


@dataclass(frozen=True, slots=True)
class IntegrityScanReport:
    valid_resource_ids: tuple[str, ...]
    invalid_resource_ids: tuple[str, ...]
    orphan_blob_hashes: tuple[str, ...] = ()
    """Content-addressed blobs on disk that no verified manifest references.

    A non-empty tuple means the catalog no longer accounts for everything the store
    published. Deleting trailing resources rolls their accounting back silently, but the
    blobs they wrote survive, so orphans make that rollback detectable. An interrupted
    commit can also leave one, because blobs publish before their resource does, so this
    is reported rather than treated as corruption.
    """


_RESOURCE_PREFIXES = {
    EvidenceResourceType.DATASET: "dset_",
    EvidenceResourceType.TRIAL: "trial_",
    EvidenceResourceType.MODEL: "model_",
    EvidenceResourceType.OPERATION: "op_",
    EvidenceResourceType.SESSION: "session_",
    EvidenceResourceType.BUNDLE: "bundle_",
}
_BLOB_KEYS = {
    "canonical_bytes",
    "canonical_hash",
    "encoding",
    "ordinal",
    "relative_path",
    "row_count",
    "stored_bytes",
    "stored_hash",
}
_MANIFEST_KEYS = {
    "blobs",
    "canonical_bytes",
    "canonical_records_hash",
    "created_at",
    "evidence_schema_id",
    "evidence_schema_version",
    "manifest_hash",
    "metadata",
    "record_schema",
    "resource_id",
    "resource_type",
    "row_count",
    "stored_bytes",
    "total_order",
}


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise EvidenceIntegrityError(f"{key} must be non-empty text")
    return value


def _validate_manifest_schema(payload: Mapping[str, Any]) -> None:
    if payload["evidence_schema_id"] != "quantos.evidence_manifest":
        raise EvidenceIntegrityError("unsupported evidence manifest schema")
    if payload["evidence_schema_version"] != 1:
        raise EvidenceIntegrityError("unsupported evidence manifest version")


def _manifest_collections(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...], tuple[dict[str, Any], ...]]:
    metadata = payload["metadata"]
    if not isinstance(metadata, dict):
        raise EvidenceIntegrityError("manifest metadata must be an object")
    total_order = payload["total_order"]
    if not isinstance(total_order, list) or not all(isinstance(item, str) for item in total_order):
        raise EvidenceIntegrityError("manifest total_order must be text fields")
    if not total_order or len(set(total_order)) != len(total_order):
        raise EvidenceIntegrityError("manifest total_order must contain unique fields")
    blobs = payload["blobs"]
    if not isinstance(blobs, list) or not blobs:
        raise EvidenceIntegrityError("manifest requires at least one blob")
    if not all(isinstance(item, dict) for item in blobs):
        raise EvidenceIntegrityError("blob descriptor must be an object")
    return dict(metadata), tuple(total_order), tuple(dict(item) for item in blobs)


def _manifest_identity(
    payload: Mapping[str, Any],
) -> tuple[EvidenceResourceType, str, datetime]:
    try:
        resource_type = EvidenceResourceType(_required_text(payload, "resource_type"))
        created_at = datetime.fromisoformat(
            _required_text(payload, "created_at").replace("Z", "+00:00")
        )
    except (ValueError, TypeError) as error:
        raise EvidenceIntegrityError("manifest enum or timestamp is invalid") from error
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise EvidenceIntegrityError("manifest created_at must be timezone-aware")
    resource_id = _required_text(payload, "resource_id")
    try:
        _validate_resource_id(resource_type, resource_id)
    except ValueError as error:
        raise EvidenceIntegrityError("manifest resource ID is invalid") from error
    return resource_type, resource_id, created_at


def _manifest_record_schema(payload: Mapping[str, Any]) -> tuple[str, int]:
    record_schema = payload["record_schema"]
    if not isinstance(record_schema, dict) or set(record_schema) != {"id", "version"}:
        raise EvidenceIntegrityError("record_schema is invalid")
    schema_id = _required_text(record_schema, "id")
    schema_version = _required_int(record_schema, "version")
    if schema_version != 1:
        raise EvidenceIntegrityError("unsupported record schema version")
    return schema_id, schema_version


def _manifest_counts(payload: Mapping[str, Any]) -> tuple[int, int, int]:
    row_count = _required_int(payload, "row_count")
    canonical_bytes = _required_int(payload, "canonical_bytes")
    stored_bytes = _required_int(payload, "stored_bytes")
    if min(row_count, canonical_bytes, stored_bytes) < 0:
        raise EvidenceIntegrityError("manifest counts cannot be negative")
    return row_count, canonical_bytes, stored_bytes


def _validate_resource_id(resource_type: EvidenceResourceType, resource_id: str) -> None:
    if _RESOURCE_ID_PATTERN.fullmatch(resource_id) is None:
        raise ValueError("resource_id must be a bounded opaque prefixed identifier")
    expected_prefix = _RESOURCE_PREFIXES[resource_type]
    if not resource_id.startswith(expected_prefix):
        raise ValueError(f"resource_id must start with {expected_prefix}")


def _required_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceIntegrityError(f"{key} must be an integer")
    return value


def _required_hash(payload: Mapping[str, Any], key: str) -> str:
    value = _required_text(payload, key)
    if _HASH_PATTERN.fullmatch(value) is None:
        raise EvidenceIntegrityError(f"{key} must be a SHA-256 hash")
    return value


def _require_exact_keys(payload: Mapping[str, Any], expected: set[str], name: str) -> None:
    if set(payload) != expected:
        raise EvidenceIntegrityError(f"{name} fields do not match schema version 1")


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evidence timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
