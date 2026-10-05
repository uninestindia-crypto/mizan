"""The cloud entry point for the paper session: token handling, close time, and state.

`scripts/cloud_paper_session.py` wraps `run_scheduled_paper_session._run` for a host with no scheduler and
no disk that outlives the job. The wrapper adds four properties, and each one is a way an unattended cloud
run can go wrong silently, so each has a test here:

* **The token is never shown.** It is a credential for a real account. Every line the wrapper prints goes
  through `redact`, including provider error text that echoes what it was sent.
* **No token fails closed.** Nothing is fetched, restored or run, and the exit code says why.
* **The close time honours the host.** A GitHub-hosted job dies at six hours, mid-order. The session ends
  early on purpose, and says so.
* **State survives the job, including a failed one.** A fresh cloud checkout has no `logs/paper_runs`, so
  without a copy out the book would restart from cash every morning. A session that dies halfway leaves
  state that is evidence, so it is saved on the way out of a failure too.

Everything here uses fakes for the quote feed and the session. Nothing touches the network, a broker or
either laptop book.
"""

from __future__ import annotations

import os
import sys
import types
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import cloud_paper_session as cloud  # noqa: E402
import run_scheduled_paper_session as scheduled  # noqa: E402

TOKEN = "eyJ-this-is-a-fake-test-credential-0123456789"
MONDAY_0900_IST = datetime(2026, 8, 31, 9, 0, tzinfo=cloud.IST)
SATURDAY_1000_IST = datetime(2026, 8, 29, 10, 0, tzinfo=cloud.IST)


class _QuoteFeedError(RuntimeError):
    """Stands in for `run_paper_pilot_session.QuoteFeedError`."""


def _fake_pilot(
    *,
    unusable: str | None = None,
    feed_error: str | None = None,
    quotes: dict[str, dict[str, Any]] | None = None,
) -> types.SimpleNamespace:
    def assert_upstox_usable() -> None:
        if unusable is not None:
            raise _QuoteFeedError(unusable)

    def fetch_upstox_live_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
        if feed_error is not None:
            raise _QuoteFeedError(feed_error)
        return quotes if quotes is not None else {s: {"price": "100.00"} for s in symbols}

    return types.SimpleNamespace(
        QuoteFeedError=_QuoteFeedError,
        assert_upstox_usable=assert_upstox_usable,
        fetch_upstox_live_quotes=fetch_upstox_live_quotes,
    )


@pytest.fixture
def no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in cloud.TOKEN_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def with_token(monkeypatch: pytest.MonkeyPatch, no_token: None) -> None:
    monkeypatch.setenv(cloud.TOKEN_VARIABLES[0], TOKEN)


@pytest.fixture
def pilot_must_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any use of the quote feed fails the test: it proves a run stopped before fetching."""

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the quote feed was used")

    monkeypatch.setitem(
        sys.modules,
        "run_paper_pilot_session",
        types.SimpleNamespace(
            QuoteFeedError=_QuoteFeedError,
            assert_upstox_usable=forbidden,
            fetch_upstox_live_quotes=forbidden,
        ),
    )


def _freeze_clock(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return moment.astimezone(tz) if tz is not None else moment

    monkeypatch.setattr(cloud, "datetime", _Frozen)


@pytest.fixture
def state_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    folder = tmp_path / "logs" / "paper_runs"
    monkeypatch.setattr(cloud, "STATE_FOLDER", folder)
    return folder


# --------------------------------------------------------------------------------------------------
# The token is never printed
# --------------------------------------------------------------------------------------------------


def test_redact_replaces_every_configured_token_value() -> None:
    environ = {"UPSTOX_ANALYTICS_TOKEN": TOKEN, "UPSTOX_ACCESS_TOKEN": "second-fake-token-value"}
    text = f"first {TOKEN} and second second-fake-token-value end"
    assert cloud.redact(text, environ) == "first [token] and second [token] end"


def test_log_redacts_a_token_that_reaches_it(
    with_token: None, capsys: pytest.CaptureFixture[str]
) -> None:
    cloud.log(f"the provider said: bad credential {TOKEN}")
    printed = capsys.readouterr().out
    assert TOKEN not in printed
    assert "[token]" in printed


def test_a_provider_error_that_echoes_the_token_is_not_printed(
    with_token: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The feed's own error text is the likeliest leak: some providers echo the credential back."""
    monkeypatch.setitem(
        sys.modules,
        "run_paper_pilot_session",
        _fake_pilot(feed_error=f"HTTP Error 401: Unauthorized for Bearer {TOKEN}"),
    )
    code = cloud.check_token()
    captured = capsys.readouterr()
    assert code == cloud.EXIT_TOKEN_REJECTED
    assert TOKEN not in captured.out + captured.err
    assert "[token]" in captured.out


