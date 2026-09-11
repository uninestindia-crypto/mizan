"""Leakage-safe walk-forward evaluation of a short-horizon return predictor.

What this does, and the order it does it in
-------------------------------------------
The order matters more than any individual step, because each one is a place a result can be
manufactured:

1. **Reserve the holdout first**, before anything looks at anything. A holdout carved out after the
   folds are chosen is not a holdout.
2. **Split the remainder** into purged, embargoed, chronological folds (``walkforward``).
3. **Fit per fold, on training rows only** -- including the standardisation. Scaling fitted on the
   whole sample leaks the validation distribution into training, and it leaks it *silently*.
4. **Collect out-of-sample predictions** from every fold's validation segment.
5. **Calibrate abstention once**, on those pooled out-of-sample predictions, never on the holdout.
6. **Score against baselines** on identical decisions, with identical costs.

The holdout is not touched by anything in this module. Evaluating it is a separate, explicit call the
caller makes exactly once, after the candidate is frozen.

Why a ridge, and why no hyperparameter search
---------------------------------------------
The declared candidate is "a simple return-prediction model". A ridge with one fixed penalty is that:
linear, closed-form, no seeds, no early stopping, nothing to tune. Searching the penalty would be
more trials against the frozen budget, and the budget is six.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import numpy as np

from quant_system.research_short_horizon.abstention import (
    AbstentionPolicy,
    CalibrationOutcome,
    calibrate_threshold,
)
from quant_system.research_short_horizon.walkforward import walk_forward_folds

__all__ = [
    "Decision",
    "EvaluationResult",
    "StrategyScore",
    "evaluate_walk_forward",
    "fit_ridge",
    "score_decisions",
]


@dataclass(frozen=True, slots=True)
class Decision:
    """One instrument on one decision date, with everything needed to score it.

    ``net_return`` is what a long position would have earned, already net of the dated NSE costs the
    governed label path priced. ``previous_return`` is the trailing one-session return, kept so the
    PREVIOUS_SIGN baseline is computed from the same rows as the candidate rather than from a
    separately assembled series that might not line up.
    """

    on: date
    symbol: str
    features: tuple[float, ...]
    net_return: Decimal
    previous_return: float


@dataclass(frozen=True, slots=True)
class StrategyScore:
    """What one strategy earned over a set of decisions."""

    strategy_id: str
    decisions: int
    trades: int
    exposure: float
    mean_net_return_per_decision: Decimal
    total_net_return: Decimal
    sharpe: float
    max_drawdown: float
    hit_rate: float

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "decisions": self.decisions,
            "trades": self.trades,
            "exposure": round(self.exposure, 6),
            "mean_net_return_per_decision": str(self.mean_net_return_per_decision),
            "total_net_return": str(self.total_net_return),
            "sharpe": round(self.sharpe, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "hit_rate": round(self.hit_rate, 6),
        }


@dataclass
class EvaluationResult:
    """Everything one trial produced, including what it declined to do."""

    held_sessions: int
    horizon_sessions: int
    folds: int
    train_rows: int
    validation_rows: int
    purged_rows: int
    embargoed_rows: int
    calibration: CalibrationOutcome
    missing_predictions: int = 0
    """Out-of-sample decisions an external forecaster had no forecast for.

    Non-zero means those decisions were scored as a forecast of exactly zero, which the long-only
    abstention rule turns into cash. That is a silent degradation: the arm looks selective when it is
    really uninformed, so the count travels with the result rather than being absorbed into it.
    """
    scores: list[StrategyScore] = field(default_factory=list)

    @property
    def candidate(self) -> StrategyScore:
        return next(score for score in self.scores if score.strategy_id == "CANDIDATE")


def fit_ridge(features: np.ndarray, targets: np.ndarray, penalty: float) -> np.ndarray:
    """Closed-form ridge with an unpenalised intercept, fitted on the rows given and no others.

    The intercept is excluded from the penalty deliberately. Penalising it shrinks the fitted mean
    toward zero, which for a return-prediction model means shrinking toward "no drift" -- a
    substantive claim about the market smuggled in as a numerical convenience.
    """
    rows, columns = features.shape
    design = np.column_stack([np.ones(rows), features])
    regulariser = np.eye(columns + 1) * penalty
    regulariser[0, 0] = 0.0
    gram = design.T @ design + regulariser
    return np.linalg.solve(gram, design.T @ targets)


def _standardise(train: np.ndarray, other: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Centre and scale using **training** moments only.

    Fitting the scaler on everything is the classic silent leak: it never errors, it improves the
    result, and the improvement is the validation distribution leaking into the training rows.
    """
    mean = train.mean(axis=0)
    deviation = train.std(axis=0)
    deviation[deviation == 0] = 1.0
    return (train - mean) / deviation, (other - mean) / deviation


