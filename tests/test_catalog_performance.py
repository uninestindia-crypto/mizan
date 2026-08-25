"""Tests for fast verified catalog pagination and tamper-evidence guarantees."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.market_data import (
    BAR_RECORD_SCHEMA,
    AuthorityReference,
    CalendarReference,
    HistoricalAcquisition,
    HistoricalDailyRequest,
    PointInTimeBar,
    SourceStatus,
    create_dataset_manifest,
)
from quant_system.evidence import (
    EvidenceIntegrityError,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.server.governed_journeys import (
    EVIDENCE_ROOT_ENV,
    JourneyApiError,
    dataset_page,
)

FIXED_TIME = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


def _create_bar_record(symbol: str, inst_key: str, d_start: date) -> tuple[PointInTimeBar, ...]:
    ev_dt = datetime(d_start.year, d_start.month, d_start.day, 18, 30, tzinfo=UTC)
    return (
        PointInTimeBar(
            provider_instrument_id=inst_key,
            symbol=symbol,
            exchange_date=d_start,
            event_at=ev_dt,
            provider_at=None,
            ingested_at=FIXED_TIME,
            available_at=ev_dt + timedelta(hours=10),
            open=Decimal("100.0"),
            high=Decimal("105.0"),
            low=Decimal("99.0"),
            close=Decimal("104.0"),
            volume=1000,
            open_interest=0,
            source_row_index=0,
        ),
    )


def _publish_dataset(store: EvidenceStore, symbol: str, day_offset: int) -> str:
    auth = AuthorityReference(
        "auth-test",
        "https://example.test",
        date(2024, 12, 1),
        date(2025, 1, 1),
        None,
        "v1",
        "a" * 64,
    )
    d_start = date(2026, 8, 1) + timedelta(days=day_offset)
    d_end = d_start + timedelta(days=1)
    inst_key = f"NSE_EQ|INE009A0102{day_offset}"
    req = HistoricalDailyRequest(
        inst_key,
        symbol,
        d_start,
        d_end,
        f"req-{symbol}-{day_offset}",
        CalendarReference("nse-cash", "2026-v1", "b" * 64),
        (d_start, d_end),
        auth,
        auth,
    )
    records = _create_bar_record(symbol, inst_key, d_start)
    manifest = create_dataset_manifest(
        req,
        records,
        acquired_at=FIXED_TIME + timedelta(seconds=day_offset),
        raw_response_hash="c" * 64,
        provider_request_id=f"provider-req-{symbol}",
        source_status=SourceStatus.COMPLETE,
        quality_findings=(),
    )
    committed = store.commit(
        draft_from_historical_acquisition(HistoricalAcquisition(manifest, records)),
        operation_id=f"op_{symbol}_{day_offset}",
    )
    return committed.manifest.resource_id


def _publish_batch(store: EvidenceStore, prefix: str, count: int) -> list[str]:
    return [_publish_dataset(store, f"{prefix}{i}", i) for i in range(1, count + 1)]


def test_list_manifests_fast_and_verified(tmp_path: Path) -> None:
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path))
    ids = _publish_batch(store, "SYM", 9)

    manifests = store.list_manifests(EvidenceResourceType.DATASET)
    assert len(manifests) == 9
    assert all(m.resource_type == EvidenceResourceType.DATASET for m in manifests)
    assert {m.resource_id for m in manifests} == set(ids)


def test_list_manifests_fails_closed_on_missing_commit(tmp_path: Path) -> None:
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path))
    _publish_dataset(store, "SYM1", 1)
    dset2_id = _publish_dataset(store, "SYM2", 2)
    (tmp_path / EvidenceResourceType.DATASET.value / dset2_id / "COMMITTED").unlink()

    with pytest.raises(EvidenceIntegrityError, match="commit marker is missing"):
        store.list_manifests(EvidenceResourceType.DATASET)


def test_list_manifests_fails_closed_on_tampered_manifest(tmp_path: Path) -> None:
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path))
    _publish_dataset(store, "SYM1", 1)
    dset2_id = _publish_dataset(store, "SYM2", 2)
    manifest_file = tmp_path / EvidenceResourceType.DATASET.value / dset2_id / "manifest.json"
    manifest_file.write_bytes(manifest_file.read_bytes() + b" ")

    with pytest.raises(EvidenceIntegrityError):
        store.list_manifests(EvidenceResourceType.DATASET)


def test_dataset_page_pagination_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(EVIDENCE_ROOT_ENV, str(tmp_path))
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path))
    _publish_batch(store, "STOCK", 5)

    page1 = dataset_page(limit=2, cursor=None)
    assert len(page1.items) == 2
    assert page1.has_more is True
    assert page1.next_cursor is not None

    page2 = dataset_page(limit=2, cursor=page1.next_cursor)
    assert len(page2.items) == 2
    assert page2.has_more is True
    assert page2.next_cursor is not None

    page3 = dataset_page(limit=2, cursor=page2.next_cursor)
    assert len(page3.items) == 1
    assert page3.has_more is False
    assert page3.next_cursor is None

    all_ids = [item.dataset_id for item in page1.items + page2.items + page3.items]
    assert len(set(all_ids)) == 5


def test_dataset_page_fails_closed_when_on_page_blob_corrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(EVIDENCE_ROOT_ENV, str(tmp_path))
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path))
    _publish_batch(store, "BLOBTEST", 3)

    manifests = store.list_manifests(EvidenceResourceType.DATASET)
    ordered_acquisitions = sorted(
        [m for m in manifests if m.schema_id == BAR_RECORD_SCHEMA],
        key=lambda m: (m.created_at, m.resource_id),
    )
    # First dataset will be on Page 1 when limit=2
    target_manifest = ordered_acquisitions[0]
    blob_descriptor = target_manifest.blobs[0]
    blob_file = (
        tmp_path
        / "blobs"
        / "sha256"
        / blob_descriptor.stored_hash[:2]
        / f"{blob_descriptor.stored_hash}.jsonl.gz"
    )
    assert blob_file.exists()
    blob_file.write_bytes(b"CORRUPTED_BLOB_CONTENT")

    with pytest.raises(JourneyApiError) as exc_info:
        dataset_page(limit=2, cursor=None)

    assert exc_info.value.code == "EVIDENCE_INTEGRITY_INVALID"
    assert exc_info.value.status_code == 409


def test_dataset_page_scoped_verification_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(EVIDENCE_ROOT_ENV, str(tmp_path))
    store = EvidenceStore(EvidenceStoreConfig(root=tmp_path))
    _publish_batch(store, "PAGETEST", 5)

    manifests = store.list_manifests(EvidenceResourceType.DATASET)
    ordered_acquisitions = sorted(
        [m for m in manifests if m.schema_id == BAR_RECORD_SCHEMA],
        key=lambda m: (m.created_at, m.resource_id),
    )
    # Target dataset at index 4 (which belongs strictly to Page 3 when limit=2)
    target_manifest = ordered_acquisitions[4]
    blob_descriptor = target_manifest.blobs[0]
    blob_file = (
        tmp_path
        / "blobs"
        / "sha256"
        / blob_descriptor.stored_hash[:2]
        / f"{blob_descriptor.stored_hash}.jsonl.gz"
    )
    assert blob_file.exists()
    blob_file.write_bytes(b"CORRUPTED_OFF_PAGE_BLOB")

    # Page 1: Manifests verified; blobs for items on Page 1 verified -> 200 OK
    page1 = dataset_page(limit=2, cursor=None)
    assert len(page1.items) == 2
    assert page1.has_more is True

    # Page 2: Manifests verified; blobs for items on Page 2 verified -> 200 OK
    page2 = dataset_page(limit=2, cursor=page1.next_cursor)
    assert len(page2.items) == 2
    assert page2.has_more is True

    # Page 3: Blobs for items on Page 3 verified -> Fails closed on corrupted blob!
    with pytest.raises(JourneyApiError) as exc_info:
        dataset_page(limit=2, cursor=page2.next_cursor)

    assert exc_info.value.code == "EVIDENCE_INTEGRITY_INVALID"
    assert exc_info.value.status_code == 409
