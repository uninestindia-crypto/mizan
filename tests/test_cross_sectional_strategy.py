"""Tests for the cross-sectional governed execution adapter.

The gap under guard: a ranking model had no surface at all. `GovernedModelStrategy` binds one
instrument and raises on the second, which is correct for a single-instrument model and makes every
cross-sectional model unexecutable.

These tests hold the new adapter to the properties that make a *ranking* decision faithful rather
than merely plausible: the cross-section it ranks is the one the model was validated over, the
selection rule travels with the bundle instead of being invented at execution, ties do not move
between runs, and nothing about the verdict gate is softer here than on the path it sits beside.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.core.domain import Side
from quant_system.data.market_data import PointInTimeBar
from quant_system.execution.cross_sectional_strategy import (
    CROSS_SECTIONAL_WINDOW_BARS,
    CrossSectionalEvidenceIdentityV1,
    CrossSectionalModelStrategy,
    CrossSectionalSelectionRuleV1,
    PromotedCrossSectionalBundleV1,
)
from quant_system.execution.governed_strategy import (
    GOVERNED_BARS_KEY,
    ExecutionSurface,
    GovernedExecutionError,
)
from quant_system.modeling import ModelCardV1, PromotionState
from quant_system.modeling.preprocessing import StandardizationStateV1
from quant_system.modeling.ridge import RidgeFittedStateV1
from quant_system.modeling.rows import (
    FEATURE_NAMES_V1,
    FEATURE_NAMES_V3,
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V3,
)
from quant_system.strategies.base import MarketContext

CANDIDATE = "cand_mizan_v1"
MODEL_ID = "model_cross_sectional_test"
UNIVERSE = ("AAA", "BBB", "CCC", "DDD", "EEE")
DECISION_AT = datetime(2026, 8, 26, 10, 0, tzinfo=UTC)
_ROWS_HASH = "a" * 64
_TARGET_HASH = "b" * 64

#: The real published Mizan model, used by one grounding test below.
_MIZAN_MANIFEST = Path(
    "data/evidence/models/mizan-v1/models/model_1f936eadcb8d44154f28af13/manifest.json"
)


# --------------------------------------------------------------------------------------------
# Fixtures: a v3 fifteen-feature model that genuinely binds, built the way training builds one.
# --------------------------------------------------------------------------------------------


def _standardization() -> StandardizationStateV1:
    """A v3 standardization state. Unit scales keep the arithmetic legible in assertions."""
    return StandardizationStateV1(
        feature_names=FEATURE_NAMES_V3,
        means=tuple("0" for _ in FEATURE_NAMES_V3),
        scales=tuple("1" for _ in FEATURE_NAMES_V3),
        zero_variance_features=(),
        training_feature_rows_hash=_ROWS_HASH,
    )


def _fitted(standardization: StandardizationStateV1) -> RidgeFittedStateV1:
    """A fitted state weighting only ``return_1``, so a test can set a name's rank directly."""
    coefficients = tuple("1" if name == "return_1" else "0" for name in FEATURE_NAMES_V3)
    return RidgeFittedStateV1(
        intercept="0",
        coefficients=coefficients,
        l2_penalty="1",
        preprocessing_state_hash=standardization.state_hash,
        training_target_hash=_TARGET_HASH,
        feature_names=FEATURE_NAMES_V3,
    )


def _card(
    verdict: PromotionState = PromotionState.SHADOW,
    candidate_id: str = CANDIDATE,
    model_id: str = MODEL_ID,
) -> ModelCardV1:
    return ModelCardV1(
        model_id=model_id,
        candidate_id=candidate_id,
        verdict=verdict,
        created_at=datetime(2026, 8, 26, 9, 0, tzinfo=UTC),
        monitoring_limits={"max_drawdown": "0.10"},
        halt_and_rollback_policy="halt on breach and roll back to the previous active model",
        limitations=("research evidence only",),
    )


def _bundle(
    *,
    verdict: PromotionState = PromotionState.SHADOW,
    selection_fraction: str = "0.4",
    apply_score_floor: bool = False,
    score_threshold: str = "0",
    symbols: tuple[str, ...] = UNIVERSE,
    standardization: StandardizationStateV1 | None = None,
    fitted: RidgeFittedStateV1 | None = None,
) -> PromotedCrossSectionalBundleV1:
    preprocessing = standardization or _standardization()
    fitted_state = fitted or _fitted(preprocessing)
    return PromotedCrossSectionalBundleV1(
        candidate_id=CANDIDATE,
        model_card=_card(verdict=verdict),
        fitted=fitted_state,
        standardization=preprocessing,
        score_threshold=score_threshold,
        selection_rule=CrossSectionalSelectionRuleV1(
            selection_fraction=selection_fraction,
            apply_score_floor=apply_score_floor,
        ),
        evidence=CrossSectionalEvidenceIdentityV1(
            model_id=MODEL_ID,
            candidate_id=CANDIDATE,
            trial_id="trial_cross_sectional_test",
            symbols=tuple(sorted(symbols)),
            fitted_state_hash=fitted_state.fitted_state_hash,
            preprocessing_state_hash=preprocessing.state_hash,
            score_threshold=score_threshold,
            feature_schema_id=FEATURE_SCHEMA_ID_V3,
            feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
        ),
    )


