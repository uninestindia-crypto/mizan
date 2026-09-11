"""Leakage-safe splitting and the abstention rule — the two places a short-horizon study goes wrong.

Both modules under test exist because the failure they prevent is silent. A split that leaks does not
raise; it returns a better number. An abstention threshold chosen on the outcome does not raise
either; it returns a much better number. Neither announces itself, so both get their own tests rather
than a few lines inside a runner.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from quant_system.research_short_horizon.abstention import (
    DECLARED_THRESHOLD_GRID,
    AbstentionPolicy,
    calibrate_threshold,
)
from quant_system.research_short_horizon.walkforward import walk_forward_folds


def _dates(count: int, start: date = date(2024, 1, 1)) -> list[date]:
    """Consecutive stand-in session dates. Calendar gaps are irrelevant to the split arithmetic."""
    return [start + timedelta(days=i) for i in range(count)]


# --- purging and the embargo --------------------------------------------------------------------


def test_no_training_label_window_can_reach_the_validation_period() -> None:
    """The leak this module exists to prevent, checked on every fold and every row.

    A training decision at ``k`` with horizon ``h`` is scored on the open at ``k + h``. If that index
    lands on or after the first validation decision, the model was fitted on an outcome it is about
    to be tested on.
    """
    dates = _dates(200)
    position = {value: index for index, value in enumerate(dates)}
    horizon = 4

    folds = walk_forward_folds(
        dates,
        horizon_sessions=horizon,
        embargo_sessions=horizon,
        validation_size=20,
        minimum_train=60,
    )
    assert folds, "the configuration must produce folds"
    for fold in folds:
        first_validation = position[fold.validation[0]]
        for training_date in fold.train:
            assert position[training_date] + horizon < first_validation, (
                f"fold {fold.index}: training decision {training_date} matures at index "
                f"{position[training_date] + horizon}, at or past validation start "
                f"{first_validation}"
            )


def test_the_embargo_removes_further_rows_beyond_the_purge() -> None:
    """Purging handles mechanical overlap; the embargo handles serial correlation."""
    dates = _dates(200)
    horizon = 4

    without = walk_forward_folds(
        dates, horizon_sessions=horizon, embargo_sessions=0, validation_size=20, minimum_train=60
    )
    with_embargo = walk_forward_folds(
        dates, horizon_sessions=horizon, embargo_sessions=10, validation_size=20, minimum_train=60
    )
    for lax, strict in zip(without, with_embargo, strict=True):
        assert strict.train_size == lax.train_size - 10
        assert len(strict.embargoed) == 10
        assert set(strict.train).isdisjoint(strict.embargoed)


def test_purged_and_embargoed_rows_are_reported_not_silently_dropped() -> None:
    """A fold that lost most of its training data must be able to say so."""
    dates = _dates(120)
    folds = walk_forward_folds(
        dates, horizon_sessions=3, embargo_sessions=3, validation_size=20, minimum_train=40
    )
    for fold in folds:
        reconstructed = set(fold.train) | set(fold.embargoed) | set(fold.purged)
        assert reconstructed == set(dates[: dates.index(fold.validation[0])]), (
            "train + embargoed + purged must account for every date before the validation start"
        )
        assert len(fold.purged) == 3


def test_validation_windows_are_chronological_and_do_not_overlap() -> None:
    dates = _dates(200)
    folds = walk_forward_folds(
        dates, horizon_sessions=2, embargo_sessions=2, validation_size=25, minimum_train=50
    )
    seen: set[date] = set()
    previous_end: date | None = None
    for fold in folds:
        assert set(fold.validation).isdisjoint(seen)
        seen.update(fold.validation)
        if previous_end is not None:
            assert fold.validation[0] > previous_end
        previous_end = fold.validation[-1]
        assert max(fold.train) < fold.validation[0]


def test_training_windows_expand() -> None:
    """Each fold trains on everything available before its own purge boundary."""
    dates = _dates(300)
    folds = walk_forward_folds(
        dates, horizon_sessions=2, embargo_sessions=2, validation_size=30, minimum_train=60
    )
    sizes = [fold.train_size for fold in folds]
    assert sizes == sorted(sizes), "an expanding window never shrinks"
    assert len(set(sizes)) > 1, "the fixture must actually exercise expansion"


def test_a_configuration_that_cannot_produce_a_fold_raises() -> None:
    """Returning no folds would read downstream as 'the model had no signal'."""
    with pytest.raises(ValueError, match="no valid fold"):
        walk_forward_folds(
            _dates(40),
            horizon_sessions=4,
            embargo_sessions=40,
            validation_size=10,
            minimum_train=20,
        )


def test_duplicate_decision_dates_are_refused() -> None:
    """One date must land wholly on one side of a split, or its cross-section leaks into itself."""
    dates = _dates(50)
    with pytest.raises(ValueError, match="unique and already de-duplicated"):
        walk_forward_folds(
            [*dates, dates[10]],
            horizon_sessions=2,
            embargo_sessions=2,
            validation_size=10,
            minimum_train=20,
        )


# --- abstention ----------------------------------------------------------------------------------


def test_abstention_scores_per_decision_not_per_trade() -> None:
    """The property that stops a lucky three-trade rule from winning the calibration.

    Three groups of decisions, 200 in total:

    ======================  =====  ===============  =========================
    Prediction magnitude    Count  Realised net     Acting on them is
    ======================  =====  ===============  =========================
    0.05                    3      +0.10 each       excellent, but rare
    0.002                   100    +0.01 each       good, and plentiful
    0.0005                  97     -0.01 each       loss-making
    ======================  =====  ===============  =========================

    Per **trade**, the selective rule looks best: threshold 0.020 acts three times at +0.10 each.
    Per **decision** it is worth 0.30/200 = 0.0015, while any threshold in (0.0005, 0.002] takes the
    first two groups and skips the losers for 1.30/200 = 0.0065 -- and threshold 0 drags in the 97
    losers for 0.33/200 = 0.00165. The broad-but-not-indiscriminate rule wins, which is the whole
    point of dividing by every decision faced.

    0.001 and 0.002 are exactly equivalent on this data, so the assertion below names the property
    rather than a grid point. Pinning one would be testing the tie-break, which has its own test.
    """
    predictions = [Decimal("0.05")] * 3 + [Decimal("0.002")] * 100 + [Decimal("0.0005")] * 97
    realised = [Decimal("0.10")] * 3 + [Decimal("0.01")] * 100 + [Decimal("-0.01")] * 97

    outcome = calibrate_threshold(
        predictions, realised, partition_label="train+validation", minimum_trades=3
    )
    by_threshold = {threshold: mean for threshold, mean, _ in outcome.scores}
    assert by_threshold[Decimal("0.020")] == Decimal("0.30") / Decimal(200)
    assert by_threshold[Decimal("0.002")] == Decimal("1.30") / Decimal(200)
    assert by_threshold[Decimal("0")] == Decimal("0.33") / Decimal(200)
    chosen = outcome.policy.threshold
    assert Decimal("0.0005") < chosen <= Decimal("0.002"), (
        f"the winner must skip the losers without skipping the plentiful winners; got {chosen}"
    )
    assert by_threshold[chosen] > by_threshold[Decimal("0")], "it must beat acting on everything"
    assert by_threshold[chosen] > by_threshold[Decimal("0.020")], (
        "and it must beat the lucky three-trade rule, which per-trade scoring would have preferred"
    )


def test_an_exact_tie_prefers_the_less_selective_threshold() -> None:
    """The tie-break, stated as its own property.

    Two thresholds that score identically differ in how much evidence they rest on: the lower one
    acts on at least as many decisions. Preferring it means a tie never quietly buys extra
    selectivity, which is the direction overfitting travels in.
    """
    predictions = [Decimal("0.05")] * 3 + [Decimal("0.002")] * 100 + [Decimal("0.0005")] * 97
    realised = [Decimal("0.10")] * 3 + [Decimal("0.01")] * 100 + [Decimal("-0.01")] * 97
    outcome = calibrate_threshold(
        predictions, realised, partition_label="train+validation", minimum_trades=3
    )
    by_threshold = {threshold: (mean, trades) for threshold, mean, trades in outcome.scores}
    assert by_threshold[Decimal("0.001")][0] == by_threshold[Decimal("0.002")][0], (
        "the fixture must actually produce a tie"
    )
    assert outcome.policy.threshold == Decimal("0.001"), "the lower of two tied thresholds wins"


def test_a_threshold_that_abstains_almost_always_is_refused() -> None:
    """'Never trade' is the cash baseline. It is a real answer, but it is not a model result."""
    predictions = [Decimal("0.05")] * 2 + [Decimal("0.0001")] * 198
    realised = [Decimal("0.50")] * 2 + [Decimal("-0.01")] * 198

    outcome = calibrate_threshold(
        predictions, realised, partition_label="train+validation", minimum_trades=30
    )
    assert Decimal("0.020") in outcome.refused, "the two-trade threshold must be refused"
    assert outcome.policy.threshold not in outcome.refused


def test_every_threshold_being_too_selective_raises_rather_than_returning_cash() -> None:
    """With fewer decisions than ``minimum_trades``, even threshold 0 cannot clear the bar.

    That is the honest outcome: a study with 20 decisions has not calibrated anything, and returning
    a policy anyway would let a 20-decision sample masquerade as a calibrated model.
    """
    predictions = [Decimal("0.0001")] * 20
    realised = [Decimal("0.01")] * 20
    with pytest.raises(ValueError, match="cash baseline, not a calibrated model"):
        calibrate_threshold(
            predictions, realised, partition_label="train+validation", minimum_trades=30
        )


def test_the_rejected_grid_points_are_kept() -> None:
    """A flat grid and a peaked grid are different claims; a report showing only the winner cannot
    tell them apart."""
    predictions = [Decimal("0.01")] * 100
    realised = [Decimal("0.002")] * 100
    outcome = calibrate_threshold(
        predictions, realised, partition_label="train+validation", minimum_trades=10
    )
    assert len(outcome.scores) == len(DECLARED_THRESHOLD_GRID)
    assert {threshold for threshold, _, _ in outcome.scores} == set(DECLARED_THRESHOLD_GRID)


def test_the_policy_records_which_partitions_calibrated_it() -> None:
    """A holdout-calibrated policy must be visibly wrong rather than indistinguishable."""
    outcome = calibrate_threshold(
        [Decimal("0.01")] * 100,
        [Decimal("0.002")] * 100,
        partition_label="train+validation",
        minimum_trades=10,
    )
    assert outcome.policy.calibrated_on == "train+validation"


def test_exposure_reports_the_fraction_of_decisions_acted_on() -> None:
    policy = AbstentionPolicy(threshold=Decimal("0.005"), calibrated_on="train+validation")
    predictions = [Decimal("0.01"), Decimal("-0.02"), Decimal("0.001"), Decimal("0")]
    assert policy.exposure(predictions) == Decimal("0.5")
    assert policy.exposure([]) == Decimal(0)


def test_abstention_is_symmetric_in_direction() -> None:
    """A short conviction is as tradeable as a long one; the rule reads magnitude only."""
    policy = AbstentionPolicy(threshold=Decimal("0.005"), calibrated_on="train+validation")
    assert policy.acts_on(Decimal("0.006")) is True
    assert policy.acts_on(Decimal("-0.006")) is True
    assert policy.acts_on(Decimal("0.004")) is False
    assert policy.acts_on(Decimal("0.005")) is True, "the boundary is inclusive"


def test_the_declared_grid_brackets_the_round_trip_cost() -> None:
    """0.224% must sit inside the grid, or the calibration cannot find the cost-aware answer."""
    round_trip = Decimal("0.00224")
    assert min(DECLARED_THRESHOLD_GRID) < round_trip < max(DECLARED_THRESHOLD_GRID)
    assert Decimal("0") in DECLARED_THRESHOLD_GRID, "acting on every prediction must be reachable"
