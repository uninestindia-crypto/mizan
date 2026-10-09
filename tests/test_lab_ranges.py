"""How much of a Lab result could be luck of the particular days: bootstrap ranges for Sharpe, yearly return and worst fall.

The method (resample the daily returns, in blocks, many times, and read off the middle 90 percent of each measure) is the
idea behind PyBroker's evaluation of strategy results, written fresh here; PyBroker's code is not used. Blocks keep runs of
good and bad days together, which a day-by-day resample would break.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from fastapi.testclient import TestClient

from quant_system.lab.ranges import (
    BLOCK_SESSIONS,
    MIN_SESSIONS,
    N_RESAMPLES,
    NOTE,
    SEED,
    bootstrap_ranges,
    stationary_indices,
)
from tests.test_v2_api import (  # noqa: F401, F811  (shared fixtures)
    client,
    data_folder,
    headers,
    ready,
)


def noise(n: int, seed: int, mean: float = 0.0, sigma: float = 0.01) -> np.ndarray:
    return np.random.default_rng(seed).normal(mean, sigma, n)


# ------------------------------------------------------------------------------ the resampling


def test_the_resampled_days_are_real_days_in_runs() -> None:
    idx = stationary_indices(500, 40, block=10, rng=np.random.default_rng(1))
    assert idx.shape == (40, 500) and idx.min() >= 0 and idx.max() < 500
    steps = np.diff(idx, axis=1)
    inside_a_run = (steps == 1) | (steps == -499)  # the next day, wrapping round the end
    assert abs((~inside_a_run).mean() - 1 / 10) < 0.02  # a run ends about once every `block` days


def test_a_block_of_one_is_the_plain_day_by_day_resample() -> None:
    idx = stationary_indices(300, 20, block=1, rng=np.random.default_rng(2))
    steps = np.diff(idx, axis=1)
    assert ((steps == 1) | (steps == -299)).mean() < 0.02


# ------------------------------------------------------------------------------ the ranges


def test_the_same_returns_always_give_the_same_ranges() -> None:
    r = noise(500, 3, 0.0005)
    assert bootstrap_ranges(r) == bootstrap_ranges(r)
    assert bootstrap_ranges(r) != bootstrap_ranges(r, seed=SEED + 1)


def test_the_shape_of_the_answer() -> None:
    out = bootstrap_ranges(noise(500, 4, 0.0005))
    assert out is not None
    assert set(out) == {
        "level",
        "resamples",
        "block",
        "sessions",
        "sharpe",
        "cagr",
        "max_drawdown",
        "note",
    }
    assert (
        out["level"] == 0.9 and out["resamples"] == N_RESAMPLES and out["block"] == BLOCK_SESSIONS
    )
    assert out["sessions"] == 500 and out["note"] == NOTE
    for key in ("sharpe", "cagr", "max_drawdown"):
        assert set(out[key]) == {"low", "high"} and out[key]["low"] <= out[key]["high"]


def test_pure_noise_has_a_sharpe_range_that_includes_zero_and_a_real_drift_does_not() -> None:
    lucky = bootstrap_ranges(noise(750, 5))
    steady = bootstrap_ranges(noise(750, 6, mean=0.002, sigma=0.005))
    assert lucky is not None and steady is not None
    assert lucky["sharpe"]["low"] < 0 < lucky["sharpe"]["high"]
    assert steady["sharpe"]["low"] > 0


def test_the_worst_fall_is_never_positive_and_is_zero_when_it_only_ever_rose() -> None:
    risen = bootstrap_ranges(np.full(200, 0.001))
    assert risen is not None
    assert risen["max_drawdown"] == {"low": 0.0, "high": 0.0}
    out = bootstrap_ranges(noise(500, 7))
    assert out is not None and out["max_drawdown"]["high"] <= 0.0


def test_a_ninety_percent_range_for_the_sharpe_ratio_covers_the_truth_most_of_the_time() -> None:
    """With data drawn from a known distribution the true yearly Sharpe should fall inside the range most of the time."""
    mean, sigma, true_sharpe = 0.0006, 0.01, 0.0006 / 0.01 * np.sqrt(252)
    inside = 0
    trials = 60
    for seed in range(trials):
        out = bootstrap_ranges(noise(500, 100 + seed, mean, sigma), resamples=400)
        assert out is not None
        inside += out["sharpe"]["low"] <= true_sharpe <= out["sharpe"]["high"]
    assert 0.72 <= inside / trials <= 1.0


def test_clustered_returns_get_a_wider_range_with_blocks_than_a_day_by_day_resample_would_give() -> (
    None
):
    rng = np.random.default_rng(8)
    shocks = rng.normal(0, 0.006, 1500)
    clustered = np.zeros(1500)
    for i in range(1, 1500):
        clustered[i] = 0.7 * clustered[i - 1] + shocks[i]  # runs of good and bad days
    with_blocks = bootstrap_ranges(clustered, block=20)
    day_by_day = bootstrap_ranges(clustered, block=1)
    assert with_blocks is not None and day_by_day is not None
    width = lambda o: o["cagr"]["high"] - o["cagr"]["low"]  # noqa: E731
    assert width(with_blocks) > width(day_by_day) * 1.3


def test_too_few_sessions_gives_no_range() -> None:
    assert bootstrap_ranges(noise(MIN_SESSIONS - 1, 9)) is None


def test_missing_and_infinite_days_are_dropped_not_propagated() -> None:
    r = noise(400, 10, 0.0005)
    r[5], r[9] = np.nan, np.inf
    out = bootstrap_ranges(r)
    assert out is not None and out["sessions"] == 398
    assert all(
        np.isfinite(v) for key in ("sharpe", "cagr", "max_drawdown") for v in out[key].values()
    )


def test_a_flat_series_has_no_sharpe_but_still_has_its_other_ranges() -> None:
    out = bootstrap_ranges(np.zeros(300))
    assert out is not None
    assert out["sharpe"] == {"low": None, "high": None}
    assert out["cagr"] == {"low": 0.0, "high": 0.0}


def test_a_total_loss_day_gives_a_loss_not_a_nan() -> None:
    r = noise(300, 11)
    r[100] = -1.0
    out = bootstrap_ranges(r, resamples=200)
    assert out is not None
    assert out["cagr"]["low"] == -1.0 and np.isfinite(out["max_drawdown"]["low"])


# ------------------------------------------------------------------------------ in a Lab run


def run_buy_and_hold(ready: TestClient, headers: dict[str, str]) -> dict[str, Any]:  # noqa: F811
    response = ready.post(
        "/api/v2/lab/runs", json={"template_id": "buy_hold", "symbols": ["AAA"]}, headers=headers
    )
    assert response.status_code == 200
    return response.json()


def test_a_lab_run_carries_ranges_and_leaves_the_verdict_alone(
    ready: TestClient,  # noqa: F811
    headers: dict[str, str],  # noqa: F811
) -> None:
    result = run_buy_and_hold(ready, headers)
    assert "ranges" in result
    ranges = result["ranges"]
    if ranges is not None:
        assert (
            ranges["sessions"] == result["period"]["sessions"] or ranges["sessions"] >= MIN_SESSIONS
        )
        assert ranges["note"] == NOTE
    assert set(result["verdict"]) >= {
        "level",
        "title",
        "body",
        "probability",
        "trials",
        "threshold",
    }
    assert (
        ready.get(f"/api/v2/lab/runs/{result['id']}").json()["ranges"] == ranges
    )  # saved with the run


def test_the_note_says_what_the_range_does_not_cover() -> None:
    assert "not a promise" in NOTE and "luck" in NOTE