def _bars(symbol: str, count: int = CROSS_SECTIONAL_WINDOW_BARS) -> tuple[PointInTimeBar, ...]:
    """A point-in-time bar sequence long enough to be scoreable, all available before the decision."""
    bars: list[PointInTimeBar] = []
    for index in range(count):
        event_at = DECISION_AT - timedelta(days=count - index)
        bars.append(
            PointInTimeBar(
                provider_instrument_id=f"NSE_EQ|{symbol}",
                symbol=symbol,
                exchange_date=date(2026, 1, 1) + timedelta(days=index),
                event_at=event_at,
                provider_at=event_at,
                ingested_at=event_at + timedelta(hours=1),
                available_at=event_at,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1000,
                open_interest=0,
                source_row_index=index,
            )
        )
    return tuple(bars)


def _history(symbols: tuple[str, ...] = UNIVERSE, bar_count: int = CROSS_SECTIONAL_WINDOW_BARS):
    return {symbol: _bars(symbol, bar_count) for symbol in symbols}


def _features(scores: dict[str, str]):
    """Feature rows whose ``return_1`` carries the intended score and whose rest are zero."""

    def provider(symbols: tuple[str, ...], decision_time: datetime):
        return {
            symbol: {
                name: (scores[symbol] if name == "return_1" else "0") for name in FEATURE_NAMES_V3
            }
            for symbol in symbols
        }

    return provider


def _context(history) -> MarketContext:
    return MarketContext(
        current_time=DECISION_AT,
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("1000000"),
        extra_data={GOVERNED_BARS_KEY: history},
    )


def _strategy(bundle=None, **kwargs) -> CrossSectionalModelStrategy:
    scores = kwargs.pop("scores", {s: str(i) for i, s in enumerate(UNIVERSE)})
    return CrossSectionalModelStrategy(
        bundle or _bundle(),
        kwargs.pop("surface", ExecutionSurface.SHADOW),
        _features(scores),
        **kwargs,
    )


# --------------------------------------------------------------------------------------------
# The verdict gate is not softer here than on the single-instrument path.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("verdict", [PromotionState.RESEARCH_ONLY, PromotionState.REJECT])
def test_unpromotable_verdict_cannot_be_bundled(verdict: PromotionState) -> None:
    """A model no surface accepts must not assemble into a bundle at all.

    This is the check that stops the Mizan models, both of which publish RESEARCH_ONLY.
    """
    with pytest.raises(GovernedExecutionError, match="not executable on any surface"):
        _bundle(verdict=verdict)


def test_shadow_verdict_may_not_drive_the_paper_surface() -> None:
    """A verdict is a ceiling, not a label; a SHADOW model must not be promoted by being handed on."""
    with pytest.raises(GovernedExecutionError, match="may not drive the PAPER surface"):
        _strategy(_bundle(verdict=PromotionState.SHADOW), surface=ExecutionSurface.PAPER)


def test_paper_verdict_may_drive_the_shadow_surface() -> None:
    """The ceiling runs one way: a fully promoted model may still run on a lesser surface."""
    strategy = _strategy(_bundle(verdict=PromotionState.PAPER), surface=ExecutionSurface.SHADOW)
    assert strategy.surface is ExecutionSurface.SHADOW


# --------------------------------------------------------------------------------------------
# The cross-section that is ranked must be the one the model was validated over.
# --------------------------------------------------------------------------------------------


def test_a_symbol_outside_the_bound_universe_is_refused() -> None:
    """An extra name changes what every other name is ranked against, so it is an error not a skip."""
    history = _history((*UNIVERSE, "ZZZ"))
    with pytest.raises(GovernedExecutionError, match="outside this model's bound universe"):
        _strategy().generate_signals(_context(history))


def test_a_partial_cross_section_abstains_rather_than_ranking_the_remainder() -> None:
    """Missing names move every rank. Ranking what is left would be a strategy nobody measured."""
    history = _history(UNIVERSE[:3])
    assert _strategy().generate_signals(_context(history)) == []


