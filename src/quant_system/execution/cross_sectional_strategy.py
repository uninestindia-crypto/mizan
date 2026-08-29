"""Governed execution for cross-sectional models.

`execution/governed_strategy.py` binds one model to one instrument. That is correct for the
single-instrument governed dataset contract, and it makes a whole model class unexecutable: a
cross-sectional model does not decide about an instrument in isolation, it *ranks* instruments
against each other on a shared decision date. Asking the single-instrument adapter to run one is not
a configuration problem -- ``GovernedModelStrategy.generate_signals`` raises on the second symbol,
because for a single-instrument model a second symbol genuinely is an error.

So this module adds the missing layer rather than relaxing the existing one. The single-instrument
path keeps every invariant a Red Team recheck hardened into it, including the per-bar symbol
verification that caught RELIANCE bars passing under an INFY key. That verification is *reused*
here, not reimplemented, which is the whole reason ``require_bar_sequence`` and its neighbours were
promoted to public names.

What this module deliberately does NOT do:

* **It does not compute the cross-sectional feature family itself.** Two of the fifteen Mizan
  features are cross-sectional ranks, which are by definition not functions of one instrument's
  history. Values arrive through :class:`CrossSectionalFeatureProvider`. The one implementation that
  provider should wrap is ``modeling.mizan_features`` -- the shared kernel both training and
  execution call. Recomputing the family here instead would be a second calculation path, the defect
  class ``agent_context/decisions/20260824-canonical-feature-window.md`` exists to prevent.
* **It does not promote anything.** The verdict gate is identical to the single-instrument one.
  ``RESEARCH_ONLY`` and ``REJECT`` execute on no surface, here as everywhere.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any, Final, Protocol, runtime_checkable

from quant_system.core.domain import Side, Signal
from quant_system.data.market_data import PointInTimeBar
from quant_system.execution.governed_strategy import (
    SURFACE_ALLOWED_VERDICTS,
    ExecutionSurface,
    GovernedExecutionError,
    available_window,
    require_bar_history,
    require_bar_sequence,
    score_row,
)
from quant_system.modeling import ModelCardV1
from quant_system.modeling.mizan_features import MIZAN_CANONICAL_WINDOW_BARS
from quant_system.modeling.preprocessing import (
    StandardizationStateV1,
    standardize_feature_values,
)
from quant_system.modeling.ridge import RidgeFittedStateV1
from quant_system.modeling.rows import feature_names_for
from quant_system.strategies.base import BaseStrategy, MarketContext

#: Bars a symbol must have before this surface will score it, imported rather than restated.
#:
#: Two constants exist and they are not interchangeable. ``MIZAN_WINDOW_BARS`` (51) is the *minimum*
#: from which a row is computable at all, and the training kernel accepts it because early rows in a
#: symbol's history legitimately had only that much prefix.
#: ``MIZAN_CANONICAL_WINDOW_BARS`` (400) is the trailing history the kernel consumes once it exists,
#: sized by ``rsi_14_centered``, which is an EMA with no bounded window -- at 51 bars it is wrong by
#: up to 0.246 of its own standard deviation, at 400 by 1.71e-12.
#:
#: **Execution requires the canonical window, not the minimum.** Training replays a symbol's early
#: life, where a short prefix is the honest answer. Execution is always at the present, where every
#: listed name has years of history, so a name served with 60 bars would be ranked against names
#: served with 400 while carrying a systematically different RSI convergence state. Ranking those
#: together is not a comparison the model was fitted to make. ``min_coverage`` remains the declared
#: way to admit a partial cross-section deliberately.
#:
#: An earlier version of this module hardcoded 21 while citing ``MIZAN_WINDOW_BARS`` in the same
#: comment -- wrong twice over, and it would have scored silently. Importing makes that impossible.
CROSS_SECTIONAL_WINDOW_BARS: Final = MIZAN_CANONICAL_WINDOW_BARS

#: Verdicts that may execute on *some* surface. SHADOW is the most permissive surface, so its
#: allowed set is exactly the set of verdicts that are executable anywhere. Naming it here keeps one
#: source of truth: a bundle refuses what no surface would accept, and the strategy then applies the
#: narrower per-surface rule on top.
_EXECUTABLE_VERDICTS: Final = SURFACE_ALLOWED_VERDICTS[ExecutionSurface.SHADOW]


@runtime_checkable
class CrossSectionalFeatureProvider(Protocol):
    """Supplies one decision date's cross-section of feature values.

    The provider returns ``{symbol: {feature_name: decimal_text}}``. It returns values rather than
    bars because cross-sectional features rank an instrument against its peers and therefore cannot
    be derived from any single instrument's history.

    Implementations must be point-in-time: a value returned for ``decision_time`` must be derivable
    from information available at ``decision_time``. This module verifies what it can -- the bar
    window backing each symbol -- but cannot verify a value it did not compute.
    """

    def __call__(
        self,
        symbols: tuple[str, ...],
        decision_time: datetime,
    ) -> Mapping[str, Mapping[str, str]]: ...


def _require_canonical_decimal(text: str, field_name: str) -> Decimal:
    """Parse a decimal field, refusing the forms that silently change meaning."""
    if not isinstance(text, str):
        raise GovernedExecutionError(
            f"{field_name} must be decimal text, got {type(text).__name__}"
        )
    try:
        value = Decimal(text)
    except ArithmeticError as error:
        raise GovernedExecutionError(f"{field_name} is not a valid decimal: {text!r}") from error
    except ValueError as error:
        raise GovernedExecutionError(f"{field_name} is not a valid decimal: {text!r}") from error
    if not value.is_finite():
        raise GovernedExecutionError(f"{field_name} must be finite, got {text!r}")
    return value


@dataclass(frozen=True, slots=True)
class CrossSectionalSelectionRuleV1:
    """How much of the ranked cross-section the model actually takes.

    ``selection_fraction`` is carried explicitly and has no default, for the same reason
    ``score_threshold`` has none on the single-instrument bundle: a selection rule invented at
    execution time is not the rule the model was validated under. The Mizan out-of-sample screen
    used the top 20%; a bundle that silently defaulted to another fraction would be executing a
    different strategy than the one that was measured.

    ``apply_score_floor`` decides whether ``score_threshold`` additionally gates the selection. The
    cross-sectional screen ranked without a floor, so this defaults to ``False`` -- but it is
    recorded on the bundle and emitted on every signal either way, so an audit can see which rule
    actually ran.
    """

    selection_fraction: str
    apply_score_floor: bool = False

    def __post_init__(self) -> None:
        fraction = _require_canonical_decimal(self.selection_fraction, "selection_fraction")
        if not Decimal(0) < fraction <= Decimal(1):
            raise GovernedExecutionError(
                f"selection_fraction must lie in (0, 1], got {self.selection_fraction!r}"
            )

    @property
    def fraction(self) -> Decimal:
        return Decimal(self.selection_fraction)

    def count_for(self, population: int) -> int:
        """How many names to take from a ranked cross-section of ``population``.

        Rounds **up**, so a non-empty cross-section always yields at least one selection rather than
        silently abstaining on a small universe. The ceiling is taken through exact integer
        comparison rather than ``math.ceil``, which would route an exact Decimal through binary
        float and can round the wrong way at a boundary.
        """
        if population <= 0:
            return 0
        exact = self.fraction * population
        whole = int(exact)
        count = whole if exact == whole else whole + 1
        return max(1, min(population, count))


@dataclass(frozen=True, slots=True)
class CrossSectionalEvidenceIdentityV1:
    """The identity of one published cross-sectional model, from a single evidence record.

    This mirrors ``ModelEvidenceIdentityV1`` but binds a **universe** rather than an instrument. The
    universe is part of the model's identity: a ranking model's every decision depends on which
    peers it ranked against, so scoring the same name inside a different universe is a different
    model, not the same model with different inputs.
    """

    model_id: str
    candidate_id: str
    trial_id: str
    symbols: tuple[str, ...]
    fitted_state_hash: str
    preprocessing_state_hash: str
    score_threshold: str
    feature_schema_id: str
    feature_schema_version: int

    def __post_init__(self) -> None:
        if not self.symbols:
            raise GovernedExecutionError(
                "a cross-sectional model must bind at least one instrument"
            )
        if len(set(self.symbols)) != len(self.symbols):
            raise GovernedExecutionError(
                "the bound universe contains a duplicate symbol; ranks would depend on how many "
                "times a name was listed"
            )
        if tuple(sorted(self.symbols)) != self.symbols:
            raise GovernedExecutionError(
                "the bound universe must be sorted, so two bundles over the same names compare "
                "and hash identically"
            )
        _require_canonical_decimal(self.score_threshold, "score_threshold")

    @classmethod
    def from_manifest_metadata(
        cls,
        metadata: Mapping[str, Any],
        *,
        score_threshold: str,
        symbols: Sequence[str],
    ) -> CrossSectionalEvidenceIdentityV1:
        """Derive an identity from one published model manifest's metadata.

        ``score_threshold`` and ``symbols`` are passed separately for the same reason the
        single-instrument builder passes them separately: neither sits on the model manifest. The
        threshold lives on the trial start record and the universe lives on the published decision
        records, and both must be read from the evidence for this same ``trial_id``.
        """
        try:
            return cls(
                model_id=metadata["model_id"],
                candidate_id=metadata["candidate_id"],
                trial_id=metadata["trial_id"],
                symbols=tuple(sorted(symbols)),
                fitted_state_hash=metadata["fitted_state"]["fitted_state_hash"],
                preprocessing_state_hash=metadata["preprocessing"]["state_hash"],
                score_threshold=score_threshold,
                feature_schema_id=metadata["feature_schema_id"],
                feature_schema_version=metadata["feature_schema_version"],
            )
        except (KeyError, TypeError) as error:
            raise GovernedExecutionError(
                f"model evidence is missing an identity field: {error}"
            ) from error


@dataclass(frozen=True, slots=True)
class PromotedCrossSectionalBundleV1:
    """A promoted cross-sectional model plus everything needed to reproduce its decisions."""

    candidate_id: str
    model_card: ModelCardV1
    fitted: RidgeFittedStateV1
    standardization: StandardizationStateV1
    score_threshold: str
    selection_rule: CrossSectionalSelectionRuleV1
    evidence: CrossSectionalEvidenceIdentityV1

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise GovernedExecutionError("bundle candidate_id cannot be empty")
        if self.model_card.candidate_id != self.candidate_id:
            raise GovernedExecutionError(
                "model card candidate does not match the bundle candidate; the card describes a "
                "different model than the fitted state supplied with it"
            )
        if self.fitted.preprocessing_state_hash != self.standardization.state_hash:
            raise GovernedExecutionError(
                "fitted state was not produced by the supplied standardization state; scoring live "
                "features with a mismatched scaler silently changes the model"
            )
        expected_names = self._declared_feature_names()
        if tuple(self.standardization.feature_names) != expected_names:
            raise GovernedExecutionError(
                "standardization does not use the feature family its schema declares; the design "
                "matrix is positional, so a mismatched family scores against the wrong column"
            )
        if len(self.fitted.coefficients) != len(expected_names):
            raise GovernedExecutionError(
                f"fitted state carries {len(self.fitted.coefficients)} coefficients but the "
                f"declared family has {len(expected_names)} features"
            )
        if self.model_card.verdict not in _EXECUTABLE_VERDICTS:
            raise GovernedExecutionError(
                f"verdict {self.model_card.verdict.value} is not executable on any surface"
            )
        _require_canonical_decimal(self.score_threshold, "score_threshold")
        self._verify_against_evidence()

    def _declared_feature_names(self) -> tuple[str, ...]:
        try:
            return feature_names_for(
                self.evidence.feature_schema_id,
                self.evidence.feature_schema_version,
            )
        except ValueError as error:
            raise GovernedExecutionError(
                "model evidence declares an unsupported feature schema: "
                f"{self.evidence.feature_schema_id} v{self.evidence.feature_schema_version}"
            ) from error

    def _verify_against_evidence(self) -> None:
        """Tie the card, the artefacts, the threshold and the universe to one published record.

        Without this, ``candidate_id`` is the only link between a card and a fitted state, and it
        links nothing: a campaign shares one candidate across every model it produces. A Red Team
        probe used exactly that against the single-instrument bundle to assemble the best model's
        card with the worst model's coefficients, at a threshold from neither.
        """
        evidence = self.evidence
        if evidence.model_id != self.model_card.model_id:
            raise GovernedExecutionError("model evidence and model card describe different models")
        if evidence.candidate_id != self.candidate_id:
            raise GovernedExecutionError(
                "model evidence candidate does not match the bundle candidate"
            )
        if evidence.fitted_state_hash != self.fitted.fitted_state_hash:
            raise GovernedExecutionError(
                "the supplied fitted state is not the one this model published; its coefficients "
                "would produce decisions no trial ever recorded"
            )
        if evidence.preprocessing_state_hash != self.standardization.state_hash:
            raise GovernedExecutionError(
                "the supplied standardization state is not the one this model published"
            )
        if evidence.score_threshold != self.score_threshold:
            raise GovernedExecutionError(
                "bundle score_threshold does not match the threshold this trial recorded"
            )

    @property
    def model_id(self) -> str:
        return self.model_card.model_id

    @property
    def universe(self) -> tuple[str, ...]:
        return self.evidence.symbols


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """One scored name inside a decision date's cross-section."""

    symbol: str
    score: Decimal
    rank: int
    selected: bool


