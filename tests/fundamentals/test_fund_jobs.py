"""Reading a company's results in the background: success, refusal, stop, a second job, all with a fake NSE."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from quant_system.fundamentals.jobs import BUSY, STOPPED, FundamentalsJobs, InvalidSymbol, TooBusy
from quant_system.fundamentals.store import FundamentalsStore
from quant_system.shariah.filings.nse_client import FilingsBlocked
from tests.fundamentals.fakes import FakeNse
from tests.fundamentals.jobs_support import Held
from tests.fundamentals.support import fixture_bytes, listing_row

SEP, DEC = date(2024, 9, 30), date(2024, 12, 31)


def _now() -> datetime:
    return datetime(2026, 10, 7, tzinfo=UTC)


def _nse() -> FakeNse:
    sep, dec = listing_row(period_end=SEP), listing_row(period_end=DEC, filed_on=date(2025, 1, 9))
    files = {
        sep.xbrl_url: fixture_bytes("tcs_2024-09-30_consolidated_trimmed.xml"),
        dec.xbrl_url: fixture_bytes("tcs_2024-12-31_consolidated_trimmed.xml"),
    }
    return FakeNse({"TCS": [sep, dec]}, files)


def _jobs(
    tmp_path: Path, nse: FakeNse, held: Held, with_store: bool = True
) -> tuple[FundamentalsJobs, FundamentalsStore]:
    store = FundamentalsStore(None, tmp_path / "f.sqlite" if with_store else None)
    return FundamentalsJobs(store, lambda: nse, _now, held), store


def test_a_job_reads_every_filing_saves_it_and_ends_with_a_plain_sentence(tmp_path: Path) -> None:
    held = Held()
    jobs, store = _jobs(tmp_path, _nse(), held)
    job_id = jobs.start("tcs")
    assert jobs.get(job_id)["status"] == "running"  # type: ignore[index]
    held.run()
    done = jobs.get(job_id)
    assert done is not None and done["status"] == "done" and done["done"] == done["total"] == 2
    assert done["saved"] == 2 and done["message"] == "Read 2 of 2 filings for TCS."
    assert [q.period_end for q in store.quarters("TCS")] == [SEP, DEC]


def test_a_second_job_while_one_runs_is_turned_away_and_a_later_one_is_allowed(
    tmp_path: Path,
) -> None:
    held = Held()
    jobs, _ = _jobs(tmp_path, _nse(), held)
    jobs.start("TCS")
    with pytest.raises(TooBusy, match="already reading"):
        jobs.start("TCS")
    held.run()
    assert jobs.start("TCS")
    assert BUSY.endswith("then try again.")


def test_a_symbol_that_is_not_one_is_refused_before_anything_starts(tmp_path: Path) -> None:
    jobs, _ = _jobs(tmp_path, _nse(), Held())
    with pytest.raises(InvalidSymbol):
        jobs.start("not a symbol!")


def test_a_refusal_from_nse_ends_the_job_in_plain_words_and_keeps_what_was_read(
    tmp_path: Path,
) -> None:
    nse = _nse()
    calls: list[str] = []

    def refuse_second(url: str) -> None:
        calls.append(url)
        if len(calls) == 2:
            raise FilingsBlocked()

    nse.on_fetch = refuse_second
    held = Held()
    jobs, store = _jobs(tmp_path, nse, held)
    job_id = jobs.start("TCS")
    held.run()
    ended = jobs.get(job_id)
    assert ended is not None and ended["status"] == "failed"
    assert (
        ended["message"]
        == "NSE is not letting QuantOS read this company's filings right now. Try again later."
    )
    assert ended["failures"] == [{"symbol": "TCS", "reason": ended["message"]}]
    assert len(store.quarters("TCS")) == 1 and len(calls) == 2  # no retry


def test_a_company_nse_lists_nothing_for_fails_with_a_reason(tmp_path: Path) -> None:
    held = Held()
    jobs, _ = _jobs(tmp_path, FakeNse({}), held)
    job_id = jobs.start("ZZZZ")
    held.run()
    ended = jobs.get(job_id)
    assert (
        ended is not None
        and ended["status"] == "failed"
        and "no quarterly results filing" in ended["message"]
    )


def test_stopping_a_job_keeps_the_filings_already_read_and_reads_no_more(tmp_path: Path) -> None:
    nse = _nse()
    held = Held()
    jobs, store = _jobs(tmp_path, nse, held)
    job_id = jobs.start("TCS")
    nse.on_fetch = lambda url: jobs.cancel(job_id) if len(nse.fetched) == 2 else None
    held.run()
    ended = jobs.get(job_id)
    assert ended is not None and ended["status"] == "cancelled" and ended["message"] == STOPPED
    assert len(store.quarters("TCS")) == 1 and len(nse.fetched) == 2


def test_stopping_before_it_starts_reading_reads_nothing(tmp_path: Path) -> None:
    nse = _nse()
    held = Held()
    jobs, store = _jobs(tmp_path, nse, held)
    job_id = jobs.start("TCS")
    assert jobs.cancel(job_id) and jobs.cancel(job_id)
    held.run()
    assert nse.fetched == [] and store.quarters("TCS") == []
    assert jobs.get(job_id)["status"] == "cancelled"  # type: ignore[index]


def test_an_unknown_job_is_not_found(tmp_path: Path) -> None:
    jobs, _ = _jobs(tmp_path, _nse(), Held())
    assert jobs.get("nope") is None and jobs.cancel("nope") is False


def test_a_computer_with_nowhere_to_save_says_so_in_plain_words(tmp_path: Path) -> None:
    held = Held()
    jobs, _ = _jobs(tmp_path, _nse(), held, with_store=False)
    job_id = jobs.start("TCS")
    held.run()
    ended = jobs.get(job_id)
    assert (
        ended is not None and ended["status"] == "failed" and "no place to save" in ended["message"]
    )


def test_an_unexpected_crash_ends_the_job_without_showing_a_stack_trace(tmp_path: Path) -> None:
    class Broken(FakeNse):
        def list_results(self, symbol: str) -> list:
            raise RuntimeError("database is locked at /secret/path")

    held = Held()
    jobs, _ = _jobs(tmp_path, Broken({}), held)
    job_id = jobs.start("TCS")
    held.run()
    ended = jobs.get(job_id)
    assert ended is not None and ended["status"] == "failed"
    assert "/secret/path" not in str(ended) and ended["message"].startswith("Something went wrong")
