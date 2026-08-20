"""Independent-root replay proof for the governed ridge training journey."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from quant_system.evidence import EvidenceStore, EvidenceStoreConfig
from quant_system.modeling import PersistedRidgeTrialV1, run_persisted_ridge_trial
from tests.modeling_training_fixtures import governed_training_journey

STORE_TIME = datetime(2026, 8, 20, 12, 10, tzinfo=UTC)
ENDED_AT = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)


def test_training_replay_is_byte_stable_across_independent_roots(tmp_path: Path) -> None:
    journey = governed_training_journey()
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_store = _store(first_root)
    second_store = _store(second_root)

    first = run_persisted_ridge_trial(
        first_store,
        operation_id="op-replay-first",
        start=journey.start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )
    second = run_persisted_ridge_trial(
        second_store,
        operation_id="op-replay-second",
        start=journey.start,
        feature_dataset=journey.features,
        label_dataset=journey.labels,
        fold=journey.fold,
        ended_at=ENDED_AT,
    )

    assert first.evaluation == second.evaluation
    assert first.outcome == second.outcome
    assert _manifest_hashes(first) == _manifest_hashes(second)
    assert (
        _manifest_hashes(first)
        == (
            "a37565d0ffdad10b158628f3889efee00a340bc915c7529ca082bde516b4f907",  # pragma: allowlist secret - deterministic public test hash.
            "27e8e6b0bfa86e553bbfacf720fa164ae8c1b5fb3f5a018bfb15949c452decbb",  # pragma: allowlist secret - deterministic public test hash.
            "4a5183af056a76552ed32aae6b7b590af5a3aa1b8ff21d22e8c94799eacf77b6",  # pragma: allowlist secret - deterministic public test hash.
        )
    )
    assert _published_files(first_root) == _published_files(second_root)


def _store(root: Path) -> EvidenceStore:
    return EvidenceStore(
        EvidenceStoreConfig(
            root=root,
            min_free_bytes=0,
            clock=lambda: STORE_TIME,
        )
    )


def _manifest_hashes(run: PersistedRidgeTrialV1) -> tuple[str, str, str]:
    return (
        run.start_commit.manifest.manifest_hash,
        run.evaluation_commit.manifest.manifest_hash,
        run.outcome_commit.manifest.manifest_hash,
    )


def _published_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "locks" not in path.parts
    }
