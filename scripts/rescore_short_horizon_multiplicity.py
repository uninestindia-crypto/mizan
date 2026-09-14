"""Re-deflate every published short-horizon result against the frozen ledger's true trial count.

What this is, and the much larger thing it is not
-------------------------------------------------
Every short-horizon deflated Sharpe in this repository was computed with ``num_trials=6`` while
``reports/short_horizon/TRIAL-LEDGER.md`` had grown to **nine** SPENT rows. The deflation's benchmark
is built from that count, so each published DSR was scored against a search two thirds its real size
-- in the direction that flatters a candidate. This tool corrects that one input on the evidence
already stored, and nothing else.

**It runs no trial, spends no multiplicity ordinal, touches no holdout, and invokes no evaluator.**
It reads four JSON files, recomputes one closed-form statistic per row, and writes them back. It
imports ``OverfittingDiagnostics`` and the ledger parser; it deliberately imports nothing from
``research_short_horizon.evaluation``, and ``tests/test_short_horizon_rescoring.py`` enforces that.

There is a **second** outstanding correction that this tool does not perform and cannot. The
evaluator itself was repaired at ``056fb1c6`` -- overlapping positions were being compounded, the
abstention threshold was chosen and measured on the same rows, and the DSR's sample length and
annualisation disagreed with each other. Those repairs move the *raw* metrics, and recovering them
requires re-running the nine trials. So:

- the raw metrics here are preserved byte-identical and remain **pre-repair**;
- only the deflation of those metrics is corrected.

That is a smaller claim than "these numbers are now right", and it is the only one the stored
evidence supports. Every artifact this tool writes says so in those terms.

Recovering the sample length, which was never serialised
--------------------------------------------------------
The pre-repair ``summarise()`` (``6131d84a:scripts/run_short_horizon_experiment.py:200``) called
``deflated_sharpe_ratio(sharpe, num_trials=DECLARED_TRIALS, sample_length_bars=max(n, 3))`` with
``periods_per_year`` left at its default of 252, and it recorded neither ``n`` nor the annualisation.
Both must be recovered before anything can be re-deflated, so the tool solves for ``n`` by inversion
and refuses to write unless the answer is pinned three independent ways:

1. **Unique per arm.** For each (arm, hold) exactly one integer ``n`` must reproduce the published
   DSR at the published trial count, to the six decimals the artifact records. The tolerance is one
   unit in that last place, because the stored Sharpe is itself rounded to six decimals and a value
   inside its own rounding envelope can land either side of a boundary.
2. **Consensus across arms.** All four arms must agree on one ``n`` per hold. They do -- 2173 / 2172
   / 2171 at holds 1 / 2 / 3, one fewer decision date per extra held session, which is the
   arithmetic the harness would produce.
3. **Exact on unrounded data.** The noise control stores 30 per-seed Sharpes *unrounded*. All 90
   reproduce their published DSR exactly at the recovered lengths. Nothing about that check is
   fitted, which makes it the strongest of the three.

Independent corroboration, produced before this tool existed: the 2026-09-12 filer hand-computed the
re-deflation of trials 7-9 at nine and wrote ``0.118147 / 0.071891 / 0.312642`` into the ledger. All
three reproduce exactly from the recovered lengths.

Idempotence
-----------
A re-scored file preserves its originals under ``*_as_published`` keys, and a second run reads its
baseline from those rather than from the value it just wrote. Running this tool twice is therefore
the same as running it once, which is what makes it safe to wire into a check.

Usage
-----
``--check`` verifies and reports without writing anything; the default writes in place.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from quant_system.analytics.multiplicity import OverfittingDiagnostics  # noqa: E402
from quant_system.modeling.promotion import GatePolicyV1  # noqa: E402
from quant_system.research_short_horizon.ledger import declared_spent_trials  # noqa: E402

RESULT_FILES: tuple[tuple[str, str], ...] = (
    ("ridge", "results-ridge.json"),
    ("timesfm30", "results-timesfm.json"),
    ("timesfm25", "results-timesfm25.json"),
    ("noise", "results-noise-control.json"),
)
"""The four arms, and nothing else.

