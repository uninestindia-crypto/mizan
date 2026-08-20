"""Shared fixtures for Quant System tests."""

from __future__ import annotations

import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.core.domain import PriceBar, Quote
from quant_system.data.loader import SyntheticDataGenerator

# Ensure all test processes isolate temporary files strictly to local installation drive
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TMP_DIR = _REPO_ROOT / "tmp"
_TMP_DIR.mkdir(parents=True, exist_ok=True)
os.environ["TEMP"] = str(_TMP_DIR)
os.environ["TMP"] = str(_TMP_DIR)
os.environ["TMPDIR"] = str(_TMP_DIR)
tempfile.tempdir = str(_TMP_DIR)


@pytest.fixture
def sample_bars() -> list[PriceBar]:
    series = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=date(2025, 1, 1),
        days=60,
        initial_price=1500.0,
        seed=42,
    )
    return series.bars


@pytest.fixture
def sample_quote() -> Quote:
    return Quote(
        symbol="INFY",
        timestamp=datetime(2025, 1, 1, 9, 15),
        bid=Decimal("1500.00"),
        ask=Decimal("1500.50"),
        bid_size=1000,
        ask_size=1200,
        last_price=Decimal("1500.25"),
    )