def test_a_successful_check_names_the_variable_but_not_its_value(
    with_token: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "run_paper_pilot_session", _fake_pilot())
    code = cloud.check_token()
    printed = capsys.readouterr().out
    assert code == 0
    assert "UPSTOX_ANALYTICS_TOKEN" in printed
    assert "value not shown" in printed
    assert TOKEN not in printed


def test_only_the_two_named_variables_are_read() -> None:
    assert cloud.configured_token_variable({"SOME_OTHER_TOKEN": TOKEN, "TOKEN": TOKEN}) is None
    assert cloud.configured_token_variable({"UPSTOX_ACCESS_TOKEN": TOKEN}) == "UPSTOX_ACCESS_TOKEN"
    assert (
        cloud.configured_token_variable(
            {"UPSTOX_ANALYTICS_TOKEN": TOKEN, "UPSTOX_ACCESS_TOKEN": "x"}
        )
        == "UPSTOX_ANALYTICS_TOKEN"
    )


def test_a_blank_token_counts_as_no_token() -> None:
    assert cloud.configured_token_variable({"UPSTOX_ANALYTICS_TOKEN": "   "}) is None


# --------------------------------------------------------------------------------------------------
# No token, or a bad one, fails closed before anything is fetched
# --------------------------------------------------------------------------------------------------


