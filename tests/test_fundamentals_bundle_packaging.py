"""The fundamentals snapshot reaches a factory-new laptop: in the repository and in every build.

The bundled snapshot is real quarterly figures read from companies' own results filings, so the Fundamentals screens
work on a fresh laptop with no internet. It travels in `data/fundamentals`.
"""

from __future__ import annotations

import gzip
import re
import subprocess
from pathlib import Path

import pytest

from quant_system.fundamentals.models import QuarterFigures
from quant_system.fundamentals.runtime import SNAPSHOT_FILE, bundled_snapshot_path
from quant_system.fundamentals.snapshot import read_snapshot

ROOT = Path(__file__).resolve().parents[1]
SPECS = ["quant_system.spec", "installer/quantos.spec", "installer/quantos-studio.spec"]
SNAPSHOT = ROOT / "data" / SNAPSHOT_FILE


@pytest.mark.parametrize("spec", SPECS)
def test_every_build_carries_the_fundamentals_data_folder(spec: str) -> None:
    text = (ROOT / spec).read_text(encoding="utf-8")
    assert "'data/fundamentals')" in text.replace('"', "'")


def test_the_snapshot_is_in_the_repository_and_not_hidden_by_the_ignore_rules() -> None:
    assert SNAPSHOT.is_file()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(SNAPSHOT.relative_to(ROOT))], cwd=ROOT, check=False
    )
    assert ignored.returncode == 1  # 1 means "not ignored"


def test_the_app_finds_the_bundled_snapshot_in_a_checkout() -> None:
    assert bundled_snapshot_path() == SNAPSHOT


def test_the_snapshot_reads_and_holds_many_companies_with_the_date_it_was_built() -> None:
    snapshot = read_snapshot(SNAPSHOT)
    assert snapshot is not None and snapshot.built_on
    assert len(snapshot.companies) > 100 and len(snapshot.industry_groups) > 100


def test_every_row_is_a_real_filing_with_its_hash_and_its_link() -> None:
    snapshot = read_snapshot(SNAPSHOT)
    assert snapshot is not None
    rows = [(symbol, raw) for symbol, quarters in snapshot.companies.items() for raw in quarters]
    assert rows
    assert all(re.fullmatch(r"[0-9a-f]{64}", raw["sha256"]) for _symbol, raw in rows)
    assert all(
        raw["source_url"].startswith("https://nsearchives.nseindia.com/") for _symbol, raw in rows
    )
    assert all(raw["symbol"] == symbol for symbol, raw in rows)


def _read_back() -> list[QuarterFigures]:
    snapshot = read_snapshot(SNAPSHOT)
    assert snapshot is not None
    return [
        QuarterFigures.from_json_dict(raw) for rows in snapshot.companies.values() for raw in rows
    ]


def test_every_row_can_be_read_back_as_quarterly_figures() -> None:
    parsed = _read_back()
    assert parsed and all(item.sha256 and item.source_url for item in parsed)


def test_the_snapshot_holds_no_secret_and_no_path_from_a_developers_machine() -> None:
    text = gzip.open(SNAPSHOT, "rt", encoding="utf-8").read()
    assert not re.search(
        r"[A-Za-z]:\\\\|/home/|/Users/|Bearer |api[_-]?key|password|secret", text, re.I
    )
