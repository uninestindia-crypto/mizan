"""The strategy records what the panel said, and records change nothing.

The headline test here is `test_signals_are_identical_with_and_without_a_journal`. The import guard
in `test_advisory_isolation.py` cannot cover `strategies/`, because the strategy is where the panel
is consulted; this behavioural equivalence is what actually proves observer mode at that layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from quant_system.advisory import (
    AdvisoryJournal,
    AdvisoryRecord,
    ExecutionMode,
)
from quant_system.alpha.ai_advisor import AIOpinion, BaseAIAdvisor, MultiAgentConsensusEngine
from quant_system.core.domain import Side, Signal
from quant_system.data.loader import SyntheticDataGenerator
from quant_system.strategies.ai_enhanced_ml import AIEnhancedMLEquityStrategy
from quant_system.strategies.base import MarketContext

CLOCK_AT = datetime(2026, 8, 22, 18, 30, 0, tzinfo=UTC)


class _ScriptedAdvisor(BaseAIAdvisor):
    """A deterministic advisor, so the panel's verdict is fixed by the test rather than the CLI."""

    def __init__(
        self,
        name: str,
        *,
        action_bias: str = "BULLISH",
        confidence: float = 0.8,
        weight_multiplier: float = 1.0,
        rationale: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(name=name)
        self._action_bias = action_bias
        self._confidence = confidence
        self._weight_multiplier = weight_multiplier
        self._rationale = rationale
        self._metadata = metadata or {}

    def evaluate_opportunity(
        self,
        symbol: str,
        quant_side: Side | None,
        quant_strength: float,
        technical_summary: Mapping[str, Any],
    ) -> AIOpinion:
        return AIOpinion(
            advisor_name=self.name,
            action_bias=self._action_bias,
            confidence=self._confidence,
            rationale=self._rationale or f"scripted verdict for {symbol}",
            weight_multiplier=self._weight_multiplier,
            metadata=self._metadata,
        )


class _ExplodingJournal(AdvisoryJournal):
    """A journal that always fails, to prove the observer cannot stop a trade."""

    def append(self, record: AdvisoryRecord) -> Any:
        raise OSError("no space left on device")


def _engine(*advisors: BaseAIAdvisor) -> MultiAgentConsensusEngine:
    return MultiAgentConsensusEngine(advisors=list(advisors))


def _context() -> MarketContext:
    bars_infy = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY", start_date=date(2025, 1, 1), days=70, initial_price=1000.0, seed=42
    )
    bars_tcs = SyntheticDataGenerator.generate_equity_bars(
        symbol="TCS", start_date=date(2025, 1, 1), days=70, initial_price=3500.0, seed=43
    )
    return MarketContext(
        current_time=datetime(2025, 3, 11, 9, 15),
        current_bars={"INFY": bars_infy.bars[-1], "TCS": bars_tcs.bars[-1]},
        historical_bars={"INFY": bars_infy.bars, "TCS": bars_tcs.bars},
        current_positions={},
        available_cash=Decimal("1000000.00"),
        extra_data={},
    )


def _strategy(
    journal: AdvisoryJournal | None,
    *advisors: BaseAIAdvisor,
) -> AIEnhancedMLEquityStrategy:
    return AIEnhancedMLEquityStrategy(
        name="TestAIEnhancedML",
        params={"train_window": 30, "top_n": 2, "confidence_threshold": 0.50},
        consensus_engine=_engine(*advisors),
        advisory_journal=journal,
        clock=lambda: CLOCK_AT,
    )


def _comparable(signals: Sequence[Signal]) -> list[tuple[Any, ...]]:
    return [(s.symbol, s.side, s.strength, s.target_weight, s.strategy_name) for s in signals]


# --- the invariant --------------------------------------------------------------------------


def test_signals_are_identical_with_and_without_a_journal(tmp_path: Path) -> None:
    """Observer mode, proven behaviourally: recording changes no decision."""
    without = _strategy(None, _ScriptedAdvisor("A")).generate_signals(_context())
    with_journal = _strategy(
        AdvisoryJournal(tmp_path / "advisory.jsonl"), _ScriptedAdvisor("A")
    ).generate_signals(_context())

    assert _comparable(with_journal) == _comparable(without)
    assert len(without) > 0, "fixture must produce signals or the comparison proves nothing"


def test_a_failing_journal_does_not_stop_the_strategy(tmp_path: Path) -> None:
    strategy = _strategy(_ExplodingJournal(tmp_path / "advisory.jsonl"), _ScriptedAdvisor("A"))
    baseline = _strategy(None, _ScriptedAdvisor("A")).generate_signals(_context())

    signals = strategy.generate_signals(_context())

    assert _comparable(signals) == _comparable(baseline)
    assert strategy.advisory_write_failures > 0, "failures must be counted, not swallowed silently"


