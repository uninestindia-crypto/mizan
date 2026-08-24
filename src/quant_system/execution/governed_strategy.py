# craft-allow: god-file — one governed boundary for bundle identity, bar integrity, and scoring.
"""Drive execution decisions from a governed, promoted model.

Before this module the system that executed was not the system that was validated. Nothing outside
``quant_system.modeling`` consumed ``RidgeFittedStateV1``, ``ModelCardV1`` or
``predict_ridge_scores``; ``execution`` and ``server`` imported nothing from ``modeling``; and
``strategies/ml_equity.py`` carried a second, ungoverned ridge with no purging, no multiplicity
accounting and no evidence, which is the one execution actually used. Every governed guarantee in
``.launch/`` described code that no live path called.

This adapter closes that gap by binding execution to the artefacts of a governed trial, and by
reusing the training kernels rather than reimplementing them:

* features come from :func:`quant_system.modeling.compute_feature_values`;
* standardization comes from :func:`quant_system.modeling.standardize_feature_values`;
* scoring uses the persisted ``RidgeFittedStateV1`` intercept and coefficients.

Two properties are load-bearing and easy to get wrong.

**The adapter is long-only, because that is what was validated.**
``validation.py`` classifies a row UP when its score exceeds the trial's ``score_threshold``, and
``_portfolio_period_returns`` records a return *only* where the prediction is UP. Every Sharpe,
accuracy and deflated Sharpe in the evidence store was therefore produced by a long-or-flat rule.
Mapping the sign of a score onto BUY/SELL would execute a decision rule the model was never
evaluated under — the same class of defect this module exists to remove. So: BUY, or nothing.

**The threshold is not zero and does not default.** Targets encode UP as ``+1`` and DOWN as ``-1``,
so a ridge fit on standardized features places its intercept at the mean target, which is negative
on any DOWN-skewed instrument. A zero threshold then requires the features to overcome the entire
class skew before a single position is taken; on real INFY data that produced zero UP predictions
across 63 sessions and a terminal ``DEGENERATE_RETURN_SERIES``. ``score_threshold`` is therefore a
required field of the bundle and must equal the value the model was validated at.

What this module does **not** yet do: run inside a live session. Nothing populates
:data:`GOVERNED_BARS_KEY` yet, because the shadow and paper engines are owned by an in-flight repair.
Until that lands, this adapter is exercised by tests and by direct callers, not by a running surface.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from enum import StrEnum
from typing import Any, Final

from quant_system.core.domain import Side, Signal
from quant_system.data.market_data import PointInTimeBar
from quant_system.modeling import (
    CURRENT_FEATURE_SCHEMA_ID,
    CURRENT_FEATURE_SCHEMA_VERSION,
    FEATURE_NAMES_V1,
    ModelCardV1,
    PromotionState,
    RidgeFittedStateV1,
    StandardizationStateV1,
    compute_feature_values,
    standardize_feature_values,
)
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1
from quant_system.modeling.ridge import predict_ridge_scores
from quant_system.strategies.base import BaseStrategy, MarketContext

__all__ = [
    "GOVERNED_BARS_KEY",
    "ModelEvidenceIdentityV1",
    "score_row",
    "ExecutionSurface",
    "GovernedExecutionError",
    "GovernedModelStrategy",
    "PromotedModelBundleV1",
    "SURFACE_ALLOWED_VERDICTS",
]

#: ``MarketContext.extra_data`` key carrying ``Mapping[str, Sequence[PointInTimeBar]]``.
#:
#: A typed ``extra_data`` key rather than a new ``MarketContext`` field, so the change is additive
#: and existing strategies are unaffected. ``PointInTimeBar`` rather than ``PriceBar`` because
#: ``PriceBar`` carries no ``available_at``, and a model fitted under point-in-time discipline then
#: scored on bars whose availability cannot be established has no defensible claim to being
#: point-in-time at the moment that matters. See
#: ``agent_context/decisions/20260822-point-in-time-bars-at-execution.md``.
GOVERNED_BARS_KEY: Final = "governed_point_in_time_bars"


class GovernedExecutionError(RuntimeError):
    """A governed model cannot be executed as configured.

    Raised for configuration and integrity faults, never for a model that simply has no opinion.
    That distinction is deliberate: a misconfigured surface that returned "no signal" would be
    indistinguishable from a healthy model declining to trade.
    """


class ExecutionSurface(StrEnum):
    """Where a governed model is being asked to make decisions."""

    SHADOW = "SHADOW"
    PAPER_PILOT = "PAPER_PILOT"
    PAPER = "PAPER"


#: Which promotion verdicts may drive which surface.
#:
#: A verdict is a ceiling, not a label. A SHADOW-verdict model may only ever run in shadow; it must
#: not be silently promoted by being handed to the paper pilot. REJECT and RESEARCH_ONLY appear
#: nowhere, so they cannot execute anywhere.
SURFACE_ALLOWED_VERDICTS: Final[Mapping[ExecutionSurface, frozenset[PromotionState]]] = {
    ExecutionSurface.SHADOW: frozenset(
        {PromotionState.SHADOW, PromotionState.PAPER_PILOT, PromotionState.PAPER}
    ),
    ExecutionSurface.PAPER_PILOT: frozenset({PromotionState.PAPER_PILOT, PromotionState.PAPER}),
    ExecutionSurface.PAPER: frozenset({PromotionState.PAPER}),
}


@dataclass(frozen=True, slots=True)
class ModelEvidenceIdentityV1:
    """The identity of one published model, taken from a single evidence record.

    This exists because ``candidate_id`` cannot bind a card to a fitted state. Every model in a
    campaign shares one candidate — all 51 trials of the NIFTY 50 run carry ``cand_ridge_v1`` — so a
    candidate check passes for *any* pairing. A Red Team probe used exactly that to build a bundle
    reporting the best model's id while holding the worst model's coefficients, at a threshold from
    neither.

    Every field here comes from the same published manifest, so a bundle cannot straddle two models
    without the forger also fabricating this record.
    """

    model_id: str
    candidate_id: str
    trial_id: str
    symbol: str
    fitted_state_hash: str
    preprocessing_state_hash: str
    score_threshold: str
    feature_schema_id: str
    feature_schema_version: int

    @classmethod
    def from_manifest_metadata(
        cls,
        metadata: Mapping[str, Any],
        *,
        score_threshold: str,
        symbol: str,
    ) -> ModelEvidenceIdentityV1:
        """Derive an identity from one published model manifest's metadata.

        ``score_threshold`` and ``symbol`` are passed separately because neither sits on the model
        manifest: the threshold lives on the trial start record, and the instrument lives on the
        published decision records. The caller must read both from the evidence for this same
        ``trial_id`` and nowhere else.
        """
        try:
            return cls(
                model_id=metadata["model_id"],
                candidate_id=metadata["candidate_id"],
                trial_id=metadata["trial_id"],
                symbol=symbol,
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
class PromotedModelBundleV1:
    """A promoted model plus everything needed to reproduce its decisions.

    Integrity checks here are only the ones that are real. ``fitted.preprocessing_state_hash`` must
    equal ``standardization.state_hash``, which is a genuine binding the training stack already
    maintains, and the card's candidate must match the bundle's. There is deliberately no
    "``model_card_hash`` must re-derive" check: ``ModelCardV1.__post_init__`` recomputes that hash
    from its own fields on every construction, so it re-derives by definition and asserting it would
    be theatre. Card tamper detection belongs at the evidence-store boundary, where
    ``load_persisted_trial_registry`` already performs it.
    """

    candidate_id: str
    model_card: ModelCardV1
    fitted: RidgeFittedStateV1
    standardization: StandardizationStateV1
    score_threshold: str
    evidence: ModelEvidenceIdentityV1

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
        if self.standardization.feature_names != FEATURE_NAMES_V1:
            raise GovernedExecutionError(
                "standardization does not use the closed v1 feature family"
            )
        if (
            self.evidence.feature_schema_id != CURRENT_FEATURE_SCHEMA_ID
            or self.evidence.feature_schema_version != CURRENT_FEATURE_SCHEMA_VERSION
        ):
            raise GovernedExecutionError(
                "model evidence uses an incompatible feature schema; governed execution requires "
                f"{CURRENT_FEATURE_SCHEMA_ID} v{CURRENT_FEATURE_SCHEMA_VERSION}, found "
                f"{self.evidence.feature_schema_id} v{self.evidence.feature_schema_version}. "
                "The model must be retrained under the canonical-window contract"
            )
        if self.model_card.verdict not in {
            PromotionState.SHADOW,
            PromotionState.PAPER_PILOT,
            PromotionState.PAPER,
        }:
            raise GovernedExecutionError(
                f"verdict {self.model_card.verdict.value} is not executable on any surface"
            )
        _require_canonical_decimal(self.score_threshold, "score_threshold")
        self._verify_against_evidence()

    def _verify_against_evidence(self) -> None:
        """Tie the card, the artefacts and the threshold to one published model record.

        Without this, `candidate_id` was the only thing linking a card to a fitted state, and it
        links nothing: a campaign shares one candidate across every model it produces.
        """
        evidence = self.evidence
        if evidence.model_id != self.model_card.model_id:
            raise GovernedExecutionError(
                f"model_id mismatch: the card says {self.model_card.model_id!r} but the evidence "
                f"describes {evidence.model_id!r}; this bundle pairs a card with another model's "
                "artefacts"
            )
        if evidence.candidate_id != self.candidate_id:
            raise GovernedExecutionError("candidate_id does not match the model evidence")
        if evidence.fitted_state_hash != self.fitted.fitted_state_hash:
            raise GovernedExecutionError(
                "fitted state does not match the model evidence; these coefficients were not "
                f"published by {evidence.model_id!r}"
            )
        if evidence.preprocessing_state_hash != self.standardization.state_hash:
            raise GovernedExecutionError("standardization does not match the model evidence")
        if evidence.score_threshold != self.score_threshold:
            raise GovernedExecutionError(
                f"score_threshold {self.score_threshold!r} is not the value trial "
                f"{evidence.trial_id!r} was validated at ({evidence.score_threshold!r}); executing "
                "at a different threshold is a different strategy"
            )

    @property
    def model_id(self) -> str:
        return self.model_card.model_id


def _require_canonical_decimal(value: str, field_name: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except ArithmeticError as error:
        raise GovernedExecutionError(f"{field_name} must be decimal text") from error
    if not parsed.is_finite():
        raise GovernedExecutionError(f"{field_name} must be finite")
    return parsed


class GovernedModelStrategy(BaseStrategy):
    """Emit signals from a promoted model, using the kernels it was trained with.

    Long-only by construction. See the module docstring for why that is a correctness property
    rather than a simplification.
    """

    def __init__(
        self,
        bundle: PromotedModelBundleV1,
        surface: ExecutionSurface,
        *,
        abstain_band: str = "0",
        strength_full_scale: str = "1",
        name: str | None = None,
    ) -> None:
        """Bind a bundle to a surface.

        Args:
            bundle: The promoted model and its preprocessing state.
            surface: Where decisions will be executed. Checked against the card's verdict.
            abstain_band: Non-negative margin above ``score_threshold`` a score must clear before a
                position is taken. A model barely above its threshold should abstain rather than
                trade at negligible conviction. Zero reproduces the validated rule exactly, so it is
                the default; any positive value is *more* conservative than what was validated.
            strength_full_scale: Score distance above the threshold that maps to full strength 1.0.
                Ridge scores are unbounded, so the map saturates rather than normalising.
        """
        allowed = SURFACE_ALLOWED_VERDICTS[surface]
        if bundle.model_card.verdict not in allowed:
            raise GovernedExecutionError(
                f"verdict {bundle.model_card.verdict.value} may not drive surface {surface.value}; "
                f"allowed here: {sorted(state.value for state in allowed)}"
            )
        band = _require_canonical_decimal(abstain_band, "abstain_band")
        if band < 0:
            raise GovernedExecutionError("abstain_band cannot be negative")
        scale = _require_canonical_decimal(strength_full_scale, "strength_full_scale")
        if scale <= 0:
            raise GovernedExecutionError("strength_full_scale must be positive")
        super().__init__(
            name=name or f"governed:{bundle.model_id}",
            params={
                "abstain_band": abstain_band,
                "model_card_hash": bundle.model_card.model_card_hash,
                "model_id": bundle.model_id,
                "feature_schema_id": bundle.evidence.feature_schema_id,
                "feature_schema_version": bundle.evidence.feature_schema_version,
                "score_threshold": bundle.score_threshold,
                "strength_full_scale": strength_full_scale,
                "surface": surface.value,
                "verdict": bundle.model_card.verdict.value,
            },
        )
        self.bundle = bundle
        self.surface = surface
        self._threshold = Decimal(bundle.score_threshold)
        self._band = band
        self._scale = scale

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        """Score the model's bound instrument when sufficient history is available."""
        history = _require_bar_history(ctx)
        symbol = self.bundle.evidence.symbol
        unexpected = [served for served in history if served != symbol]
        if unexpected:
            raise GovernedExecutionError(
                f"this model was fitted on {symbol!r} and cannot score {unexpected[0]!r}. The "
                "governed dataset contract is single-instrument, so a model has no meaning "
                "applied to another instrument's price series"
            )
        if symbol not in history:
            return []
        bars = _require_bar_sequence(symbol, history[symbol])
        signal = self._signal_for(symbol, bars, ctx.current_time)
        return [] if signal is None else [signal]

    def _signal_for(
        self,
        symbol: str,
        bars: tuple[PointInTimeBar, ...],
        decision_time: datetime,
    ) -> Signal | None:
        window = _available_window(bars, decision_time)
        if len(window) < FEATURE_WARMUP_BARS_V1:
            # Too little available history to compute the feature family. No signal is the only
            # honest answer; a degraded one would be scored as if it were comparable.
            return None
        features = compute_feature_values(window)
        standardized = standardize_feature_values(features, self.bundle.standardization)
        score = score_row(self.bundle.fitted, standardized)
        if score <= self._threshold + self._band:
            return None
        return Signal(
            symbol=symbol,
            side=Side.BUY,
            strength=self._strength(score),
            timestamp=decision_time,
            strategy_name=self.name,
            metadata={
                "abstain_band": str(self._band),
                "decision_at": decision_time.isoformat(),
                "feature_values": dict(features),
                "feature_schema_id": self.bundle.evidence.feature_schema_id,
                "feature_schema_version": self.bundle.evidence.feature_schema_version,
                "fitted_state_hash": self.bundle.fitted.fitted_state_hash,
                "model_card_hash": self.bundle.model_card.model_card_hash,
                "model_id": self.bundle.model_id,
                "preprocessing_state_hash": self.bundle.standardization.state_hash,
                "raw_score": str(score),
                "score_threshold": self.bundle.score_threshold,
                "surface": self.surface.value,
            },
        )

    def _strength(self, score: Decimal) -> float:
        """Map score distance above the threshold into ``[0.0, 1.0]``, saturating at full scale."""
        with localcontext() as context:
            context.prec = 40
            context.rounding = ROUND_HALF_EVEN
            excess = score - self._threshold
            ratio = excess / self._scale
        return float(min(Decimal(1), max(Decimal(0), ratio)))


