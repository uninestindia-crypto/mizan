"""Updating an AI app: it uses the app's own update, says what really happened, and never claims a change it did not see."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quant_system.server.app import app
from quant_system.server.v2 import cli_bridge, cli_models


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_bridge, "_jobs", {})
    monkeypatch.setattr(cli_bridge, "invalidate_cache", lambda: None)
    monkeypatch.setattr(cli_models, "clear_cache", lambda: None)


def _wait(agent_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = cli_bridge.job_snapshot(agent_id)
        assert snapshot is not None
        if snapshot["state"] != "RUNNING":
            return snapshot
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def _versions(monkeypatch: pytest.MonkeyPatch, *seen: str) -> None:
    """The version the app reports each time it is asked, in order (the last one repeats)."""
    queue = list(seen)

    def run_hidden(args: list[str], **kwargs: Any) -> tuple[int, str]:
        return 0, (queue.pop(0) if len(queue) > 1 else queue[0]) + "\n"

    monkeypatch.setattr(cli_bridge, "_run_hidden", run_hidden)


def _streams(monkeypatch: pytest.MonkeyPatch, *, code: int = 0) -> list[list[str]]:
    ran: list[list[str]] = []

    def stream(job: Any, args: list[str], timeout: float) -> int:
        ran.append(args)
        return code

    monkeypatch.setattr(cli_bridge, "_stream", stream)
    return ran


def test_the_apps_own_update_is_used_and_the_new_version_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_bridge, "_find", lambda command: f"C:\\{command}.exe")
    _versions(monkeypatch, "codex-cli 0.162.1", "codex-cli 0.170.0")
    ran = _streams(monkeypatch)
    cli_bridge.start_agent_job("codex", "update")
    done = _wait("codex")
    assert ran == [["C:\\codex.exe", "update"]]  # no installer was run
    assert done["state"] == "DONE" and done["before"] == "codex-cli 0.162.1"
    assert done["message"] == "Codex was updated from version 0.162.1 to 0.170.0."
    assert done["after"] == "codex-cli 0.170.0"


def test_an_app_that_is_already_current_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_bridge, "_find", lambda command: f"C:\\{command}.exe")
    _versions(monkeypatch, "2.1.296 (Claude Code)")
    _streams(monkeypatch)
    cli_bridge.start_agent_job("claude", "update")
    done = _wait("claude")
    assert done["state"] == "DONE"
    assert done["message"] == "Claude Code is already up to date (version 2.1.296)."


def test_when_the_apps_own_update_fails_the_installer_is_tried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_bridge, "_find", lambda command: f"C:\\{command}.exe")
    _versions(monkeypatch, "1.0.0", "1.1.0")
    ran: list[list[str]] = []

    def stream(job: Any, args: list[str], timeout: float) -> int:
        ran.append(args)
        return (
            1 if args[0] != "powershell.exe" else 0
        )  # the app's update fails, the installer works

    monkeypatch.setattr(cli_bridge, "_stream", stream)
    cli_bridge.start_agent_job("claude", "update")
    done = _wait("claude")
    assert ran[0] == ["C:\\claude.exe", "update"]
    assert ran[1][0] == "powershell.exe" and "install.ps1" in ran[1][-1]
    assert done["state"] == "DONE" and "from version 1.0.0 to 1.1.0" in done["message"]


def test_a_failed_update_is_reported_failed_with_a_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_bridge, "_find", lambda command: f"C:\\{command}.exe")
    _versions(monkeypatch, "1.0.0")
    _streams(monkeypatch, code=1)
    cli_bridge.start_agent_job("codex", "update")
    done = _wait("codex")
    assert done["state"] == "FAILED" and "did not finish" in done["message"]


def test_a_company_app_with_no_update_step_is_not_called_updated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet = replace(
        cli_bridge.SUPPORTED_AGENTS[0],
        id="acme",
        name="Acme",
        update=(),
        install=(),
        update_command=(),
    )
    monkeypatch.setattr(cli_bridge, "get_agent", lambda agent_id: quiet)
    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\acme.exe")
    _versions(monkeypatch, "1.0")
    _streams(monkeypatch)
    cli_bridge.start_agent_job("acme", "update")
    done = _wait("acme")
    assert done["state"] == "FAILED" and done["message"] == "There is no way to update Acme yet."


def test_a_click_while_another_step_runs_says_what_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\codex.cmd")
    monkeypatch.setattr(cli_bridge, "_check_auth_status", lambda agent, exe: (True, "Signed in"))
    monkeypatch.setattr(cli_bridge, "_stream", lambda job, args, timeout: release.wait(5) and 0)
    first = cli_bridge.start_agent_job("codex", "signin")
    second = cli_bridge.start_agent_job("codex", "update")
    assert first["joined"] is False and second["joined"] is True
    assert second["action"] == "signin" and second["job"]["id"] == first["job"]["id"]
    assert second["message"] == "Codex is busy signing in. Try again when it has finished."
    release.set()
    _wait("codex")


def test_the_same_click_twice_joins_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    release = threading.Event()
    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\codex.cmd")
    monkeypatch.setattr(cli_bridge, "_stream", lambda job, args, timeout: release.wait(5) and 0)
    _versions(monkeypatch, "1.0.0")
    first = cli_bridge.start_agent_job("codex", "update")
    second = cli_bridge.start_agent_job("codex", "update")
    assert second["joined"] is True and second["message"] == second["job"]["message"]
    assert first["job"]["id"] == second["job"]["id"]
    release.set()
    _wait("codex")


def test_a_finished_job_says_how_long_ago_it_ended(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_bridge, "_find", lambda command: "C:\\codex.cmd")
    _versions(monkeypatch, "1.0.0")
    _streams(monkeypatch)
    cli_bridge.start_agent_job("codex", "update")
    _wait("codex")
    time.sleep(0.05)
    snapshot = cli_bridge.job_snapshot("codex")
    assert snapshot is not None and snapshot["ended_seconds_ago"] is not None
    assert snapshot["ended_seconds_ago"] >= 0


# ---------------------------------------------------------------------------------- the automatic update


def test_the_auto_update_box_needs_an_object_not_a_bare_true() -> None:
    client = TestClient(app, base_url="http://localhost:8000")
    token = client.get("/api/v1/csrf-token").json()["csrf_token"]
    headers = {"X-CSRF-Token": token}
    assert client.post("/api/v2/cli/auto-update", json=True, headers=headers).status_code == 422
    ok = client.post("/api/v2/cli/auto-update", json={"enabled": False}, headers=headers)
    assert ok.status_code == 200 and ok.json()["auto_update_cli"] is False


def test_automatic_updates_cover_company_apps_only_if_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acme = replace(cli_bridge.SUPPORTED_AGENTS[0], id="acme", name="Acme")
    other = replace(cli_bridge.SUPPORTED_AGENTS[0], id="other", name="Other")
    monkeypatch.setattr(
        cli_bridge, "all_agents", lambda: (*cli_bridge.SUPPORTED_AGENTS, acme, other)
    )
    monkeypatch.setattr(
        cli_bridge, "_custom_auto_update_flags", lambda: {"acme": True, "other": False}
    )
    monkeypatch.setattr(cli_bridge, "_program", lambda agent: f"C:\\{agent.id}.exe")
    started: list[str] = []

    def start(agent_id: str, action: str) -> dict[str, Any]:
        started.append(agent_id)
        return {}

    monkeypatch.setattr(cli_bridge, "start_agent_job", start)
    cli_bridge.auto_update_all_clis()
    assert started == ["antigravity", "codex", "claude", "acme"]
    started.clear()
    cli_bridge.auto_update_all_clis(include_built_in=False)  # the box is off, one company app asked
    assert started == ["acme"]


def test_the_daily_updater_runs_only_while_the_box_is_on_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    def update_all(*, include_built_in: bool = True) -> list[dict[str, Any]]:
        calls.append(include_built_in)
        return []

    monkeypatch.setattr(cli_bridge, "auto_update_all_clis", update_all)
    stop = cli_bridge.start_cli_auto_updates(lambda: True, first_delay=0.01, interval=0.02)
    deadline = time.monotonic() + 5
    while len(calls) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    stop()
    seen = len(calls)
    time.sleep(0.1)
    assert seen >= 2 and all(calls) and len(calls) <= seen + 1


@pytest.mark.skipif(sys.platform != "win32", reason="the whole-tree stop is a Windows command")
def test_a_stuck_update_is_stopped_with_everything_it_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran: list[list[str]] = []

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        ran.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", run)

    class Fake:
        pid = 4242

        def kill(self) -> None:  # pragma: no cover - must not be needed
            raise AssertionError("a plain kill leaves the installer's children running")

    cli_bridge._kill_tree(Fake())  # type: ignore[arg-type]
    assert ran == [["taskkill", "/PID", "4242", "/T", "/F"]]


@pytest.mark.skipif(sys.platform != "win32", reason="the stand-in program is a Windows batch file")
def test_a_real_program_is_updated_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """No fakes inside the bridge: a stand-in program answers ``--version`` and ``update`` as a real app would."""
    (tmp_path / "version.txt").write_text("1.0.0\n", encoding="utf-8")
    (tmp_path / "fakeapp.cmd").write_text(
        "@echo off\r\n"
        'if "%1"=="--version" (type "%~dp0version.txt" & exit /b 0)\r\n'
        'if "%1"=="update" (echo Downloading... & echo 2.0.0> "%~dp0version.txt" & exit /b 0)\r\n'
        "exit /b 1\r\n",
        encoding="ascii",
    )
    fake = replace(
        cli_bridge.SUPPORTED_AGENTS[1],
        id="fakeapp",
        name="Fake App",
        commands=("fakeapp",),
        extra_dirs=(str(tmp_path),),
    )
    monkeypatch.setattr(cli_bridge, "all_agents", lambda: (*cli_bridge.SUPPORTED_AGENTS, fake))
    monkeypatch.setattr(
        cli_bridge, "get_agent", lambda agent_id: fake if agent_id == "fakeapp" else None
    )
    cli_bridge.start_agent_job("fakeapp", "update")
    done = _wait("fakeapp")
    assert done["state"] == "DONE", done
    assert done["message"] == "Fake App was updated from version 1.0.0 to 2.0.0."
    assert "Downloading..." in done["output"]
    cli_bridge.start_agent_job("fakeapp", "update")  # nothing newer now
    assert _wait("fakeapp")["message"] == "Fake App is already up to date (version 2.0.0)."
