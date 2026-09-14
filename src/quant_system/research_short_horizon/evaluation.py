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
5. **Calibrate abstention on strictly earlier folds**, and apply that threshold forward.
6. **Score against baselines** on identical decisions, with identical costs, on a capital-constrained
   portfolio ledger.

The holdout is not touched by anything in this module. Evaluating it is a separate, explicit call the
caller makes exactly once, after the candidate is frozen.

Two things step 5 and step 6 used to get wrong
----------------------------------------------
Both produced numbers that looked out-of-sample and were not, and neither would have raised anything.

**Step 5 pooled every fold.** One threshold was chosen on all folds' out-of-sample predictions and
then scored on those same rows. Choosing on a sample and measuring on it are one operation there: the
reported figure includes the selection. The pooled grid is still computed and published, because the
search it represents is a real cost that a later reader must be able to price -- but the applied
threshold for each fold now comes only from folds before it, and the first fold, having nothing
before it, holds cash.

**Step 6 compounded overlapping positions.** Decisions are daily and each is held ``held_sessions``
sessions, so consecutive dates overlap; averaging each date's cohort and compounding those averages
in sequence runs the book at ``held_sessions`` times its capital. See :func:`score_decisions`.

Why a ridge, and why no hyperparameter search
---------------------------------------------
The declared candidate is "a simple return-prediction model". A ridge with one fixed penalty is that:
linear, closed-form, no seeds, no early stopping, nothing to tune. Searching the penalty would be
more trials against the frozen budget in ``reports/short_horizon/TRIAL-LEDGER.md``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import numpy as np