def test_no_journal_means_no_file_is_created(tmp_path: Path) -> None:
    _strategy(None, _ScriptedAdvisor("A")).generate_signals(_context())
    assert list(tmp_path.iterdir()) == []


# --- capture happens ------------------------------------------------------------------------


def test_every_evaluation_is_recorded(tmp_path: Path) -> None:
    journal = AdvisoryJournal(tmp_path / "advisory.jsonl")
    strategy = _strategy(journal, _ScriptedAdvisor("A"))

    strategy.generate_signals(_context())

    records = journal.records()
    assert len(records) > 0
    assert strategy.advisory_write_failures == 0
    journal.verify_chain()


def test_vetoed_opinions_are_captured_not_discarded(tmp_path: Path) -> None:
    """The veto branch `continue`s, so capture must precede it or these rows vanish."""
    journal = AdvisoryJournal(tmp_path / "advisory.jsonl")
    strategy = _strategy(
        journal,
        _ScriptedAdvisor("Vetoer", action_bias="VETO", confidence=0.85, weight_multiplier=0.0),
    )

    signals = strategy.generate_signals(_context())

    records = journal.records()
    assert signals == [], "a panel-wide veto should suppress every entry signal"
    assert len(records) > 0, "the veto itself must still be on record"
    assert all(record["action_bias"] == "VETO" for record in records)
    assert all(record["weight_multiplier"] == "0" for record in records)


def test_records_are_written_in_chain_order(tmp_path: Path) -> None:
    journal = AdvisoryJournal(tmp_path / "advisory.jsonl")
    _strategy(journal, _ScriptedAdvisor("A")).generate_signals(_context())

    entries = journal.verify_chain()
    assert [entry.sequence for entry in entries] == list(range(len(entries)))


# --- what the records say ---------------------------------------------------------------------


def _all_records(tmp_path: Path, *advisors: BaseAIAdvisor) -> list[Mapping[str, Any]]:
    journal = AdvisoryJournal(tmp_path / "advisory.jsonl")
    _strategy(journal, *advisors).generate_signals(_context())
    records = journal.records()
    assert records, "expected at least one record"
    return list(records)


def _first_record(tmp_path: Path, *advisors: BaseAIAdvisor) -> Mapping[str, Any]:
    """The first row of the first panel, which is a MEMBER — members precede their aggregate."""
    return _all_records(tmp_path, *advisors)[0]


def _first_aggregate(tmp_path: Path, *advisors: BaseAIAdvisor) -> Mapping[str, Any]:
    aggregates = [
        record
        for record in _all_records(tmp_path, *advisors)
        if record["metadata"].get("panel_role") == "AGGREGATE"
    ]
    assert aggregates, "expected at least one aggregate record"
    return aggregates[0]


def test_records_are_non_authoritative(tmp_path: Path) -> None:
    assert _first_record(tmp_path, _ScriptedAdvisor("A"))["authority"] == "NON_AUTHORITATIVE"


def test_panel_provenance_is_recorded_as_undetermined(tmp_path: Path) -> None:
    """The engine destroys per-advisor provenance, and the record says so rather than guessing."""
    record = _first_record(tmp_path, _ScriptedAdvisor("A"))
    assert record["execution_mode"] == ExecutionMode.UNDETERMINED.value
    assert record["model"]["interface"] == "AGGREGATE"


def test_the_panel_roster_is_recorded_on_the_aggregate(tmp_path: Path) -> None:
    record = _first_aggregate(tmp_path, _ScriptedAdvisor("Alpha"), _ScriptedAdvisor("Beta"))
    assert record["metadata"]["panel_advisors"] == ["Alpha", "Beta"]


def test_anchoring_is_recorded_because_the_panel_is_shown_the_answer(tmp_path: Path) -> None:
    record = _first_record(tmp_path, _ScriptedAdvisor("A"))
    assert record["anchored_on_quant_signal"] is True
    assert record["quant_side_shown"] == Side.BUY.value
    assert record["quant_strength_shown"] is not None


def test_observation_window_comes_from_the_market_context(tmp_path: Path) -> None:
    record = _first_record(tmp_path, _ScriptedAdvisor("A"))
    assert record["observation_window_end"] == "2025-03-11"


def test_recorded_at_uses_the_injected_clock_not_the_bar_time(tmp_path: Path) -> None:
    record = _first_record(tmp_path, _ScriptedAdvisor("A"))
    assert record["recorded_at"] == "2026-08-22T18:30:00.000000Z"


