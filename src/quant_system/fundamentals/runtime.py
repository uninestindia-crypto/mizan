"""Putting the pieces together for the running app: where the files are, and one store, service and job runner.

A source checkout, a built app and a cloud container keep the bundled snapshot in different places, so every
candidate is tried in a fixed order. A missing snapshot is a normal state: the app then simply holds no filings
until a person asks it to read a company from inside the app.
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from quant_system.fundamentals.jobs import FundamentalsJobs, SourceFactory
from quant_system.fundamentals.service import FundamentalsService
from quant_system.fundamentals.store import FundamentalsStore
from quant_system.shariah.filings.nse_client import NseFilingsClient

SNAPSHOT_FILE: Final = Path("fundamentals") / "fundamentals_snapshot.json.gz"
USER_DB_NAME: Final = "fundamentals.sqlite"
REPO_ROOT: Final = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Runtime:
    service: FundamentalsService
    jobs: FundamentalsJobs


def _roots() -> list[Path]:
    """Folders that can hold a ``data`` folder, best first: an explicit app root, the built app, the checkout."""
    roots: list[Path] = []
    override = os.environ.get("QUANTOS_APP_ROOT")
    if override:
        roots.append(Path(override))
    if getattr(sys, "frozen", False):
        beside = Path(sys.executable).resolve().parent
        roots += [beside, beside / "_internal"]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        roots.append(Path(bundle))
    roots.append(REPO_ROOT)
    return list(dict.fromkeys(roots))


def bundled_snapshot_path() -> Path:
    """The bundled snapshot when one exists, else where it would be. A missing file is a normal state."""
    candidates = [root / "data" / SNAPSHOT_FILE for root in _roots()]
    return next((path for path in candidates if path.is_file()), candidates[0])


def user_db_path() -> Path:
    from quant_system.server.v2 import (
        paths,
    )  # the app's own state folder; imported here to keep this package light

    return paths.state_dir() / USER_DB_NAME


def _today() -> date:
    return datetime.now(UTC).astimezone().date()


def _now() -> datetime:
    return datetime.now(UTC)


def _live_source() -> SourceFactory:
    return NseFilingsClient


def build_runtime(
    snapshot: Path | None,
    user_db: Path | None,
    source: SourceFactory | None = None,
    today: Callable[[], date] = _today,
) -> Runtime:
    """A runtime over the given files. Tests pass a fake `source` and a fixed `today`; the app passes neither."""
    store = FundamentalsStore(snapshot, user_db)
    return Runtime(
        FundamentalsService(store, today),
        FundamentalsJobs(store, source or _live_source(), _now),
    )


_built: dict[tuple[str, str], Runtime] = {}
_lock = threading.Lock()


def default_runtime() -> Runtime:
    """The app's own runtime, built once per pair of files so jobs and the store are shared by every request."""
    snapshot, user_db = bundled_snapshot_path(), user_db_path()
    key = (str(snapshot), str(user_db))
    with _lock:
        if key not in _built:
            _built[key] = build_runtime(snapshot, user_db)
        return _built[key]


def forget_runtimes() -> None:
    """Drop the cached runtimes (for tests that move the app root)."""
    with _lock:
        _built.clear()
