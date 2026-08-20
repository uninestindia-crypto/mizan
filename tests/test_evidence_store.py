"""Behavior tests for immutable content-addressed evidence publication."""

from __future__ import annotations

import json
import multiprocessing
import threading
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from quant_system.evidence import (
    BlobDescriptor,
    CanonicalizationError,
    CommitPhase,
    EvidenceBusy,
    EvidenceConflict,
    EvidenceDraft,
    EvidenceIntegrityError,
    EvidenceLimitExceeded,
    EvidenceNotFound,
    EvidenceResourceType,
    EvidenceSensitiveData,
    EvidenceStorageError,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.evidence.canonical import canonical_json_bytes, sha256_hex
from quant_system.evidence.io import decompress_bounded

FIXED_TIME = datetime(2025, 1, 4, 12, 0, tzinfo=UTC)


class SimulatedCrash(RuntimeError):
    pass


class SimulatedCancellation(RuntimeError):
    pass


def test_commit_and_verified_open_are_deterministic_and_chunked(tmp_path: Path) -> None:
    store = _store(tmp_path, chunk_bytes=180)

    first = store.commit(_draft("dset_alpha"), operation_id="op_first")
    opened = store.open_verified(EvidenceResourceType.DATASET, "dset_alpha")

    assert first.published is True
    assert first.deduplicated is False
    assert len(first.manifest.blobs) >= 2
    assert opened.manifest == first.manifest
    assert opened.records == _records()
    assert all(blob.canonical_bytes <= 180 for blob in first.manifest.blobs)
    assert all(_gzip_mtime(tmp_path / blob.relative_path) == 0 for blob in first.manifest.blobs)


def test_identical_commit_is_safe_deduplication(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.commit(_draft("dset_same"), operation_id="op_first")

    second = store.commit(_draft("dset_same"), operation_id="op_second")

    assert second.published is False
    assert second.deduplicated is True
    assert second.manifest.manifest_hash == first.manifest.manifest_hash


def test_same_draft_is_byte_deterministic_across_roots(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first = _store(first_root).commit(_draft("dset_stable"), operation_id="op_first")
    second = _store(second_root).commit(_draft("dset_stable"), operation_id="op_second")

    assert first.manifest == second.manifest
    assert (first_root / "datasets/dset_stable/manifest.json").read_bytes() == (
        second_root / "datasets/dset_stable/manifest.json"
    ).read_bytes()
    assert _blob_bytes(first_root, first.manifest.blobs) == _blob_bytes(
        second_root,
        second.manifest.blobs,
    )


def test_same_resource_id_with_different_content_is_conflict(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.commit(_draft("dset_conflict"), operation_id="op_first")
    changed = replace(
        _draft("dset_conflict"),
        records=(*_records()[:-1], {"ordinal": 3, "value": "changed"}),
    )

    with pytest.raises(EvidenceConflict):
        store.commit(changed, operation_id="op_second")


def test_blob_corruption_blocks_all_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = store.commit(_draft("dset_corrupt_blob"), operation_id="op_first")
    blob_path = tmp_path / result.manifest.blobs[0].relative_path
    blob_path.write_bytes(blob_path.read_bytes() + b"tamper")

    with pytest.raises(EvidenceIntegrityError, match="blob"):
        store.open_verified(EvidenceResourceType.DATASET, "dset_corrupt_blob")


def test_manifest_corruption_blocks_open(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.commit(_draft("dset_corrupt_manifest"), operation_id="op_first")
    manifest_path = tmp_path / "datasets" / "dset_corrupt_manifest" / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["metadata"]["source"] = "tampered"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvidenceIntegrityError, match="manifest"):
        store.open_verified(EvidenceResourceType.DATASET, "dset_corrupt_manifest")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("created_at", "2025-01-04T12:00:00", "timezone-aware"),
        ("record_schema", {"id": "quantos.test_dataset", "version": 2}, "record schema"),
        ("blobs", ["not-an-object"], "blob descriptor"),
    ],
)
# test-allow: no-assertion - checker cannot parse this multiline parametrized test signature.
def test_coherently_rehashed_invalid_manifest_schema_is_rejected(
    tmp_path: Path,
    field: str,
    value: Any,
    message: str,
) -> None:
    store = _store(tmp_path)
    store.commit(_draft("dset_bad_schema"), operation_id="op_first")
    _rewrite_manifest(tmp_path, "dset_bad_schema", field, value)

    with pytest.raises(EvidenceIntegrityError, match=message):
        store.open_verified(EvidenceResourceType.DATASET, "dset_bad_schema")


@pytest.mark.parametrize(
    "phase",
    [
        CommitPhase.STAGING_CREATED,
        CommitPhase.BLOBS_STAGED,
        CommitPhase.BLOBS_PUBLISHED,
        CommitPhase.MANIFEST_STAGED,
        CommitPhase.COMMIT_MARKER_STAGED,
    ],
)
# test-allow: no-assertion - checker cannot parse a multiline parametrized signature body.
def test_crash_before_atomic_publication_never_exposes_resource(
    tmp_path: Path,
    phase: CommitPhase,
) -> None:
    store = _store(tmp_path)

    with pytest.raises(SimulatedCrash):
        store.commit(
            _draft("dset_crash"),
            operation_id="op_crash",
            phase_hook=lambda observed: _crash_at(observed, phase),
        )

    with pytest.raises(EvidenceNotFound):
        store.open_verified(EvidenceResourceType.DATASET, "dset_crash")
    recovery = store.recover()
    assert recovery.quarantined_staging_count == 1
    assert not any((tmp_path / ".staging").iterdir())


def test_cooperative_cancellation_leaves_no_visible_resource(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(SimulatedCancellation, match="cancelled"):
        store.commit(
            _draft("dset_cancelled"),
            operation_id="op_cancelled",
            phase_hook=lambda phase: _cancel_after_blob_staging(phase),
        )

    with pytest.raises(EvidenceNotFound):
        store.open_verified(EvidenceResourceType.DATASET, "dset_cancelled")
    assert store.recover().quarantined_staging_count == 1


def test_missing_commit_marker_blocks_open(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.commit(_draft("dset_marker"), operation_id="op_first")
    marker = tmp_path / "datasets" / "dset_marker" / "COMMITTED"
    marker.unlink()

    with pytest.raises(EvidenceIntegrityError, match="commit marker"):
        store.open_verified(EvidenceResourceType.DATASET, "dset_marker")


def test_commit_marker_hash_tamper_blocks_open(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.commit(_draft("dset_marker_hash"), operation_id="op_first")
    marker = tmp_path / "datasets" / "dset_marker_hash" / "COMMITTED"
    marker.write_bytes(f"{'0' * 64}\n".encode())

    with pytest.raises(EvidenceIntegrityError, match="commit marker"):
        store.open_verified(EvidenceResourceType.DATASET, "dset_marker_hash")


def test_crash_after_atomic_publication_is_recoverable_by_idempotent_retry(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(SimulatedCrash):
        store.commit(
            _draft("dset_published_crash"),
            operation_id="op_crash",
            phase_hook=lambda observed: _crash_at(observed, CommitPhase.RESOURCE_PUBLISHED),
        )

    opened = store.open_verified(EvidenceResourceType.DATASET, "dset_published_crash")
    retry = store.commit(_draft("dset_published_crash"), operation_id="op_retry")
    assert opened.manifest == retry.manifest
    assert retry.deduplicated is True


def test_commit_does_not_report_success_before_published_readback(tmp_path: Path) -> None:
    store = _store(tmp_path)

    def corrupt_after_publish(phase: CommitPhase) -> None:
        if phase == CommitPhase.RESOURCE_PUBLISHED:
            blob = next((tmp_path / "blobs").rglob("*.jsonl.gz"))
            blob.write_bytes(blob.read_bytes() + b"corrupt-after-rename")

    with pytest.raises(EvidenceIntegrityError, match="blob"):
        store.commit(
            _draft("dset_readback"),
            operation_id="op_readback",
            phase_hook=corrupt_after_publish,
        )

    assert store.rebuild_index().invalid_resource_ids == ("dset_readback",)


def test_active_reference_can_rollback_a_to_b_to_a(tmp_path: Path) -> None:
    store = _store(tmp_path)
    artifact_a = store.commit(_draft("dset_a"), operation_id="op_a").manifest.identity
    artifact_b = store.commit(_draft("dset_b"), operation_id="op_b").manifest.identity

    store.set_active("research-dataset", artifact_a)
    store.set_active("research-dataset", artifact_b)
    rolled_back = store.set_active("research-dataset", artifact_a)

    assert rolled_back.target == artifact_a
    assert store.resolve_active("research-dataset").manifest.identity == artifact_a


def test_failed_pointer_replace_preserves_previous_reference(tmp_path: Path) -> None:
    store = _store(tmp_path)
    artifact_a = store.commit(_draft("dset_a"), operation_id="op_a").manifest.identity
    artifact_b = store.commit(_draft("dset_b"), operation_id="op_b").manifest.identity
    store.set_active("research-dataset", artifact_a)

    with pytest.raises(SimulatedCrash):
        store.set_active(
            "research-dataset",
            artifact_b,
            before_replace=lambda: (_ for _ in ()).throw(SimulatedCrash("pointer crash")),
        )

    assert store.resolve_active("research-dataset").manifest.identity == artifact_a


def test_active_reference_cannot_redirect_to_wrong_manifest_hash(tmp_path: Path) -> None:
    store = _store(tmp_path)
    target = store.commit(_draft("dset_active_hash"), operation_id="op_target").manifest.identity
    store.set_active("research-dataset", target)
    pointer_path = tmp_path / "active" / "research-dataset.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["target"]["manifest_hash"] = "0" * 64
    pointer["reference_hash"] = sha256_hex(
        canonical_json_bytes(
            {key: value for key, value in pointer.items() if key != "reference_hash"}
        )
    )
    pointer_path.write_bytes(canonical_json_bytes(pointer))

    with pytest.raises(EvidenceIntegrityError, match="target hash"):
        store.resolve_active("research-dataset")


def test_path_traversal_resource_id_is_rejected_before_write(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(ValueError, match="resource_id"):
        store.commit(_draft("dset_../../escape"), operation_id="op_bad")
    assert tuple(tmp_path.parent.glob("escape*")) == ()


@pytest.mark.parametrize(
    "secret_key",
    ["access_token", "upstox_access_token", "authorization_header"],
)
def test_secret_shaped_metadata_is_rejected(tmp_path: Path, secret_key: str) -> None:
    store = _store(tmp_path)
    draft = replace(_draft("dset_secret"), metadata={secret_key: "must-not-persist"})

    with pytest.raises(EvidenceSensitiveData, match=secret_key):
        store.commit(draft, operation_id="op_secret")


def test_float_is_rejected_from_canonical_evidence(tmp_path: Path) -> None:
    store = _store(tmp_path)
    draft = replace(_draft("dset_float"), records=({"ordinal": 1, "value": 1.5},))

    with pytest.raises(CanonicalizationError, match="float"):
        store.commit(draft, operation_id="op_float")


def test_oversized_integer_encoding_fails_with_typed_canonical_error(tmp_path: Path) -> None:
    store = _store(tmp_path)
    draft = replace(
        _draft("dset_huge_integer"),
        records=({"ordinal": 1, "value": 10**5000},),
    )

    with pytest.raises(CanonicalizationError, match="encode"):
        store.commit(draft, operation_id="op_huge_integer")


# test-allow: loop-in-test - fixed iterations construct one over-depth recursive input.
def test_excessive_canonical_nesting_is_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    nested: dict[str, Any] = {"value": "bottom"}
    for _index in range(34):
        nested = {"child": nested}
    draft = replace(_draft("dset_deep"), metadata=nested)

    with pytest.raises(CanonicalizationError, match="depth"):
        store.commit(draft, operation_id="op_deep")


def test_out_of_order_and_duplicate_total_keys_are_rejected(tmp_path: Path) -> None:
    store = _store(tmp_path)
    out_of_order = replace(
        _draft("dset_order"),
        records=({"ordinal": 2}, {"ordinal": 1}, {"ordinal": 1}),
    )

    with pytest.raises(EvidenceIntegrityError, match="strict total order"):
        store.commit(out_of_order, operation_id="op_order")


def test_bundle_limit_is_enforced_before_publication(tmp_path: Path) -> None:
    store = _store(tmp_path, chunk_bytes=512, max_bundle_bytes=512)
    draft = replace(
        _draft("dset_too_large"),
        records=({"ordinal": 1, "value": "x" * 600},),
    )

    with pytest.raises(EvidenceLimitExceeded, match="512"):
        store.commit(draft, operation_id="op_large")
    assert not (tmp_path / "datasets" / "dset_too_large").exists()


def test_near_limit_bundle_commits_and_reopens_exactly(tmp_path: Path) -> None:
    store = _store(tmp_path, chunk_bytes=1024, max_bundle_bytes=1024)
    draft = replace(
        _draft("dset_near_limit"),
        records=({"ordinal": 1, "value": "x" * 950},),
    )

    committed = store.commit(draft, operation_id="op_near_limit")
    opened = store.open_verified(EvidenceResourceType.DATASET, "dset_near_limit")

    assert 950 < committed.manifest.canonical_bytes <= 1024
    assert opened.records == draft.records


# test-allow: no-assertion - checker cannot parse a multiline signature with fixtures.
def test_insufficient_disk_is_rejected_before_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path, min_free_bytes=1)
    monkeypatch.setattr(
        "quant_system.evidence.store.shutil.disk_usage",
        lambda _path: SimpleNamespace(free=0),
    )

    with pytest.raises(EvidenceStorageError, match="free bytes"):
        store.commit(_draft("dset_no_space"), operation_id="op_no_space")

    assert not (tmp_path / "datasets" / "dset_no_space").exists()
    assert not any((tmp_path / ".staging").iterdir())


# test-allow: no-assertion - checker cannot parse a multiline signature with fixtures.
def test_write_failure_never_exposes_partial_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)

    def fail_write(_path: Path, _contents: bytes) -> None:
        raise OSError("simulated disk failure")

    monkeypatch.setattr("quant_system.evidence.store.write_fsynced", fail_write)
    with pytest.raises(OSError, match="simulated disk failure"):
        store.commit(_draft("dset_write_failure"), operation_id="op_write_failure")

    assert not (tmp_path / "datasets" / "dset_write_failure").exists()
    report = store.recover()
    assert report.quarantined_staging_count == 1


def test_concurrent_store_instance_is_refused_without_mutation(tmp_path: Path) -> None:
    first_store = _store(tmp_path)
    second_store = _store(tmp_path)
    lease_held = threading.Event()
    release_lease = threading.Event()
    thread_error: list[BaseException] = []

    def hold_commit() -> None:
        try:
            first_store.commit(
                _draft("dset_first"),
                operation_id="op_first",
                phase_hook=lambda phase: _hold_at_manifest(
                    phase,
                    lease_held=lease_held,
                    release_lease=release_lease,
                ),
            )
        except BaseException as error:  # pragma: no cover - asserted after join
            thread_error.append(error)

    worker = threading.Thread(target=hold_commit)
    worker.start()
    assert lease_held.wait(timeout=2)
    try:
        with pytest.raises(EvidenceBusy):
            second_store.commit(_draft("dset_second"), operation_id="op_second")
    finally:
        release_lease.set()
        worker.join(timeout=2)

    assert worker.is_alive() is False
    assert thread_error == []
    assert not (tmp_path / "datasets" / "dset_second").exists()


def test_live_cross_process_lease_blocks_commit_and_recovery(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    errors = context.Queue()
    worker = context.Process(
        target=_hold_commit_process,
        args=(str(tmp_path), ready, release, errors),
    )
    worker.start()
    assert ready.wait(timeout=10)
    competing_store = _store(tmp_path)
    try:
        with pytest.raises(EvidenceBusy, match="op_process"):
            competing_store.commit(_draft("dset_competing"), operation_id="op_competing")
        with pytest.raises(EvidenceBusy, match="op_process"):
            competing_store.recover()
        assert (tmp_path / ".staging").is_dir()
        assert any((tmp_path / ".staging").iterdir())
    finally:
        release.set()
        worker.join(timeout=10)
        if worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)

    assert worker.exitcode == 0
    assert errors.empty()
    assert (
        competing_store.open_verified(
            EvidenceResourceType.DATASET,
            "dset_process",
        ).manifest.resource_id
        == "dset_process"
    )


def test_stale_lease_is_quarantined_before_recovery_continues(tmp_path: Path) -> None:
    store = _store(tmp_path)
    lease_path = tmp_path / "locks" / "governed-operation.lock"
    lease_path.write_bytes(
        canonical_json_bytes(
            {
                "acquired_at": "2025-01-01T00:00:00Z",
                "heartbeat_at": "2025-01-01T00:00:05Z",
                "operation_id": "op_dead",
                "pid": 2_000_000_000,
                "process_identity": "dead-process",
                "schema_id": "quantos.evidence_lease",
                "schema_version": 1,
                "token": "0" * 32,
            }
        )
    )

    report = store.recover()

    assert report.quarantined_lease_count == 1
    assert not lease_path.exists()
    assert len(tuple((tmp_path / "quarantine" / "leases").iterdir())) == 1


def test_oversized_lease_fails_closed_without_touching_staging(tmp_path: Path) -> None:
    store = _store(tmp_path)
    staged = tmp_path / ".staging" / "orphan"
    staged.mkdir()
    lease_path = tmp_path / "locks" / "governed-operation.lock"
    lease_path.write_bytes(b"x" * 4097)

    with pytest.raises(EvidenceIntegrityError, match="size limit"):
        store.recover()

    assert staged.is_dir()


def test_lease_heartbeat_advances_at_publication_phase_boundaries(tmp_path: Path) -> None:
    ticks = iter(FIXED_TIME + timedelta(seconds=index) for index in range(10))
    store = _store(tmp_path, clock=lambda: next(ticks))
    observed: dict[str, Any] = {}

    def capture_lease(phase: CommitPhase) -> None:
        if phase == CommitPhase.MANIFEST_STAGED:
            lease_path = tmp_path / "locks" / "governed-operation.lock"
            observed.update(json.loads(lease_path.read_text(encoding="utf-8")))

    store.commit(
        _draft("dset_heartbeat"),
        operation_id="op_heartbeat",
        phase_hook=capture_lease,
    )

    assert observed["operation_id"] == "op_heartbeat"
    assert observed["heartbeat_at"] > observed["acquired_at"]


def test_bounded_decompression_rejects_truncation_and_expansion() -> None:
    import gzip

    stored = gzip.compress(b"bounded\n", mtime=0)

    with pytest.raises(EvidenceIntegrityError, match="gzip"):
        decompress_bounded(stored[:-3], expected_bytes=8)
    with pytest.raises(EvidenceIntegrityError, match="size"):
        decompress_bounded(stored, expected_bytes=2)


# test-allow: no-assertion - checker cannot parse a multiline signature with fixtures.
def test_blob_symlink_is_rejected_before_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    result = store.commit(_draft("dset_symlink"), operation_id="op_symlink")
    blob_path = tmp_path / result.manifest.blobs[0].relative_path
    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == blob_path or real_is_symlink(path),
    )

    with pytest.raises(EvidenceIntegrityError, match="symbolic links"):
        store.open_verified(EvidenceResourceType.DATASET, "dset_symlink")


# test-allow: no-assertion - checker cannot parse a multiline signature with fixtures.
def test_configured_store_directory_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "evidence"
    root.mkdir()
    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path.name == ".staging" or real_is_symlink(path),
    )

    with pytest.raises(EvidenceIntegrityError, match="symbolic links"):
        _store(root)


def test_rebuilt_index_is_deterministic_and_reports_corrupt_resources(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.commit(_draft("dset_valid"), operation_id="op_valid")
    corrupt_draft = replace(
        _draft("dset_invalid"),
        records=(*_records()[:-1], {"ordinal": 3, "value": "separate-blob"}),
    )
    corrupt = store.commit(corrupt_draft, operation_id="op_invalid")
    corrupt_path = tmp_path / corrupt.manifest.blobs[0].relative_path
    corrupt_path.write_bytes(b"corrupt")

    report = store.rebuild_index()
    repeated = store.rebuild_index()

    assert report.valid_resource_ids == ("dset_valid",)
    assert report.invalid_resource_ids == ("dset_invalid",)
    assert repeated == report


def test_rebuilt_index_reports_invalid_resource_directory_name(tmp_path: Path) -> None:
    store = _store(tmp_path)
    (tmp_path / "datasets" / "unexpected-directory").mkdir()

    report = store.rebuild_index()

    assert report.valid_resource_ids == ()
    assert report.invalid_resource_ids == ("unexpected-directory",)


def test_different_consumed_value_changes_manifest_and_blob_hash(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.commit(_draft("dset_first"), operation_id="op_first")
    changed = replace(
        _draft("dset_second"),
        records=(*_records()[:-1], {"ordinal": 3, "value": "changed"}),
    )

    second = store.commit(changed, operation_id="op_second")

    assert second.manifest.manifest_hash != first.manifest.manifest_hash
    assert second.manifest.canonical_records_hash != first.manifest.canonical_records_hash


def _store(
    root: Path,
    *,
    chunk_bytes: int = 1024,
    max_bundle_bytes: int = 8192,
    min_free_bytes: int = 0,
    clock: Callable[[], datetime] = lambda: FIXED_TIME,
) -> EvidenceStore:
    return EvidenceStore(
        EvidenceStoreConfig(
            root=root,
            chunk_uncompressed_bytes=chunk_bytes,
            max_bundle_bytes=max_bundle_bytes,
            min_free_bytes=min_free_bytes,
            clock=clock,
        )
    )


def _draft(resource_id: str) -> EvidenceDraft:
    return EvidenceDraft(
        resource_type=EvidenceResourceType.DATASET,
        resource_id=resource_id,
        schema_id="quantos.test_dataset",
        schema_version=1,
        metadata={"source": "recorded-fixture", "currency": "INR"},
        records=_records(),
        total_order=("ordinal",),
    )


def _records() -> tuple[dict[str, Any], ...]:
    return (
        {"ordinal": 1, "value": "alpha" * 20},
        {"ordinal": 2, "value": "beta" * 20},
        {"ordinal": 3, "value": "gamma" * 20},
    )


def _gzip_mtime(path: Path) -> int:
    contents = path.read_bytes()
    return int.from_bytes(contents[4:8], byteorder="little")


def _rewrite_manifest(root: Path, resource_id: str, field: str, value: Any) -> None:
    resource = root / "datasets" / resource_id
    manifest_path = resource / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload[field] = value
    unsigned = {key: item for key, item in payload.items() if key != "manifest_hash"}
    payload["manifest_hash"] = sha256_hex(canonical_json_bytes(unsigned))
    manifest_path.write_bytes(canonical_json_bytes(payload))
    (resource / "COMMITTED").write_bytes(f"{payload['manifest_hash']}\n".encode())


def _blob_bytes(root: Path, descriptors: Sequence[BlobDescriptor]) -> tuple[bytes, ...]:
    return tuple((root / descriptor.relative_path).read_bytes() for descriptor in descriptors)


def _crash_at(observed: CommitPhase, target: CommitPhase) -> None:
    if observed == target:
        raise SimulatedCrash(f"crash at {target.value}")


def _cancel_after_blob_staging(phase: CommitPhase) -> None:
    if phase == CommitPhase.BLOBS_STAGED:
        raise SimulatedCancellation("commit cancelled by caller")


def _hold_at_manifest(
    phase: CommitPhase,
    *,
    lease_held: threading.Event,
    release_lease: threading.Event,
) -> None:
    if phase != CommitPhase.MANIFEST_STAGED:
        return
    lease_held.set()
    if not release_lease.wait(timeout=2):
        raise TimeoutError("test did not release evidence lease")


def _hold_commit_process(
    root: str,
    ready: Any,
    release: Any,
    errors: Any,
) -> None:
    try:
        _store(Path(root)).commit(
            _draft("dset_process"),
            operation_id="op_process",
            phase_hook=lambda phase: _hold_process_at_manifest(phase, ready, release),
        )
    except BaseException as error:  # pragma: no cover - delivered to the parent process
        errors.put(repr(error))
        raise


def _hold_process_at_manifest(phase: CommitPhase, ready: Any, release: Any) -> None:
    if phase != CommitPhase.MANIFEST_STAGED:
        return
    ready.set()
    if not release.wait(timeout=10):
        raise TimeoutError("parent did not release cross-process evidence lease")