def test_hindsight_is_undetermined_without_a_declared_cutoff(tmp_path: Path) -> None:
    """The default panel identity declares no cutoff, so contamination is unknown, not clean."""
    assert _first_record(tmp_path, _ScriptedAdvisor("A"))["hindsight"] == "UNDETERMINED"


def test_the_observation_is_fingerprinted_and_carried(tmp_path: Path) -> None:
    record = _first_aggregate(tmp_path, _ScriptedAdvisor("A"))
    assert len(record["prompt_sha256"]) == 64
    assert "rsi" in record["metadata"]["observation"]


def test_members_and_aggregate_share_one_observation_fingerprint(tmp_path: Path) -> None:
    """Rows from one panel evaluation must be joinable, which is what the shared hash is for."""
    records = _all_records(tmp_path, _ScriptedAdvisor("Alpha"), _ScriptedAdvisor("Beta"))
    first_panel = records[:3]
    assert len({record["prompt_sha256"] for record in first_panel}) == 1
    assert [record["metadata"]["panel_role"] for record in first_panel] == [
        "MEMBER",
        "MEMBER",
        "AGGREGATE",
    ]


def test_the_same_observation_yields_the_same_fingerprint(tmp_path: Path) -> None:
    first = _first_record(tmp_path / "a", _ScriptedAdvisor("A"))
    second = _first_record(tmp_path / "b", _ScriptedAdvisor("A"))
    assert first["prompt_sha256"] == second["prompt_sha256"]


# --- secrets --------------------------------------------------------------------------------


def test_advisor_key_material_never_reaches_the_journal(tmp_path: Path) -> None:
    """`_panel_member_details` copies named fields only, so `key_id`/`masked_key` cannot ride along."""
    records = _all_records(
        tmp_path,
        _ScriptedAdvisor("A", metadata={"key_id": "k-1", "masked_key": "sk-***", "mode": "X"}),
    )
    for record in records:
        assert "key_id" not in record["metadata"]
        assert "masked_key" not in record["metadata"]


def test_the_aggregate_still_carries_individual_opinions(tmp_path: Path) -> None:
    """Pre-existing metadata key preserved; `panel_members` was added alongside, not instead."""
    record = _first_aggregate(tmp_path, _ScriptedAdvisor("A"))
    assert "individual_opinions" in record["metadata"]


def test_a_credential_in_a_rationale_costs_the_record_not_the_trade(tmp_path: Path) -> None:
    """Rationales *do* survive into `individual_opinions`, so that is the real leak path.

    The value lands inside a nested list, which a flat metadata scan would walk straight past.
    """
    leaky = "sk-ant-api03-AbCdEfGhIjKlMnOpQr"
    journal = AdvisoryJournal(tmp_path / "advisory.jsonl")
    strategy = _strategy(journal, _ScriptedAdvisor("A", rationale=f"see {leaky}"))
    baseline = _strategy(None, _ScriptedAdvisor("A")).generate_signals(_context())

    signals = strategy.generate_signals(_context())

    assert _comparable(signals) == _comparable(baseline), "the trade must be unaffected"
    assert strategy.advisory_write_failures > 0
    assert journal.records() == [], "no record may carry the credential"
    on_disk = journal.path.read_text(encoding="utf-8") if journal.path.exists() else ""
    assert leaky not in on_disk, "the credential must not reach the file either"


def test_a_credential_in_a_veto_rationale_is_also_refused(tmp_path: Path) -> None:
    """The veto path copies advisor rationales into the aggregate rationale itself."""
    journal = AdvisoryJournal(tmp_path / "advisory.jsonl")
    strategy = _strategy(
        journal,
        _ScriptedAdvisor(
            "A",
            action_bias="VETO",
            weight_multiplier=0.0,
            rationale="blocked, key ghp_AbCdEfGhIjKlMnOpQrSt",
        ),
    )

    strategy.generate_signals(_context())

    assert strategy.advisory_write_failures > 0
    assert journal.records() == []


@pytest.mark.parametrize("require_ai", [True, False])
def test_capture_happens_regardless_of_the_confirmation_setting(
    tmp_path: Path, require_ai: bool
) -> None:
    journal = AdvisoryJournal(tmp_path / "advisory.jsonl")
    strategy = AIEnhancedMLEquityStrategy(
        name="TestAIEnhancedML",
        params={
            "train_window": 30,
            "top_n": 2,
            "confidence_threshold": 0.50,
            "require_ai_confirmation": require_ai,
        },
        consensus_engine=_engine(_ScriptedAdvisor("A", action_bias="VETO", weight_multiplier=0.0)),
        advisory_journal=journal,
        clock=lambda: CLOCK_AT,
    )

    strategy.generate_signals(_context())

    assert len(journal.records()) > 0
