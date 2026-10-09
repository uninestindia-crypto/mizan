"""Reading company filings in the background: one job at a time, plain messages, stop, and what gets saved.

The NSE reader is always a fake that answers from a script. Nothing here reaches the network or sleeps: a job runs
when the test says so, and the one test that uses a real thread waits on events, never on the clock.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from quant_system.shariah.filings.models import FilingFigures, ReadStatus
from quant_system.shariah.filings.nse_client import (
    FilingsBlocked,
    FilingsUnavailable,
    InvalidSymbol,
)
from quant_system.shariah.filings.selection import NO_SHEET, Selection
from quant_system.shariah.filings.store import FilingsStore
from quant_system.shariah.services.filing_jobs import MAX_KEPT, FilingJobs, TooBusy
from quant_system.shariah.services.filing_words import (
    BUSY,
    NOTHING_TO_REFRESH,
    SAVE_FAILED_PREFIX,
    STOPPED,
    TOO_MANY_BLOCKS,
)
from tests.shariah.proof_service_fixtures import (
    bank_figures,
    broken_figures,
    figures_for,
    make_store,
    tcs_figures,
)

Outcome = Selection | Exception


def read_fine(figures: FilingFigures) -> Selection:
    return Selection(figures, figures.read_status, figures.read_note, 1)


def named(symbol: str) -> FilingFigures:
    return figures_for(symbol, f"{symbol} Limited")


class Spawner:
    """Holds the jobs' work until the test runs it, so a test can look at a job before and after."""

    def __init__(self) -> None:
        self.tasks: list[Callable[[], None]] = []

    def __call__(self, task: Callable[[], None]) -> None:
        self.tasks.append(task)

    def run(self, index: int = 0) -> None:
        self.tasks[index]()


class Script:
    """A fake NSE reader: each stock answers from the script, and every request is remembered."""

    def __init__(self, answers: dict[str, Outcome] | None = None) -> None:
        self.answers = answers or {}
        self.asked: list[str] = []
        self.after_read: Callable[[str], None] = lambda symbol: None

    def read_company(self, symbol: str) -> Selection:
        self.asked.append(symbol)
        self.after_read(symbol)
        answer = self.answers.get(symbol) or read_fine(named(symbol))
        if isinstance(answer, Exception):
            raise answer
        return answer


class Rig:
    def __init__(
        self, tmp_path: Path, tracked: list[str] | None = None, snapshot: bool = False
    ) -> None:
        self.store = make_store(tmp_path, None if snapshot else {})
        self.user_db = tmp_path / "user_filings.sqlite"
        self.script = Script()
        self.spawn = Spawner()
        self.tracked = tracked or []
        self.jobs = FilingJobs(self.store, lambda: self.script, lambda: self.tracked, self.spawn)

    def saved(self, symbol: str) -> bool:
        return self.store.get(symbol) is not None


def run_many(rig: Rig, count: int) -> list[str]:
    """Start and finish `count` one-stock jobs, one after the other."""
    ids = []
    for index in range(count):
        ids.append(rig.jobs.start_one("TCS"))
        rig.spawn.run(index)
    return ids


# ------------------------------------------------------------------------------------- one stock


