"""The frozen trial ledger, read as the runtime authority for the multiplicity count.

Why this module exists
----------------------
``reports/short_horizon/TRIAL-LEDGER.md`` is frozen evidence: it was written before any result
existed and its binding rule is that a trial not listed there cannot be added after a result is seen.
The deflated Sharpe of every trial divides by a benchmark built from that count, so the ledger is not
documentation about the study -- it is a **numerical input to every published figure**.

It was treated as documentation anyway. ``DECLARED_TRIALS`` in the experiment script was a literal
``6`` while the ledger had grown to nine SPENT rows, and the two were connected by nothing at all.
Three trials (7-9, TimesFM 2.5) were published in that window, each deflated against a search two
thirds its real size, in the direction that flatters a candidate. The ledger's own rows carried
hand-computed corrections at the true count, which is the tell: a person had noticed and the code
still had not.

A test can catch that drift, and one does (``tests/test_short_horizon_trial_count.py``). But a test
catches it in CI, which is after a run may already have written a wrong number into an artifact. So
the parse happens at run time too, and a disagreement refuses the run rather than publishing.

What counts as a trial, and what deliberately does not
------------------------------------------------------
Only rows whose first cell is a bare integer. Two kinds of row are excluded, and the ledger states
why each consumes no ordinal:

- ``C1``, the abstention threshold grid, declared **once** and applied identically to every hold.
- ``NOISE``, the control. A control is not a candidate: it cannot be promoted under any outcome, so
  counting it would deflate the real candidates for the crime of being measured carefully.

Excluding them is a substantive claim about the search, not a parsing convenience, which is why it
lives here next to the parser rather than in a caller's comment.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "LEDGER_RELATIVE_PATH",
    "SpentTrial",
    "declared_spent_trials",
    "default_ledger_path",
    "read_spent_trials",
    "require_declared_trials",
]

LEDGER_RELATIVE_PATH = Path("reports") / "short_horizon" / "TRIAL-LEDGER.md"
"""Location of the frozen ledger, relative to the repository root."""

_MINIMUM_CELLS = 4
"""``| # | Family | Hold | Status | ...`` -- status is the fourth cell and the reason a row counts."""


@dataclass(frozen=True)
class SpentTrial:
    """One numbered ledger row recorded as ``SPENT``.

    ``SPENT`` means the trial ran and its result counts whatever it was. A disappointing result does
    not return the ordinal, which is the property that makes the count a denominator rather than a
    tally of successes.
    """

    number: int
    family: str
    hold: str


def default_ledger_path() -> Path:
    """The ledger inside this checkout.

    Derived from this module's own location so that a worktree, a verification clone and the install
    root each read their own ledger rather than one of them reading another's.
    """
    return Path(__file__).resolve().parents[3] / LEDGER_RELATIVE_PATH


def read_spent_trials(ledger_path: Path | None = None) -> tuple[SpentTrial, ...]:
    """Parse the numbered ``SPENT`` rows, in ledger order.

    Raises rather than returning an empty tuple when the ledger is missing or contains no spent row.
    An absent denominator is not a denominator of zero, and a deflation computed against "no declared
    search" is precisely the failure this module exists to prevent.
    """
    path = default_ledger_path() if ledger_path is None else ledger_path
    if not path.is_file():
        raise FileNotFoundError(
            f"frozen trial ledger not found at {path}. Every short-horizon deflated Sharpe divides "
            "by a benchmark built from its trial count, so there is no safe default to assume."
        )

    trials: list[SpentTrial] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < _MINIMUM_CELLS or not cells[0].isdigit():
            continue
        if "SPENT" not in cells[3]:
            continue
        trials.append(SpentTrial(number=int(cells[0]), family=cells[1], hold=cells[2]))

    if not trials:
        raise ValueError(
            f"{path} records no numbered SPENT trial. Either the ledger was truncated or its table "
            "shape changed; both are reasons to stop, not to deflate against a guess."
        )

    numbers = [trial.number for trial in trials]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(
            f"{path} trial numbers are not contiguous from 1: {numbers}. A gap means a trial was "
            "removed after its result was seen, which the ledger's own rule forbids."
        )
    return tuple(trials)


def declared_spent_trials(ledger_path: Path | None = None) -> int:
    """How many trials the frozen ledger says have been spent. The multiplicity count."""
    return len(read_spent_trials(ledger_path))


def require_declared_trials(declared: int, ledger_path: Path | None = None) -> int:
    """Refuse to proceed unless ``declared`` equals the ledger's spent-trial count.

    Called before a run produces any figure. The constant stays explicit and greppable in the caller
    -- an unpinned parse with no declared expectation would let a careless ledger edit silently
    re-score published work instead of failing -- and this reconciles the two at the only moment when
    being wrong is still cheap.
    """
    actual = declared_spent_trials(ledger_path)
    if declared != actual:
        path = default_ledger_path() if ledger_path is None else ledger_path
        direction = (
            "too low a count flatters every candidate"
            if declared < actual
            else "too high a count penalises every candidate"
        )
        raise ValueError(
            f"declared multiplicity count {declared} disagrees with {path}, which records {actual} "
            f"SPENT trials. Refusing to publish a deflated Sharpe against the wrong denominator: "
            f"{direction}. Reconcile the ledger and the constant before running."
        )
    return actual
