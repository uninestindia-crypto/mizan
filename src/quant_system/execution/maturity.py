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

    The entry session is resolved by instant, not by calendar date: it is the latest session whose
    ``open_at`` is at or before ``entry_time``. Comparing aware datetimes avoids converting a UTC
    entry time into an exchange-local date, which is where timezone defects live. The runner works
    in UTC and the calendar in IST; for NSE hours those dates coincide, but relying on that
    coincidence would be a latent bug rather than a design.
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
        entry_ordinal = None
        for ordinal, session in enumerate(sessions):
            if session.open_at <= entry_time:
                entry_ordinal = ordinal
            else:
                break
        if entry_ordinal is None:
            raise MaturityPolicyError(
                f"no exchange session had opened at {entry_time.isoformat()}; the calendar does "
                "not cover this entry, so its maturity cannot be resolved"
            )
        exit_ordinal = entry_ordinal + self._holding_sessions
        if exit_ordinal >= len(sessions):
            raise MaturityPolicyError(
                f"the calendar ends before the {self._holding_sessions}-session horizon for an "
                f"entry at {entry_time.isoformat()}; extend the calendar rather than maturing early"
            )
        return sessions[exit_ordinal].open_at
