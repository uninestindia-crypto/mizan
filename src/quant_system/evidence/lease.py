"""Exclusive cross-process mutation lease for evidence publication."""

from __future__ import annotations

import os
import re
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_system.evidence.canonical import canonical_json_bytes, parse_canonical_json
from quant_system.evidence.errors import EvidenceBusy, EvidenceIntegrityError

_LEASE_MAX_BYTES = 4096
_LEASE_POLL_SECONDS = 0.025
_TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}")


@dataclass(frozen=True, slots=True)
class LeaseRecord:
    operation_id: str
    pid: int
    process_identity: str
    acquired_at: str
    heartbeat_at: str
    token: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "acquired_at": self.acquired_at,
            "heartbeat_at": self.heartbeat_at,
            "operation_id": self.operation_id,
            "pid": self.pid,
            "process_identity": self.process_identity,
            "schema_id": "quantos.evidence_lease",
            "schema_version": 1,
            "token": self.token,
        }


class LeaseHandle(AbstractContextManager[LeaseRecord]):
    def __init__(self, path: Path, record: LeaseRecord) -> None:
        self._path = path
        self._record = record

    def __enter__(self) -> LeaseRecord:
        return self._record

    def heartbeat(self, now: datetime) -> None:
        try:
            current = _read_lease(self._path)
        except FileNotFoundError as error:
            raise EvidenceIntegrityError("evidence lease disappeared during mutation") from error
        if current.token != self._record.token:
            raise EvidenceIntegrityError("evidence lease ownership changed unexpectedly")
        updated = replace(self._record, heartbeat_at=_utc_text(now))
        temporary = self._path.with_name(f".{self._path.name}.{uuid.uuid4().hex}.tmp")
        try:
            _write_new_lease(temporary, updated)
            os.replace(temporary, self._path)
        finally:
            temporary.unlink(missing_ok=True)
        self._record = updated

    def __exit__(self, _exc_type: Any, _exc_value: Any, _traceback: Any) -> None:
        try:
            current = _read_lease(self._path)
        except FileNotFoundError:
            return
        if current.token != self._record.token:
            raise EvidenceIntegrityError("evidence lease ownership changed unexpectedly")
        self._path.unlink()


class LeaseManager:
    def __init__(
        self,
        path: Path,
        *,
        wait_seconds: float = 0.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.path = path
        self.wait_seconds = wait_seconds
        self._monotonic = monotonic
        self._sleep = sleep

    def acquire(self, operation_id: str, now: datetime) -> LeaseHandle:
        if not operation_id or len(operation_id) > 128:
            raise ValueError("operation_id must contain 1-128 characters")
        timestamp = _utc_text(now)
        record = LeaseRecord(
            operation_id=operation_id,
            pid=os.getpid(),
            process_identity=_current_process_identity(),
            acquired_at=timestamp,
            heartbeat_at=timestamp,
            token=uuid.uuid4().hex,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = self._monotonic() + self.wait_seconds
        while True:
            try:
                _write_new_lease(self.path, record)
            except FileExistsError as error:
                if self._monotonic() >= deadline:
                    owner = _read_lease(self.path)
                    raise EvidenceBusy(
                        f"evidence mutation is owned by {owner.operation_id} "
                        f"(pid {owner.pid}); waited {self.wait_seconds:g}s"
                    ) from error
                self._sleep(_LEASE_POLL_SECONDS)
                continue
            return LeaseHandle(self.path, record)


def recover_stale_lease(path: Path, quarantine_directory: Path) -> int:
    if not path.exists():
        return 0
    record = _read_lease(path)
    if _process_matches(record.pid, record.process_identity):
        raise EvidenceBusy(
            f"live evidence mutation is owned by {record.operation_id} (pid {record.pid})"
        )
    quarantine_directory.mkdir(parents=True, exist_ok=True)
    target = quarantine_directory / f"lease-{uuid.uuid4().hex}.json"
    os.replace(path, target)
    return 1


def _read_lease(path: Path) -> LeaseRecord:
    if path.is_symlink():
        raise EvidenceIntegrityError("evidence lease cannot be a symbolic link")
    try:
        with path.open("rb") as stream:
            contents = stream.read(_LEASE_MAX_BYTES + 1)
        if len(contents) > _LEASE_MAX_BYTES:
            raise EvidenceIntegrityError("evidence lease exceeds its size limit")
        payload = parse_canonical_json(contents, description="evidence lease")
        if not isinstance(payload, dict):
            raise ValueError("lease object")
        if set(payload) != {
            "acquired_at",
            "heartbeat_at",
            "operation_id",
            "pid",
            "process_identity",
            "schema_id",
            "schema_version",
            "token",
        }:
            raise ValueError("lease fields")
        if payload["schema_id"] != "quantos.evidence_lease" or payload["schema_version"] != 1:
            raise ValueError("lease schema")
        record = LeaseRecord(
            operation_id=str(payload["operation_id"]),
            pid=int(payload["pid"]),
            process_identity=str(payload["process_identity"]),
            acquired_at=str(payload["acquired_at"]),
            heartbeat_at=str(payload["heartbeat_at"]),
            token=str(payload["token"]),
        )
        _validate_lease_record(record)
        return record
    except EvidenceIntegrityError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceIntegrityError("evidence lease is malformed") from error


def _current_process_identity() -> str:
    if os.name == "nt":
        return _windows_process_identity(os.getpid()) or f"pid:{os.getpid()}"
    try:
        return Path(f"/proc/{os.getpid()}/stat").read_text(encoding="utf-8").split()[21]
    except (OSError, IndexError):
        return f"pid:{os.getpid()}"


def _write_new_lease(path: Path, record: LeaseRecord) -> None:
    descriptor = os.open(
        path,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json_bytes(record.to_dict()))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("lease timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _validate_lease_record(record: LeaseRecord) -> None:
    if not 1 <= len(record.operation_id) <= 128 or record.pid <= 0:
        raise ValueError("lease operation or PID")
    if not record.process_identity or _TOKEN_PATTERN.fullmatch(record.token) is None:
        raise ValueError("lease process identity or token")
    acquired_at = datetime.fromisoformat(record.acquired_at.replace("Z", "+00:00"))
    heartbeat_at = datetime.fromisoformat(record.heartbeat_at.replace("Z", "+00:00"))
    if acquired_at.tzinfo is None or heartbeat_at.tzinfo is None:
        raise ValueError("lease timestamps must be timezone-aware")
    if heartbeat_at < acquired_at:
        raise ValueError("lease heartbeat predates acquisition")


def _process_matches(pid: int, identity: str) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        observed = _windows_process_identity(pid)
        return observed is not None and observed == identity
    try:
        observed = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[21]
    except (OSError, IndexError):
        return False
    return observed == identity


def _windows_process_identity(pid: int) -> str | None:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        exit_code = wintypes.DWORD()
        if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        if exit_code.value != 259:  # STILL_ACTIVE
            return None
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        success = ctypes.windll.kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        )
        if not success:
            return None
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return str(ticks)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