def test_reading_one_stock_saves_its_filing_and_ends_with_a_plain_sentence(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.script.answers["TCS"] = read_fine(tcs_figures())
    job = rig.jobs.start_one("tcs")
    assert rig.jobs.get(job) == {
        "status": "running",
        "done": 0,
        "total": 1,
        "message": "Reading the latest filing for TCS from NSE.",
        "failures": [],
    }
    rig.spawn.run()
    assert rig.jobs.get(job) == {
        "status": "done",
        "done": 1,
        "total": 1,
        "message": "Read the latest filing for TCS.",
        "failures": [],
    }
    assert rig.script.asked == ["TCS"] and rig.saved("TCS")


def test_a_symbol_that_is_not_an_nse_symbol_starts_nothing(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    with pytest.raises(InvalidSymbol):
        rig.jobs.start_one("not a symbol")
    assert rig.spawn.tasks == []


@pytest.mark.parametrize(
    ("answer", "words"),
    [
        (FilingsBlocked(), "NSE is not letting QuantOS read"),
        (FilingsUnavailable(), "NSE did not answer. Check your internet connection"),
        (Selection(None, ReadStatus.NO_BALANCE_SHEET, NO_SHEET, 3), "carries a balance sheet"),
        (read_fine(bank_figures()), "This company is a bank"),
        (read_fine(broken_figures()), "does not agree with itself"),
    ],
)
def test_a_stock_that_cannot_be_read_fails_in_plain_words_and_nothing_is_saved(
    tmp_path: Path, answer: Outcome, words: str
) -> None:
    rig = Rig(tmp_path)
    rig.script.answers["TCS"] = answer
    job = rig.jobs.start_one("TCS")
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert state is not None and state["status"] == "failed" and state["done"] == 1
    assert words in state["message"]
    assert state["failures"] == [{"symbol": "TCS", "reason": state["message"]}]
    assert not rig.saved("TCS") and not rig.user_db.exists()


def test_an_unexpected_failure_reads_as_a_plain_sentence_and_leaks_nothing(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.script.answers["TCS"] = RuntimeError("secret internal detail")
    job = rig.jobs.start_one("TCS")
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert state is not None and state["status"] == "failed"
    assert state["message"] == "QuantOS could not read this company's filing."
    assert "secret" not in str(state)


def test_a_filing_that_could_not_be_saved_stops_the_job_and_says_so(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("a file where the data folder should be")
    rig.store = FilingsStore(None, blocker / "user.sqlite")
    rig.jobs = FilingJobs(rig.store, lambda: rig.script, lambda: [], rig.spawn)
    job = rig.jobs.start_one("TCS")
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert state is not None and state["status"] == "failed"
    assert state["message"].startswith(SAVE_FAILED_PREFIX) and "could not save" in state["message"]


# ------------------------------------------------------------------------------------- one at a time


def test_a_second_job_is_refused_while_one_is_running_and_allowed_once_it_ends(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    rig.jobs.start_one("TCS")
    with pytest.raises(TooBusy, match=BUSY):
        rig.jobs.start_one("INFY")
    with pytest.raises(TooBusy):
        rig.jobs.start_refresh()
    rig.spawn.run()
    assert rig.jobs.start_one("INFY")


def test_a_real_thread_runs_the_job_and_the_busy_and_stop_rules_hold_while_it_runs(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path, {})
    entered, release = threading.Event(), threading.Event()

    class Blocking:
        def read_company(self, symbol: str) -> Selection:
            entered.set()
            release.wait(10)  # a failure guard only: the test sets this itself
            return read_fine(named(symbol))

    jobs = FilingJobs(store, Blocking, lambda: [])
    job = jobs.start_one("TCS")
    assert entered.wait(10)
    state = jobs.get(job)
    assert state is not None and state["status"] == "running"
    with pytest.raises(TooBusy):
        jobs.start_one("INFY")
    assert jobs.cancel(job) is True
    worker = next(t for t in threading.enumerate() if t.name == "shariah-filings")
    release.set()
    assert worker.daemon is True
    worker.join(10)
    final = jobs.get(job)
    assert final is not None and final["status"] == "cancelled" and final["message"] == STOPPED
    assert store.get("TCS") is None  # what the stopped job was in the middle of is not kept


# ------------------------------------------------------------------------------------- stopping


def test_a_job_stopped_before_it_starts_reads_nothing(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    job = rig.jobs.start_one("TCS")
    assert rig.jobs.cancel(job) is True
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert state is not None and state["status"] == "cancelled" and state["message"] == STOPPED
    assert rig.script.asked == [] and not rig.user_db.exists()


def test_stopping_a_refresh_stops_before_the_next_stock_and_keeps_what_was_already_read(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, tracked=["AAA", "BBB", "CCC"])
    job = rig.jobs.start_refresh()
    rig.script.after_read = lambda symbol: rig.jobs.cancel(job) if symbol == "BBB" else None
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert rig.script.asked == ["AAA", "BBB"]  # CCC was never asked for
    assert state is not None and state["status"] == "cancelled" and state["done"] == 1
    assert rig.saved("AAA") and not rig.saved("BBB")  # BBB was being read when it was stopped


def test_stopping_twice_or_after_the_end_changes_nothing(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    job = rig.jobs.start_one("TCS")
    rig.spawn.run()
    assert rig.jobs.cancel(job) is True and rig.jobs.cancel(job) is True
    state = rig.jobs.get(job)
    assert state is not None and state["status"] == "done"


def test_stopping_a_job_that_does_not_exist_says_so(tmp_path: Path) -> None:
    assert Rig(tmp_path).jobs.cancel("nope") is False
    assert Rig(tmp_path).jobs.get("nope") is None


# ------------------------------------------------------------------------------------- refreshing many


def test_a_refresh_reads_what_the_app_follows_then_what_is_already_screened(tmp_path: Path) -> None:
    rig = Rig(tmp_path, tracked=["INFY", "tcs", "not a symbol", "INFY"], snapshot=True)
    job = rig.jobs.start_refresh()
    state = rig.jobs.get(job)
    assert state is not None and state["total"] == 4 and "1 of 4: INFY" in state["message"]
    rig.spawn.run()
    # followed stocks first (once each, bad symbols dropped), then the cleanly read ones; a bank is not re-read
    assert rig.script.asked == ["INFY", "TCS", "DRYBREW", "FOODCO"]


def test_a_refresh_says_how_far_it_has_got(tmp_path: Path) -> None:
    rig = Rig(tmp_path, tracked=["AAA", "BBB", "CCC"])
    job = rig.jobs.start_refresh()
    seen: list[str] = []
    rig.script.after_read = lambda symbol: seen.append((rig.jobs.get(job) or {})["message"])
    rig.spawn.run()
    assert seen == [
        "Reading filing 1 of 3: AAA.",
        "Reading filing 2 of 3: BBB.",
        "Reading filing 3 of 3: CCC.",
    ]


def test_a_refresh_with_some_failures_still_ends_done_and_lists_each_one(tmp_path: Path) -> None:
    rig = Rig(tmp_path, tracked=["AAA", "BBB", "CCC"])
    rig.script.answers["BBB"] = FilingsUnavailable()
    job = rig.jobs.start_refresh()
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert state is not None and state["status"] == "done" and state["done"] == 3
    assert state["message"] == "Updated 2 of 3 stocks. 1 could not be read."
    assert [f["symbol"] for f in state["failures"]] == ["BBB"]
    assert rig.saved("AAA") and not rig.saved("BBB") and rig.saved("CCC")


def test_a_refresh_that_could_read_nothing_fails_and_says_why(tmp_path: Path) -> None:
    rig = Rig(tmp_path, tracked=["AAA", "BBB"])
    rig.script.answers.update(AAA=FilingsUnavailable(), BBB=FilingsUnavailable())
    job = rig.jobs.start_refresh()
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert state is not None and state["status"] == "failed"
    assert state["message"].startswith(
        "QuantOS could not read any company filing. NSE did not answer."
    )


def test_a_refresh_with_nothing_to_refresh_ends_at_once(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    job = rig.jobs.start_refresh()
    assert rig.spawn.tasks == []
    assert rig.jobs.get(job) == {
        "status": "done",
        "done": 0,
        "total": 0,
        "message": NOTHING_TO_REFRESH,
        "failures": [],
    }


def test_three_refusals_in_a_row_stop_the_refresh_and_nothing_is_retried(tmp_path: Path) -> None:
    rig = Rig(tmp_path, tracked=["AAA", "BBB", "CCC", "DDD", "EEE"])
    refused: dict[str, Outcome] = {s: FilingsBlocked() for s in ("AAA", "BBB", "CCC", "DDD", "EEE")}
    rig.script.answers.update(refused)
    job = rig.jobs.start_refresh()
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert rig.script.asked == ["AAA", "BBB", "CCC"]  # each asked once; DDD and EEE left alone
    assert state is not None and state["status"] == "failed" and state["message"] == TOO_MANY_BLOCKS


def test_a_success_between_refusals_starts_the_count_again(tmp_path: Path) -> None:
    rig = Rig(tmp_path, tracked=["AAA", "BBB", "CCC", "DDD", "EEE"])
    blocked = ("AAA", "BBB", "DDD", "EEE")
    rig.script.answers.update({s: FilingsBlocked() for s in blocked})
    job = rig.jobs.start_refresh()
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert rig.script.asked == ["AAA", "BBB", "CCC", "DDD", "EEE"]
    assert state is not None and state["status"] == "done" and rig.saved("CCC")


def test_an_older_filing_never_replaces_a_newer_one_but_the_stock_still_counts_as_read(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path, snapshot=True)
    older = figures_for(
        "TCS",
        "Tata",
        period_end=date(2024, 3, 31),
        ytd_start=date(2023, 4, 1),
        quarter_start=date(2024, 1, 1),
    )
    rig.script.answers["TCS"] = read_fine(older)
    job = rig.jobs.start_one("TCS")
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert state is not None and state["status"] == "done"
    held = rig.store.get("TCS")
    assert held is not None and held.proof.period_end.isoformat() == "2024-09-30"


# ------------------------------------------------------------------------------------- bookkeeping


def test_only_the_newest_jobs_are_remembered(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    ids = run_many(rig, MAX_KEPT + 5)
    assert rig.jobs.get(ids[0]) is None
    assert rig.jobs.get(ids[-1]) is not None


def test_a_failure_keeps_at_most_two_hundred_listed(tmp_path: Path) -> None:
    names = [f"S{n}" for n in range(230)]
    rig = Rig(tmp_path, tracked=names)
    rig.script.answers.update({name: FilingsUnavailable() for name in names})
    job = rig.jobs.start_refresh()
    rig.spawn.run()
    state = rig.jobs.get(job)
    assert state is not None and state["done"] == 230 and len(state["failures"]) == 200


def test_the_complete_set_of_messages_has_no_developer_words() -> None:
    sentences = [BUSY, STOPPED, TOO_MANY_BLOCKS, NOTHING_TO_REFRESH, SAVE_FAILED_PREFIX]
    banned = ("api", "json", "http", "403", "xbrl", "exception", "traceback")
    assert [s for s in sentences if any(word in s.lower().split() for word in banned)] == []
