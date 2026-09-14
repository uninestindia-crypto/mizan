"""Every published short-horizon DSR must be deflated against the frozen ledger's true trial count.

The defect these tests exist for
--------------------------------
``DECLARED_TRIALS`` was a literal ``6`` while ``reports/short_horizon/TRIAL-LEDGER.md`` had grown to
nine SPENT rows. Three trials were published in that window, each deflated against a search two
thirds its real size -- in the direction that flatters a candidate. Nothing failed, because nothing
connected the constant to the ledger.

So the binding is tested from both ends:

- the *code* refuses to run when its constant disagrees with the ledger
  (:mod:`quant_system.research_short_horizon.ledger`);
- the *artifacts* committed to this repository are checked to actually carry the corrected figures,
  because a fixed script and a stale JSON produce exactly the same wrong quotation.

The second half is the unusual one and it is deliberate. These tests read the real published results,
not fixtures. A fixture would prove the arithmetic and let the artifact rot.

What is deliberately NOT asserted
---------------------------------
That the raw metrics are correct. They are not: they predate the evaluator repair at ``056fb1c6``
(compounded overlapping positions, pooled abstention calibration, and a DSR sample length and
annualisation that disagreed). Re-deriving them means re-running nine trials. These tests pin the
*deflation* of the metrics that were published, which is a smaller and separately true claim.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from quant_system.analytics.multiplicity import OverfittingDiagnostics
from quant_system.research_short_horizon.ledger import (
    declared_spent_trials,
    read_spent_trials,
    require_declared_trials,
)

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "reports" / "short_horizon"
EXPERIMENT = REPO / "scripts" / "run_short_horizon_experiment.py"
RESCORER = REPO / "scripts" / "rescore_short_horizon_multiplicity.py"

RESULT_FILES = (
    "results-ridge.json",
    "results-timesfm.json",
    "results-timesfm25.json",
    "results-noise-control.json",
)

EXPECTED_SAMPLE_PERIODS = {"hold1": 2173, "hold2": 2172, "hold3": 2171}
"""Recovered by inversion, agreed by all four arms, and confirmed exactly by 90 unrounded draws.

Pinned here so that a future change to the recovery cannot quietly land on different lengths: the
whole re-scoring rests on these three integers, and they are not stored in the published artifacts.
"""

PUBLISHED_PERIODS_PER_YEAR = 252
"""The annualisation the pre-repair scorer used. Part of what the 90/90 reproduction confirms."""


def _load(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((REPORTS / name).read_text(encoding="utf-8"))
    return payload


def _candidate(trial: dict[str, Any]) -> dict[str, Any]:
    for score in trial["strategies"]:
        if score["strategy_id"] == "CANDIDATE":
            candidate: dict[str, Any] = score
            return candidate
    raise AssertionError("trial has no CANDIDATE row")


def _dsr(sharpe: float, trials: int, periods: int) -> float:
    return round(
        OverfittingDiagnostics.deflated_sharpe_ratio(
            estimated_sharpe=sharpe,
            num_trials=trials,
            sample_length_bars=periods,
            periods_per_year=PUBLISHED_PERIODS_PER_YEAR,
        ),
        6,
    )


def _trials(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (hold, trial) for hold, trial in sorted(payload["trials"].items()) if "strategies" in trial
    ]


# --------------------------------------------------------------------------------------
# The ledger is the authority, and the code is bound to it
# --------------------------------------------------------------------------------------


def test_the_ledger_records_nine_spent_trials() -> None:
    """Three families x three holds. If this moves, every DSR below must move with it."""
    assert declared_spent_trials() == 9


def test_the_control_and_the_calibration_grid_are_not_counted_as_trials() -> None:
    """NOISE and C1 consume no ordinal. Counting them would deflate real candidates unfairly."""
    numbers = {trial.number for trial in read_spent_trials()}
    assert numbers == set(range(1, 10))


def test_require_declared_trials_accepts_the_ledger_count() -> None:
    assert require_declared_trials(9) == 9


def test_require_declared_trials_refuses_a_stale_constant() -> None:
    """The exact regression: a constant of 6 against a ledger of 9 must stop the run."""
    with pytest.raises(ValueError, match="disagrees with"):
        require_declared_trials(6)


def test_the_refusal_says_which_way_the_error_flatters() -> None:
    """A reader must not have to work out whether a stale count helped or hurt the candidate."""
    with pytest.raises(ValueError, match="flatters every candidate"):
        require_declared_trials(6)
    with pytest.raises(ValueError, match="penalises every candidate"):
        require_declared_trials(12)


def test_a_missing_ledger_refuses_rather_than_defaulting(tmp_path: Path) -> None:
    """No denominator is not a denominator of zero, and must never be silently substituted."""
    with pytest.raises(FileNotFoundError):
        read_spent_trials(tmp_path / "absent.md")


def test_a_ledger_with_a_gap_is_refused(tmp_path: Path) -> None:
    """A gap means a trial was removed after its result was seen, which the ledger's rule forbids."""
    ledger = tmp_path / "TRIAL-LEDGER.md"
    ledger.write_text(
        "| # | Family | Hold | Status |\n| 1 | a | 1 | **SPENT** |\n| 3 | a | 3 | **SPENT** |\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not contiguous"):
        read_spent_trials(ledger)


