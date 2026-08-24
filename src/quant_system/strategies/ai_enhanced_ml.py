"""AI-Enhanced Machine Learning Strategy combining rolling statistical alpha with multi-agent consensus."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import numpy as np

from quant_system.advisory import (
    AdvisorInterface,
    AdvisoryJournal,
    ExecutionMode,
    ModelIdentity,
    capture_opinion,
    capture_panel_members,
    observation_fingerprint,
)
from quant_system.alpha.ai_advisor import AIOpinion, MultiAgentConsensusEngine
from quant_system.alpha.technical import TechnicalIndicators
from quant_system.core.domain import Side, Signal
from quant_system.strategies.base import BaseStrategy, MarketContext
from quant_system.strategies.ml_equity import MLEquityStrategy, RollingRidgeClassifier

logger = logging.getLogger(__name__)

# The aggregate identity. A panel verdict is not a single model call, so it carries no single
# interface or execution mode — the per-advisor rows written alongside it carry the real ones.
_PANEL_IDENTITY = ModelIdentity(
    provider="quant_system",
    model_id="MultiAgentConsensusEngine",
    interface=AdvisorInterface.AGGREGATE,
)


class AIEnhancedMLEquityStrategy(BaseStrategy):
    """Integrates statistical ML probability with multi-agent advisory consensus.

    Pipeline:
    1. Feature Engineering: Returns, RSI, SMA distance, ATR.
    2. Rolling Statistical Classifier: Computes zero-lookahead direction probability.
    3. Multi-Agent AI Advisory: Evaluates technical context, checks for divergence/vetoes,
       and calculates conviction-based position weight multipliers.
    """

    #: This strategy computes its own ridge inline via ``RollingRidgeClassifier`` — no purging, no
    #: multiplicity accounting, no evidence. That is acceptable for research and backtesting, and
    #: it is a second calculation path if it executes (SLICES.md slice rule 2), so execution
    #: surfaces refuse it. The governed alternative is
    #: ``quant_system.execution.governed_strategy.GovernedModelStrategy``.
    research_only = True

    def __init__(
        self,
        name: str = "AIEnhancedMLEquityStrategy",
        params: Mapping[str, Any] | None = None,
        consensus_engine: MultiAgentConsensusEngine | None = None,
        advisory_journal: AdvisoryJournal | None = None,
        advisory_model: ModelIdentity | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        default_params = {
            "train_window": 60,
            "top_n": 2,
            "confidence_threshold": 0.52,
            "l2_penalty": 1.0,
            "require_ai_confirmation": True,
        }
        if params:
            default_params.update(params)
        super().__init__(name=name, params=default_params)
        self.consensus_engine = consensus_engine or MultiAgentConsensusEngine()

        # Observer wiring. `None` disables recording entirely and the strategy behaves exactly as
        # it did before, which is what keeps the pre-existing signal-count test valid as proof that
        # observation changes nothing.
        self.advisory_journal = advisory_journal
        self.advisory_model = advisory_model or _PANEL_IDENTITY
        self._clock = clock or (lambda: datetime.now(UTC))
        self.advisory_write_failures = 0

    def _record_advisory_opinion(
        self,
        *,
        symbol: str,
        opinion: AIOpinion,
        observation: Mapping[str, Any],
        quant_strength: float,
        ctx: MarketContext,
    ) -> None:
        """Seal one panel verdict into the advisory journal. Never raises, never decides.

        Failures are counted and logged rather than propagated. This component holds no authority
        by construction, so a full disk must not be able to stop the strategy from trading — that
        would hand the observer exactly the power the design denies it. The counter exists because
        silently swallowed failures would leave invisible gaps in the dataset, which is the flaw
        this journal was built to prevent.
        """
        if self.advisory_journal is None:
            return

        try:
            panel_advisors = [advisor.name for advisor in self.consensus_engine.advisors]
            fingerprint = observation_fingerprint(observation)
            recorded_at = self._clock()
            # The panel is handed `quant_side` and `quant_strength` before being asked, so every
            # opinion it returns is anchored on the answer by construction.
            window_end = ctx.current_time.date()
            strength_shown = Decimal(str(quant_strength))

            # One row per advisor, each carrying its own execution mode, then the panel verdict.
            # Members come first so a reader of the chain sees the inputs before the aggregate.
            member_records = capture_panel_members(
                opinion,
                symbol=symbol,
                model=self.advisory_model,
                prompt_sha256=fingerprint,
                recorded_at=recorded_at,
                anchored_on_quant_signal=True,
                observation_window_end=window_end,
                quant_side_shown=Side.BUY.value,
                quant_strength_shown=strength_shown,
                extra_metadata={"strategy": self.name},
            )
            aggregate_record = capture_opinion(
                opinion,
                symbol=symbol,
                model=self.advisory_model,
                prompt_sha256=fingerprint,
                # The aggregate is a panel verdict, not a model call. Members carry the real modes.
                execution_mode=ExecutionMode.UNDETERMINED,
                recorded_at=recorded_at,
                anchored_on_quant_signal=True,
                observation_window_end=window_end,
                quant_side_shown=Side.BUY.value,
                quant_strength_shown=strength_shown,
                extra_metadata={
                    "strategy": self.name,
                    "panel_role": "AGGREGATE",
                    "panel_advisors": panel_advisors,
                    "observation": {str(k): str(v) for k, v in observation.items()},
                },
            )
            # Every record is constructed — and therefore validated — before anything is appended,
            # so a rejected record cannot leave a half-written panel in the journal.
            for record in (*member_records, aggregate_record):
                self.advisory_journal.append(record)
        except Exception:
            self.advisory_write_failures += 1
            logger.exception(
                "advisory journal write failed for %s; the decision is unaffected", symbol
            )

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        signals: list[Signal] = []
        train_window = int(self.params["train_window"])
        top_n = int(self.params["top_n"])
        threshold = float(self.params["confidence_threshold"])
        l2_penalty = float(self.params["l2_penalty"])
        require_ai = bool(self.params["require_ai_confirmation"])

        candidate_scores: dict[str, float] = {}
        candidate_weights: dict[str, float] = {}
        candidate_opinions: dict[str, str] = {}

        for symbol, bars in ctx.historical_bars.items():
            n_bars = len(bars)
            if n_bars < train_window + 22:
                continue

            # Build zero-lookahead training dataset
            X_train: list[list[float]] = []
            y_train: list[float] = []

            start_i = max(20, n_bars - train_window - 1)
            for i in range(start_i, n_bars - 1):
                feat = MLEquityStrategy._extract_feature_vector(bars, i)
                if feat is None:
                    continue
                fwd_ret = float(bars[i + 1].close) - float(bars[i].close)
                X_train.append(feat)
                y_train.append(1.0 if fwd_ret > 0 else -1.0)

            if len(X_train) < 20:
                continue

            # Fit rolling classifier
            model = RollingRidgeClassifier(l2_penalty=l2_penalty)
            model.fit(np.array(X_train), np.array(y_train))

            # Evaluate latest bar
            curr_feat = MLEquityStrategy._extract_feature_vector(bars, n_bars - 1)
            if curr_feat is None:
                continue

            prob_up = model.predict_score(np.array(curr_feat))

            if prob_up > threshold:
                closes = [float(b.close) for b in bars]
                curr_p = closes[-1]
                rsi_series = TechnicalIndicators.rsi([Decimal(str(c)) for c in closes], period=14)
                sma_series = TechnicalIndicators.sma([Decimal(str(c)) for c in closes], period=20)
                atr_series = TechnicalIndicators.atr(bars, period=14)

                tech_summary = {
                    "current_price": curr_p,
                    "rsi": rsi_series[-1] if rsi_series else 50.0,
                    "sma_distance_pct": (curr_p - sma_series[-1]) / curr_p if sma_series else 0.0,
                    "atr_normalized": (atr_series[-1] / curr_p) if atr_series else 0.02,
                    "return_5d": curr_feat[1],
                    "model_prob_up": prob_up,
                }

                # Query AI multi-agent consensus
                ai_opinion = self.consensus_engine.evaluate(
                    symbol=symbol,
                    quant_side=Side.BUY,
                    quant_strength=prob_up,
                    technical_summary=tech_summary,
                )

                # Observe before deciding. The veto below `continue`s, so recording afterwards
                # would discard every refusal — and refusals are the rows the prospective
                # "would the panel's vetoes have helped?" question is built on.
                self._record_advisory_opinion(
                    symbol=symbol,
                    opinion=ai_opinion,
                    observation=tech_summary,
                    quant_strength=prob_up,
                    ctx=ctx,
                )

                # Skip if vetoed by AI advisory layer
                if require_ai and (
                    ai_opinion.action_bias == "VETO" or ai_opinion.weight_multiplier <= 0.0
                ):
                    continue

                candidate_scores[symbol] = prob_up * ai_opinion.confidence
                candidate_weights[symbol] = ai_opinion.weight_multiplier
                candidate_opinions[symbol] = ai_opinion.rationale

        # Rank and pick top N assets
        sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        selected_symbols = {sym for sym, _ in sorted_candidates[:top_n]}

        base_weight = 1.0 / max(1, len(selected_symbols)) if selected_symbols else 0.0

        for sym in selected_symbols:
            mult = candidate_weights.get(sym, 1.0)
            final_weight = min(0.35, base_weight * mult)
            signals.append(
                Signal(
                    symbol=sym,
                    side=Side.BUY,
                    strength=candidate_scores[sym],
                    timestamp=ctx.current_time,
                    strategy_name=self.name,
                    target_weight=final_weight,
                )
            )

        # Generate EXIT signals for currently held positions no longer selected
        for held_sym, pos in ctx.current_positions.items():
            if pos.quantity > 0 and held_sym not in selected_symbols:
                signals.append(
                    Signal(
                        symbol=held_sym,
                        side=None,  # Exit to Flat
                        strength=0.0,
                        timestamp=ctx.current_time,
                        strategy_name=self.name,
                        target_weight=0.0,
                    )
                )

        return signals
