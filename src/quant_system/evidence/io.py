"""Bounded deterministic filesystem and compression primitives."""

from __future__ import annotations

import gzip
import io
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_system.evidence.canonical import canonical_json_bytes, parse_canonical_json, sha256_hex
from quant_system.evidence.errors import (
    EvidenceConflict,
    EvidenceIntegrityError,
)
from quant_system.evidence.models import ActiveReference, EvidenceIdentity, EvidenceResourceType


def deterministic_gzip(contents: bytes) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", compresslevel=9, mtime=0) as stream:
        stream.write(contents)
    return output.getvalue()


def decompress_bounded(contents: bytes, expected_bytes: int) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(contents), mode="rb") as stream:
            decompressed = stream.read(expected_bytes + 1)
    except (OSError, EOFError) as error:
        raise EvidenceIntegrityError("blob gzip stream is invalid") from error
    if len(decompressed) != expected_bytes:
        raise EvidenceIntegrityError("canonical blob size does not match")
    return decompressed


def parse_jsonl(contents: bytes) -> list[dict[str, Any]]:
    if not contents.endswith(b"\n"):
        raise EvidenceIntegrityError("canonical JSONL must end with a newline")
    records: list[dict[str, Any]] = []
    for index, line in enumerate(contents.splitlines(keepends=True)):
        parsed = parse_canonical_json(line, description=f"JSONL record {index}")
        if not isinstance(parsed, dict):
            raise EvidenceIntegrityError("canonical JSONL record must be an object")
        records.append(parsed)
    return records


def parse_active_reference(payload: Any, purpose: str) -> ActiveReference:
    if not isinstance(payload, dict) or set(payload) != {
        "purpose",
        "reference_hash",
        "schema_id",
        "schema_version",
        "target",
        "updated_at",
    }:
        raise EvidenceIntegrityError("active reference fields are invalid")
    if payload["schema_id"] != "quantos.active_reference" or payload["schema_version"] != 1:
        raise EvidenceIntegrityError("active reference schema is invalid")
    unsigned = dict(payload)
    observed_hash = unsigned.pop("reference_hash")
    if (
        not isinstance(observed_hash, str)
        or sha256_hex(canonical_json_bytes(unsigned)) != observed_hash
    ):
        raise EvidenceIntegrityError("active reference hash does not match")
    target = payload["target"]
    if not isinstance(target, dict) or set(target) != {
        "manifest_hash",
        "resource_id",
        "resource_type",
    }:
        raise EvidenceIntegrityError("active reference target is invalid")
    try:
        identity = EvidenceIdentity(
            EvidenceResourceType(target["resource_type"]),
            str(target["resource_id"]),
            str(target["manifest_hash"]),
        )
        updated_at = datetime.fromisoformat(str(payload["updated_at"]).replace("Z", "+00:00"))
        reference = ActiveReference(str(payload["purpose"]), identity, updated_at, observed_hash)
    except (ValueError, TypeError) as error:
        raise EvidenceIntegrityError("active reference values are invalid") from error
    if reference.purpose != purpose:
        raise EvidenceIntegrityError("active reference purpose does not match its path")
    return reference


def write_fsynced(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlink(path.parent)
    try:
        with path.open("xb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise EvidenceConflict(f"staged evidence path already exists: {path.name}") from error


def read_bounded(path: Path, expected_or_limit: int, *, description: str) -> bytes:
    reject_symlink(path)
    try:
        with path.open("rb") as stream:
            contents = stream.read(expected_or_limit + 1)
    except FileNotFoundError as error:
        raise EvidenceIntegrityError(f"{description} is missing") from error
    if len(contents) > expected_or_limit:
        raise EvidenceIntegrityError(f"{description} exceeds its declared size")
    return contents


def reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise EvidenceIntegrityError(f"symbolic links are forbidden in evidence paths: {path.name}")


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evidence clock must be timezone-aware")
    return value.astimezone(UTC)
