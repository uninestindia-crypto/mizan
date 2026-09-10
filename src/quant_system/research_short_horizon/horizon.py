"""How "N trading sessions held" maps onto this repository's decision/entry/exit convention.

The convention, read off the code rather than assumed
-----------------------------------------------------
``modeling.labels._build_label`` resolves a decision at calendar ordinal ``k`` to::

    entry_session = calendar.sessions[k + 1]
    exit_session  = calendar.sessions[k + horizon_sessions]

Both legs fill at the session **open**. So ``horizon_sessions`` counts decision -> entry -> exit,
and the number of sessions the position is actually *held* is ``horizon_sessions - 1``:

======================  ===================  =====================================
Sessions held           ``horizon_sessions``  Fills
======================  ===================  =====================================
1                       2                    open(k+1) -> open(k+2)
2                       3                    open(k+1) -> open(k+3)
3                       4                    open(k+1) -> open(k+4)
======================  ===================  =====================================

Why this is a module and not a constant in a script
---------------------------------------------------
The off-by-one is exactly the kind of thing that is obvious once and wrong forever after. The
existing Flagship book already carries a documented instance of it -- a historical label horizon of
11 that the portfolio policy converts to 10 held sessions -- and the loss diagnosis had to state the
conversion explicitly because the two numbers do not match by eye.

``tests/test_short_horizon_mapping.py`` proves this table against the real label builder rather than
restating it, so a change to the convention breaks a test instead of silently reinterpreting every
result in the study.

The requested experiment is holds of 1, 2 and 3. A one-session hold is the shortest thing this
repository's execution contract can express: it cannot fill at the same open it decided on, so
"decide today, hold zero sessions" has no meaning here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "HOLD_TO_HORIZON_SESSIONS",
    "HoldSpec",
    "MINIMUM_HELD_SESSIONS",
    "hold_specs",
    "horizon_for_hold",
]

MINIMUM_HELD_SESSIONS: Final = 1
"""One session is the floor: entry is the next eligible open, so a zero-session hold cannot exist."""

HOLD_TO_HORIZON_SESSIONS: Final[dict[int, int]] = {1: 2, 2: 3, 3: 4}
"""The three holds this study evaluates, and the ``horizon_sessions`` each one requires."""


@dataclass(frozen=True, slots=True)
class HoldSpec:
    """One evaluated holding period, with everything a caller needs to stay consistent.

    ``embargo_sessions`` matters as much as the horizon. Labels for consecutive decisions overlap:
    a decision on day ``k`` and one on day ``k+1`` share exit windows when the hold exceeds one
    session, so a validation fold that begins immediately after a training fold ends is scored on
    outcomes the training rows already saw. The embargo must therefore be at least the horizon.
    """

    held_sessions: int
    horizon_sessions: int
    embargo_sessions: int

    @property
    def label(self) -> str:
        return f"hold{self.held_sessions}"

    @property
    def entry_offset(self) -> int:
        """Calendar ordinals from decision to the entry open."""
        return 1

    @property
    def exit_offset(self) -> int:
        """Calendar ordinals from decision to the exit open."""
        return self.horizon_sessions


def horizon_for_hold(held_sessions: int) -> int:
    """``horizon_sessions`` for a given number of held sessions.

    Raises rather than clamping. A caller asking for a hold this study did not declare is either
    widening the experiment budget by accident or has an off-by-one, and both should stop.
    """
    if held_sessions < MINIMUM_HELD_SESSIONS:
        raise ValueError(
            f"a position is held for at least {MINIMUM_HELD_SESSIONS} session; "
            f"entry is the next eligible open, so {held_sessions} has no execution meaning"
        )
    horizon = HOLD_TO_HORIZON_SESSIONS.get(held_sessions)
    if horizon is None:
        raise ValueError(
            f"hold of {held_sessions} sessions is outside the declared experiment budget "
            f"{sorted(HOLD_TO_HORIZON_SESSIONS)}; adding one is a new trial, not a free parameter"
        )
    return horizon


def hold_specs() -> tuple[HoldSpec, ...]:
    """The declared holds, in order, each with an embargo matched to its own overlap."""
    return tuple(
        HoldSpec(
            held_sessions=held,
            horizon_sessions=horizon,
            embargo_sessions=horizon,
        )
        for held, horizon in sorted(HOLD_TO_HORIZON_SESSIONS.items())
    )
