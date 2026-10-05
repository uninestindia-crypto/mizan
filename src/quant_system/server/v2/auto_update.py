"""Keeps running paper books up to date: one quick market-data update after each close, when it is safe.

The decision is a pure function (:func:`decide`) so it is tested without threads or the network; the
worker (:class:`AutoUpdater`) only gathers the facts, asks, and starts the existing quick update
(:class:`quant_system.market.downloader.MarketDownload`, ``mode="update"``). There is no second
download path.

An update is attempted only when it cannot surprise the person: the setting is on, a paper book is
running, the data came from QuantOS's own download, and that data is the folder the app is using.
A quick update writes into the app's own folder and then connects it, so without the last check a
person who connected their own research data would be switched to another folder.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from quant_system.market import MarketIndex
from quant_system.market.downloader import MarketDownload, baseline_exists
from quant_system.server.v2.jobs import IndexJob
from quant_system.server.v2.state import AppState

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
# NSE closes at 15:30 IST. A session's prices are treated as available from 18:00 IST.
SETTLED_AFTER = time(18, 0)
POLL_SECONDS = 600.0
FIRST_LOOK_SECONDS = 30.0
RETRY_GAP = timedelta(hours=1)
MAX_ATTEMPTS = 3
# An update that finishes cleanly but finds nothing newer, this many times for one session, means
# there was no newer session (a market holiday): stop, and say so. The next evening's update
# fetches the whole recent window, so a provider that was merely late catches up by itself.
SETTLE_AFTER_MISSES = 2

State = Literal["OFF", "IDLE", "CANNOT", "UPDATING", "CURRENT", "BEHIND"]


def expected_session(now: datetime) -> date:
    """The latest weekday session whose prices should be available at ``now``.

    Exchange holidays are not known here. A holiday only means a clean update finds nothing newer,
    which :data:`SETTLE_AFTER_MISSES` turns into "no newer session" instead of more tries.
    """
    local = now.astimezone(IST)
    day = local.date()
    if day.weekday() < 5 and local.time() >= SETTLED_AFTER:
        return day
    day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


@dataclass(frozen=True)
class Facts:
    now: datetime
    enabled: bool
    running_books: int
    has_baseline: bool
    folder_is_app_data: bool
    index_ready: bool
    latest_session: date | None
    expected: date
    busy: bool  # a download or an index build is in progress
    attempts: int  # tries so far for ``expected``
    last_attempt: datetime | None
    last_failure: str | None = None
    misses: int = 0  # tries that finished cleanly and still left the data behind


@dataclass(frozen=True)
class Decision:
    state: State
    message: str
    start: bool = False
    retry_at: datetime | None = None


def _day(value: date) -> str:
    return f"{value.day} {value:%b %Y}"


def decide(facts: Facts) -> Decision:
    if not facts.enabled:
        return Decision(
            "OFF",
            "Automatic updates are off. Paper books move forward when you update your market data.",
        )
    if facts.running_books == 0:
        return Decision("IDLE", "Nothing to keep up to date: you have no running paper books.")
    if not facts.has_baseline:
        return Decision(
            "CANNOT",
            "Automatic updates need market data downloaded by QuantOS itself. "
            "Download it in Settings → Data and they start working.",
        )
    if not facts.folder_is_app_data:
        return Decision(
            "CANNOT",
            "Your books use market data from your own folder, so QuantOS will not change it by "
            "itself. Update that data yourself, or switch to the QuantOS download in Settings → Data.",
        )
    if not facts.index_ready or facts.latest_session is None:
        return Decision("CANNOT", "Market data is not connected yet.")
    if facts.busy:
        return Decision("UPDATING", "Updating prices now…")
    if facts.latest_session >= facts.expected:
        return Decision("CURRENT", f"Prices are up to date, to {_day(facts.latest_session)}.")
    if facts.misses >= SETTLE_AFTER_MISSES:
        return Decision(
            "CURRENT",
            f"Prices are up to date, to {_day(facts.latest_session)}. There was no newer trading "
            "session to fetch, which usually means a market holiday. QuantOS looks again after "
            "the next close.",
        )
    behind = (
        f"Prices run to {_day(facts.latest_session)}; "
        f"a newer session ({_day(facts.expected)}) should be available."
    )
    if facts.misses:
        behind += " The last update found nothing newer, which is normal on a market holiday."
    reason = f" The last try failed: {facts.last_failure}" if facts.last_failure else ""
    if facts.attempts >= MAX_ATTEMPTS:
        return Decision(
            "BEHIND",
            f"{behind} QuantOS tried {facts.attempts} times and newer prices were not available "
            "(it may have been a market holiday). It will try again after the next close." + reason,
        )
    if facts.last_attempt is not None and facts.now - facts.last_attempt < RETRY_GAP:
        retry_at = facts.last_attempt + RETRY_GAP
        local = retry_at.astimezone()
        return Decision(
            "BEHIND",
            f"{behind} Next automatic try at {local:%H:%M}." + reason,
            retry_at=retry_at,
        )
    return Decision("BEHIND", f"{behind} QuantOS will update them shortly.", start=True)


class AutoUpdater:
    """Polls every few minutes and starts a quick update when :func:`decide` says to."""

    def __init__(
        self,
        *,
        state: AppState,
        index: MarketIndex,
        job: IndexJob,
        download: MarketDownload,
        data_dir: Callable[[], Path],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._state = state
        self._index = index
        self._job = job
        self._download = download
        self._data_dir = data_dir
        self._clock = clock
        self._lock = threading.Lock()
        self._target: date | None = None
        self._attempts = 0
        self._misses = 0
        self._last_attempt: datetime | None = None
        self._run: str | None = None  # the download run this updater started, by its start stamp
        self._run_counted = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ----------------------------------------------------------------------------- facts

    def _facts(self) -> Facts:
        now = self._clock()
        expected = expected_session(now)
        settings = self._state.settings()
        folder = self._data_dir()
        ready = self._index.is_ready()
        latest: date | None = None
        if ready:
            try:
                latest = date.fromisoformat(str(self._index.meta().get("latest_session", ""))[:10])
            except ValueError:
                latest = None
        download = self._download.snapshot()
        busy = download["state"] == "RUNNING" or self._job.running
        with self._lock:
            if self._target != expected:  # a new session to chase starts with a clean slate
                self._target, self._attempts, self._last_attempt = expected, 0, None
                self._misses, self._run, self._run_counted = 0, None, False
            finished = (
                download["state"] == "DONE"
                and download.get("finished_at") is not None  # so the index build has started too
                and download.get("started_at") == self._run
                and not busy
            )
            if finished and not self._run_counted and (latest is None or latest < expected):
                self._misses += 1  # a clean run that still left the data behind
                self._run_counted = True
            attempts, last_attempt, misses = self._attempts, self._last_attempt, self._misses
        failed = download["state"] == "ERROR" and last_attempt is not None
        return Facts(
            now=now,
            enabled=settings.auto_update_paper_books,
            running_books=sum(1 for b in self._state.paper_books() if b["stopped_session"] is None),
            has_baseline=baseline_exists(folder),
            folder_is_app_data=_same_folder(settings.data_folder, folder),
            index_ready=ready,
            latest_session=latest,
            expected=expected,
            busy=busy,
            attempts=attempts,
            last_attempt=last_attempt,
            last_failure=str(download["message"]) if failed else None,
            misses=misses,
        )

    # --------------------------------------------------------------------------- actions

    def tick(self) -> Decision:
        """One look: start a quick update if one is due. Returns what was decided."""
        facts = self._facts()
        decision = decide(facts)
        if decision.start:
            try:
                started = self._download.start(self._data_dir(), mode="update")
            except OSError:
                logger.exception("Automatic update could not start")
                started = False
            if started:
                with self._lock:
                    self._attempts += 1
                    self._last_attempt = facts.now
                    self._run = self._download.snapshot().get("started_at")
                    self._run_counted = False
                logger.info("Automatic update started for session %s", facts.expected)
            # Either way a download is now running: ours, or one someone else started first.
            return Decision("UPDATING", "Updating prices now…")
        return decision

    def snapshot(self) -> dict[str, Any]:
        """What the Paper page shows. Reading it never starts anything."""
        facts = self._facts()
        decision = decide(facts)
        return {
            "enabled": facts.enabled,
            "state": decision.state,
            "message": decision.message,
            "latest_session": facts.latest_session.isoformat() if facts.latest_session else None,
            "expected_session": facts.expected.isoformat(),
            "attempts": facts.attempts,
            "next_try": decision.retry_at.isoformat(timespec="minutes")
            if decision.retry_at
            else None,
        }

    # ---------------------------------------------------------------------------- worker

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, name="QuantOS-AutoUpdate", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(2.0)

    def _loop(self) -> None:
        delay = FIRST_LOOK_SECONDS
        while not self._stop.wait(delay):
            try:
                self.tick()
            except Exception:  # a failed look must never end the worker
                logger.exception("Automatic update check failed")
            delay = POLL_SECONDS


def _same_folder(connected: str | None, own: Path) -> bool:
    if not connected:
        return False
    try:
        return Path(connected).resolve() == own.resolve()
    except OSError:
        return False