class CrossSectionalModelStrategy(BaseStrategy):
    """Rank a bound universe on one decision date and take the declared top fraction.

    Fail-closed choices, each of which could reasonably have gone the other way and is therefore
    stated rather than left for a reader to infer:

    * **A partial cross-section is refused, not ranked.** If bound names cannot be scored, every rank
      in the cross-section differs from the rank the model was validated under. Scoring the remainder
      would produce plausible signals from a strategy nobody measured. ``min_coverage`` relaxes this
      deliberately and defaults to demanding the full universe.
    * **A foreign symbol is refused.** Serving a name outside the bound universe changes what every
      other name is ranked against.
    * **Ties break by symbol, ascending.** Two identical scores must not select different names on
      two runs over identical input.
    """

    def __init__(
        self,
        bundle: PromotedCrossSectionalBundleV1,
        surface: ExecutionSurface,
        feature_provider: CrossSectionalFeatureProvider,
        *,
        min_coverage: str = "1",
        name: str = "governed_cross_sectional",
    ) -> None:
        allowed = SURFACE_ALLOWED_VERDICTS[surface]
        if bundle.model_card.verdict not in allowed:
            raise GovernedExecutionError(
                f"a {bundle.model_card.verdict.value} model may not drive the {surface.value} "
                f"surface; permitted verdicts are {sorted(state.value for state in allowed)}"
            )
        coverage = _require_canonical_decimal(min_coverage, "min_coverage")
        if not Decimal(0) < coverage <= Decimal(1):
            raise GovernedExecutionError(f"min_coverage must lie in (0, 1], got {min_coverage!r}")
        super().__init__(
            name=name,
            params={
                "apply_score_floor": bundle.selection_rule.apply_score_floor,
                "candidate_id": bundle.candidate_id,
                "feature_schema_id": bundle.evidence.feature_schema_id,
                "feature_schema_version": bundle.evidence.feature_schema_version,
                "min_coverage": min_coverage,
                "model_card_hash": bundle.model_card.model_card_hash,
                "model_id": bundle.model_id,
                "score_threshold": bundle.score_threshold,
                "selection_fraction": bundle.selection_rule.selection_fraction,
                "surface": surface.value,
                "universe_size": len(bundle.universe),
                "verdict": bundle.model_card.verdict.value,
            },
        )
        self.bundle = bundle
        self.surface = surface
        self._provider = feature_provider
        self._threshold = Decimal(bundle.score_threshold)
        self._min_coverage = coverage

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        """Score the whole bound universe, rank it, and take the declared fraction."""
        history = require_bar_history(ctx)
        bound = set(self.bundle.universe)
        foreign = sorted(served for served in history if served not in bound)
        if foreign:
            raise GovernedExecutionError(
                f"served bar history contains {foreign[0]!r}, which is outside this model's bound "
                f"universe of {len(bound)} instruments. A ranking model's decisions depend on which "
                "peers it ranked against, so an extra name changes every rank"
            )

        scoreable = self._scoreable_symbols(history, ctx.current_time)
        if not self._coverage_sufficient(len(scoreable), len(self.bundle.universe)):
            return []

        features = self._provider(scoreable, ctx.current_time)
        ranked = self._rank(scoreable, features)
        # The selection count is taken from the cross-section actually ranked, not from the bound
        # universe, because that is what the model was validated over: each rebalance in the screen
        # took the top fraction of the names that had data that date. `_strength` must be handed the
        # same number -- computing it from the universe instead made rank strengths disagree with
        # the selection whenever `min_coverage` admitted a partial cross-section.
        take = self.bundle.selection_rule.count_for(len(ranked))
        return [
            self._signal_for(candidate, features[candidate.symbol], ctx.current_time, take)
            for candidate in ranked
            if candidate.selected
        ]

    def _scoreable_symbols(
        self,
        history: Mapping[str, Sequence[PointInTimeBar]],
        decision_time: datetime,
    ) -> tuple[str, ...]:
        """The bound names with enough point-in-time history to be scored at all.

        Every served sequence is validated even for a name that turns out to have too little
        history, so a malformed payload fails loudly instead of quietly shrinking the cross-section.
        """
        scoreable: list[str] = []
        for symbol in self.bundle.universe:
            served = history.get(symbol)
            if served is None:
                continue
            bars = require_bar_sequence(symbol, served)
            window = available_window(bars, decision_time)
            if len(window) >= CROSS_SECTIONAL_WINDOW_BARS:
                scoreable.append(symbol)
        return tuple(scoreable)

    def _coverage_sufficient(self, served: int, population: int) -> bool:
        if served == 0:
            return False
        return Decimal(served) >= self._min_coverage * Decimal(population)

    def _rank(
        self,
        symbols: tuple[str, ...],
        features: Mapping[str, Mapping[str, str]],
    ) -> tuple[RankedCandidate, ...]:
        expected = tuple(self.bundle.standardization.feature_names)
        scored: list[tuple[str, Decimal]] = []
        for symbol in symbols:
            values = features.get(symbol)
            if values is None:
                raise GovernedExecutionError(
                    f"the feature provider returned no values for {symbol!r}, which the served bar "
                    "history says is scoreable. A silently shrunk cross-section changes every rank"
                )
            if tuple(values) != expected:
                raise GovernedExecutionError(
                    f"feature values for {symbol!r} do not match the declared family; the design "
                    "matrix is positional and a reordered row scores against the wrong column"
                )
            standardized = standardize_feature_values(values, self.bundle.standardization)
            scored.append((symbol, score_row(self.bundle.fitted, standardized)))

        # Descending by score, ascending by symbol on a tie. The symbol key is what makes two runs
        # over identical input select identical names.
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        take = self.bundle.selection_rule.count_for(len(scored))
        floor = self._threshold if self.bundle.selection_rule.apply_score_floor else None
        return tuple(
            RankedCandidate(
                symbol=symbol,
                score=score,
                rank=index + 1,
                selected=index < take and (floor is None or score > floor),
            )
            for index, (symbol, score) in enumerate(scored)
        )

    def _signal_for(
        self,
        candidate: RankedCandidate,
        values: Mapping[str, str],
        decision_time: datetime,
        take: int,
    ) -> Signal:
        return Signal(
            symbol=candidate.symbol,
            side=Side.BUY,
            strength=self._strength(candidate.rank, take),
            timestamp=decision_time,
            strategy_name=self.name,
            metadata={
                "apply_score_floor": self.bundle.selection_rule.apply_score_floor,
                "cross_sectional_rank": candidate.rank,
                "decision_at": decision_time.isoformat(),
                "feature_schema_id": self.bundle.evidence.feature_schema_id,
                "feature_schema_version": self.bundle.evidence.feature_schema_version,
                "feature_values": dict(values),
                "fitted_state_hash": self.bundle.fitted.fitted_state_hash,
                "model_card_hash": self.bundle.model_card.model_card_hash,
                "model_id": self.bundle.model_id,
                "preprocessing_state_hash": self.bundle.standardization.state_hash,
                "raw_score": str(candidate.score),
                "score_threshold": self.bundle.score_threshold,
                "selection_fraction": self.bundle.selection_rule.selection_fraction,
                "surface": self.surface.value,
                "universe_size": len(self.bundle.universe),
            },
        )

    def _strength(self, rank: int, take: int) -> float:
        """Map cross-sectional rank into ``[0.0, 1.0]``, strongest at rank 1.

        Rank rather than score distance, because a cross-sectional model's claim is ordinal: it says
        this name should outperform that one, not that either has a particular expected return. The
        single-instrument adapter scales by score distance above its threshold, which is the right
        answer for a model whose claim genuinely *is* the score.

        ``take`` is passed in rather than recomputed so it is necessarily the same count the
        selection used.
        """
        if take <= 1:
            return 1.0
        with localcontext() as context:
            context.prec = 40
            context.rounding = ROUND_HALF_EVEN
            ratio = Decimal(take - rank) / Decimal(take - 1)
        return float(min(Decimal(1), max(Decimal(0), ratio)))
