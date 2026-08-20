"""Deterministic point-in-time construction of the governed six-feature family."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.market_data import (
    DatasetStatus,
    HistoricalAcquisition,
    PointInTimeBar,
    SourceStatus,
)
from quant_system.data.market_data_evidence import canonical_sha256, utc_text
from quant_system.evidence import EvidenceIntegrityError
from quant_system.modeling.authorities import (
    HistoricalUniverseSnapshotV1,
    SessionCalendarV1,
    authority_is_effective,
    validate_authority_reference,
)
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.rows import (
    FEATURE_NAMES_V1,
    FEATURE_ROW_SCHEMA,
    FEATURE_SCHEMA_ID_V1,
    FEATURE_SCHEMA_VERSION_V1,
    FeatureDatasetV1,
    FeatureRowV1,
    decimal_result,
    derived_dataset_hash,
)

FEATURE_WARMUP_BARS_V1 = 21


def build_feature_dataset(
    acquisition: HistoricalAcquisition,
    candidate_id: str,
    calendar: SessionCalendarV1,
    universe: HistoricalUniverseSnapshotV1,
) -> FeatureDatasetV1:
    """Build deterministic feature evidence or reject the first invalid dependency."""
    _validate_governed_inputs(acquisition, calendar, universe)
    if len(acquisition.records) < FEATURE_WARMUP_BARS_V1:
        raise ModelingError(
            ModelingFailureCode.INSUFFICIENT_HISTORY,
            f"feature schema requires at least {FEATURE_WARMUP_BARS_V1} bars",
        )
    rows = tuple(
        _build_feature_row(acquisition, candidate_id, calendar, universe, ordinal)
        for ordinal in range(FEATURE_WARMUP_BARS_V1 - 1, len(acquisition.records))
    )
    manifest = acquisition.manifest
    corporate_authority = manifest.corporate_action_authority
    if corporate_authority is None:
        raise AssertionError("governed input validation must require corporate authority")
    unsigned_metadata = {
        "calendar_hash": calendar.reference.content_hash,
        "candidate_id": candidate_id,
        "corporate_action_authority_hash": corporate_authority.content_hash,
        "feature_schema_id": FEATURE_SCHEMA_ID_V1,
        "feature_schema_version": FEATURE_SCHEMA_VERSION_V1,
        "source_dataset_hash": manifest.manifest_hash,
        "source_dataset_id": manifest.dataset_id,
        "universe_authority_hash": universe.authority.content_hash,
    }
    dataset_hash = derived_dataset_hash(FEATURE_ROW_SCHEMA, unsigned_metadata, rows)
    return FeatureDatasetV1(
        dataset_id=f"dset_{dataset_hash[:24]}",
        dataset_hash=dataset_hash,
        candidate_id=candidate_id,
        source_dataset_id=manifest.dataset_id,
        source_dataset_hash=manifest.manifest_hash,
        calendar_hash=calendar.reference.content_hash,
        corporate_action_authority_hash=corporate_authority.content_hash,
        universe_authority_hash=universe.authority.content_hash,
        rows=rows,
    )


def _validate_governed_inputs(
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    universe: HistoricalUniverseSnapshotV1,
) -> None:
    try:
        draft_from_historical_acquisition(acquisition)
    except EvidenceIntegrityError as error:
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            str(error),
        ) from error
    manifest = acquisition.manifest
    if manifest.status != DatasetStatus.ACCEPTED or manifest.source_status != SourceStatus.COMPLETE:
        raise ModelingError(
            ModelingFailureCode.DATASET_NOT_GOVERNED,
            "features require an accepted complete acquisition",
        )
    if manifest.calendar is None:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISSING,
            "dataset has no versioned exchange calendar",
        )
    if manifest.calendar != calendar.reference:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "dataset calendar does not match the supplied sessions",
        )
    if manifest.corporate_action_authority is None:
        raise ModelingError(
            ModelingFailureCode.CORPORATE_ACTION_AUTHORITY_MISSING,
            "dataset has no corporate-action authority",
        )
    try:
        validate_authority_reference(
            manifest.corporate_action_authority,
            field_name="corporate-action authority",
        )
    except ValueError as error:
        raise ModelingError(
            ModelingFailureCode.CORPORATE_ACTION_AUTHORITY_INVALID,
            str(error),
        ) from error
    if manifest.historical_universe_authority is None:
        raise ModelingError(
            ModelingFailureCode.UNIVERSE_AUTHORITY_MISSING,
            "dataset has no historical-universe authority",
        )
    if manifest.historical_universe_authority != universe.authority:
        raise ModelingError(
            ModelingFailureCode.UNIVERSE_AUTHORITY_MISMATCH,
            "dataset universe reference does not match the supplied snapshot",
        )
    if not universe.contains(manifest.provider_instrument_id):
        raise ModelingError(
            ModelingFailureCode.UNIVERSE_MEMBER_INELIGIBLE,
            f"instrument is absent from historical universe: {manifest.provider_instrument_id}",
        )
    _validate_record_order(acquisition.records)
    _validate_complete_calendar_coverage(acquisition, calendar)
    _validate_session_and_authority_coverage(acquisition, calendar, universe)


def _validate_record_order(records: tuple[PointInTimeBar, ...]) -> None:
    dates = tuple(record.exchange_date for record in records)
    if tuple(sorted(set(dates))) == dates:
        return
    offending = _first_nonascending_record(records)
    raise ModelingError(
        ModelingFailureCode.RECORD_ORDER_INVALID,
        "market records must be unique and strictly chronological",
        offending_record_key=_record_key(offending),
    )


def _first_nonascending_record(records: tuple[PointInTimeBar, ...]) -> PointInTimeBar:
    for previous, current in zip(records[:-1], records[1:], strict=True):
        if current.exchange_date <= previous.exchange_date:
            return current
    raise AssertionError("nonascending record must exist")


def _validate_complete_calendar_coverage(
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
) -> None:
    manifest = acquisition.manifest
    expected_dates = tuple(
        session.exchange_date
        for session in calendar.sessions
        if manifest.requested_start <= session.exchange_date <= manifest.requested_end
    )
    observed_dates = tuple(record.exchange_date for record in acquisition.records)
    missing_dates = tuple(sorted(set(expected_dates) - set(observed_dates)))
    if missing_dates:
        missing = missing_dates[0]
        raise ModelingError(
            ModelingFailureCode.CALENDAR_SESSION_MISSING,
            f"complete acquisition is missing calendar session {missing.isoformat()}",
            offending_record_key=f"missing_session={missing.isoformat()}",
        )
    unexpected_dates = tuple(sorted(set(observed_dates) - set(expected_dates)))
    if unexpected_dates:
        unexpected = unexpected_dates[0]
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            f"complete acquisition contains unexpected session {unexpected.isoformat()}",
            offending_record_key=f"unexpected_session={unexpected.isoformat()}",
        )


def _validate_session_and_authority_coverage(
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    universe: HistoricalUniverseSnapshotV1,
) -> None:
    corporate_authority = acquisition.manifest.corporate_action_authority
    if corporate_authority is None:
        raise AssertionError("corporate authority must be present")
    for record in acquisition.records:
        session = calendar.session_for_date(record.exchange_date)
        if session is None:
            raise ModelingError(
                ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
                f"calendar has no session for {record.exchange_date.isoformat()}",
                offending_record_key=_record_key(record),
            )
        if not authority_is_effective(corporate_authority, record.exchange_date):
            raise ModelingError(
                ModelingFailureCode.CORPORATE_ACTION_AUTHORITY_NOT_EFFECTIVE,
                f"corporate-action authority is not effective on {record.exchange_date}",
                offending_record_key=_record_key(record),
            )
        if not universe.is_effective(record.exchange_date):
            raise ModelingError(
                ModelingFailureCode.UNIVERSE_AUTHORITY_NOT_EFFECTIVE,
                f"historical-universe authority is not effective on {record.exchange_date}",
                offending_record_key=_record_key(record),
            )


def _build_feature_row(
    acquisition: HistoricalAcquisition,
    candidate_id: str,
    calendar: SessionCalendarV1,
    universe: HistoricalUniverseSnapshotV1,
    ordinal: int,
) -> FeatureRowV1:
    current = acquisition.records[ordinal]
    session = calendar.session_for_date(current.exchange_date)
    if session is None:
        raise AssertionError("calendar coverage must be validated before feature construction")
    consumed = acquisition.records[: ordinal + 1]
    for record in consumed:
        if record.available_at > session.close_at:
            raise ModelingError(
                ModelingFailureCode.POINT_IN_TIME_VIOLATION,
                "feature input was not available by the decision time",
                offending_record_key=_record_key(record),
            )
    features = _six_features(consumed)
    preprocessing_input_hash = canonical_sha256(
        {
            "decision_at": utc_text(session.close_at),
            "feature_schema_id": FEATURE_SCHEMA_ID_V1,
            "feature_schema_version": FEATURE_SCHEMA_VERSION_V1,
            "records": [record.to_canonical_dict() for record in consumed],
        }
    )
    manifest = acquisition.manifest
    return FeatureRowV1(
        candidate_id=candidate_id,
        dataset_id=manifest.dataset_id,
        dataset_hash=manifest.manifest_hash,
        provider_instrument_id=manifest.provider_instrument_id,
        symbol=manifest.symbol,
        decision_at=session.close_at,
        information_cutoff_at=max(record.available_at for record in consumed),
        universe_authority_hash=universe.authority.content_hash,
        feature_schema_id=FEATURE_SCHEMA_ID_V1,
        feature_schema_version=FEATURE_SCHEMA_VERSION_V1,
        features=features,
        preprocessing_input_hash=preprocessing_input_hash,
    )


def _six_features(records: tuple[PointInTimeBar, ...]) -> dict[str, str]:
    closes = tuple(record.close for record in records)
    current = closes[-1]
    if current <= 0:
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "current close must be positive",
            offending_record_key=_record_key(records[-1]),
        )
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        values = (
            _return(current, closes[-2]),
            _return(current, closes[-6]),
            _return(current, closes[-11]),
            (_wilder_rsi(closes, 14) - Decimal(50)) / Decimal(50),
            (current - sum(closes[-20:]) / Decimal(20)) / current,
            _wilder_atr(records, 14) / current,
        )
        return {
            name: decimal_result(value)
            for name, value in zip(FEATURE_NAMES_V1, values, strict=True)
        }


def _return(current: Decimal, previous: Decimal) -> Decimal:
    if previous <= 0:
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "return denominator must be positive",
        )
    return (current - previous) / previous


def _wilder_rsi(closes: tuple[Decimal, ...], period: int) -> Decimal:
    deltas = tuple(
        current - previous for previous, current in zip(closes[:-1], closes[1:], strict=True)
    )
    gains = tuple(max(Decimal(0), delta) for delta in deltas)
    losses = tuple(max(Decimal(0), -delta) for delta in deltas)
    average_gain = sum(gains[:period]) / Decimal(period)
    average_loss = sum(losses[:period]) / Decimal(period)
    for gain, loss in zip(gains[period:], losses[period:], strict=True):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
    if average_loss == 0:
        return Decimal(50) if average_gain == 0 else Decimal(100)
    relative_strength = average_gain / average_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + relative_strength)


def _wilder_atr(records: tuple[PointInTimeBar, ...], period: int) -> Decimal:
    true_ranges = [records[0].high - records[0].low]
    true_ranges.extend(
        _true_range(record, previous.close)
        for previous, record in zip(records[:-1], records[1:], strict=True)
    )
    average = sum(true_ranges[:period]) / Decimal(period)
    for true_range in true_ranges[period:]:
        average = (average * (period - 1) + true_range) / period
    return average


def _true_range(record: PointInTimeBar, previous_close: Decimal) -> Decimal:
    return max(
        record.high - record.low,
        abs(record.high - previous_close),
        abs(record.low - previous_close),
    )


def _record_key(record: PointInTimeBar) -> str:
    return (
        f"provider_instrument_id={record.provider_instrument_id},"
        f"exchange_date={record.exchange_date.isoformat()},"
        f"source_row_index={record.source_row_index}"
    )
