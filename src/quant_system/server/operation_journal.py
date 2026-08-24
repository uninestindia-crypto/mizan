"""Durable, integrity-checked receipts for governed asynchronous operations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_system.server.schemas import OperationStatus, OperationType

_SCHEMA_ID = "quantos.server.operation_receipt"
_SCHEMA_VERSION = 1
_MAX_RECEIPT_BYTES = 1024 * 1024
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_OPERATION_ID_PATTERN = re.compile(r"op-[0-9a-f]{12}")


class OperationJournalError(RuntimeError):
    """Raised when durable operation state cannot be trusted or persisted."""


class OperationReceiptConflict(OperationJournalError):
    """Raised when one durable idempotency identity is bound to another intent."""


@dataclass(frozen=True)
class OperationReceipt:
    """Closed durable representation of one supervised operation."""

    operation_id: str
    operation_type: OperationType
    idempotency_key_hash: str
    request_fingerprint: str
    status: OperationStatus
    progress: float
    stage: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    cancellation_requested: bool = False

    def with_status(self, **changes: Any) -> OperationReceipt:
        """Return a new receipt with selected runtime fields replaced."""
        return replace(self, **changes)


class OperationJournal:
    """Atomically claims and updates idempotency receipts below one evidence root."""

    def __init__(self, evidence_root: Path) -> None:
        self._evidence_root = Path(os.path.abspath(evidence_root))
        self._directory = self._evidence_root / ".server" / "operation-receipts"

    def lookup(self, idempotency_key: str) -> OperationReceipt | None:
        """Load one existing receipt, failing closed on malformed durable state."""
        key_hash = _sha256_text(idempotency_key)
        path = self._receipt_path(key_hash)
        if not path.exists():
            return None
        return self._read(path, expected_key_hash=key_hash)

    def create(
        self,
        *,
        idempotency_key: str,
        operation_id: str,
        operation_type: OperationType,
        request_fingerprint: str,
        created_at: datetime,
    ) -> tuple[OperationReceipt, bool]:
        """Claim one key atomically, returning the existing receipt when another writer won."""
        key_hash = _sha256_text(idempotency_key)
        receipt = OperationReceipt(
            operation_id=operation_id,
            operation_type=operation_type,
            idempotency_key_hash=key_hash,
            request_fingerprint=request_fingerprint,
            status=OperationStatus.PENDING,
            progress=0.0,
            stage="INITIALIZING",
            created_at=_aware_utc(created_at),
        )
        path = self._receipt_path(key_hash)
        payload = _receipt_bytes(receipt)
        self._prepare_directory()
        try:
            _write_exclusive(path, payload)
        except FileExistsError:
            existing = self._read(path, expected_key_hash=key_hash)
            _validate_same_intent(existing, operation_type, request_fingerprint)
            return existing, False
        except OSError as error:
            raise OperationJournalError("durable operation receipt could not be claimed") from error
        return receipt, True

    def save(self, receipt: OperationReceipt) -> None:
        """Atomically replace one previously claimed receipt."""
        path = self._receipt_path(receipt.idempotency_key_hash)
        self._prepare_directory()
        if not path.is_file() or path.is_symlink():
            raise OperationJournalError("durable operation receipt is missing or unsafe")
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            _write_exclusive(temporary, _receipt_bytes(receipt))
            os.replace(temporary, path)
        except OSError as error:
            _remove_owned_temporary(temporary)
            raise OperationJournalError("durable operation receipt could not be updated") from error

    def _receipt_path(self, key_hash: str) -> Path:
        if _SHA256_PATTERN.fullmatch(key_hash) is None:
            raise OperationJournalError("durable idempotency identity is invalid")
        return self._directory / f"{key_hash}.json"

    def _prepare_directory(self) -> None:
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise OperationJournalError("durable operation directory is unavailable") from error
        for path in (self._evidence_root, self._directory.parent, self._directory):
            if path.is_symlink() or not path.is_dir():
                raise OperationJournalError("durable operation directory is unsafe")

    def _read(self, path: Path, *, expected_key_hash: str) -> OperationReceipt:
        if path.is_symlink() or not path.is_file():
            raise OperationJournalError("durable operation receipt is unsafe")
        try:
            with path.open("rb") as stream:
                contents = stream.read(_MAX_RECEIPT_BYTES + 1)
        except OSError as error:
            raise OperationJournalError("durable operation receipt cannot be read") from error
        if len(contents) > _MAX_RECEIPT_BYTES:
            raise OperationJournalError("durable operation receipt exceeds its size limit")
        receipt = _parse_receipt(contents)
        if receipt.idempotency_key_hash != expected_key_hash:
            raise OperationJournalError(
                "durable operation receipt identity does not match its path"
            )
        return receipt


def _validate_same_intent(
    receipt: OperationReceipt,
    operation_type: OperationType,
    request_fingerprint: str,
) -> None:
    if (
        receipt.operation_type is not operation_type
        or receipt.request_fingerprint != request_fingerprint
    ):
        raise OperationReceiptConflict(
            "the durable idempotency key already identifies a different operation intent"
        )


def _receipt_bytes(receipt: OperationReceipt) -> bytes:
    unsigned = _receipt_payload(receipt)
    envelope = dict(unsigned)
    envelope["receipt_hash"] = hashlib.sha256(_json_bytes(unsigned)).hexdigest()
    payload = _json_bytes(envelope)
    if len(payload) > _MAX_RECEIPT_BYTES:
        raise OperationJournalError("durable operation receipt exceeds its size limit")
    return payload


def _receipt_payload(receipt: OperationReceipt) -> dict[str, Any]:
    return {
        "cancellation_requested": receipt.cancellation_requested,
        "completed_at": _datetime_text(receipt.completed_at),
        "created_at": _datetime_text(receipt.created_at),
        "error": receipt.error,
        "idempotency_key_hash": receipt.idempotency_key_hash,
        "operation_id": receipt.operation_id,
        "operation_type": receipt.operation_type.value,
        "progress": format(receipt.progress, ".4f"),
        "request_fingerprint": receipt.request_fingerprint,
        "result": receipt.result,
        "schema_id": _SCHEMA_ID,
        "schema_version": _SCHEMA_VERSION,
        "stage": receipt.stage,
        "started_at": _datetime_text(receipt.started_at),
        "status": receipt.status.value,
    }


def _parse_receipt(contents: bytes) -> OperationReceipt:
    try:
        payload = json.loads(contents.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise OperationJournalError("durable operation receipt is not valid JSON") from error
    expected_fields = {
        "cancellation_requested",
        "completed_at",
        "created_at",
        "error",
        "idempotency_key_hash",
        "operation_id",
        "operation_type",
        "progress",
        "receipt_hash",
        "request_fingerprint",
        "result",
        "schema_id",
        "schema_version",
        "stage",
        "started_at",
        "status",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise OperationJournalError("durable operation receipt fields are invalid")
    observed_hash = payload.pop("receipt_hash")
    expected_hash = hashlib.sha256(_json_bytes(payload)).hexdigest()
    if observed_hash != expected_hash:
        raise OperationJournalError("durable operation receipt hash does not match")
    return _receipt_from_payload(payload)


def _receipt_from_payload(payload: dict[str, Any]) -> OperationReceipt:
    if payload.get("schema_id") != _SCHEMA_ID or payload.get("schema_version") != _SCHEMA_VERSION:
        raise OperationJournalError("durable operation receipt schema is unsupported")
    operation_id = payload.get("operation_id")
    key_hash = payload.get("idempotency_key_hash")
    fingerprint = payload.get("request_fingerprint")
    stage = payload.get("stage")
    cancellation_requested = payload.get("cancellation_requested")
    if not isinstance(operation_id, str) or _OPERATION_ID_PATTERN.fullmatch(operation_id) is None:
        raise OperationJournalError("durable operation ID is invalid")
    if not isinstance(key_hash, str) or _SHA256_PATTERN.fullmatch(key_hash) is None:
        raise OperationJournalError("durable idempotency identity is invalid")
    if not isinstance(fingerprint, str) or _SHA256_PATTERN.fullmatch(fingerprint) is None:
        raise OperationJournalError("durable request fingerprint is invalid")
    if not isinstance(stage, str) or not stage or len(stage) > 96:
        raise OperationJournalError("durable operation stage is invalid")
    if not isinstance(cancellation_requested, bool):
        raise OperationJournalError("durable cancellation state is invalid")
    try:
        progress = float(str(payload["progress"]))
        operation_type = OperationType(str(payload["operation_type"]))
        status = OperationStatus(str(payload["status"]))
    except (KeyError, TypeError, ValueError) as parse_error:
        raise OperationJournalError(
            "durable operation enum or progress is invalid"
        ) from parse_error
    if not 0.0 <= progress <= 1.0:
        raise OperationJournalError("durable operation progress is outside its contract")
    result = _optional_mapping(payload.get("result"), "result")
    error_payload = _optional_mapping(payload.get("error"), "error")
    created_at = _parse_datetime(payload.get("created_at"), "created_at", required=True)
    if created_at is None:
        raise OperationJournalError("durable operation created_at is required")
    return OperationReceipt(
        operation_id=operation_id,
        operation_type=operation_type,
        idempotency_key_hash=key_hash,
        request_fingerprint=fingerprint,
        status=status,
        progress=progress,
        stage=stage,
        created_at=created_at,
        started_at=_parse_datetime(payload.get("started_at"), "started_at"),
        completed_at=_parse_datetime(payload.get("completed_at"), "completed_at"),
        result=result,
        error=error_payload,
        cancellation_requested=cancellation_requested,
    )


def _parse_datetime(value: Any, field: str, *, required: bool = False) -> datetime | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise OperationJournalError(f"durable operation {field} is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise OperationJournalError(f"durable operation {field} is invalid") from error
    return _aware_utc(parsed)


def _optional_mapping(value: Any, field: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise OperationJournalError(f"durable operation {field} is invalid")
    return value


def _json_bytes(value: dict[str, Any]) -> bytes:
    try:
        serialized = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise OperationJournalError("durable operation receipt is not JSON-safe") from error
    return (serialized + "\n").encode("utf-8")


def _write_exclusive(path: Path, contents: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())


def _remove_owned_temporary(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _datetime_text(value: datetime | None) -> str | None:
    return _aware_utc(value).isoformat() if value is not None else None


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OperationJournalError("durable operation time must be timezone-aware")
    return value.astimezone(UTC)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")
