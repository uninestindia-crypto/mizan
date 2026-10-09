"""Where the bundled filing snapshot and the list of listed companies live, in a source checkout and in a built app.

The built app carries its data folder in more than one place (beside the program, inside its bundle), so every
candidate is tried in a fixed order and the first file that exists is used. Nothing here writes anything.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

__all__ = [
    "LISTED_FILE",
    "SNAPSHOT_FILE",
    "bundled_snapshot_path",
    "candidate_files",
    "listed_equities_count",
]

SNAPSHOT_FILE = Path("shariah") / "filings_snapshot.json.gz"
LISTED_FILE = Path("authorities") / "nse-all-listed-equities.csv"
REPO_ROOT = Path(__file__).resolve().parents[4]


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


def candidate_files(relative: Path) -> list[Path]:
    """Every place a bundled data file can be, best first."""
    return [root / "data" / relative for root in _roots()]


def bundled_snapshot_path() -> Path:
    """The bundled snapshot when one exists, else where it would be. A missing file is a normal state."""
    candidates = candidate_files(SNAPSHOT_FILE)
    return next((path for path in candidates if path.is_file()), candidates[0])


@lru_cache(maxsize=4)
def _count_rows(path: Path, modified: int, size: int) -> int:
    # Both are part of the cache key: a changed file is counted again, even when two writes share one clock tick.
    del modified, size
    with path.open(encoding="utf-8", newline="") as handle:
        return max(sum(1 for line in handle if line.strip()) - 1, 0)


def listed_equities_count() -> int | None:
    """How many companies NSE lists, from the bundled list, or None when this copy has no such list."""
    for path in candidate_files(LISTED_FILE):
        try:
            seen = path.stat()
            return _count_rows(path, seen.st_mtime_ns, seen.st_size)
        except (OSError, UnicodeDecodeError):
            continue
    return None
