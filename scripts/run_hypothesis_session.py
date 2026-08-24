"""Record a model-proposed strategy hypothesis, and optionally spend a trial ordinal on it.

This is the countable half of the advisory design. Asking a model what a stock will do tomorrow
produces an opinion nobody can account for; asking it to propose a *rule* produces one declared
attempt, and declared attempts can be counted and deflated against.

The runner does not call a model. The founder's workflow is a reasoning conversation with Claude or
ChatGPT; this records the result of that conversation with its provenance attached. A network call
here would add credentials, latency, and non-determinism to a step whose entire value is the
durable record — and `--knowledge-cutoff` has to be declared by a human regardless, because no
provider API reports it.

Recording a hypothesis costs nothing. Registering one spends an ordinal, permanently, and every
future deflated Sharpe in this journal's programme must discount against the resulting count.

Examples
--------
Record without spending an ordinal::

    python scripts/run_hypothesis_session.py \
        --journal data/advisory/hypotheses.jsonl \
        --title "Cross-sectional reversal on 5-day losers" \
        --proposed-rule "Rank NIFTY 50 by 5-day return; long the bottom decile, hold 5 sessions." \
        --reasoning-file tmp/claude-reasoning.txt \
        --prompt-file tmp/question.txt \
        --provider anthropic --model-id claude-opus-5 \
        --knowledge-cutoff 2026-05-01 \
        --execution-mode LIVE_MODEL

Show what has been spent so far::

    python scripts/run_hypothesis_session.py --journal data/advisory/hypotheses.jsonl --status
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from quant_system.advisory import (
    AdvisorInterface,
    AdvisoryError,
    AdvisoryJournal,
    ExecutionMode,
    HypothesisRegistry,
    ModelIdentity,
    capture_hypothesis,
)

EXIT_OK = 0
EXIT_REFUSED = 3


def _read_text(path: Path, label: str) -> str:
    if not path.is_file():
        raise SystemExit(f"{label} not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _parse_date(raw: str | None, label: str) -> date | None:
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise SystemExit(f"{label} must be an ISO date (YYYY-MM-DD): {raw}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_hypothesis_session",
        description="Record a model-proposed strategy hypothesis; optionally spend a trial ordinal.",
    )
    parser.add_argument("--journal", required=True, type=Path, help="advisory journal JSONL path")
    parser.add_argument(
        "--status",
        action="store_true",
        help="print the attempt count and recorded hypotheses, then exit without writing",
    )
    parser.add_argument("--title", help="short name for the hypothesis")
    parser.add_argument("--proposed-rule", help="the testable rule, stated precisely")
    parser.add_argument("--reasoning", help="the model's reasoning, inline")
    parser.add_argument("--reasoning-file", type=Path, help="the model's reasoning, from a file")
    parser.add_argument("--prompt", help="the question put to the model, inline")
    parser.add_argument(
        "--prompt-file", type=Path, help="the question put to the model, from a file"
    )
    parser.add_argument("--provider", help="e.g. anthropic, openai")
    parser.add_argument("--model-id", help="e.g. claude-opus-5")
    parser.add_argument("--model-version", help="optional version string")
    parser.add_argument(
        "--knowledge-cutoff",
        help="the model's declared training cutoff (YYYY-MM-DD). Omitting it makes hindsight "
        "UNDETERMINED rather than clean.",
    )
    parser.add_argument(
        "--execution-mode",
        choices=[mode.value for mode in ExecutionMode],
        help="how the hypothesis was produced. Required; there is deliberately no default.",
    )
    parser.add_argument("--universe-scope", help="e.g. NIFTY50")
    parser.add_argument(
        "--observation-window-end",
        help="last date of data the model was shown (YYYY-MM-DD)",
    )
    parser.add_argument("--hypothesis-id", help="override the content-derived id")
    parser.add_argument(
        "--register",
        action="store_true",
        help="spend the next trial ordinal on this hypothesis. Irreversible.",
    )
    return parser


def _deflation_note(spent: int) -> str:
    """State the multiplicity cost so it reads correctly at any count, including one."""
    if spent == 1:
        return (
            "This programme has spent 1 attempt. Every deflated Sharpe computed for it must "
            "discount against that count, and each further hypothesis raises it."
        )
    return (
        f"This programme has spent {spent} attempts. Every deflated Sharpe computed for it must "
        f"discount against {spent}, not against a single trial."
    )


def _print_status(registry: HypothesisRegistry) -> int:
    hypotheses = registry.hypotheses()
    spent = registry.attempt_count()
    print(f"journal: {registry.journal.path}")
    print(f"hypotheses recorded: {len(hypotheses)}")
    print(f"trial ordinals spent: {spent}")
    print(f"next ordinal would be: {registry.next_ordinal()}")
    if spent:
        print(f"\n{_deflation_note(spent)}")
    for record in hypotheses:
        ordinal = record.get("trial_ordinal")
        marker = f"ordinal {ordinal}" if ordinal is not None else "UNREGISTERED"
        print(f"  [{marker}] {record.get('hypothesis_id')} - {record.get('title')}")
    return EXIT_OK


def _require(args: argparse.Namespace, *names: str) -> None:
    missing = [f"--{name.replace('_', '-')}" for name in names if getattr(args, name) is None]
    if missing:
        raise SystemExit(f"missing required argument(s): {', '.join(missing)}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    journal = AdvisoryJournal(args.journal)
    registry = HypothesisRegistry(journal)

    if args.status:
        # Catching here reports and fails; it never substitutes a count. That distinction is the
        # whole point: `run_governed_promotion.py` deliberately lets `AdvisoryError` propagate,
        # because an unverifiable count must abort a promotion rather than deflate against a
        # smaller number. This is a human-facing CLI, so a stack trace is a presentation failure —
        # but the refusal must still be a refusal. Do not "recover" a partial count here.
        try:
            return _print_status(registry)
        except AdvisoryError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            print(
                "The attempt count cannot be trusted and is deliberately not reported. "
                "An unverifiable count must never be read as zero.",
                file=sys.stderr,
            )
            return EXIT_REFUSED

    _require(args, "title", "proposed_rule", "provider", "model_id", "execution_mode")

    if (args.reasoning is None) == (args.reasoning_file is None):
        raise SystemExit("supply exactly one of --reasoning or --reasoning-file")
    if (args.prompt is None) == (args.prompt_file is None):
        raise SystemExit("supply exactly one of --prompt or --prompt-file")

    reasoning = args.reasoning or _read_text(args.reasoning_file, "--reasoning-file")
    prompt = args.prompt or _read_text(args.prompt_file, "--prompt-file")
    cutoff = _parse_date(args.knowledge_cutoff, "--knowledge-cutoff")
    window_end = _parse_date(args.observation_window_end, "--observation-window-end")

    model = ModelIdentity(
        provider=args.provider,
        model_id=args.model_id,
        interface=AdvisorInterface.DIRECT_API,
        model_version=args.model_version,
        knowledge_cutoff=cutoff,
    )

    try:
        hypothesis = capture_hypothesis(
            title=args.title,
            model=model,
            prompt=prompt,
            reasoning=reasoning,
            proposed_rule=args.proposed_rule,
            execution_mode=ExecutionMode(args.execution_mode),
            recorded_at=datetime.now(UTC),
            hypothesis_id=args.hypothesis_id,
            universe_scope=args.universe_scope,
            observation_window_end=window_end,
        )
    except AdvisoryError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    try:
        if args.register:
            registered, _ = registry.register(hypothesis, datetime.now(UTC))
            hypothesis = registered
        else:
            registry.record(hypothesis)
    except AdvisoryError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_REFUSED

    print(f"hypothesis_id: {hypothesis.hypothesis_id}")
    print(f"hindsight:     {hypothesis.hindsight.value}")
    if hypothesis.hindsight.value == "CONTAMINATED":
        print(
            "  ^ the model's declared cutoff is later than the window it was shown, so it may "
            "already know how that period resolved. This cannot be prompted away."
        )
    if cutoff is None:
        print("  ^ no --knowledge-cutoff declared, so hindsight could not be computed.")

    if hypothesis.is_registered:
        print(f"trial_ordinal: {hypothesis.trial_ordinal} (SPENT, irreversible)")
        print(f"\n{_deflation_note(registry.attempt_count())}")
    else:
        print("trial_ordinal: none - UNREGISTERED")
        print(
            "\nRecorded only. Backtesting this without registering it would be undeclared "
            "multiplicity; `assert_registered_for_backtest()` will refuse."
        )
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
