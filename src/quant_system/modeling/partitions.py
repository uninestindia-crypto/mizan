"""Purged expanding-window folds with a session-count embargo."""

from __future__ import annotations

from datetime import datetime

from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.modeling.authorities import SessionCalendarV1
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.folds import FoldSpecV1, PartitionedFoldV1
from quant_system.modeling.rows import (
    LABEL_HORIZON_SESSIONS_V1,
    LabelRowV1,
)


def build_purged_fold(
    rows: tuple[LabelRowV1, ...],
    *,
    fold_id: str,
    ordinal: int,
    validation_start: datetime,
    validation_end: datetime,
    calendar: SessionCalendarV1,
    embargo_sessions: int,
) -> PartitionedFoldV1:
    """Partition one chronological label stream and record every removed row."""
    _validate_partition_inputs(
        rows,
        validation_start,
        validation_end,
        embargo_sessions,
        calendar,
    )
    validation_ordinal = calendar.ordinal_for_close(validation_start)
    if validation_ordinal is None:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "validation start must be an exchange-session close",
        )
    embargo_closes = {
        session.close_at
        for session in calendar.sessions[
            max(0, validation_ordinal - embargo_sessions) : validation_ordinal
        ]
    }
    validation_rows = tuple(
        row for row in rows if validation_start <= row.decision_at <= validation_end
    )
    candidates = tuple(row for row in rows if row.decision_at < validation_start)
    purged = tuple(row for row in candidates if row.exit_at >= validation_start)
    purge_keys = {row.record_key for row in purged}
    after_purge = tuple(row for row in candidates if row.record_key not in purge_keys)
    embargoed = tuple(row for row in after_purge if row.decision_at in embargo_closes)
    embargo_keys = {row.record_key for row in embargoed}
    train_rows = tuple(row for row in after_purge if row.record_key not in embargo_keys)
    if not train_rows or not validation_rows:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "partition must retain non-empty training and validation rows",
        )
    removed = tuple(sorted((*purged, *embargoed), key=lambda row: (row.decision_at, row.symbol)))
    purge_start = removed[0].decision_at if removed else validation_start
    spec = FoldSpecV1(
        fold_id=fold_id,
        ordinal=ordinal,
        train_start=train_rows[0].decision_at,
        train_end=train_rows[-1].decision_at,
        validation_start=validation_start,
        validation_end=validation_end,
        purge_start=purge_start,
        purge_end=validation_start,
        embargo_sessions=embargo_sessions,
        label_horizon_sessions=LABEL_HORIZON_SESSIONS_V1,
        train_row_count=len(train_rows),
        validation_row_count=len(validation_rows),
        train_class_balance=_class_balance(train_rows),
        validation_class_balance=_class_balance(validation_rows),
        train_hash=_rows_hash(train_rows),
        validation_hash=_rows_hash(validation_rows),
    )
    return PartitionedFoldV1(
        spec=spec,
        train_rows=train_rows,
        validation_rows=validation_rows,
        purged_record_keys=tuple(row.record_key for row in purged),
        embargoed_record_keys=tuple(row.record_key for row in embargoed),
    )


def _validate_partition_inputs(
    rows: tuple[LabelRowV1, ...],
    validation_start: datetime,
    validation_end: datetime,
    embargo_sessions: int,
    calendar: SessionCalendarV1,
) -> None:
    if not rows:
        raise ModelingError(ModelingFailureCode.PARTITION_INVALID, "label rows cannot be empty")
    if validation_start.tzinfo is None or validation_start.utcoffset() is None:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "validation_start must be timezone-aware",
        )
    if validation_end.tzinfo is None or validation_end.utcoffset() is None:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "validation_end must be timezone-aware",
        )
    if validation_start > validation_end:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "validation start must not follow validation end",
        )
    if embargo_sessions < LABEL_HORIZON_SESSIONS_V1:
        raise ModelingError(
            ModelingFailureCode.EMBARGO_TOO_SHORT,
            "embargo must be at least the maximum label horizon",
        )
    keys = tuple((row.decision_at, row.symbol) for row in rows)
    if tuple(sorted(set(keys))) != keys:
        raise ModelingError(
            ModelingFailureCode.RECORD_ORDER_INVALID,
            "label rows must be unique and strictly chronological",
        )
    if len({row.candidate_id for row in rows}) != 1:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "one fold cannot mix candidate identities",
        )
    if calendar.ordinal_for_close(validation_start) is None:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "validation start must be an exchange-session close",
        )
    if calendar.ordinal_for_close(validation_end) is None:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "validation end must be an exchange-session close",
        )
    for row in rows:
        decision_ordinal = calendar.ordinal_for_close(row.decision_at)
        if decision_ordinal is None or decision_ordinal + 2 >= len(calendar.sessions):
            raise ModelingError(
                ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
                "label chronology is not represented by the supplied calendar",
                offending_record_key=row.record_key,
            )
        if (
            row.entry_at != calendar.sessions[decision_ordinal + 1].open_at
            or row.exit_at != calendar.sessions[decision_ordinal + 2].open_at
        ):
            raise ModelingError(
                ModelingFailureCode.PARTITION_INVALID,
                "label does not use the next two eligible session opens",
                offending_record_key=row.record_key,
            )


def _rows_hash(rows: tuple[LabelRowV1, ...]) -> str:
    return canonical_sha256(
        {
            "records": [row.to_canonical_dict() for row in rows],
            "schema_id": "quantos.fold_label_rows",
            "schema_version": 1,
        }
    )


def _class_balance(rows: tuple[LabelRowV1, ...]) -> dict[str, int]:
    return {
        "DOWN": sum(row.target == "DOWN" for row in rows),
        "UP": sum(row.target == "UP" for row in rows),
    }
