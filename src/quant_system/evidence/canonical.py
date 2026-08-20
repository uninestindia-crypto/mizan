"""Canonical JSON and JSONL primitives for evidence hashing."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, NoReturn

from quant_system.data.market_data_evidence import decimal_text
from quant_system.evidence.errors import (
    CanonicalizationError,
    EvidenceIntegrityError,
    EvidenceSensitiveData,
)

MAX_CANONICAL_DEPTH = 32
_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "password",
    "private_key",
    "refresh_token",
    "secret",
}
_KEY_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")


def canonicalize(value: Any, *, path: str = "$", depth: int = 0) -> Any:
    """Return the closed canonical JSON value or fail on ambiguous input."""
    if depth > MAX_CANONICAL_DEPTH:
        raise CanonicalizationError(f"canonical value exceeds depth at {path}")
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        raise CanonicalizationError(f"float is forbidden in canonical evidence at {path}")
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return _canonical_mapping(value, path=path, depth=depth)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | memoryview):
        return [
            canonicalize(item, path=f"{path}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        ]
    raise CanonicalizationError(f"unsupported canonical type at {path}: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    normalized = canonicalize(value)
    try:
        serialized = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise CanonicalizationError(
            "canonical value cannot be encoded within runtime limits"
        ) from error
    return (serialized + "\n").encode("utf-8")


def parse_canonical_json(contents: bytes, *, description: str) -> Any:
    try:
        decoded = contents.decode("utf-8")
        parsed = json.loads(
            decoded,
            parse_float=_reject_json_float,
            parse_constant=_reject_json_constant,
        )
        recanonicalized = canonical_json_bytes(parsed)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        CanonicalizationError,
        TypeError,
        ValueError,
    ) as error:
        raise EvidenceIntegrityError(f"{description} is not valid canonical JSON") from error
    if recanonicalized != contents:
        raise EvidenceIntegrityError(f"{description} is not canonically encoded")
    return parsed


def sha256_hex(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def reject_sensitive_keys(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        _reject_sensitive_mapping(value, path)
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        _reject_sensitive_sequence(value, path)


def strict_order_key(record: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[Any, ...]:
    values: list[Any] = []
    for field in fields:
        if field not in record:
            raise EvidenceIntegrityError(f"total-order field is missing: {field}")
        values.append(_order_token(record[field], field))
    return tuple(values)


def validate_strict_total_order(
    records: Sequence[Mapping[str, Any]],
    fields: tuple[str, ...],
) -> None:
    previous: tuple[Any, ...] | None = None
    for record in records:
        current = strict_order_key(record, fields)
        if previous is not None and current <= previous:
            raise EvidenceIntegrityError("records must follow one unique strict total order")
        previous = current


# craft-allow: many-params - checker counts the keyword-only separator and annotations; there are three inputs.
def _canonical_mapping(value: Mapping[Any, Any], *, path: str, depth: int) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for raw_key, child in value.items():
        if not isinstance(raw_key, str):
            raise CanonicalizationError(f"canonical object key must be text at {path}")
        key = unicodedata.normalize("NFC", raw_key)
        if key in normalized:
            raise CanonicalizationError(f"canonical object has duplicate normalized key at {path}")
        normalized[key] = canonicalize(child, path=f"{path}.{key}", depth=depth + 1)
    return normalized


def _reject_sensitive_mapping(value: Mapping[Any, Any], path: str) -> None:
    for key, child in value.items():
        normalized = _KEY_SEPARATOR_PATTERN.sub("_", str(key).lower()).strip("_")
        padded_key = f"_{normalized}_"
        if any(f"_{sensitive_key}_" in padded_key for sensitive_key in _SENSITIVE_KEYS):
            raise EvidenceSensitiveData(f"secret-shaped field is forbidden: {path}.{key}")
        reject_sensitive_keys(child, path=f"{path}.{key}")


def _reject_sensitive_sequence(value: Sequence[Any], path: str) -> None:
    for index, child in enumerate(value):
        reject_sensitive_keys(child, path=f"{path}[{index}]")


def _order_token(value: Any, field: str) -> tuple[int, Any]:
    if value is None:
        return 0, 0
    if isinstance(value, bool):
        return 1, int(value)
    if isinstance(value, int):
        return 2, value
    if isinstance(value, Decimal):
        return 3, value
    if isinstance(value, str):
        return 4, unicodedata.normalize("NFC", value)
    raise EvidenceIntegrityError(f"total-order field has unsupported type: {field}")


def _reject_json_float(value: str) -> NoReturn:
    raise CanonicalizationError(f"float is forbidden: {value}")


def _reject_json_constant(value: str) -> NoReturn:
    raise CanonicalizationError(f"non-finite number is forbidden: {value}")
