"""Compounded figures must describe a portfolio someone could actually have funded.

Two defects, both of which produced numbers that looked out-of-sample and were not:

1. **Overlapping positions were compounded as if sequential.** Decisions are made every session and
   held ``held_sessions`` sessions, so consecutive decision dates overlap. Averaging each date's
   cohort and compounding those averages in order runs the book at ``held_sessions`` times its
   capital -- at hold 3, an equity path no funded portfolio could have followed. That path was what
   ``total_net_return`` and ``max_drawdown`` were computed from, and what the deflated Sharpe's
   sample length was taken against.

2. **The abstention threshold was chosen and scored on the same rows.** One threshold was calibrated
   on every fold's pooled out-of-sample predictions, then the candidate was scored with it on those
   same predictions. Selection and measurement on one sample is a development result.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from quant_system.research_short_horizon.evaluation import (
    Decision,
    evaluate_walk_forward,
    score_decisions,
)

START = date(2024, 1, 1)


def _row(day: int, symbol: str, net: str, previous: float = 0.0) -> Decision:
    return Decision(
        on=START + timedelta(days=day),
        symbol=symbol,
        features=(float(day), previous),
        net_return=Decimal(net),
        previous_return=previous,
    )


# --- the capital constraint ----------------------------------------------------------------------


def test_a_hold_of_one_is_unchanged_by_the_tranche_ledger() -> None:
    """With no overlap there are no tranches, so the repair must be a no-op on hold 1."""
    rows = [_row(day, "A", "0.01") for day in range(6)]
    score = score_decisions("X", rows, [True] * 6, periods_per_year=252.0, held_sessions=1)

    assert score.portfolio_periods == 6
    assert score.dropped_dates == 0
    assert float(score.total_net_return) == pytest.approx(1.01**6 - 1.0)


def test_overlapping_holds_compound_over_blocks_not_over_every_date() -> None:
    """Six daily decisions held three sessions each is two portfolio turns, not six."""
    rows = [_row(day, "A", "0.01") for day in range(6)]
    score = score_decisions("X", rows, [True] * 6, periods_per_year=84.0, held_sessions=3)

    assert score.portfolio_periods == 2, "three staggered tranches turn the book over twice in six"
    assert float(score.total_net_return) == pytest.approx(1.01**2 - 1.0)


def test_the_old_overlapping_compounding_overstated_the_return() -> None:
    """Pins the direction of the error: the defect inflated the headline, it did not deflate it."""
    rows = [_row(day, "A", "0.01") for day in range(9)]
    corrected = score_decisions("X", rows, [True] * 9, periods_per_year=84.0, held_sessions=3)
    overlapping = 1.01**9 - 1.0  # what compounding every decision date produced

    assert float(corrected.total_net_return) == pytest.approx(1.01**3 - 1.0)
    assert overlapping > float(corrected.total_net_return)


def test_a_trailing_partial_block_is_dropped_and_counted() -> None:
    """A block with fewer than held_sessions settlements is one the book only partly participated in."""
    rows = [_row(day, "A", "0.01") for day in range(7)]
    score = score_decisions("X", rows, [True] * 7, periods_per_year=84.0, held_sessions=3)

    assert score.portfolio_periods == 2
    assert score.dropped_dates == 1
    assert score.decisions == 7, (
        "every decision still counts toward exposure and the per-decision mean"
    )


def test_exposure_never_implies_more_than_the_whole_book() -> None:
    """The tranche construction is what makes this true; the old one could not state it."""
    rows = [_row(day, symbol, "0.01") for day in range(6) for symbol in ("A", "B")]
    score = score_decisions("X", rows, [True] * len(rows), periods_per_year=84.0, held_sessions=3)

    assert score.exposure <= 1.0
    assert score.portfolio_periods == 2


def test_held_sessions_must_be_positive() -> None:
    with pytest.raises(ValueError, match="held_sessions"):
        score_decisions(
            "X", [_row(0, "A", "0.01")], [True], periods_per_year=252.0, held_sessions=0
        )


def test_the_per_decision_mean_is_untouched_by_the_ledger_change() -> None:
    """Only the compounded statistics moved. The per-decision mean never had the overlap problem."""
    rows = [_row(day, "A", "0.01") for day in range(9)]
    one = score_decisions("X", rows, [True] * 9, periods_per_year=252.0, held_sessions=1)
    three = score_decisions("X", rows, [True] * 9, periods_per_year=84.0, held_sessions=3)

    assert one.mean_net_return_per_decision == three.mean_net_return_per_decision
    assert one.trades == three.trades == 9


# --- past-only abstention ------------------------------------------------------------------------


def _walk_forward_rows(dates: int = 400) -> list[Decision]:
    """Deterministic rows with a mild, learnable signal, two names per date."""
    rows: list[Decision] = []
    for day in range(dates):
        for index, symbol in enumerate(("A", "B")):
            drift = ((day * 7 + index * 13) % 21 - 10) / 1000.0
            rows.append(_row(day, symbol, f"{drift:.6f}", previous=drift))
    return rows


def _run(rows: list[Decision]):
    return evaluate_walk_forward(
        rows,
        held_sessions=1,
        horizon_sessions=2,
        embargo_sessions=2,
        validation_size=40,
        minimum_train=80,
        penalty=1.0,
        periods_per_year=252.0,
        minimum_trades=5,
    )


def test_the_applied_threshold_comes_from_earlier_folds_only() -> None:
    result = _run(_walk_forward_rows())

    assert result.applied_policies, (
        "the per-fold policies must be published, not just the pooled one"
    )
    for entry in result.applied_policies[1:]:
        assert entry["basis"].startswith("folds < ") or "uncalibratable" in entry["basis"], (
            f"a fold was scored with a threshold from somewhere other than its past: {entry}"
        )


def test_the_first_fold_holds_cash_because_it_has_no_past() -> None:
    """Borrowing a threshold for fold 0 could only have come from fold 0's own outcome."""
    first = _run(_walk_forward_rows()).applied_policies[0]

    assert first["threshold"] == ""
    assert "no earlier fold" in first["basis"]


