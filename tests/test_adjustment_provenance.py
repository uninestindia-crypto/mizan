"""The adjustment contract: derived data must not be able to claim it is raw.

Two obligations pull against each other here and both are non-negotiable.

1. A derived, corporate-action-adjusted series must carry honest provenance. Before this contract
   existed, ``DatasetManifest.to_canonical_dict`` emitted the literal
   ``{"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}`` for every dataset, so evidence built on
   adjusted bars declared itself unadjusted -- permanently, because the manifest is immutable.

2. Every manifest hash already committed to this repository must stay exactly what it was. Those
   hashes bind published model evidence. Changing them would invalidate historical research that
   nothing is wrong with, which is a worse outcome than the defect being fixed.

The two are reconciled by making the new field optional and version-tagged: ``adjustment=None``
reproduces the version-1 payload byte for byte, and setting it switches to version 2. The first test
below is the one that keeps obligation 2 honest, and it compares against hashes captured from the
real evidence store rather than from the code under test.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.data.adjustment_provenance import (
    ADJUSTMENT_METHOD_V1,
    ADJUSTMENT_METHOD_VERSION_V1,
    AdjustmentBasis,
    AdjustmentFactorRecord,
    AdjustmentProvenanceError,
    AdjustmentReference,
    AdjustmentStatus,
    FactorValidation,
    UnresolvedAction,
    carry_factor,
    spans_unresolved,
)
from quant_system.data.market_data import (
    DATASET_MANIFEST_VERSION,
    DATASET_MANIFEST_VERSION_ADJUSTED,
    AuthorityReference,
    CalendarReference,
    DatasetManifest,
    DatasetStatus,
    SourceStatus,
)
from quant_system.data.market_data_evidence import canonical_sha256

REPO_ROOT = Path(__file__).resolve().parent.parent


def _manifest(**overrides: object) -> DatasetManifest:
    base: dict[str, object] = {
        "dataset_id": "dset_abc",
        "status": DatasetStatus.ACCEPTED,
        "source_status": SourceStatus.COMPLETE,
        "acquired_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "request_id": "req-1",
        "provider_request_id": "prov-1",
        "provider_instrument_id": "NSE_EQ|INE009A01021",
        "symbol": "INFY",
        "requested_start": date(2024, 1, 1),
        "requested_end": date(2024, 12, 31),
        "received_start": date(2024, 1, 1),
        "received_end": date(2024, 12, 31),
        "row_count": 3,
        "raw_response_hash": "a" * 64,
        "canonical_content_hash": "b" * 64,
        "calendar": CalendarReference(calendar_id="cal", version="1", content_hash="c" * 64),
        "corporate_action_authority": AuthorityReference(
            authority_id="ca",
            source_url="https://example.invalid/ca",
            publication_date=date(2024, 1, 1),
            effective_from=date(2024, 1, 1),
            effective_to=None,
            version="1",
            content_hash="d" * 64,
        ),
        "historical_universe_authority": AuthorityReference(
            authority_id="uni",
            source_url="https://example.invalid/uni",
            publication_date=date(2024, 1, 1),
            effective_from=date(2024, 1, 1),
            effective_to=None,
            version="1",
            content_hash="e" * 64,
        ),
        "quality_findings": (),
        "manifest_hash": "f" * 64,
    }
    base.update(overrides)
    return DatasetManifest(**base)  # type: ignore[arg-type]


def _reference(**overrides: object) -> AdjustmentReference:
    base: dict[str, object] = {
        "method": ADJUSTMENT_METHOD_V1,
        "method_version": ADJUSTMENT_METHOD_VERSION_V1,
        "status": AdjustmentStatus.ADJUSTED,
        "basis": AdjustmentBasis.TOTAL_RETURN,
        "authority_id": "nse-corporate-actions-INFY",
        "authority_content_hash": "1" * 64,
        "authority_source_url": "https://www.nseindia.com/api/corporates-corporateActions",
        "authority_publication_date": date(2026, 9, 10),
        "code_revision": "5523843c",
        "derived_at": datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC),
        "source_dataset_id": "dset_abc",
        "source_manifest_hash": "f" * 64,
        "factors": (),
    }
    base.update(overrides)
    return AdjustmentReference(**base)  # type: ignore[arg-type]


# --- obligation 2: existing evidence keeps its identity ---------------------------------------


def test_an_unadjusted_manifest_emits_the_exact_version_one_payload() -> None:
    payload = _manifest().to_canonical_dict(include_identity=False)
    assert payload["adjustment"] == {"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}
    assert payload["schema_version"] == DATASET_MANIFEST_VERSION == 1


@pytest.mark.parametrize(
    "manifest_path",
    sorted(
        (REPO_ROOT / "data/evidence/market-cache/nifty50-current-20160822-20260821/store/datasets")
        .glob("*/manifest.json")
    )[:20],
    ids=lambda p: p.parent.name,
)
def test_real_committed_manifests_still_hash_to_their_recorded_identity(manifest_path: Path) -> None:
    """The regression that matters: no hash in the repository may move.

    Recomputes each stored manifest's hash from its own canonical payload and compares it against
    the identity the store recorded when it was written. This reads real evidence rather than
    round-tripping the code under test, so a change that alters the payload shape is caught even if
    the dataclass and the serializer change together.
    """
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    resource = _find_dataset_manifest(payload)
    assert resource is not None, "no dataset manifest block found"

    recorded = resource.pop("manifest_hash", None)
    resource.pop("dataset_id", None)
    assert recorded, "stored manifest carries no identity to check against"
    assert canonical_sha256(resource) == recorded


def test_the_code_still_emits_the_same_payload_shape_as_committed_evidence() -> None:
    """The previous test proves the store is self-consistent; this one binds the *code* to it.

    Self-consistency would survive any change to `to_canonical_dict`, because it never calls it. So
    compare the key set and the adjustment block the code produces today against a manifest actually
    committed to this repository. Adding, removing or renaming a key -- or making the adjustment
    block unconditional again -- moves every future hash away from every past one, and fails here.
    """
    stored = next(
        (
            _find_dataset_manifest(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(
                (
                    REPO_ROOT
                    / "data/evidence/market-cache/nifty50-current-20160822-20260821/store/datasets"
                ).glob("*/manifest.json")
            )[:1]
        ),
        None,
    )
    assert stored is not None, "no committed manifest available to compare against"
    stored.pop("manifest_hash", None)
    stored.pop("dataset_id", None)

    produced = _manifest().to_canonical_dict(include_identity=False)
    assert set(produced) == set(stored), "canonical manifest key set drifted from committed evidence"
    assert produced["adjustment"] == stored["adjustment"]
    assert produced["schema_version"] == stored["schema_version"]
    assert produced["schema_id"] == stored["schema_id"]


def _find_dataset_manifest(node: object) -> dict | None:
    if isinstance(node, dict):
        if "manifest_hash" in node and "adjustment" in node and "symbol" in node:
            return dict(node)
        for value in node.values():
            found = _find_dataset_manifest(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_dataset_manifest(value)
            if found is not None:
                return found
    return None


# --- obligation 1: a derived series cannot claim to be raw -------------------------------------


def test_an_adjusted_manifest_declares_itself_adjusted_and_bumps_the_schema_version() -> None:
    manifest = _manifest(adjustment=_reference())
    payload = manifest.to_canonical_dict(include_identity=False)

    assert payload["schema_version"] == DATASET_MANIFEST_VERSION_ADJUSTED == 2
    assert payload["adjustment"]["status"] == "ADJUSTED"
    assert payload["adjustment"]["method"] == ADJUSTMENT_METHOD_V1
    assert payload["adjustment"] != {"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}


def test_an_adjusted_manifest_cannot_collide_with_its_raw_source() -> None:
    """Two series that differ in adjustment must not share one identity."""
    raw = canonical_sha256(_manifest().to_canonical_dict(include_identity=False))
    adjusted = canonical_sha256(
        _manifest(adjustment=_reference()).to_canonical_dict(include_identity=False)
    )
    assert raw != adjusted


def test_the_reference_binds_method_authority_revision_time_and_source() -> None:
    """Everything a reproduction needs, or the artifact is not reproducible."""
    payload = _reference().to_canonical_dict()
    assert payload["method"] == ADJUSTMENT_METHOD_V1
    assert payload["method_version"] == ADJUSTMENT_METHOD_VERSION_V1
    assert payload["authority"]["content_hash"] == "1" * 64
    assert payload["authority"]["source_url"].startswith("https://www.nseindia.com/")
    assert payload["code_revision"] == "5523843c"
    assert payload["derived_at"] == "2026-09-10T12:00:00Z"
    assert payload["source_manifest_hash"] == "f" * 64
    assert payload["basis"] == "TOTAL_RETURN"


def test_two_factor_sets_produce_different_factor_set_hashes() -> None:
    one = _reference(
        factors=(
            AdjustmentFactorRecord(
                date(2024, 6, 1),
                Decimal("0.5"),
                ("bonus",),
                FactorValidation.PARSED_AND_GAP_CONFIRMED,
                "Bonus 1:1",
            ),
        )
    )
    other = _reference(
        factors=(
            AdjustmentFactorRecord(
                date(2024, 6, 1),
                Decimal("0.25"),
                ("bonus",),
                FactorValidation.PARSED_AND_GAP_CONFIRMED,
                "Bonus 3:1",
            ),
        )
    )
    assert one.factor_set_hash != other.factor_set_hash


def test_a_raw_reference_may_not_carry_factors() -> None:
    with pytest.raises(AdjustmentProvenanceError, match="RAW series cannot carry"):
        _reference(
            status=AdjustmentStatus.RAW,
            factors=(
                AdjustmentFactorRecord(
                    date(2024, 6, 1),
                    Decimal("0.5"),
                    ("bonus",),
                    FactorValidation.PARSED_AND_GAP_CONFIRMED,
                    "Bonus 1:1",
                ),
            ),
        )


def test_factors_must_be_in_ascending_ex_date_order() -> None:
    with pytest.raises(AdjustmentProvenanceError, match="ascending ex-date order"):
        _reference(
            factors=(
                AdjustmentFactorRecord(
                    date(2024, 7, 1),
                    Decimal("0.5"),
                    (),
                    FactorValidation.PARSED_AND_GAP_CONFIRMED,
                    "later",
                ),
                AdjustmentFactorRecord(
                    date(2024, 6, 1),
                    Decimal("0.5"),
                    (),
                    FactorValidation.PARSED_AND_GAP_CONFIRMED,
                    "earlier",
                ),
            )
        )


def test_a_non_positive_factor_is_refused() -> None:
    with pytest.raises(AdjustmentProvenanceError, match="non-positive"):
        AdjustmentFactorRecord(
            date(2024, 6, 1), Decimal("0"), (), FactorValidation.PARSED_AND_GAP_CONFIRMED, "zero"
        )


# --- carry_factor and spans_unresolved: what a return calculation may do ------------------------


def _factor(on: date, value: str, validation: FactorValidation) -> AdjustmentFactorRecord:
    return AdjustmentFactorRecord(on, Decimal(value), ("bonus",), validation, "test")


def test_carry_factor_multiplies_only_factors_inside_the_open_closed_window() -> None:
    reference = _reference(
        factors=(
            _factor(date(2024, 6, 1), "0.5", FactorValidation.PARSED_AND_GAP_CONFIRMED),
            _factor(date(2024, 6, 10), "0.5", FactorValidation.PARSED_AND_GAP_CONFIRMED),
            _factor(date(2024, 7, 1), "0.5", FactorValidation.PARSED_AND_GAP_CONFIRMED),
        )
    )
    # (after, through] -- an ex-date exactly at `after` has already been reflected in that price.
    assert carry_factor(reference, after=date(2024, 6, 1), through=date(2024, 6, 30)) == Decimal(
        "0.5"
    )
    assert carry_factor(reference, after=date(2024, 5, 1), through=date(2024, 6, 30)) == Decimal(
        "0.25"
    )
    assert carry_factor(reference, after=date(2024, 7, 1), through=date(2024, 7, 31)) == Decimal(1)


def test_carry_factor_converts_a_bonus_price_ratio_into_the_economic_return() -> None:
    """The whole point: a 1:1 bonus halves the quote and doubles the shares. The holder is flat."""
    reference = _reference(
        factors=(_factor(date(2024, 6, 15), "0.5", FactorValidation.PARSED_AND_GAP_CONFIRMED),)
    )
    entry, raw_exit = Decimal("100"), Decimal("50")
    carry = carry_factor(reference, after=date(2024, 6, 10), through=date(2024, 6, 20))
    assert (raw_exit / carry - entry) / entry == 0


def test_carry_factor_excludes_a_gap_inferred_factor() -> None:
    """A gap-inferred size would mechanically drive the window's return to zero. Refuse instead."""
    reference = _reference(
        factors=(_factor(date(2024, 6, 15), "0.36", FactorValidation.GAP_INFERRED_ONLY),)
    )
    assert carry_factor(reference, after=date(2024, 6, 10), through=date(2024, 6, 20)) == Decimal(1)
    assert spans_unresolved(reference, after=date(2024, 6, 10), through=date(2024, 6, 20)) is True


