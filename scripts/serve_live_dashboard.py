"""QuantOS Live Paper Trading Web Dashboard Server with GUI Session Controls.

Provides a modern, Bloomberg/TradingView-styled real-time dashboard with interactive
GUI controls to configure automated market schedules (start time, market close time,
capital, slippage, and rebalance frequency) for the Mīzān alpha model.
"""

from __future__ import annotations

import argparse
import http.server
import json
import logging
import os
import signal
import socketserver
import subprocess
import sys
from pathlib import Path
from typing import Any

# The dashboard markup is a library asset (see quant_system.server.ui.live_dashboard).
# It used to be defined here and imported back into server/app.py, which made the library
# depend on this script and broke `mypy src launcher.py scripts`.
from quant_system.server.ui.live_dashboard import HTML_DASHBOARD

PROJECT_ROOT = Path(__file__).resolve().parent.parent
#: The dashboard's script is a static asset of the app (the page's CSP forbids inline scripts).
LIVE_DASHBOARD_JS = (
    PROJECT_ROOT / "src" / "quant_system" / "server" / "static" / "live_dashboard.js"
)
STATUS_FILE = PROJECT_ROOT / "logs" / "paper_runs" / "live_paper_status.json"
PID_FILE = PROJECT_ROOT / "logs" / "paper_runs" / "runner.pid"
XS_STATE_FILE = PROJECT_ROOT / "logs" / "xs_monthly_new" / "paper_watch" / "state.json"


def load_env_file() -> None:
    """Read `.env` into the environment. Called from `main`, never at import.

    This ran at module scope. Importing the module -- which a test, a tool, or an editor's
    autocomplete will do -- therefore wrote the founder's real Upstox access token into
    `os.environ` as a side effect of the import statement. Seven tests asserting what happens
    *without* a token failed the moment anything imported this file, because by then there was one.

    A credential belongs in the environment of the process that was launched to use it, not in the
    environment of anything that happens to import the module that reads it.
    """
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("quant_system.dashboard")

ACTIVE_PROCESS: subprocess.Popen[bytes] | None = None


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/index.html", "/live", "/trading-live"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
        elif self.path == "/api/control/available":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"available": True}).encode("utf-8"))
        elif self.path == "/static/live_dashboard.js":
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(LIVE_DASHBOARD_JS.read_bytes())
        elif self.path in ("/api/status", "/api/paper-pilot/live-status"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            if STATUS_FILE.exists():
                try:
                    with open(STATUS_FILE, encoding="utf-8") as f:
                        data = f.read()
                    self.wfile.write(data.encode("utf-8"))
                except Exception as err:
                    self.wfile.write(json.dumps({"error": str(err)}).encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"status": "WAITING_FOR_DATA"}).encode("utf-8"))
        elif self.path in ("/api/xs_status", "/api/xs-monthly/status"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            if XS_STATE_FILE.exists():
                try:
                    with open(XS_STATE_FILE, encoding="utf-8") as f:
                        data = f.read()
                    self.wfile.write(data.encode("utf-8"))
                except Exception as err:
                    self.wfile.write(json.dumps({"error": str(err)}).encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"status": "WAITING_FOR_DATA"}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        global ACTIVE_PROCESS
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"

        try:
            req_data = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            req_data = {}

        if self.path == "/api/control/start":
            stop_time = str(req_data.get("end_time_ist", "15:30:00"))
            cmd, child_env = build_pilot_launch(req_data)

            logger.info("Starting background paper pilot: %s", " ".join(cmd))
            try:
                # Stop existing if any
                if ACTIVE_PROCESS and ACTIVE_PROCESS.poll() is None:
                    ACTIVE_PROCESS.terminate()

                ACTIVE_PROCESS = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=child_env)
                PID_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(PID_FILE, "w") as pf:
                    pf.write(str(ACTIVE_PROCESS.pid))

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "status": "STARTED",
                            "pid": ACTIVE_PROCESS.pid,
                            "message": f"Mīzān session started. Automated trading active until {stop_time} IST.",
                        }
                    ).encode("utf-8")
                )
            except Exception as err:
                logger.exception("Failed to start process: %s", err)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(err)}).encode("utf-8"))

        elif self.path == "/api/control/stop":
            logger.info("Halting active paper pilot session...")
            halted = False
            halted = False
            if ACTIVE_PROCESS and ACTIVE_PROCESS.poll() is None:
                ACTIVE_PROCESS.terminate()
                halted = True

            if PID_FILE.exists():
                try:
                    with open(PID_FILE) as pf:
                        old_pid = int(pf.read().strip())
                    os.kill(old_pid, signal.SIGTERM)
                    halted = True
                except Exception:
                    pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            # `halted` was assigned in both branches above and never read, so this endpoint
            # reported HALTED even when nothing was running and no PID file existed. Using the
            # flag is what the assignments were plainly for.
            self.wfile.write(
                json.dumps(
                    {
                        "status": "HALTED" if halted else "NOT_RUNNING",
                        "message": (
                            "Trading session halted and reconciled to disk."
                            if halted
                            else "No active trading session was found to halt."
                        ),
                    }
                ).encode("utf-8")
            )
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format: str, *args: Any) -> None:
        return


