"""Start the real QuantOS app for end-to-end tests, against an isolated state folder.

Layout under ``QUANTOS_E2E_DIR`` (wiped on every start):

    app/            QUANTOS_APP_ROOT: settings database and the market index are written here
    fixture/data/   a miniature evidence store in the real on-disk format (tests.market_fixtures)

Nothing here touches the user's real QuantOS data or Windows Credential Manager entries.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from tests.market_fixtures import build_standard_store  # noqa: E402

e2e_dir = Path(os.environ["QUANTOS_E2E_DIR"])
shutil.rmtree(e2e_dir, ignore_errors=True)
(e2e_dir / "app").mkdir(parents=True)
build_standard_store(e2e_dir / "fixture" / "data")
os.environ["QUANTOS_APP_ROOT"] = str(e2e_dir / "app")

from quant_system.server.app import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("QUANTOS_E2E_PORT", "8770")), log_level="warning")
