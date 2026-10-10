"""Opening the app must not pay for libraries that only a research screen needs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Each takes a second or more to load on an ordinary laptop. A person who opens QuantOS waits for all of them
# unless they are loaded only when the screen that uses them is opened.
HEAVY_LIBRARIES = ("scipy",)


def _loaded_after_importing_the_app() -> set[str]:
    code = (
        "import sys, json\n"
        "import quant_system.server.app\n"
        "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules})))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    import json

    return set(json.loads(result.stdout.strip().splitlines()[-1]))


def test_importing_the_app_does_not_load_the_heavy_research_libraries() -> None:
    loaded = _loaded_after_importing_the_app()
    assert [name for name in HEAVY_LIBRARIES if name in loaded] == []
