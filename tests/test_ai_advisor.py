"""Unit tests for AI Multi-Agent Advisory Layer."""

from quant_system.alpha.ai_advisor import (
    ClaudeCLIAdvisor,
    DirectAPIAdvisor,
    MultiAgentConsensusEngine,
    SignalStrengthRuleAdvisor,
    TrendDivergenceRuleAdvisor,
)
from quant_system.alpha.key_pool import KeyPoolManager, ProviderType
from quant_system.core.domain import Side


def test_claude_advisor_overbought_veto() -> None:
    advisor = ClaudeCLIAdvisor()
    opinion = advisor.evaluate_opportunity(
        symbol="RELIANCE",
        quant_side=Side.BUY,
        quant_strength=0.75,
        technical_summary={"rsi": 85.0, "atr_normalized": 0.02},
    )
    assert opinion.action_bias == "VETO"
    assert opinion.weight_multiplier == 0.0
    assert "Overbought" in opinion.rationale


def test_codex_advisor_divergence_veto() -> None:
    advisor = TrendDivergenceRuleAdvisor()
    opinion = advisor.evaluate_opportunity(
        symbol="TCS",
        quant_side=Side.BUY,
        quant_strength=0.65,
        technical_summary={"sma_distance_pct": -0.08, "return_5d": -0.05},
    )
    assert opinion.action_bias == "VETO"
    assert opinion.weight_multiplier == 0.0
    assert "divergence" in opinion.rationale.lower()


def test_antigravity_advisor_conviction() -> None:
    advisor = SignalStrengthRuleAdvisor()
    opinion = advisor.evaluate_opportunity(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.70,
        technical_summary={"rsi": 55.0, "atr_normalized": 0.02},
    )
    assert opinion.action_bias == "BULLISH"
    assert opinion.weight_multiplier == 1.0
    assert opinion.confidence >= 0.70


def test_multi_agent_consensus_engine_approval_and_veto() -> None:
    engine = MultiAgentConsensusEngine()

    # Normal bullish setup
    opinion = engine.evaluate(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.65,
        technical_summary={
            "rsi": 55.0,
            "atr_normalized": 0.02,
            "sma_distance_pct": 0.02,
            "return_5d": 0.01,
        },
    )
    assert opinion.action_bias == "BULLISH"
    assert opinion.weight_multiplier > 0.0

    # Overbought setup should be vetoed by consensus
    veto_opinion = engine.evaluate(
        symbol="INFY",
        quant_side=Side.BUY,
        quant_strength=0.65,
        technical_summary={
            "rsi": 88.0,
            "atr_normalized": 0.02,
            "sma_distance_pct": 0.02,
            "return_5d": 0.01,
        },
    )
    assert veto_opinion.action_bias == "VETO"
    assert veto_opinion.weight_multiplier == 0.0


def test_hybrid_consensus_with_key_pool() -> None:
    pool = KeyPoolManager()
    pool.add_key("sk-test-groq", ProviderType.GROQ)
    pool.add_key("sk-test-or", ProviderType.OPENROUTER)

    engine = MultiAgentConsensusEngine(key_pool=pool)
    assert any(isinstance(a, DirectAPIAdvisor) for a in engine.advisors)

    opinion = engine.evaluate(
        symbol="HDFCBANK",
        quant_side=Side.BUY,
        quant_strength=0.70,
        technical_summary={"rsi": 52.0, "atr_normalized": 0.015},
    )
    assert opinion.action_bias in {"BULLISH", "NEUTRAL"}
    assert opinion.weight_multiplier > 0.0
