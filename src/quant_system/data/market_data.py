"""Point-in-time market-data contracts and canonical evidence hashing."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from quant_system.core.domain import PriceBar
from quant_system.data.adjustment_provenance import AdjustmentReference
from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text

DATASET_MANIFEST_SCHEMA = "quantos.dataset_manifest"
DATASET_MANIFEST_VERSION = 1
"""Provider values. The ``adjustment`` block is the fixed ``PROVIDER_UNSPECIFIED``/``RAW`` literal.

Emitted whenever ``DatasetManifest.adjustment`` is ``None``, which is every manifest already written
to this repository. The payload is unchanged, so their hashes are unchanged.
"""

DATASET_MANIFEST_VERSION_ADJUSTED = 2
"""Derived values. The ``adjustment`` block is a full
:class:`~quant_system.data.adjustment_provenance.AdjustmentReference`.

The version distinguishes the two payload *shapes*, so a reader never has to guess whether the
``adjustment`` block is a placeholder literal or real provenance -- and a derived dataset can no
longer masquerade as a raw one.
"""
BAR_RECORD_SCHEMA = "quantos.point_in_time_bar"
BAR_RECORD_VERSION = 1
UPSTOX_HISTORICAL_SOURCE = "UPSTOX_HISTORICAL"
UPSTOX_PROVIDER = "UPSTOX"
UPSTOX_HISTORICAL_API_VERSION = "v3"
UPSTOX_HISTORICAL_ENDPOINT = "historical-candle"
UPSTOX_HISTORICAL_DOCUMENTATION = (
    "https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/"
)

_SYMBOL_PATTERN = re.compile(r"[A-Z0-9&-]{1,20}")
_NSE_EQUITY_KEY_PATTERN = re.compile(r"NSE_EQ\|[A-Z0-9]{12}")


class DatasetStatus(StrEnum):
    """Whether accepted evidence is complete enough for governed use."""

    ACCEPTED = "ACCEPTED"
    PARTIAL = "PARTIAL"


class SourceStatus(StrEnum):
    """Completeness of the provider response for the requested range."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"


class FindingSeverity(StrEnum):
    """Impact of a data-quality finding."""

    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class FindingDisposition(StrEnum):
    """Treatment applied to a detected quality finding."""

    NONE = "NONE"
    REJECTED = "REJECTED"
    REPAIRED = "REPAIRED"


class QualityCode(StrEnum):
    """Stable market-data quality codes."""

    REVERSE_ORDER = "REVERSE_ORDER"
    DUPLICATE_KEY = "DUPLICATE_KEY"
    INVALID_OHLC = "INVALID_OHLC"
    INVALID_VOLUME = "INVALID_VOLUME"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    NOT_AVAILABLE_AT_ACQUISITION = "NOT_AVAILABLE_AT_ACQUISITION"
    OUT_OF_REQUEST_RANGE = "OUT_OF_REQUEST_RANGE"
    NON_SESSION_DATE = "NON_SESSION_DATE"
    PROVIDER_RANGE_UNAVAILABLE = "PROVIDER_RANGE_UNAVAILABLE"
    CORPORATE_ACTION_AUTHORITY_UNRESOLVED = "CORPORATE_ACTION_AUTHORITY_UNRESOLVED"
    HISTORICAL_UNIVERSE_AUTHORITY_UNRESOLVED = "HISTORICAL_UNIVERSE_AUTHORITY_UNRESOLVED"
    CALENDAR_UNRESOLVED = "CALENDAR_UNRESOLVED"


class AcquisitionFailureCode(StrEnum):
    """Stable typed outcomes for a failed provider acquisition."""

    PROVIDER_UNAUTHORIZED = "PROVIDER_UNAUTHORIZED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    PROVIDER_MALFORMED = "PROVIDER_MALFORMED"
    PROVIDER_SCHEMA_DRIFT = "PROVIDER_SCHEMA_DRIFT"
    DATASET_EMPTY = "DATASET_EMPTY"
    DATA_QUALITY_BLOCKED = "DATA_QUALITY_BLOCKED"


