"""Trial 11 (Kronos-base, five paths): the runner, the inputs and the once-only scoring wrapper.

The trial is one run, scored once, on whichever machine finishes first. Everything that could quietly make it a
different trial, or a second one, has a test here: a modified generator, inputs that are not the declared data, a
fallback to fewer paths, a forecast file from the wrong trial, and a second scoring.
"""

from __future__ import annotations

import gzip
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import kronos_trial11 as runner  # noqa: E402
import score_kronos_trial11 as wrapper  # noqa: E402

GENERATOR = REPO_ROOT / "scripts" / "generate_kronos_forecasts.py"
SCORER = REPO_ROOT / "scripts" / "run_kronos_trial.py"
INPUTS = REPO_ROOT / "reports" / "kronos_trial11" / "kronos-inputs.json.gz"
LEDGER = REPO_ROOT / "reports" / "kronos_trial11" / "TRIAL-LEDGER.md"


@pytest.fixture(scope="module")
def generator() -> Any:
    return runner.load_generator(GENERATOR)


# --------------------------------------------------------------------------------------------------
# The declared generator is what runs
# --------------------------------------------------------------------------------------------------


def test_the_pinned_generator_hash_is_the_real_generators() -> None:
    assert runner.sha256_file(GENERATOR) == runner.GENERATOR_SHA256


def test_a_modified_generator_is_refused(tmp_path: Path) -> None:
    tampered = tmp_path / "generate_kronos_forecasts.py"
    tampered.write_bytes(GENERATOR.read_bytes() + b"\n# one extra line\n")

    with pytest.raises(SystemExit, match="declared"):
        runner.load_generator(tampered)


def test_the_scorer_is_the_one_the_declaration_pins() -> None:
    assert runner.sha256_file(SCORER) in LEDGER.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------------------
# The inputs are the declared data
# --------------------------------------------------------------------------------------------------


def test_the_inputs_file_is_the_declared_one() -> None:
    assert runner.sha256_file(INPUTS) == wrapper.INPUTS_SHA256


def test_the_inputs_reproduce_the_declared_plan(generator: Any) -> None:
    bars = runner.read_inputs(INPUTS, generator)

    assert runner.plan_summary(generator, bars) == (
        runner.EXPECTED_NAMES,
        runner.EXPECTED_DATES,
        runner.EXPECTED_FORECASTS,
    )


def test_inputs_survive_a_write_and_read_unchanged(generator: Any, tmp_path: Path) -> None:
    bar = generator.Bar
    bars = {
        "AAA": [bar(date(2024, 7, 1), 100.1, 101.25, 99.0, 100.5, 12345.0)],
        "BBB": [bar(date(2024, 7, 2), 0.1 + 0.2, 3.0, 0.0001, 1 / 3, 7.0)],
    }
    path = tmp_path / "inputs.json.gz"

    runner.write_inputs(bars, path)

    assert runner.read_inputs(path, generator) == bars


def test_inputs_are_written_deterministically(generator: Any, tmp_path: Path) -> None:
    bars = {"AAA": [generator.Bar(date(2024, 7, 1), 1.0, 2.0, 0.5, 1.5, 10.0)]}
    first, second = tmp_path / "a.json.gz", tmp_path / "b.json.gz"

    runner.write_inputs(bars, first)
    runner.write_inputs(bars, second)

    assert first.read_bytes() == second.read_bytes()


def test_a_file_that_is_not_the_inputs_schema_is_refused(generator: Any, tmp_path: Path) -> None:
    other = tmp_path / "other.json.gz"
    other.write_bytes(gzip.compress(json.dumps({"schema": "something-else"}).encode()))

    with pytest.raises(SystemExit, match="kronos-trial11-inputs-v1"):
        runner.read_inputs(other, generator)


# --------------------------------------------------------------------------------------------------
# Device and code
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("requested", "cuda", "expected"),
    [("auto", True, "cuda"), ("auto", False, "cpu"), ("cpu", True, "cpu"), ("cuda", True, "cuda")],
)
def test_device_resolution(requested: str, cuda: bool, expected: str) -> None:
    assert runner.resolve_device(requested, cuda) == expected


def test_asking_for_a_gpu_that_is_absent_is_an_error_not_a_quiet_downgrade() -> None:
    with pytest.raises(SystemExit, match="no CUDA device"):
        runner.resolve_device("cuda", False)


