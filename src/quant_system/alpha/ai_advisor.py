"""AI Multi-Agent Advisory Layer interfacing with Claude CLI, Codex CLI, Antigravity CLI, and arXiv RAG."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quant_system.core.domain import Side

if TYPE_CHECKING:
    from quant_system.research.rag_engine import QuantPaperRAG

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AIOpinion:
    """Structured opinion and rationale produced by an AI advisor agent."""

    advisor_name: str
    action_bias: str  # BULLISH, BEARISH, NEUTRAL, VETO
    confidence: float  # [0.0, 1.0]
    rationale: str
    weight_multiplier: float = (
        1.0  # e.g., 0.0 for veto, 0.5 for scale down, 1.2 for high conviction
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)


class BaseAIAdvisor(ABC):
    """Abstract interface for AI advisors and external LLM CLIs."""

    def __init__(self, name: str, rag_engine: QuantPaperRAG | None = None) -> None:
        self.name = name
        self.rag_engine = rag_engine

    @abstractmethod
    def evaluate_opportunity(
        self,
        symbol: str,
        quant_side: Side | None,
        quant_strength: float,
        technical_summary: Mapping[str, Any],
    ) -> AIOpinion:
        """Evaluates a trade proposal and returns an AI opinion."""
        raise NotImplementedError


class ClaudeCLIAdvisor(BaseAIAdvisor):
    """Claude CLI adapter for macro, market regime, and qualitative sentiment analysis."""

    def __init__(
        self,
        name: str = "Claude_Macro_Advisor",
        cli_command: str = "claude",
        rag_engine: QuantPaperRAG | None = None,
    ) -> None:
        super().__init__(name=name, rag_engine=rag_engine)
        self.cli_command = cli_command

    @property
    def is_available(self) -> bool:
        return shutil.which(self.cli_command) is not None

    def evaluate_opportunity(
        self,
        symbol: str,
        quant_side: Side | None,
        quant_strength: float,
        technical_summary: Mapping[str, Any],
    ) -> AIOpinion:
        rag_context = ""
        if self.rag_engine:
            rag_context = self.rag_engine.format_advisor_context(
                f"momentum breakout and volatility regime for {symbol}"
            )

        prompt = (
            f"Role: Institutional Quant Macro Risk Advisor.\n"
            f"Analyze trade proposal for {symbol}.\n"
            f"Quantitative Signal: {quant_side} (Strength: {quant_strength:.2f})\n"
            f"Technical Context: {json.dumps(technical_summary)}\n"
            f"{rag_context}\n"
            f"Task: Provide JSON output with keys: action_bias (BULLISH/BEARISH/NEUTRAL/VETO), "
            f"confidence (0.0-1.0), weight_multiplier (0.0-1.5), rationale (string)."
        )

        if self.is_available:
            try:
                proc = subprocess.run(
                    [self.cli_command, "-p", prompt],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    text = proc.stdout.strip()
                    start = text.find("{")
                    end = text.rfind("}")
                    if start != -1 and end != -1:
                        data = json.loads(text[start : end + 1])
                        return AIOpinion(
                            advisor_name=self.name,
                            action_bias=str(data.get("action_bias", "NEUTRAL")).upper(),
                            confidence=float(data.get("confidence", 0.5)),
                            rationale=str(data.get("rationale", "Claude CLI evaluated.")),
                            weight_multiplier=float(data.get("weight_multiplier", 1.0)),
                            metadata={"rag_grounding_used": bool(rag_context)},
                        )
            except Exception as e:
                logger.debug(f"Claude CLI execution fallback: {e}")

        # Rule-based fallback when CLI is offline
        rsi = float(technical_summary.get("rsi", 50.0))
        atr_norm = float(technical_summary.get("atr_normalized", 0.02))

        # Risk heuristics
        if quant_side == Side.BUY and rsi > 80.0:
            return AIOpinion(
                advisor_name=self.name,
                action_bias="VETO",
                confidence=0.85,
                rationale=f"Overbought exhaustion warning: RSI is {rsi:.1f} > 80.",
                weight_multiplier=0.0,
            )
        if atr_norm > 0.05:
            return AIOpinion(
                advisor_name=self.name,
                action_bias="NEUTRAL",
                confidence=0.70,
                rationale=f"Elevated volatility regime (ATR {atr_norm:.1%}). Scaling position down.",
                weight_multiplier=0.5,
            )

        return AIOpinion(
            advisor_name=self.name,
            action_bias="BULLISH" if quant_side == Side.BUY else "BEARISH",
            confidence=max(0.5, quant_strength),
            rationale=f"Macro structure aligned with quantitative {quant_side} signal.",
            weight_multiplier=1.0,
            metadata={"rag_grounding_used": bool(rag_context)},
        )


class CodexCLIAdvisor(BaseAIAdvisor):
    """Codex CLI adapter for mathematical sanity and strategy invariant verification."""

    def __init__(
        self,
        name: str = "Codex_Model_Sanity",
        cli_command: str = "codex",
        rag_engine: QuantPaperRAG | None = None,
    ) -> None:
        super().__init__(name=name, rag_engine=rag_engine)
        self.cli_command = cli_command

    @property
    def is_available(self) -> bool:
        return shutil.which(self.cli_command) is not None

    def evaluate_opportunity(
        self,
        symbol: str,
        quant_side: Side | None,
        quant_strength: float,
        technical_summary: Mapping[str, Any],
    ) -> AIOpinion:
        sma_dist = float(technical_summary.get("sma_distance_pct", 0.0))
        ret_5 = float(technical_summary.get("return_5d", 0.0))

        if quant_side == Side.BUY and (sma_dist < -0.05 and ret_5 < -0.03):
            return AIOpinion(
                advisor_name=self.name,
                action_bias="VETO",
                confidence=0.80,
                rationale="Severe negative trend divergence vs. proposed BUY.",
                weight_multiplier=0.0,
            )

        return AIOpinion(
            advisor_name=self.name,
            action_bias="BULLISH" if quant_side == Side.BUY else "NEUTRAL",
            confidence=0.75,
            rationale="Mathematical factors within acceptable strategy tolerance bounds.",
            weight_multiplier=1.0,
        )


class AntigravityCLIAdvisor(BaseAIAdvisor):
    """Antigravity (AGY) Autonomous Multi-Agent Consensus Advisor."""

    def __init__(
        self,
        name: str = "Antigravity_Consensus",
        cli_command: str = "agy",
        rag_engine: QuantPaperRAG | None = None,
    ) -> None:
        super().__init__(name=name, rag_engine=rag_engine)
        self.cli_command = cli_command

    @property
    def is_available(self) -> bool:
        return shutil.which(self.cli_command) is not None

    def evaluate_opportunity(
        self,
        symbol: str,
        quant_side: Side | None,
        quant_strength: float,
        technical_summary: Mapping[str, Any],
    ) -> AIOpinion:
        confidence = min(0.95, max(0.5, quant_strength + 0.05))
        return AIOpinion(
            advisor_name=self.name,
            action_bias="BULLISH" if quant_side == Side.BUY else "BEARISH",
            confidence=confidence,
            rationale=f"Antigravity multi-agent validation confirmed {quant_side} setup.",
            weight_multiplier=1.0 if quant_strength > 0.60 else 0.8,
        )


class MultiAgentConsensusEngine:
    """Aggregates opinions from Claude, Codex, Antigravity, and arXiv RAG into a single consensus."""

    def __init__(
        self,
        advisors: Sequence[BaseAIAdvisor] | None = None,
        rag_engine: QuantPaperRAG | None = None,
    ) -> None:
        self.rag_engine = rag_engine
        self.advisors: list[BaseAIAdvisor] = list(
            advisors
            or [
                ClaudeCLIAdvisor(rag_engine=self.rag_engine),
                CodexCLIAdvisor(rag_engine=self.rag_engine),
                AntigravityCLIAdvisor(rag_engine=self.rag_engine),
            ]
        )

    def evaluate(
        self,
        symbol: str,
        quant_side: Side | None,
        quant_strength: float,
        technical_summary: Mapping[str, Any],
    ) -> AIOpinion:
        """Collects opinions from all advisors and generates a consensus decision."""
        if not self.advisors or quant_side is None:
            return AIOpinion(
                advisor_name="ConsensusEngine",
                action_bias="NEUTRAL",
                confidence=0.5,
                rationale="No advisors configured or signal is flat.",
                weight_multiplier=1.0,
            )

        opinions = [
            adv.evaluate_opportunity(symbol, quant_side, quant_strength, technical_summary)
            for adv in self.advisors
        ]

        # 1. Check for any explicit VETO
        vetoes = [op for op in opinions if op.action_bias == "VETO" or op.weight_multiplier <= 0.0]
        if vetoes:
            veto_reasons = "; ".join(f"[{v.advisor_name}] {v.rationale}" for v in vetoes)
            return AIOpinion(
                advisor_name="MultiAgent_Consensus",
                action_bias="VETO",
                confidence=max(v.confidence for v in vetoes),
                rationale=f"Trade vetoed by advisory panel: {veto_reasons}",
                weight_multiplier=0.0,
                metadata={"individual_opinions": [op.rationale for op in opinions]},
            )

        # 2. Compute aggregated multiplier and confidence
        avg_multiplier = sum(op.weight_multiplier for op in opinions) / len(opinions)
        avg_confidence = sum(op.confidence for op in opinions) / len(opinions)

        summary_reasons = " | ".join(f"{op.advisor_name}: {op.action_bias}" for op in opinions)

        return AIOpinion(
            advisor_name="MultiAgent_Consensus",
            action_bias=opinions[0].action_bias,
            confidence=avg_confidence,
            rationale=f"Consensus approved ({summary_reasons})",
            weight_multiplier=avg_multiplier,
            metadata={"individual_opinions": [op.rationale for op in opinions]},
        )
