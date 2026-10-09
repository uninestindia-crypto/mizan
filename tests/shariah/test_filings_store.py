"""Exact JSON round trips, the bundled snapshot, and the per-user database."""

from __future__ import annotations

import gzip
import json
import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_filings_builders import FETCHED_AT, TCS_FIXTURE, make_filing, make_row

from quant_system.shariah.filings.extract import extract_figures
from quant_system.shariah.filings.models import FigureLine, FilingFigures, ReadStatus
from quant_system.shariah.filings.store import (
    FilingsStore,
    FilingsStoreError,
    IndustrySnapshot,
    write_snapshot,
)


def figures_for(
    symbol: str = "TCS", period_end: date = date(2024, 9, 30), **changes: Any
) -> FilingFigures:
    raw = make_filing(period_end=period_end, **changes)
    row = make_row(
        symbol=symbol, period_end=period_end, consolidated=changes.pop("consolidated", True)
    )
    return extract_figures(raw, row, FETCHED_AT)


def real() -> FilingFigures:
    return extract_figures(TCS_FIXTURE.read_bytes(), make_row(), FETCHED_AT)


def contains_float(value: object) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(contains_float(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_float(item) for item in value)
    return False


def test_json_round_trip_is_exact_and_holds_no_floats() -> None:
    original = real()
    document = json.loads(json.dumps(original.to_json_dict()))
    assert FilingFigures.from_json_dict(document) == original
    assert contains_float(document) is False
    assert document["lines"]["total_assets"]["value_inr"] == "1611240000000.00"
    assert document["proof"]["period_end"] == "2024-09-30"
    assert document["read_status"] == "READ_OK"
    assert document["segment_names"][0] == "Banking, Financial Services and Insurance"


@pytest.mark.parametrize(
    "text",
    ["0.1", "0.30000000000000004", "123456789012345678901234567890.123456789", "-0.00", "7"],
)
def test_decimals_survive_json_without_drifting(text: str) -> None:
    figures = real()
    line = FigureLine("Assets", "Total assets", Decimal(text), "Balance sheet at 30 Sep 2024", "-7")
    changed = replace(figures, lines={**figures.lines, "total_assets": line})
    restored = FilingFigures.from_json_dict(json.loads(json.dumps(changed.to_json_dict())))
    assert str(restored.lines["total_assets"].value_inr) == text
    assert restored == changed


def test_shares_in_issue_is_written_for_readers_but_recomputed_on_load() -> None:
    document = real().to_json_dict()
    assert document["shares_in_issue"] == "3620000000"
    document["shares_in_issue"] = "1"
    assert FilingFigures.from_json_dict(document).shares_in_issue == 3_620_000_000


@pytest.mark.parametrize("bad", [1.5, True, None, ["1"]])
def test_money_must_be_a_string_in_json(bad: object) -> None:
    document = real().to_json_dict()
    document["lines"]["total_assets"]["value_inr"] = bad
    with pytest.raises(ValueError, match="value_inr"):
        FilingFigures.from_json_dict(document)


@pytest.mark.parametrize("missing", ["symbol", "proof", "lines", "read_status", "tie_out"])
def test_a_document_missing_a_field_is_refused(missing: str) -> None:
    document = real().to_json_dict()
    del document[missing]
    with pytest.raises(ValueError, match=missing):
        FilingFigures.from_json_dict(document)


def test_a_document_without_segment_names_loads_with_none() -> None:
    document = real().to_json_dict()
    del document["segment_names"]
    assert FilingFigures.from_json_dict(document).segment_names == ()


def test_an_empty_store_has_no_data_and_creates_nothing(tmp_path: Path) -> None:
    store = FilingsStore(None, tmp_path / "never" / "user.sqlite")
    assert store.get("TCS") is None
    assert store.symbols() == []
    assert store.coverage() == {"screened": 0, "newest_filing": None, "snapshot_built_on": None}
    assert not (tmp_path / "never").exists()


def test_put_without_a_user_database_says_so_in_plain_words(tmp_path: Path) -> None:
    with pytest.raises(FilingsStoreError) as caught:
        FilingsStore(None, None).put(real())
    assert "save" in str(caught.value)


def test_user_database_round_trip_creates_folders_and_uses_wal(tmp_path: Path) -> None:
    path = tmp_path / "state" / "shariah_filings.sqlite"
    original = real()
    assert FilingsStore(None, path).put(original) is True
    reopened = FilingsStore(None, path)
    assert reopened.get("TCS") == original
    assert reopened.get("tcs") == original
    assert reopened.symbols() == ["TCS"]
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)


