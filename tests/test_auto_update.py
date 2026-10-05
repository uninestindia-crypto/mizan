"""Paper books keep themselves up to date: when an update is due, and when it must not happen."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.market.downloader import MARKER
from quant_system.server.app import app
from quant_system.server.v2 import paths, router
from quant_system.server.v2.auto_update import (
    IST,
    MAX_ATTEMPTS,
    RETRY_GAP,
    AutoUpdater,
    Facts,
    decide,
    expected_session,
)
from quant_system.server.v2.state import AppState

# 2026-10-05 is a Monday.
MONDAY = date(2026, 10, 5)


def _ist(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST).astimezone(UTC)


# --------------------------------------------------------------------- which session is due


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (_ist(MONDAY, 18, 0), MONDAY),  # evening of a weekday: today's session is available
        (_ist(MONDAY, 17, 59), date(2026, 10, 2)),  # still before 18:00: Monday's is not
        (_ist(MONDAY, 9, 0), date(2026, 10, 2)),  # Monday morning: last Friday
        (_ist(date(2026, 10, 3), 12), date(2026, 10, 2)),  # Saturday: Friday
        (_ist(date(2026, 10, 4), 21), date(2026, 10, 2)),  # Sunday night: still Friday
        (_ist(date(2026, 10, 9), 23, 30), date(2026, 10, 9)),  # Friday late: Friday
    ],
)
def test_the_session_that_should_be_available(now: datetime, expected: date) -> None:
    assert expected_session(now) == expected


# ------------------------------------------------------------------------- the decision


def _facts(**changes: Any) -> Facts:
    base: dict[str, Any] = {
        "now": _ist(MONDAY, 19),
        "enabled": True,
        "running_books": 1,
        "has_baseline": True,
        "folder_is_app_data": True,
        "index_ready": True,
        "latest_session": date(2026, 10, 2),
        "expected": MONDAY,
        "busy": False,
        "attempts": 0,
        "last_attempt": None,
    }
    base.update(changes)
    return Facts(**base)


def test_an_update_starts_when_the_prices_are_a_session_behind() -> None:
    decision = decide(_facts())
    assert decision.start and decision.state == "BEHIND"
    assert (
        "will update them shortly" in decision.message
    )  # nothing has started yet, so it must not say so


@pytest.mark.parametrize(
    ("changes", "state"),
    [
        ({"enabled": False}, "OFF"),
        ({"running_books": 0}, "IDLE"),
        ({"has_baseline": False}, "CANNOT"),
        ({"folder_is_app_data": False}, "CANNOT"),
        ({"index_ready": False, "latest_session": None}, "CANNOT"),
        ({"busy": True}, "UPDATING"),
        ({"latest_session": MONDAY}, "CURRENT"),
        ({"latest_session": MONDAY + timedelta(days=1)}, "CURRENT"),
    ],
)
def test_it_never_starts_when_it_should_not(changes: dict[str, Any], state: str) -> None:
    decision = decide(_facts(**changes))
    assert decision.state == state and not decision.start
    assert decision.message  # always something a person can read


def test_a_folder_the_person_connected_is_explained_not_touched() -> None:
    message = decide(_facts(folder_is_app_data=False)).message
    assert "your own folder" in message and "will not change it" in message


def test_it_waits_an_hour_between_tries_and_says_when() -> None:
    now = _ist(MONDAY, 19)
    soon = decide(_facts(now=now, attempts=1, last_attempt=now - timedelta(minutes=10)))
    assert not soon.start and soon.state == "BEHIND" and soon.retry_at is not None
    assert soon.retry_at == now - timedelta(minutes=10) + RETRY_GAP
    later = decide(_facts(now=now, attempts=1, last_attempt=now - RETRY_GAP))
    assert later.start


def test_it_gives_up_after_three_tries_until_the_next_session() -> None:
    now = _ist(MONDAY, 23)
    done = decide(_facts(now=now, attempts=MAX_ATTEMPTS, last_attempt=now - timedelta(hours=3)))
    assert not done.start and done.state == "BEHIND"
    assert "holiday" in done.message and "next close" in done.message


def test_two_clean_misses_mean_no_newer_session_and_one_is_just_a_note() -> None:
    now = _ist(MONDAY, 21)
    one = decide(_facts(now=now, attempts=1, misses=1, last_attempt=now - timedelta(minutes=5)))
    assert one.state == "BEHIND" and "market holiday" in one.message and not one.start
    two = decide(_facts(now=now, attempts=2, misses=2, last_attempt=now - RETRY_GAP))
    assert two.state == "CURRENT" and not two.start and "up to date, to 2 Oct 2026" in two.message


def test_a_failed_try_is_reported_in_plain_words() -> None:
    now = _ist(MONDAY, 19)
    decision = decide(
        _facts(
            now=now,
            attempts=1,
            last_attempt=now - timedelta(minutes=5),
            last_failure="No stocks could be downloaded: no internet.",
        )
    )
    assert "No stocks could be downloaded" in decision.message


# ----------------------------------------------------------------------------- the worker


class _Download:
    """A stand-in for the real downloader that records what it is asked to do."""

    def __init__(self) -> None:
        self.starts: list[tuple[Path, str]] = []
        self.accept = True
        self.state = "IDLE"
        self.message = ""
        self.run: str | None = None

    def start(self, folder: Path, *, mode: str = "auto") -> bool:
        if not self.accept:
            return False
        self.starts.append((folder, mode))
        self.run = f"run-{len(self.starts)}"
        self.state = "RUNNING"
        return True

    def finish(self, state: str = "DONE") -> None:
        self.state = state

    def snapshot(self) -> dict[str, Any]:
        done = self.state in ("DONE", "ERROR", "CANCELLED")
        return {
            "state": self.state,
            "message": self.message,
            "started_at": self.run,
            "finished_at": "later" if done else None,
        }


class _Index:
    def __init__(self, latest: str | None) -> None:
        self.latest = latest

    def is_ready(self) -> bool:
        return self.latest is not None

    def meta(self) -> dict[str, str]:
        return {"latest_session": self.latest or ""}


class _Job:
    running = False


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _baseline(folder: Path) -> None:
    cache = folder / "evidence" / "market-cache" / "all-market-20260101"
    (cache / "store" / "datasets").mkdir(parents=True)
    (cache / MARKER).write_text("{}", encoding="utf-8")


@pytest.fixture()
def rig(tmp_path: Path) -> Iterator[dict[str, Any]]:
    folder = tmp_path / "data"
    _baseline(folder)
    state = AppState(tmp_path / "state" / "app.sqlite")
    state.update_settings({"data_folder": str(folder)})
    state.create_paper_book("Book", {}, {})
    download, index, clock = _Download(), _Index("2026-10-02"), _Clock(_ist(MONDAY, 19))
    updater = AutoUpdater(
        state=state,
        index=index,  # type: ignore[arg-type]
        job=_Job(),  # type: ignore[arg-type]
        download=download,  # type: ignore[arg-type]
        data_dir=lambda: folder,
        clock=clock,
    )
    yield {
        "updater": updater,
        "download": download,
        "index": index,
        "clock": clock,
        "state": state,
        "folder": folder,
    }


def test_the_worker_starts_one_quick_update_in_the_apps_own_folder(rig: dict[str, Any]) -> None:
    assert rig["updater"].tick().state == "UPDATING"
    assert rig["download"].starts == [(rig["folder"], "update")]
    rig["updater"].tick()  # while it runs, nothing is piled on top
    rig["download"].finish()
    rig["clock"].now += timedelta(minutes=10)  # finished, but the hour between tries has not passed
    rig["updater"].tick()
    assert len(rig["download"].starts) == 1


def test_it_does_nothing_once_the_prices_are_current(rig: dict[str, Any]) -> None:
    rig["index"].latest = "2026-10-05"
    assert rig["updater"].tick().state == "CURRENT"
    assert rig["download"].starts == []


def test_it_retries_after_an_hour_then_stops_after_three(rig: dict[str, Any]) -> None:
    updater, download, clock = rig["updater"], rig["download"], rig["clock"]
    for _ in range(MAX_ATTEMPTS + 2):
        updater.tick()
        download.finish("ERROR")  # every try fails
        clock.now += RETRY_GAP + timedelta(minutes=1)
    assert len(download.starts) == MAX_ATTEMPTS
    assert "tried 3 times" in updater.snapshot()["message"]


def test_the_next_session_starts_with_a_clean_slate(rig: dict[str, Any]) -> None:
    updater, download, clock = rig["updater"], rig["download"], rig["clock"]
    for _ in range(MAX_ATTEMPTS + 1):
        updater.tick()
        download.finish("ERROR")
        clock.now += RETRY_GAP + timedelta(minutes=1)
    assert len(download.starts) == MAX_ATTEMPTS
    clock.now = _ist(date(2026, 10, 6), 19)  # Tuesday evening: a new session is due
    updater.tick()
    assert len(download.starts) == MAX_ATTEMPTS + 1


def test_clean_updates_that_find_nothing_newer_settle_as_a_holiday(rig: dict[str, Any]) -> None:
    """2 Oct 2026 was a market holiday: the data cannot reach that date, and no one did anything wrong."""
    updater, download, clock = rig["updater"], rig["download"], rig["clock"]
    updater.tick()
    download.finish()  # a clean run, and the data is still at 2 Oct's predecessor
    clock.now += RETRY_GAP + timedelta(minutes=1)
    first = updater.snapshot()
    assert first["state"] == "BEHIND" and "market holiday" in first["message"]
    updater.tick()  # the second clean try
    download.finish()
    clock.now += RETRY_GAP + timedelta(minutes=1)
    settled = updater.snapshot()
    assert settled["state"] == "CURRENT" and "no newer trading session" in settled["message"]
    updater.tick()
    assert len(download.starts) == 2  # and it stops asking
    clock.now = _ist(date(2026, 10, 6), 19)  # the next session starts the count again
    updater.tick()
    assert len(download.starts) == 3


def test_a_failed_run_is_not_mistaken_for_a_holiday(rig: dict[str, Any]) -> None:
    updater, download, clock = rig["updater"], rig["download"], rig["clock"]
    for _ in range(2):
        updater.tick()
        download.finish("ERROR")
        clock.now += RETRY_GAP + timedelta(minutes=1)
    assert updater.snapshot()["state"] == "BEHIND"
    updater.tick()
    assert len(download.starts) == 3


def test_a_download_someone_else_started_is_not_counted_as_a_try(rig: dict[str, Any]) -> None:
    rig["download"].accept = False
    rig["updater"].tick()
    assert rig["updater"].snapshot()["attempts"] == 0
    rig["download"].accept = True
    rig["updater"].tick()
    assert len(rig["download"].starts) == 1


def test_it_leaves_alone_data_that_is_not_the_apps_own(rig: dict[str, Any], tmp_path: Path) -> None:
    rig["state"].update_settings({"data_folder": str(tmp_path / "my-research-data")})
    assert rig["updater"].tick().state == "CANNOT"
    assert rig["download"].starts == []


def test_it_does_nothing_when_switched_off(rig: dict[str, Any]) -> None:
    rig["state"].update_settings({"auto_update_paper_books": False})
    assert rig["updater"].tick().state == "OFF"
    assert rig["download"].starts == []


def test_a_stopped_book_does_not_need_updating(rig: dict[str, Any]) -> None:
    book = rig["state"].paper_books()[0]["id"]
    rig["state"].stop_paper_book(book, "2026-10-02")
    assert rig["updater"].tick().state == "IDLE"
    assert rig["download"].starts == []


def test_a_failed_download_is_shown_with_its_reason(rig: dict[str, Any]) -> None:
    rig["updater"].tick()
    rig["download"].finish("ERROR")
    rig["download"].message = "No stocks could be downloaded: no internet."
    rig["clock"].now += timedelta(minutes=5)
    snap = rig["updater"].snapshot()
    assert snap["state"] == "BEHIND" and "no internet" in snap["message"]
    assert snap["latest_session"] == "2026-10-02" and snap["expected_session"] == "2026-10-05"


def test_the_worker_thread_starts_and_stops(rig: dict[str, Any]) -> None:
    updater = rig["updater"]
    updater.start()
    assert updater._thread is not None and updater._thread.is_alive()
    updater.start()  # starting twice does not make two workers
    updater.stop()
    assert not updater._thread.is_alive()


# ------------------------------------------------------------------------------------ API


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("QUANTOS_APP_ROOT", str(tmp_path / "app"))
    monkeypatch.setattr(paths, "fixed_drive_roots", lambda: [])
    monkeypatch.setattr(paths, "_user_folders", lambda: [])
    monkeypatch.setattr(paths, "data_scan", paths.DataFolderScan())
    router.reset_services()
    with TestClient(app, base_url="http://localhost:8000") as test_client:
        yield test_client
    router.reset_services()


def test_the_server_runs_the_worker_only_while_it_is_up(client: TestClient) -> None:
    worker = router.services().auto._thread
    assert worker is not None and worker.is_alive()
    thread = worker
    router.reset_services()
    assert not thread.is_alive()


def test_the_paper_page_can_ask_what_the_updater_is_doing(client: TestClient) -> None:
    body = client.get("/api/v2/paper/updates").json()
    assert body["enabled"] is True and body["state"] == "IDLE"
    assert set(body) >= {"message", "latest_session", "expected_session", "attempts", "next_try"}


def test_the_switch_is_a_setting_and_defaults_on(client: TestClient) -> None:
    assert client.get("/api/v2/settings").json()["auto_update_paper_books"] is True
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    off = client.put(
        "/api/v2/settings", json={"auto_update_paper_books": False}, headers={"X-CSRF-Token": token}
    )
    assert off.status_code == 200 and off.json()["auto_update_paper_books"] is False
    assert client.get("/api/v2/paper/updates").json()["state"] == "OFF"
