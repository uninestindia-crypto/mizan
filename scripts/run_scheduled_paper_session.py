"""Pre-open refresh then a paper trading session, for unattended scheduled runs.

A scheduled run has nobody watching it, so every step that could silently produce a plausible-but-
wrong session is checked and made to fail loudly instead:

* **Bars must be fresh, counted in trading sessions.** The decision uses the last *completed*
  session, and the run refuses if any trading day between the newest cached bar and today is
  missing. Two earlier versions of this check both failed on a real morning: "did the refresh
  advance?" was the off-by-one described below, and a four-calendar-day staleness bound passed on
  exactly its boundary while Friday's bar was absent entirely. Only a session count can tell a long
  weekend from a dead provider.
* **Macro must cover the same date.** Missing India VIX or NIFTY makes every feature row
  uncomputable, and the session would report a clean 0-proposal run that looked like a decision.
* **Today must be a trading day**, decided against the published NSE holiday calendar rather than
  inferred. The inference this replaces asked "did the previous calendar day trade?", which differs
  from "does today trade?" on exactly the days that matter: it ran a full session **on** the first
  holiday after a trading day, filling orders at stale prices and advancing the portfolio, and then
  refused the genuine trading day after it. One off-by-one, two wrong outcomes, both silent.

  The calendar is `data/authorities/nse-trading-holidays.json`, fetched from the NSE public API. It
  covers a bounded set of years; a date outside them is refused rather than assumed, because a
  calendar that silently stops being authoritative is worse than none.

None of this makes the session *correct* -- it makes it honest about when it should not run.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))

#: Where the refreshed evidence lands. Kept distinct from the historical stores so a scheduled run
#: can never overwrite the ten-year caches other work depends on.
BARS_CACHE = PROJECT_ROOT / "data/evidence/market-cache/nifty500-refresh-20230828-20260827"
MACRO_CACHE = PROJECT_ROOT / "data/evidence/market-cache/macro-refresh-20230828-20260827"
UNIVERSE_CSV = PROJECT_ROOT / "data/evidence/market-cache/scheduled-universe-instruments.csv"

#: Where this refresh writes its own ingestion summary.
#:
#: The ingester's `--summary-file` defaults to
#: `data/evidence/market-analysis/all-market-ingestion-summary.json`, which is the **all-market**
#: record: 3,359 targets and 4,501,992 bars. Omitting the flag meant every scheduled NIFTY500
#: refresh overwrote it with its own 500-symbol result, destroying the larger record. That already
#: happened and was committed in `e853376a`; it would have recurred at 09:00 daily. A refresh writes
#: its summary beside the cache it refreshed, never over an unrelated one.

#: Bars are fetched three years back. The kernel consumes at most 400 trailing sessions, so this is
#: comfortable headroom, and it stays clear of the provider's ten-year retrieval limit.
LOOKBACK_DAYS = 3 * 365

#: Trading sessions that may be missing between the newest cached bar and today before the run
#: refuses. Zero: at 09:00 the newest completed session is the previous trading day, and anything
#: older means the refresh did not get what it asked for.
#:
#: This counts **sessions**, not calendar days. The four-calendar-day bound it replaces could not
#: tell a long weekend from a dead provider, and on 2026-08-31 it passed on exactly its boundary --
#: 4 against a limit of `> 4` -- while the cache was missing Friday 2026-08-28 entirely. Every
#: feature that session computed was a trading day stale and nothing reported it.
MAX_MISSED_SESSIONS = 0


#: The published NSE trading-holiday calendar, committed so the decision is auditable.
HOLIDAY_AUTHORITY = PROJECT_ROOT / "data/authorities/nse-trading-holidays.json"


def log(message: str) -> None:
    print(f"{datetime.now(IST):%Y-%m-%d %H:%M:%S IST} | {message}", flush=True)


class NotATradingDay(Exception):
    """Today is a weekend, a published holiday, or outside the calendar's coverage."""