def test_a_newer_period_replaces_an_older_one_and_not_the_reverse(tmp_path: Path) -> None:
    store = FilingsStore(None, tmp_path / "u.sqlite")
    march, september = figures_for(period_end=date(2024, 3, 31)), figures_for()
    assert store.put(march) is True
    assert store.put(september) is True
    assert store.get("TCS") == september
    assert store.put(march) is False
    assert store.get("TCS") == september


def test_the_same_period_refetched_replaces_but_never_downgrades(tmp_path: Path) -> None:
    store = FilingsStore(None, tmp_path / "u.sqlite")
    good = figures_for()
    standalone = figures_for(consolidated=False, nature="Standalone")
    partial = figures_for(balance={"CashAndCashEquivalents": None})
    assert partial.read_status is ReadStatus.READ_PARTIAL
    assert store.put(partial) is True
    assert store.put(good) is True
    assert store.get("TCS") == good
    assert store.put(partial) is False
    assert store.put(standalone) is False
    assert store.put(good) is True


@pytest.mark.parametrize("symbol", ["X'; DROP TABLE filings;--", "", "A" * 40, "T CS", "../x"])
def test_odd_symbols_find_nothing_and_cannot_be_saved(tmp_path: Path, symbol: str) -> None:
    store = FilingsStore(None, tmp_path / "u.sqlite")
    store.put(real())
    assert store.get(symbol) is None
    with pytest.raises(FilingsStoreError):
        store.put(replace(real(), symbol=symbol))
    assert store.symbols() == ["TCS"]


@pytest.mark.parametrize("junk", [b"not a database at all", b"", b"\x00" * 4096])
def test_a_corrupt_user_database_reads_as_empty(tmp_path: Path, junk: bytes) -> None:
    path = tmp_path / "u.sqlite"
    path.write_bytes(junk)
    store = FilingsStore(None, path)
    assert store.get("TCS") is None
    assert store.symbols() == []
    assert store.coverage()["screened"] == 0


def test_saving_over_a_corrupt_user_database_keeps_the_old_file_aside(tmp_path: Path) -> None:
    path = tmp_path / "u.sqlite"
    path.write_bytes(b"not a database at all")
    store = FilingsStore(None, path)
    assert store.put(real()) is True
    assert store.get("TCS") == real()
    assert (tmp_path / "u.sqlite.corrupt").read_bytes() == b"not a database at all"


def test_an_unusable_user_database_path_reads_empty_and_fails_to_save_plainly(
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "file-not-folder"
    blocker.write_text("x", encoding="utf-8")
    store = FilingsStore(None, blocker / "u.sqlite")
    assert store.get("TCS") is None
    with pytest.raises(FilingsStoreError) as caught:
        store.put(real())
    assert "could not save" in str(caught.value)


def test_a_row_that_does_not_parse_is_skipped_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "u.sqlite"
    store = FilingsStore(None, path)
    store.put(real())
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO filings (symbol, period_end, payload) VALUES (?, ?, ?)",
            ("BAD", "2024-09-30", "{not json"),
        )
    assert store.get("BAD") is None
    assert store.get("TCS") == real()
    assert store.symbols() == ["TCS"]