from quant_system.research_short_horizon.abstention import (
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
    portfolio_periods: int = 0
    """Non-overlapping portfolio periods the compounded figures were computed over.

    This is the sample length ``total_net_return``, ``sharpe`` and ``max_drawdown`` actually rest on,
    and it is far smaller than the decision-date count: with ``held_sessions`` tranches the book
    turns over once every ``held_sessions`` sessions. Published so a deflated Sharpe cannot be
    computed against the wrong ``n``.
    """

    dropped_dates: int = 0
    """Trailing decision dates outside the last complete period, excluded from compounding.

    A partial block has fewer than ``held_sessions`` tranche settlements in it, so scoring it would
    credit the book with a period it only partly participated in.
    """

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
            "portfolio_periods": self.portfolio_periods,
            "dropped_dates": self.dropped_dates,
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
    applied_policies: list[dict[str, str]] = field(default_factory=list)
    """The threshold actually used on each fold, and what it was calibrated on.

    ``calibration`` above is the pooled grid, kept for disclosure of the search. It is **not** what
    scored the candidate: choosing a threshold on all folds' out-of-sample predictions and then
    reporting that threshold's score on the same rows measures the selection, not the rule. Each
    entry here was fitted on strictly earlier folds; fold 0 held cash.
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
    held_sessions: int = 1,
) -> StrategyScore:
    """Score one strategy over the decisions it was given.

    ``mean_net_return_per_decision`` divides by **every** decision faced, not by the trades taken.
    Dividing by trades rewards abstaining down to a handful of lucky calls; dividing by decisions
    prices the cash periods at the zero they actually earn.

    Compounding is capital-constrained
    ----------------------------------
    Decisions are made every session but each one is held for ``held_sessions``, so consecutive
    decision dates overlap. An earlier version averaged each date's cohort and compounded those
    averages as if they were consecutive, non-overlapping periods. At hold 3 that silently ran the
    book at three times its capital and produced an equity path no funded portfolio could have
    followed -- which is what ``total_net_return`` and ``max_drawdown`` were computed from.

    The fix is the standard staggered-tranche ledger. Capital is split into ``held_sessions`` equal
    tranches; tranche ``i % held_sessions`` enters on date ``i`` and settles ``held_sessions``
    sessions later, so exactly one tranche settles per session and total exposure never exceeds one.
    A block of ``held_sessions`` consecutive dates is then one **non-overlapping** portfolio period in
    which every tranche settles exactly once, and the block's return is the equal-weighted mean of its
    dates' cohort returns. Those blocks may legitimately be compounded, and ``periods_per_year =
    252 / held_sessions`` is then the matching annualisation rather than an assumption.

    A trailing partial block is dropped rather than scored: fewer than ``held_sessions`` settlements
    means the book only partly participated in it. The count is reported as ``dropped_dates``.
    """
    if held_sessions < 1:
        raise ValueError(f"{strategy_id}: held_sessions must be >= 1, got {held_sessions}")
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
    daily = [
        float(sum(values, start=Decimal(0)) / Decimal(len(values)))
        for _, values in sorted(by_date.items())
    ]

    # One block = held_sessions consecutive dates = one full turn of the staggered book. Every
    # tranche settles exactly once inside it, so blocks do not overlap and may be compounded.
    complete = (len(daily) // held_sessions) * held_sessions
    dropped = len(daily) - complete
    periods = [
        sum(daily[start : start + held_sessions]) / held_sessions
        for start in range(0, complete, held_sessions)
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
        portfolio_periods=int(series.size),
        dropped_dates=dropped,
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
    fold_spans: list[tuple[int, int]] = []
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

        fold_spans.append((len(out_of_sample), len(out_of_sample) + len(validation)))
        out_of_sample.extend(validation)
        scores.extend(float(value) for value in fold_scores)

    if not out_of_sample:
        raise ValueError("no out-of-sample decision survived the fold construction")

    decimal_scores = [Decimal(str(value)) for value in scores]
    realised = [row.net_return for row in out_of_sample]

    # Disclosure only. Pooling every fold's out-of-sample prediction and choosing the best threshold
    # on it, then reporting that threshold's score on the same rows, is selection and measurement on
    # one sample: a development result, not an out-of-sample one. It is still computed and published
    # because the grid it explored is part of what the search cost -- but it does not drive a single
    # decision below.
    calibration = calibrate_threshold(
        decimal_scores,
        realised,
        partition_label=(
            "walk-forward validation folds, POOLED - disclosure only, not applied "
            "(holdout untouched)"
        ),
        minimum_trades=minimum_trades,
        long_only=True,
    )

    # What is actually applied: for each fold, a threshold calibrated on strictly earlier folds. The
    # first fold has nothing before it, so it sits in cash rather than borrowing a threshold that
    # could only have come from its own outcome.
    applied_take: list[bool] = []
    applied_policies: list[dict[str, str]] = []
    for index, (start, end) in enumerate(fold_spans):
        if start == 0:
            applied_take.extend([False] * (end - start))
            applied_policies.append(
                {"fold": str(index), "threshold": "", "basis": "no earlier fold; held cash"}
            )
            continue
        try:
            past = calibrate_threshold(
                decimal_scores[:start],
                realised[:start],
                partition_label=f"folds < {index} only",
                minimum_trades=minimum_trades,
                long_only=True,
            )
        except ValueError as exc:
            applied_take.extend([False] * (end - start))
            applied_policies.append(
                {"fold": str(index), "threshold": "", "basis": f"uncalibratable: {exc}"}
            )
            continue
        applied_policies.append(
            {
                "fold": str(index),
                "threshold": str(past.policy.threshold),
                "basis": past.policy.calibrated_on,
            }
        )
        applied_take.extend(past.policy.acts_on(value) for value in decimal_scores[start:end])

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
        applied_policies=applied_policies,
    )
    result.scores = _all_scores(
        out_of_sample,
        scores,
        applied_take,
        periods_per_year=periods_per_year,
        held_sessions=held_sessions,
    )
    return result


def _all_scores(
    decisions: Sequence[Decision],
    scores: Sequence[float],
    candidate_take: Sequence[bool],
    *,
    periods_per_year: float,
    held_sessions: int,
) -> list[StrategyScore]:
    """The candidate and every baseline, over the identical decision set.

    Identical decisions, deliberately. A baseline computed over a different set of dates or names is
    not a comparison, and the difference between two such numbers is uninterpretable.
    """
    return [
        score_decisions(
            "CANDIDATE",
            decisions,
            candidate_take,
            periods_per_year=periods_per_year,
            held_sessions=held_sessions,
        ),
        score_decisions(
            "CANDIDATE_NO_ABSTENTION",
            decisions,
            [value > 0 for value in scores],
            periods_per_year=periods_per_year,
            held_sessions=held_sessions,
        ),
        score_decisions(
            "CASH",
            decisions,
            [False] * len(decisions),
            periods_per_year=periods_per_year,
            held_sessions=held_sessions,
        ),
        # Renamed from BUY_AND_HOLD, which it never was. It re-enters every name on every decision
        # date and pays the round trip each time; a buy-once passive portfolio pays it twice in
        # total. Calling this "buy and hold" made the candidate's cost discipline look like an
        # achievement against a straw man, and made its sign flips across horizons look like
        # statements about market regimes.
        #
        # A true buy-once baseline is not constructible from `Decision`: the contract carries one
        # cost-charged holding-period return per row and no price level, so there is nothing to
        # compound a held position from. That is a stated gap, not one to fill with an estimate.
        score_decisions(
            "ALWAYS_TRADE",
            decisions,
            [True] * len(decisions),
            periods_per_year=periods_per_year,
            held_sessions=held_sessions,
        ),
        score_decisions(
            "PREVIOUS_SIGN",
            decisions,
            [row.previous_return > 0 for row in decisions],
            periods_per_year=periods_per_year,
            held_sessions=held_sessions,
        ),
    ]
