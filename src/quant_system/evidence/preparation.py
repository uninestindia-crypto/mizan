"""Canonical preparation and deterministic chunking for evidence drafts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from quant_system.evidence.canonical import (
    canonical_json_bytes,
    canonicalize,
    reject_sensitive_keys,
    sha256_hex,
    validate_strict_total_order,
)
from quant_system.evidence.errors import EvidenceIntegrityError, EvidenceLimitExceeded
from quant_system.evidence.io import deterministic_gzip
from quant_system.evidence.models import (
    BlobDescriptor,
    EvidenceDraft,
    EvidenceStoreConfig,
)


@dataclass(frozen=True, slots=True)
class PreparedBlob:
    descriptor: BlobDescriptor
    canonical: bytes
    stored: bytes


@dataclass(frozen=True, slots=True)
class PreparedDraft:
    metadata: dict[str, Any]
    records: tuple[dict[str, Any], ...]
    blobs: tuple[PreparedBlob, ...]
    canonical_records_hash: str
    canonical_bytes: int
    stored_bytes: int


def prepare_draft(draft: EvidenceDraft, config: EvidenceStoreConfig) -> PreparedDraft:
    metadata = canonicalize(draft.metadata, path="$.metadata")
    if not isinstance(metadata, dict):
        raise EvidenceIntegrityError("evidence metadata must be an object")
    reject_sensitive_keys(metadata, path="$.metadata")
    metadata_size = len(canonical_json_bytes(metadata))
    if metadata_size > config.max_manifest_bytes:
        raise EvidenceLimitExceeded(
            f"canonical metadata is {metadata_size} bytes; limit is {config.max_manifest_bytes}"
        )
    records: list[dict[str, Any]] = []
    lines: list[bytes] = []
    for index, raw_record in enumerate(draft.records):
        normalized = canonicalize(raw_record, path=f"$.records[{index}]")
        if not isinstance(normalized, dict):
            raise EvidenceIntegrityError("every evidence record must be an object")
        reject_sensitive_keys(normalized, path=f"$.records[{index}]")
        records.append(normalized)
        lines.append(canonical_json_bytes(normalized))
    validate_strict_total_order(records, draft.total_order)
    total_size = sum(map(len, lines))
    if total_size > config.max_bundle_bytes:
        raise EvidenceLimitExceeded(
            f"canonical evidence is {total_size} bytes; limit is {config.max_bundle_bytes}"
        )
    blobs = _chunk(lines, config.chunk_uncompressed_bytes)
    combined = b"".join(lines)
    return PreparedDraft(
        metadata=metadata,
        records=tuple(records),
        blobs=blobs,
        canonical_records_hash=sha256_hex(combined),
        canonical_bytes=total_size,
        stored_bytes=sum(blob.descriptor.stored_bytes for blob in blobs),
    )


def _chunk(lines: Sequence[bytes], chunk_bytes: int) -> tuple[PreparedBlob, ...]:
    chunks: list[bytes] = []
    current = bytearray()
    for line in lines:
        if len(line) > chunk_bytes:
            raise EvidenceLimitExceeded("one canonical record exceeds the chunk-size limit")
        if current and len(current) + len(line) > chunk_bytes:
            chunks.append(bytes(current))
            current.clear()
        current.extend(line)
    if current:
        chunks.append(bytes(current))
    prepared: list[PreparedBlob] = []
    for ordinal, canonical in enumerate(chunks):
        stored = deterministic_gzip(canonical)
        stored_hash = sha256_hex(stored)
        descriptor = BlobDescriptor(
            ordinal=ordinal,
            row_count=canonical.count(b"\n"),
            canonical_bytes=len(canonical),
            stored_bytes=len(stored),
            canonical_hash=sha256_hex(canonical),
            stored_hash=stored_hash,
            relative_path=f"blobs/sha256/{stored_hash[:2]}/{stored_hash}.jsonl.gz",
        )
        prepared.append(PreparedBlob(descriptor, canonical, stored))
    return tuple(prepared)