def test_the_pooled_calibration_is_published_but_labelled_as_not_applied() -> None:
    """The search it represents is a real cost, so it is disclosed rather than deleted."""
    calibration = _run(_walk_forward_rows()).calibration

    assert "disclosure only" in calibration.policy.calibrated_on
    assert "not applied" in calibration.policy.calibrated_on
    assert "holdout untouched" in calibration.policy.calibrated_on
    assert calibration.scores, "every grid point considered is still reported"


def test_the_candidate_trades_strictly_less_than_an_unabstaining_rule() -> None:
    """Fold 0 is forced to cash, so the applied rule cannot act on every decision the model liked.

    Under the old pooled calibration nothing forced that: one threshold covered every fold including
    the first, and it had been chosen with the first fold's own outcome in the pool.
    """
    result = _run(_walk_forward_rows())
    candidate = result.candidate
    unabstaining = next(s for s in result.scores if s.strategy_id == "CANDIDATE_NO_ABSTENTION")

    assert candidate.trades < unabstaining.trades
    assert candidate.decisions == unabstaining.decisions


def test_every_scored_fold_publishes_the_threshold_it_used() -> None:
    """No fold may be scored by a rule that is not written down beside the result."""
    result = _run(_walk_forward_rows())

    assert len(result.applied_policies) >= 1
    assert [entry["fold"] for entry in result.applied_policies] == [
        str(index) for index in range(len(result.applied_policies))
    ]


def test_portfolio_periods_reach_the_score_for_every_strategy() -> None:
    """The deflated Sharpe reads this. A zero here silently restores the wrong sample length."""
    for score in _run(_walk_forward_rows()).scores:
        assert score.portfolio_periods > 0
        assert score.to_dict()["portfolio_periods"] == score.portfolio_periods
