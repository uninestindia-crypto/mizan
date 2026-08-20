"""Integration tests from governed market-data acquisition to immutable evidence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.market_data import (
    AuthorityReference,
    CalendarReference,
    HistoricalAcquisition,
    HistoricalDailyRequest,
    PointInTimeBar,
    SourceStatus,
    create_dataset_manifest,
)
from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.evidence import (
    EvidenceIntegrityError,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

FIXED_TIME = datetime(2025, 1, 4, 12, 0, tzinfo=UTC)
INSTRUMENT_KEY = "NSE_EQ|INE009A01021"


def _wrong_row_count(acquisition: HistoricalAcquisition) -> HistoricalAcquisition:
    return replace(acquisition, manifest=replace(acquisition.manifest, row_count=99))


def _wrong_dataset_id(acquisition: HistoricalAcquisition) -> HistoricalAcquisition:
    return replace(
        acquisition,
        manifest=replace(acquisition.manifest, dataset_id="dset_wrong_identity"),
    )


def _wrong_received_range(acquisition: HistoricalAcquisition) -> HistoricalAcquisition:
    return _replace_and_rehash_manifest(acquisition, received_start=date(2025, 1, 1))


def _wrong_instrument(acquisition: HistoricalAcquisition) -> HistoricalAcquisition:
    return _replace_and_rehash_manifest(
        acquisition,
        provider_instrument_id="NSE_EQ|INE467B01029",
    )


def test_governed_acquisition_round_trips_through_verified_evidence(tmp_path: Path) -> None:
    acquisition = _acquisition()
    store = _store(tmp_path)

    committed = store.commit(
        draft_from_historical_acquisition(acquisition),
        operation_id="op_acquisition",
    )
    opened = store.open_verified(EvidenceResourceType.DATASET, acquisition.manifest.dataset_id)

    assert committed.manifest.resource_id == acquisition.manifest.dataset_id
    assert committed.manifest.metadata == acquisition.manifest.to_canonical_dict()
    assert opened.records == tuple(record.to_canonical_dict() for record in acquisition.records)
    assert opened.manifest.canonical_records_hash == committed.manifest.canonical_records_hash


def test_acquisition_record_tamper_is_rejected_before_publication(tmp_path: Path) -> None:
    acquisition = _acquisition()
    changed_record = replace(acquisition.records[0], close=Decimal("1856"))
    tampered = replace(acquisition, records=(changed_record, acquisition.records[1]))

    with pytest.raises(EvidenceIntegrityError, match="content hash"):
        draft_from_historical_acquisition(tampered)

    assert tuple(tmp_path.iterdir()) == ()


def test_acquisition_manifest_identity_tamper_is_rejected() -> None:
    acquisition = _acquisition()
    tampered = replace(
        acquisition,
        manifest=replace(acquisition.manifest, manifest_hash="0" * 64),
    )

    with pytest.raises(EvidenceIntegrityError, match="manifest hash"):
        draft_from_historical_acquisition(tampered)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (_wrong_row_count, "row count"),
        (_wrong_dataset_id, "dataset ID"),
        (_wrong_received_range, "received range"),
        (_wrong_instrument, "instrument identity"),
    ],
)
# test-allow: no-assertion - checker cannot parse this multiline parametrized test signature.
def test_acquisition_structural_mismatch_is_rejected(
    mutator: Callable[[HistoricalAcquisition], HistoricalAcquisition],
    message: str,
) -> None:
    with pytest.raises(EvidenceIntegrityError, match=message):
        draft_from_historical_acquisition(mutator(_acquisition()))


def _store(root: Path) -> EvidenceStore:
    return EvidenceStore(
        EvidenceStoreConfig(
            root=root,
            chunk_uncompressed_bytes=1024,
            max_bundle_bytes=8192,
            min_free_bytes=0,
            clock=lambda: FIXED_TIME,
        )
    )


def _acquisition() -> HistoricalAcquisition:
    authority = AuthorityReference(
        authority_id="authority-test",
        source_url="https://example.test/authority",
        publication_date=date(2024, 12, 1),
        effective_from=date(2025, 1, 1),
        effective_to=None,
        version="v1",
        content_hash="a" * 64,
    )
    request = HistoricalDailyRequest(
        instrument_key=INSTRUMENT_KEY,
        symbol="INFY",
        from_date=date(2025, 1, 2),
        to_date=date(2025, 1, 3),
        request_id="req-governed",
        calendar=CalendarReference("nse-cash", "2025-v1", "b" * 64),
        expected_sessions=(date(2025, 1, 2), date(2025, 1, 3)),
        corporate_action_authority=authority,
        historical_universe_authority=authority,
    )
    records = (
        _bar(date(2025, 1, 2), datetime(2025, 1, 1, 18, 30, tzinfo=UTC), 0),
        _bar(date(2025, 1, 3), datetime(2025, 1, 2, 18, 30, tzinfo=UTC), 1),
    )
    manifest = create_dataset_manifest(
        request,
        records,
        acquired_at=FIXED_TIME,
        raw_response_hash="c" * 64,
        provider_request_id="provider-request-1",
        source_status=SourceStatus.COMPLETE,
        quality_findings=(),
    )
    return HistoricalAcquisition(manifest, records)


def _bar(exchange_date: date, event_at: datetime, source_row_index: int) -> PointInTimeBar:
    return PointInTimeBar(
        provider_instrument_id=INSTRUMENT_KEY,
        symbol="INFY",
        exchange_date=exchange_date,
        event_at=event_at,
        provider_at=None,
        ingested_at=FIXED_TIME,
        available_at=event_at + timedelta(hours=10),
        open=Decimal("1850"),
        high=Decimal("1870"),
        low=Decimal("1840"),
        close=Decimal("1855"),
        volume=250_000,
        open_interest=0,
        source_row_index=source_row_index,
    )


def _replace_and_rehash_manifest(
    acquisition: HistoricalAcquisition,
    **changes: object,
) -> HistoricalAcquisition:
    draft = replace(
        acquisition.manifest,
        dataset_id="",
        manifest_hash="",
        **changes,
    )
    manifest_hash = canonical_sha256(draft.to_canonical_dict(include_identity=False))
    manifest = replace(
        draft,
        dataset_id=f"dset_{manifest_hash[:24]}",
        manifest_hash=manifest_hash,
    )
    return replace(acquisition, manifest=manifest)