def _require_bar_sequence(symbol: str, served: object) -> tuple[PointInTimeBar, ...]:
    """Coerce one symbol's served history to bars, or fail with a code a caller can match.

    Previously a malformed value reached the feature kernel and surfaced as ``TypeError`` or
    ``AttributeError`` — indistinguishable from a genuine bug in the model code. An empty sequence
    stays legal: served-nothing is a real outcome, malformed is not, and the two must not collapse
    into one another.
    """
    if isinstance(served, str) or not isinstance(served, Sequence):
        raise GovernedExecutionError(
            f"bar history for {symbol!r} must be a sequence of PointInTimeBar, got "
            f"{type(served).__name__}"
        )
    bars = tuple(served)
    if any(not isinstance(bar, PointInTimeBar) for bar in bars):
        raise GovernedExecutionError(
            f"bar history for {symbol!r} contains an entry that is not a PointInTimeBar"
        )
    mismatched_symbol = next((bar.symbol for bar in bars if bar.symbol != symbol), None)
    if mismatched_symbol is not None:
        raise GovernedExecutionError(
            f"bar history bound to {symbol!r} contains a bar for {mismatched_symbol!r}. The map key "
            "cannot substitute for the instrument identity carried by each point-in-time record"
        )
    dates = [bar.exchange_date for bar in bars]
    if len(set(dates)) != len(dates):
        raise GovernedExecutionError(
            f"bar history for {symbol!r} contains duplicate exchange dates. The training builder "
            "rejects the same input as RECORD_ORDER_INVALID, and overlapping bars silently change "
            "feature values rather than failing"
        )
    return bars


