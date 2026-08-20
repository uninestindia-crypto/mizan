"""Canonical scalar serialization and hashing for market-data evidence."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def canonical_sha256(payload: Any) -> str:
    """Hash canonical UTF-8 JSON after Unicode normalization."""
    canonical_text = json.dumps(
        _normalize_text(payload),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(f"{canonical_text}\n".encode()).hexdigest()


def raw_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("canonical decimals must be finite")
    fixed = format(value, "f")
    if "." in fixed:
        fixed = fixed.rstrip("0").rstrip(".")
    return "0" if fixed in {"-0", ""} else fixed


def utc_text(value: datetime) -> str:
    utc_value = value.astimezone(UTC)
    return utc_value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _normalize_text(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {str(key): _normalize_text(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_text(item) for item in value]
    return value
