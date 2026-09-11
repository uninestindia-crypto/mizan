"""Serve the XS-monthly paper-watch dashboard (separate, research only).

Own port (default 8091 — the main dashboard lives on 8080), own files.
Read-only against the watch state. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from typing import Any

from quant_system.research_xs_monthly.dashboard import render_dashboard

STATE_DEFAULT = Path("logs/xs_monthly_new/paper_watch/state.json")


def _load_state(path: Path) -> dict[str, Any]:
    if path.is_file():
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return payload
    return {"capital": "?", "cash": "?", "open": [], "closed": [], "runs": []}


def make_handler(state_path: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            if self.path not in ("/", "/index.html"):
                self.send_response(404)
                self.end_headers()
                return
            try:
                page = render_dashboard(_load_state(state_path))
                body = page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (OSError, ValueError) as exc:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"dashboard error: {exc}".encode())

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--state", type=Path, default=STATE_DEFAULT)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.state))
    print(f"xs-monthly watch dashboard on http://127.0.0.1:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
