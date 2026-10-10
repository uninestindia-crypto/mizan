"""Choosing which filing to read, and walking back at most three times."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from test_filings_builders import FETCHED_AT, TCS_FIXTURE, make_filing, make_row
from test_filings_client import FakeClock, FakeTransport, listing_row, ok

from quant_system.shariah.filings.extract import extract_figures
from quant_system.shariah.filings.models import FilingFigures, ReadStatus, ResultRow
from quant_system.shariah.filings.nse_client import (
    FilingsBlocked,
    FilingsNotFound,
    NseFilingsClient,
)
from quant_system.shariah.filings.selection import MAX_CANDIDATES, rank_candidates, select_filing
from quant_system.shariah.filings.service import read_company_filing

SEP25, MAR25, SEP24, MAR24 = (
    date(2025, 9, 30),
    date(2025, 3, 31),
    date(2024, 9, 30),
    date(2024, 3, 31),
)


def row(period_end: date, relating_to: str = "Second Quarter", **changes: object) -> ResultRow:
    base = "https://nsearchives.nseindia.com/corporate/xbrl/"
    url = f"{base}INDAS_{period_end}_{changes.get('consolidated', True)}.xml"
    changes.setdefault("xbrl_url", url)
    return make_row(period_end=period_end, relating_to=relating_to, **changes)


class Fetcher:
    """Returns real extraction results for canned files and remembers what was asked for."""

    def __init__(self, files: dict[str, bytes], fail: dict[str, Exception] | None = None) -> None:
        self.files = files
        self.fail = fail or {}
        self.calls: list[ResultRow] = []

    def __call__(self, candidate: ResultRow) -> FilingFigures:
        self.calls.append(candidate)
        if candidate.xbrl_url in self.fail:
            raise self.fail[candidate.xbrl_url]
        raw = self.files.get(candidate.xbrl_url, make_filing(period_end=candidate.period_end))
        return extract_figures(raw, candidate, FETCHED_AT)


def no_balance_sheet(rows: list[ResultRow]) -> dict[str, bytes]:
    return {
        r.xbrl_url: make_filing(period_end=r.period_end, with_balance_sheet=False) for r in rows
    }


def test_ranking_is_newest_first_consolidated_first_and_ind_as_only() -> None:
    rows = [
        row(SEP24, consolidated=False),
        row(SEP24),
        row(date(2024, 12, 31), "Third Quarter"),
        row(MAR24, "Fourth Quarter"),
        row(date(2023, 9, 30), ind_as=False),
        row(SEP25, lender_flag="B", ind_as=False),
        row(SEP25, lender_flag="F", ind_as=False),
    ]
    order = [(r.period_end, r.consolidated) for r in rank_candidates(rows)]
    assert order == [
        (SEP24, True),
        (SEP24, False),
        (MAR24, True),
        (date(2024, 12, 31), True),
    ]


def test_periods_that_normally_carry_a_balance_sheet_come_before_newer_ones_that_do_not() -> None:
    rows = [
        row(date(2024, 12, 31), "Third Quarter"),
        row(SEP24),
        row(date(2024, 6, 30), "First Quarter"),
    ]
    assert [r.period_end for r in rank_candidates(rows)] == [
        SEP24,
        date(2024, 12, 31),
        date(2024, 6, 30),
    ]


def test_a_later_refiling_of_the_same_period_is_tried_first() -> None:
    older = row(
        SEP24,
        filed_on=date(2024, 10, 10),
        xbrl_url="https://nsearchives.nseindia.com/corporate/xbrl/a.xml",
    )
    newer = row(
        SEP24,
        filed_on=date(2024, 11, 1),
        xbrl_url="https://nsearchives.nseindia.com/corporate/xbrl/b.xml",
    )
    assert [r.xbrl_url[-5:] for r in rank_candidates([older, newer])] == ["b.xml", "a.xml"]


def test_the_newest_balance_sheet_is_read_and_nothing_else_is_fetched() -> None:
    rows = [row(SEP24), row(SEP24, consolidated=False), row(MAR24, "Fourth Quarter")]
    fetch = Fetcher({})
    result = select_filing(rows, fetch)
    assert result.read_status is ReadStatus.READ_OK
    assert result.figures is not None and result.figures.proof.period_end == SEP24
    assert [(c.period_end, c.consolidated) for c in fetch.calls] == [(SEP24, True)]
    assert result.tried == 1


def test_it_walks_back_at_most_three_filings_then_gives_up() -> None:
    rows = [row(SEP25), row(MAR25, "Fourth Quarter"), row(SEP24), row(MAR24, "Fourth Quarter")]
    fetch = Fetcher(no_balance_sheet(rows))
    result = select_filing(rows, fetch)
    assert MAX_CANDIDATES == 3
    assert [c.period_end for c in fetch.calls] == [SEP25, MAR25, SEP24]
    assert result.read_status is ReadStatus.NO_BALANCE_SHEET
    assert result.tried == 3
    assert "balance sheet" in result.note


def test_a_period_without_a_balance_sheet_is_skipped_for_both_versions() -> None:
    rows = [row(SEP25), row(SEP25, consolidated=False), row(MAR25, "Fourth Quarter")]
    fetch = Fetcher(no_balance_sheet(rows[:2]))
    result = select_filing(rows, fetch)
    assert [(c.period_end, c.consolidated) for c in fetch.calls] == [(SEP25, True), (MAR25, True)]
    assert result.read_status is ReadStatus.READ_OK
    assert result.figures is not None and result.figures.proof.period_end == MAR25
    assert result.tried == 2


def test_an_unreadable_consolidated_filing_does_not_fall_back_to_standalone() -> None:
    consolidated, standalone = row(SEP24), row(SEP24, consolidated=False)
    broken = make_filing(
        balance={"TradeReceivablesCurrent": None, "TradeReceivablesNoncurrent": None}
    )
    fetch = Fetcher({consolidated.xbrl_url: broken})
    result = select_filing([standalone, consolidated], fetch)
    assert result.read_status is ReadStatus.READ_PARTIAL
    assert result.figures is not None and result.figures.proof.consolidated is True
    assert len(fetch.calls) == 1


def test_a_filing_nse_no_longer_has_counts_as_a_candidate_and_the_walk_continues() -> None:
    rows = [row(SEP25), row(MAR25, "Fourth Quarter")]
    fetch = Fetcher({}, fail={rows[0].xbrl_url: FilingsNotFound()})
    result = select_filing(rows, fetch)
    assert result.read_status is ReadStatus.READ_OK
    assert result.figures is not None and result.figures.proof.period_end == MAR25
    assert result.tried == 2


def test_a_block_is_not_swallowed() -> None:
    fetch = Fetcher({}, fail={row(SEP25).xbrl_url: FilingsBlocked()})
    with pytest.raises(FilingsBlocked):
        select_filing([row(SEP25), row(MAR25)], fetch)


def test_a_bank_gets_one_look_so_the_proof_can_say_what_was_seen() -> None:
    rows = [row(SEP24, lender_flag="B", ind_as=False), row(MAR24, lender_flag="B", ind_as=False)]
    fetch = Fetcher({})
    result = select_filing(rows, fetch)
    assert result.read_status is ReadStatus.FORMAT_NOT_READ
    assert [c.period_end for c in fetch.calls] == [SEP24]
    assert result.figures is not None and result.figures.proof.sha256 != ""
    assert "bank" in result.note.lower()


def test_a_company_is_judged_by_its_newest_filing_not_an_old_one() -> None:
    rows = [row(SEP25, lender_flag="F", ind_as=False), row(MAR24, "Fourth Quarter")]
    fetch = Fetcher({})
    result = select_filing(rows, fetch)
    assert result.read_status is ReadStatus.FORMAT_NOT_READ
    assert [c.period_end for c in fetch.calls] == [SEP25]
    assert "lender" in result.note.lower()


def test_no_filings_at_all_gives_up_without_fetching() -> None:
    fetch = Fetcher({})
    result = select_filing([], fetch)
    assert (result.read_status, result.figures, result.tried) == (
        ReadStatus.NO_BALANCE_SHEET,
        None,
        0,
    )
    assert fetch.calls == []
    assert "NSE" in result.note


def make_client(handler: Callable[[str], object]) -> NseFilingsClient:
    clock = FakeClock()
    return NseFilingsClient(FakeTransport(handler), clock.sleep, clock.monotonic, 1.2)  # type: ignore[arg-type]


def test_read_company_filing_lists_fetches_and_extracts_with_an_injected_clock() -> None:
    def handler(url: str) -> object:
        if "api/corporates-financial-results" in url:
            return ok(json.dumps([listing_row()]).encode())
        return ok(TCS_FIXTURE.read_bytes())

    now = datetime(2026, 10, 7, 10, 0, tzinfo=UTC)
    result = read_company_filing(make_client(handler), "TCS", lambda: now)
    assert result.read_status is ReadStatus.READ_OK
    assert result.figures is not None
    assert result.figures.proof.fetched_at == "2026-10-07T10:00:00Z"
    assert result.figures.shares_in_issue == 3_620_000_000
