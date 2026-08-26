#!/usr/bin/env python3
"""Convenience executable script for Mizan CLI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from quant_system.modeling.mizan_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
