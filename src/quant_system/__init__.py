"""Modular Quantitative Trading & Backtesting System (QuantOS)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

__version__ = "2.1.0"

# Enforce 100% drive isolation: all runtime caches, logs, tempfiles, and data stay on the installation drive
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LOCAL_TMP = _REPO_ROOT / "tmp"
_LOCAL_TMP.mkdir(parents=True, exist_ok=True)
(_REPO_ROOT / "data").mkdir(parents=True, exist_ok=True)
(_REPO_ROOT / "logs").mkdir(parents=True, exist_ok=True)

# Set environment variables for all sub-processes and standard libraries
os.environ["TEMP"] = str(_LOCAL_TMP)
os.environ["TMP"] = str(_LOCAL_TMP)
os.environ["TMPDIR"] = str(_LOCAL_TMP)
os.environ["MPLCONFIGDIR"] = str(_LOCAL_TMP / "matplotlib")
if "PYTHONPYCACHEPREFIX" not in os.environ:
    os.environ["PYTHONPYCACHEPREFIX"] = str(_LOCAL_TMP / "pycache")
tempfile.tempdir = str(_LOCAL_TMP)
