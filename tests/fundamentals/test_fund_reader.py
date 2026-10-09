"""Choosing which filings to read for a company, and reading them through an injected NSE client."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from quant_system.fundamentals.models import ReadStatus
from quant_system.fundamentals.reader import Hooks, plan_rows, read_company
from quant_system.shariah.filings.nse_client import FilingsBlocked
from tests.fundamentals.fakes import FakeNse
from tests.fundamentals.support import fixture_bytes, listing_row, quarter_ends

NOW = datetime(2026, 10, 7, 12, 30, tzinfo=UTC)
SEP, DEC = date(2024, 9, 30), date(2024, 12, 31)


def _clock() -> datetime:
    return NOW


def _rows(consolidated: bool = True, count: int = 8) -> list:
    return [
        replace(
            listing_row(period_end=end, consolidated=consolidated),
            filed_on=end + timedelta(days=15),
        )
        for end in quarter_ends(count)
    ]


def test_the_newest_filings_are_planned_first_and_cut_to_the_count_asked_for() -> None:
    planned = plan_rows(_rows(count=12), 8)
    assert len(planned) == 8
    assert planned[0].period_end == date(2024, 12, 31) and planned[-1].period_end == date(
        2023, 3, 31
    )


def test_consolidated_is_planned_when_the_newest_quarter_has_one_and_standalone_is_left_out() -> (
    None
):
    mixed = [*_rows(True, 4), *_rows(False, 4)]
    planned = plan_rows(mixed, 8)
    assert len(planned) == 4 and all(row.consolidated for row in planned)


def test_standalone_is_planned_when_the_newest_quarter_has_no_consolidated_filing() -> None:
    older_consolidated = _rows(True, 6)[:-1]
    planned = plan_rows([*older_consolidated, *_rows(False, 3)], 8)
    assert planned and all(not row.consolidated for row in planned)


def test_a_re_filed_quarter_is_planned_once_with_the_later_filing() -> None:
    first = listing_row(period_end=SEP)
    again = replace(
        first, filed_on=first.filed_on + timedelta(days=30), xbrl_url=first.xbrl_url + "?v=2"
    )  # type: ignore[operator]
    planned = plan_rows([first, again], 8)
    assert planned == [again]


def test_half_yearly_filings_are_not_planned_as_quarters() -> None:
    half = replace(listing_row(period_end=SEP), period_kind="Half-Yearly")
    assert plan_rows([half, *_rows(2)], 8) != [half]
    assert half not in plan_rows([half, *_rows(2)], 8)


def test_a_bank_plans_only_its_newest_filing_so_the_layout_can_be_recorded() -> None:
    bank = [
        replace(listing_row(symbol="HDFCBANK", period_end=end, flag="B")) for end in quarter_ends(4)
    ]
    planned = plan_rows(bank, 8)
    assert [row.period_end for row in planned] == [DEC]


def test_nothing_listed_plans_nothing() -> None:
    assert plan_rows([], 8) == []


def test_reading_a_company_returns_each_filing_with_the_time_it_was_read() -> None:
    sep, dec = listing_row(period_end=SEP), listing_row(period_end=DEC, filed_on=date(2025, 1, 9))
    nse = FakeNse(
        {"TCS": [sep, dec]},
        {
            sep.xbrl_url: fixture_bytes("tcs_2024-09-30_consolidated_trimmed.xml"),
            dec.xbrl_url: fixture_bytes("tcs_2024-12-31_consolidated_trimmed.xml"),
        },
    )
    result = read_company(nse, "TCS", 8, _clock)
    assert [q.period_end for q in result.quarters] == [DEC, SEP]
    assert {q.status for q in result.quarters} == {ReadStatus.READ_OK}
    assert {q.fetched_at for q in result.quarters} == {"2026-10-07T12:30:00Z"}
    assert nse.listed == ["TCS"] and len(nse.fetched) == 2


def test_a_filing_that_nse_no_longer_has_is_skipped_and_counted() -> None:
    sep, dec = listing_row(period_end=SEP), listing_row(period_end=DEC, filed_on=date(2025, 1, 9))
    nse = FakeNse(
        {"TCS": [sep, dec]},
        {sep.xbrl_url: fixture_bytes("tcs_2024-09-30_consolidated_trimmed.xml")},
    )
    result = read_company(nse, "TCS", 8, _clock)
    assert [q.period_end for q in result.quarters] == [SEP] and result.skipped == 1


def test_a_refusal_from_nse_is_not_swallowed() -> None:
    nse = FakeNse({"TCS": [listing_row()]}, fail_with=FilingsBlocked())
    with pytest.raises(FilingsBlocked):
        read_company(nse, "TCS", 8, _clock)


def test_a_bank_gives_one_record_saying_its_layout_is_not_read() -> None:
    bank = listing_row(symbol="HDFCBANK", flag="B")
    nse = FakeNse(
        {"HDFCBANK": [bank]},
        {bank.xbrl_url: fixture_bytes("hdfcbank_2024-09-30_consolidated_trimmed.xml")},
    )
    result = read_company(nse, "HDFCBANK", 8, _clock)
    assert [q.status for q in result.quarters] == [ReadStatus.FORMAT_NOT_READ]
    assert len(nse.fetched) == 1


def test_a_company_with_no_filings_gives_nothing_and_asks_for_nothing() -> None:
    nse = FakeNse({})
    result = read_company(nse, "NOPE", 8, _clock)
    assert result.quarters == [] and nse.fetched == []


def test_progress_is_reported_and_reading_can_be_stopped_between_filings() -> None:
    sep, dec = listing_row(period_end=SEP), listing_row(period_end=DEC, filed_on=date(2025, 1, 9))
    files = {
        sep.xbrl_url: fixture_bytes("tcs_2024-09-30_consolidated_trimmed.xml"),
        dec.xbrl_url: fixture_bytes("tcs_2024-12-31_consolidated_trimmed.xml"),
    }
    nse = FakeNse({"TCS": [sep, dec]}, files)
    seen: list[tuple[int, int]] = []
    hooks = Hooks(
        progress=lambda done, total: seen.append((done, total)), stop=lambda: len(seen) >= 1
    )
    result = read_company(nse, "TCS", 8, _clock, hooks)
    assert seen == [(1, 2)] and len(result.quarters) == 1 and len(nse.fetched) == 1
