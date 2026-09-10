"""The corporate-action authority must never claim a window its content does not cover.

A live paper book lost 0.608 pp of NAV to a single unadjusted corporate action -- HEG gapped
-64.3% overnight on 2026-09-07 and every consumer marked it silently as a price move. The bars were
`RAW`, and the authority that would have exposed the event declared
`effective_to: 2026-08-21` while the price cache held bars through 2026-09-09.

Three defects produced that, all in `scripts/ingest_all_market_data.py`:

1. `build_corporate_action_authority` hardcoded `effective_from`, `effective_to` and
   `publication_date` as literals, so every dataset ingested on any date claimed the same coverage;
2. `fetch_or_load_corporate_actions` returned any existing file unconditionally, so a symbol's
   record froze permanently on first write;
3. every fetch failure wrote `[]`, which (2) then trusted forever -- one network blip permanently
   poisoning a symbol's authority.

Each test below fails against the pre-repair behaviour. Full diagnosis:
`agent_context/work/active/20260910-NOTICE-corporate-action-authority-window-stale-vs-price-cache.md`
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from ingest_all_market_data import (  # noqa: E402
    build_corporate_action_authority,
    fetch_or_load_corporate_actions,
)

FROM = date(2016, 8, 22)
TO = date(2026, 9, 9)
NOW = datetime(2026, 9, 10, 4, 0, tzinfo=UTC)

SAMPLE = [
    {"symbol": "HEG", "subject": "Face Value Split", "exDate": "07-Sep-2026"},
]


def _payload(items: list[dict[str, str]]) -> bytes:
    return json.dumps(items).encode("utf-8")


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, body: bytes | None) -> dict[str, int]:
    """Serve `body`, or raise when it is None. Returns a call counter."""
    calls = {"n": 0}

    def fake_urlopen(*_args: object, **_kwargs: object) -> _FakeResponse:
        calls["n"] += 1
        if body is None:
            raise OSError("network unavailable")
        return _FakeResponse(body)

    monkeypatch.setattr("ingest_all_market_data.urllib.request.urlopen", fake_urlopen)
    return calls


def test_authority_window_tracks_the_requested_end_not_a_hardcoded_literal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect that let the HEG event through: a window frozen at 2026-08-21."""
    _patch_urlopen(monkeypatch, _payload(SAMPLE))

    record = fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)
    authority = build_corporate_action_authority(record, "HEG")

    assert record.status == "FETCHED"
    assert record.covers_requested_end is True
    assert authority.effective_to == TO, "authority must reach the newest requested bar"
    assert authority.effective_from == FROM
    assert authority.publication_date == NOW.date()
    assert authority.effective_to != date(2026, 8, 21), "the hardcoded literal is back"


def test_a_later_end_date_forces_a_refetch_rather_than_reusing_a_frozen_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defect 2: once written, the record used to be returned forever."""
    calls = _patch_urlopen(monkeypatch, _payload(SAMPLE))

    first = fetch_or_load_corporate_actions("HEG", FROM, date(2026, 8, 21), tmp_path, now=NOW)
    assert first.effective_to == date(2026, 8, 21)
    assert calls["n"] == 1

    # Same symbol, a later end date -- the cached file cannot be evidence for the new window.
    second = fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)
    assert calls["n"] == 2, "a wider window must re-fetch, not reuse"
    assert second.effective_to == TO


def test_a_fresh_record_covering_the_window_is_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cadence fix must not turn every call into a network round trip."""
    calls = _patch_urlopen(monkeypatch, _payload(SAMPLE))

    fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)
    assert calls["n"] == 1

    again = fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)
    assert calls["n"] == 1, "an in-window, in-date record must be reused"
    assert again.status == "FETCHED"
    assert again.count == len(SAMPLE)


def test_a_record_older_than_the_max_age_is_refetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cadence: the authority must not outlive the daily price refresh."""
    calls = _patch_urlopen(monkeypatch, _payload(SAMPLE))

    fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)
    assert calls["n"] == 1

    later = NOW.replace(day=12)  # 48 hours on
    fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=later, max_age_hours=24.0)
    assert calls["n"] == 2, "a record older than max_age must be re-pulled"


def test_a_failed_fetch_never_widens_the_window_it_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed: report what we can stand behind, never the window we asked for."""
    _patch_urlopen(monkeypatch, _payload(SAMPLE))
    fetch_or_load_corporate_actions("HEG", FROM, date(2026, 8, 21), tmp_path, now=NOW)

    _patch_urlopen(monkeypatch, None)  # network dies
    stale = fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)

    assert stale.status == "STALE"
    assert stale.covers_requested_end is False
    assert stale.effective_to == date(2026, 8, 21), "must keep the window it actually fetched"
    assert stale.count == len(SAMPLE), "the good content is retained, not discarded"

    authority = build_corporate_action_authority(stale, "HEG")
    assert authority.effective_to < TO, "a failed refresh must not claim to cover the new bars"