def test_the_experiment_constant_matches_the_ledger() -> None:
    source = EXPERIMENT.read_text(encoding="utf-8")
    match = re.search(r"^DECLARED_TRIALS\s*=\s*(\d+)", source, flags=re.MULTILINE)
    assert match, "DECLARED_TRIALS is no longer a module-level literal"
    assert int(match.group(1)) == declared_spent_trials()


def test_the_experiment_verifies_the_count_at_run_time() -> None:
    """A CI-only check lets a wrong number reach an artifact before anything notices."""
    source = EXPERIMENT.read_text(encoding="utf-8")
    assert "require_declared_trials(DECLARED_TRIALS)" in source


# --------------------------------------------------------------------------------------
# The published artifacts actually carry the corrected figures
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", RESULT_FILES)
def test_every_results_file_declares_the_ledger_count(name: str) -> None:
    payload = _load(name)
    declared = declared_spent_trials()
    assert payload["declared_trials"] == declared
    for hold, trial in _trials(payload):
        assert trial["multiplicity_count"] == declared, f"{name} {hold}"


@pytest.mark.parametrize("name", RESULT_FILES)
def test_every_results_file_preserves_what_it_published(name: str) -> None:
    """The original figure survives the correction. Without it the delta is unauditable."""
    payload = _load(name)
    assert payload["declared_trials_as_published"] == 6
    for hold, trial in _trials(payload):
        assert trial["multiplicity_count_as_published"] == 6, f"{name} {hold}"
        assert "deflated_sharpe_ratio_as_published" in trial, f"{name} {hold}"


@pytest.mark.parametrize("name", RESULT_FILES)
def test_every_published_dsr_reproduces_from_its_stored_sharpe(name: str) -> None:
    """The recovery must explain the artifact it is correcting, to within its own rounding.

    Two of the twelve candidate rows land one unit-in-the-last-place away, because the stored Sharpe
    is itself rounded to six decimals. That is the entire tolerance permitted here -- anything larger
    would mean the scoring convention is not what the re-scoring believes it is.
    """
    payload = _load(name)
    for hold, trial in _trials(payload):
        sharpe = float(_candidate(trial)["sharpe"])
        published = float(trial["deflated_sharpe_ratio_as_published"])
        recomputed = _dsr(
            sharpe, trial["multiplicity_count_as_published"], EXPECTED_SAMPLE_PERIODS[hold]
        )
        assert abs(recomputed - published) <= 1e-6 + 1e-12, f"{name} {hold}"