def test_missing_or_altered_kronos_code_is_refused(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    (model / "__init__.py").write_text("x", encoding="utf-8")

    with pytest.raises(SystemExit, match="declared Kronos code"):
        runner.verify_code(tmp_path)


# --------------------------------------------------------------------------------------------------
# The declaration and the code agree
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        runner.GENERATOR_SHA256,
        wrapper.INPUTS_SHA256,
        runner.KRONOS_CODE_COMMIT,
        *runner.KRONOS_CODE_SHA256.values(),
        *(revision for revision, _sha in runner.WEIGHTS.values()),
        *(sha for _revision, sha in runner.WEIGHTS.values()),
    ],
)
def test_every_pinned_value_is_written_in_the_declaration(value: str) -> None:
    assert value in LEDGER.read_text(encoding="utf-8")


def test_the_trial_is_base_with_five_paths() -> None:
    assert (runner.MODEL_KEY, runner.SAMPLES, runner.TRIAL) == ("base", 5, 11)


# --------------------------------------------------------------------------------------------------
# Scoring happens once, on the declared forecasts, against eleven attempts
# --------------------------------------------------------------------------------------------------


def _declared_forecast_file() -> dict[str, Any]:
    return {
        "trial": 11,
        "model_repo": "NeoQuasar/Kronos-base",
        "samples": 5,
        "forecast_count": wrapper.EXPECTED_FORECASTS,
        "inputs_sha256": wrapper.INPUTS_SHA256,
        "forecasts": [{}] * wrapper.EXPECTED_FORECASTS,
    }


def test_the_declared_forecast_file_passes_the_integrity_check() -> None:
    assert wrapper.check_forecasts(_declared_forecast_file()) == []


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("trial", 10),
        ("model_repo", "NeoQuasar/Kronos-small"),
        ("samples", 1),
        ("forecast_count", 100),
        ("inputs_sha256", "0" * 64),
    ],
)
def test_forecasts_from_any_other_configuration_are_refused(field: str, wrong: object) -> None:
    document = _declared_forecast_file()
    document[field] = wrong

    assert wrapper.check_forecasts(document)


def test_a_truncated_forecast_list_is_refused() -> None:
    document = _declared_forecast_file()
    document["forecasts"] = [{}] * 10

    assert wrapper.check_forecasts(document)


def test_trial_ten_forecasts_cannot_be_scored_as_trial_eleven(tmp_path: Path) -> None:
    trial_ten = tmp_path / "f.json"
    trial_ten.write_text(
        json.dumps({"model_repo": "NeoQuasar/Kronos-small", "samples": 1, "forecasts": []}),
        encoding="utf-8",
    )

    assert wrapper.score(trial_ten, tmp_path / "out.json", reports=tmp_path) == 2
    assert not (tmp_path / "out.json").exists()


def test_a_results_file_for_trial_eleven_anywhere_blocks_scoring(tmp_path: Path) -> None:
    elsewhere = tmp_path / "some" / "other" / "place"
    elsewhere.mkdir(parents=True)
    (elsewhere / "results-from-another-machine.json").write_text(
        json.dumps({"trial": 11}), encoding="utf-8"
    )
    forecasts = tmp_path / "f.json"
    forecasts.write_text(json.dumps(_declared_forecast_file()), encoding="utf-8")

    assert wrapper.score(forecasts, tmp_path / "out.json", reports=tmp_path) == 2
    assert not (tmp_path / "out.json").exists()


def test_a_trial_ten_results_file_does_not_block_trial_eleven(tmp_path: Path) -> None:
    (tmp_path / "results-kronos.json").write_text(json.dumps({"trial": 10}), encoding="utf-8")

    assert wrapper.results_for_trial(tmp_path) == []