def test_a_short_history_makes_a_name_unscoreable_and_the_cross_section_partial() -> None:
    history = _history()
    history["CCC"] = _bars("CCC", CROSS_SECTIONAL_WINDOW_BARS - 1)
    assert _strategy().generate_signals(_context(history)) == []


def test_min_coverage_relaxes_the_full_cross_section_requirement_deliberately() -> None:
    """Partial coverage is available, but only by declaring it -- never as a silent fallback."""
    history = _history(UNIVERSE[:4])
    signals = _strategy(min_coverage="0.8").generate_signals(_context(history))
    # 0.4 of the four names actually ranked, not of the five bound: the fraction applies to the
    # cross-section the model sees, which is what each rebalance in the screen did.
    assert [signal.symbol for signal in signals] == ["DDD", "CCC"]


def test_bars_carrying_another_instrument_are_refused() -> None:
    """The per-bar symbol check is reused, not reimplemented.

    A recheck of the single-instrument path found bars whose own symbol was RELIANCE passing under
    the map key INFY, because the key was checked and the record was not. Reusing that function is
    the reason it was promoted to a public name.
    """
    history = _history()
    history["AAA"] = _bars("BBB")
    with pytest.raises(GovernedExecutionError, match="contains a bar for 'BBB'"):
        _strategy().generate_signals(_context(history))


def test_missing_bar_history_is_an_error_not_an_abstention() -> None:
    context = MarketContext(
        current_time=DECISION_AT,
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("1000000"),
        extra_data={},
    )
    with pytest.raises(GovernedExecutionError, match="missing"):
        _strategy().generate_signals(context)


# --------------------------------------------------------------------------------------------
# Ranking and selection.
# --------------------------------------------------------------------------------------------


def test_the_declared_fraction_selects_the_top_of_the_ranking() -> None:
    """0.4 of five names is two, and they are the two highest scores."""
    scores = {"AAA": "5", "BBB": "1", "CCC": "4", "DDD": "2", "EEE": "3"}
    signals = _strategy(scores=scores).generate_signals(_context(_history()))
    assert [signal.symbol for signal in signals] == ["AAA", "CCC"]
    assert all(signal.side is Side.BUY for signal in signals)


def test_the_selection_fraction_rounds_up_so_a_small_universe_still_trades() -> None:
    """Rounding down would make a five-name universe at 0.1 abstain entirely and silently."""
    signals = _strategy(_bundle(selection_fraction="0.1")).generate_signals(_context(_history()))
    assert len(signals) == 1


def test_ties_break_by_symbol_so_two_identical_runs_select_identical_names() -> None:
    """Every name scores the same; only the deterministic tie-break decides who is selected."""
    scores = dict.fromkeys(UNIVERSE, "1")
    strategy = _strategy(scores=scores)
    first = [signal.symbol for signal in strategy.generate_signals(_context(_history()))]
    second = [signal.symbol for signal in strategy.generate_signals(_context(_history()))]
    assert first == second == ["AAA", "BBB"]


def test_rank_is_recorded_on_every_signal() -> None:
    scores = {"AAA": "5", "BBB": "1", "CCC": "4", "DDD": "2", "EEE": "3"}
    signals = _strategy(scores=scores).generate_signals(_context(_history()))
    assert [signal.metadata["cross_sectional_rank"] for signal in signals] == [1, 2]


def test_strength_is_ordinal_and_strongest_at_rank_one() -> None:
    """A cross-sectional claim is ordinal, so strength tracks rank rather than score distance."""
    scores = {"AAA": "5", "BBB": "1", "CCC": "4", "DDD": "2", "EEE": "3"}
    signals = _strategy(scores=scores).generate_signals(_context(_history()))
    assert signals[0].strength == 1.0
    assert signals[1].strength == 0.0


def test_the_score_floor_applies_only_when_the_bundle_declares_it() -> None:
    """The screen ranked without a floor. Applying one silently would change the strategy."""
    scores = {"AAA": "-5", "BBB": "-4", "CCC": "-3", "DDD": "-2", "EEE": "-1"}
    without_floor = _strategy(_bundle(score_threshold="0"), scores=scores)
    assert len(without_floor.generate_signals(_context(_history()))) == 2

    with_floor = _strategy(_bundle(score_threshold="0", apply_score_floor=True), scores=scores)
    assert with_floor.generate_signals(_context(_history())) == []


