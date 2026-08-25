"""Unit tests for non-authoritative advisory record contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from quant_system.advisory import (
    ActionBias,
    AdvisorInterface,
    AdvisoryError,
    AdvisoryFailureCode,
    AdvisoryOpinionRecord,
    AdvisoryRecordType,
    Authority,
    ExecutionMode,
    HindsightStatus,
    ModelIdentity,
    StrategyHypothesisRecord,
    capture_hypothesis,
    capture_opinion,
    infer_execution_mode,
    prompt_fingerprint,
    sanitize_metadata,
)

RECORDED_AT = datetime(2026, 8, 22, 17, 42, 53, tzinfo=UTC)
PROMPT = "Evaluate the momentum regime for the instrument."
PROMPT_HASH = prompt_fingerprint(PROMPT)


def _model(knowledge_cutoff: date | None = None) -> ModelIdentity:
    return ModelIdentity(
        provider="anthropic",
        model_id="claude-opus-5",
        interface=AdvisorInterface.DIRECT_API,
        model_version="20260501",
        knowledge_cutoff=knowledge_cutoff,
    )


def _opinion_record(**overrides: object) -> AdvisoryOpinionRecord:
    kwargs: dict[str, object] = {
        "recorded_at": RECORDED_AT,
        "advisor_name": "Claude_Macro_Advisor",
        "model": _model(),
        "execution_mode": ExecutionMode.LIVE_MODEL,
        "symbol": "NSE_EQ|INE009A01021",
        "action_bias": ActionBias.BULLISH,
        "confidence": Decimal("0.62"),
        "weight_multiplier": Decimal("1.0"),
        "rationale": "Trend structure intact.",
        "prompt_sha256": PROMPT_HASH,
        "anchored_on_quant_signal": False,
    }
    kwargs.update(overrides)
    return AdvisoryOpinionRecord(**kwargs)  # type: ignore[arg-type]


class _FakeOpinion:
    """Structural stand-in matching `SupportsAIOpinion`."""

    def __init__(
        self,
        *,
        action_bias: str = "BULLISH",
        confidence: float = 0.62,
        weight_multiplier: float = 1.0,
        rationale: str = "Momentum intact.",
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.advisor_name = "Claude_Macro_Advisor"
        self.action_bias = action_bias
        self.confidence = confidence
        self.weight_multiplier = weight_multiplier
        self.rationale = rationale
        self.metadata = metadata or {}


# --- authority ------------------------------------------------------------------------------


def test_opinion_record_is_non_authoritative_by_default() -> None:
    record = _opinion_record()
    assert record.authority is Authority.NON_AUTHORITATIVE
    assert record.record_type is AdvisoryRecordType.OPINION


def test_authority_enum_admits_exactly_one_value() -> None:
    assert list(Authority) == [Authority.NON_AUTHORITATIVE]


def test_wrong_record_type_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(record_type=AdvisoryRecordType.STRATEGY_HYPOTHESIS)
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED


# --- provenance -----------------------------------------------------------------------------


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(recorded_at=datetime(2026, 8, 22, 17, 42, 53))
    assert excinfo.value.code is AdvisoryFailureCode.TIMESTAMP_NOT_UTC


def test_non_utc_offset_is_accepted_and_normalized_in_payload() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    record = _opinion_record(recorded_at=datetime(2026, 8, 22, 23, 12, 53, tzinfo=ist))
    assert record.canonical_payload()["recorded_at"] == "2026-08-22T17:42:53.000000Z"


def test_malformed_prompt_hash_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(prompt_sha256="not-a-hash")
    assert excinfo.value.code is AdvisoryFailureCode.HASH_INVALID


def test_empty_advisor_name_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(advisor_name="")
    assert excinfo.value.code is AdvisoryFailureCode.PROVENANCE_INCOMPLETE


def test_real_upstox_instrument_key_is_a_valid_symbol() -> None:
    record = _opinion_record(symbol="NSE_EQ|INE009A01021")
    assert record.symbol == "NSE_EQ|INE009A01021"


# --- numeric bounds -------------------------------------------------------------------------


@pytest.mark.parametrize("confidence", [Decimal("-0.01"), Decimal("1.01")])
def test_confidence_outside_unit_interval_is_rejected(confidence: Decimal) -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(confidence=confidence)
    assert excinfo.value.code is AdvisoryFailureCode.CONFIDENCE_OUT_OF_RANGE


def test_negative_weight_multiplier_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(weight_multiplier=Decimal("-0.5"))
    assert excinfo.value.code is AdvisoryFailureCode.WEIGHT_MULTIPLIER_INVALID


def test_non_finite_confidence_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(confidence=Decimal("NaN"))
    assert excinfo.value.code is AdvisoryFailureCode.NON_FINITE_VALUE


# --- anchoring ------------------------------------------------------------------------------


def test_unanchored_record_carrying_the_quant_signal_is_contradictory() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(anchored_on_quant_signal=False, quant_side_shown="BUY")
    assert excinfo.value.code is AdvisoryFailureCode.PROVENANCE_INCOMPLETE


def test_anchored_record_may_carry_the_quant_signal() -> None:
    record = _opinion_record(
        anchored_on_quant_signal=True,
        quant_side_shown="BUY",
        quant_strength_shown=Decimal("0.75"),
    )
    payload = record.canonical_payload()
    assert payload["anchored_on_quant_signal"] is True
    assert payload["quant_strength_shown"] == "0.75"


# --- hindsight ------------------------------------------------------------------------------


def test_cutoff_after_observation_window_is_contaminated() -> None:
    record = _opinion_record(
        model=_model(knowledge_cutoff=date(2026, 5, 1)),
        observation_window_end=date(2024, 12, 31),
    )
    assert record.hindsight is HindsightStatus.CONTAMINATED


def test_cutoff_before_observation_window_is_clean() -> None:
    record = _opinion_record(
        model=_model(knowledge_cutoff=date(2023, 12, 31)),
        observation_window_end=date(2024, 12, 31),
    )
    assert record.hindsight is HindsightStatus.CLEAN


def test_missing_cutoff_is_undetermined_not_clean() -> None:
    record = _opinion_record(
        model=_model(knowledge_cutoff=None),
        observation_window_end=date(2024, 12, 31),
    )
    assert record.hindsight is HindsightStatus.UNDETERMINED


def test_hindsight_travels_in_the_canonical_payload() -> None:
    record = _opinion_record(
        model=_model(knowledge_cutoff=date(2026, 5, 1)),
        observation_window_end=date(2024, 12, 31),
    )
    assert record.canonical_payload()["hindsight"] == "CONTAMINATED"


# --- secrets --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["api_key", "API-KEY", "masked_key", "key_id", "session_id", "bearer_token", "private_key"],
)
def test_credential_shaped_metadata_keys_are_rejected(key: str) -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(metadata={key: "value"})
    assert excinfo.value.code is AdvisoryFailureCode.SECRET_MATERIAL_PRESENT


def test_credential_shaped_metadata_values_are_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(metadata={"note": "sk-ant-api03-AbCdEfGhIjKlMnOp"})
    assert excinfo.value.code is AdvisoryFailureCode.SECRET_MATERIAL_PRESENT


def test_credential_prefix_in_rationale_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _opinion_record(rationale="leaked ghp_AbCdEfGhIjKlMnOpQrSt here")
    assert excinfo.value.code is AdvisoryFailureCode.SECRET_MATERIAL_PRESENT


def test_a_sha256_in_free_text_is_not_mistaken_for_a_secret() -> None:
    digest = "650bd8197d8c1ac39e1c6b1f2469d96ee88e468384f07b1b3df83987544cb400"
    record = _opinion_record(rationale=f"corporate action authority {digest}")
    assert digest in record.rationale


def test_sanitize_metadata_strips_panel_key_fields() -> None:
    cleaned = sanitize_metadata({"key_id": "k1", "masked_key": "sk-***", "provider": "groq"})
    assert cleaned == {"provider": "groq"}


# --- hashing --------------------------------------------------------------------------------


def test_content_hash_is_stable_across_equal_records() -> None:
    assert _opinion_record().content_sha256() == _opinion_record().content_sha256()


def test_content_hash_changes_when_any_field_changes() -> None:
    baseline = _opinion_record().content_sha256()
    assert _opinion_record(confidence=Decimal("0.63")).content_sha256() != baseline


def test_execution_mode_is_part_of_the_hashed_content() -> None:
    live = _opinion_record(execution_mode=ExecutionMode.LIVE_MODEL).content_sha256()
    fallback = _opinion_record(execution_mode=ExecutionMode.HEURISTIC_FALLBACK).content_sha256()
    assert live != fallback


# --- capture adapter ------------------------------------------------------------------------


def test_capture_opinion_seals_a_panel_opinion() -> None:
    record = capture_opinion(
        _FakeOpinion(metadata={"key_id": "k1", "masked_key": "sk-***", "mode": "DIRECT_API"}),
        symbol="NSE_EQ|INE009A01021",
        model=_model(knowledge_cutoff=date(2026, 5, 1)),
        prompt=PROMPT,
        execution_mode=ExecutionMode.LIVE_MODEL,
        recorded_at=RECORDED_AT,
        anchored_on_quant_signal=True,
        observation_window_end=date(2024, 12, 31),
        quant_side_shown="BUY",
        quant_strength_shown=Decimal("0.75"),
    )
    assert record.prompt_sha256 == PROMPT_HASH
    assert record.metadata == {"mode": "DIRECT_API"}
    assert record.hindsight is HindsightStatus.CONTAMINATED
    assert record.confidence == Decimal("0.62")


def test_capture_converts_float_confidence_without_binary_artifacts() -> None:
    record = capture_opinion(
        _FakeOpinion(confidence=0.1),
        symbol="INFY",
        model=_model(),
        prompt=PROMPT,
        execution_mode=ExecutionMode.LIVE_MODEL,
        recorded_at=RECORDED_AT,
        anchored_on_quant_signal=False,
    )
    assert record.confidence == Decimal("0.1")


def test_capture_rejects_an_unrecognised_action_bias() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        capture_opinion(
            _FakeOpinion(action_bias="MOONSHOT"),
            symbol="INFY",
            model=_model(),
            prompt=PROMPT,
            execution_mode=ExecutionMode.LIVE_MODEL,
            recorded_at=RECORDED_AT,
            anchored_on_quant_signal=False,
        )
    assert excinfo.value.code is AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED


def test_the_real_panel_opinion_satisfies_the_capture_protocol() -> None:
    from quant_system.alpha.ai_advisor import ClaudeCLIAdvisor
    from quant_system.core.domain import Side

    opinion = ClaudeCLIAdvisor().evaluate_opportunity(
        symbol="RELIANCE",
        quant_side=Side.BUY,
        quant_strength=0.75,
        technical_summary={"rsi": 85.0, "atr_normalized": 0.02},
    )
    record = capture_opinion(
        opinion,
        symbol="RELIANCE",
        model=_model(),
        prompt=PROMPT,
        execution_mode=ExecutionMode.HEURISTIC_FALLBACK,
        recorded_at=RECORDED_AT,
        anchored_on_quant_signal=True,
        quant_side_shown="BUY",
    )
    assert record.action_bias is ActionBias.VETO
    assert record.execution_mode is ExecutionMode.HEURISTIC_FALLBACK


def test_the_veto_fallback_branch_now_declares_its_mode() -> None:
    """Regression guard: this branch cancels a trade at confidence 0.85 and used to emit no
    metadata at all, making a degraded panel indistinguishable from a working one."""
    from quant_system.alpha.ai_advisor import ClaudeCLIAdvisor
    from quant_system.core.domain import Side

    opinion = ClaudeCLIAdvisor().evaluate_opportunity(
        symbol="RELIANCE",
        quant_side=Side.BUY,
        quant_strength=0.75,
        technical_summary={"rsi": 85.0, "atr_normalized": 0.02},
    )
    assert opinion.action_bias == "VETO"
    assert infer_execution_mode(opinion) is ExecutionMode.HEURISTIC_FALLBACK


def test_an_unmarked_opinion_is_still_undetermined_never_live() -> None:
    assert infer_execution_mode(_FakeOpinion(metadata={})) is None
    assert infer_execution_mode(_FakeOpinion(metadata={"mode": "something_new"})) is None


def test_rule_based_advisors_declare_themselves_as_rules() -> None:
    """Codex and Antigravity never invoke a CLI; their records must not imply a model answered."""
    from quant_system.alpha.ai_advisor import SignalStrengthRuleAdvisor, TrendDivergenceRuleAdvisor
    from quant_system.core.domain import Side

    def mode_of(advisor: AdvisorInterface) -> ExecutionMode | None:
        return infer_execution_mode(
            advisor.evaluate_opportunity(
                symbol="INFY",
                quant_side=Side.BUY,
                quant_strength=0.7,
                technical_summary={"sma_distance_pct": 0.01, "return_5d": 0.01},
            )
        )

    assert mode_of(TrendDivergenceRuleAdvisor()) is ExecutionMode.DETERMINISTIC_RULE
    assert mode_of(SignalStrengthRuleAdvisor()) is ExecutionMode.DETERMINISTIC_RULE


def test_infer_execution_mode_reads_the_tagged_branch() -> None:
    assert (
        infer_execution_mode(_FakeOpinion(metadata={"mode": "HEURISTIC_FALLBACK"}))
        is ExecutionMode.HEURISTIC_FALLBACK
    )
    assert (
        infer_execution_mode(_FakeOpinion(metadata={"mode": "DIRECT_API"}))
        is ExecutionMode.LIVE_MODEL
    )


# --- strategy hypotheses --------------------------------------------------------------------


def _hypothesis() -> StrategyHypothesisRecord:
    return capture_hypothesis(
        title="Cross-sectional reversal on 5-day losers",
        model=_model(knowledge_cutoff=date(2026, 5, 1)),
        prompt=PROMPT,
        reasoning="Short-horizon reversal is documented in Indian equities.",
        proposed_rule="Rank NIFTY 50 by 5-day return; long the bottom decile.",
        execution_mode=ExecutionMode.LIVE_MODEL,
        recorded_at=RECORDED_AT,
        universe_scope="NIFTY50",
        observation_window_end=date(2024, 12, 31),
    )


def test_a_fresh_hypothesis_holds_no_trial_ordinal() -> None:
    hypothesis = _hypothesis()
    assert hypothesis.trial_ordinal is None
    assert hypothesis.is_registered is False


def test_backtesting_an_unregistered_hypothesis_fails_closed() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _hypothesis().assert_registered_for_backtest()
    assert excinfo.value.code is AdvisoryFailureCode.HYPOTHESIS_NOT_REGISTERED


def test_registration_spends_an_ordinal_and_permits_backtesting() -> None:
    registered = _hypothesis().register(52, RECORDED_AT)
    registered.assert_registered_for_backtest()
    assert registered.trial_ordinal == 52
    assert registered.is_registered is True


def test_registration_is_not_reversible() -> None:
    registered = _hypothesis().register(52, RECORDED_AT)
    with pytest.raises(AdvisoryError) as excinfo:
        registered.register(53, RECORDED_AT)
    assert excinfo.value.code is AdvisoryFailureCode.HYPOTHESIS_ALREADY_REGISTERED


def test_register_returns_a_copy_and_leaves_the_original_unregistered() -> None:
    original = _hypothesis()
    original.register(52, RECORDED_AT)
    assert original.trial_ordinal is None


def test_ordinal_below_one_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        _hypothesis().register(0, RECORDED_AT)
    assert excinfo.value.code is AdvisoryFailureCode.TRIAL_ORDINAL_INVALID


def test_registered_at_without_an_ordinal_is_rejected() -> None:
    with pytest.raises(AdvisoryError) as excinfo:
        StrategyHypothesisRecord(
            recorded_at=RECORDED_AT,
            hypothesis_id="hyp_1",
            title="t",
            model=_model(),
            execution_mode=ExecutionMode.LIVE_MODEL,
            reasoning="r",
            proposed_rule="p",
            prompt_sha256=PROMPT_HASH,
            registered_at=RECORDED_AT,
        )
    assert excinfo.value.code is AdvisoryFailureCode.PROVENANCE_INCOMPLETE


def test_hypothesis_id_is_derived_deterministically_from_content() -> None:
    assert _hypothesis().hypothesis_id == _hypothesis().hypothesis_id


def test_hypothesis_hindsight_is_computed_like_an_opinion() -> None:
    assert _hypothesis().hindsight is HindsightStatus.CONTAMINATED
