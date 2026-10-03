"""Performance statistics and the honest verdict.

The verdict answers one question: *is there evidence this beats simply holding NIFTY, after costs
and after allowing for how many ideas the user has tried?* It uses the deflated Sharpe probability
(:class:`~quant_system.analytics.multiplicity.OverfittingDiagnostics`) of the strategy's daily
returns in excess of the benchmark, with every lab run the user has made counted as a trial, and
the platform's own promotion gate (0.95) as the bar.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from quant_system.analytics.errors import MultiplicityError
from quant_system.analytics.multiplicity import OverfittingDiagnostics
from quant_system.lab.simulator import SimResult

EVIDENCE_GATE = 0.95
MIN_SESSIONS = 252
MIN_ROUND_TRIPS = 20
SESSIONS_PER_YEAR = 252

VerdictLevel = Literal["LOST", "TOO_SHORT", "NO_EVIDENCE", "PROMISING", "EDGE"]


@dataclass(frozen=True, slots=True)
class Performance:
    start_equity: float
    final_equity: float
    total_return: float
    cagr: float | None
    volatility: float | None
    sharpe: float | None
    max_drawdown: float
    time_invested: float
    fills: int
    round_trips: int
    win_rate: float | None
    avg_hold_sessions: float | None
    charges: float
    slippage: float

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}


@dataclass(frozen=True, slots=True)
class Verdict:
    level: VerdictLevel
    title: str
    body: str
    probability: float | None
    trials: int
    threshold: float = EVIDENCE_GATE

    def as_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}


def daily_returns(equity: Sequence[Decimal]) -> np.ndarray:
    values = np.array([float(v) for v in equity], dtype=np.float64)
    if values.size < 2:
        return np.zeros(0, dtype=np.float64)
    out: np.ndarray = values[1:] / values[:-1] - 1.0
    return out


def performance(result: SimResult) -> Performance:
    values = np.array([float(v) for v in result.equity], dtype=np.float64)
    returns = daily_returns(result.equity)
    start, final = float(values[0]), float(values[-1])
    n = returns.size
    std = float(np.std(returns, ddof=1)) if n > 1 else 0.0
    cagr = (final / start) ** (SESSIONS_PER_YEAR / n) - 1.0 if n > 0 and final > 0 else None
    peaks = np.maximum.accumulate(values)
    invested = np.array([float(v) for v in result.invested], dtype=np.float64)
    trips = result.round_trips
    wins = sum(1 for trip in trips if trip.pnl > 0)
    return Performance(
        start_equity=start,
        final_equity=final,
        total_return=final / start - 1.0,
        cagr=cagr,
        volatility=std * math.sqrt(SESSIONS_PER_YEAR) if n > 1 else None,
        sharpe=float(np.mean(returns)) / std * math.sqrt(SESSIONS_PER_YEAR) if std > 0 else None,
        max_drawdown=float((values / peaks - 1.0).min()),
        time_invested=float(np.mean(invested > 0)) if invested.size else 0.0,
        fills=len(result.fills),
        round_trips=len(trips),
        win_rate=wins / len(trips) if trips else None,
        avg_hold_sessions=float(np.mean([trip.sessions for trip in trips])) if trips else None,
        charges=float(result.charges),
        slippage=float(result.slippage),
    )


def excess_probability(
    strategy_equity: Sequence[Decimal], benchmark_equity: Sequence[Decimal], trials: int
) -> float | None:
    """Deflated Sharpe probability that the strategy's excess return over the benchmark is real."""
    excess = daily_returns(strategy_equity) - daily_returns(benchmark_equity)
    if excess.size < 3:
        return None
    std = float(np.std(excess))
    if std <= 0.0:
        return None
    centered = excess - float(np.mean(excess))
    skewness = float(np.mean(centered**3)) / std**3
    kurtosis = float(np.mean(centered**4)) / std**4
    information_ratio = (
        float(np.mean(excess)) / float(np.std(excess, ddof=1)) * math.sqrt(SESSIONS_PER_YEAR)
    )
    try:
        return OverfittingDiagnostics.deflated_sharpe_ratio(
            estimated_sharpe=information_ratio,
            num_trials=trials,
            sample_length_bars=int(excess.size),
            skewness=skewness,
            kurtosis=kurtosis,
            periods_per_year=SESSIONS_PER_YEAR,
        )
    except (MultiplicityError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class Comparison:
    """What the strategy is judged against, in words a user reads in the verdict."""

    name: str
    phrase: str


NIFTY = Comparison(name="NIFTY", phrase="simply holding NIFTY")
WHOLE_LIST = Comparison(
    name="owning the whole list", phrase="owning every stock in the list equally"
)


def verdict(
    strategy: Performance,
    comparison: Performance,
    probability: float | None,
    trials: int,
    sessions: int,
    counts_trades: bool,
    against: Comparison = NIFTY,
    cap_reason: str | None = None,
) -> Verdict:
    """Map results to one of five plain-language verdicts. Never says 'profitable'.

    ``cap_reason`` stops the verdict at PROMISING when the test itself is known to flatter the
    strategy (a universe chosen with today's knowledge), however strong the statistics look.
    """
    tries = f"your {trials} test{'s' if trials != 1 else ''}"
    diff = strategy.total_return - comparison.total_return
    if diff <= 0:
        return Verdict(
            "LOST",
            f"Lost to {against.name}",
            (
                f"After all charges this returned {strategy.total_return:.1%} against "
                f"{comparison.total_return:.1%} for {against.phrase} over the same period."
            ),
            probability,
            trials,
        )
    too_short = sessions < MIN_SESSIONS or (
        counts_trades and strategy.round_trips < MIN_ROUND_TRIPS
    )
    if too_short:
        return Verdict(
            "TOO_SHORT",
            "Too little history to judge",
            (
                f"It finished {diff:.1%} ahead of {against.phrase}, but with {sessions} sessions "
                f"and {strategy.round_trips} completed trades there is not enough evidence to "
                "tell skill from luck."
            ),
            probability,
            trials,
        )
    if probability is None or probability < 0.5:
        return Verdict(
            "NO_EVIDENCE",
            f"No real evidence it beats {against.name}",
            (
                f"It finished {diff:.1%} ahead, but the daily difference from {against.phrase} is "
                f"small and noisy enough to be luck once {tries} are taken into account."
            ),
            probability,
            trials,
        )
    if probability < EVIDENCE_GATE or cap_reason is not None:
        body = (
            f"It beat {against.phrase} by {diff:.1%}. Allowing for {tries}, the chance the edge is "
            f"real is {probability:.0%}"
        )
        if probability < EVIDENCE_GATE:
            body += f", below the {EVIDENCE_GATE:.0%} bar QuantOS requires."
        else:
            body += f". {cap_reason}"
        return Verdict("PROMISING", "Promising, not proven", body, probability, trials)
    return Verdict(
        "EDGE",
        "Evidence of an edge — paper trade it next",
        (
            f"It beat {against.phrase} by {diff:.1%}, and allowing for {tries} the chance the edge "
            f"is real is {probability:.0%}. Past results can still fail: run it on paper before "
            "real money."
        ),
        probability,
        trials,
    )