def test_a_provider_that_omits_a_scoreable_symbol_is_refused() -> None:
    """A silently shrunk cross-section changes every rank, so it must not pass as an abstention."""

    def incomplete(symbols: tuple[str, ...], decision_time: datetime):
        return {
            symbol: dict.fromkeys(FEATURE_NAMES_V3, "0") for symbol in symbols if symbol != "AAA"
        }

    strategy = CrossSectionalModelStrategy(_bundle(), ExecutionSurface.SHADOW, incomplete)
    with pytest.raises(GovernedExecutionError, match="returned no values for 'AAA'"):
        strategy.generate_signals(_context(_history()))


def test_a_reordered_feature_row_is_refused() -> None:
    """The design matrix is positional; a reordered row would score against the wrong column."""

    def reordered(symbols: tuple[str, ...], decision_time: datetime):
        names = tuple(reversed(FEATURE_NAMES_V3))
        return {symbol: dict.fromkeys(names, "0") for symbol in symbols}

    strategy = CrossSectionalModelStrategy(_bundle(), ExecutionSurface.SHADOW, reordered)
    with pytest.raises(GovernedExecutionError, match="do not match the declared family"):
        strategy.generate_signals(_context(_history()))


# --------------------------------------------------------------------------------------------
# Bundle and identity integrity.
# --------------------------------------------------------------------------------------------


def test_a_fitted_state_the_model_never_published_is_refused() -> None:
    """`candidate_id` links nothing: a campaign shares one candidate across every model it produces."""
    standardization = _standardization()
    fitted = _fitted(standardization)
    with pytest.raises(GovernedExecutionError, match="not the one this model published"):
        PromotedCrossSectionalBundleV1(
            candidate_id=CANDIDATE,
            model_card=_card(),
            fitted=fitted,
            standardization=standardization,
            score_threshold="0",
            selection_rule=CrossSectionalSelectionRuleV1("0.2"),
            evidence=CrossSectionalEvidenceIdentityV1(
                model_id=MODEL_ID,
                candidate_id=CANDIDATE,
                trial_id="trial_cross_sectional_test",
                symbols=UNIVERSE,
                fitted_state_hash="c" * 64,
                preprocessing_state_hash=standardization.state_hash,
                score_threshold="0",
                feature_schema_id=FEATURE_SCHEMA_ID_V3,
                feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
            ),
        )


def test_a_threshold_the_trial_never_recorded_is_refused() -> None:
    standardization = _standardization()
    fitted = _fitted(standardization)
    with pytest.raises(GovernedExecutionError, match="does not match the threshold"):
        PromotedCrossSectionalBundleV1(
            candidate_id=CANDIDATE,
            model_card=_card(),
            fitted=fitted,
            standardization=standardization,
            score_threshold="0.5",
            selection_rule=CrossSectionalSelectionRuleV1("0.2"),
            evidence=CrossSectionalEvidenceIdentityV1(
                model_id=MODEL_ID,
                candidate_id=CANDIDATE,
                trial_id="trial_cross_sectional_test",
                symbols=UNIVERSE,
                fitted_state_hash=fitted.fitted_state_hash,
                preprocessing_state_hash=standardization.state_hash,
                score_threshold="0",
                feature_schema_id=FEATURE_SCHEMA_ID_V3,
                feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
            ),
        )


def test_a_standardization_from_a_different_family_than_the_schema_declares_is_refused() -> None:
    """The v1 six-feature scaler against a v3 schema is a fifteen-column model fed six columns."""
    six = StandardizationStateV1(
        feature_names=FEATURE_NAMES_V1,
        means=tuple("0" for _ in range(6)),
        scales=tuple("1" for _ in range(6)),
        zero_variance_features=(),
        training_feature_rows_hash=_ROWS_HASH,
    )
    fitted = RidgeFittedStateV1(
        intercept="0",
        coefficients=tuple("0" for _ in range(6)),
        l2_penalty="1",
        preprocessing_state_hash=six.state_hash,
        training_target_hash=_TARGET_HASH,
    )
    with pytest.raises(GovernedExecutionError, match="feature family its schema declares"):
        _bundle(standardization=six, fitted=fitted)


def test_an_unsorted_universe_is_refused() -> None:
    """Two bundles over the same names must compare and hash identically."""
    with pytest.raises(GovernedExecutionError, match="must be sorted"):
        CrossSectionalEvidenceIdentityV1(
            model_id=MODEL_ID,
            candidate_id=CANDIDATE,
            trial_id="trial_cross_sectional_test",
            symbols=("EEE", "AAA", "BBB", "CCC", "DDD"),
            fitted_state_hash="c" * 64,
            preprocessing_state_hash="d" * 64,
            score_threshold="0",
            feature_schema_id=FEATURE_SCHEMA_ID_V3,
            feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
        )


