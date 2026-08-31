"""The unattended scheduled session's refusal rules.

A Red Team pass found the trading-day guard **inverted**: it ran a full session on the first holiday
after a trading day -- filling orders at stale prices, charging real statutory fees, writing a full
report and advancing the portfolio -- and then refused the genuine trading day after it. One
off-by-one, two wrong outcomes, both silent, and no test existed to catch either.

The cause was semantic rather than arithmetic. The guard asked "did the previous calendar day
trade?" by watching whether a refresh advanced the newest cached bar. On the first holiday it does
advance, because the refresh collects the previous session's bar that the previous run had not yet
seen. The question that needed answering was "does *today* trade?", and no amount of looking at
historical bars answers it -- so it is now answered from the published NSE calendar.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from run_scheduled_paper_session import (  # noqa: E402
    HOLIDAY_AUTHORITY,
    MAX_MISSED_SESSIONS,
    NotATradingDay,
    require_trading_day,
    trading_sessions_between,
)

AUTHORITY = json.loads(HOLIDAY_AUTHORITY.read_text(encoding="utf-8"))
HOLIDAYS = {entry["date"]: entry["description"] for entry in AUTHORITY["holidays"]}
COVERED_YEAR = int(sorted(AUTHORITY["covers_years"])[0])


def test_the_holiday_authority_is_real_and_says_where_it_came_from() -> None:
    """An authority nobody can trace is not an authority."""
    assert AUTHORITY["source_url"].startswith("https://www.nseindia.com/")
    assert AUTHORITY["source_segment"] == "CM"
    assert AUTHORITY["holiday_count"] == len(AUTHORITY["holidays"]) > 0
    assert all(date.fromisoformat(day) for day in HOLIDAYS)


def test_a_weekend_is_refused() -> None:
    saturday = date(2026, 8, 29)
    assert saturday.weekday() == 5
    with pytest.raises(NotATradingDay, match="does not trade at weekends"):
        require_trading_day(saturday)


def test_an_ordinary_weekday_is_a_trading_day() -> None:
    monday = date(2026, 8, 31)
    assert monday.isoformat() not in HOLIDAYS
    require_trading_day(monday)


def test_every_published_holiday_is_refused() -> None:
    """The exact failure: the session used to run on these days and fill against stale prices."""
    weekday_holidays = [day for day in HOLIDAYS if date.fromisoformat(day).weekday() < 5]
    assert weekday_holidays, "the calendar lists no weekday holidays, so this proves nothing"
    for day in weekday_holidays:
        with pytest.raises(NotATradingDay, match="trading holiday"):
            require_trading_day(date.fromisoformat(day))


def test_the_day_after_a_holiday_is_not_refused() -> None:
    """The other half of the same off-by-one: a real session was silently skipped.

    Under the old inference the bar date had not advanced on the day after a holiday, so the run
    logged "treating today as non-trading" and stopped -- on a day the exchange was open.
    """
    for day in sorted(HOLIDAYS):
        after = date.fromisoformat(day)
        for _ in range(5):
            after = date.fromordinal(after.toordinal() + 1)
            if after.weekday() < 5 and after.isoformat() not in HOLIDAYS:
                break
        else:  # pragma: no cover - only if a week were entirely non-trading
            continue
        require_trading_day(after)


def test_a_year_the_calendar_does_not_cover_is_refused_not_assumed() -> None:
    """Fail-closed. A calendar that silently stops being authoritative is worse than none."""
    uncovered = date(COVERED_YEAR + 5, 3, 1)
    while uncovered.weekday() >= 5:  # the weekend check fires first, so land on a weekday
        uncovered = date.fromordinal(uncovered.toordinal() + 1)
    with pytest.raises(NotATradingDay, match="covers"):
        require_trading_day(uncovered)


def test_a_missing_calendar_is_refused(monkeypatch, tmp_path) -> None:
    import run_scheduled_paper_session as runner

    monkeypatch.setattr(runner, "HOLIDAY_AUTHORITY", tmp_path / "absent.json")
    with pytest.raises(NotATradingDay, match="missing"):
        runner.require_trading_day(date(COVERED_YEAR, 8, 31))


def test_the_rehearsal_flag_is_gone() -> None:
    """`--skip-refresh` disabled every data guard and still traded and persisted state.

    A rehearsal whose artifacts are identical to a real session is not a rehearsal. It is removed
    rather than fixed, because the honest rehearsal is to run the session script directly.
    """
    source = (REPO_ROOT / "scripts/run_scheduled_paper_session.py").read_text(encoding="utf-8")
    assert "args.skip_refresh" not in source
    assert '"--skip-refresh"' not in source


def test_staleness_is_counted_in_trading_sessions_not_calendar_days() -> None:
    """Calendar arithmetic cannot tell a long weekend from a dead provider.

    On 2026-08-31 the four-calendar-day bound passed on exactly its boundary -- 4 against a limit
    of `> 4` -- while Friday 2026-08-28's bar was missing entirely, so every feature that session
    computed was a trading day stale and nothing said so.
    """
    friday, monday = date(2026, 8, 28), date(2026, 8, 31)
    thursday, wednesday = date(2026, 8, 27), date(2026, 8, 26)

    assert trading_sessions_between(friday, monday) == 0, "a weekend is not a missed session"
    assert trading_sessions_between(thursday, monday) == 1, "Friday traded and its bar is absent"
    assert trading_sessions_between(wednesday, monday) == 2

    assert MAX_MISSED_SESSIONS == 0, (
        "at 09:00 the newest completed session is the previous trading day; anything older means "
        "the refresh did not deliver what it asked for"
    )
    assert trading_sessions_between(thursday, monday) > MAX_MISSED_SESSIONS, (
        "the exact case that slipped through on 2026-08-31 must now refuse"
    )


def test_the_refresh_writes_its_own_summary_not_the_all_market_one() -> None:
    """The ingester's `--summary-file` default is the **all-market** record, and omitting it
    destroyed that record.

    `data/evidence/market-analysis/all-market-ingestion-summary.json` covers 3,359 targets and
    4,501,992 bars. Every scheduled NIFTY500 refresh overwrote it with its own 500-symbol result;
    that was committed in `e853376a` and would have recurred at 09:00 daily.

    Driven, not read. An earlier version of this test parsed `refresh_bars` and asserted the flag
    appeared in the command *literal* -- which a comment mentioning the flag can satisfy, and which
    thirteen independent mutants walked straight through in the round that shipped it. This calls
    the builder and inspects the command it actually returns.
    """
    from run_scheduled_paper_session import BARS_CACHE, build_refresh_command

    command = build_refresh_command(date(2026, 9, 1))

    assert "--summary-file" in command, (
        "the refresh does not pass --summary-file, so the ingester falls back to its default: the "
        "all-market summary. A NIFTY500 refresh would overwrite a 3,359-target record."
    )
    destination = Path(command[command.index("--summary-file") + 1])
    assert BARS_CACHE in destination.parents, (
        f"the summary is written to {destination}, outside the cache this refresh owns. A refresh "
        "must not write over a record it did not produce."
    )
    assert "market-analysis" not in destination.parts, (
        f"the summary is written into {destination}, the all-market directory"
    )


def test_the_all_market_summary_still_covers_the_whole_market() -> None:
    """The file that was destroyed, restored, and now guarded.

    A 500-entry all-market summary is the corruption, not a smaller universe: this file is the
    record of the full ingest and nothing else may write it.
    """
    import json as _json

    path = REPO_ROOT / "data/evidence/market-analysis/all-market-ingestion-summary.json"
    if not path.is_file():
        pytest.skip("the all-market summary is not present in this checkout")

    document = _json.loads(path.read_text(encoding="utf-8"))
    entries = document if isinstance(document, list) else document.get("results", document)

    assert len(entries) > 3000, (
        f"the all-market summary holds {len(entries)} entries. It covered 3,359; a scheduled "
        "NIFTY500 refresh writing over it leaves exactly 500."
    )
