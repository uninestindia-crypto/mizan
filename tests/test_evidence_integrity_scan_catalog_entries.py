"""The integrity scan must not report a store clean that the read path refuses to read.

`_scan_resource_type` silently skipped any non-directory entry in a catalog directory, while
`list_manifests` and `list_verified` treat the identical condition as a fatal
`EvidenceIntegrityError`. That made `scan_integrity()` -- the function an operator or adjudicator
runs to confirm a store is healthy -- more permissive than the reader it exists to certify: one
stray file (a partial copy, an interrupted sync, an editor swapfile, `Thumbs.db`) produced a clean
integrity report on a store `list_verified` could not open.

The property under test is the agreement between the two, not the specific bucket: whatever the read
path refuses, the scan must account for.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from quant_system.evidence import (
    EvidenceDraft,
    EvidenceIntegrityError,
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

FIXED_TIME = datetime(2025, 1, 4, 12, 0, tzinfo=UTC)

#: Every catalog directory an evidence store maintains. The defect was not specific to one of them,
#: so neither is the test: a stray entry is equally unreadable in any.
CATALOG_TYPES = (
    EvidenceResourceType.DATASET,
    EvidenceResourceType.TRIAL,
    EvidenceResourceType.MODEL,
    EvidenceResourceType.OPERATION,
    EvidenceResourceType.SESSION,
    EvidenceResourceType.BUNDLE,
)


@pytest.mark.parametrize("resource_type", CATALOG_TYPES, ids=lambda item: item.value)
def test_a_stray_catalog_entry_is_reported_invalid_not_skipped(
    tmp_path: Path,
    resource_type: EvidenceResourceType,
) -> None:
    """The exact defect: a stray file made the scan report a store it could not read as clean."""
    store = _store(tmp_path)
    (tmp_path / resource_type.value / "stray.txt").write_bytes(b"not a resource")

    report = store.scan_integrity()

    assert "stray.txt" in report.invalid_resource_ids, (
        f"scan_integrity() did not account for a stray entry in {resource_type.value}/, so it "
        f"reports a clean store that list_verified() refuses to read"
    )


@pytest.mark.parametrize("resource_type", CATALOG_TYPES, ids=lambda item: item.value)
def test_the_scan_and_the_read_path_agree_about_a_stray_entry(
    tmp_path: Path,
    resource_type: EvidenceResourceType,
) -> None:
    """The invariant behind the fix, asserted as an agreement rather than as one bucket.

    `list_verified` is the authority here and is deliberately not relaxed: a catalog it cannot
    fully read is a fatal integrity error. The scan is required only to stop calling that clean.
    """
    store = _store(tmp_path)
    (tmp_path / resource_type.value / "stray.txt").write_bytes(b"not a resource")

    with pytest.raises(EvidenceIntegrityError, match="non-directory entry"):
        store.list_verified(resource_type)

    report = store.scan_integrity()
    assert report.invalid_resource_ids, (
        "list_verified() refused this store, so the integrity scan must not report it clean"
    )


def test_a_stray_entry_does_not_hide_the_resources_beside_it(tmp_path: Path) -> None:
    """Why the entry is recorded as invalid rather than raising.

    `_scan_resource_type` already catches a per-resource integrity failure so that one bad resource
    cannot hide the state of every other one. Raising on a stray file would make `scan_integrity`
    unable to report on a store with one stray file at all -- worse than the behaviour it replaces,
    not better.
    """
    store = _store(tmp_path)
    store.commit(_draft("dset_real"), operation_id="op_publish_one")
    (tmp_path / "datasets" / "stray.txt").write_bytes(b"not a resource")

    report = store.scan_integrity()

    assert "dset_real" in report.valid_resource_ids
    assert "stray.txt" in report.invalid_resource_ids


def test_a_clean_store_still_reports_no_invalid_entries(tmp_path: Path) -> None:
    """Guards the repair against becoming a false positive on an ordinary healthy store."""
    store = _store(tmp_path)
    store.commit(_draft("dset_real"), operation_id="op_publish_one")

    report = store.scan_integrity()

    assert report.valid_resource_ids == ("dset_real",)
    assert report.invalid_resource_ids == ()
    assert report.orphan_blob_hashes == ()


def _store(
    root: Path,
    *,
    clock: Callable[[], datetime] = lambda: FIXED_TIME,
) -> EvidenceStore:
    return EvidenceStore(
        EvidenceStoreConfig(
            root=root,
            chunk_uncompressed_bytes=1024,
            max_bundle_bytes=8192,
            min_free_bytes=0,
            clock=clock,
            lease_wait_seconds=0.0,
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
    )
