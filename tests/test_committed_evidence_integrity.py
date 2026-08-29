"""Committed evidence stores must still verify after a checkout.

This closes a blind spot that let a repository-wide defect stay invisible. Evidence resources are
content-addressed: each carries a ``COMMITTED`` marker holding the manifest hash, compared
byte-for-byte on open. With ``core.autocrlf=true`` and a ``* text=auto`` attribute, git rewrites
that marker to CRLF on checkout, appending a byte the hash does not contain, and **every resource in
the store fails integrity**.

It was found by accident. The caches committed on 2026-08-29 went through a branch checkout and then
read 499/499 and 50/50 datasets bad, while older stores stayed clean only because they had never
been re-checked-out since being committed. Their blobs are LF; a fresh clone on Windows would have
corrupted all of them.

**No test opened a committed store, so CI was green throughout.** These tests exist so that cannot
happen again: they read what is actually on disk, which after a clone or a branch switch is what
git wrote, not what was authored.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from quant_system.evidence import EvidenceResourceType, EvidenceStore, EvidenceStoreConfig

REPO_ROOT = Path(__file__).resolve().parent.parent

#: A small committed store, opened through the real verification path. Small so the cost stays
#: proportionate: the byte-level test below is what gives repository-wide coverage.
SAMPLE_STORE = REPO_ROOT / "data/evidence/models/mizan-v1"


def _tracked_committed_markers() -> list[Path]:
    """Every COMMITTED marker git tracks, as absolute paths."""
    result = subprocess.run(
        ["git", "ls-files", "data/evidence/**/COMMITTED"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("git is unavailable, so tracked files cannot be enumerated")
    return [REPO_ROOT / line for line in result.stdout.splitlines() if line]


def test_no_committed_marker_carries_a_carriage_return() -> None:
    """The exact defect: autocrlf appends \\r to the hash marker and every resource fails.

    Checked at the byte level rather than by opening every store, because it is the same failure
    for all 4,000+ of them and this runs in well under a second.
    """
    markers = _tracked_committed_markers()
    assert markers, "no committed evidence markers found; the store layout has moved"
    corrupted = [
        marker.relative_to(REPO_ROOT).as_posix()
        for marker in markers
        if b"\r" in marker.read_bytes()
    ]
    assert not corrupted, (
        f"{len(corrupted)} of {len(markers)} COMMITTED markers contain a carriage return, so their "
        f"stores will fail integrity. This is line-ending conversion on checkout; "
        f"`data/evidence/** -text` in .gitattributes prevents it. First: {corrupted[:3]}"
    )


def test_gitattributes_exempts_evidence_from_line_ending_conversion() -> None:
    """The guard itself, so removing it fails here rather than silently on someone's clone."""
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "data/evidence/** -text" in attributes, (
        ".gitattributes no longer exempts data/evidence from line-ending conversion; committed "
        "evidence stores will be corrupted by checkout on Windows"
    )


@pytest.mark.skipif(not SAMPLE_STORE.exists(), reason="sample evidence store is not present")
def test_a_committed_evidence_store_opens_and_verifies() -> None:
    """Open a committed store through the real path, not just inspect its bytes.

    The byte test above catches the known cause; this catches the class. Anything that makes a
    committed resource unreadable -- a truncated blob, a rewritten manifest, an encoding change --
    surfaces here as a failure to verify rather than as a green suite and a broken clone.
    """
    store = EvidenceStore(EvidenceStoreConfig(root=SAMPLE_STORE))
    verified = [
        resource
        for resource_type in (EvidenceResourceType.MODEL, EvidenceResourceType.TRIAL)
        for resource in store.list_verified(resource_type)
    ]
    assert verified, f"{SAMPLE_STORE.name} verified no resources at all"