@pytest.mark.parametrize("name", RESULT_FILES)
def test_every_rescored_dsr_recomputes_exactly(name: str) -> None:
    """The corrected value is not a stored opinion: it must fall out of the stored inputs."""
    payload = _load(name)
    for hold, trial in _trials(payload):
        sharpe = float(_candidate(trial)["sharpe"])
        expected = _dsr(sharpe, trial["multiplicity_count"], EXPECTED_SAMPLE_PERIODS[hold])
        assert trial["deflated_sharpe_ratio"] == expected, f"{name} {hold}"


def test_all_ninety_noise_draws_reproduce_exactly_at_both_counts() -> None:
    """The unfitted check. Per-seed Sharpes are unrounded, so a wrong sample length shows up at once."""
    payload = _load("results-noise-control.json")
    checked = 0
    for hold, trial in _trials(payload):
        periods = EXPECTED_SAMPLE_PERIODS[hold]
        for draw in trial["noise_distribution"]["draws"]:
            sharpe = float(draw["sharpe"])
            assert (
                _dsr(sharpe, draw["multiplicity_count_as_published"], periods)
                == (draw["deflated_sharpe_ratio_as_published"])
            ), f"{hold} seed {draw['seed']} (as published)"
            assert (
                _dsr(sharpe, draw["multiplicity_count"], periods) == (draw["deflated_sharpe_ratio"])
            ), f"{hold} seed {draw['seed']} (re-scored)"
            checked += 1
    assert checked == 90