def build_pilot_launch(req_data: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """The child's argv and environment. The token goes in the environment, never in argv.

    It used to be appended to `cmd` as `--upstox-token <token>`, which leaked it twice:

    - `logger.info("Starting background paper pilot: %s", " ".join(cmd))` wrote the whole bearer
      token in plaintext to stderr, and to a file wherever the dashboard is launched with
      redirection;
    - argv is readable from the process table by any local process for as long as the session runs,
      which is the whole trading day.

    The credential here is the `UPSTOX_ANALYTICS_TOKEN` class, valid for about a year.

    Redacting the log line would have fixed only the first leak, and only until someone added
    another log statement. Keeping the token out of `cmd` entirely fixes both by construction:
    `resolve_upstox_token` (`run_paper_pilot_session.py:118`) already reads the environment, so the
    child needs no flag. An operator-supplied token still wins, which is what `--upstox-token` meant
    -- the competing analytics variable is removed from the child's environment so it cannot
    outrank what the operator just typed.
    """
    upstox_token = req_data.get("upstox_token") or os.getenv("UPSTOX_ACCESS_TOKEN", "")

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_paper_pilot_session.py"),
        "--realtime",
        "--capital",
        str(req_data.get("capital", 50000)),
        "--slippage-bps",
        str(req_data.get("slippage_bps", 5.0)),
        "--end-time-ist",
        str(req_data.get("end_time_ist", "15:30:00")),
        "--interval-seconds",
        str(req_data.get("interval_seconds", 10.0)),
        "--model-profile",
        str(req_data.get("model_profile", "sprint_50k")),
        "--universe-name",
        str(req_data.get("universe_name", "NIFTY500")),
    ]

    child_env = dict(os.environ)
    if upstox_token:
        # Explicit beats inherited, exactly as the flag did.
        child_env.pop("UPSTOX_ANALYTICS_TOKEN", None)
        child_env["UPSTOX_ACCESS_TOKEN"] = upstox_token

    return cmd, child_env


class ThreadedDashboardServer(socketserver.ThreadingTCPServer):
    """One thread per connection, because the dashboard is a page a browser keeps open.

    `socketserver.TCPServer` handles exactly one request at a time. A browser holding a connection
    open -- a keep-alive, a tab left on the page, a request that never completes -- blocks every
    other request behind it, so the port stays open and listening while nothing is answered. That
    is what happened on 2026-09-01: the process was alive, `Get-NetTCPConnection` showed it
    listening, and the page was dead.
    """

    daemon_threads = True  # a stuck client must not keep the process alive at shutdown
    allow_reuse_address = True


def build_dashboard_server(port: int = 8080, host: str = "127.0.0.1") -> ThreadedDashboardServer:
    """The bound server, not yet serving.

    Separate from `serve_dashboard` so a test can bind port 0, learn the port the OS chose, and
    drive real concurrent requests against it. `serve_forever` blocks, so a test cannot otherwise
    observe whether a stalled client blocks anyone else.
    """
    # Loopback, not 0.0.0.0. This page serves an Upstox access-token field and Start/Halt
    # controls; bound to all interfaces those were reachable by anyone on the network.
    return ThreadedDashboardServer((host, port), DashboardHandler)


def serve_dashboard(port: int = 8080, host: str = "127.0.0.1") -> None:
    with build_dashboard_server(port=port, host=host) as httpd:
        logger.info("=" * 75)
        logger.info("QuantOS Live Trading Dashboard running at http://localhost:%d", port)
        logger.info("Serving live P&L and market state from %s", STATUS_FILE)
        logger.info("=" * 75)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Dashboard server shutting down...")


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantOS Live Trading Dashboard Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to serve dashboard on")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Interface to bind. Defaults to loopback: this page exposes a token field and "
        "session controls, so binding it to 0.0.0.0 hands those to the whole network.",
    )
    args = parser.parse_args()
    load_env_file()
    serve_dashboard(port=args.port, host=args.host)
    return 0


if __name__ == "__main__":
    sys.exit(main())