def snapshot_path(tmp_path: Path, *filings: FilingFigures, built_on: str = "2026-10-01") -> Path:
    path = tmp_path / "filings_snapshot.json.gz"
    write_snapshot(path, {f.symbol: f for f in filings}, built_on)
    return path


def test_snapshot_is_a_versioned_sorted_document(tmp_path: Path) -> None:
    path = snapshot_path(tmp_path, figures_for("ZZZ"), figures_for("AAA"))
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        document = json.load(handle)
    assert document["format"] == 1
    assert document["built_on"] == "2026-10-01"
    assert document["source"] == "NSE corporate-financial-results XBRL"
    assert list(document["filings"]) == ["AAA", "ZZZ"]


def test_snapshot_bytes_are_identical_across_builds(tmp_path: Path) -> None:
    first = snapshot_path(tmp_path, real())
    second = tmp_path / "second.json.gz"
    write_snapshot(second, {"TCS": real()}, "2026-10-01")
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("field", ["sha256", "source_url"])
def test_a_snapshot_refuses_a_row_without_its_proof(tmp_path: Path, field: str) -> None:
    figures = real()
    blank: dict[str, Any] = {field: ""}
    bare = replace(figures, proof=replace(figures.proof, **blank))
    path = tmp_path / "out.json.gz"
    with pytest.raises(FilingsStoreError) as caught:
        write_snapshot(path, {"TCS": bare}, "2026-10-01")
    assert field in str(caught.value)
    assert not path.exists()


def test_snapshot_rows_are_served_and_counted(tmp_path: Path) -> None:
    partial = figures_for("PART", balance={"CashAndCashEquivalents": None})
    path = snapshot_path(
        tmp_path, real(), partial, figures_for("OLD", period_end=date(2024, 3, 31))
    )
    store = FilingsStore(path, None)
    assert store.get("TCS") == real()
    assert store.get("PART") == partial
    assert store.symbols() == ["OLD", "PART", "TCS"]
    assert store.coverage() == {
        "screened": 2,
        "newest_filing": "2024-09-30",
        "snapshot_built_on": "2026-10-01",
    }


def test_the_newer_filing_wins_between_snapshot_and_user_database(tmp_path: Path) -> None:
    snapshot = snapshot_path(
        tmp_path, figures_for("ABC", period_end=date(2024, 3, 31)), figures_for("XYZ")
    )
    store = FilingsStore(snapshot, tmp_path / "u.sqlite")
    fresh = figures_for("ABC")
    stale = figures_for("XYZ", period_end=date(2024, 3, 31))
    assert store.put(fresh) is True
    assert store.put(stale) is False
    assert store.get("ABC") == fresh
    assert store.get("XYZ") == figures_for("XYZ")
    assert store.symbols() == ["ABC", "XYZ"]
    assert store.coverage()["newest_filing"] == "2024-09-30"


@pytest.mark.parametrize(
    "writer",
    [
        lambda p: p.write_bytes(b"not gzip"),
        lambda p: p.write_bytes(gzip.compress(b"{broken")),
        lambda p: p.write_bytes(gzip.compress(b'{"format": 2, "built_on": "x", "filings": {}}')),
        lambda p: p.write_bytes(gzip.compress(b'{"format": 1, "filings": []}')),
        lambda p: p.write_bytes(gzip.compress(b"[1, 2]")),
        lambda p: p.write_bytes(b""),
    ],
    ids=["not-gzip", "bad-json", "future-format", "filings-not-a-map", "not-a-map", "empty"],
)
def test_a_damaged_snapshot_reads_as_empty(tmp_path: Path, writer: Any) -> None:
    path = tmp_path / "snap.json.gz"
    writer(path)
    store = FilingsStore(path, None)
    assert store.get("TCS") is None
    assert store.symbols() == []
    assert store.coverage()["snapshot_built_on"] is None


