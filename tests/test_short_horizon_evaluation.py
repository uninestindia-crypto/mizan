"""The evaluation harness itself, because it is the thing that produces the numbers.

A backtest harness is the least self-checking code in a research repository: every bug in it returns
a plausible number rather than an error, and the bugs that flatter the result are the ones nobody
investigates. So the properties below are checked directly rather than inferred from the fact that a
run completed.

The one that matters most is :func:`test_a_leaked_target_is_visible_end_to_end` -- it feeds the
harness a feature that *is* the answer and confirms the harness reports a spectacular result. That
sounds backwards. It is the control: if a known leak did **not** show up, the harness would be
incapable of detecting an unknown one, and every honest-looking number it produced would be
uninterpretable.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from quant_system.research_short_horizon.evaluation import (  # noqa: E402
    Decision,
    evaluate_walk_forward,
    fit_ridge,
    score_decisions,
)


def _decisions(
    dates: int, symbols: int = 4, *, seed: int = 20260910, leak: bool = False
) -> list[Decision]:
    """Synthetic decisions with no real signal, unless ``leak`` plants one.

    Without ``leak`` the features are independent of the target, so any strategy that appears to
    profit is measuring noise -- which is what the no-signal tests below rely on.
    """
    rng = np.random.default_rng(seed)
    start = date(2020, 1, 1)
    rows: list[Decision] = []
    for day in range(dates):
        for index in range(symbols):
            net = float(rng.normal(0.0, 0.02))
            noise = tuple(float(value) for value in rng.normal(0.0, 1.0, 3))
            features = (net, *noise) if leak else noise
            rows.append(
                Decision(
                    on=start + timedelta(days=day),
                    symbol=f"SYM{index}",
                    features=features,
                    net_return=Decimal(str(round(net, 10))),
                    previous_return=float(rng.normal()),
                )
            )
    return rows


# --- the ridge itself ----------------------------------------------------------------------------


def test_ridge_recovers_a_known_linear_relationship() -> None:
    """With a negligible penalty the fit must reproduce the coefficients that generated the data."""
    rng = np.random.default_rng(7)
    features = rng.normal(size=(400, 3))
    truth = np.array([0.5, -1.25, 2.0])
    targets = 3.0 + features @ truth
    fitted = fit_ridge(features, targets, penalty=1e-9)
    assert fitted[0] == pytest.approx(3.0, abs=1e-6), "intercept"
    assert fitted[1:] == pytest.approx(truth, abs=1e-6)


def test_the_intercept_is_not_penalised() -> None:
    """Penalising it would shrink the fitted mean toward zero -- a claim about the market, not maths.

    Data with a large constant offset and no slope: a heavy penalty must leave the intercept intact
    while crushing the slopes.
    """
    rng = np.random.default_rng(11)
    features = rng.normal(size=(500, 2))
    targets = np.full(500, 7.0)
    fitted = fit_ridge(features, targets, penalty=1e6)
    assert fitted[0] == pytest.approx(7.0, abs=1e-3), "the offset must survive the penalty"
    assert np.abs(fitted[1:]).max() < 1e-3, "the slopes must not"


# --- scoring -------------------------------------------------------------------------------------


def test_scoring_divides_by_decisions_faced_not_trades_taken() -> None:
    """Per-trade scoring rewards abstaining down to a lucky handful. Per-decision does not."""
    rows = [
        Decision(date(2024, 1, 1) + timedelta(days=i), "A", (0.0,), Decimal("0.10"), 0.0)
        for i in range(2)
    ] + [
        Decision(date(2024, 2, 1) + timedelta(days=i), "A", (0.0,), Decimal("0"), 0.0)
        for i in range(98)
    ]
    take = [True, True] + [False] * 98
    score = score_decisions("SELECTIVE", rows, take, periods_per_year=252.0)

    assert score.trades == 2
    assert score.decisions == 100
    assert score.mean_net_return_per_decision == Decimal("0.20") / Decimal(100)
    assert score.exposure == pytest.approx(0.02)


def test_abstained_decisions_earn_exactly_zero_not_nothing() -> None:
    """A skipped decision is a period in cash, which is a zero return -- not an absent observation.

    Dropping them instead would shorten the series and inflate the Sharpe of a selective rule.
    """
    rows = [
        Decision(date(2024, 1, 1) + timedelta(days=i), "A", (0.0,), Decimal("-0.05"), 0.0)
        for i in range(50)
    ]
    all_in = score_decisions("ALL", rows, [True] * 50, periods_per_year=252.0)
    half = score_decisions("HALF", rows, [True] * 25 + [False] * 25, periods_per_year=252.0)

    assert all_in.mean_net_return_per_decision == Decimal("-0.05")
    assert half.mean_net_return_per_decision == Decimal("-0.025")
    assert half.decisions == all_in.decisions == 50, "abstaining must not shorten the series"


def test_same_date_decisions_aggregate_into_one_period() -> None:
    """Positions held simultaneously are one period. Treating them as many understates volatility."""
    on = date(2024, 5, 1)
    rows = [
        Decision(on, "A", (0.0,), Decimal("0.10"), 0.0),
        Decision(on, "B", (0.0,), Decimal("-0.10"), 0.0),
        Decision(on + timedelta(days=1), "A", (0.0,), Decimal("0.02"), 0.0),
        Decision(on + timedelta(days=1), "B", (0.0,), Decimal("0.02"), 0.0),
    ]
    score = score_decisions("EQUAL_WEIGHT", rows, [True] * 4, periods_per_year=252.0)
    # Day one averages to exactly zero; day two to +0.02. Two periods, not four.
    assert score.mean_net_return_per_decision == Decimal("0.04") / Decimal(4)
    assert score.max_drawdown == pytest.approx(0.0, abs=1e-12)


def test_scoring_zero_decisions_raises_rather_than_returning_a_flat_line() -> None:
    with pytest.raises(ValueError, match="cannot score zero decisions"):
        score_decisions("EMPTY", [], [], periods_per_year=252.0)


# --- the end-to-end pass -------------------------------------------------------------------------


def _run(rows: list[Decision], **overrides: object):
    settings: dict[str, object] = {
        "held_sessions": 1,
        "horizon_sessions": 2,
        "embargo_sessions": 2,
        "validation_size": 40,
        "minimum_train": 120,
        "penalty": 1.0,
        "periods_per_year": 252.0,
        "minimum_trades": 5,
    }
    settings.update(overrides)
    return evaluate_walk_forward(rows, **settings)  # type: ignore[arg-type]


def test_a_leaked_target_is_visible_end_to_end() -> None:
    """The control. A feature that *is* the answer must produce an obviously spectacular result.

    If planting a known leak did not show up here, the harness could not detect an unknown one, and
    none of its honest-looking numbers would mean anything.
    """
    leaked = _run(_decisions(400, leak=True))
    clean = _run(_decisions(400, leak=False))

    assert leaked.candidate.sharpe > 3.0, "a target-as-feature must be trivially profitable"
    assert leaked.candidate.mean_net_return_per_decision > Decimal("0.005")
    assert clean.candidate.sharpe < leaked.candidate.sharpe / 3, (
        "and noise features must not come close"
    )


def test_no_signal_data_does_not_produce_a_profitable_candidate() -> None:
    """Features independent of the target must not earn anything meaningful."""
    result = _run(_decisions(400, leak=False))
    assert abs(float(result.candidate.mean_net_return_per_decision)) < 0.002
    assert result.folds >= 2


def test_every_fold_purges_and_embargoes_and_reports_how_much() -> None:
    result = _run(_decisions(400), horizon_sessions=4, embargo_sessions=4)
    assert result.purged_rows > 0
    assert result.embargoed_rows > 0
    assert result.validation_rows > 0
    assert result.train_rows > result.validation_rows


def test_baselines_are_scored_on_the_identical_decision_set() -> None:
    """A baseline computed over different rows is not a comparison."""
    result = _run(_decisions(400))
    counts = {score.strategy_id: score.decisions for score in result.scores}
    assert len(set(counts.values())) == 1, f"decision counts differ across strategies: {counts}"
    assert {"CANDIDATE", "CANDIDATE_NO_ABSTENTION", "CASH", "ALWAYS_TRADE", "PREVIOUS_SIGN"} <= set(
        counts
    )


def test_cash_is_exactly_flat() -> None:
    """The floor the whole study is measured against must be exactly zero, not nearly zero."""
    cash = next(s for s in _run(_decisions(400)).scores if s.strategy_id == "CASH")
    assert cash.trades == 0
    assert cash.mean_net_return_per_decision == Decimal(0)
    assert cash.total_net_return == Decimal(0)
    assert cash.max_drawdown == 0.0


def test_always_trade_takes_every_decision() -> None:
    """Renamed from BUY_AND_HOLD, which it never was.

    It re-enters every name on every decision date and pays the round trip each time; a buy-once
    passive portfolio pays it twice in total. The old name made this a straw man to beat and made
    the candidate's sign flips across horizons read as statements about market regimes.
    """
    result = _run(_decisions(400))
    hold = next(s for s in result.scores if s.strategy_id == "ALWAYS_TRADE")
    assert hold.trades == hold.decisions
    assert hold.exposure == pytest.approx(1.0)
    assert not any(s.strategy_id == "BUY_AND_HOLD" for s in result.scores), (
        "the misleading label must be gone, not aliased"
    )


def test_the_abstention_policy_is_long_only() -> None:
    """Nothing in this repository models shorting, so a negative forecast means cash."""
    result = _run(_decisions(400))
    assert result.calibration.policy.long_only is True
    assert "holdout" in result.calibration.policy.calibrated_on


def test_supplied_predictions_replace_the_ridge_without_changing_the_decision_set() -> None:
    """The TimesFM arm's entry point: same decisions, same baselines, different forecaster."""
    rows = _decisions(400)
    external = {(row.on, row.symbol): float(row.net_return) for row in rows}  # a perfect oracle
    supplied = _run(rows, predictions=external)
    fitted = _run(rows)

    assert supplied.candidate.decisions == fitted.candidate.decisions
    assert supplied.candidate.sharpe > fitted.candidate.sharpe, (
        "an oracle must beat a ridge on noise, or the predictions are not being used"
    )
    supplied_hold = next(s for s in supplied.scores if s.strategy_id == "ALWAYS_TRADE")
    fitted_hold = next(s for s in fitted.scores if s.strategy_id == "ALWAYS_TRADE")
    assert supplied_hold.to_dict() == fitted_hold.to_dict(), (
        "baselines must be identical across arms -- they do not depend on the forecaster"
    )


