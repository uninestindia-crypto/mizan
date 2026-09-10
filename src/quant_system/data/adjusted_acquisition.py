"""Derive a corporate-action-adjusted acquisition from a raw one, without touching the raw one.

The provider's acquisition is genuinely RAW and stays that way: its manifest, its hash and its bars
are never modified, so every piece of evidence already bound to it keeps its identity. What this
module produces is a **separate derived artifact** with its own dataset id and manifest hash, whose
manifest carries an :class:`~quant_system.data.adjustment_provenance.AdjustmentReference` naming the
method, the authority, the code revision, the derivation time, the source manifest hash and every
individual factor.

Two series that differ in adjustment therefore cannot collide on one identity, and neither can claim
to be the other. That is the whole point: before this existed, anything built on adjusted bars
declared itself ``RAW`` because ``to_canonical_dict`` emitted that literal unconditionally.

Raw prices are still what a fill executes at, so the raw acquisition is kept and handed separately
to the cost path -- see ``modeling.labels.build_label_dataset``, which prices costs on raw opens
while measuring the return on the adjusted ones.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

from quant_system.data.adjustment_provenance import (
    ADJUSTMENT_METHOD_V1,
    ADJUSTMENT_METHOD_VERSION_V1,
    AdjustmentBasis,
    AdjustmentFactorRecord,
    AdjustmentReference,
    AdjustmentStatus,
    FactorValidation,
    UnresolvedAction,
)
from quant_system.data.corporate_actions import (
    AdjustmentPlan,
    BarPoint,
    adjust_bars,
)
from quant_system.data.market_data import (
    BAR_RECORD_SCHEMA,
    BAR_RECORD_VERSION,
    DatasetManifest,
    HistoricalAcquisition,
    PointInTimeBar,
)
from quant_system.data.market_data_evidence import canonical_sha256

__all__ = ["derive_adjusted_acquisition", "reference_from_plan"]

_VALIDATION_BY_SOURCE = {
    "PARSED": FactorValidation.PARSED_AND_GAP_CONFIRMED,
    "VALIDATED": FactorValidation.INDEPENDENTLY_VALIDATED,
}


def reference_from_plan(
    plan: AdjustmentPlan,
    *,
    manifest: DatasetManifest,
    basis: AdjustmentBasis,
    authority_content_hash: str,
    authority_source_url: str,
    authority_publication_date: date | None,
    code_revision: str,
    derived_at: datetime,
) -> AdjustmentReference:
    """Turn one instrument's adjustment plan into hashable provenance.

    A dividend factor is labelled ``DIVIDEND_POLICY`` rather than ``PARSED_AND_GAP_CONFIRMED``: no
    ex-date gap can corroborate a payout removal, because the quote genuinely does drop by the
    payout. Removing it is a return-definition choice, and calling it "confirmed" would overstate
    the evidence.
    """
    factors = tuple(
        AdjustmentFactorRecord(
            ex_date=item.ex_date,
            factor=item.factor,
            kinds=item.kinds,
            validation=(
                FactorValidation.DIVIDEND_POLICY
                if item.kinds == ("dividend",)
                else _VALIDATION_BY_SOURCE[item.source]
            ),
            detail=item.detail,
        )
        for item in sorted(plan.factors, key=lambda f: f.ex_date)
    )
    unresolved = tuple(
        UnresolvedAction(ex_date=item.ex_date, reason=item.reason, subject=item.subject)
        for item in sorted(plan.unresolved, key=lambda u: u.ex_date)
    )
    return AdjustmentReference(
        method=ADJUSTMENT_METHOD_V1,
        method_version=ADJUSTMENT_METHOD_VERSION_V1,
        status=AdjustmentStatus.ADJUSTED,
        basis=basis,
        authority_id=f"nse-corporate-actions-{manifest.symbol}",
        authority_content_hash=authority_content_hash,
        authority_source_url=authority_source_url,
        authority_publication_date=authority_publication_date,
        code_revision=code_revision,
        derived_at=derived_at,
        source_dataset_id=manifest.dataset_id,
        source_manifest_hash=manifest.manifest_hash,
        factors=factors,
        unresolved=unresolved,
    )


def derive_adjusted_acquisition(
    acquisition: HistoricalAcquisition,
    plan: AdjustmentPlan,
    reference: AdjustmentReference,
) -> HistoricalAcquisition:
    """A new acquisition whose bars are back-adjusted and whose manifest says so.

    The returned manifest gets a fresh ``dataset_id`` and ``manifest_hash`` computed over its own
    canonical payload, which now includes the adjustment reference. It cannot be mistaken for the
    raw dataset it came from, and the raw dataset is returned unmodified to the caller that still
    holds it.

    ``canonical_content_hash`` is recomputed over the adjusted records for the same reason: a
    content hash that still described the raw bars would let two different series share it.
    """
    if reference.source_manifest_hash != acquisition.manifest.manifest_hash:
        raise ValueError("adjustment reference does not bind the supplied acquisition")

    ordered = sorted(acquisition.records, key=lambda record: record.exchange_date)
    points = [
        BarPoint(
            on=record.exchange_date,
            open=record.open,
            high=record.high,
            low=record.low,
            close=record.close,
            volume=record.volume,
        )
        for record in ordered
    ]
    adjusted_points = adjust_bars(points, plan.factors)
    adjusted_records = tuple(
        _rescaled(record, point) for record, point in zip(ordered, adjusted_points, strict=True)
    )

    content_hash = canonical_sha256(
        {
            "records": [record.to_canonical_dict() for record in adjusted_records],
            "schema_id": BAR_RECORD_SCHEMA,
            "schema_version": BAR_RECORD_VERSION,
        }
    )
    draft = replace(
        acquisition.manifest,
        dataset_id="",
        manifest_hash="",
        canonical_content_hash=content_hash,
        adjustment=reference,
    )
    manifest_hash = canonical_sha256(draft.to_canonical_dict(include_identity=False))
    manifest = replace(
        draft,
        dataset_id=f"dset_{manifest_hash[:24]}",
        manifest_hash=manifest_hash,
    )
    return HistoricalAcquisition(manifest=manifest, records=adjusted_records)


def _rescaled(record: PointInTimeBar, point: BarPoint) -> PointInTimeBar:
    """One bar re-expressed on the adjusted basis, keeping every timestamp and identity field.

    Only the five price/volume fields move. Every timestamp, instrument identifier and source row
    index is preserved exactly, so a derived bar remains traceable to the provider row it came from.
    """
    return replace(
        record,
        open=point.open,
        high=point.high,
        low=point.low,
        close=point.close,
        volume=point.volume,
    )
