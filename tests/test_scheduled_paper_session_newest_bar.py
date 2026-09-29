"""The scheduled run's "newest cached bar" check reads each instrument's newest dataset only.

It used to verify and parse every dataset ever stored. The store never deletes and each daily
refresh adds 499, so the check grew from 70 s on 2026-09-01 to 3 h 51 min on 2026-09-21, and the
restarted flagship book never got past it. These tests pin the replacement: which datasets it
opens, what date it reports, and that it refuses a dataset it cannot place.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_scheduled_paper_session as scheduled  # noqa: E402


def _manifest(resource_id: str, instrument: str | None, created: datetime) -> SimpleNamespace:
    metadata: dict[str, Any] = {} if instrument is None else {"provider_instrument_id": instrument}
    return SimpleNamespace(resource_id=resource_id, created_at=created, metadata=metadata)


EARLY = datetime(2026, 9, 1, 3, 30, tzinfo=UTC)
LATE = datetime(2026, 9, 24, 12, 1, tzinfo=UTC)


def test_one_dataset_per_instrument_the_newest_created() -> None:
    manifests = [
        _manifest("dset_a_old", "NSE_EQ|A", EARLY),
        _manifest("dset_a_new", "NSE_EQ|A", LATE),
        _manifest("dset_b_only", "NSE_EQ|B", EARLY),
    ]
    assert scheduled.newest_dataset_per_instrument(manifests) == ["dset_a_new", "dset_b_only"]


def test_directory_order_does_not_change_the_choice() -> None:
    forward = [
        _manifest("dset_a_old", "NSE_EQ|A", EARLY),
        _manifest("dset_a_new", "NSE_EQ|A", LATE),
    ]
    assert scheduled.newest_dataset_per_instrument(forward) == ["dset_a_new"]
    assert scheduled.newest_dataset_per_instrument(list(reversed(forward))) == ["dset_a_new"]


def test_a_tie_on_created_at_resolves_to_the_greater_resource_id() -> None:
    tied = [_manifest("dset_x", "NSE_EQ|A", LATE), _manifest("dset_y", "NSE_EQ|A", LATE)]
    assert scheduled.newest_dataset_per_instrument(tied) == ["dset_y"]
    assert scheduled.newest_dataset_per_instrument(list(reversed(tied))) == ["dset_y"]


def test_a_dataset_without_an_instrument_is_refused_not_skipped() -> None:
    with pytest.raises(ValueError, match="dset_orphan has no provider_instrument_id"):
        scheduled.newest_dataset_per_instrument([_manifest("dset_orphan", None, LATE)])


class _FakeStore:
    """Stands in for `EvidenceStore`, recording which datasets were verified."""

    manifests: list[SimpleNamespace] = []
    opened: list[str] = []

    def __init__(self, config: Any) -> None:
        self.config = config

    def list_manifests(self, resource_type: Any) -> tuple[SimpleNamespace, ...]:
        return tuple(self.manifests)

    def open_verified(self, resource_type: Any, resource_id: str) -> SimpleNamespace:
        type(self).opened.append(resource_id)
        return SimpleNamespace(resource_id=resource_id)

    def list_verified(self, resource_type: Any) -> tuple[Any, ...]:
        raise AssertionError("the check must not load every dataset in the store")


def _install_fake_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifests: list[SimpleNamespace],
    last_bar: dict[str, date | None],
) -> type[_FakeStore]:
    (tmp_path / "store").mkdir()
    monkeypatch.setattr(scheduled, "BARS_CACHE", tmp_path)

    store_class = type("Store", (_FakeStore,), {"manifests": manifests, "opened": []})

    import cached_nifty50_evidence

    import quant_system.evidence as evidence

    def acquisition(verified: SimpleNamespace) -> SimpleNamespace:
        newest = last_bar[verified.resource_id]
        records = [] if newest is None else [SimpleNamespace(exchange_date=newest)]
        return SimpleNamespace(records=records)

    monkeypatch.setattr(evidence, "EvidenceStore", store_class)
    monkeypatch.setattr(
        cached_nifty50_evidence, "historical_acquisition_from_verified", acquisition
    )
    return store_class


def test_only_the_newest_dataset_of_each_instrument_is_verified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifests = [
        _manifest("dset_a_old", "NSE_EQ|A", EARLY),
        _manifest("dset_a_new", "NSE_EQ|A", LATE),
        _manifest("dset_b_old", "NSE_EQ|B", EARLY),
        _manifest("dset_b_new", "NSE_EQ|B", LATE),
    ]
    last_bar = {
        "dset_a_old": date(2026, 8, 28),
        "dset_a_new": date(2026, 9, 23),
        "dset_b_old": date(2026, 8, 28),
        "dset_b_new": date(2026, 9, 22),
    }
    store = _install_fake_store(monkeypatch, tmp_path, manifests, last_bar)

    assert scheduled.newest_cached_bar_date() == date(2026, 9, 23)
    assert sorted(store.opened) == ["dset_a_new", "dset_b_new"]


def test_a_truncated_newest_dataset_lowers_the_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The old maximum over every stored dataset could never go down, which left the "went
    backwards" refusal unreachable. The newest data is what the check now reports."""
    manifests = [
        _manifest("dset_a_old", "NSE_EQ|A", EARLY),
        _manifest("dset_a_new", "NSE_EQ|A", LATE),
    ]
    last_bar = {"dset_a_old": date(2026, 9, 23), "dset_a_new": date(2026, 9, 18)}
    _install_fake_store(monkeypatch, tmp_path, manifests, last_bar)

    assert scheduled.newest_cached_bar_date() == date(2026, 9, 18)


def test_an_empty_newest_dataset_does_not_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifests = [
        _manifest("dset_a_new", "NSE_EQ|A", LATE),
        _manifest("dset_b_new", "NSE_EQ|B", LATE),
    ]
    last_bar: dict[str, date | None] = {"dset_a_new": None, "dset_b_new": date(2026, 9, 22)}
    _install_fake_store(monkeypatch, tmp_path, manifests, last_bar)

    assert scheduled.newest_cached_bar_date() == date(2026, 9, 22)


def test_no_store_means_no_bar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(scheduled, "BARS_CACHE", tmp_path / "absent")
    assert scheduled.newest_cached_bar_date() is None
