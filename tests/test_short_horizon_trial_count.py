"""The declared multiplicity count must equal the frozen ledger, or the deflation is wrong.

``run_short_horizon_experiment.DECLARED_TRIALS`` read 6 while
``reports/short_horizon/TRIAL-LEDGER.md`` had grown to 9 SPENT trials. Nothing connected the two, so
the constant went stale silently and every DSR a fresh run published was deflated against a search
two thirds its real size -- in the direction that flatters a candidate.

The ledger's own rows 7-9 already carried hand-computed corrections ("0.394441 ... 0.312642 at 9"),
which is the tell: a human had noticed, and the code still had not. This test makes the divergence a
failure instead of a discrepancy someone has to spot.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "reports" / "short_horizon" / "TRIAL-LEDGER.md"
EXPERIMENT = REPO / "scripts" / "run_short_horizon_experiment.py"


def _declared_trials() -> int:
    """Read the constant without executing the script's ``__main__`` path."""
    source = EXPERIMENT.read_text(encoding="utf-8")
    match = re.search(r"^DECLARED_TRIALS\s*=\s*(\d+)", source, flags=re.MULTILINE)
    assert match, "DECLARED_TRIALS is no longer a module-level literal in the experiment script"
    return int(match.group(1))


def _spent_ledger_rows() -> list[str]:
    """Numbered ledger rows marked SPENT.

    Only rows whose first cell is a bare integer count. ``C1`` (the abstention grid) and ``NOISE``
    (the control) are deliberately excluded -- the ledger states why each consumes no trial, and
    counting a control as a candidate would deflate the real candidates for being measured carefully.
    """
    rows: list[str] = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        if "SPENT" in cells[3]:
            rows.append(cells[0])
    return rows


def test_the_ledger_is_present() -> None:
    """A missing ledger is not a passing test. The deflation has no denominator without it."""
    assert LEDGER.is_file(), f"frozen trial ledger not found at {LEDGER}"


def test_declared_trials_equals_the_spent_ledger_rows() -> None:
    spent = _spent_ledger_rows()
    assert _declared_trials() == len(spent), (
        f"DECLARED_TRIALS is {_declared_trials()} but the ledger records {len(spent)} SPENT "
        f"trials ({', '.join(spent)}). A trial that ran counts whatever its result was; update the "
        "constant, and remember that raising it lowers every DSR that follows."
    )


def test_the_ledger_rows_are_contiguous_from_one() -> None:
    """A gap means a trial was removed after the fact, which the ledger's own rule forbids."""
    spent = [int(row) for row in _spent_ledger_rows()]
    assert spent == list(range(1, len(spent) + 1)), (
        f"ledger trial numbers are not contiguous: {spent}"
    )


@pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None, reason="experiment script imports numpy"
)
def test_the_constant_the_script_actually_holds_matches_the_source_literal() -> None:
    """Guards against the literal above being shadowed by a later assignment in the same module."""
    spec = importlib.util.spec_from_file_location("_short_horizon_experiment", EXPERIMENT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    assert module.DECLARED_TRIALS == _declared_trials()