def test_scoring_deflates_against_eleven_and_relabels_only_the_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import run_kronos_trial as scorer

    seen: dict[str, Any] = {}

    def fake_main(argv: list[str]) -> int:
        seen["trials_during_call"] = scorer.DECLARED_TRIALS
        out = Path(argv[argv.index("--out") + 1])
        out.write_text(
            json.dumps(
                {
                    "trial": 10,
                    "declaration": "reports/kronos_trial/TRIAL-LEDGER.md",
                    "gate": {"policy_id": "kronos-trial-10", "passed": False},
                    "candidate_dsr": 0.0123,
                    "multiplicity_count": scorer.DECLARED_TRIALS,
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(scorer, "main", fake_main)
    monkeypatch.setattr(scorer, "DECLARED_TRIALS", 10)
    forecasts = tmp_path / "f.json"
    forecasts.write_text(json.dumps(_declared_forecast_file()), encoding="utf-8")
    out = tmp_path / "results.json"

    assert wrapper.score(forecasts, out, reports=tmp_path) == 0

    result = json.loads(out.read_text(encoding="utf-8"))
    assert seen["trials_during_call"] == 11
    assert result["multiplicity_count"] == 11
    assert (result["trial"], result["gate"]["policy_id"]) == (11, "kronos-trial-11")
    assert result["declaration"] == wrapper.DECLARATION
    assert result["candidate_dsr"] == 0.0123


def test_a_second_scoring_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import run_kronos_trial as scorer

    calls = SimpleNamespace(count=0)

    def fake_main(argv: list[str]) -> int:
        calls.count += 1
        Path(argv[argv.index("--out") + 1]).write_text(json.dumps({"trial": 10}), encoding="utf-8")
        return 0

    monkeypatch.setattr(scorer, "main", fake_main)
    forecasts = tmp_path / "f.json"
    forecasts.write_text(json.dumps(_declared_forecast_file()), encoding="utf-8")

    first = wrapper.score(forecasts, tmp_path / "one.json", reports=tmp_path)
    second = wrapper.score(forecasts, tmp_path / "two.json", reports=tmp_path)

    assert (first, second) == (0, 2)
    assert calls.count == 1
    assert not (tmp_path / "two.json").exists()
    assert wrapper.sentinel_path(tmp_path).is_file()


def test_the_sentinel_alone_blocks_scoring_whatever_the_output_is_called(tmp_path: Path) -> None:
    sentinel = wrapper.sentinel_path(tmp_path)
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text(json.dumps({"trial": 11}), encoding="utf-8")
    forecasts = tmp_path / "f.json"
    forecasts.write_text(json.dumps(_declared_forecast_file()), encoding="utf-8")

    assert wrapper.score(forecasts, tmp_path / "any-name-at-all.txt", reports=tmp_path) == 2
    assert not (tmp_path / "any-name-at-all.txt").exists()


def test_a_scoring_that_fails_leaves_no_sentinel_so_it_can_be_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import run_kronos_trial as scorer

    monkeypatch.setattr(scorer, "main", lambda _argv: 1)
    forecasts = tmp_path / "f.json"
    forecasts.write_text(json.dumps(_declared_forecast_file()), encoding="utf-8")

    assert wrapper.score(forecasts, tmp_path / "out.json", reports=tmp_path) == 1
    assert not wrapper.sentinel_path(tmp_path).exists()


# --------------------------------------------------------------------------------------------------
# The downloadable package
# --------------------------------------------------------------------------------------------------

PACKAGE = REPO_ROOT / "reports" / "kronos_trial11" / runner.PACKAGE_NAME


def test_the_package_holds_exactly_what_a_machine_without_the_repo_needs(tmp_path: Path) -> None:
    import zipfile

    built = tmp_path / runner.PACKAGE_NAME
    runner.build_package(REPO_ROOT, built)

    with zipfile.ZipFile(built) as archive:
        names = sorted(archive.namelist())
        generator_bytes = archive.read("generate_kronos_forecasts.py")

    assert names == sorted(
        [
            "generate_kronos_forecasts.py",
            "kronos_trial11.py",
            "kronos-inputs.json.gz",
            "README.md",
            "TRIAL-LEDGER.md",
        ]
    )
    assert generator_bytes == GENERATOR.read_bytes()


def test_the_package_is_built_deterministically(tmp_path: Path) -> None:
    first, second = tmp_path / "a.zip", tmp_path / "b.zip"

    runner.build_package(REPO_ROOT, first)
    runner.build_package(REPO_ROOT, second)

    assert first.read_bytes() == second.read_bytes()


def test_the_committed_package_is_not_stale(tmp_path: Path) -> None:
    """If the runner, README, ledger or inputs change, the zip people download must be rebuilt."""
    rebuilt = tmp_path / runner.PACKAGE_NAME
    runner.build_package(REPO_ROOT, rebuilt)

    assert PACKAGE.read_bytes() == rebuilt.read_bytes()
