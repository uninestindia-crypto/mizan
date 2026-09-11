"""The cash/no-trade rule, and why it is part of the candidate rather than a filter on the results.

The arithmetic that makes this necessary
----------------------------------------
The round-trip cost this repository models is about **0.224%**. Amortised over a holding period:

======================  ==========================
Sessions held           Cost per held session
======================  ==========================
21 (XS-Monthly)         ~1.1 basis points
10 (Flagship)           ~2.2 basis points
**1**                   **~22.4 basis points**
======================  ==========================

A one-session strategy pays twenty times the per-session friction of the monthly book. It cannot
afford to hold an opinion on every name on every day; it has to be able to say *nothing here is worth
0.224%* and sit in cash.

So abstention is not a post-hoc filter applied to disappointing results -- that would be selecting a
threshold on the outcome, which is exactly the multiplicity abuse the trial ledger exists to prevent.
It is a declared component of the candidate, with a threshold calibrated on training and validation
partitions only, and it is applied identically across every horizon in the study.

What the threshold is
---------------------
A prediction is acted on only when its magnitude clears ``threshold``. The threshold is chosen from a
declared grid, on training/validation data alone, by the criterion declared in the trial ledger --
never by looking at the holdout, and never re-chosen per horizon.

An important negative property: a threshold high enough to abstain on everything scores exactly zero,
and zero is better than most costed short-horizon strategies. :func:`calibrate_threshold` therefore
refuses a threshold that leaves fewer than ``minimum_trades`` acted-on decisions, because "never
trade" is a real answer but it is the *cash baseline*, not a model result, and it must be reported as
such rather than dressed up as one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Final

__all__ = [
    "DECLARED_THRESHOLD_GRID",
    "AbstentionPolicy",
    "CalibrationOutcome",
    "calibrate_threshold",
]

DECLARED_THRESHOLD_GRID: Final[tuple[Decimal, ...]] = (
    Decimal("0"),
    Decimal("0.001"),
    Decimal("0.002"),
    Decimal("0.003"),
    Decimal("0.005"),
    Decimal("0.008"),
    Decimal("0.012"),
    Decimal("0.020"),
)
"""The one grid, declared once for all six trials in ``reports/short_horizon/TRIAL-LEDGER.md``.

It spans from "act on every prediction" (0) to "act only on predictions of 2% or more", which
brackets the 0.224% round trip by an order of magnitude either side. Eight points, chosen for
coverage rather than tuned: a finer grid would be a larger search for no more information.
"""


@dataclass(frozen=True, slots=True)
class AbstentionPolicy:
    """A calibrated cash rule. Immutable, and it travels with the model it was calibrated for."""

    threshold: Decimal
    calibrated_on: str
    """Which partitions produced it -- recorded so a holdout-calibrated policy is visibly wrong."""

    long_only: bool = False
    """Whether a negative prediction means *cash* rather than *short*.

    True for every strategy in this repository. Nothing here models shorting -- ``validation.py``
    records a return only where the predicted target is ``UP``, and the execution surfaces have no
    short path. A symmetric rule would credit a -3% forecast with the *long* return, which is not a
    trade anyone could place here and would flatter the result exactly where the model is most
    confidently wrong.
    """

    def acts_on(self, prediction: Decimal) -> bool:
        """Whether a prediction is strong enough to be worth its round trip."""
        if self.long_only:
            return prediction >= self.threshold
        return abs(prediction) >= self.threshold

    def exposure(self, predictions: Sequence[Decimal]) -> Decimal:
        """Fraction of decisions this policy would act on. 0 means fully in cash."""
        if not predictions:
            return Decimal(0)
        acted = sum(1 for value in predictions if self.acts_on(value))
        return Decimal(acted) / Decimal(len(predictions))


@dataclass(frozen=True, slots=True)
class CalibrationOutcome:
    """The chosen threshold and every candidate that was considered, with its score.

    The rejected candidates are kept. A threshold chosen from a grid where every point scored about
    the same is a different claim from one chosen from a grid with a clear peak, and a report that
    shows only the winner cannot tell the two apart.
    """

    policy: AbstentionPolicy
    scores: tuple[tuple[Decimal, Decimal, int], ...]
    """``(threshold, mean net return per decision, trades)`` for every grid point."""

    refused: tuple[Decimal, ...]
    """Grid points rejected for leaving fewer than ``minimum_trades`` acted-on decisions."""


def calibrate_threshold(
    predictions: Sequence[Decimal],
    realised_net_returns: Sequence[Decimal],
    *,
    partition_label: str,
    grid: Sequence[Decimal] = DECLARED_THRESHOLD_GRID,
    minimum_trades: int = 30,
    long_only: bool = False,
) -> CalibrationOutcome:
    """Choose the threshold that maximises mean net return per **decision**, not per trade.

    Per decision, deliberately. Scoring per *trade* rewards abstaining down to a handful of lucky
    decisions: a rule that trades three times and wins all three shows a superb per-trade average and
    is indistinguishable from noise. Dividing by every decision the strategy faced prices the cash
    periods honestly -- an abstained decision contributes exactly zero, which is what sitting in cash
    actually earns.

    ``realised_net_returns[i]`` must be the return the strategy would have earned by acting on
    ``predictions[i]`` in its predicted direction, already net of costs.
    """
    if len(predictions) != len(realised_net_returns):
        raise ValueError("predictions and realised returns must align one to one")
    if not predictions:
        raise ValueError("cannot calibrate an abstention threshold on no decisions")

    total = Decimal(len(predictions))
    scores: list[tuple[Decimal, Decimal, int]] = []
    refused: list[Decimal] = []
    best: tuple[Decimal, Decimal] | None = None

    probe = AbstentionPolicy(
        threshold=Decimal(0), calibrated_on=partition_label, long_only=long_only
    )
    for threshold in grid:
        rule = replace(probe, threshold=threshold)
        acted = [
            realised
            for prediction, realised in zip(predictions, realised_net_returns, strict=True)
            if rule.acts_on(prediction)
        ]
        # Abstained decisions earn exactly zero, so the sum over acted decisions divided by ALL
        # decisions is the mean net return per decision.
        mean = (sum(acted, start=Decimal(0)) / total) if acted else Decimal(0)
        scores.append((threshold, mean, len(acted)))
        if len(acted) < minimum_trades:
            refused.append(threshold)
            continue
        # Strictly greater, so an exact tie keeps the threshold already held -- and because the grid
        # is ascending, that is the *less selective* one. A tie between two thresholds is a tie
        # between two rules resting on different amounts of evidence, and the lower one acts on at
        # least as many decisions. Preferring it means a tie never quietly buys extra selectivity,
        # which is the direction overfitting travels in.
        if best is None or mean > best[1]:
            best = (threshold, mean)

    if best is None:
        raise ValueError(
            f"every threshold in the grid left fewer than {minimum_trades} acted-on decisions out "
            f"of {len(predictions)}. That is the cash baseline, not a calibrated model, and it must "
            f"be reported as such"
        )
    return CalibrationOutcome(
        policy=AbstentionPolicy(
            threshold=best[0], calibrated_on=partition_label, long_only=long_only
        ),
        scores=tuple(scores),
        refused=tuple(refused),
    )
