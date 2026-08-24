"""Immutable market-acquisition cache support for the NIFTY 50 campaign runner."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.market_data import (
    BAR_RECORD_SCHEMA,
    BAR_RECORD_VERSION,
    AuthorityReference,
    CalendarReference,
    DatasetManifest,
    FindingDisposition,
    FindingSeverity,
    HistoricalAcquisition,
    HistoricalAcquisitionFailure,
    HistoricalDailyRequest,
    PointInTimeBar,
    QualityCode,
    QualityFinding,
    SourceStatus,
    create_dataset_manifest,
)
from quant_system.evidence import (
    EvidenceIntegrityError,
    EvidenceResourceType,
    EvidenceStore,
    VerifiedEvidence,
)


@dataclass(frozen=True, slots=True)
class CachedAcquisitionQuery:
    """Identity fields that distinguish discovery and governed acquisitions."""

    provider_instrument_id: str
    symbol: str
    requested_start: date
    requested_end: date
    calendar_hash: str | None
    corporate_action_hash: str | None
    historical_universe_hash: str | None

    @classmethod
    def from_request(cls, request: HistoricalDailyRequest) -> CachedAcquisitionQuery:
        return cls(
            provider_instrument_id=request.instrument_key,
            symbol=request.symbol,
            requested_start=request.from_date,
            requested_end=request.to_date,
            calendar_hash=request.calendar.content_hash if request.calendar else None,
            corporate_action_hash=_authority_hash(request.corporate_action_authority),
            historical_universe_hash=_authority_hash(request.historical_universe_authority),
        )

    @classmethod
    def from_manifest(cls, manifest: DatasetManifest) -> CachedAcquisitionQuery:
        return cls(
            provider_instrument_id=manifest.provider_instrument_id,
            symbol=manifest.symbol,
            requested_start=manifest.requested_start,
            requested_end=manifest.requested_end,
            calendar_hash=manifest.calendar.content_hash if manifest.calendar else None,
            corporate_action_hash=_authority_hash(manifest.corporate_action_authority),
            historical_universe_hash=_authority_hash(manifest.historical_universe_authority),
        )

    def matches(self, metadata: Mapping[str, Any]) -> bool:
        requested = metadata.get("requested_range")
        if not isinstance(requested, Mapping):
            return False
        return (
            metadata.get("provider_instrument_id") == self.provider_instrument_id
            and metadata.get("symbol") == self.symbol
            and requested.get("start") == self.requested_start.isoformat()
            and requested.get("end") == self.requested_end.isoformat()
            and _optional_hash(metadata.get("calendar")) == self.calendar_hash
            and _optional_hash(metadata.get("corporate_action_authority"))
            == self.corporate_action_hash
            and _optional_hash(metadata.get("historical_universe_authority"))
            == self.historical_universe_hash
        )


def _authority_hash(authority: AuthorityReference | None) -> str | None:
    return authority.content_hash if authority else None


def _optional_hash(value: object) -> str | None:
    return value.get("content_hash") if isinstance(value, Mapping) else None


def _parse_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise EvidenceIntegrityError(f"cached {field} must be text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceIntegrityError(f"cached {field} is not an ISO datetime") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceIntegrityError(f"cached {field} must be timezone-aware")
    return parsed


def _parse_date(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise EvidenceIntegrityError(f"cached {field} must be text")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise EvidenceIntegrityError(f"cached {field} is not an ISO date") from error


# craft-allow: deep-nesting — strict nested schema reconstruction is clearer beside validation.
def _parse_authority(value: object, field: str) -> AuthorityReference | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise EvidenceIntegrityError(f"cached {field} must be an object or null")
    try:
        effective_to = value.get("effective_to")
        authority = AuthorityReference(
            authority_id=str(value["authority_id"]),
            source_url=str(value["source_url"]),
            publication_date=_parse_date(value["publication_date"], f"{field}.publication_date"),
            effective_from=_parse_date(value["effective_from"], f"{field}.effective_from"),
            effective_to=(
                _parse_date(effective_to, f"{field}.effective_to")
                if effective_to is not None
                else None
            ),
            version=str(value["version"]),
            content_hash=str(value["content_hash"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceIntegrityError(f"cached {field} is malformed") from error
    if authority.to_canonical_dict() != dict(value):
        raise EvidenceIntegrityError(f"cached {field} is non-canonical")
    return authority


def _parse_calendar(value: object) -> CalendarReference | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise EvidenceIntegrityError("cached calendar must be an object or null")
    try:
        calendar = CalendarReference(
            calendar_id=str(value["calendar_id"]),
            version=str(value["version"]),
            content_hash=str(value["content_hash"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceIntegrityError("cached calendar is malformed") from error
    if calendar.to_canonical_dict() != dict(value):
        raise EvidenceIntegrityError("cached calendar is non-canonical")
    return calendar


# craft-allow: deep-nesting — collection item parsing must bind each nested canonical field.
def _parse_findings(value: object) -> tuple[QualityFinding, ...]:
    if not isinstance(value, list):
        raise EvidenceIntegrityError("cached quality_findings must be a list")
    findings: list[QualityFinding] = []
    try:
        for item in value:
            if not isinstance(item, Mapping):
                raise TypeError("quality finding is not an object")
            finding = _parse_finding(item)
            if finding.to_canonical_dict() != dict(item):
                raise ValueError("non-canonical quality finding")
            findings.append(finding)
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceIntegrityError("cached quality finding is malformed") from error
    return tuple(findings)


def _parse_finding(item: Mapping[str, Any]) -> QualityFinding:
    return QualityFinding(
        code=QualityCode(str(item["code"])),
        severity=FindingSeverity(str(item["severity"])),
        count=int(item["count"]),
        disposition=FindingDisposition(str(item["disposition"])),
        record_keys=tuple(str(key) for key in item["record_keys"]),
        repair_rule=(str(item["repair_rule"]) if item["repair_rule"] is not None else None),
        repair_hash=(str(item["repair_hash"]) if item["repair_hash"] is not None else None),
    )


# craft-allow: deep-nesting — immutable bar reconstruction mirrors the canonical nested schema.
def _parse_record(value: Mapping[str, Any]) -> PointInTimeBar:
    try:
        if value["schema_id"] != BAR_RECORD_SCHEMA or value["schema_version"] != BAR_RECORD_VERSION:
            raise ValueError("unexpected bar schema")
        provider_at = value["provider_at"]
        record = PointInTimeBar(
            provider_instrument_id=str(value["provider_instrument_id"]),
            symbol=str(value["symbol"]),
            exchange_date=_parse_date(value["exchange_date"], "bar.exchange_date"),
            event_at=_parse_datetime(value["event_at"], "bar.event_at"),
            provider_at=(
                _parse_datetime(provider_at, "bar.provider_at") if provider_at is not None else None
            ),
            ingested_at=_parse_datetime(value["ingested_at"], "bar.ingested_at"),
            available_at=_parse_datetime(value["available_at"], "bar.available_at"),
            open=Decimal(str(value["open"])),
            high=Decimal(str(value["high"])),
            low=Decimal(str(value["low"])),
            close=Decimal(str(value["close"])),
            volume=int(value["volume"]),
            open_interest=int(value["open_interest"]),
            source_row_index=int(value["source_row_index"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceIntegrityError("cached point-in-time bar is malformed") from error
    if record.to_canonical_dict() != dict(value):
        raise EvidenceIntegrityError("cached point-in-time bar is non-canonical")
    return record


def _request_from_metadata(metadata: Mapping[str, Any]) -> HistoricalDailyRequest:
    requested = metadata["requested_range"]
    if not isinstance(requested, Mapping):
        raise TypeError("requested_range is not an object")
    return HistoricalDailyRequest(
        instrument_key=str(metadata["provider_instrument_id"]),
        symbol=str(metadata["symbol"]),
        from_date=_parse_date(requested["start"], "requested_range.start"),
        to_date=_parse_date(requested["end"], "requested_range.end"),
        request_id=(str(metadata["request_id"]) if metadata["request_id"] is not None else None),
        calendar=_parse_calendar(metadata["calendar"]),
        corporate_action_authority=_parse_authority(
            metadata["corporate_action_authority"], "corporate_action_authority"
        ),
        historical_universe_authority=_parse_authority(
            metadata["historical_universe_authority"], "historical_universe_authority"
        ),
    )


# craft-allow: deep-nesting — manifest reconstruction intentionally validates nested evidence.
def historical_acquisition_from_verified(verified: VerifiedEvidence) -> HistoricalAcquisition:
    """Rebuild and semantically revalidate one acquisition from verified canonical evidence."""
    metadata = verified.manifest.metadata
    if verified.manifest.resource_type != EvidenceResourceType.DATASET:
        raise EvidenceIntegrityError("cached acquisition is not dataset evidence")
    try:
        records = tuple(_parse_record(record) for record in verified.records)
        manifest = create_dataset_manifest(
            _request_from_metadata(metadata),
            records,
            acquired_at=_parse_datetime(metadata["acquired_at"], "acquired_at"),
            raw_response_hash=str(metadata["raw_response_hash"]),
            provider_request_id=(
                str(metadata["provider_request_id"])
                if metadata["provider_request_id"] is not None
                else None
            ),
            source_status=SourceStatus(str(metadata["source_status"])),
            quality_findings=_parse_findings(metadata["quality_findings"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise EvidenceIntegrityError("cached dataset manifest is malformed") from error
    if manifest.to_canonical_dict() != metadata:
        raise EvidenceIntegrityError("cached dataset metadata does not rebuild canonically")
    if manifest.dataset_id != verified.manifest.resource_id:
        raise EvidenceIntegrityError("cached dataset ID differs from its evidence path")
    acquisition = HistoricalAcquisition(manifest=manifest, records=records)
    draft_from_historical_acquisition(acquisition)
    return acquisition


def load_cached_acquisition(
    store: EvidenceStore, query: CachedAcquisitionQuery
) -> HistoricalAcquisition | None:
    """Return one exact cache hit; fail on corruption or ambiguous matching datasets."""
    matches = [
        verified
        for verified in store.list_verified(EvidenceResourceType.DATASET)
        if query.matches(verified.manifest.metadata)
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise EvidenceIntegrityError(
            f"acquisition cache has {len(matches)} entries for one exact query"
        )
    return historical_acquisition_from_verified(matches[0])


def persist_verified_acquisition(
    store: EvidenceStore,
    acquisition: HistoricalAcquisition,
    *,
    operation_id: str,
) -> HistoricalAcquisition:
    """Atomically publish an acquisition, reopen it, and require exact semantic equality."""
    store.commit(draft_from_historical_acquisition(acquisition), operation_id=operation_id)
    verified = store.open_verified(
        EvidenceResourceType.DATASET,
        acquisition.manifest.dataset_id,
    )
    rebuilt = historical_acquisition_from_verified(verified)
    if rebuilt != acquisition:
        raise EvidenceIntegrityError("published acquisition did not round-trip exactly")
    return rebuilt


def acquire_or_load(
    store: EvidenceStore,
    query: CachedAcquisitionQuery,
    fetch: Callable[[], HistoricalAcquisition | HistoricalAcquisitionFailure],
    *,
    operation_id: str,
) -> tuple[HistoricalAcquisition | HistoricalAcquisitionFailure, str]:
    """Use verified cache first; contact the provider only on an unambiguous cache miss."""
    cached = load_cached_acquisition(store, query)
    if cached is not None:
        return cached, "CACHE_HIT"
    outcome = fetch()
    if isinstance(outcome, HistoricalAcquisitionFailure):
        return outcome, "CACHE_MISS_FAILED"
    if CachedAcquisitionQuery.from_manifest(outcome.manifest) != query:
        raise EvidenceIntegrityError("provider acquisition does not match the cache query")
    saved = persist_verified_acquisition(store, outcome, operation_id=operation_id)
    return saved, "CACHE_MISS_SAVED"
