"""Background market-index build: one at a time, with progress the UI can poll."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_system.market import build_market_index
from quant_system.market.index_builder import BuildReport

Builder = Callable[[Path, Path, Callable[[float, str], None]], BuildReport]


class IndexJob:
    def __init__(self, builder: Builder = build_market_index) -> None:
        self._builder = builder
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.state = "IDLE"
        self.progress = 0.0
        self.message = ""
        self.error: str | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.report: dict[str, Any] | None = None

    @property
    def running(self) -> bool:
        return self.state == "RUNNING"

    def start(self, data_folder: Path, index_dir: Path) -> bool:
        """Start a build unless one is already running. Returns whether a build was started."""
        with self._lock:
            if self.running:
                return False
            self.state = "RUNNING"
            self.progress = 0.0
            self.message = "Starting"
            self.error = None
            self.report = None
            self.started_at = _now()
            self.finished_at = None
            self._thread = threading.Thread(
                target=self._run,
                args=(data_folder, index_dir),
                name="quantos-index-build",
                daemon=True,
            )
            self._thread.start()
            return True

    def _run(self, data_folder: Path, index_dir: Path) -> None:
        started = time.perf_counter()
        try:
            report = self._builder(data_folder, index_dir, self._on_progress)
        except Exception as err:  # the UI must hear about any failure, whatever its type
            self.state = "ERROR"
            self.error = str(err) or type(err).__name__
        else:
            self.report = {
                key: (str(value) if isinstance(value, Path) else value)
                for key, value in asdict(report).items()
            }
            self.state = "DONE"
            self.progress = 1.0
            self.message = (
                f"Indexed {report.symbols:,} symbols in {time.perf_counter() - started:.0f} s"
            )
        finally:
            self.finished_at = _now()

    def _on_progress(self, fraction: float, message: str) -> None:
        self.progress = max(0.0, min(1.0, fraction))
        self.message = message

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "report": self.report,
        }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
