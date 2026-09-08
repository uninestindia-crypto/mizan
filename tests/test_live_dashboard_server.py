"""The dashboard must answer a second request while a first one is still open.

Filed against the 2026-09-01 observation: the process was alive, the port was listening, and the
page was dead. `socketserver.TCPServer` serves exactly one request at a time, so a browser holding
a connection open blocks everyone behind it -- including the founder trying to halt a session from
that page.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from scripts.serve_live_dashboard import build_dashboard_server

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def running_dashboard():
    """A real bound server on an OS-chosen port, serving in a background thread."""
    server = build_dashboard_server(port=0, host="127.0.0.1")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_the_dashboard_answers_while_another_client_holds_a_connection_open(
    running_dashboard,
) -> None:
    port = running_dashboard

    # A client that connects, sends a partial request, and never finishes it. This is the browser
    # tab left open on the page, reduced to its essentials.
    stalled = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        stalled.sendall(b"GET /api/status HTTP/1.1\r\nHost: localhost\r\n")

        # Under the single-threaded server this call never returns and the test times out.
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=5) as response:
            assert response.status == 200
    finally:
        stalled.close()


def test_the_dashboard_still_answers_after_a_stalled_client_disappears(
    running_dashboard,
) -> None:
    """A dropped connection must not take the handler thread down with it."""
    port = running_dashboard

    abandoned = socket.create_connection(("127.0.0.1", port), timeout=5)
    abandoned.sendall(b"GET /api/status HTTP/1.1\r\n")
    abandoned.close()

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=5) as response:
        assert response.status == 200


def test_the_dashboard_answers_xs_status(running_dashboard) -> None:
    """The dashboard must serve XS monthly status for the multi-model dashboard view."""
    port = running_dashboard
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/xs_status", timeout=5) as response:
        assert response.status == 200
        assert "application/json" in response.headers.get("Content-Type", "")


def test_the_dashboard_binds_loopback_only(running_dashboard) -> None:
    """The page carries an access-token field and Start/Halt controls."""
    port = running_dashboard
    with pytest.raises((urllib.error.URLError, OSError, TimeoutError)):
        # A non-loopback local address must not reach it.
        with socket.create_connection((_a_non_loopback_address(), port), timeout=2):
            pass


def _a_non_loopback_address() -> str:
    """This machine's LAN address, or a value guaranteed to refuse, when there is none."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))  # TEST-NET-1; no packet is actually sent
        address = probe.getsockname()[0]
    except OSError:  # pragma: no cover - a machine with no routable interface
        address = "192.0.2.1"
    finally:
        probe.close()
    return address if not address.startswith("127.") else "192.0.2.1"


def test_importing_the_dashboard_does_not_put_credentials_in_the_environment(tmp_path) -> None:
    """Importing a module must not be how a secret enters a process.

    The `.env` read ran at module scope, so `import scripts.serve_live_dashboard` wrote the real
    Upstox access token into `os.environ`. Seven tests asserting behaviour *without* a token failed
    as soon as anything imported this file. The value is never printed here; only its absence is
    asserted.
    """
    env = dict(os.environ)
    env.pop("UPSTOX_ACCESS_TOKEN", None)
    env["PYTHONPATH"] = os.pathsep.join([str(_REPO_ROOT), str(_REPO_ROOT / "src")])

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, scripts.serve_live_dashboard as d; "
            "print('PRESENT' if os.environ.get('UPSTOX_ACCESS_TOKEN') else 'ABSENT'); "
            "print('LOADER' if callable(d.load_env_file) else 'NO_LOADER')",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
        timeout=120,
    )

    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.split() == ["ABSENT", "LOADER"]


