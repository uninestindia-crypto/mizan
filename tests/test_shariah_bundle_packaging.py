"""The Shariah filings snapshot reaches a factory-new laptop: in the repository, every build and the installer.

The bundled snapshot is real figures from companies' own results filings, so the Shariah screens work on a fresh
laptop with no internet. It travels in `data/shariah` beside the hand-entered sample database, and the list of
listed companies that the coverage line counts travels in `data/authorities`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from quant_system.shariah.filings.models import FilingFigures
from quant_system.shariah.filings.snapshot import read_snapshot
from quant_system.shariah.services.proof_paths import LISTED_FILE, SNAPSHOT_FILE

ROOT = Path(__file__).resolve().parents[1]
SPECS = ["quant_system.spec", "installer/quantos.spec", "installer/quantos-studio.spec"]
SNAPSHOT = ROOT / "data" / SNAPSHOT_FILE
LISTED = ROOT / "data" / LISTED_FILE


@pytest.mark.parametrize("spec", SPECS)
def test_every_build_carries_the_shariah_data_folder_where_the_snapshot_and_the_sample_database_live(
    spec: str,
) -> None:
    text = (ROOT / spec).read_text(encoding="utf-8")
    assert "'data/shariah')" in text.replace('"', "'")


@pytest.mark.parametrize("spec", SPECS)
def test_every_build_carries_the_list_of_listed_companies_the_coverage_line_counts(
    spec: str,
) -> None:
    text = (ROOT / spec).read_text(encoding="utf-8")
    assert "nse-all-listed-equities.csv" in text and "'data/authorities')" in text.replace('"', "'")
    assert LISTED.is_file()


def test_the_installer_replaces_the_staged_shariah_folder_on_every_update_so_a_newer_snapshot_arrives() -> (
    None
):
    script = (ROOT / "installer" / "quant_os_setup.iss").read_text(encoding="utf-8")
    staged = next(line for line in script.splitlines() if line.startswith('Source: "{#SourceDir}'))
    assert "ignoreversion" in staged and "onlyifdoesntexist" not in staged
    assert 'Source: "..\\data\\shariah\\*"' in script


def test_the_release_build_stages_the_shariah_folder_into_the_program_folder() -> None:
    script = (ROOT / "scripts" / "build-windows-release.ps1").read_text(encoding="utf-8")
    assert 'Join-Path $projectRoot "data\\shariah"' in script


def test_the_snapshot_is_in_the_repository_and_not_hidden_by_the_ignore_rules() -> None:
    assert SNAPSHOT.is_file()
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(SNAPSHOT.relative_to(ROOT))], cwd=ROOT, check=False
    )
    assert ignored.returncode == 1  # 1 means "not ignored"


def test_every_row_of_the_snapshot_is_a_real_filing_with_its_hash_and_its_link() -> None:
    snapshot = read_snapshot(SNAPSHOT)
    assert snapshot is not None and snapshot.built_on and len(snapshot.filings) > 100
    rows = [FilingFigures.from_json_dict(raw) for raw in snapshot.filings.values()]
    assert all(re.fullmatch(r"[0-9a-f]{64}", row.proof.sha256) for row in rows)
    assert all(row.proof.source_url.startswith("https://nsearchives.nseindia.com/") for row in rows)
    assert {row.symbol for row in rows} == set(snapshot.filings)


def test_the_snapshot_holds_no_secret_and_no_path_from_a_developers_machine() -> None:
    import gzip

    text = gzip.open(SNAPSHOT, "rt", encoding="utf-8").read()
    assert not re.search(
        r"[A-Za-z]:\\\\|/home/|/Users/|Bearer |api[_-]?key|password|secret", text, re.I
    )
