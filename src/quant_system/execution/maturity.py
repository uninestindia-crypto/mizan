"""When an open shadow entry is allowed to mature.

The shadow runner matured an entry on the **first same-symbol quote after its fill**. A governed
model is validated on a two-session label — decision at a session close, entry at the next open,
exit at the following open — so under that rule a daily-bar model could open and close a position
inside a single session. That is not a noisier measurement of the validated strategy; it is a
different strategy.

:class:`SessionHorizonMaturity` restores the structural property the validated contract implies: a
position opened on one session cannot be closed on that same session.

**What this does not claim.** The validated label enters and exits at session *opens*. The shadow
runner fills on quotes — after the S9-B1 repair, the first quote later than the decision — so entry
and exit instants are intraday. This policy therefore does not make shadow P&L equal backtest P&L,
and nothing here should be read as saying it does. It closes the structural gap, not the pricing
one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from quant_system.modeling.authorities import SessionCalendarV1

__all__ = [
    "ImmediateMaturity",
    "MaturityPolicy",
    "MaturityPolicyError",
    "SessionHorizonMaturity",
]


class MaturityPolicyError(RuntimeError):
    """A maturity instant could not be resolved.

    Raised rather than guessed. Maturing anyway would restore the unvalidated intraday behaviour
    this module exists to remove; never maturing would strand an open position with no signal to
    the operator. Both are worse than a loud failure.
    """


class MaturityPolicy(Protocol):
    """Return the earliest instant at which an entry filled at ``entry_time`` may mature."""

    def matures_at(self, entry_time: datetime) -> datetime: ...


class ImmediateMaturity:
    """Mature on the next same-symbol quote. The runner's behaviour before a horizon existed.

    Kept as an explicit, nameable policy so that "no horizon" is a choice a caller can state,
    rather than something that happens when a field is left unset.
    """

    def matures_at(self, entry_time: datetime) -> datetime:
        return entry_time


class SessionHorizonMaturity:
    """Hold a position across whole exchange sessions before it may mature.

    ``holding_sessions`` counts session boundaries crossed **from the entry**, and defaults to 1.
    That default is derived, not arbitrary: ``LABEL_HORIZON_SESSIONS_V1 = 2`` counts
    decision -> entry -> exit, so the decision is taken at the close of session T, the entry
    executes at the open of T+1, and the exit at the open of T+2. Measured from the entry, that is
    exactly one session boundary. Changing the label horizon without changing this default would
    put execution and validation back out of step, so the relationship is stated here rather than
    left to be rediscovered.

    The entry session is resolved by instant, not by calendar date: it is the first session whose
    ``close_at`` is at or after ``entry_time`` — the session the position is actually held through.
    A pre-open fill therefore belongs to the session about to open, and a post-close fill to the
    next one, rather than to a session that had already ended. Comparing aware datetimes avoids
    converting a UTC entry time into an exchange-local date, which is where timezone defects live.
    """

    def __init__(self, calendar: SessionCalendarV1, holding_sessions: int = 1) -> None:
        if holding_sessions < 1:
            raise MaturityPolicyError("holding_sessions must be at least one session")
        self._calendar = calendar
        self._holding_sessions = holding_sessions

    @property
    def holding_sessions(self) -> int:
        return self._holding_sessions

    def matures_at(self, entry_time: datetime) -> datetime:
        if entry_time.tzinfo is None or entry_time.utcoffset() is None:
            raise MaturityPolicyError("entry_time must be timezone-aware")
        sessions = self._calendar.sessions
        # The entry session is the first session still open at, or opening after, the entry
        # instant — the session the position is actually held through.
        #
        # An earlier version used the last session whose open_at had already passed. That resolved
        # an entry to a session which, for a pre-open or post-close fill, was not open at that
        # instant. The consequence was measured: a 09:05 pre-open entry resolved to the previous
        # day, so the one-session horizon landed on 09:15 the same morning and the position was
        # held for ten minutes and counted as a full session.
        # A pre-open fill belongs to the session about to open, but an entry that predates the
        # calendar entirely is not a pre-open fill — it is a calendar that does not cover the run,
        # and the two must not collapse into one another. Coverage starts at the beginning of the
        # first session's own exchange date, derived from that session's timestamp so no UTC time
        # is converted into an exchange-local date here.
        coverage_start = sessions[0].open_at.replace(hour=0, minute=0, second=0, microsecond=0)
        if entry_time < coverage_start:
            raise MaturityPolicyError(
                f"entry at {entry_time.isoformat()} predates the calendar's first session date "
                f"({sessions[0].exchange_date.isoformat()}); the calendar does not cover this "
                "entry, so its maturity cannot be resolved"
            )
        entry_ordinal = next(
            (ordinal for ordinal, session in enumerate(sessions) if session.close_at >= entry_time),
            None,
        )
        if entry_ordinal is None:
            raise MaturityPolicyError(
                f"the calendar ends before {entry_time.isoformat()}; no session covers this entry, "
                "so its maturity cannot be resolved"
            )
        exit_ordinal = entry_ordinal + self._holding_sessions
        if exit_ordinal >= len(sessions):
            raise MaturityPolicyError(
                f"the calendar ends before the {self._holding_sessions}-session horizon for an "
                f"entry at {entry_time.isoformat()}; extend the calendar rather than maturing early"
            )
        return sessions[exit_ordinal].open_at