def require_trading_day(day: date) -> None:
    """Refuse unless `day` is a genuine NSE trading session.

    Fail-closed on every uncertainty. An absent calendar, a malformed one, or a year it does not
    cover all refuse: assuming a day trades because nothing said otherwise is how the previous
    version came to run a full session on a closed market.
    """
    if day.weekday() >= 5:
        raise NotATradingDay(f"{day:%Y-%m-%d %A}: NSE does not trade at weekends")
    if not HOLIDAY_AUTHORITY.is_file():
        raise NotATradingDay(
            f"the trading-holiday authority is missing at {HOLIDAY_AUTHORITY}; refusing rather "
            "than assuming the market is open"
        )
    import json

    document = json.loads(HOLIDAY_AUTHORITY.read_text(encoding="utf-8"))
    covered = set(document.get("covers_years", []))
    if str(day.year) not in covered:
        raise NotATradingDay(
            f"the trading-holiday authority covers {sorted(covered)} and not {day.year}; refresh "
            f"it from {document.get('source_url', 'the NSE holiday API')} before running again"
        )
    for holiday in document.get("holidays", []):
        if holiday.get("date") == day.isoformat():
            raise NotATradingDay(
                f"{day:%Y-%m-%d %A} is an NSE trading holiday: {holiday.get('description')}"
            )


def trading_sessions_between(start: date, end: date) -> int:
    """Trading sessions strictly after `start` and strictly before `end`.

    Friday to Monday is 0 -- nothing was missed. Thursday to Monday is 1, because Friday traded and
    its bar is absent. That distinction is the whole point: calendar arithmetic cannot make it.
    """
    missed = 0
    day = date.fromordinal(start.toordinal() + 1)
    while day < end:
        try:
            require_trading_day(day)
            missed += 1
        except NotATradingDay:
            pass
        day = date.fromordinal(day.toordinal() + 1)
    return missed


