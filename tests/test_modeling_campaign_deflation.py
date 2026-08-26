"""Regressions for re-deflating published models against the complete attempt count."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from quant_system.evidence import EvidenceStore, EvidenceStoreConfig
from quant_system.modeling import run_persisted_ridge_trial
from quant_system.modeling.persisted_trials import (
    campaign_deflated_sharpe_ratios,
    load_persisted_trial_registry,
)
from tests.modeling_training_fixtures import governed_training_journey

ENDED_AT = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)


def test_published_deflated_sharpe_is_frozen_at_its_own_ordinal(tmp_path: Path) -> None:
    """Red Team Major 2: the published number deflates against N, not the final campaign count.

    This pins the documented behaviour rather than calling it a defect: immutable evidence
    cannot be rewritten, so the published field is honestly 'deflated at ordinal N'.
    """
    store = _campaign(tmp_path, attempts=4)

    published = _published_deflations(store)

    assert len(published) == 4
    assert published[1] > published[4]


def test_campaign_redeflation_reports_the_complete_attempt_count(tmp_path: Path) -> None:
    """Red Team Major 2: a reader must be able to obtain the honest campaign-final number."""
    store = _campaign(tmp_path, attempts=4)
    registry = load_persisted_trial_registry(store)

    redeflated = campaign_deflated_sharpe_ratios(store)
    published = _published_deflations(store)

    assert registry.multiplicity_count == 4
    assert len(redeflated) == 4
    assert all(Decimal(value) <= published[ordinal] for ordinal, value in _by_ordinal(redeflated))
    assert Decimal(redeflated["trial_ridge_001"]) < published[1]


def test_redeflation_leaves_the_published_evidence_untouched(tmp_path: Path) -> None:
    store = _campaign(tmp_path, attempts=2)
    before = _published_deflations(store)

    campaign_deflated_sharpe_ratios(store)

    assert _published_deflations(store) == before


def _campaign(root: Path, *, attempts: int) -> EvidenceStore:
    store = EvidenceStore(EvidenceStoreConfig(root=root / "evidence", min_free_bytes=0))
    for ordinal in range(1, attempts + 1):
        journey = governed_training_journey(trial_id=f"trial_ridge_{ordinal:03d}")
        run_persisted_ridge_trial(
            store,
            operation_id=f"op-attempt-{ordinal}",
            start=replace(
                journey.start,
                l2_penalty=str(ordinal),
                multiplicity_ordinal=ordinal,
            ),
            feature_dataset=journey.features,
            label_dataset=journey.labels,
            fold=journey.fold,
            ended_at=ENDED_AT,
        )
    return store


def _published_deflations(store: EvidenceStore) -> dict[int, Decimal]:
    from quant_system.evidence import EvidenceResourceType

    published: dict[int, Decimal] = {}
    for evidence in store.list_verified(EvidenceResourceType.MODEL):
        metadata = evidence.manifest.metadata
        ordinal = int(str(metadata["multiplicity_count"]))
        published[ordinal] = Decimal(str(metadata["deflated_sharpe_ratio"]))
    return published


def _by_ordinal(redeflated: dict[str, str]) -> tuple[tuple[int, str], ...]:
    return tuple(
        (int(trial_id.rsplit("_", 1)[1]), value) for trial_id, value in sorted(redeflated.items())
    )


# test-allow: loop-in-test — setup loop over literal tuples (2, 3)
def test_tail_deletion_leaves_detectable_orphan_blobs(tmp_path: Path) -> None:
    """Red Team Major 1: discarding trailing attempts silently rolled multiplicity back.

    Deleting the tail is exactly the shape a researcher discarding unwanted attempts
    produces, and the contiguity check cannot see it. The content-addressed blobs those
    attempts published survive the deletion, so the store can still report that the catalog
    no longer accounts for everything it once wrote.
    """
    import shutil

    from quant_system.evidence import EvidenceResourceType

    store = _campaign(tmp_path, attempts=3)
    assert store.rebuild_index().orphan_blob_hashes == ()

    for ordinal in (2, 3):
        trial_id = f"trial_ridge_{ordinal:03d}"
        shutil.rmtree(tmp_path / "evidence" / "trials" / trial_id)
        shutil.rmtree(tmp_path / "evidence" / "trials" / f"{trial_id}_outcome")
    for evidence in store.list_verified(EvidenceResourceType.MODEL):
        metadata = evidence.manifest.metadata
        if int(str(metadata["multiplicity_count"])) > 1:
            shutil.rmtree(tmp_path / "evidence" / "models" / str(metadata["model_id"]))

    report = store.rebuild_index()

    assert load_persisted_trial_registry(store).multiplicity_count == 1
    assert report.invalid_resource_ids == ()
    assert report.orphan_blob_hashes != ()
