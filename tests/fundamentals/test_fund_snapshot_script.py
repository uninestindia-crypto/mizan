"""The developer snapshot builder, driven by a fake source: no network, no real state, nothing under data/."""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from quant_system.fundamentals.extract import extract_quarter
from quant_system.fundamentals.reader import CompanyRead
from quant_system.fundamentals.store import FundamentalsStore
from quant_system.shariah.filings.models import IndustryGroup
from quant_system.shariah.filings.nse_client import FilingsBlocked, FilingsUnavailable
from scripts.build_fundamentals_snapshot import (
    DEFAULT_OUT,
    LiveSource,
    load_universe_symbols,
    main,
)
from tests.fundamentals.support import fixture_bytes, listing_row

REPO = Path(__file__).resolve().parents[2]
UNIVERSE = REPO / "data" / "authorities" / "nse-research-universe-liquid-10y.csv"
STAMP = "2026-10-07T00:00:00Z"
GROUPS = {"AAA": IndustryGroup("Aaa Ltd.", "Capital Goods", "INE000A01011")}


def _read_for(symbol: str) -> CompanyRead:
    sep = extract_quarter(
        fixture_bytes("tcs_2024-09-30_consolidated_trimmed.xml"),
        listing_row(symbol, date(2024, 9, 30)),
        STAMP,
    )
    dec = extract_quarter(
        fixture_bytes("tcs_2024-12-31_consolidated_trimmed.xml"),
        listing_row(symbol, date(2024, 12, 31), filed_on=date(2025, 1, 9)),
        STAMP,
    )
    return CompanyRead([replace(q, symbol=symbol) for q in (sep, dec)], 0, 2)


class FakeSource:
    def __init__(self, outcomes: Mapping[str, CompanyRead | Exception] | None = None) -> None:
        self.outcomes = outcomes or {}
        self.asked: list[tuple[str, int]] = []
        self.industry_calls = 0
        self.industry_error: Exception | None = None

    def read_company(self, symbol: str, quarters: int) -> CompanyRead:
        self.asked.append((symbol, quarters))
        outcome = self.outcomes.get(symbol) or _read_for(symbol)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def fetch_industry_groups(self) -> dict[str, IndustryGroup]:
        self.industry_calls += 1
        if self.industry_error is not None:
            raise self.industry_error
        return dict(GROUPS)


