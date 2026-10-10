"""Score short-horizon trial 11 (Kronos-base, five paths) exactly as declared, and only once.

Declaration: `reports/kronos_trial11/TRIAL-LEDGER.md`. This is `scripts/run_kronos_trial.py`, which is another
record's file and is run here unmodified, with three things this wrapper owns:

- **The count.** The scorer deflates against `DECLARED_TRIALS = 10`. This sets it to 11 for the call, so the
  deflated Sharpe is judged against eleven attempts, as the declaration says.
- **Once, for real.** The scorer refuses an existing results file only at the path it is given. A second run
  on another machine, or into a differently named file, could score the same trial twice. This writes a sentinel,
  `reports/kronos_trial11/SCORED.json`, when scoring succeeds, and refuses if the sentinel or any results file for
  trial 11 exists under `reports/`.
- **Only the declared forecasts.** The forecast file must say it is trial 11, Kronos-base, five paths, the full
  23,805 forecasts, built from the declared inputs file. Anything else is refused before any scoring happens.

The scorer writes `"trial": 10` and a trial-10 gate policy id as literals. After it finishes, this corrects those
three labels. Every number is the scorer's own.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

TRIAL = 11
DECLARATION = "reports/kronos_trial11/TRIAL-LEDGER.md"
REPORT_DIR = ROOT_DIR / "reports" / "kronos_trial11"
DEFAULT_FORECASTS = REPORT_DIR / "kronos-forecasts.json"
DEFAULT_RESULTS = REPORT_DIR / "results-kronos-trial11.json"
SENTINEL_NAME = "SCORED.json"

#: SHA-256 of `reports/kronos_trial11/kronos-inputs.json.gz`, the declared model inputs.
INPUTS_SHA256 = "fdbbdd152c582355aabd9ee827d02eac61ca4642133fd10da21f43af2c2cd9c4"
EXPECTED_FORECASTS = 23_805


def results_for_trial(reports: Path, trial: int = TRIAL) -> list[Path]:
    """Every results file under `reports` that says it scores `trial`."""
    found: list[Path] = []
    for path in sorted(reports.rglob("results*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(document, dict) and document.get("trial") == trial:
            found.append(path)
    return found


def sentinel_path(reports: Path) -> Path:
    """A fixed place that says the trial was scored, whatever the results file was called."""
    return reports / "kronos_trial11" / SENTINEL_NAME


def check_forecasts(document: dict[str, Any]) -> list[str]:
    """Reasons the forecast file is not the declared trial's, or an empty list."""
    problems: list[str] = []
    expected = {
        "trial": TRIAL,
        "model_repo": "NeoQuasar/Kronos-base",
        "samples": 5,
        "forecast_count": EXPECTED_FORECASTS,
        "inputs_sha256": INPUTS_SHA256,
    }
    for key, wanted in expected.items():
        if document.get(key) != wanted:
            problems.append(f"{key} is {document.get(key)!r}, declared {wanted!r}")
    if len(document.get("forecasts", [])) != EXPECTED_FORECASTS:
        problems.append("the forecasts list does not hold the declared 23,805 records")
    return problems


def relabel(path: Path) -> None:
    """Correct the labels the scorer writes as trial-10 literals. No number is touched."""
    document = json.loads(path.read_text(encoding="utf-8"))
    document["trial"] = TRIAL
    document["declaration"] = DECLARATION
    document.setdefault("gate", {})["policy_id"] = f"kronos-trial-{TRIAL}"
    document["scored_by"] = (
        "scripts/score_kronos_trial11.py (scorer unmodified, multiplicity_count 11)"
    )
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def score(forecasts: Path, out: Path, *, reports: Path = ROOT_DIR / "reports") -> int:
    sentinel = sentinel_path(reports)
    spent = results_for_trial(reports) + ([sentinel] if sentinel.exists() else [])
    if out.exists() or spent:
        listed = ", ".join(str(p) for p in ([out] if out.exists() else []) + spent)
        print(f"REFUSED: trial {TRIAL} has already been scored ({listed}). The result stands.")
        return 2
    if not forecasts.is_file():
        print(f"REFUSED: no forecasts at {forecasts}")
        return 2
    problems = check_forecasts(json.loads(forecasts.read_text(encoding="utf-8")))
    if problems:
        print("REFUSED: these forecasts are not the declared trial 11's:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    import run_kronos_trial as scorer

    scorer.DECLARED_TRIALS = TRIAL
    code = int(scorer.main(["--forecasts", str(forecasts), "--out", str(out)]))
    if code == 0:
        relabel(out)
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(
            json.dumps({"trial": TRIAL, "scored_to": str(out), "forecasts": str(forecasts)}),
            encoding="utf-8",
        )
    return code


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    forecasts = Path(args[0]) if args else DEFAULT_FORECASTS
    out = Path(args[1]) if len(args) > 1 else DEFAULT_RESULTS
    return score(forecasts, out)


if __name__ == "__main__":
    raise SystemExit(main())