def test_a_duplicated_name_in_the_universe_is_refused() -> None:
    with pytest.raises(GovernedExecutionError, match="duplicate symbol"):
        CrossSectionalEvidenceIdentityV1(
            model_id=MODEL_ID,
            candidate_id=CANDIDATE,
            trial_id="trial_cross_sectional_test",
            symbols=("AAA", "AAA", "BBB"),
            fitted_state_hash="c" * 64,
            preprocessing_state_hash="d" * 64,
            score_threshold="0",
            feature_schema_id=FEATURE_SCHEMA_ID_V3,
            feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
        )


@pytest.mark.parametrize("fraction", ["0", "-0.1", "1.5", "NaN", "Infinity", "abc"])
def test_an_invalid_selection_fraction_is_refused(fraction: str) -> None:
    with pytest.raises(GovernedExecutionError):
        CrossSectionalSelectionRuleV1(fraction)


@pytest.mark.parametrize(
    ("population", "fraction", "expected"),
    [(0, "0.2", 0), (1, "0.2", 1), (5, "0.2", 1), (10, "0.2", 2), (43, "0.2", 9), (50, "0.2", 10)],
)
def test_selection_count_is_exact_at_the_boundaries(
    population: int, fraction: str, expected: int
) -> None:
    """Computed in exact integer arithmetic; routing a Decimal through float can round either way."""
    assert CrossSectionalSelectionRuleV1(fraction).count_for(population) == expected


# --------------------------------------------------------------------------------------------
# Grounding: the real published Mizan model.
# --------------------------------------------------------------------------------------------


# test-allow: skipped-test — conditional skip when optional local evidence store is absent
@pytest.mark.skipif(not _MIZAN_MANIFEST.exists(), reason="Mizan evidence store not present")
def test_the_real_mizan_model_reconstructs_and_is_then_refused_as_research_only() -> None:
    """The gate that matters, exercised against the model this work was actually asked about.

    The fitted state is reconstructed from the published manifest and must rehash to the recorded
    ``fitted_state_hash`` -- otherwise this test would be asserting against a model the trial never
    published. It then fails to bundle, because both Mizan models are RESEARCH_ONLY.
    """
    metadata = json.loads(_MIZAN_MANIFEST.read_text(encoding="utf-8"))["metadata"]
    published = metadata["fitted_state"]
    preprocessing = metadata["preprocessing"]

    standardization = StandardizationStateV1(
        feature_names=tuple(preprocessing["feature_names"]),
        means=tuple(preprocessing["means"]),
        scales=tuple(preprocessing["scales"]),
        zero_variance_features=tuple(preprocessing["zero_variance_features"]),
        training_feature_rows_hash=preprocessing["training_feature_rows_hash"],
    )
    assert standardization.state_hash == preprocessing["state_hash"]

    fitted = RidgeFittedStateV1(
        intercept=published["intercept"],
        coefficients=tuple(published["coefficients"]),
        l2_penalty=published["l2_penalty"],
        preprocessing_state_hash=published["preprocessing_state_hash"],
        training_target_hash=published["training_target_hash"],
        feature_names=tuple(published["coefficient_names"]),
    )
    assert fitted.fitted_state_hash == published["fitted_state_hash"]
    assert metadata["verdict"] == "RESEARCH_ONLY"

    card = ModelCardV1(
        model_id=metadata["model_id"],
        candidate_id=metadata["candidate_id"],
        verdict=PromotionState.RESEARCH_ONLY,
        created_at=datetime(2026, 8, 25, 19, 33, tzinfo=UTC),
        monitoring_limits={"max_drawdown": "0.10"},
        halt_and_rollback_policy="halt on breach and roll back to the previous active model",
        limitations=("research evidence only",),
    )
    with pytest.raises(GovernedExecutionError, match="not executable on any surface"):
        PromotedCrossSectionalBundleV1(
            candidate_id=metadata["candidate_id"],
            model_card=card,
            fitted=fitted,
            standardization=standardization,
            score_threshold="0",
            selection_rule=CrossSectionalSelectionRuleV1("0.2"),
            evidence=CrossSectionalEvidenceIdentityV1(
                model_id=metadata["model_id"],
                candidate_id=metadata["candidate_id"],
                trial_id=metadata["trial_id"],
                symbols=("AAA",),
                fitted_state_hash=fitted.fitted_state_hash,
                preprocessing_state_hash=standardization.state_hash,
                score_threshold="0",
                feature_schema_id=metadata["feature_schema_id"],
                feature_schema_version=metadata["feature_schema_version"],
            ),
        )
