"""How much of a Lab result could be luck of the particular days.

A strategy's Sharpe ratio, yearly return and worst fall are single numbers from a single history. This resamples the daily
returns many times (in blocks, so that runs of good and bad days stay together) and reports the middle 90 percent of each
measure. A wide range says the result could easily have come out very differently on other days.

The idea (bootstrap ranges on strategy results) is the one PyBroker's evaluation uses; this is a fresh implementation of the
stationary bootstrap (Politis and Romano 1994). PyBroker's code is not used: it is licensed Apache 2.0 with the Commons
Clause. The resampling is seeded, so the same returns always give the same ranges.

These ranges are about the luck of the days. They do not replace the verdict, which also counts how many ideas were tried.
"""

from __future__ import annotations

from typing import Any

import numpy as np

SESSIONS_PER_YEAR = 252
MIN_SESSIONS = 60
N_RESAMPLES = 2000
BLOCK_SESSIONS = 10
LEVEL = 0.90
SEED = 20261009
_CHUNK = 250  # resamples handled at a time, so a ten-year test does not need gigabytes
NOTE = (
    "How much of this could be luck of the particular days. The range is where the middle 90 out of 100 reshuffles of the "
    "same days landed. It is not a promise about the future, and it does not count the other ideas you may have tried: "
    "the verdict above does."
)


def stationary_indices(n: int, resamples: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Day numbers for ``resamples`` reshuffled histories of ``n`` days, drawn in runs of about ``block`` days.

    Each run starts at a random day and follows the real calendar from there (wrapping round at the end); a new run starts
    after each day with probability ``1 / block``.
    """
    positions = np.arange(n)
    starts = rng.integers(0, n, size=(resamples, n))
    restart = rng.random((resamples, n)) < 1.0 / block
    restart[:, 0] = True
    run_start = np.maximum.accumulate(np.where(restart, positions, 0), axis=1)
    base = np.take_along_axis(starts, run_start, axis=1)
    index: np.ndarray = (base + (positions - run_start)) % n
    return index


def _measures(sample: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sharpe ratio, yearly return and worst fall of each row of reshuffled daily returns."""
    n = sample.shape[1]
    mean, std = sample.mean(axis=1), sample.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sharpe = np.where(std > 1e-12, mean / std * np.sqrt(SESSIONS_PER_YEAR), np.nan)
    growth = np.cumprod(1.0 + sample, axis=1)
    total = growth[:, -1]
    with np.errstate(divide="ignore", invalid="ignore"):
        cagr = np.where(total > 0, total ** (SESSIONS_PER_YEAR / n) - 1.0, -1.0)
    peak = np.maximum.accumulate(
        np.concatenate([np.ones((len(growth), 1)), growth], axis=1), axis=1
    )[:, 1:]
    worst = (growth / peak - 1.0).min(axis=1)
    return sharpe, cagr, worst


def _range(values: np.ndarray, level: float) -> dict[str, float | None]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"low": None, "high": None}
    tail = (1.0 - level) / 2.0 * 100.0
    low, high = np.percentile(finite, [tail, 100.0 - tail])
    return {"low": round(float(low), 4), "high": round(float(high), 4)}


def bootstrap_ranges(
    returns: np.ndarray,
    *,
    resamples: int = N_RESAMPLES,
    block: int = BLOCK_SESSIONS,
    seed: int = SEED,
    level: float = LEVEL,
) -> dict[str, Any] | None:
    """The range of Sharpe ratio, yearly return and worst fall over reshuffles of ``returns`` (simple daily returns).

    ``None`` when there are fewer than ``MIN_SESSIONS`` usable days, because a range from so little says nothing.
    """
    clean = np.asarray(returns, dtype=np.float64)
    clean = clean[np.isfinite(clean)]
    if clean.size < MIN_SESSIONS:
        return None
    rng = np.random.default_rng(seed)
    sharpe: list[np.ndarray] = []
    cagr: list[np.ndarray] = []
    worst: list[np.ndarray] = []
    for start in range(0, resamples, _CHUNK):
        count = min(_CHUNK, resamples - start)
        sample = clean[stationary_indices(clean.size, count, block, rng)]
        s, c, w = _measures(sample)
        sharpe.append(s)
        cagr.append(c)
        worst.append(w)
    return {
        "level": level,
        "resamples": resamples,
        "block": block,
        "sessions": int(clean.size),
        "sharpe": _range(np.concatenate(sharpe), level),
        "cagr": _range(np.concatenate(cagr), level),
        "max_drawdown": _range(np.concatenate(worst), level),
        "note": NOTE,
    }
