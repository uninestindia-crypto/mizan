"""Trial-ordinal registration for model-proposed strategy hypotheses.

A hypothesis is the countable use of a reasoning model. A per-bar forecast cannot be deflated
against — the attempts are unbounded and invisible — but a proposed *rule* is one declared attempt,
and declared attempts can be counted and discounted.

The count comes from the journal, never from the caller. An ordinal a human types is a number, not
a count; only a figure derived from durable, tamper-evident history can honestly feed a deflation.
`agent_context/CURRENT.md` records what is at stake: GRASIM's published deflated Sharpe of
``0.696673`` looked nearly promotable and fell to ``0.397794`` once re-deflated against the real
attempt count of 51.

Nothing here computes a promotion statistic. The registry reports an attempt count; a governed
runner decides what to do with it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from quant_system.advisory.errors import AdvisoryError, AdvisoryFailureCode
from quant_system.advisory.journal import AdvisoryJournal, JournalEntry
from quant_system.advisory.records import AdvisoryRecordType, StrategyHypothesisRecord


def _ordinal_of(record: Mapping[str, Any]) -> int | None:
    """A registered hypothesis carries an int ordinal. `bool` is excluded — it subclasses `int`."""
    ordinal = record.get("trial_ordinal")
    if isinstance(ordinal, int) and not isinstance(ordinal, bool):
        return ordinal
    return None


def _spent_ordinals(records: Sequence[Mapping[str, Any]]) -> list[int]:
    return [ordinal for record in records if (ordinal := _ordinal_of(record)) is not None]


class HypothesisRegistry:
    """Records hypotheses and spends trial ordinals drawn from the journal's own history."""

    def __init__(self, journal: AdvisoryJournal) -> None:
        self.journal = journal

    def record(self, hypothesis: StrategyHypothesisRecord) -> JournalEntry:
        """Append an unregistered hypothesis. It cannot be backtested until it is registered."""
        if hypothesis.is_registered:
            raise AdvisoryError(
                AdvisoryFailureCode.HYPOTHESIS_ALREADY_REGISTERED,
                (
                    f"hypothesis {hypothesis.hypothesis_id} already holds ordinal "
                    f"{hypothesis.trial_ordinal}; use register() to spend one instead"
                ),
                offending_field="trial_ordinal",
            )
        return self.journal.append(hypothesis)

    def register(
        self,
        hypothesis: StrategyHypothesisRecord,
        registered_at: datetime,
    ) -> tuple[StrategyHypothesisRecord, JournalEntry]:
        """Spend the next trial ordinal on this hypothesis and append the registered record.

        Verifies the whole chain first. That is not defensive habit: if a row could be removed, the
        attempt count would drop, the ordinal would be too low, and the resulting deflation would be
        too weak — a silent failure biased in the candidate's favour. Counting an unverified journal
        would make this registry decorative.
        """
        # `records()` verifies the chain before returning anything, and one read serves every
        # check below — the count, the duplicate guard, and the next ordinal.
        existing = self.hypotheses()
        ordinals = _spent_ordinals(existing)

        if any(
            record.get("hypothesis_id") == hypothesis.hypothesis_id and _ordinal_of(record)
            for record in existing
        ):
            raise AdvisoryError(
                AdvisoryFailureCode.HYPOTHESIS_ALREADY_REGISTERED,
                (
                    f"hypothesis {hypothesis.hypothesis_id} is already registered in this journal; "
                    "spending a second ordinal on one idea would inflate the attempt count"
                ),
                offending_field="hypothesis_id",
            )

        next_ordinal = (max(ordinals) + 1) if ordinals else 1
        registered = hypothesis.register(next_ordinal, registered_at)
        return registered, self.journal.append(registered)

    def attempt_count(self) -> int:
        """How many trial ordinals this journal has spent. The figure a deflation must use."""
        return len(_spent_ordinals(self.hypotheses()))

    def next_ordinal(self) -> int:
        """The ordinal the next registration would spend, without spending it."""
        ordinals = _spent_ordinals(self.hypotheses())
        return (max(ordinals) + 1) if ordinals else 1

    def hypotheses(self) -> list[Mapping[str, Any]]:
        """Every hypothesis payload in the journal, in order. Verifies the chain."""
        return [
            record
            for record in self.journal.records()
            if record.get("record_type") == AdvisoryRecordType.STRATEGY_HYPOTHESIS.value
        ]