@dataclass(frozen=True, slots=True)
class AuthorityReference:
    """Effective-dated source authority used by a governed dataset."""

    authority_id: str
    source_url: str
    publication_date: date
    effective_from: date
    effective_to: date | None
    version: str
    content_hash: str

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "authority_id": self.authority_id,
            "content_hash": self.content_hash,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "publication_date": self.publication_date.isoformat(),
            "source_url": self.source_url,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class CalendarReference:
    """Versioned exchange-session calendar evidence."""

    calendar_id: str
    version: str
    content_hash: str

    def to_canonical_dict(self) -> dict[str, str]:
        return {
            "calendar_id": self.calendar_id,
            "content_hash": self.content_hash,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class HistoricalDailyRequest:
    """Validated request for one NSE-equity daily history."""

    instrument_key: str
    symbol: str
    from_date: date
    to_date: date
    request_id: str | None = None
    calendar: CalendarReference | None = None
    expected_sessions: tuple[date, ...] | None = None
    corporate_action_authority: AuthorityReference | None = None
    historical_universe_authority: AuthorityReference | None = None

    def __post_init__(self) -> None:
        if _NSE_EQUITY_KEY_PATTERN.fullmatch(self.instrument_key) is None:
            raise ValueError("instrument_key must identify one NSE cash equity")
        if _SYMBOL_PATTERN.fullmatch(self.symbol) is None:
            raise ValueError("symbol must be 1-20 uppercase NSE symbol characters")
        if self.from_date > self.to_date:
            raise ValueError("from_date must be on or before to_date")
        if self.to_date > _add_years(self.from_date, 10):
            raise ValueError("daily history cannot exceed the Upstox ten-year retrieval limit")
        if self.request_id is not None and not 1 <= len(self.request_id) <= 128:
            raise ValueError("request_id must contain 1-128 characters when provided")
        if self.expected_sessions is not None:
            if self.calendar is None:
                raise ValueError("expected_sessions requires a versioned calendar reference")
            if tuple(sorted(set(self.expected_sessions))) != self.expected_sessions:
                raise ValueError("expected_sessions must be unique and strictly ascending")
            if any(
                session < self.from_date or session > self.to_date
                for session in self.expected_sessions
            ):
                raise ValueError("expected_sessions must remain within the requested range")


@dataclass(frozen=True, slots=True)
class QualityFinding:
    """A deterministic anomaly report and any approved disposition."""

    code: QualityCode
    severity: FindingSeverity
    count: int
    disposition: FindingDisposition
    record_keys: tuple[str, ...] = ()
    repair_rule: str | None = None
    repair_hash: str | None = None

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("quality finding count must be positive")
        if self.disposition == FindingDisposition.REPAIRED:
            if self.repair_rule is None or self.repair_hash is None:
                raise ValueError("repaired findings require a rule and transformation hash")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "count": self.count,
            "disposition": self.disposition.value,
            "record_keys": list(self.record_keys),
            "repair_hash": self.repair_hash,
            "repair_rule": self.repair_rule,
            "severity": self.severity.value,
        }


