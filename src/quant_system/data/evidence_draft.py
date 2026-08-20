"""Bind governed market-data acquisitions to immutable evidence drafts."""

from __future__ import annotations

from quant_system.data.market_data import (
    BAR_RECORD_SCHEMA,
    BAR_RECORD_VERSION,
    HistoricalAcquisition,
)
from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.evidence import (
    EvidenceDraft,
    EvidenceIntegrityError,
    EvidenceResourceType,
)

DATASET_TOTAL_ORDER = (
    "provider_instrument_id",
    "event_at",
    "ingested_at",
    "source_row_index",
)


def draft_from_historical_acquisition(acquisition: HistoricalAcquisition) -> EvidenceDraft:
    """Validate the acquisition's existing identity and prepare its exact consumed rows."""
    manifest = acquisition.manifest
    records = tuple(record.to_canonical_dict() for record in acquisition.records)
    if not records or manifest.row_count != len(records):
        raise EvidenceIntegrityError("dataset manifest row count does not match acquisition")
    expected_content_hash = canonical_sha256(
        {
            "records": records,
            "schema_id": BAR_RECORD_SCHEMA,
            "schema_version": BAR_RECORD_VERSION,
        }
    )
    if manifest.canonical_content_hash != expected_content_hash:
        raise EvidenceIntegrityError("dataset canonical content hash does not match acquisition")
    expected_manifest_hash = canonical_sha256(manifest.to_canonical_dict(include_identity=False))
    if manifest.manifest_hash != expected_manifest_hash:
        raise EvidenceIntegrityError("dataset manifest hash does not match its canonical payload")
    if manifest.dataset_id != f"dset_{expected_manifest_hash[:24]}":
        raise EvidenceIntegrityError("dataset ID does not match its manifest hash")
    if (
        manifest.received_start != acquisition.records[0].exchange_date
        or manifest.received_end != acquisition.records[-1].exchange_date
    ):
        raise EvidenceIntegrityError("dataset received range does not match acquisition records")
    if any(
        record.provider_instrument_id != manifest.provider_instrument_id
        or record.symbol != manifest.symbol
        for record in acquisition.records
    ):
        raise EvidenceIntegrityError(
            "dataset instrument identity does not match acquisition records"
        )
    return EvidenceDraft(
        resource_type=EvidenceResourceType.DATASET,
        resource_id=manifest.dataset_id,
        schema_id=BAR_RECORD_SCHEMA,
        schema_version=BAR_RECORD_VERSION,
        metadata=manifest.to_canonical_dict(),
        records=records,
        total_order=DATASET_TOTAL_ORDER,
    )