def score_decisions(
    strategy_id: str,
    decisions: Sequence[Decision],
    take: Sequence[bool],
    *,
    periods_per_year: float,
) -> StrategyScore:
    """Score one strategy over the decisions it was given.

    ``mean_net_return_per_decision`` divides by **every** decision faced, not by the trades taken.
    Dividing by trades rewards abstaining down to a handful of lucky calls; dividing by decisions
    prices the cash periods at the zero they actually earn.
    """
    total = len(decisions)
    if total == 0:
        raise ValueError(f"{strategy_id}: cannot score zero decisions")
    realised = [
        decision.net_return if acted else Decimal(0)
        for decision, acted in zip(decisions, take, strict=True)
    ]
    trades = sum(1 for acted in take if acted)
    wins = sum(1 for value, acted in zip(realised, take, strict=True) if acted and value > 0)

    # Aggregate to one portfolio return per decision date: decisions on the same date are held
    # simultaneously, so treating them as separate periods would understate volatility.
    by_date: dict[date, list[Decimal]] = {}
    for decision, value in zip(decisions, realised, strict=True):
        by_date.setdefault(decision.on, []).append(value)
    periods = [
        float(sum(values, start=Decimal(0)) / Decimal(len(values)))
        for _, values in sorted(by_date.items())
    ]

    series = np.asarray(periods, dtype=float)
    mean = float(series.mean()) if series.size else 0.0
    deviation = float(series.std(ddof=1)) if series.size > 1 else 0.0
    sharpe = (mean / deviation) * float(np.sqrt(periods_per_year)) if deviation > 0 else 0.0

    equity = np.cumprod(1.0 + series) if series.size else np.array([1.0])
    peak = np.maximum.accumulate(equity)
    drawdown = float(np.max((peak - equity) / peak)) if series.size else 0.0

    return StrategyScore(
        strategy_id=strategy_id,
        decisions=total,
        trades=trades,
        exposure=trades / total,
        mean_net_return_per_decision=sum(realised, start=Decimal(0)) / Decimal(total),
        total_net_return=Decimal(str(float(equity[-1] - 1.0))) if series.size else Decimal(0),
        sharpe=sharpe,
        max_drawdown=drawdown,
        hit_rate=(wins / trades) if trades else 0.0,
    )


