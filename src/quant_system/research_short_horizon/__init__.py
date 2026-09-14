"""Short-horizon research: 1, 2 and 3 trading sessions held after entry.

Deliberately separate from the two longer-horizon books
-------------------------------------------------------
Flagship holds 10 sessions and XS-Monthly holds 21. Nothing here touches either -- not their models,
their weights, their portfolio state, their logs or their evidence. A short-horizon result must not
be able to move a longer-horizon book, and a longer-horizon change must not silently reinterpret a
short-horizon number. They are different studies with different cost economics: a 0.224% round trip
that is 1.1 basis points per session over 21 sessions is 22 basis points per session over one.

That cost asymmetry is the whole reason this study is hard, and it is why the abstention rule below
is a first-class part of the candidate rather than a post-hoc filter.
"""

from quant_system.research_short_horizon.abstention import (
    DECLARED_THRESHOLD_GRID,
    AbstentionPolicy,
    CalibrationOutcome,
    calibrate_threshold,
)
from quant_system.research_short_horizon.horizon import (
    HOLD_TO_HORIZON_SESSIONS,
    HoldSpec,
    hold_specs,
    horizon_for_hold,
)
from quant_system.research_short_horizon.ledger import (
    SpentTrial,
    declared_spent_trials,
    read_spent_trials,
    require_declared_trials,
)
from quant_system.research_short_horizon.walkforward import Fold, walk_forward_folds

__all__ = [
    "DECLARED_THRESHOLD_GRID",
    "HOLD_TO_HORIZON_SESSIONS",
    "AbstentionPolicy",
    "CalibrationOutcome",
    "Fold",
    "HoldSpec",
    "SpentTrial",
    "calibrate_threshold",
    "declared_spent_trials",
    "hold_specs",
    "horizon_for_hold",
    "read_spent_trials",
    "require_declared_trials",
    "walk_forward_folds",
]
