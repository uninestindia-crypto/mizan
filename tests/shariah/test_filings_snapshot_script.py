"""The developer snapshot builder, driven by a fake source (no network, no real state)."""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest
from test_filings_builders import FETCHED_AT, TCS_FIXTURE, make_filing, make_row

from quant_system.shariah.filings.extract import extract_figures
from quant_system.shariah.filings.models import IndustryGroup, ReadStatus
from quant_system.shariah.filings.nse_client import FilingsBlocked, FilingsUnavailable
from quant_system.shariah.filings.selection import Selection
from scripts.build_shariah_filings_snapshot import (
    load_sample_symbols,
    load_universe_symbols,
    main,
)

REPO = Path(__file__).resolve().parents[2]
UNIVERSE = REPO / "data" / "authorities" / "nse-research-universe-liquid-10y.csv"
GROUPS = {"AAA": IndustryGroup("Aaa Ltd.", "Capital Goods", "INE000A01011")}


def selection_for(symbol: str, raw: bytes | None = None, **row: object) -> Selection:
    figures = extract_figures(raw or make_filing(), make_row(symbol=symbol, **row), FETCHED_AT)
    return Selection(figures, figures.read_status, figures.read_note, 1)


class FakeSource:
    def __init__(self, outcomes: Mapping[str, Selection | Exception] | None = None) -> None:
        self.outcomes = outcomes or {}
        self.asked: list[str] = []
        self.industry_calls = 0
        self.industry_error: Exception | None = None

    def read_company(self, symbol: str) -> Selection:
        self.asked.append(symbol)
        outcome = self.outcomes.get(symbol) or selection_for(symbol)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def fetch_industry_groups(self) -> dict[str, IndustryGroup]:
        self.industry_calls += 1
        if self.industry_error is not None:
            raise self.industry_error
        return dict(GROUPS)


def write_universe(path: Path, symbols: list[str]) -> Path:
    lines = [
        "# comment line",
        "Symbol,ISIN Code,InstrumentKey",
        *[f"{s},INE0,NSE_EQ|INE0" for s in symbols],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(tmp_path: Path, source: FakeSource, *extra: str, symbols: list[str] | None = None) -> int:
    universe = write_universe(tmp_path / "universe.csv", symbols or ["CCC", "AAA", "BBB"])
    args = [
        "--symbols-csv", str(universe),
        "--out", str(tmp_path / "out.json.gz"),
        "--resume-dir", str(tmp_path / "resume"),
        "--pause", "0",
        "--built-on", "2026-10-07",
        *extra,
    ]  # fmt: skip
    return main(args, lambda pause: source)


def document(tmp_path: Path) -> dict[str, object]:
    with gzip.open(tmp_path / "out.json.gz", "rt", encoding="utf-8") as handle:
        loaded: dict[str, object] = json.load(handle)
    return loaded


def test_universe_symbols_skip_comments_header_and_bad_rows(tmp_path: Path) -> None:
    path = write_universe(tmp_path / "u.csv", ["BBB", "AAA", "BBB", "BAD SYM", ""])
    assert load_universe_symbols(path) == ["AAA", "BBB"]


def test_the_real_research_universe_file_is_readable() -> None:
    symbols = load_universe_symbols(UNIVERSE)
    assert len(symbols) > 400
    assert "3MINDIA" in symbols
    assert "Symbol" not in symbols


def test_sample_symbols_come_from_a_read_only_copy_of_the_sample_database(tmp_path: Path) -> None:
    db = tmp_path / "sample.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE companies (ticker TEXT)")
        connection.executemany(
            "INSERT INTO companies VALUES (?)",
            [("ABB.NS",), ("TCS.NS",), ("X.BO",), ("ITC",), ("A B.NS",)],
        )
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    assert load_sample_symbols(db) == ["ABB", "ITC", "TCS", "X"]
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert load_sample_symbols(tmp_path / "missing.db") == []


def test_a_build_writes_a_sorted_snapshot_and_a_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = FakeSource()
    assert run(tmp_path, source) == 0
    doc = document(tmp_path)
    assert list(doc["filings"]) == ["AAA", "BBB", "CCC"]  # type: ignore[call-overload]
    assert doc["built_on"] == "2026-10-07"
    assert doc["industry_groups"] == {"AAA": "Capital Goods"}
    assert doc["industry_read_on"] == "2026-10-07"
    printed = capsys.readouterr().out
    assert "READ_OK" in printed
    assert "failed" in printed
    assert source.asked == ["AAA", "BBB", "CCC"]
    assert source.industry_calls == 1


