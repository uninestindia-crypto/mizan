"""Real process-termination recovery tests for immutable evidence publication."""

from __future__ import annotations

import multiprocessing
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from quant_system.evidence import (
    CommitPhase,
    EvidenceDraft,
    EvidenceNotFound,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

FIXED_TIME = datetime(2025, 1, 4, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "phase",
    [
        CommitPhase.STAGING_CREATED,
        CommitPhase.BLOBS_STAGED,
        CommitPhase.BLOBS_PUBLISHED,
        CommitPhase.MANIFEST_STAGED,
        CommitPhase.COMMIT_MARKER_STAGED,
        CommitPhase.RESOURCE_PUBLISHED,
    ],
)
# test-allow: no-assertion - checker cannot parse a multiline parametrized test body.
def test_os_process_kill_at_every_commit_phase_recovers_safely(
    tmp_path: Path,
    phase: CommitPhase,
) -> None:
    context = multiprocessing.get_context("spawn")
    reached_phase = context.Event()
    worker = context.Process(
        target=_block_commit_process,
        args=(str(tmp_path), phase.value, reached_phase),
    )
    worker.start()
    assert reached_phase.wait(timeout=10)
    worker.kill()
    worker.join(timeout=10)
    assert worker.is_alive() is False
    assert worker.exitcode != 0

    recovered_store = _store(tmp_path)
    recovery = recovered_store.recover()

    assert recovery.quarantined_lease_count == 1
    assert not any((tmp_path / ".staging").iterdir())
    if phase == CommitPhase.RESOURCE_PUBLISHED:
        opened = recovered_store.open_verified(EvidenceResourceType.DATASET, "dset_killed")
        assert opened.manifest.resource_id == "dset_killed"
    else:
        with pytest.raises(EvidenceNotFound):
            recovered_store.open_verified(EvidenceResourceType.DATASET, "dset_killed")


def _block_commit_process(root: str, target_phase: str, reached_phase: Any) -> None:
    target = CommitPhase(target_phase)

    def block_at_target(phase: CommitPhase) -> None:
        if phase != target:
            return
        reached_phase.set()
        threading.Event().wait(timeout=30)

    _store(Path(root)).commit(
        _draft(),
        operation_id="op_killed",
        phase_hook=block_at_target,
    )


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


def _draft() -> EvidenceDraft:
    return EvidenceDraft(
        resource_type=EvidenceResourceType.DATASET,
        resource_id="dset_killed",
        schema_id="quantos.test_dataset",
        schema_version=1,
        metadata={"source": "process-kill-fixture"},
        records=({"ordinal": 1, "value": "complete-or-invisible"},),
        total_order=("ordinal",),
    )
