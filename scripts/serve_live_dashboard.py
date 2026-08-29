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
STATUS_FILE = PROJECT_ROOT / "logs" / "paper_runs" / "live_paper_status.json"
PID_FILE = PROJECT_ROOT / "logs" / "paper_runs" / "runner.pid"

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
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
        elif self.path == "/api/status":
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
            capital = str(req_data.get("capital", 50000))
            slippage = str(req_data.get("slippage_bps", 5.0))
            stop_time = str(req_data.get("end_time_ist", "15:30:00"))
            interval = str(req_data.get("interval_seconds", 10.0))
            universe_name = str(req_data.get("universe_name", "NIFTY500"))
            model_profile = str(req_data.get("model_profile", "sprint_50k"))
            upstox_token = req_data.get("upstox_token") or os.getenv("UPSTOX_ACCESS_TOKEN", "")

            python_exe = sys.executable
            script_path = str(PROJECT_ROOT / "scripts" / "run_paper_pilot_session.py")

            cmd = [
                python_exe,
                script_path,
                "--realtime",
                "--capital",
                capital,
                "--slippage-bps",
                slippage,
                "--end-time-ist",
                stop_time,
                "--interval-seconds",
                interval,
                "--model-profile",
                model_profile,
                "--universe-name",
                universe_name,
            ]
            if upstox_token:
                cmd.extend(["--upstox-token", upstox_token])

            logger.info("Starting background paper pilot: %s", " ".join(cmd))
            try:
                # Stop existing if any
                if ACTIVE_PROCESS and ACTIVE_PROCESS.poll() is None:
                    ACTIVE_PROCESS.terminate()

                ACTIVE_PROCESS = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
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


def serve_dashboard(port: int = 8080) -> None:
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), DashboardHandler) as httpd:
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
    args = parser.parse_args()
    serve_dashboard(port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