def _require_bar_history(ctx: MarketContext) -> Mapping[str, Sequence[PointInTimeBar]]:
    """Extract the governed bar history, refusing to proceed if the surface never supplied it."""
    raw = ctx.extra_data.get(GOVERNED_BARS_KEY)
    if raw is None:
        raise GovernedExecutionError(
            f"MarketContext.extra_data is missing {GOVERNED_BARS_KEY!r}. A governed model needs "
            "point-in-time bar history; returning no signal here would make a misconfigured "
            "surface look like a model with no opinion"
        )
    if not isinstance(raw, Mapping):
        raise GovernedExecutionError(f"{GOVERNED_BARS_KEY!r} must map symbol to a bar sequence")
    return raw


def _available_window(
    bars: tuple[PointInTimeBar, ...],
    decision_time: datetime,
) -> tuple[PointInTimeBar, ...]:
    """Keep only bars whose information was available by the decision, oldest first.

    This is the execution-side half of the point-in-time guarantee. The training builder rejects a
    feature row whose inputs were not available by its decision time; here the same rule is applied
    by filtering, because at execution a not-yet-available bar is an ordinary occurrence rather than
    a defect in the dataset.
    """
    available = tuple(bar for bar in bars if bar.available_at <= decision_time)
    return tuple(sorted(available, key=lambda bar: bar.exchange_date))


def score_row(fitted: RidgeFittedStateV1, standardized: tuple[str, ...]) -> Decimal:
    """Score one standardized row with the **validated** scorer.

    This calls ``predict_ridge_scores`` rather than recomputing the dot product. An earlier version
    reimplemented it in Decimal for "exact reconciliation"; a Red Team probe showed the two
    disagreeing by 4e-13, which flipped a decision at the threshold — the adapter traded where
    validation had recorded nothing. Faithfulness to the validated rule beats arithmetic purity, and
    the only way to guarantee it is to run the same function.
    """
    if len(standardized) != len(fitted.coefficients):
        raise GovernedExecutionError(
            "standardized row width does not match the fitted coefficients"
        )
    return Decimal(predict_ridge_scores(fitted, (standardized,))[0])
