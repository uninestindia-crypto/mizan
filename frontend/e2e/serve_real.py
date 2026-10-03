"""Start the real app with an empty state folder; the test points it at the user's real data folder."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

state = Path(os.environ["QUANTOS_E2E_DIR"])
shutil.rmtree(state, ignore_errors=True)
(state / "app").mkdir(parents=True)
os.environ["QUANTOS_APP_ROOT"] = str(state / "app")

from quant_system.server.app import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("QUANTOS_E2E_PORT", "8771")), log_level="warning")