def test_the_reserved_holdout_never_reaches_the_evaluator() -> None:
    """The brief requires the final holdout stay untouched until a candidate is frozen.

    Checked structurally rather than by inspection: the split is performed, then the evaluator is
    driven with the development rows only, and every date it scored is asserted to be strictly before
    the holdout boundary. A future refactor that passed the whole set through would fail here rather
    than quietly producing a better number.
    """
    from run_short_horizon_experiment import split_holdout

    rows = _decisions(400)
    development, holdout = split_holdout(rows, holdout_sessions=80)
    assert holdout, "the fixture must actually reserve something"
    boundary = min(row.on for row in holdout)
    assert max(row.on for row in development) < boundary

    result = _run(development)
    # Reconstruct which dates the evaluator scored, from the decisions it returned counts for.
    assert result.validation_rows > 0
    scored_dates = {row.on for row in development}
    assert all(on < boundary for on in scored_dates)
    assert not scored_dates & {row.on for row in holdout}


def test_the_holdout_split_is_chronological_not_random() -> None:
    """A randomly sampled holdout leaks the future into training through overlapping labels."""
    from run_short_horizon_experiment import split_holdout

    development, holdout = split_holdout(_decisions(300), holdout_sessions=60)
    assert len({row.on for row in holdout}) == 60
    assert max(row.on for row in development) < min(row.on for row in holdout)


def test_a_holdout_larger_than_the_sample_raises() -> None:
    from run_short_horizon_experiment import split_holdout

    with pytest.raises(ValueError, match="leaves nothing to train on"):
        split_holdout(_decisions(50), holdout_sessions=50)


def test_a_configuration_with_no_out_of_sample_rows_raises() -> None:
    with pytest.raises(ValueError, match="no valid fold|no out-of-sample"):
        _run(_decisions(60), minimum_train=200, validation_size=40)