@dataclass(frozen=True, slots=True)
class PointInTimeBar:
    """Daily OHLCV record with explicit information availability."""

    provider_instrument_id: str
    symbol: str
    exchange_date: date
    event_at: datetime
    provider_at: datetime | None
    ingested_at: datetime
    available_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    open_interest: int
    source_row_index: int

    def __post_init__(self) -> None:
        for field_name in ("event_at", "ingested_at", "available_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.provider_at is not None:
            if self.provider_at.tzinfo is None or self.provider_at.utcoffset() is None:
                raise ValueError("provider_at must be timezone-aware when present")
        if self.available_at < self.event_at:
            raise ValueError("available_at cannot precede event_at")
        if self.ingested_at < self.available_at:
            raise ValueError("record was not available at acquisition")
        if self.open_interest < 0:
            raise ValueError("open_interest cannot be negative")
        PriceBar(
            symbol=self.symbol,
            timestamp=self.event_at,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )

    def to_price_bar(self) -> PriceBar:
        return PriceBar(
            symbol=self.symbol,
            timestamp=self.event_at,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "available_at": utc_text(self.available_at),
            "close": decimal_text(self.close),
            "event_at": utc_text(self.event_at),
            "exchange_date": self.exchange_date.isoformat(),
            "high": decimal_text(self.high),
            "ingested_at": utc_text(self.ingested_at),
            "low": decimal_text(self.low),
            "open": decimal_text(self.open),
            "open_interest": self.open_interest,
            "provider_at": utc_text(self.provider_at) if self.provider_at else None,
            "provider_instrument_id": self.provider_instrument_id,
            "schema_id": BAR_RECORD_SCHEMA,
            "schema_version": BAR_RECORD_VERSION,
            "source_row_index": self.source_row_index,
            "symbol": self.symbol,
            "volume": self.volume,
        }


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Canonical provenance and quality evidence for one provider response."""

    dataset_id: str
    status: DatasetStatus
    source_status: SourceStatus
    acquired_at: datetime
    request_id: str | None
    provider_request_id: str | None
    provider_instrument_id: str
    symbol: str
    requested_start: date
    requested_end: date
    received_start: date
    received_end: date
    row_count: int
    raw_response_hash: str
    canonical_content_hash: str
    calendar: CalendarReference | None
    corporate_action_authority: AuthorityReference | None
    historical_universe_authority: AuthorityReference | None
    quality_findings: tuple[QualityFinding, ...]
    manifest_hash: str
    adjustment: AdjustmentReference | None = None
    """Provenance for a derived, corporate-action-adjusted series. ``None`` means provider values.

    A provider response is genuinely RAW and keeps that label forever. What used to be dishonest was
    that *derived* series were forced to claim it too: ``to_canonical_dict`` emitted the literal
    ``{"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}`` unconditionally, so evidence built on
    adjusted bars declared itself unadjusted, immutably.

    Setting this field switches the manifest to schema version
    :data:`DATASET_MANIFEST_VERSION_ADJUSTED` and emits the full reference. Leaving it ``None``
    reproduces the version-1 payload **byte for byte**, so every manifest hash already committed to
    this repository is unchanged -- see ``tests/test_adjustment_provenance.py``. Derived series are
    published alongside raw ones, never in place of them.
    """

    @property
    def is_governed_eligible(self) -> bool:
        return self.status == DatasetStatus.ACCEPTED

    # craft-allow: long-function - table-driven schema mapping is clearest in one visible contract.
    def to_canonical_dict(  # craft-allow: deep-nesting - conditional fields are serialization, not control flow.
        self, *, include_identity: bool = True
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "acquired_at": utc_text(self.acquired_at),
            "adjustment": (
                self.adjustment.to_canonical_dict()
                if self.adjustment is not None
                else {"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}
            ),
            "available_timestamp_field": "available_at",
            "calendar": self.calendar.to_canonical_dict() if self.calendar else None,
            "canonical_content_hash": self.canonical_content_hash,
            "corporate_action_authority": (
                self.corporate_action_authority.to_canonical_dict()
                if self.corporate_action_authority
                else None
            ),
            "currency": "INR",
            "event_timestamp_field": "event_at",
            "historical_universe_authority": (
                self.historical_universe_authority.to_canonical_dict()
                if self.historical_universe_authority
                else None
            ),
            "ingested_timestamp_field": "ingested_at",
            "interval": "1",
            "mapping_history": [
                {
                    "provider_instrument_id": self.provider_instrument_id,
                    "source": "ACQUISITION_REQUEST",
                    "symbol": self.symbol,
                }
            ],
            "provider": UPSTOX_PROVIDER,
            "provider_api_version": UPSTOX_HISTORICAL_API_VERSION,
            "provider_documentation": UPSTOX_HISTORICAL_DOCUMENTATION,
            "provider_endpoint_id": UPSTOX_HISTORICAL_ENDPOINT,
            "provider_instrument_id": self.provider_instrument_id,
            "provider_request_id": self.provider_request_id,
            "provider_timestamp_field": None,
            "quality_findings": [item.to_canonical_dict() for item in self.quality_findings],
            "raw_response_hash": self.raw_response_hash,
            "received_range": {
                "end": self.received_end.isoformat(),
                "start": self.received_start.isoformat(),
            },
            "record_schema": {"id": BAR_RECORD_SCHEMA, "version": BAR_RECORD_VERSION},
            "requested_range": {
                "end": self.requested_end.isoformat(),
                "start": self.requested_start.isoformat(),
            },
            "request_id": self.request_id,
            "row_count": self.row_count,
            "schema_id": DATASET_MANIFEST_SCHEMA,
            "schema_version": (
                DATASET_MANIFEST_VERSION_ADJUSTED
                if self.adjustment is not None
                else DATASET_MANIFEST_VERSION
            ),
            "source": UPSTOX_HISTORICAL_SOURCE,
            "source_status": self.source_status.value,
            "status": self.status.value,
            "symbol": self.symbol,
            "timezone": "Asia/Kolkata",
            "transformation_version": "upstox-v3-daily-canonical-v1",
            "unit": "days",
            "units": {
                "open_interest": "contracts",
                "price": "INR",
                "volume": "shares",
            },
        }
        if include_identity:
            payload["dataset_id"] = self.dataset_id
            payload["manifest_hash"] = self.manifest_hash
        return payload


@dataclass(frozen=True, slots=True)
class HistoricalAcquisition:
    """Accepted raw acquisition, including research-only partial evidence."""

    manifest: DatasetManifest
    records: tuple[PointInTimeBar, ...]

    @property
    def bars(self) -> tuple[PriceBar, ...]:
        return tuple(record.to_price_bar() for record in self.records)


@dataclass(frozen=True, slots=True)
class HistoricalAcquisitionFailure:
    """Typed, non-secret provider or validation failure."""

    code: AcquisitionFailureCode
    detected_at: datetime
    retryable: bool
    recovery_action: str
    provider_status: int | None = None
    provider_code: str | None = None
    retry_after_seconds: int | None = None
    quality_findings: tuple[QualityFinding, ...] = ()


HistoricalAcquisitionOutcome = HistoricalAcquisition | HistoricalAcquisitionFailure


def create_dataset_manifest(
    request: HistoricalDailyRequest,
    records: tuple[PointInTimeBar, ...],
    *,
    acquired_at: datetime,
    raw_response_hash: str,
    provider_request_id: str | None,
    source_status: SourceStatus,
    quality_findings: tuple[QualityFinding, ...],
) -> DatasetManifest:
    """Create a deterministic manifest whose identity covers every consumed field."""
    content_hash = canonical_sha256(
        {
            "records": [record.to_canonical_dict() for record in records],
            "schema_id": BAR_RECORD_SCHEMA,
            "schema_version": BAR_RECORD_VERSION,
        }
    )
    has_blocking_finding = any(
        finding.severity == FindingSeverity.BLOCKING for finding in quality_findings
    )
    status = (
        DatasetStatus.PARTIAL
        if source_status == SourceStatus.PARTIAL or has_blocking_finding
        else DatasetStatus.ACCEPTED
    )
    draft = DatasetManifest(
        dataset_id="",
        status=status,
        source_status=source_status,
        acquired_at=acquired_at,
        request_id=request.request_id,
        provider_request_id=provider_request_id,
        provider_instrument_id=request.instrument_key,
        symbol=request.symbol,
        requested_start=request.from_date,
        requested_end=request.to_date,
        received_start=records[0].exchange_date,
        received_end=records[-1].exchange_date,
        row_count=len(records),
        raw_response_hash=raw_response_hash,
        canonical_content_hash=content_hash,
        calendar=request.calendar,
        corporate_action_authority=request.corporate_action_authority,
        historical_universe_authority=request.historical_universe_authority,
        quality_findings=quality_findings,
        manifest_hash="",
    )
    manifest_hash = canonical_sha256(draft.to_canonical_dict(include_identity=False))
    return replace(
        draft,
        dataset_id=f"dset_{manifest_hash[:24]}",
        manifest_hash=manifest_hash,
    )


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)
