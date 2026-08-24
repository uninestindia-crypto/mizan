"""The ungoverned ridge must not reach an execution surface.

`strategies/ml_equity.py` defines `RollingRidgeClassifier`, a second ridge implementation with no
purging, no multiplicity accounting and no evidence. A governed alternative exists, but
`RealtimeShadowRunner` accepted any `BaseStrategy`, so nothing stopped an operator running the
ungoverned one in a shadow session. SLICES.md slice rule 2: a slice "may not introduce a second
calculation path".

Research use is untouched. An ungoverned ridge in a backtest is research; the violation is that it
could execute.
"""

from __future__ import annotations

import pytest

from quant_system.execution.governed_strategy import GovernedExecutionError
from quant_system.execution.realtime_shadow import RealtimeShadowConfig, RealtimeShadowRunner
from quant_system.strategies.ai_enhanced_ml import AIEnhancedMLEquityStrategy
from quant_system.strategies.base import BaseStrategy, MarketContext
from quant_system.strategies.ml_equity import MLEquityStrategy


class _PlainStrategy(BaseStrategy):
    """A hand-written strategy that embeds no model. Must remain executable."""

    def __init__(self) -> None:
        super().__init__(name="plain")

    def generate_signals(self, ctx: MarketContext) -> list:  # type: ignore[type-arg]
        return []


def _runner(strategy: BaseStrategy) -> RealtimeShadowRunner:
    return RealtimeShadowRunner(
        config=RealtimeShadowConfig(session_id="s", model_id="m"),
        live_feed=None,  # type: ignore[arg-type]
        strategy=strategy,
    )


def test_ml_equity_strategy_cannot_drive_a_shadow_session() -> None:
    """The ungoverned ridge, refused at the surface it could previously reach."""
    with pytest.raises(GovernedExecutionError, match="research"):
        _runner(MLEquityStrategy())


def test_ai_enhanced_ml_equity_strategy_cannot_drive_a_shadow_session() -> None:
    """Same ungoverned ridge, reached through the AI-enhanced wrapper."""
    with pytest.raises(GovernedExecutionError, match="research"):
        _runner(AIEnhancedMLEquityStrategy())


def test_both_ungoverned_strategies_declare_themselves_research_only() -> None:
    """The marker is the declaration the surface reads; pin it so it cannot be dropped silently."""
    assert MLEquityStrategy.research_only is True
    assert AIEnhancedMLEquityStrategy.research_only is True


def test_a_strategy_with_no_embedded_model_is_still_accepted() -> None:
    """The guard must block a second calculation path, not every hand-written strategy.

    The pre-existing Slice 9 sessions use strategies like this one. If this fails, the guard is too
    broad and has broken quote-driven shadow sessions that were never the defect.
    """
    runner = _runner(_PlainStrategy())

    assert runner.strategy is not None


def test_a_session_with_no_strategy_at_all_is_still_accepted() -> None:
    """Several Slice 9 tests construct a runner with no strategy to exercise feed handling."""
    runner = RealtimeShadowRunner(
        config=RealtimeShadowConfig(session_id="s", model_id="m"),
        live_feed=None,  # type: ignore[arg-type]
    )

    assert runner.strategy is None


def test_research_use_of_the_ungoverned_ridge_is_untouched() -> None:
    """Blocking execution must not remove the research capability.

    An ungoverned ridge in a backtest is research, not a governance violation. Constructing the
    strategy, and the classifier it embeds, must keep working.
    """
    from quant_system.strategies.ml_equity import RollingRidgeClassifier

    assert RollingRidgeClassifier(l2_penalty=1.0) is not None
    assert MLEquityStrategy() is not None
