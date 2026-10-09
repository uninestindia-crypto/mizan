"""Where the figures live: a bundled read-only snapshot and a per-user database written from the app."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from quant_system.fundamentals.models import QuarterFigures, ReadStatus
from quant_system.fundamentals.snapshot import (
    FundamentalsStoreError,
    IndustrySnapshot,
    read_snapshot,
    write_snapshot,
)
from quant_system.fundamentals.store import FundamentalsStore
from tests.fundamentals.support import quarter

SEP, DEC = date(2024, 9, 30), date(2024, 12, 31)


def _q(
    end: date = SEP, symbol: str = "ABC", profit: int = 100, filed_in: int = 20
) -> QuarterFigures:
    made = quarter(end, revenue=1000, profit=profit)
    return replace(made, symbol=symbol, filed_on=end + timedelta(days=filed_in))


def _store(
    tmp_path: Path, snapshot: dict[str, list[QuarterFigures]] | None = None
) -> FundamentalsStore:
    path = tmp_path / "snapshot.json.gz"
    if snapshot is not None:
        write_snapshot(
            path,
            snapshot,
            "2026-10-01",
            IndustrySnapshot({"ABC": "Information Technology"}, "2026-10-01"),
        )
    return FundamentalsStore(path, tmp_path / "state" / "fundamentals.sqlite")


def test_with_neither_file_the_store_is_simply_empty(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.quarters("ABC") == [] and store.symbols() == [] and store.industry("ABC") is None
    assert store.coverage() == {"companies": 0, "newest_filing": None, "snapshot_built_on": None}


def test_a_store_with_no_paths_at_all_also_works() -> None:
    store = FundamentalsStore(None, None)
    assert store.quarters("ABC") == [] and store.symbols() == []


def test_the_bundled_snapshot_is_read_and_never_written(tmp_path: Path) -> None:
    store = _store(tmp_path, {"ABC": [_q(SEP), _q(DEC)]})
    before = (tmp_path / "snapshot.json.gz").read_bytes()
    assert [q.period_end for q in store.quarters("ABC")] == [SEP, DEC]
    assert store.put([_q(date(2024, 6, 30))]) == 1
    assert (tmp_path / "snapshot.json.gz").read_bytes() == before


def test_a_snapshot_is_the_same_bytes_for_the_same_input(tmp_path: Path) -> None:
    rows = {"ABC": [_q(SEP)]}
    write_snapshot(tmp_path / "a.gz", rows, "2026-10-01", None)
    write_snapshot(tmp_path / "b.gz", rows, "2026-10-01", None)
    assert (tmp_path / "a.gz").read_bytes() == (tmp_path / "b.gz").read_bytes()


def test_a_snapshot_refuses_a_row_without_its_proof(tmp_path: Path) -> None:
    with pytest.raises(FundamentalsStoreError, match="sha256"):
        write_snapshot(tmp_path / "x.gz", {"ABC": [replace(_q(), sha256="")]}, "2026-10-01", None)
    with pytest.raises(FundamentalsStoreError, match="source link"):
        write_snapshot(
            tmp_path / "x.gz", {"ABC": [replace(_q(), source_url="")]}, "2026-10-01", None
        )
    with pytest.raises(FundamentalsStoreError, match="belong to"):
        write_snapshot(tmp_path / "x.gz", {"ABC": [_q(symbol="XYZ")]}, "2026-10-01", None)


def test_a_damaged_or_missing_snapshot_reads_as_nothing(tmp_path: Path) -> None:
    broken = tmp_path / "broken.gz"
    broken.write_bytes(b"this is not a gzip file")
    assert read_snapshot(broken) is None and read_snapshot(tmp_path / "missing.gz") is None


def test_a_filing_saved_from_the_app_is_kept_in_the_user_database(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.put([_q(SEP), _q(DEC)]) == 2
    reopened = FundamentalsStore(None, tmp_path / "state" / "fundamentals.sqlite")
    assert [q.period_end for q in reopened.quarters("ABC")] == [SEP, DEC]


def test_a_newer_filing_replaces_an_older_one_for_the_same_quarter(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put([_q(SEP, profit=100, filed_in=20)])
    assert store.put([_q(SEP, profit=250, filed_in=40)]) == 1
    kept = store.quarters("ABC")[0]
    assert kept.value("profit_for_period") == 250 and kept.filed_on == SEP + timedelta(days=40)


def test_an_older_filing_never_replaces_a_newer_one(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put([_q(SEP, filed_in=40)])
    assert store.put([_q(SEP, filed_in=20)]) == 0
    assert store.quarters("ABC")[0].filed_on == SEP + timedelta(days=40)


def test_a_failed_read_never_replaces_a_clean_read_of_the_same_filing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put([_q(SEP)])
    failed = replace(_q(SEP), status=ReadStatus.TIE_OUT_FAILED, note="x")
    assert store.put([failed]) == 0 and store.quarters("ABC")[0].usable


def test_a_clean_read_replaces_a_failed_read_of_the_same_filing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put([replace(_q(SEP), status=ReadStatus.TIE_OUT_FAILED, note="x")])
    assert store.put([_q(SEP)]) == 1 and store.quarters("ABC")[0].usable


def test_the_two_bases_are_kept_apart(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put([_q(SEP), replace(_q(SEP), consolidated=False)])
    assert sorted(q.consolidated for q in store.quarters("ABC")) == [False, True]


def test_a_filing_saved_from_the_app_beats_an_older_snapshot_row_only_if_it_is_newer(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path, {"ABC": [_q(SEP, filed_in=30)]})
    assert store.put([_q(SEP, filed_in=10)]) == 0
    assert store.put([_q(SEP, filed_in=50)]) == 1
    assert store.quarters("ABC")[0].filed_on == SEP + timedelta(days=50)


def test_symbols_and_coverage_count_both_places(tmp_path: Path) -> None:
    store = _store(tmp_path, {"ABC": [_q(SEP)]})
    store.put([_q(DEC, symbol="XYZ")])
    assert store.symbols() == ["ABC", "XYZ"]
    assert store.coverage() == {
        "companies": 2,
        "newest_filing": DEC.isoformat(),
        "snapshot_built_on": "2026-10-01",
    }


def test_the_industry_group_comes_from_the_snapshot_and_a_newer_saved_one_wins(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path, {"ABC": [_q(SEP)]})
    assert store.industry("ABC") == "Information Technology"
    store.put_industry({"ABC": "Software"}, "2026-10-05")
    assert store.industry("ABC") == "Software"
    store.put_industry({"ABC": "Old"}, "2026-09-01")
    assert store.industry("ABC") == "Software"


def test_a_symbol_that_is_not_one_is_refused_when_saving(tmp_path: Path) -> None:
    with pytest.raises(FundamentalsStoreError, match="not a valid"):
        _store(tmp_path).put([_q(symbol="bad symbol!")])


def test_a_damaged_user_database_is_kept_aside_and_a_fresh_one_started(tmp_path: Path) -> None:
    folder = tmp_path / "state"
    folder.mkdir()
    (folder / "fundamentals.sqlite").write_bytes(b"not a database at all, just text" * 10)
    store = FundamentalsStore(None, folder / "fundamentals.sqlite")
    assert store.quarters("ABC") == []
    assert store.put([_q(SEP)]) == 1
    assert (folder / "fundamentals.sqlite.corrupt").exists() and len(store.quarters("ABC")) == 1


def test_reading_never_creates_the_user_database(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.quarters("ABC")
    store.symbols()
    assert not (tmp_path / "state").exists()


def test_a_store_with_nowhere_to_save_says_so_in_plain_words() -> None:
    with pytest.raises(FundamentalsStoreError, match="no place to save"):
        FundamentalsStore(None, None).put([_q(SEP)])
