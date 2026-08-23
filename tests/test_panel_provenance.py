"""Per-advisor provenance, the default panel's composition, and the consensus vote.

The panel has real authority — it vetoes trades and scales position weight — so every advisor's
decision fields are pinned here as characterization tests: `action_bias`, `confidence`,
`weight_multiplier`, and `rationale` across the whole matrix, so a future edit that changes a
decision fails loudly rather than being noticed after it has traded. Adding provenance moved none
of them.

Two changes here were authorised behaviour changes and are pinned by their own tests: the rule
advisors left the default panel, and the aggregate direction became a majority vote instead of
whichever advisor happened to be listed first.

`ClaudeCLIAdvisor` is constructed with a command that cannot exist, so `is_available` is False and
the fallback path is taken deterministically. Without that the test would depend on whether
`claude` happens to be on PATH, and would spend up to five seconds per call shelling out.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from quant_system.advisory import ExecutionMode, infer_execution_mode
from quant_system.alpha.ai_advisor import (
    AIOpinion,
    BaseAIAdvisor,
    ClaudeCLIAdvisor,
    MultiAgentConsensusEngine,
    SignalStrengthRuleAdvisor,
    TrendDivergenceRuleAdvisor,
)
from quant_system.core.domain import Side

ABSENT_COMMAND = "quantos_no_such_cli_binary_xyz"


def _claude() -> ClaudeCLIAdvisor:
    return ClaudeCLIAdvisor(cli_command=ABSENT_COMMAND)


def _decision(opinion: AIOpinion) -> tuple[str, float, float, str]:
    """Exactly the fields that change what the system does. Metadata is deliberately excluded."""
    return (
        opinion.action_bias,
        opinion.confidence,
        opinion.weight_multiplier,
        opinion.rationale,
    )


class _ScriptedAdvisor(BaseAIAdvisor):
    def __init__(self, name: str, *, metadata: Mapping[str, Any] | None = None) -> None:
        super().__init__(name=name)
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
            action_bias="BULLISH",
            confidence=0.8,
            rationale="fixed",
            weight_multiplier=1.0,
            metadata=self._metadata,
        )


# --- decisions are pinned ---------------------------------------------------------------------


def test_claude_fallback_veto_decision_is_unchanged() -> None:
    opinion = _claude().evaluate_opportunity(
        symbol="RELIANCE",
        quant_side=Side.BUY,
        quant_strength=0.75,
        technical_summary={"rsi": 85.0, "atr_normalized": 0.02},
    )
    assert _decision(opinion) == (
        "VETO",
        0.85,
        0.0,
        "Overbought exhaustion warning: RSI is 85.0 > 80.",
    )


def test_claude_fallback_volatility_decision_is_unchanged() -> None:
    opinion = _claude().evaluate_opportunity(
        symbol="RELIANCE",
        quant_side=Side.BUY,
        quant_strength=0.75,
        technical_summary={"rsi": 55.0, "atr_normalized": 0.06},
    )
    assert _decision(opinion) == (
        "NEUTRAL",
        0.70,
        0.5,
        "Elevated volatility regime (ATR 6.0%). Scaling position down.",
    )


def test_claude_fallback_default_decision_is_unchanged() -> None:
    opinion = _claude().evaluate_opportunity(
        symbol="RELIANCE",
        quant_side=Side.BUY,
        quant_strength=0.72,
        technical_summary={"rsi": 55.0, "atr_normalized": 0.02},
    )
    assert _decision(opinion) == (
        "BULLISH",
        0.72,
        1.0,
        "Macro structure aligned with quantitative BUY signal.",
    )


def test_trend_divergence_veto_decision_is_unchanged() -> None:
    opinion = TrendDivergenceRuleAdvisor().evaluate_opportunity(
        symbol="TCS",
        quant_side=Side.BUY,
        quant_strength=0.7,
        technical_summary={"sma_distance_pct": -0.06, "return_5d": -0.04},
    )
    assert _decision(opinion) == (
        "VETO",
        0.80,
        0.0,
        "Severe negative trend divergence vs. proposed BUY.",
    )


def test_trend_divergence_default_decision_is_unchanged() -> None:
    opinion = TrendDivergenceRuleAdvisor().evaluate_opportunity(
        symbol="TCS",
        quant_side=Side.BUY,
        quant_strength=0.7,
        technical_summary={"sma_distance_pct": 0.01, "return_5d": 0.01},
    )
    assert _decision(opinion) == (
        "BULLISH",
        0.75,
        1.0,
        "Mathematical factors within acceptable strategy tolerance bounds.",
    )


@pytest.mark.parametrize(
    ("strength", "expected_confidence", "expected_multiplier"),
    [(0.70, 0.75, 1.0), (0.50, 0.55, 0.8), (0.99, 0.95, 1.0)],
)
def test_signal_strength_decision_is_unchanged(
    strength: float, expected_confidence: float, expected_multiplier: float
) -> None:
    opinion = SignalStrengthRuleAdvisor().evaluate_opportunity(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=strength,
        technical_summary={},
    )
    assert opinion.action_bias == "BULLISH"
    assert opinion.confidence == pytest.approx(expected_confidence)
    assert opinion.weight_multiplier == expected_multiplier


# --- provenance is now present ------------------------------------------------------------------


@pytest.mark.parametrize(
    "summary",
    [
        {"rsi": 85.0, "atr_normalized": 0.02},
        {"rsi": 55.0, "atr_normalized": 0.06},
        {"rsi": 55.0, "atr_normalized": 0.02},
    ],
    ids=["veto", "volatility", "default"],
)
def test_every_claude_fallback_branch_declares_a_mode(summary: dict[str, float]) -> None:
    """All three branches. Two of them used to emit no metadata at all."""
    opinion = _claude().evaluate_opportunity(
        symbol="RELIANCE",
        quant_side=Side.BUY,
        quant_strength=0.72,
        technical_summary=summary,
    )
    assert infer_execution_mode(opinion) is ExecutionMode.HEURISTIC_FALLBACK


@pytest.mark.parametrize(
    "summary",
    [
        {"sma_distance_pct": -0.06, "return_5d": -0.04},
        {"sma_distance_pct": 0.01, "return_5d": 0.01},
    ],
    ids=["veto", "default"],
)
def test_every_trend_divergence_branch_declares_itself_a_rule(summary: dict[str, float]) -> None:
    opinion = TrendDivergenceRuleAdvisor().evaluate_opportunity(
        symbol="TCS", quant_side=Side.BUY, quant_strength=0.7, technical_summary=summary
    )
    assert infer_execution_mode(opinion) is ExecutionMode.DETERMINISTIC_RULE


def test_signal_strength_declares_itself_a_rule() -> None:
    opinion = SignalStrengthRuleAdvisor().evaluate_opportunity(
        symbol="INFY", quant_side=Side.BUY, quant_strength=0.7, technical_summary={}
    )
    assert infer_execution_mode(opinion) is ExecutionMode.DETERMINISTIC_RULE


def test_a_panel_seated_with_rules_reports_them_as_rules() -> None:
    """The composition that used to be the default. Its records now say what it really was."""
    engine = MultiAgentConsensusEngine(
        advisors=[_claude(), TrendDivergenceRuleAdvisor(), SignalStrengthRuleAdvisor()]
    )
    aggregate = engine.evaluate(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.72,
        technical_summary={"rsi": 55.0, "atr_normalized": 0.02, "sma_distance_pct": 0.01},
    )
    modes = [member["mode"] for member in aggregate.metadata["panel_members"]]
    assert modes == ["HEURISTIC_FALLBACK", "DETERMINISTIC_RULE", "DETERMINISTIC_RULE"]
    assert "LIVE_MODEL" not in modes
    assert "CLI_SUBSCRIPTION" not in modes


# --- the aggregate ------------------------------------------------------------------------------


class _DirectionalAdvisor(BaseAIAdvisor):
    def __init__(self, name: str, action_bias: str) -> None:
        super().__init__(name=name)
        self._action_bias = action_bias

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
            confidence=0.8,
            rationale=f"{self.name} says {self._action_bias}",
            weight_multiplier=1.0,
            metadata={"mode": "DETERMINISTIC_RULE"},
        )


def _vote(*biases: str) -> str:
    engine = MultiAgentConsensusEngine(
        advisors=[_DirectionalAdvisor(f"A{i}", bias) for i, bias in enumerate(biases)]
    )
    return engine.evaluate(
        symbol="INFY", quant_side=Side.BUY, quant_strength=0.7, technical_summary={}
    ).action_bias


# --- the default panel --------------------------------------------------------------------------


def test_the_default_panel_contains_no_rule_advisors() -> None:
    """The rules are importable but not seated by default; a one-model panel says it is one."""
    names = [type(advisor).__name__ for advisor in MultiAgentConsensusEngine().advisors]
    assert names == ["ClaudeCLIAdvisor"]
    assert "TrendDivergenceRuleAdvisor" not in names
    assert "SignalStrengthRuleAdvisor" not in names


def test_rule_advisors_can_still_be_seated_explicitly() -> None:
    engine = MultiAgentConsensusEngine(
        advisors=[TrendDivergenceRuleAdvisor(), SignalStrengthRuleAdvisor()]
    )
    assert len(engine.advisors) == 2


# --- the vote -----------------------------------------------------------------------------------


def test_majority_direction_wins() -> None:
    assert _vote("BULLISH", "BULLISH", "NEUTRAL") == "BULLISH"
    assert _vote("NEUTRAL", "NEUTRAL", "BULLISH") == "NEUTRAL"


def test_a_split_panel_returns_neutral_rather_than_a_direction() -> None:
    """A divided panel fails toward not trading."""
    assert _vote("BULLISH", "NEUTRAL") == "NEUTRAL"
    assert _vote("BULLISH", "BEARISH") == "NEUTRAL"


def test_a_single_advisor_carries_the_direction() -> None:
    assert _vote("BEARISH") == "BEARISH"


def test_the_vote_is_not_the_first_advisors_opinion() -> None:
    """The defect this replaced: direction taken from whichever advisor was listed first."""
    assert _vote("BULLISH", "NEUTRAL", "NEUTRAL") == "NEUTRAL"
    assert _vote("NEUTRAL", "BULLISH", "BULLISH") == "BULLISH"


def test_panel_members_mirror_the_individual_opinions() -> None:
    engine = MultiAgentConsensusEngine(
        advisors=[TrendDivergenceRuleAdvisor(), SignalStrengthRuleAdvisor()]
    )
    aggregate = engine.evaluate(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.72,
        technical_summary={"sma_distance_pct": 0.01, "return_5d": 0.01},
    )
    members = aggregate.metadata["panel_members"]
    assert [member["rationale"] for member in members] == aggregate.metadata["individual_opinions"]
    assert [member["advisor_name"] for member in members] == [
        "TrendDivergence_Rule",
        "SignalStrength_Rule",
    ]


def test_panel_members_are_recorded_on_the_veto_path_too() -> None:
    engine = MultiAgentConsensusEngine(
        advisors=[TrendDivergenceRuleAdvisor(), SignalStrengthRuleAdvisor()]
    )
    aggregate = engine.evaluate(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.72,
        technical_summary={"sma_distance_pct": -0.06, "return_5d": -0.04},
    )
    assert aggregate.action_bias == "VETO"
    assert len(aggregate.metadata["panel_members"]) == 2


def test_an_empty_panel_still_reports_itself() -> None:
    aggregate = MultiAgentConsensusEngine(advisors=[]).evaluate(
        symbol="INFY", quant_side=Side.BUY, quant_strength=0.7, technical_summary={}
    )
    assert _decision(aggregate) == (
        "NEUTRAL",
        0.5,
        1.0,
        "No advisors configured or signal is flat.",
    )
    assert aggregate.metadata["panel_members"] == ()


def test_credential_shaped_advisor_metadata_never_enters_panel_members() -> None:
    """`_panel_member_details` copies named fields, so `masked_key` cannot ride along."""
    engine = MultiAgentConsensusEngine(
        advisors=[_ScriptedAdvisor("A", metadata={"key_id": "k1", "masked_key": "sk-***"})]
    )
    aggregate = engine.evaluate(
        symbol="INFY", quant_side=Side.BUY, quant_strength=0.7, technical_summary={}
    )
    member = aggregate.metadata["panel_members"][0]
    assert set(member) == {
        "advisor_name",
        "action_bias",
        "confidence",
        "weight_multiplier",
        "rationale",
        "mode",
    }


def test_the_aggregate_decision_ignores_advisor_metadata() -> None:
    """The proof that adding metadata cannot move a decision: same decisions, different metadata."""
    plain = MultiAgentConsensusEngine(advisors=[_ScriptedAdvisor("A"), _ScriptedAdvisor("B")])
    tagged = MultiAgentConsensusEngine(
        advisors=[
            _ScriptedAdvisor("A", metadata={"mode": "DIRECT_API", "noise": [1, 2, 3]}),
            _ScriptedAdvisor("B", metadata={"mode": "HEURISTIC_FALLBACK"}),
        ]
    )
    kwargs: dict[str, Any] = {
        "symbol": "INFY",
        "quant_side": Side.BUY,
        "quant_strength": 0.7,
        "technical_summary": {},
    }
    assert _decision(plain.evaluate(**kwargs)) == _decision(tagged.evaluate(**kwargs))