def _universe(path: Path, symbols: list[str]) -> Path:
    lines = [
        "# comment line",
        "Symbol,ISIN Code,InstrumentKey",
        *[f"{s},INE0,NSE_EQ|INE0" for s in symbols],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run(tmp_path: Path, source: FakeSource, *extra: str, symbols: list[str] | None = None) -> int:
    universe = _universe(tmp_path / "universe.csv", symbols or ["CCC", "AAA", "BBB"])
    args = [
        "--symbols-csv", str(universe),
        "--out", str(tmp_path / "out.json.gz"),
        "--resume-dir", str(tmp_path / "resume"),
        "--pause", "0",
        "--built-on", "2026-10-07",
        *extra,
    ]  # fmt: skip
    return main(args, lambda pause: source)


def _document(tmp_path: Path) -> dict[str, object]:
    with gzip.open(tmp_path / "out.json.gz", "rb") as handle:
        return dict(json.loads(handle.read()))


def test_the_default_output_is_the_bundled_snapshot_path() -> None:
    assert DEFAULT_OUT == REPO / "data" / "fundamentals" / "fundamentals_snapshot.json.gz"


def test_the_universe_file_is_read_without_its_comment_lines() -> None:
    symbols = load_universe_symbols(UNIVERSE)
    assert len(symbols) > 400 and "TCS" in symbols and symbols == sorted(symbols)


def test_a_run_writes_every_company_with_its_filings_and_its_industry(tmp_path: Path) -> None:
    source = FakeSource()
    assert _run(tmp_path, source) == 0
    document = _document(tmp_path)
    assert sorted(document["companies"]) == ["AAA", "BBB", "CCC"]  # type: ignore[call-overload]
    assert (
        document["industry_groups"] == {"AAA": "Capital Goods"}
        and document["built_on"] == "2026-10-07"
    )
    assert source.asked == [("AAA", 8), ("BBB", 8), ("CCC", 8)] and source.industry_calls == 1


def test_what_is_written_can_be_read_back_by_the_store(tmp_path: Path) -> None:
    _run(tmp_path, FakeSource())
    store = FundamentalsStore(tmp_path / "out.json.gz", None)
    assert [q.period_end for q in store.quarters("AAA")] == [date(2024, 9, 30), date(2024, 12, 31)]
    assert store.industry("AAA") == "Capital Goods" and store.symbols() == ["AAA", "BBB", "CCC"]


def test_the_same_run_gives_the_same_bytes(tmp_path: Path) -> None:
    _run(tmp_path, FakeSource())
    first = (tmp_path / "out.json.gz").read_bytes()
    (tmp_path / "resume").rename(tmp_path / "resume-1")
    _run(tmp_path, FakeSource())
    assert (tmp_path / "out.json.gz").read_bytes() == first


def test_limit_and_only_choose_the_symbols_and_quarters_sets_how_many_filings(
    tmp_path: Path,
) -> None:
    source = FakeSource()
    _run(tmp_path, source, "--limit", "2", "--quarters", "4")
    assert source.asked == [("AAA", 4), ("BBB", 4)]
    only = FakeSource()
    (tmp_path / "again").mkdir()
    _run(tmp_path / "again", only, "--only", "tcs, infy")
    assert only.asked == [("INFY", 8), ("TCS", 8)]


def test_a_stopped_run_resumes_without_asking_nse_again_for_what_it_already_read(
    tmp_path: Path,
) -> None:
    first = FakeSource({"BBB": FilingsBlocked()})
    assert (
        _run(tmp_path, first, symbols=["AAA", "BBB"]) == 0
    )  # one refusal is reported, the rest carries on
    second = FakeSource()
    assert _run(tmp_path, second, symbols=["AAA", "BBB"]) == 0
    assert second.asked == [("BBB", 8)] and second.industry_calls == 0


def test_three_refusals_in_a_row_stop_the_run_and_write_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    refused = {s: FilingsBlocked() for s in ("AAA", "BBB", "CCC")}
    assert _run(tmp_path, FakeSource(refused)) == 2
    assert (
        not (tmp_path / "out.json.gz").exists()
        and "Stopped after 3 refusals" in capsys.readouterr().out
    )


def test_one_company_that_fails_is_counted_and_the_rest_are_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, FakeSource({"BBB": FilingsUnavailable()})) == 0
    assert sorted(_document(tmp_path)["companies"]) == ["AAA", "CCC"]  # type: ignore[call-overload]
    assert "failed" in capsys.readouterr().out


def test_a_company_with_no_filings_is_counted_and_left_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(tmp_path, FakeSource({"BBB": CompanyRead([], 0, 0)})) == 0
    assert sorted(_document(tmp_path)["companies"]) == ["AAA", "CCC"]  # type: ignore[call-overload]
    assert "no filings" in capsys.readouterr().out


def test_a_row_without_its_proof_is_refused_and_nothing_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bare = CompanyRead([replace(q, sha256="") for q in _read_for("AAA").quarters], 0, 2)
    code = _run(tmp_path, FakeSource({"AAA": bare}))
    assert (
        code == 1
        and "Not written" in capsys.readouterr().out
        and not (tmp_path / "out.json.gz").exists()
    )


def test_a_refusal_to_give_the_industry_list_stops_the_run_in_plain_words(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = FakeSource()
    source.industry_error = FilingsUnavailable()
    assert _run(tmp_path, source) == 2 and "Stopped" in capsys.readouterr().out


def test_the_live_source_is_polite_whatever_pause_it_is_given() -> None:
    assert LiveSource(0.0)._client.pause_seconds == 1.2
    assert LiveSource(3.0)._client.pause_seconds == 3.0
