"""Chronological walk-forward splits with purging and an embargo, for overlapping labels.

Why a plain expanding split is wrong here
-----------------------------------------
A label for a decision on session ``k`` matures at the open of session ``k + horizon``. Decisions on
consecutive sessions therefore produce labels whose outcome windows **overlap**. Split a series at
session ``s`` and the last few training rows are scored on prices that fall on the validation side
of the cut: the model is fitted on the answer it is about to be tested on.

The size of the leak is exactly the horizon, and so is the fix.

**Purge.** Drop training rows whose label window reaches into or past the validation start. For a
decision at ``k`` with horizon ``h``, the window ends at ``k + h``, so every training row with
``k + h >= validation_start`` must go.

**Embargo.** Drop training rows immediately *before* the purge boundary as well. Purging alone
handles the mechanical overlap; the embargo handles serial correlation in the features themselves,
which makes a row just before the boundary nearly a copy of one just after it. Prado's convention is
an embargo on the order of the label horizon, which is what :class:`HoldSpec` carries.

Nothing here is clever, and that is deliberate. The split is the part of a backtest most likely to be
quietly wrong and least likely to announce it, so it is a separate module with its own tests rather
than three lines inside a runner.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

__all__ = ["Fold", "walk_forward_folds"]


@dataclass(frozen=True, slots=True)
class Fold:
    """One chronological fold: which decision dates train, which validate, and what was removed.

    ``purged`` and ``embargoed`` are kept rather than discarded silently. A fold that dropped a third
    of its training data to purging is telling you something about the horizon relative to the fold
    size, and a runner that cannot see that will report a thin fold as if it were a full one.
    """

    index: int
    train: tuple[date, ...]
    validation: tuple[date, ...]
    purged: tuple[date, ...]
    embargoed: tuple[date, ...]

    @property
    def train_size(self) -> int:
        return len(self.train)

    @property
    def validation_size(self) -> int:
        return len(self.validation)


def walk_forward_folds(
    decision_dates: Sequence[date],
    *,
    horizon_sessions: int,
    embargo_sessions: int,
    validation_size: int,
    minimum_train: int,
    max_folds: int | None = None,
) -> tuple[Fold, ...]:
    """Expanding-window folds over ``decision_dates``, purged and embargoed.

    ``decision_dates`` must be the ordered, de-duplicated session dates on which a decision could be
    made -- the shared cross-sectional grid, not one row per instrument. Every instrument deciding on
    the same date belongs to the same side of every split, because splitting a date across train and
    validation would leak that date's cross-section into itself.

    Raises on a configuration that cannot produce a single valid fold, rather than returning an empty
    tuple. Silently producing no folds reads downstream as "the model had no signal".
    """
    if horizon_sessions < 1:
        raise ValueError("horizon_sessions must be at least 1")
    if embargo_sessions < 0:
        raise ValueError("embargo_sessions cannot be negative")
    if validation_size < 1:
        raise ValueError("validation_size must be at least 1")
    if minimum_train < 1:
        raise ValueError("minimum_train must be at least 1")

    ordered = tuple(sorted(set(decision_dates)))
    if len(ordered) != len(decision_dates):
        raise ValueError("decision_dates must be unique and already de-duplicated")

    folds: list[Fold] = []
    start = minimum_train
    while start + validation_size <= len(ordered):
        validation = ordered[start : start + validation_size]
        candidate_train = ordered[:start]

        # Purge: a training decision whose label window reaches the validation start is scored on
        # prices inside the validation period.
        purge_from = max(0, start - horizon_sessions)
        purged = candidate_train[purge_from:]
        kept = candidate_train[:purge_from]

        # Embargo: also drop the rows immediately before the purge boundary. Their features overlap
        # the purged window's, so keeping them reintroduces most of the leak purging just removed.
        embargo_from = max(0, len(kept) - embargo_sessions)
        embargoed = kept[embargo_from:]
        train = kept[:embargo_from]

        if train:
            folds.append(
                Fold(
                    index=len(folds),
                    train=train,
                    validation=validation,
                    purged=purged,
                    embargoed=embargoed,
                )
            )
        start += validation_size
        if max_folds is not None and len(folds) >= max_folds:
            break

    if not folds:
        raise ValueError(
            f"no valid fold: {len(ordered)} decision dates with minimum_train={minimum_train}, "
            f"validation_size={validation_size}, horizon={horizon_sessions} and "
            f"embargo={embargo_sessions} leaves no training rows after purging"
        )
    return tuple(folds)