def test_an_independently_validated_factor_is_usable() -> None:
    reference = _reference(
        factors=(_factor(date(2024, 6, 15), "0.36", FactorValidation.INDEPENDENTLY_VALIDATED),)
    )
    assert carry_factor(reference, after=date(2024, 6, 10), through=date(2024, 6, 20)) == Decimal(
        "0.36"
    )
    assert spans_unresolved(reference, after=date(2024, 6, 10), through=date(2024, 6, 20)) is False


def test_spans_unresolved_catches_a_recorded_unresolved_action() -> None:
    reference = _reference(
        unresolved=(UnresolvedAction(date(2024, 6, 15), "RATIO_NOT_PUBLISHED", "Demerger"),)
    )
    assert spans_unresolved(reference, after=date(2024, 6, 10), through=date(2024, 6, 20)) is True
    assert spans_unresolved(reference, after=date(2024, 6, 16), through=date(2024, 6, 20)) is False
    assert spans_unresolved(reference, after=date(2024, 6, 1), through=date(2024, 6, 15)) is True


def test_no_reference_means_no_carry_and_nothing_unresolved() -> None:
    assert carry_factor(None, after=date(2024, 1, 1), through=date(2030, 1, 1)) == Decimal(1)
    assert spans_unresolved(None, after=date(2024, 1, 1), through=date(2030, 1, 1)) is False