def test_one_bad_snapshot_row_does_not_hide_the_others(tmp_path: Path) -> None:
    document = {
        "format": 1,
        "built_on": "2026-10-01",
        "source": "x",
        "filings": {"TCS": real().to_json_dict(), "BAD": {"symbol": "BAD"}},
    }
    path = tmp_path / "snap.json.gz"
    path.write_bytes(gzip.compress(json.dumps(document).encode("utf-8")))
    store = FilingsStore(path, None)
    assert store.get("TCS") == real()
    assert store.get("BAD") is None
    assert store.symbols() == ["TCS"]


def test_a_missing_snapshot_path_is_empty(tmp_path: Path) -> None:
    assert FilingsStore(tmp_path / "nope.json.gz", None).symbols() == []


GROUPS = IndustrySnapshot({"TCS": "Information Technology", "ABB": "Capital Goods"}, "2026-10-07")


def snapshot_with_industry(tmp_path: Path) -> Path:
    path = tmp_path / "with_industry.json.gz"
    write_snapshot(path, {"TCS": real()}, "2026-10-01", GROUPS)
    return path


def test_snapshot_carries_industry_groups_and_the_date_they_were_read(tmp_path: Path) -> None:
    with gzip.open(snapshot_with_industry(tmp_path), "rt", encoding="utf-8") as handle:
        document = json.load(handle)
    assert document["industry_groups"] == {"ABB": "Capital Goods", "TCS": "Information Technology"}
    assert list(document["industry_groups"]) == ["ABB", "TCS"]
    assert document["industry_source"] == "NSE Nifty Total Market list"
    assert document["industry_read_on"] == "2026-10-07"


def test_a_snapshot_without_industry_groups_still_loads(tmp_path: Path) -> None:
    store = FilingsStore(snapshot_path(tmp_path, real()), None)
    assert store.industry_group("TCS") is None
    assert store.get("TCS") == real()


def test_industry_group_is_served_from_the_snapshot_for_any_symbol(tmp_path: Path) -> None:
    store = FilingsStore(snapshot_with_industry(tmp_path), None)
    assert store.industry_group("TCS") == "Information Technology"
    assert store.industry_group("abb") == "Capital Goods"
    assert store.industry_group("NOPE") is None
    assert store.industry_group("X'; DROP TABLE filings;--") is None
    assert store.symbols() == ["TCS"]


def test_the_per_user_industry_table_is_saved_and_the_later_reading_wins(tmp_path: Path) -> None:
    store = FilingsStore(snapshot_with_industry(tmp_path), tmp_path / "u.sqlite")
    assert (
        store.put_industry_groups(
            {"ITC": "Fast Moving Consumer Goods", "TCS": "IT Services"}, "2026-10-08"
        )
        == 2
    )
    assert store.industry_group("ITC") == "Fast Moving Consumer Goods"
    assert store.industry_group("TCS") == "IT Services"
    assert store.put_industry_groups({"ABB": "Old"}, "2026-01-01") == 1
    assert store.industry_group("ABB") == "Capital Goods"
    assert (
        FilingsStore(None, tmp_path / "u.sqlite").industry_group("ITC")
        == "Fast Moving Consumer Goods"
    )


def test_odd_industry_rows_are_skipped_and_saving_needs_a_user_database(tmp_path: Path) -> None:
    store = FilingsStore(None, tmp_path / "u.sqlite")
    assert store.put_industry_groups({"BA D": "x", "ITC": "", "OK": "Power"}, "2026-10-08") == 1
    assert store.industry_group("OK") == "Power"
    with pytest.raises(FilingsStoreError):
        FilingsStore(None, None).put_industry_groups({"OK": "Power"}, "2026-10-08")


def test_a_corrupt_user_database_has_no_industry_groups(tmp_path: Path) -> None:
    path = tmp_path / "u.sqlite"
    path.write_bytes(b"not a database at all")
    assert FilingsStore(None, path).industry_group("TCS") is None
