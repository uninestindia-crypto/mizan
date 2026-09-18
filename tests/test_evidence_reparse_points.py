"""Evidence paths must refuse every reparse point, not only the subset `is_symlink()` reports.

`Path.is_symlink()` returns False for a Windows junction (`mklink /J`). Windows is this project's
build target, and on it the redirection an unprivileged user can actually create is the junction:
`os.symlink` needs `SeCreateSymbolicLinkPrivilege` and `mklink /J` needs nothing. So a guard that
only sees symlinks did not mean what its name said on the platform that matters.

That was not cosmetic. `EvidenceStore.recover()` builds `staging_root` and `quarantine` directly
from `self.root` rather than through `_contained_path`, so `reject_symlink` is the only containment
guard on that path. With `quarantine/staging` junctioned to a sibling directory, `recover()`
reported a successful quarantine while writing staged evidence outside the configured root.

These tests are Windows-only because a junction is a Windows construct. On POSIX the guard's
`is_symlink()` branch already does the whole job and is covered by the store's own suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from quant_system.evidence import (
    EvidenceIntegrityError,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.evidence.io import read_bounded, reject_symlink

windows_only = pytest.mark.skipif(
    os.name != "nt", reason="a junction is a Windows reparse point; POSIX has no equivalent to make"
)


@windows_only
def test_the_guard_refuses_a_junction(tmp_path: Path) -> None:
    """The exact gap: `is_symlink()` is False for a junction, so the guard let it through."""
    target = tmp_path / "outside"
    target.mkdir()
    link = tmp_path / "link"
    _make_junction(link, target)

    assert not link.is_symlink(), "precondition: is_symlink() does not report a junction"

    with pytest.raises(EvidenceIntegrityError, match="reparse"):
        reject_symlink(link)


@windows_only
def test_recover_no_longer_writes_outside_the_root_through_a_junction(tmp_path: Path) -> None:
    """The escape this repair exists to close, driven through the real public API.

    `recover()` is the one place in the store that builds its paths directly instead of through
    `_contained_path`, so it had no second line of defence behind the guard.
    """
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "store"
    (root / "quarantine").mkdir(parents=True)
    staged = root / ".staging" / "stagedwork"
    staged.mkdir(parents=True)
    (staged / "manifest.json").write_text("staged evidence", encoding="utf-8")
    _make_junction(root / "quarantine" / "staging", outside)

    store = EvidenceStore(EvidenceStoreConfig(root=root))

    with pytest.raises(EvidenceIntegrityError, match="reparse"):
        store.recover()

    assert not list(outside.iterdir()), (
        f"recover() wrote outside the configured root: {[p.name for p in outside.iterdir()]}"
    )
    assert staged.is_dir(), "the staged directory should be left in place for a human to inspect"


@windows_only
def test_the_guard_separates_a_junction_from_an_ordinary_entry(tmp_path: Path) -> None:
    """The discrimination, asserted on both sides in one case.

    A repair that rejects everything would pass a test that only checks the junction is refused, so
    the accepted and refused sides belong together where the contrast is visible.
    """
    ordinary_directory = tmp_path / "plain"
    ordinary_directory.mkdir()
    ordinary_file = tmp_path / "plain.json"
    ordinary_file.write_text("{}", encoding="utf-8")
    target = tmp_path / "outside"
    target.mkdir()
    junction = tmp_path / "link"
    _make_junction(junction, target)

    reject_symlink(ordinary_directory)
    reject_symlink(ordinary_file)

    with pytest.raises(EvidenceIntegrityError, match="reparse") as refusal:
        reject_symlink(junction)
    assert junction.name in str(refusal.value), "the refusal must name the offending entry"


def test_a_missing_path_still_reports_absence_rather_than_a_reparse_error(tmp_path: Path) -> None:
    """The contract `read_bounded` depends on, asserted through `read_bounded` itself.

    The guard runs before the open, and `Path.is_symlink()` returns False for a missing path rather
    than raising. If the reparse check let an `OSError` escape instead of swallowing it, every
    bounded read of an absent file would report a reparse point instead of a missing one. Asserting
    the message keeps that honest where asserting "did not throw" would not.

    Not Windows-only: the contract is identical on every platform.
    """
    with pytest.raises(EvidenceIntegrityError, match="is missing"):
        read_bounded(tmp_path / "does-not-exist", 128, description="manifest")


def _make_junction(link: Path, target: Path) -> None:
    """Create a directory junction, or skip when this machine cannot make one."""
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not link.exists():
        # Conditional on the filesystem supporting junctions, not a permanent skip. The cases are
        # already gated to Windows; this covers a Windows machine where `mklink /J` is refused --
        # a FAT or network volume, or a locked-down runner.
        # test-allow: skipped-test - environment cannot create a junction; never skips on CI
        pytest.skip(f"could not create a junction on this machine: {result.stderr.strip()}")
    assert sys.platform == "win32"
