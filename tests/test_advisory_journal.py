"""Unit tests for the append-only, hash-chained advisory journal."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.advisory import (
    GENESIS_SHA256,
    ActionBias,
    AdvisorInterface,
    AdvisoryError,
    AdvisoryFailureCode,
    AdvisoryJournal,
    AdvisoryOpinionRecord,
    ExecutionMode,
    ModelIdentity,
    capture_hypothesis,
    prompt_fingerprint,
)
from quant_system.data.market_data_evidence import canonical_sha256

RECORDED_AT = datetime(2026, 8, 22, 17, 42, 53, tzinfo=UTC)
PROMPT_HASH = prompt_fingerprint("prompt")

MODEL = ModelIdentity(
    provider="anthropic",
    model_id="claude-opus-5",
    interface=AdvisorInterface.DIRECT_API,
    knowledge_cutoff=date(2026, 5, 1),
)


def _record(symbol: str = "INFY", confidence: str = "0.62") -> AdvisoryOpinionRecord:
    return AdvisoryOpinionRecord(
        recorded_at=RECORDED_AT,
        advisor_name="Claude_Macro_Advisor",
        model=MODEL,
        execution_mode=ExecutionMode.LIVE_MODEL,
        symbol=symbol,
        action_bias=ActionBias.BULLISH,
        confidence=Decimal(confidence),
        weight_multiplier=Decimal("1.0"),
        rationale="Trend structure intact.",
        prompt_sha256=PROMPT_HASH,
        anchored_on_quant_signal=False,
        observation_window_end=date(2024, 12, 31),
    )


@pytest.fixture
def journal(tmp_path: Path) -> AdvisoryJournal:
    return AdvisoryJournal(tmp_path / "nested" / "advisory.jsonl")


def test_reading_a_missing_journal_yields_nothing(journal: AdvisoryJournal) -> None:
    assert journal.read_entries() == []
    assert journal.verify_chain() == []


def test_first_entry_chains_to_genesis(journal: AdvisoryJournal) -> None:
    entry = journal.append(_record())
    assert entry.sequence == 0
    assert entry.previous_sha256 == GENESIS_SHA256


def test_append_creates_parent_directories(journal: AdvisoryJournal) -> None:
    journal.append(_record())
    assert journal.path.exists()


def test_entries_chain_in_order(journal: AdvisoryJournal) -> None:
    first = journal.append(_record(symbol="INFY"))
    second = journal.append(_record(symbol="TCS"))
    third = journal.append(_record(symbol="WIPRO"))

    assert [first.sequence, second.sequence, third.sequence] == [0, 1, 2]
    assert second.previous_sha256 == first.entry_sha256
    assert third.previous_sha256 == second.entry_sha256
    journal.verify_chain()


def test_journal_survives_reopening(tmp_path: Path) -> None:
    path = tmp_path / "advisory.jsonl"
    AdvisoryJournal(path).append(_record(symbol="INFY"))
    second = AdvisoryJournal(path).append(_record(symbol="TCS"))

    assert second.sequence == 1
    reopened = AdvisoryJournal(path)
    assert len(reopened.verify_chain()) == 2


def test_both_record_types_share_one_journal(journal: AdvisoryJournal) -> None:
    journal.append(_record())
    journal.append(
        capture_hypothesis(
            title="Cross-sectional reversal",
            model=MODEL,
            prompt="prompt",
            reasoning="Documented in Indian equities.",
            proposed_rule="Long the bottom decile of 5-day returns.",
            execution_mode=ExecutionMode.LIVE_MODEL,
            recorded_at=RECORDED_AT,
        )
    )
    records = journal.records()
    assert [entry["record_type"] for entry in records] == ["OPINION", "STRATEGY_HYPOTHESIS"]


def test_records_are_returned_in_append_order(journal: AdvisoryJournal) -> None:
    for symbol in ("INFY", "TCS", "WIPRO"):
        journal.append(_record(symbol=symbol))
    assert [entry["symbol"] for entry in journal.records()] == ["INFY", "TCS", "WIPRO"]


def test_every_persisted_record_declares_non_authoritative(journal: AdvisoryJournal) -> None:
    journal.append(_record())
    assert journal.records()[0]["authority"] == "NON_AUTHORITATIVE"


# --- tamper evidence ------------------------------------------------------------------------


def _rewrite_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def test_editing_a_record_breaks_the_chain(journal: AdvisoryJournal) -> None:
    journal.append(_record(confidence="0.62"))
    journal.append(_record(symbol="TCS"))

    lines = journal.path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    payload["record"]["confidence"] = "0.99"
    lines[0] = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    _rewrite_lines(journal.path, lines)

    with pytest.raises(AdvisoryError) as excinfo:
        journal.verify_chain()
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_CHAIN_BROKEN


def test_deleting_an_entry_breaks_the_chain(journal: AdvisoryJournal) -> None:
    journal.append(_record(symbol="INFY"))
    journal.append(_record(symbol="TCS"))
    journal.append(_record(symbol="WIPRO"))

    lines = journal.path.read_text(encoding="utf-8").splitlines()
    _rewrite_lines(journal.path, [lines[0], lines[2]])

    with pytest.raises(AdvisoryError) as excinfo:
        journal.verify_chain()
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_CHAIN_BROKEN


def test_reordering_entries_breaks_the_chain(journal: AdvisoryJournal) -> None:
    journal.append(_record(symbol="INFY"))
    journal.append(_record(symbol="TCS"))

    lines = journal.path.read_text(encoding="utf-8").splitlines()
    _rewrite_lines(journal.path, [lines[1], lines[0]])

    with pytest.raises(AdvisoryError) as excinfo:
        journal.verify_chain()
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_CHAIN_BROKEN


def test_forging_the_entry_hash_still_breaks_the_link(journal: AdvisoryJournal) -> None:
    journal.append(_record(confidence="0.62"))
    journal.append(_record(symbol="TCS"))

    lines = journal.path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[0])
    payload["record"]["confidence"] = "0.99"
    # Re-seal entry 0 so it is internally consistent — the strongest forgery available without
    # rewriting the whole file. Entry 1 still points at the original hash, so the chain still fails.
    payload["entry_sha256"] = canonical_sha256(
        {
            "sequence": payload["sequence"],
            "previous_sha256": payload["previous_sha256"],
            "record": payload["record"],
        }
    )
    lines[0] = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    _rewrite_lines(journal.path, lines)

    reopened = AdvisoryJournal(journal.path)
    assert reopened.read_entries()[0].recompute_sha256() == payload["entry_sha256"]
    with pytest.raises(AdvisoryError) as excinfo:
        reopened.verify_chain()
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_CHAIN_BROKEN


def test_malformed_json_is_reported_with_its_line_number(journal: AdvisoryJournal) -> None:
    journal.append(_record())
    with journal.path.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    with pytest.raises(AdvisoryError) as excinfo:
        journal.read_entries()
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED
    assert "line 2" in str(excinfo.value)


def test_blank_lines_are_tolerated(journal: AdvisoryJournal) -> None:
    journal.append(_record())
    with journal.path.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    assert len(journal.verify_chain()) == 1


def test_a_non_object_line_is_rejected(journal: AdvisoryJournal) -> None:
    journal.path.parent.mkdir(parents=True, exist_ok=True)
    journal.path.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(AdvisoryError) as excinfo:
        journal.read_entries()
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED


def test_journal_never_rewrites_existing_bytes(journal: AdvisoryJournal) -> None:
    journal.append(_record(symbol="INFY"))
    first_line = journal.path.read_bytes()
    journal.append(_record(symbol="TCS"))
    assert journal.path.read_bytes().startswith(first_line)
