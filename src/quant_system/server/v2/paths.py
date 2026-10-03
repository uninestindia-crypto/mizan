"""Where QuantOS 2.0 keeps its own files, and where it looks for market data."""

from __future__ import annotations

import ctypes
import os
import string
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from quant_system.market.sources import discover_caches

MARKET_CACHE = Path("evidence") / "market-cache"


def app_root() -> Path:
    """The install folder (frozen app) or the project root (source). ``QUANTOS_APP_ROOT`` overrides."""
    override = os.environ.get("QUANTOS_APP_ROOT")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[4]


def state_dir() -> Path:
    path = app_root() / "data" / "quantos2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def index_dir() -> Path:
    return state_dir() / "index"


def spa_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "static" / "app"


def is_data_folder(path: Path) -> bool:
    """A QuantOS data folder holds ``evidence/market-cache`` with at least one recognised cache.

    A recognised cache has a ``store/datasets`` folder, which is what the index reads. A folder with
    only a few tracked files under ``evidence`` (such as a source checkout) does not qualify.
    """
    try:
        return bool(discover_caches(path / MARKET_CACHE))
    except OSError:
        return False


def count_datasets(path: Path) -> int:
    """Committed daily-bar datasets across every recognised cache in a data folder."""
    total = 0
    for cache in discover_caches(path / MARKET_CACHE):
        try:
            total += sum(1 for _ in os.scandir(cache.store / "datasets"))
        except OSError:
            continue
    return total


_SKIP_DIRS = frozenset(
    {
        "windows",
        "program files",
        "program files (x86)",
        "programdata",
        "$recycle.bin",
        "system volume information",
        "recovery",
        "perflogs",
        "appdata",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "site-packages",
        "$windows.~bt",
        "windowsapps",
    }
)
_DRIVE_FIXED = 3


def resolve_data_folder(chosen: Path) -> Path | None:
    r"""Turn whatever folder the user picked into the QuantOS data folder inside it.

    People pick the checkout, the ``data`` folder, ``evidence`` or ``market-cache`` itself. All of
    those mean the same thing, so accept them rather than asking for the exact one.
    """
    attempts = [chosen, chosen / "data"]
    if chosen.name.lower() == "evidence":
        attempts.append(chosen.parent)
    if chosen.name.lower() == "market-cache":
        attempts.append(chosen.parent.parent)
    for attempt in attempts:
        if is_data_folder(attempt):
            return attempt.resolve()
    found = scan_for_data_folders([chosen], max_seconds=6.0, max_depth=4)
    return found[0][0] if found else None


def fixed_drive_roots() -> list[Path]:
    """Internal drives only. Floppy, card-reader, network and optical drives are never probed."""
    if sys.platform != "win32":
        return [Path.home()]
    roots: list[Path] = []
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        get_type = ctypes.windll.kernel32.GetDriveTypeW
    except (AttributeError, OSError):
        return [Path(f"{letter}:\\") for letter in "CDEFGH"]
    for index, letter in enumerate(string.ascii_uppercase):
        if mask & (1 << index) and get_type(f"{letter}:\\") == _DRIVE_FIXED:
            roots.append(Path(f"{letter}:\\"))
    return roots


def _user_folders() -> list[Path]:
    home = Path.home()
    names = ("Documents", "Downloads", "Desktop", "OneDrive")
    folders = [home / name for name in names]
    for variable in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        value = os.environ.get(variable)
        if value:
            folders.append(Path(value))
    return [folder for folder in folders if folder.is_dir()]


def _quick_locations() -> list[Path]:
    """Places a data folder usually is, checked directly without walking anything."""
    root = app_root()
    places = [root / "data", root.parent / "data", root.parent / "quant_system" / "data"]
    for drive in fixed_drive_roots():
        for name in (
            "quant_system",
            "QuantOS",
            "Quant OS Project/quant_system",
            "Quant OS/quant_system",
        ):
            places.append(drive / name / "data")
        places.append(drive / "data")
    return places


def scan_for_data_folders(
    roots: list[Path], *, max_seconds: float = 12.0, max_depth: int = 5
) -> list[tuple[Path, int]]:
    r"""Walk ``roots`` breadth first for ``evidence\market-cache`` and return ``(data folder, datasets)``.

    Bounded by time and depth, skips system and developer folders, and never follows junctions or
    symlinks, so it is safe to run on a whole drive.
    """
    deadline = time.monotonic() + max_seconds
    found: dict[Path, int] = {}
    queue: deque[tuple[Path, int]] = deque((root, 0) for root in roots)
    while queue and time.monotonic() < deadline:
        folder, depth = queue.popleft()
        try:
            entries = list(os.scandir(folder))
        except OSError:
            continue
        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False) or entry.is_symlink():
                    continue
            except OSError:
                continue
            lowered = entry.name.lower()
            if lowered == "evidence":
                if (Path(entry.path) / "market-cache").is_dir() and is_data_folder(folder):
                    found[folder.resolve()] = 0
                continue
            if lowered in _SKIP_DIRS or depth >= max_depth:
                continue
            queue.append((Path(entry.path), depth + 1))
    return sorted(((f, count_datasets(f)) for f in found), key=lambda item: -item[1])


def data_folder_candidates() -> list[tuple[Path, int]]:
    """Likely data folders with their dataset counts, fullest first. Fast: never walks a drive."""
    seen: list[Path] = []
    for candidate in _quick_locations():
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved not in seen and is_data_folder(resolved):
            seen.append(resolved)
    return sorted(((folder, count_datasets(folder)) for folder in seen), key=lambda item: -item[1])


class DataFolderScan:
    """One background search of this PC for market data, started automatically on first need.

    The search checks the usual places instantly, then walks the user's folders and every internal
    drive. ``snapshot()`` is cheap, so the app can poll it while the walk runs.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = "IDLE"  # IDLE | RUNNING | DONE
        self._found: list[tuple[Path, int]] = []
        self._finished_at: float | None = None

    def start(self, *, force: bool = False) -> bool:
        with self._lock:
            if self._state == "RUNNING":
                return False
            if self._state == "DONE" and not force:
                return False
            self._state = "RUNNING"
            self._found = list(data_folder_candidates())
        threading.Thread(target=self._run, name="QuantOS-DataScan", daemon=True).start()
        return True

    def _run(self) -> None:
        results: dict[Path, int] = {}
        try:
            for roots, seconds, depth in (
                (_user_folders(), 6.0, 5),
                (fixed_drive_roots(), 25.0, 5),
            ):
                for folder, count in scan_for_data_folders(
                    roots, max_seconds=seconds, max_depth=depth
                ):
                    results[folder] = count
                with self._lock:
                    merged = dict(self._found)
                    merged.update(results)
                    self._found = sorted(merged.items(), key=lambda item: -item[1])
        finally:
            with self._lock:
                self._state = "DONE"
                self._finished_at = time.monotonic()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "found": [{"path": str(path), "datasets": count} for path, count in self._found],
            }


data_scan = DataFolderScan()
