"""The hypothesis session runner records provenance and refuses to guess at it."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_system.advisory import AdvisoryJournal, HypothesisRegistry
from scripts.run_hypothesis_session import EXIT_OK, EXIT_REFUSED, main

BASE_ARGS = [
    "--title",
    "Cross-sectional reversal on 5-day losers",
    "--proposed-rule",
    "Rank NIFTY 50 by 5-day return; long the bottom decile, hold 5 sessions.",
    "--reasoning",
    "Short-horizon reversal is documented in Indian equities.",
    "--prompt",
    "What short-horizon pattern is worth testing on NIFTY 50?",
    "--provider",
    "anthropic",
    "--model-id",
    "claude-opus-5",
    "--execution-mode",
    "LIVE_MODEL",
]


def _args(journal: Path, *extra: str) -> list[str]:
    return ["--journal", str(journal), *BASE_ARGS, *extra]


@pytest.fixture
def journal_path(tmp_path: Path) -> Path:
    return tmp_path / "hypotheses.jsonl"


def test_recording_without_registering_spends_no_ordinal(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_args(journal_path)) == EXIT_OK

    out = capsys.readouterr().out
    assert "UNREGISTERED" in out
    assert "undeclared multiplicity" in out

    registry = HypothesisRegistry(AdvisoryJournal(journal_path))
    assert registry.attempt_count() == 0
    assert len(registry.hypotheses()) == 1


def test_registering_spends_an_ordinal_and_says_so(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_args(journal_path, "--register")) == EXIT_OK

    out = capsys.readouterr().out
    assert "trial_ordinal: 1 (SPENT, irreversible)" in out
    assert "has spent 1 attempt." in out
    assert "discount against that count" in out
    assert HypothesisRegistry(AdvisoryJournal(journal_path)).attempt_count() == 1


def test_ordinals_accumulate_across_sessions(journal_path: Path) -> None:
    main(_args(journal_path, "--register"))
    main(
        [
            "--journal",
            str(journal_path),
            "--title",
            "Second idea",
            "--proposed-rule",
            "Something else entirely.",
            "--reasoning",
            "Different reasoning.",
            "--prompt",
            "Another question.",
            "--provider",
            "openai",
            "--model-id",
            "gpt-nonexistent",
            "--execution-mode",
            "LIVE_MODEL",
            "--register",
        ]
    )
    assert HypothesisRegistry(AdvisoryJournal(journal_path)).attempt_count() == 2


def test_registering_the_same_hypothesis_twice_is_refused(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_args(journal_path, "--register")) == EXIT_OK
    assert main(_args(journal_path, "--register")) == EXIT_REFUSED

    assert "REFUSED" in capsys.readouterr().err
    assert HypothesisRegistry(AdvisoryJournal(journal_path)).attempt_count() == 1


# --- provenance is required, never guessed ------------------------------------------------------


@pytest.mark.parametrize(
    "drop",
    ["--title", "--proposed-rule", "--provider", "--model-id", "--execution-mode"],
)
def test_missing_provenance_is_rejected(journal_path: Path, drop: str) -> None:
    args = _args(journal_path)
    index = args.index(drop)
    del args[index : index + 2]
    with pytest.raises(SystemExit):
        main(args)


def test_execution_mode_has_no_default(journal_path: Path) -> None:
    """A default of LIVE_MODEL would let an unattributed paste look like a model response."""
    args = _args(journal_path)
    index = args.index("--execution-mode")
    del args[index : index + 2]
    with pytest.raises(SystemExit) as excinfo:
        main(args)
    assert "--execution-mode" in str(excinfo.value)


def test_reasoning_must_come_from_exactly_one_source(journal_path: Path, tmp_path: Path) -> None:
    reasoning_file = tmp_path / "reasoning.txt"
    reasoning_file.write_text("from a file", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        main(_args(journal_path, "--reasoning-file", str(reasoning_file)))
    assert "exactly one" in str(excinfo.value)


def test_reasoning_can_be_read_from_a_file(journal_path: Path, tmp_path: Path) -> None:
    reasoning_file = tmp_path / "reasoning.txt"
    reasoning_file.write_text("Momentum decays over five sessions.", encoding="utf-8")
    args = _args(journal_path)
    index = args.index("--reasoning")
    del args[index : index + 2]

    assert main([*args, "--reasoning-file", str(reasoning_file)]) == EXIT_OK
    record = HypothesisRegistry(AdvisoryJournal(journal_path)).hypotheses()[0]
    assert record["reasoning"] == "Momentum decays over five sessions."


def test_a_missing_reasoning_file_is_reported(journal_path: Path, tmp_path: Path) -> None:
    args = _args(journal_path)
    index = args.index("--reasoning")
    del args[index : index + 2]
    with pytest.raises(SystemExit) as excinfo:
        main([*args, "--reasoning-file", str(tmp_path / "absent.txt")])
    assert "not found" in str(excinfo.value)


# --- hindsight ----------------------------------------------------------------------------------


def test_hindsight_is_undetermined_without_a_declared_cutoff(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(_args(journal_path))
    out = capsys.readouterr().out
    assert "hindsight:     UNDETERMINED" in out
    assert "no --knowledge-cutoff declared" in out


def test_contamination_is_reported_loudly(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(
        _args(
            journal_path,
            "--knowledge-cutoff",
            "2026-05-01",
            "--observation-window-end",
            "2024-12-31",
        )
    )
    out = capsys.readouterr().out
    assert "hindsight:     CONTAMINATED" in out
    assert "cannot be prompted away" in out


def test_a_cutoff_before_the_window_is_clean(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(
        _args(
            journal_path,
            "--knowledge-cutoff",
            "2023-12-31",
            "--observation-window-end",
            "2024-12-31",
        )
    )
    assert "hindsight:     CLEAN" in capsys.readouterr().out


def test_a_malformed_date_is_rejected(journal_path: Path) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(_args(journal_path, "--knowledge-cutoff", "May 2026"))
    assert "ISO date" in str(excinfo.value)


# --- status -------------------------------------------------------------------------------------


def test_status_reports_the_attempt_count(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(_args(journal_path, "--register"))
    capsys.readouterr()

    assert main(["--journal", str(journal_path), "--status"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "trial ordinals spent: 1" in out
    assert "next ordinal would be: 2" in out
    assert "has spent 1 attempt." in out


def test_status_on_an_empty_journal_writes_nothing(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--journal", str(journal_path), "--status"]) == EXIT_OK
    assert "trial ordinals spent: 0" in capsys.readouterr().out
    assert not journal_path.exists()


def test_the_deflation_note_reads_correctly_at_a_count_of_one(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ "against 1, not against one" was the earlier wording, and it read as nonsense."""
    main(_args(journal_path, "--register"))
    out = capsys.readouterr().out
    assert "not against a single trial" not in out
    assert "has spent 1 attempt." in out


def test_the_deflation_note_pluralises_beyond_one(
    journal_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(_args(journal_path, "--register"))
    main(
        [
            "--journal",
            str(journal_path),
            "--title",
            "Second idea",
            "--proposed-rule",
            "Something else entirely.",
            "--reasoning",
            "Different reasoning.",
            "--prompt",
            "Another question.",
            "--provider",
            "openai",
            "--model-id",
            "gpt-nonexistent",
            "--execution-mode",
            "LIVE_MODEL",
            "--register",
        ]
    )
    out = capsys.readouterr().out
    assert "has spent 2 attempts" in out
    assert "discount against 2, not against a single trial" in out
