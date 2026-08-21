"""Immutable evidence contracts for chronological model-validation folds."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from quant_system.data.market_data_evidence import utc_text
from quant_system.modeling.rows import LabelRowV1

_FOLD_PATTERN = re.compile(r"fold_[a-z0-9][a-z0-9_-]{0,91}")
_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class FoldSpecV1:
    fold_id: str
    ordinal: int
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    purge_start: datetime
    purge_end: datetime
    embargo_sessions: int
    label_horizon_sessions: int
    train_row_count: int
    validation_row_count: int
    train_class_balance: Mapping[str, int]
    validation_class_balance: Mapping[str, int]
    train_hash: str
    validation_hash: str

    def __post_init__(self) -> None:
        if _FOLD_PATTERN.fullmatch(self.fold_id) is None:
            raise ValueError("fold_id is invalid")
        for name in (
            "ordinal",
            "embargo_sessions",
            "label_horizon_sessions",
            "train_row_count",
            "validation_row_count",
        ):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an exact integer")
        if self.ordinal < 1:
            raise ValueError("fold ordinal must be positive")
        _require_hash(self.train_hash, "train_hash")
        _require_hash(self.validation_hash, "validation_hash")
        object.__setattr__(
            self,
            "train_class_balance",
            MappingProxyType(dict(self.train_class_balance)),
        )
        object.__setattr__(
            self,
            "validation_class_balance",
            MappingProxyType(dict(self.validation_class_balance)),
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "embargo_sessions": self.embargo_sessions,
            "fold_id": self.fold_id,
            "label_horizon_sessions": self.label_horizon_sessions,
            "ordinal": self.ordinal,
            "purge_end": utc_text(self.purge_end),
            "purge_start": utc_text(self.purge_start),
            "train_class_balance": dict(self.train_class_balance),
            "train_end": utc_text(self.train_end),
            "train_hash": self.train_hash,
            "train_row_count": self.train_row_count,
            "train_start": utc_text(self.train_start),
            "validation_class_balance": dict(self.validation_class_balance),
            "validation_end": utc_text(self.validation_end),
            "validation_hash": self.validation_hash,
            "validation_row_count": self.validation_row_count,
            "validation_start": utc_text(self.validation_start),
        }


@dataclass(frozen=True, slots=True)
class PartitionedFoldV1:
    spec: FoldSpecV1
    train_rows: tuple[LabelRowV1, ...]
    validation_rows: tuple[LabelRowV1, ...]
    purged_record_keys: tuple[str, ...]
    embargoed_record_keys: tuple[str, ...]


def _require_hash(value: str, field_name: str) -> None:
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a SHA-256 hash")
