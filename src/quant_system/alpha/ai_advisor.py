"""AI Multi-Agent Advisory Layer: Claude CLI, direct REST APIs, arXiv RAG, and deterministic rules.

Not every advisor here reaches a model. `TrendDivergenceRuleAdvisor` and `SignalStrengthRuleAdvisor`
are hardcoded rules and say so in their `metadata["mode"]`; only `ClaudeCLIAdvisor` and
`DirectAPIAdvisor` can produce a model response, and each falls back to a rule when it cannot.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quant_system.alpha.direct_providers import (
    BaseDirectAPIClient,
    get_direct_client_for_provider,
    parse_json_from_llm_response,
)
from quant_system.alpha.key_pool import KeyPoolManager, ProviderType
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
    """Abstract interface for AI advisors, external LLM CLIs, and Direct APIs."""

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

    def _fallback_heuristic(
        self,
        quant_side: Side | None,
        quant_strength: float,
        technical_summary: Mapping[str, Any],
        rag_context: str = "",
    ) -> AIOpinion:
        """Deterministic rule-based safety fallback when AI/CLI is offline."""
        rsi = float(technical_summary.get("rsi", 50.0))
        atr_norm = float(technical_summary.get("atr_normalized", 0.02))

        if quant_side == Side.BUY and rsi > 80.0:
            return AIOpinion(
                advisor_name=self.name,
                action_bias="VETO",
                confidence=0.85,
                rationale=f"Overbought exhaustion warning: RSI is {rsi:.1f} > 80.",
                weight_multiplier=0.0,
                metadata={"rag_grounding_used": bool(rag_context), "mode": "HEURISTIC_FALLBACK"},
            )
        if atr_norm > 0.05:
            return AIOpinion(
                advisor_name=self.name,
                action_bias="NEUTRAL",
                confidence=0.70,
                rationale=f"Elevated volatility regime (ATR {atr_norm:.1%}). Scaling position down.",
                weight_multiplier=0.5,
                metadata={"rag_grounding_used": bool(rag_context), "mode": "HEURISTIC_FALLBACK"},
            )

        return AIOpinion(
            advisor_name=self.name,
            action_bias="BULLISH" if quant_side == Side.BUY else "BEARISH",
            confidence=max(0.5, quant_strength),
            rationale=f"Macro structure aligned with quantitative {quant_side} signal.",
            weight_multiplier=1.0,
            metadata={"rag_grounding_used": bool(rag_context), "mode": "HEURISTIC_FALLBACK"},
        )


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
                    data = parse_json_from_llm_response(text)
                    if data:
                        return AIOpinion(
                            advisor_name=self.name,
                            action_bias=str(data.get("action_bias", "NEUTRAL")).upper(),
                            confidence=float(data.get("confidence", 0.5)),
                            rationale=str(data.get("rationale", "Claude CLI evaluated.")),
                            weight_multiplier=float(data.get("weight_multiplier", 1.0)),
                            metadata={
                                "rag_grounding_used": bool(rag_context),
                                "mode": "CLI_SUBSCRIPTION",
                            },
                        )
            except Exception as e:
                logger.debug(f"Claude CLI execution fallback: {e}")

        return self._fallback_heuristic(quant_side, quant_strength, technical_summary, rag_context)


class TrendDivergenceRuleAdvisor(BaseAIAdvisor):
    """Deterministic trend-divergence rule. **Not a model** — no CLI, no API, no inference.

    Vetoes a BUY when price sits far below its 20-period SMA *and* the 5-day return is sharply
    negative. Previously named `CodexCLIAdvisor` and carrying a `cli_command` it never invoked,
    which made a hardcoded threshold look like a second opinion from a language model.
    """

    def __init__(
        self,
        name: str = "TrendDivergence_Rule",
        rag_engine: QuantPaperRAG | None = None,
    ) -> None:
        super().__init__(name=name, rag_engine=rag_engine)

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
                metadata={"mode": "DETERMINISTIC_RULE"},
            )

        return AIOpinion(
            advisor_name=self.name,
            action_bias="BULLISH" if quant_side == Side.BUY else "NEUTRAL",
            confidence=0.75,
            rationale="Mathematical factors within acceptable strategy tolerance bounds.",
            weight_multiplier=1.0,
            metadata={"mode": "DETERMINISTIC_RULE"},
        )


class SignalStrengthRuleAdvisor(BaseAIAdvisor):
    """Deterministic restatement of the quant signal. **Not a model, and not an opinion.**

    `action_bias` is a direct function of `quant_side`, so this advisor structurally cannot disagree
    with the signal it is asked to review; `confidence` and `weight_multiplier` are closed-form in
    `quant_strength`. It therefore adds a vote without adding information, and on a panel it pulls
    the averaged `weight_multiplier` toward its own constant.

    Previously named `AntigravityCLIAdvisor` and carrying a `cli_command` it never invoked. Kept
    because the sizing curve is reusable, but it is **not** a default panel member: see
    `MultiAgentConsensusEngine.__init__`.
    """

    def __init__(
        self,
        name: str = "SignalStrength_Rule",
        rag_engine: QuantPaperRAG | None = None,
    ) -> None:
        super().__init__(name=name, rag_engine=rag_engine)

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
            metadata={"mode": "DETERMINISTIC_RULE"},
        )


class DirectAPIAdvisor(BaseAIAdvisor):
    """Direct REST API Advisor supporting OpenRouter, Groq, OpenAI, and Anthropic with auto-rotation."""

    def __init__(
        self,
        provider: ProviderType,
        name: str | None = None,
        key_pool: KeyPoolManager | None = None,
        model: str | None = None,
        rag_engine: QuantPaperRAG | None = None,
        client: BaseDirectAPIClient | None = None,
    ) -> None:
        advisor_name = name or f"{provider.value.capitalize()}_Direct_Advisor"
        super().__init__(name=advisor_name, rag_engine=rag_engine)
        self.provider = provider
        self.key_pool = key_pool
        self.model = model
        self.client = client or get_direct_client_for_provider(provider)

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
            f"Role: Institutional Quant Macro & Risk Advisor.\n"
            f"Analyze trade proposal for {symbol}.\n"
            f"Quantitative Signal: {quant_side} (Strength: {quant_strength:.2f})\n"
            f"Technical Context: {json.dumps(technical_summary)}\n"
            f"{rag_context}\n"
            f"Task: Respond in valid JSON with keys: action_bias (BULLISH/BEARISH/NEUTRAL/VETO), "
            f"confidence (0.0-1.0), weight_multiplier (0.0-1.5), rationale (string)."
        )

        if self.key_pool and self.client:
            # Multi-key failover loop
            while True:
                active_key = self.key_pool.get_active_key(self.provider)
                if not active_key:
                    break

                content, status_code, retry_after, err_msg = self.client.execute(
                    prompt, active_key, model=self.model
                )

                if status_code == 200 and content:
                    parsed = parse_json_from_llm_response(content)
                    if parsed:
                        self.key_pool.record_success(active_key)
                        return AIOpinion(
                            advisor_name=self.name,
                            action_bias=str(parsed.get("action_bias", "NEUTRAL")).upper(),
                            confidence=float(parsed.get("confidence", 0.5)),
                            rationale=str(
                                parsed.get("rationale", f"{self.provider.value} evaluated.")
                            ),
                            weight_multiplier=float(parsed.get("weight_multiplier", 1.0)),
                            metadata={
                                "provider": self.provider.value,
                                "key_id": active_key.key_id,
                                "masked_key": active_key.mask_key(),
                                "rag_grounding_used": bool(rag_context),
                                "mode": "DIRECT_API",
                            },
                        )

                # If rate limited (429) or temporary server error, put key in cooldown and auto-rotate
                if status_code in {429, 503, 408}:
                    self.key_pool.record_rate_limit(active_key, retry_after_seconds=retry_after)
                    logger.warning(
                        f"Direct API key {active_key.key_id} hit status {status_code}; auto-rotating to backup key..."
                    )
                    continue
                else:
                    self.key_pool.record_error(active_key, is_fatal=(status_code in {401, 403}))
                    break

        return self._fallback_heuristic(quant_side, quant_strength, technical_summary, rag_context)


def _majority_action_bias(opinions: Sequence[AIOpinion]) -> str:
    """The direction most advisors chose; ``NEUTRAL`` when the panel is split.

    Replaces `opinions[0].action_bias`, which made the panel's direction whichever advisor happened
    to be first in the list — a panel that looked like a vote without being one.

    A tie resolves to ``NEUTRAL`` rather than to any direction, so a divided panel fails toward not
    trading. That is the conservative side here: `agent_context/CURRENT.md` records `NO_TRADE`
    beating the ridge candidate on 26 of 40 published models.

    Callers reach this only after the veto check has returned, so no ``VETO`` opinion is in scope.
    """
    if not opinions:
        return "NEUTRAL"

    tally = Counter(op.action_bias for op in opinions)
    ranked = tally.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "NEUTRAL"
    return ranked[0][0]


def _panel_member_details(opinions: Sequence[AIOpinion]) -> tuple[dict[str, Any], ...]:
    """Preserve per-advisor provenance for observers, without leaking credential-shaped fields.

    The aggregate returned by `MultiAgentConsensusEngine.evaluate` previously kept only a list of
    rationale strings, so no caller downstream could tell whether a verdict came from a model, a
    fallback, or a hardcoded rule. This carries the fields an observer needs.

    Fields are copied by name rather than by spreading `op.metadata`, so `key_id` and `masked_key`
    from `DirectAPIAdvisor` cannot ride along into anything that later gets persisted.
    """
    return tuple(
        {
            "advisor_name": op.advisor_name,
            "action_bias": op.action_bias,
            "confidence": op.confidence,
            "weight_multiplier": op.weight_multiplier,
            "rationale": op.rationale,
            "mode": op.metadata.get("mode"),
        }
        for op in opinions
    )


class MultiAgentConsensusEngine:
    """Aggregates opinions from Claude, Codex, Antigravity, OpenRouter, Groq, and arXiv RAG into a single consensus."""

    def __init__(
        self,
        advisors: Sequence[BaseAIAdvisor] | None = None,
        key_pool: KeyPoolManager | None = None,
        rag_engine: QuantPaperRAG | None = None,
    ) -> None:
        self.rag_engine = rag_engine
        self.key_pool = key_pool

        if advisors is not None:
            self.advisors = list(advisors)
        else:
            # Default panel: advisors that can actually reach a model. `TrendDivergenceRuleAdvisor`
            # and `SignalStrengthRuleAdvisor` are deliberately excluded — they are deterministic
            # rules, and seating them here made a one-model panel look like a three-model one while
            # dragging the averaged `weight_multiplier` toward their constants. Pass them in
            # `advisors=` explicitly if you want a rule on the panel.
            panel: list[BaseAIAdvisor] = [
                ClaudeCLIAdvisor(rag_engine=self.rag_engine),
            ]
            if self.key_pool:
                for prov in [
                    ProviderType.OPENROUTER,
                    ProviderType.GROQ,
                    ProviderType.OPENAI,
                    ProviderType.ANTHROPIC,
                ]:
                    if any(k.provider == prov for k in self.key_pool.keys):
                        panel.append(
                            DirectAPIAdvisor(
                                provider=prov, key_pool=self.key_pool, rag_engine=self.rag_engine
                            )
                        )
            self.advisors = panel

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
                metadata={"mode": "DETERMINISTIC_RULE", "panel_members": ()},
            )

        opinions = [
            adv.evaluate_opportunity(symbol, quant_side, quant_strength, technical_summary)
            for adv in self.advisors
        ]

        panel_members = _panel_member_details(opinions)

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
                metadata={
                    "individual_opinions": [op.rationale for op in opinions],
                    "panel_members": panel_members,
                },
            )

        # 2. Compute aggregated multiplier and confidence
        avg_multiplier = sum(op.weight_multiplier for op in opinions) / len(opinions)
        avg_confidence = sum(op.confidence for op in opinions) / len(opinions)

        summary_reasons = " | ".join(f"{op.advisor_name}: {op.action_bias}" for op in opinions)

        return AIOpinion(
            advisor_name="MultiAgent_Consensus",
            action_bias=_majority_action_bias(opinions),
            confidence=avg_confidence,
            rationale=f"Consensus approved ({summary_reasons})",
            weight_multiplier=avg_multiplier,
            metadata={
                "individual_opinions": [op.rationale for op in opinions],
                "panel_members": panel_members,
            },
        )