def test_the_noise_order_statistics_match_their_own_draws() -> None:
    """The reports quote the median and the worst draw; both must come from the re-scored seeds."""
    payload = _load("results-noise-control.json")
    for hold, trial in _trials(payload):
        distribution = trial["noise_distribution"]
        ordered = sorted(draw["deflated_sharpe_ratio"] for draw in distribution["draws"])
        assert distribution["dsr_min"] == ordered[0], hold
        assert distribution["dsr_median"] == ordered[len(ordered) // 2], hold
        assert distribution["dsr_max"] == ordered[-1], hold


# --------------------------------------------------------------------------------------
# Properties the correction must have
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", RESULT_FILES)
def test_more_trials_never_raises_a_dsr(name: str) -> None:
    """Deflation is monotone in the attempt count. A correction that raised one would be a defect."""
    payload = _load(name)
    for hold, trial in _trials(payload):
        assert trial["deflated_sharpe_ratio"] <= trial["deflated_sharpe_ratio_as_published"], (
            f"{name} {hold}: re-scoring against a larger search raised the DSR"
        )


def test_the_rescoring_preserves_every_comparison_against_the_control() -> None:
    """Re-deflation is rank-preserving, so no conclusion may move -- only levels.

    This is what licenses every unchanged narrative sentence in the reports. If a single comparison
    flipped, those sentences would need re-reading rather than re-labelling.
    """
    noise = _load("results-noise-control.json")
    models = {name: _load(name) for name in RESULT_FILES[:3]}
    for hold, noise_trial in _trials(noise):
        draws = noise_trial["noise_distribution"]["draws"]
        for name, payload in models.items():
            trial = payload["trials"][hold]
            before = sum(
                1
                for d in draws
                if d["deflated_sharpe_ratio_as_published"]
                > trial["deflated_sharpe_ratio_as_published"]
            )
            after = sum(
                1 for d in draws if d["deflated_sharpe_ratio"] > trial["deflated_sharpe_ratio"]
            )
            assert before == after, (
                f"{name} {hold}: noise-beats-model count moved {before} -> {after}"
            )


@pytest.mark.parametrize("name", RESULT_FILES)
def test_nothing_became_promotable(name: str) -> None:
    """Re-scoring can only lower a DSR, so this can only fail if something else went wrong."""
    payload = _load(name)
    for hold, trial in _trials(payload):
        assert trial["gate_passed"] is False, f"{name} {hold}"
        assert trial["verdict"] == "RESEARCH_ONLY", f"{name} {hold}"
        assert trial["deflated_sharpe_ratio"] < float(trial["gate_min_deflated_sharpe"])


@pytest.mark.parametrize("name", RESULT_FILES)
def test_the_file_records_that_no_trial_was_run(name: str) -> None:
    """A re-scored artifact must not be mistakable for a fresh campaign."""
    payload = _load(name)
    assert payload["rescoring"]["trials_run"] == 0
    assert payload["rescoring"]["ordinals_spent"] == 0
    assert payload["rescoring"]["applied"] == "multiplicity_count_only"


@pytest.mark.parametrize("name", RESULT_FILES)
def test_the_file_discloses_that_raw_metrics_predate_the_evaluator_repair(name: str) -> None:
    """The correction this did NOT apply must travel with the one it did."""
    payload = _load(name)
    for hold, trial in _trials(payload):
        note = trial["rescoring"]
        assert note["raw_metrics_recomputed"] is False, f"{name} {hold}"
        assert note["raw_metrics_predate_evaluator_repair"] == "056fb1c6", f"{name} {hold}"


def test_the_rescorer_does_not_import_the_evaluation_path() -> None:
    """It must be structurally incapable of running a trial, not merely documented as not doing so."""
    source = RESCORER.read_text(encoding="utf-8")
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    joined = "\n".join(imports)
    for forbidden in (
        "research_short_horizon.evaluation",
        "research_short_horizon.walkforward",
        "train_mizan",
        "run_governed_ridge_training",
        "build_mizan_feature_store",
    ):
        assert forbidden not in joined, f"the re-scorer imports {forbidden}; it could run a trial"


def test_the_rescorer_is_idempotent() -> None:
    """Running it twice must equal running it once, or a check-in-CI would corrupt the artifacts."""
    spec = importlib.util.spec_from_file_location("_rescorer", RESCORER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)

    gate_policy = module.GatePolicyV1(policy_id="short-horizon-research-v1")
    for name in RESULT_FILES:
        payload = _load(name)
        for hold, trial in _trials(payload):
            once = json.loads(json.dumps(trial))
            twice = module.rescore_trial(
                json.loads(json.dumps(trial)),
                periods=EXPECTED_SAMPLE_PERIODS[hold],
                trials=declared_spent_trials(),
                gate=gate_policy,
            )
            assert twice["deflated_sharpe_ratio"] == once["deflated_sharpe_ratio"], f"{name} {hold}"
            assert (
                twice["deflated_sharpe_ratio_as_published"]
                == (once["deflated_sharpe_ratio_as_published"])
            ), f"{name} {hold}"
            assert twice["multiplicity_count_as_published"] == 6, f"{name} {hold}"


# --------------------------------------------------------------------------------------
# The prose artifacts must not still quote the superseded figures
# --------------------------------------------------------------------------------------

SUPERSEDED_HEADLINES = {
    "0.394441": "TimesFM 2.5 hold 3, published at 6 trials",
    "0.191369": "TimesFM 3.0 hold 3, published at 6 trials",
    "0.094711": "ridge hold 3, published at 6 trials",
}

PROSE_ARTIFACTS = (
    REPO / "reports" / "model_cards" / "README.md",
    REPO / "reports" / "short_horizon" / "COMPARISON-REPORT.md",
)


@pytest.mark.parametrize("path", PROSE_ARTIFACTS, ids=lambda p: p.name)
def test_summary_prose_does_not_lead_with_a_superseded_dsr(path: Path) -> None:
    """These two files are the entry points a reader quotes from, so they must not headline a stale
    figure. The detailed cards legitimately print the published value beside the corrected one, which
    is why only the summaries are checked here."""
    text = path.read_text(encoding="utf-8")
    for figure, description in SUPERSEDED_HEADLINES.items():
        if figure in text:
            assert "as published" in text or "previously" in text or "published at 6" in text, (
                f"{path.name} quotes {figure} ({description}) without marking it superseded"
            )
