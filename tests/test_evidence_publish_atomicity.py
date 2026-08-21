"""Regressions proving a failed commit never leaves a resource behind."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quant_system.evidence import (
    EvidenceDraft,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.evidence.errors import (
    EvidenceBusy,
    EvidenceIntegrityError,
    EvidenceLimitExceeded,
)

STORE_TIME = datetime(2026, 8, 20, 12, 10, tzinfo=UTC)


def test_oversized_metadata_is_refused_without_publishing_anything(tmp_path: Path) -> None:
    """Red Team Blocker 3A: metadata past max_manifest_bytes must not brick the catalog."""
    store = _store(tmp_path)
    store.commit(_draft("trial_good"), operation_id="op-good")

    with pytest.raises((EvidenceLimitExceeded, EvidenceIntegrityError)):
        store.commit(
            _draft("trial_probe", metadata={"note": "x" * 1_200_000}),
            operation_id="op-bigmeta",
        )

    assert not (tmp_path / "trials" / "trial_probe").exists()
    assert [
        evidence.manifest.resource_id
        for evidence in store.list_verified(EvidenceResourceType.TRIAL)
    ] == ["trial_good"]
    assert store.rebuild_index().invalid_resource_ids == ()


def test_boolean_schema_version_is_refused_at_write_time(tmp_path: Path) -> None:
    """Red Team Blocker 3B: bool subclasses int, so `!= 1` alone let True through."""
    store = _store(tmp_path)
    store.commit(_draft("trial_good"), operation_id="op-good")

    with pytest.raises((ValueError, EvidenceIntegrityError)):
        store.commit(
            _draft("trial_bool", schema_version=True),  # noqa: FBT003
            operation_id="op-bool",
        )

    assert not (tmp_path / "trials" / "trial_bool").exists()
    assert [
        evidence.manifest.resource_id
        for evidence in store.list_verified(EvidenceResourceType.TRIAL)
    ] == ["trial_good"]

    store.commit(_draft("trial_bool"), operation_id="op-bool-retry")

    assert [
        evidence.manifest.resource_id
        for evidence in store.list_verified(EvidenceResourceType.TRIAL)
    ] == ["trial_bool", "trial_good"]


def _draft(
    resource_id: str,
    *,
    metadata: dict[str, object] | None = None,
    schema_version: int = 1,
) -> EvidenceDraft:
    return EvidenceDraft(
        resource_type=EvidenceResourceType.TRIAL,
        resource_id=resource_id,
        schema_id="quantos.ridge_trial_start",
        schema_version=schema_version,
        metadata=metadata if metadata is not None else {"note": "x"},
        records=({"trial_id": resource_id},),
        total_order=("trial_id",),
    )


def _store(root: Path, *, lease_wait_seconds: float = 0.0) -> EvidenceStore:
    return EvidenceStore(
        EvidenceStoreConfig(
            root=root,
            min_free_bytes=0,
            clock=lambda: STORE_TIME,
            lease_wait_seconds=lease_wait_seconds,
        )
    )


def test_commit_waits_briefly_for_a_contended_lease(tmp_path: Path) -> None:
    """Red Team Major 4: concurrent publication is the normal case, not an error.

    ``acquire`` used to raise on the first ``FileExistsError`` with no wait, retry, or backoff,
    so two agents publishing at once surfaced ``EvidenceBusy`` to whichever lost the race.
    """
    store = _store(tmp_path, lease_wait_seconds=5.0)
    holder = _store(tmp_path, lease_wait_seconds=5.0)
    held = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with holder._lease.acquire("op-holder", STORE_TIME):
            held.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=hold)
    worker.start()
    try:
        assert held.wait(timeout=5)
        threading.Timer(0.2, release.set).start()
        store.commit(_draft("trial_waited"), operation_id="op-waited")
    finally:
        release.set()
        worker.join(timeout=5)

    assert (
        store.open_verified(EvidenceResourceType.TRIAL, "trial_waited").manifest.resource_id
        == "trial_waited"
    )


def test_a_permanently_held_lease_still_fails_closed(tmp_path: Path) -> None:
    """The wait is bounded: a lease that is never released must still fail closed."""
    store = _store(tmp_path, lease_wait_seconds=0.2)
    holder = _store(tmp_path, lease_wait_seconds=0.2)
    held = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with holder._lease.acquire("op-forever", STORE_TIME):
            held.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=hold)
    worker.start()
    try:
        assert held.wait(timeout=5)
        with pytest.raises(EvidenceBusy):
            store.commit(_draft("trial_blocked"), operation_id="op-blocked")
    finally:
        release.set()
        worker.join(timeout=5)

    assert not (tmp_path / "trials" / "trial_blocked").exists()