def test_limit_takes_the_first_symbols_in_sorted_order(tmp_path: Path) -> None:
    source = FakeSource()
    assert run(tmp_path, source, "--limit", "2") == 0
    assert list(document(tmp_path)["filings"]) == ["AAA", "BBB"]  # type: ignore[call-overload]


def test_a_rerun_uses_the_cache_and_produces_the_same_bytes(tmp_path: Path) -> None:
    assert run(tmp_path, FakeSource()) == 0
    first = (tmp_path / "out.json.gz").read_bytes()
    second_source = FakeSource({s: FilingsUnavailable() for s in ("AAA", "BBB", "CCC")})
    assert run(tmp_path, second_source) == 0
    assert second_source.asked == []
    assert second_source.industry_calls == 0
    assert (tmp_path / "out.json.gz").read_bytes() == first


def test_sample_database_symbols_are_added_when_asked(tmp_path: Path) -> None:
    db = tmp_path / "sample.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE companies (ticker TEXT)")
        connection.execute("INSERT INTO companies VALUES ('ZZZ.NS')")
    source = FakeSource()
    assert run(tmp_path, source, "--extra-symbols-from-sample-db", "--sample-db", str(db)) == 0
    assert source.asked == ["AAA", "BBB", "CCC", "ZZZ"]


def test_a_symbol_nse_could_not_answer_is_counted_failed_and_retried_next_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flaky = FakeSource({"BBB": FilingsUnavailable()})
    assert run(tmp_path, flaky) == 0
    assert list(document(tmp_path)["filings"]) == ["AAA", "CCC"]  # type: ignore[call-overload]
    assert "failed" in capsys.readouterr().out
    healthy = FakeSource()
    assert run(tmp_path, healthy) == 0
    assert healthy.asked == ["BBB"]
    assert list(document(tmp_path)["filings"]) == ["AAA", "BBB", "CCC"]  # type: ignore[call-overload]


def test_a_company_with_no_filing_is_counted_but_not_stored_and_not_asked_again(
    tmp_path: Path,
) -> None:
    none = Selection(None, ReadStatus.NO_BALANCE_SHEET, "NSE lists no results filing.", 0)
    assert run(tmp_path, FakeSource({"BBB": none})) == 0
    assert list(document(tmp_path)["filings"]) == ["AAA", "CCC"]  # type: ignore[call-overload]
    again = FakeSource()
    assert run(tmp_path, again) == 0
    assert again.asked == []


def test_a_row_without_its_proof_stops_the_build_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = selection_for("BBB")
    assert good.figures is not None
    bare = replace(
        good, figures=replace(good.figures, proof=replace(good.figures.proof, sha256=""))
    )
    assert run(tmp_path, FakeSource({"BBB": bare})) == 1
    assert not (tmp_path / "out.json.gz").exists()
    assert "sha256" in capsys.readouterr().out


def test_three_blocks_in_a_row_stop_the_build_politely(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocked = {s: FilingsBlocked() for s in ("AAA", "BBB", "CCC", "DDD", "EEE")}
    source = FakeSource(blocked)
    assert run(tmp_path, source, symbols=["AAA", "BBB", "CCC", "DDD", "EEE"]) == 2
    assert source.asked == ["AAA", "BBB", "CCC"]
    assert not (tmp_path / "out.json.gz").exists()
    assert "not letting" in capsys.readouterr().out


def test_an_industry_list_that_cannot_be_read_stops_the_build_before_any_filing(
    tmp_path: Path,
) -> None:
    source = FakeSource()
    source.industry_error = FilingsUnavailable()
    assert run(tmp_path, source) == 2
    assert source.asked == []
    assert not (tmp_path / "out.json.gz").exists()


def test_the_builder_can_read_a_real_filing_end_to_end(tmp_path: Path) -> None:
    real = selection_for("AAA", TCS_FIXTURE.read_bytes())
    assert run(tmp_path, FakeSource({"AAA": real}), symbols=["AAA"]) == 0
    row = document(tmp_path)["filings"]["AAA"]  # type: ignore[index]
    assert row["lines"]["total_assets"]["value_inr"] == "1611240000000.00"


def test_figures_for_a_different_symbol_than_asked_stop_the_build(tmp_path: Path) -> None:
    assert run(tmp_path, FakeSource({"AAA": selection_for("OTHER")}), symbols=["AAA"]) == 1
    assert not (tmp_path / "out.json.gz").exists()
