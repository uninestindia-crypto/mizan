"""Where QuantOS 2.0 keeps its own files, and where it looks for market data."""

from __future__ import annotations

import os
import string
import sys
from pathlib import Path

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


def data_folder_candidates() -> list[tuple[Path, int]]:
    r"""Likely data folders with their dataset counts, fullest first.

    Looks at this install's own ``data`` folder, then ``<drive>:\quant_system\data`` on each drive.
    """
    seen: list[Path] = []
    candidates = [app_root() / "data"]
    if sys.platform == "win32":
        candidates += [
            Path(f"{letter}:\\") / "quant_system" / "data" for letter in string.ascii_uppercase
        ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved not in seen and is_data_folder(resolved):
            seen.append(resolved)
    return sorted(((folder, count_datasets(folder)) for folder in seen), key=lambda item: -item[1])