def test_check_with_no_token_exits_10_without_touching_the_feed(
    no_token: None, pilot_must_not_run: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cloud.main(["check"]) == cloud.EXIT_NO_TOKEN == 10
    assert "no token" in capsys.readouterr().out


def test_run_with_no_token_exits_10_and_runs_no_session(
    no_token: None,
    pilot_must_not_run: None,
    state_folder: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def session_must_not_run(_namespace: object) -> int:
        raise AssertionError("the session ran without a token")

    monkeypatch.setattr(scheduled, "_run", session_must_not_run)
    saved = tmp_path / "state"
    assert cloud.main(["run", "--state-dir", str(saved)]) == cloud.EXIT_NO_TOKEN
    assert not saved.exists()


def test_no_token_is_refused_before_the_calendar_is_consulted(
    no_token: None, pilot_must_not_run: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a Saturday with no token the answer is 10, not 12: the credential is the first refusal."""
    _freeze_clock(monkeypatch, SATURDAY_1000_IST)

    def calendar_must_not_be_read(_day: object) -> None:
        raise AssertionError("the trading calendar was read before the token was checked")

    monkeypatch.setattr(scheduled, "require_trading_day", calendar_must_not_be_read)
    assert cloud.main(["run"]) == cloud.EXIT_NO_TOKEN


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"unusable": "UPSTOX_ANALYTICS_TOKEN expired at 2026-08-23 03:30 IST"}, 11),
        (
            {
                "feed_error": "1 of 1 quote batches failed. First error: HTTP Error 401: Unauthorized"
            },
            11,
        ),
        ({"feed_error": "1 of 1 quote batches failed. First error: HTTP Error 403: Forbidden"}, 11),
        ({"feed_error": "1 of 1 quote batches failed. First error: <urlopen error timed out>"}, 13),
        ({"feed_error": "Upstox returned no quotes for any of 3 symbols"}, 13),
    ],
)
def test_check_classifies_a_failure_by_whose_fault_it_is(
    with_token: None, monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, str], expected: int
) -> None:
    monkeypatch.setitem(sys.modules, "run_paper_pilot_session", _fake_pilot(**kwargs))
    assert cloud.check_token() == expected


def test_a_rejected_token_stops_run_before_state_is_restored_or_a_session_starts(
    with_token: None,
    state_folder: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        sys.modules, "run_paper_pilot_session", _fake_pilot(unusable="token expired")
    )
    _freeze_clock(monkeypatch, MONDAY_0900_IST)
    monkeypatch.setattr(scheduled, "require_trading_day", lambda _day: None)

    def session_must_not_run(_namespace: object) -> int:
        raise AssertionError("the session ran on a rejected token")

    monkeypatch.setattr(scheduled, "_run", session_must_not_run)
    saved = tmp_path / "state"
    saved.mkdir()
    (saved / "portfolio_state.json").write_text("{}", encoding="utf-8")
    assert cloud.main(["run", "--state-dir", str(saved)]) == cloud.EXIT_TOKEN_REJECTED
    assert not state_folder.exists()


# --------------------------------------------------------------------------------------------------
# Not a trading day
# --------------------------------------------------------------------------------------------------


def test_a_weekend_exits_12_before_the_token_is_used_or_a_session_starts(
    with_token: None,
    pilot_must_not_run: None,
    state_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Uses the real NSE calendar, so a closed day is refused by the same rule the laptop uses."""
    _freeze_clock(monkeypatch, SATURDAY_1000_IST)

    def session_must_not_run(_namespace: object) -> int:
        raise AssertionError("the session ran on a Saturday")

    monkeypatch.setattr(scheduled, "_run", session_must_not_run)
    assert cloud.main(["run"]) == cloud.EXIT_NOT_A_TRADING_DAY == 12
    assert "does not trade at weekends" in capsys.readouterr().out
    assert not state_folder.exists()


def test_a_holiday_exits_12(
    with_token: None, pilot_must_not_run: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_clock(monkeypatch, MONDAY_0900_IST)

    def holiday(_day: object) -> None:
        raise scheduled.NotATradingDay("2026-08-31 Monday is an NSE trading holiday: test")

    monkeypatch.setattr(scheduled, "require_trading_day", holiday)
    assert cloud.main(["run"]) == cloud.EXIT_NOT_A_TRADING_DAY


# --------------------------------------------------------------------------------------------------
# The close time
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "limit", "expected", "truncated"),
    [
        (MONDAY_0900_IST, None, time(15, 30), False),
        (MONDAY_0900_IST, 340, time(14, 20), True),
        (MONDAY_0900_IST.replace(minute=10, second=45), 360, time(14, 50), True),
        (MONDAY_0900_IST, 600, time(15, 30), False),
        (datetime(2026, 8, 31, 3, 30, tzinfo=UTC), 340, time(14, 20), True),
    ],
    ids=["no-limit", "six-hour-host", "rounds-down-to-the-minute", "limit-past-close", "utc-input"],
)
def test_session_end_time(
    now: datetime, limit: int | None, expected: time, truncated: bool
) -> None:
    assert cloud.session_end_time(now, max_runtime_minutes=limit) == (expected, truncated)


def test_a_limited_host_closes_the_session_early_and_says_so(
    with_token: None,
    state_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setitem(sys.modules, "run_paper_pilot_session", _fake_pilot())
    _freeze_clock(monkeypatch, MONDAY_0900_IST)
    handed_over: list[Any] = []

    def session(namespace: Any) -> int:
        handed_over.append(namespace)
        return 0

    monkeypatch.setattr(scheduled, "_run", session)
    assert cloud.main(["run", "--max-runtime-minutes", "340"]) == 0
    assert handed_over[0].end_time_ist == "14:20:00"
    printed = capsys.readouterr().out
    assert "NOTICE" in printed
    assert "14:20 IST, earlier than 15:30" in printed


def test_an_unlimited_host_runs_to_the_close_without_a_notice(
    with_token: None,
    state_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setitem(sys.modules, "run_paper_pilot_session", _fake_pilot())
    _freeze_clock(monkeypatch, MONDAY_0900_IST)
    handed_over: list[Any] = []

    def session(namespace: Any) -> int:
        handed_over.append(namespace)
        return 0

    monkeypatch.setattr(scheduled, "_run", session)
    assert cloud.main(["run"]) == 0
    assert handed_over[0].end_time_ist == "15:30:00"
    assert "NOTICE" not in capsys.readouterr().out


# --------------------------------------------------------------------------------------------------
# State outlives the job
# --------------------------------------------------------------------------------------------------


def _arrange_session(
    monkeypatch: pytest.MonkeyPatch, state_folder: Path, *, code: int = 0, fail: bool = False
) -> list[str]:
    """A session that reads the restored state, writes new state, then returns or fails."""
    monkeypatch.setitem(sys.modules, "run_paper_pilot_session", _fake_pilot())
    _freeze_clock(monkeypatch, MONDAY_0900_IST)
    seen_at_start: list[str] = []

    def session(_namespace: object) -> int:
        existing = state_folder / "portfolio_state.json"
        seen_at_start.append(existing.read_text(encoding="utf-8") if existing.exists() else "")
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text('{"after": true}', encoding="utf-8")
        (state_folder / "reports" / "today.md").parent.mkdir(parents=True, exist_ok=True)
        (state_folder / "reports" / "today.md").write_text("report", encoding="utf-8")
        if fail:
            raise RuntimeError("the session died halfway")
        return code

    monkeypatch.setattr(scheduled, "_run", session)
    return seen_at_start


def test_state_is_restored_before_the_session_and_saved_after_it(
    with_token: None, state_folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = tmp_path / "state"
    saved.mkdir()
    (saved / "portfolio_state.json").write_text('{"before": true}', encoding="utf-8")
    seen = _arrange_session(monkeypatch, state_folder)

    assert cloud.main(["run", "--state-dir", str(saved)]) == 0

    assert seen == ['{"before": true}']
    assert (saved / "portfolio_state.json").read_text(encoding="utf-8") == '{"after": true}'
    assert (saved / "reports" / "today.md").read_text(encoding="utf-8") == "report"


def test_state_is_saved_even_when_the_session_raises(
    with_token: None, state_folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A half-finished session's state is evidence. Losing it with the job is the failure."""
    saved = tmp_path / "state"
    _arrange_session(monkeypatch, state_folder, fail=True)

    with pytest.raises(RuntimeError, match="died halfway"):
        cloud.main(["run", "--state-dir", str(saved)])

    assert (saved / "portfolio_state.json").read_text(encoding="utf-8") == '{"after": true}'
    assert (saved / "reports" / "today.md").is_file()


def test_state_is_saved_when_the_session_exits_non_zero_and_the_code_is_passed_through(
    with_token: None, state_folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = tmp_path / "state"
    _arrange_session(monkeypatch, state_folder, code=11)

    assert cloud.main(["run", "--state-dir", str(saved)]) == 11

    assert (saved / "portfolio_state.json").is_file()


def test_without_a_state_dir_nothing_is_copied(
    with_token: None, state_folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _arrange_session(monkeypatch, state_folder)
    assert cloud.main(["run"]) == 0
    assert (state_folder / "portfolio_state.json").is_file()
    assert not (tmp_path / "state").exists()


# --------------------------------------------------------------------------------------------------
# sync_tree copies plain files and nothing else
# --------------------------------------------------------------------------------------------------


def test_sync_tree_copies_nested_files_and_counts_them(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "a" / "b").mkdir(parents=True)
    (source / "top.json").write_text("1", encoding="utf-8")
    (source / "a" / "b" / "deep.md").write_text("2", encoding="utf-8")

    copied = cloud.sync_tree(source, tmp_path / "destination")

    assert copied == 2
    assert (tmp_path / "destination" / "top.json").read_text(encoding="utf-8") == "1"
    assert (tmp_path / "destination" / "a" / "b" / "deep.md").read_text(encoding="utf-8") == "2"


def test_sync_tree_of_a_missing_source_copies_nothing(tmp_path: Path) -> None:
    assert cloud.sync_tree(tmp_path / "absent", tmp_path / "destination") == 0
    assert not (tmp_path / "destination").exists()


def test_sync_tree_skips_a_linked_file(tmp_path: Path) -> None:
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("must not be copied", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    (source / "real.json").write_text("ok", encoding="utf-8")
    link = source / "link.json"
    try:
        os.symlink(outside, link)
    except OSError as error:
        # test-allow: skipped-test - the account cannot create symlinks (WinError 1314); CI can
        pytest.skip(f"cannot create a symlink on this machine: {error}")

    copied = cloud.sync_tree(source, tmp_path / "destination")

    assert copied == 1
    assert not (tmp_path / "destination" / "link.json").exists()
    assert (tmp_path / "destination" / "real.json").is_file()


def test_sync_tree_does_not_descend_a_linked_folder(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("must not be copied", encoding="utf-8")
    source = tmp_path / "source"
    source.mkdir()
    (source / "real.json").write_text("ok", encoding="utf-8")
    try:
        os.symlink(outside, source / "linked-folder", target_is_directory=True)
    except OSError as error:
        # test-allow: skipped-test - the account cannot create symlinks (WinError 1314); CI can
        pytest.skip(f"cannot create a symlink on this machine: {error}")

    copied = cloud.sync_tree(source, tmp_path / "destination")

    assert copied == 1
    assert not (tmp_path / "destination" / "linked-folder").exists()


def test_sync_tree_will_not_write_through_a_link_in_the_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "state.json").write_text("new", encoding="utf-8")
    victim = tmp_path / "victim.txt"
    victim.write_text("original", encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()
    try:
        os.symlink(victim, destination / "state.json")
    except OSError as error:
        # test-allow: skipped-test - the account cannot create symlinks (WinError 1314); CI can
        pytest.skip(f"cannot create a symlink on this machine: {error}")

    copied = cloud.sync_tree(source, destination)

    assert copied == 0
    assert victim.read_text(encoding="utf-8") == "original"


# --------------------------------------------------------------------------------------------------
# The repository never receives the token, even through state
# --------------------------------------------------------------------------------------------------


def test_save_state_copies_the_book_out(
    state_folder: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_folder.mkdir(parents=True)
    (state_folder / "portfolio_state.json").write_text('{"cash": 1}', encoding="utf-8")
    saved = tmp_path / "state"

    assert cloud.main(["save-state", "--state-dir", str(saved)]) == 0

    assert (saved / "portfolio_state.json").read_text(encoding="utf-8") == '{"cash": 1}'
    assert "saved 1 state file(s)" in capsys.readouterr().out


def test_save_state_refuses_when_a_state_file_holds_the_token(
    with_token: None,
    state_folder: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_folder.mkdir(parents=True)
    (state_folder / "portfolio_state.json").write_text('{"cash": 1}', encoding="utf-8")
    (state_folder / "debug.log").write_text(f"Authorization: Bearer {TOKEN}", encoding="utf-8")
    saved = tmp_path / "state"

    assert cloud.main(["save-state", "--state-dir", str(saved)]) == cloud.EXIT_TOKEN_IN_STATE == 14

    printed = capsys.readouterr().out
    assert "debug.log" in printed
    assert TOKEN not in printed
    assert not saved.exists()


def test_run_reports_a_token_in_state_even_when_the_session_succeeded(
    with_token: None, state_folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "run_paper_pilot_session", _fake_pilot())
    _freeze_clock(monkeypatch, MONDAY_0900_IST)

    def session(_namespace: object) -> int:
        state_folder.mkdir(parents=True, exist_ok=True)
        (state_folder / "trace.txt").write_text(TOKEN, encoding="utf-8")
        return 0

    monkeypatch.setattr(scheduled, "_run", session)
    saved = tmp_path / "state"

    assert cloud.main(["run", "--state-dir", str(saved)]) == cloud.EXIT_TOKEN_IN_STATE
    assert not saved.exists()


def test_files_containing_token_finds_nested_files_and_ignores_the_rest(
    tmp_path: Path,
) -> None:
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "hit.txt").write_text(f"x {TOKEN} y", encoding="utf-8")
    (tmp_path / "clean.txt").write_text("nothing here", encoding="utf-8")
    environ = {"UPSTOX_ANALYTICS_TOKEN": TOKEN}

    assert cloud.files_containing_token(tmp_path, environ) == [tmp_path / "a" / "b" / "hit.txt"]
    assert cloud.files_containing_token(tmp_path, {}) == []