def test_the_env_file_still_reaches_the_environment_when_the_entry_point_asks(
    tmp_path, monkeypatch
) -> None:
    """Moving the load must not have removed it: the real launcher still needs the token."""
    from scripts import serve_live_dashboard

    env_file = tmp_path / ".env"
    env_file.write_text("QUANTOS_TEST_ONLY_KEY=a-value\n", encoding="utf-8")
    monkeypatch.setattr(serve_live_dashboard, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("QUANTOS_TEST_ONLY_KEY", raising=False)

    serve_live_dashboard.load_env_file()

    assert os.environ["QUANTOS_TEST_ONLY_KEY"] == "a-value"


def test_the_env_file_never_overwrites_a_value_already_set(tmp_path, monkeypatch) -> None:
    """A token passed on the command line must beat a stale one on disk."""
    from scripts import serve_live_dashboard

    env_file = tmp_path / ".env"
    env_file.write_text("QUANTOS_TEST_ONLY_KEY=from-disk\n", encoding="utf-8")
    monkeypatch.setattr(serve_live_dashboard, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("QUANTOS_TEST_ONLY_KEY", "from-the-caller")

    serve_live_dashboard.load_env_file()

    assert os.environ["QUANTOS_TEST_ONLY_KEY"] == "from-the-caller"


_SECRET = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.not-a-real-token.signature"


def test_the_token_never_reaches_the_child_command_line(monkeypatch) -> None:
    """argv is readable from the process table by any local process, all session long."""
    from scripts.serve_live_dashboard import build_pilot_launch

    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    cmd, _ = build_pilot_launch({"upstox_token": _SECRET})

    assert _SECRET not in " ".join(cmd)
    assert "--upstox-token" not in cmd


def test_the_log_line_the_dashboard_writes_carries_no_token(monkeypatch) -> None:
    """The whole bearer token was written to stderr, and to a file under redirection."""
    from scripts.serve_live_dashboard import build_pilot_launch

    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    cmd, _ = build_pilot_launch({"upstox_token": _SECRET})

    # Exactly what `logger.info("Starting background paper pilot: %s", " ".join(cmd))` emits.
    logged = "Starting background paper pilot: {}".format(" ".join(cmd))
    assert _SECRET not in logged


def test_the_token_still_reaches_the_child_that_needs_it(monkeypatch) -> None:
    """Removing the leak must not remove the credential: the session cannot run without it."""
    from scripts.serve_live_dashboard import build_pilot_launch

    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    _, child_env = build_pilot_launch({"upstox_token": _SECRET})

    assert child_env["UPSTOX_ACCESS_TOKEN"] == _SECRET


def test_an_operator_supplied_token_outranks_an_inherited_analytics_one(monkeypatch) -> None:
    """`--upstox-token` meant explicit-wins. Passing through the environment must keep that."""
    from scripts.serve_live_dashboard import build_pilot_launch

    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "the-inherited-one")
    _, child_env = build_pilot_launch({"upstox_token": _SECRET})

    assert child_env["UPSTOX_ACCESS_TOKEN"] == _SECRET
    assert "UPSTOX_ANALYTICS_TOKEN" not in child_env


def test_an_inherited_token_survives_when_the_operator_supplies_none(monkeypatch) -> None:
    """The scheduled path supplies no token and must keep working off the environment."""
    from scripts.serve_live_dashboard import build_pilot_launch

    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "the-inherited-one")
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    _, child_env = build_pilot_launch({})

    assert child_env["UPSTOX_ANALYTICS_TOKEN"] == "the-inherited-one"


def test_the_session_settings_the_operator_chose_do_reach_the_child(monkeypatch) -> None:
    """A guard against fixing the leak by dropping the arguments."""
    from scripts.serve_live_dashboard import build_pilot_launch

    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    cmd, _ = build_pilot_launch(
        {
            "capital": 250000,
            "slippage_bps": 7.5,
            "end_time_ist": "14:45:00",
            "universe_name": "NIFTY50",
        }
    )

    assert cmd[cmd.index("--capital") + 1] == "250000"
    assert cmd[cmd.index("--slippage-bps") + 1] == "7.5"
    assert cmd[cmd.index("--end-time-ist") + 1] == "14:45:00"
    assert cmd[cmd.index("--universe-name") + 1] == "NIFTY50"