def newest_cached_bar_date() -> date | None:
    """The newest exchange date already in the bars cache, or None when it is empty."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from cached_nifty50_evidence import historical_acquisition_from_verified

    from quant_system.evidence import EvidenceResourceType, EvidenceStore, EvidenceStoreConfig

    store_root = BARS_CACHE / "store"
    if not store_root.exists():
        return None
    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    newest: date | None = None
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        records = historical_acquisition_from_verified(verified).records
        if records and (newest is None or records[-1].exchange_date > newest):
            newest = records[-1].exchange_date
    return newest


def build_universe_csv(universe_name: str) -> int:
    """Write the instrument-key CSV the ingester needs, from the published constituent authority.

    The ingester requires an ``Instrument Key`` column; the constituent authorities do not carry
    one. Joining them here is why an earlier attempt silently ingested nothing and still exited 0.
    """
    import csv

    authority = {
        "NIFTY50": PROJECT_ROOT / "data/authorities/nse-nifty50-constituents.csv",
        "NIFTY500": PROJECT_ROOT / "data/authorities/nse-nifty500-constituents.csv",
    }[universe_name.upper()]
    with open(authority, encoding="utf-8-sig") as handle:
        wanted = {(row.get("Symbol") or "").strip() for row in csv.DictReader(handle)}
    with open(
        PROJECT_ROOT / "data/authorities/nse-all-listed-equities.csv", encoding="utf-8-sig"
    ) as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = [
            row
            for row in reader
            if (row.get("Symbol") or "").strip() in wanted
            and (row.get("Instrument Key") or "").startswith("NSE_EQ|")
        ]
    UNIVERSE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(UNIVERSE_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def build_refresh_command(to_day: date) -> list[str]:
    """The ingester invocation this refresh runs.

    Extracted so a test can read the command the code actually produces rather than the source text
    that produces it. `--summary-file` was omitted here for weeks and the ingester fell back to its
    default -- the all-market record -- so every scheduled NIFTY500 refresh overwrote a 3,359-target
    file with its own 500. A test that greps this function's source passes the moment the flag
    appears anywhere in it, including in a comment explaining its absence.
    """
    return [
        sys.executable,
        str(PROJECT_ROOT / "scripts/ingest_all_market_data.py"),
        "--universe-csv",
        str(UNIVERSE_CSV),
        "--cache-root",
        str(BARS_CACHE),
        "--from-date",
        (to_day - timedelta(days=LOOKBACK_DAYS)).isoformat(),
        "--to-date",
        to_day.isoformat(),
        "--concurrency",
        "8",
        "--summary-file",
        str(BARS_CACHE / "ingestion-summary.json"),
        # Explicit, for the same reason as the summary file above.
        #
        # `--corporate-actions-dir` defaults into the ten-year all-market store, so this refresh
        # wrote its corporate-action records there. Harmless while every NIFTY 500 name already has
        # a file that parses -- measured: 0 non-list, 0 unreadable -- but a new index constituent
        # absent from the 3,359-name authority would have its three-year record written into a
        # store whose `build_corporate_action_authority` hardcodes an effective window of
        # 2016-08-22..2026-08-21. A three-year record labelled as covering ten years is a
        # provenance defect, and it would be discovered by an adjustment that failed to apply.
        "--corporate-actions-dir",
        str(BARS_CACHE / "corporate-actions"),
    ]


def refresh_bars(universe_name: str, to_day: date) -> None:
    matched = build_universe_csv(universe_name)
    log(f"universe {universe_name}: {matched} instruments with provider keys")
    if matched == 0:
        raise SystemExit("refusing to run: no instrument keys resolved for the universe")
    log("refreshing bars ...")
    subprocess.run(build_refresh_command(to_day), check=True, cwd=PROJECT_ROOT)


def refresh_macro(to_day: date) -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from ingest_macro_regimes import ingest_macro_series

    log("refreshing macro ...")
    ingest_macro_series(
        MACRO_CACHE,
        from_date=to_day - timedelta(days=LOOKBACK_DAYS),
        to_date=to_day,
    )


def macro_covers(day: date) -> bool:
    import json

    for name in ("INDIAVIX", "NIFTY50"):
        path = MACRO_CACHE / f"macro_{name}.json"
        if not path.is_file():
            return False
        days = {c[0][:10] for c in json.loads(path.read_text(encoding="utf-8")).get("candles", [])}
        if day.isoformat() not in days:
            return False
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-name", default="NIFTY500", choices=["NIFTY50", "NIFTY500"])
    parser.add_argument("--capital", default="1000000.0")
    parser.add_argument("--end-time-ist", default="15:30:00")
    parser.add_argument("--interval-seconds", default="30")
    args = parser.parse_args()

    today = datetime.now(IST).date()
    log(f"scheduled paper session for {today:%Y-%m-%d %A}")
    try:
        require_trading_day(today)
    except NotATradingDay as refusal:
        log(f"refusing: {refusal}")
        return 2

    before = newest_cached_bar_date()
    log(f"newest cached bar before refresh: {before}")

    # There is deliberately no `--skip-refresh`. It used to wrap every guard below and still run
    # the real session: live quotes, filled orders, a full markdown report, and a permanent advance
    # of `sessions_completed` and the rebalance clock -- all on whatever happened to be cached. A
    # rehearsal that leaves artifacts identical to a session is not a rehearsal. To exercise the
    # wiring, run `scripts/run_paper_pilot_session.py` directly and read what it writes.
    target = today - timedelta(days=1)
    refresh_bars(args.universe_name, target)
    refresh_macro(target)
    after = newest_cached_bar_date()
    log(f"newest cached bar after refresh : {after}")
    if after is None:
        log("refusing: the bars cache is empty after a refresh")
        return 3
    if before is not None and after < before:
        log(f"refusing: the newest cached bar went backwards, {before} -> {after}")
        return 4
    # Counted in trading sessions. Today being a trading day is decided by the calendar above; what
    # remains is whether the refresh actually delivered the sessions between then and now.
    missed = trading_sessions_between(after, today)
    if missed > MAX_MISSED_SESSIONS:
        log(
            f"refusing: newest bar is {after} and {missed} trading session(s) are missing between "
            f"it and today. Every feature would be computed from stale data. The refresh did not "
            f"deliver what it asked for -- check the provider and the token."
        )
        return 4
    if not macro_covers(after):
        log(f"refusing: macro does not cover {after}; every feature row would be uncomputable")
        return 5

    log("starting paper session ...")
    session = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/run_paper_pilot_session.py"),
        "--realtime",
        "--universe-name",
        args.universe_name,
        "--capital",
        args.capital,
        "--end-time-ist",
        args.end_time_ist,
        "--interval-seconds",
        args.interval_seconds,
    ]
    completed = subprocess.run(session, check=False, cwd=PROJECT_ROOT)
    log(f"paper session exited {completed.returncode}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