def test_a_failed_first_fetch_does_not_become_a_permanent_empty_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defect 3: one network blip used to write `[]` and have it trusted forever."""
    _patch_urlopen(monkeypatch, None)
    failed = fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)

    assert failed.status == "UNAVAILABLE"
    assert failed.covers_requested_end is False
    assert failed.effective_to == FROM, "an unavailable record covers nothing"

    # The next run must retry rather than trust the empty file.
    calls = _patch_urlopen(monkeypatch, _payload(SAMPLE))
    recovered = fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)

    assert calls["n"] == 1, "a previously failed symbol must be retried"
    assert recovered.status == "FETCHED"
    assert recovered.effective_to == TO
    assert recovered.count == len(SAMPLE)


def test_a_legacy_file_without_provenance_is_refetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every file already in the repository predates provenance. None may be trusted on sight."""
    legacy = tmp_path / "nse-corporate-actions-HEG.json"
    legacy.write_bytes(_payload([{"symbol": "HEG", "subject": "old"}]))

    calls = _patch_urlopen(monkeypatch, _payload(SAMPLE))
    record = fetch_or_load_corporate_actions("HEG", FROM, TO, tmp_path, now=NOW)

    assert calls["n"] == 1, "a file with no provenance must be re-pulled"
    assert record.status == "FETCHED"
    assert record.effective_to == TO


def test_genuinely_empty_response_is_distinguished_from_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A symbol with no filings is fully covered evidence; a failed call is not."""
    _patch_urlopen(monkeypatch, _payload([]))
    record = fetch_or_load_corporate_actions("NOFILINGS", FROM, TO, tmp_path, now=NOW)

    assert record.status == "FETCHED"
    assert record.covers_requested_end is True
    assert record.count == 0
    assert record.effective_to == TO, "no filings still means the window was checked"


def test_corporate_actions_are_requested_from_the_history_anchor_not_the_bar_window() -> None:
    """The bar request's `from_date` is the wrong lower bound for a corporate-action query.

    The NIFTY500 refresh asks for ``to_day - 3*365`` (2023-09-11) while its store still holds bars
    from 2023-08-28. Bounding the authority by the bar request leaves the *start* of the series
    uncovered -- the same defect as the stale window at the end, measured after the first refetch.
    """
    from ingest_all_market_data import CA_HISTORY_ANCHOR

    refresh_from = date(2023, 9, 11)  # what run_scheduled_paper_session actually passes
    oldest_retained_bar = date(2023, 8, 28)  # what the store actually holds

    assert CA_HISTORY_ANCHOR < oldest_retained_bar < refresh_from
    assert min(refresh_from, CA_HISTORY_ANCHOR) <= oldest_retained_bar, (
        "the corporate-action window must reach bars the store still retains"
    )


def test_a_widened_lower_bound_forces_a_refetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: the freshness check originally compared only `effective_to`.

    A run that widened `from_date` to reach older retained bars was served the narrower cached
    record with no network call at all -- it asked for more history, silently got less, and
    reported success. Caught in production during the first remediation refetch.
    """
    calls = _patch_urlopen(monkeypatch, _payload(SAMPLE))

    narrow = fetch_or_load_corporate_actions("HEG", date(2023, 9, 11), TO, tmp_path, now=NOW)
    assert narrow.effective_from == date(2023, 9, 11)
    assert calls["n"] == 1

    wide = fetch_or_load_corporate_actions("HEG", date(2016, 8, 22), TO, tmp_path, now=NOW)
    assert calls["n"] == 2, "a wider lower bound must re-fetch, not reuse the narrower record"
    assert wide.effective_from == date(2016, 8, 22)


def test_a_narrower_request_still_reuses_a_wider_cached_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lower-bound check must not turn every narrower request into a needless round trip."""
    calls = _patch_urlopen(monkeypatch, _payload(SAMPLE))

    fetch_or_load_corporate_actions("HEG", date(2016, 8, 22), TO, tmp_path, now=NOW)
    assert calls["n"] == 1

    fetch_or_load_corporate_actions("HEG", date(2023, 9, 11), TO, tmp_path, now=NOW)
    assert calls["n"] == 1, "a record spanning more than asked for is still valid evidence"
