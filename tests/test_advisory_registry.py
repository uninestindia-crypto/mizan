"""Trial ordinals come from the journal's history, and a tampered journal cannot under-count."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.advisory import (
    AdvisorInterface,
    AdvisoryError,
    AdvisoryFailureCode,
    AdvisoryJournal,
    ExecutionMode,
    HypothesisRegistry,
    ModelIdentity,
    StrategyHypothesisRecord,
    capture_hypothesis,
)

RECORDED_AT = datetime(2026, 8, 23, 9, 0, 0, tzinfo=UTC)

MODEL = ModelIdentity(
    provider="anthropic",
    model_id="claude-opus-5",
    interface=AdvisorInterface.DIRECT_API,
    knowledge_cutoff=date(2026, 5, 1),
)


def _hypothesis(title: str, rule: str = "long the bottom decile") -> StrategyHypothesisRecord:
    return capture_hypothesis(
        title=title,
        model=MODEL,
        prompt=f"what about {title}",
        reasoning="documented in Indian equities",
        proposed_rule=rule,
        execution_mode=ExecutionMode.LIVE_MODEL,
        recorded_at=RECORDED_AT,
        universe_scope="NIFTY50",
        observation_window_end=date(2024, 12, 31),
    )


@pytest.fixture
def registry(tmp_path: Path) -> HypothesisRegistry:
    return HypothesisRegistry(AdvisoryJournal(tmp_path / "hypotheses.jsonl"))


# --- counting ---------------------------------------------------------------------------------


def test_an_empty_journal_has_spent_nothing(registry: HypothesisRegistry) -> None:
    assert registry.attempt_count() == 0
    assert registry.next_ordinal() == 1


def test_recording_does_not_spend_an_ordinal(registry: HypothesisRegistry) -> None:
    registry.record(_hypothesis("reversal"))
    assert registry.attempt_count() == 0
    assert registry.next_ordinal() == 1
    assert len(registry.hypotheses()) == 1


def test_registering_spends_one_ordinal(registry: HypothesisRegistry) -> None:
    registered, _ = registry.register(_hypothesis("reversal"), RECORDED_AT)
    assert registered.trial_ordinal == 1
    assert registry.attempt_count() == 1
    assert registry.next_ordinal() == 2


def test_ordinals_increase_across_registrations(registry: HypothesisRegistry) -> None:
    ordinals = [
        registry.register(_hypothesis(f"idea {n}", rule=f"rule {n}"), RECORDED_AT)[0].trial_ordinal
        for n in range(1, 4)
    ]
    assert ordinals == [1, 2, 3]
    assert registry.attempt_count() == 3


def test_unregistered_records_do_not_inflate_the_count(registry: HypothesisRegistry) -> None:
    registry.record(_hypothesis("draft one", rule="rule a"))
    registry.record(_hypothesis("draft two", rule="rule b"))
    registry.register(_hypothesis("the real attempt", rule="rule c"), RECORDED_AT)
    assert registry.attempt_count() == 1
    assert len(registry.hypotheses()) == 3


def test_the_count_survives_reopening(tmp_path: Path) -> None:
    path = tmp_path / "hypotheses.jsonl"
    HypothesisRegistry(AdvisoryJournal(path)).register(_hypothesis("first"), RECORDED_AT)
    reopened = HypothesisRegistry(AdvisoryJournal(path))
    assert reopened.attempt_count() == 1
    assert reopened.next_ordinal() == 2


# --- the guards -------------------------------------------------------------------------------


def test_registering_the_same_hypothesis_twice_is_refused(registry: HypothesisRegistry) -> None:
    """A second ordinal on one idea would inflate the count and over-deflate."""
    hypothesis = _hypothesis("reversal")
    registry.register(hypothesis, RECORDED_AT)
    with pytest.raises(AdvisoryError) as excinfo:
        registry.register(hypothesis, RECORDED_AT)
    assert excinfo.value.code is AdvisoryFailureCode.HYPOTHESIS_ALREADY_REGISTERED
    assert registry.attempt_count() == 1


def test_recording_an_already_registered_record_is_refused(registry: HypothesisRegistry) -> None:
    registered, _ = registry.register(_hypothesis("reversal"), RECORDED_AT)
    with pytest.raises(AdvisoryError) as excinfo:
        registry.record(registered)
    assert excinfo.value.code is AdvisoryFailureCode.HYPOTHESIS_ALREADY_REGISTERED


def test_an_unregistered_hypothesis_refuses_to_be_backtested(registry: HypothesisRegistry) -> None:
    hypothesis = _hypothesis("reversal")
    registry.record(hypothesis)
    with pytest.raises(AdvisoryError) as excinfo:
        hypothesis.assert_registered_for_backtest()
    assert excinfo.value.code is AdvisoryFailureCode.HYPOTHESIS_NOT_REGISTERED


def test_a_registered_hypothesis_may_be_backtested(registry: HypothesisRegistry) -> None:
    registered, _ = registry.register(_hypothesis("reversal"), RECORDED_AT)
    registered.assert_registered_for_backtest()


# --- tamper resistance ------------------------------------------------------------------------


def test_deleting_a_row_cannot_lower_the_attempt_count(registry: HypothesisRegistry) -> None:
    """The load-bearing property: a shrinking count would weaken every future deflation."""
    for n in range(1, 4):
        registry.register(_hypothesis(f"idea {n}", rule=f"rule {n}"), RECORDED_AT)
    assert registry.attempt_count() == 3

    lines = registry.journal.path.read_text(encoding="utf-8").splitlines()
    registry.journal.path.write_text("".join(f"{line}\n" for line in lines[:-1]), encoding="utf-8")

    with pytest.raises(AdvisoryError) as excinfo:
        registry.attempt_count()
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_TRUNCATED


def test_registering_onto_a_tampered_journal_is_refused(registry: HypothesisRegistry) -> None:
    registry.register(_hypothesis("first"), RECORDED_AT)
    registry.register(_hypothesis("second", rule="rule b"), RECORDED_AT)

    lines = registry.journal.path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    payload["record"]["trial_ordinal"] = 99
    lines[0] = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    registry.journal.path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    with pytest.raises(AdvisoryError) as excinfo:
        registry.register(_hypothesis("third", rule="rule c"), RECORDED_AT)
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_CHAIN_BROKEN


def test_opinions_in_the_same_journal_are_not_counted_as_attempts(
    registry: HypothesisRegistry,
) -> None:
    """Advisory opinions share the journal; only hypotheses spend ordinals."""
    from quant_system.advisory import ActionBias, AdvisoryOpinionRecord

    registry.journal.append(
        AdvisoryOpinionRecord(
            recorded_at=RECORDED_AT,
            advisor_name="Claude_Macro_Advisor",
            model=MODEL,
            execution_mode=ExecutionMode.LIVE_MODEL,
            symbol="INFY",
            action_bias=ActionBias.BULLISH,
            confidence=Decimal("0.6"),
            weight_multiplier=Decimal("1"),
            rationale="trend intact",
            prompt_sha256="0" * 64,
            anchored_on_quant_signal=False,
        )
    )
    registry.register(_hypothesis("reversal"), RECORDED_AT)
    assert registry.attempt_count() == 1
    assert len(registry.hypotheses()) == 1