``results-noise-control.superseded-*.json`` is a superseded archive that the experiment script moved
aside when a stale run collided with a corrected one. It is history, and history is not re-scored.
"""

DECIMALS = 6
"""The precision every artifact records a DSR to. The re-scored values match it exactly."""

SEARCH_MAX_PERIODS = 4000
"""Upper bound of the sample-length search. The study spans ~2,400 sessions before the 252-session
holdout, so a true value anywhere near this bound would itself be evidence of a misunderstanding."""

PUBLISHED_PERIODS_PER_YEAR = 252
"""The pre-repair default. Confirmed by 90/90 exact reproductions on unrounded noise draws.

The repaired evaluator passes ``252 / held_sessions`` instead, which is the correct pairing with a
Sharpe annualised the same way. That is part of the *other* correction: re-deflating the published
figures under a convention they were not computed with would silently mix the two."""


class RescoreRefused(Exception):
    """Raised instead of writing a number the tool cannot stand behind."""


def _round(value: float) -> float:
    return round(value, DECIMALS)


def _tolerance() -> float:
    """One unit in the last recorded place, plus room for binary64 comparison residue."""
    return 10.0**-DECIMALS + 1e-12


def _dsr(sharpe: float, trials: int, periods: int) -> float:
    return OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=sharpe,
        num_trials=trials,
        sample_length_bars=periods,
        periods_per_year=PUBLISHED_PERIODS_PER_YEAR,
    )


def candidate_score(trial: dict[str, Any]) -> dict[str, Any]:
    """The ``CANDIDATE`` row, which is the only strategy the deflation is computed on.

    ``CASH``, ``ALWAYS_TRADE`` and ``PREVIOUS_SIGN`` are baselines: they are scored on identical
    decisions so the candidate can be read against them, but none is eligible for promotion and none
    carries a DSR.
    """
    scores: list[dict[str, Any]] = trial["strategies"]
    for score in scores:
        if score["strategy_id"] == "CANDIDATE":
            return score
    raise RescoreRefused("trial has no CANDIDATE strategy row")


def published_dsr(trial: dict[str, Any]) -> float:
    """The DSR as originally published, surviving any number of re-scorings."""
    if "deflated_sharpe_ratio_as_published" in trial:
        return float(trial["deflated_sharpe_ratio_as_published"])
    return float(trial["deflated_sharpe_ratio"])


def published_trials(trial: dict[str, Any]) -> int:
    """The trial count the published DSR was scored against, surviving re-scoring."""
    if "multiplicity_count_as_published" in trial:
        return int(trial["multiplicity_count_as_published"])
    return int(trial["multiplicity_count"])


def solve_sample_periods(sharpe: float, target: float, trials: int) -> set[int]:
    """Every integer sample length reproducing ``target`` at ``trials``, within one last place."""
    tolerance = _tolerance()
    return {
        periods
        for periods in range(3, SEARCH_MAX_PERIODS)
        if abs(_round(_dsr(sharpe, trials, periods)) - target) <= tolerance
    }


def recover_sample_periods(payloads: dict[str, dict[str, Any]]) -> dict[str, int]:
    """One sample length per hold, agreed by every arm, or a refusal.

    A per-arm solution set can legitimately be large -- at hold 1 the noise arm's DSR rounds to
    ``0.000000`` across a wide range of ``n``, so that arm constrains almost nothing on its own. The
    intersection is what identifies the value, and requiring it to be a singleton is what stops a
    degenerate arm from silently widening the answer.
    """
    per_hold: dict[str, list[tuple[str, set[int]]]] = {}
    for arm, payload in payloads.items():
        for hold, trial in payload["trials"].items():
            if "strategies" not in trial:
                continue
            candidate = candidate_score(trial)
            solutions = solve_sample_periods(
                float(candidate["sharpe"]), published_dsr(trial), published_trials(trial)
            )
            if not solutions:
                raise RescoreRefused(
                    f"{arm} {hold}: no sample length in [3, {SEARCH_MAX_PERIODS}) reproduces the "
                    f"published DSR {published_dsr(trial)} from Sharpe {candidate['sharpe']} at "
                    f"{published_trials(trial)} trials. The scoring convention is not what this "
                    "tool believes it is, and re-deflating on a guess would be worse than stopping."
                )
            per_hold.setdefault(hold, []).append((arm, solutions))

    recovered: dict[str, int] = {}
    for hold, entries in per_hold.items():
        agreed = set.intersection(*[solutions for _, solutions in entries])
        if len(agreed) != 1:
            detail = ", ".join(f"{arm}:{len(solutions)}" for arm, solutions in entries)
            raise RescoreRefused(
                f"{hold}: the arms do not agree on one sample length (candidates {sorted(agreed)}; "
                f"per-arm solution counts {detail}). Without agreement the recovered length is an "
                "assumption, not a measurement."
            )
        recovered[hold] = agreed.pop()
    return recovered


def verify_noise_draws(payload: dict[str, Any], periods_by_hold: dict[str, int]) -> tuple[int, int]:
    """Re-derive every per-seed DSR from its **unrounded** Sharpe. Returns (exact, total).

    This is the check that cannot be fitted: the noise draws store full-precision Sharpes, so a
    recovered sample length that is even one session wrong shows up immediately across 90 rows.
    """
    exact = total = 0
    for hold, trial in payload["trials"].items():
        distribution = trial.get("noise_distribution")
        if not distribution:
            continue
        for draw in distribution["draws"]:
            total += 1
            baseline = draw.get("deflated_sharpe_ratio_as_published", draw["deflated_sharpe_ratio"])
            trials = draw.get("multiplicity_count_as_published", published_trials(trial))
            recomputed = _round(_dsr(float(draw["sharpe"]), int(trials), periods_by_hold[hold]))
            if recomputed == float(baseline):
                exact += 1
    return exact, total


def rescore_trial(
    trial: dict[str, Any], *, periods: int, trials: int, gate: GatePolicyV1
) -> dict[str, Any]:
    """Re-deflate one trial in place. Every raw metric is left exactly as published."""
    candidate = candidate_score(trial)
    sharpe = float(candidate["sharpe"])
    was_trials = published_trials(trial)
    was_dsr = published_dsr(trial)

    reproduced = _round(_dsr(sharpe, was_trials, periods))
    rescored = _round(_dsr(sharpe, trials, periods))

    trial["deflated_sharpe_ratio_as_published"] = was_dsr
    trial["multiplicity_count_as_published"] = was_trials
    trial["deflated_sharpe_ratio"] = rescored
    trial["multiplicity_count"] = trials
    trial["gate_passed"] = (
        rescored >= float(gate.min_deflated_sharpe)
        and float(candidate["max_drawdown"]) <= float(gate.max_drawdown)
        and int(candidate["trades"]) >= gate.min_attributable_records
    )
    trial["verdict"] = "PROMOTABLE_PENDING_HOLDOUT" if trial["gate_passed"] else "RESEARCH_ONLY"
    trial["rescoring"] = {
        "applied": "multiplicity_count_only",
        "dsr_delta": _round(rescored - was_dsr),
        "periods_per_year": PUBLISHED_PERIODS_PER_YEAR,
        "raw_metrics_recomputed": False,
        "raw_metrics_predate_evaluator_repair": "056fb1c6",
        "reproduced_published_dsr": reproduced,
        "reproduction_exact": reproduced == was_dsr,
        "sample_length_bars": periods,
        "sample_length_recovered_by": "inversion, cross-arm consensus, 90/90 unrounded noise draws",
    }

    distribution = trial.get("noise_distribution")
    if distribution:
        _rescore_noise_distribution(distribution, periods=periods, trials=trials)
    return trial


def _rescore_noise_distribution(distribution: dict[str, Any], *, periods: int, trials: int) -> None:
    """Re-deflate all 30 seeds and rebuild the order statistics the reports quote."""
    for key in ("dsr_min", "dsr_median", "dsr_max", "dsr_p90"):
        distribution.setdefault(f"{key}_as_published", distribution[key])

    for draw in distribution["draws"]:
        if "deflated_sharpe_ratio_as_published" not in draw:
            draw["deflated_sharpe_ratio_as_published"] = draw["deflated_sharpe_ratio"]
            draw["multiplicity_count_as_published"] = draw.get("multiplicity_count", 6)
        draw["deflated_sharpe_ratio"] = _round(_dsr(float(draw["sharpe"]), trials, periods))
        draw["multiplicity_count"] = trials

    ordered = sorted(draw["deflated_sharpe_ratio"] for draw in distribution["draws"])
    distribution["dsr_min"] = ordered[0]
    distribution["dsr_median"] = ordered[len(ordered) // 2]
    distribution["dsr_max"] = ordered[-1]
    distribution["dsr_p90"] = ordered[int(0.9 * (len(ordered) - 1))]


def rescore(reports_dir: Path, *, check_only: bool) -> int:
    declared = declared_spent_trials()
    gate = GatePolicyV1(policy_id="short-horizon-research-v1")

    payloads: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    for arm, filename in RESULT_FILES:
        path = reports_dir / filename
        if not path.is_file():
            raise RescoreRefused(f"missing results file {path}")
        paths[arm] = path
        payloads[arm] = json.loads(path.read_text(encoding="utf-8"))

    print("=== SHORT-HORIZON RE-SCORING: multiplicity only ===")
    print(f"ledger           : {declared} SPENT trials (the corrected denominator)")
    print(f"mode             : {'CHECK, nothing written' if check_only else 'WRITE in place'}")

    periods_by_hold = recover_sample_periods(payloads)
    print(f"sample lengths   : {periods_by_hold} (recovered, cross-arm consensus)")

    exact, total = verify_noise_draws(payloads["noise"], periods_by_hold)
    print(f"noise draws      : {exact}/{total} reproduce their published DSR exactly")
    if exact != total:
        raise RescoreRefused(
            f"only {exact} of {total} unrounded noise draws reproduce. The recovered sample lengths "
            "or the annualisation are wrong, and every re-scored figure would inherit that."
        )

    inexact: list[str] = []
    for arm, payload in payloads.items():
        for hold, trial in sorted(payload["trials"].items()):
            if "strategies" not in trial:
                continue
            before = published_dsr(trial)
            rescore_trial(trial, periods=periods_by_hold[hold], trials=declared, gate=gate)
            note = trial["rescoring"]
            if not note["reproduction_exact"]:
                inexact.append(f"{arm} {hold}")
            flag = "" if note["reproduction_exact"] else "  [reproduces 1 ulp off, see below]"
            print(
                f"  {arm:10s} {hold}: {before:.6f} -> {trial['deflated_sharpe_ratio']:.6f} "
                f"({note['dsr_delta']:+.6f}){flag}"
            )
        payload["declared_trials_as_published"] = payload.get(
            "declared_trials_as_published", payload["declared_trials"]
        )
        payload["declared_trials"] = declared
        payload["rescoring"] = {
            "applied": "multiplicity_count_only",
            "note": (
                "Deflated Sharpe re-computed against the frozen ledger's true SPENT-trial count. "
                "Every raw metric is as originally published and PREDATES the evaluator repair at "
                "056fb1c6; this file corrects the deflation of those metrics, not the metrics."
            ),
            "ordinals_spent": 0,
            "sample_length_bars_by_hold": periods_by_hold,
            "tool": "scripts/rescore_short_horizon_multiplicity.py",
            "trials_run": 0,
        }

    if inexact:
        print(
            f"\n{len(inexact)} of 12 candidate rows reproduce one unit-in-last-place off "
            f"({', '.join(inexact)}). Expected: the stored Sharpe is itself rounded to 6 dp, and a "
            "value inside its own rounding envelope lands either side of that boundary. All 90 "
            "unrounded noise draws are exact."
        )

    promotable = [
        f"{arm} {hold}"
        for arm, payload in payloads.items()
        for hold, trial in payload["trials"].items()
        if trial.get("gate_passed")
    ]
    print(
        f"\ngate             : {len(promotable)} rows pass -> {promotable or 'NOTHING PROMOTABLE'}"
    )

    if check_only:
        print("\nCHECK ONLY: no file written.")
        return 0

    for arm, payload in payloads.items():
        paths[arm].write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"written          : {paths[arm]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=ROOT_DIR / "reports" / "short_horizon")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the recovery and report the deltas without writing anything",
    )
    args = parser.parse_args()
    try:
        return rescore(args.reports_dir, check_only=args.check)
    except RescoreRefused as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