def evaluate_walk_forward(
    decisions: Sequence[Decision],
    *,
    held_sessions: int,
    horizon_sessions: int,
    embargo_sessions: int,
    validation_size: int,
    minimum_train: int,
    penalty: float,
    periods_per_year: float,
    minimum_trades: int = 30,
    predictions: dict[tuple[date, str], float] | None = None,
) -> EvaluationResult:
    """Run the whole out-of-sample pass and return every strategy's score.

    ``predictions`` lets an *external* forecaster supply its own numbers keyed by (date, symbol) --
    that is how the TimesFM arm plugs in. It is zero-shot, so it has nothing to fit and its training
    folds are used only to decide which decisions are out-of-sample for the ridge, keeping the two
    arms scored on the identical decision set.
    """
    ordered_dates = sorted({decision.on for decision in decisions})
    folds = walk_forward_folds(
        ordered_dates,
        horizon_sessions=horizon_sessions,
        embargo_sessions=embargo_sessions,
        validation_size=validation_size,
        minimum_train=minimum_train,
    )
    by_date: dict[date, list[Decision]] = {}
    for decision in decisions:
        by_date.setdefault(decision.on, []).append(decision)

    out_of_sample: list[Decision] = []
    scores: list[float] = []
    train_rows = validation_rows = purged_rows = embargoed_rows = missing = 0

    for fold in folds:
        train = [row for on in fold.train for row in by_date.get(on, [])]
        validation = [row for on in fold.validation for row in by_date.get(on, [])]
        train_rows += len(train)
        validation_rows += len(validation)
        purged_rows += sum(len(by_date.get(on, [])) for on in fold.purged)
        embargoed_rows += sum(len(by_date.get(on, [])) for on in fold.embargoed)
        if not train or not validation:
            continue

        if predictions is None:
            train_x = np.asarray([row.features for row in train], dtype=float)
            train_y = np.asarray([float(row.net_return) for row in train], dtype=float)
            validation_x = np.asarray([row.features for row in validation], dtype=float)
            scaled_train, scaled_validation = _standardise(train_x, validation_x)
            coefficients = fit_ridge(scaled_train, train_y, penalty)
            fold_scores = (
                np.column_stack([np.ones(len(validation)), scaled_validation]) @ coefficients
            )
        else:
            missing += sum(1 for row in validation if (row.on, row.symbol) not in predictions)
            fold_scores = np.asarray(
                [predictions.get((row.on, row.symbol), 0.0) for row in validation], dtype=float
            )

        out_of_sample.extend(validation)
        scores.extend(float(value) for value in fold_scores)

    if not out_of_sample:
        raise ValueError("no out-of-sample decision survived the fold construction")

    calibration = calibrate_threshold(
        [Decimal(str(value)) for value in scores],
        [row.net_return for row in out_of_sample],
        partition_label="walk-forward validation folds (holdout untouched)",
        minimum_trades=minimum_trades,
        long_only=True,
    )
    policy = calibration.policy

    result = EvaluationResult(
        held_sessions=held_sessions,
        horizon_sessions=horizon_sessions,
        folds=len(folds),
        train_rows=train_rows,
        validation_rows=validation_rows,
        purged_rows=purged_rows,
        embargoed_rows=embargoed_rows,
        calibration=calibration,
        missing_predictions=missing,
    )
    result.scores = _all_scores(out_of_sample, scores, policy, periods_per_year=periods_per_year)
    return result


def _all_scores(
    decisions: Sequence[Decision],
    scores: Sequence[float],
    policy: AbstentionPolicy,
    *,
    periods_per_year: float,
) -> list[StrategyScore]:
    """The candidate and every baseline, over the identical decision set.

    Identical decisions, deliberately. A baseline computed over a different set of dates or names is
    not a comparison, and the difference between two such numbers is uninterpretable.
    """
    return [
        score_decisions(
            "CANDIDATE",
            decisions,
            [policy.acts_on(Decimal(str(value))) for value in scores],
            periods_per_year=periods_per_year,
        ),
        score_decisions(
            "CANDIDATE_NO_ABSTENTION",
            decisions,
            [value > 0 for value in scores],
            periods_per_year=periods_per_year,
        ),
        score_decisions(
            "CASH", decisions, [False] * len(decisions), periods_per_year=periods_per_year
        ),
        score_decisions(
            "BUY_AND_HOLD", decisions, [True] * len(decisions), periods_per_year=periods_per_year
        ),
        score_decisions(
            "PREVIOUS_SIGN",
            decisions,
            [row.previous_return > 0 for row in decisions],
            periods_per_year=periods_per_year,
        ),
    ]
