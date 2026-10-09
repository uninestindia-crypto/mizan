"""Per-date signal evaluation, copied from Microsoft Qlib and extended with a real information ratio.

Source: ``qlib/contrib/eva/alpha.py`` of https://github.com/microsoft/qlib (local copy:
``Learn from open source codebase/qlib-main``). Copyright (c) Microsoft Corporation, MIT licence; the licence text is in
``THIRD_PARTY_NOTICES.md`` at the repository root.

A signal is judged one date at a time: on each date, how well did the ranking of the names line up with what happened next
(``calc_ic``), what did the top of the ranking earn against the bottom (``calc_long_short_return``), how often was the
top up and the bottom down (``calc_long_short_prec``), and how much of the ranking is the same as yesterday's
(``pred_autocorr``, a signal that is redrawn every day cannot be traded cheaply). The *information ratio* of a signal is
the mean of the per-date IC divided by its standard deviation across dates (``ic_summary``).

What differs from upstream: the joblib parallel helpers and Qlib's logger are left out; ``ic_summary`` is new (upstream
leaves the ratio to its reporting layer); the inputs are plain pandas Series indexed by (datetime, instrument), exactly as
upstream documents.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

__all__ = [
    "ICSummary",
    "calc_ic",
    "calc_long_short_prec",
    "calc_long_short_return",
    "ic_summary",
    "pred_autocorr",
]

MIN_DATES_FOR_RATIO = 3


def calc_long_short_prec(
    pred: pd.Series,
    label: pd.Series,
    date_col: str = "datetime",
    quantile: float = 0.2,
    dropna: bool = False,
    is_alpha: bool = False,
) -> tuple[pd.Series, pd.Series]:
    """On each date, the share of the top-quantile names that rose and of the bottom-quantile names that fell.

    ``pred`` and ``label`` are indexed by (datetime, instrument). With ``is_alpha`` the label is first made relative to the
    date's average. Returns (long precision, short precision), each indexed by date.
    """
    if is_alpha:
        label = label - label.groupby(level=date_col, group_keys=False).mean()
    if int(1 / quantile) >= len(label.index.get_level_values(1).unique()):
        raise ValueError("Need more instruments to calculate precision")

    df = pd.DataFrame({"pred": pred, "label": label})
    if dropna:
        df = df.dropna()
    group = df.groupby(level=date_col, group_keys=False)

    def count(x: pd.DataFrame) -> int:
        return int(len(x) * quantile)

    long = group.apply(lambda x: x.nlargest(count(x), columns="pred").label)
    short = group.apply(lambda x: x.nsmallest(count(x), columns="pred").label)
    long_by_date = long.groupby(date_col, group_keys=False)
    short_by_date = short.groupby(date_col, group_keys=False)
    long_rose = long_by_date.apply(lambda x: x > 0).groupby(date_col, group_keys=False).sum()
    short_fell = short_by_date.apply(lambda x: x < 0).groupby(date_col, group_keys=False).sum()
    return long_rose / long_by_date.count(), short_fell / short_by_date.count()


def calc_long_short_return(
    pred: pd.Series,
    label: pd.Series,
    date_col: str = "datetime",
    quantile: float = 0.2,
    dropna: bool = False,
) -> tuple[pd.Series, pd.Series]:
    """Per date: half the gap between the top and bottom quantiles' average return, and the average of all names.

    ``label`` must be raw returns. Returns (long-short return, average return), each indexed by date.
    """
    df = pd.DataFrame({"pred": pred, "label": label})
    if dropna:
        df = df.dropna()
    group = df.groupby(level=date_col, group_keys=False)

    def count(x: pd.DataFrame) -> int:
        return int(len(x) * quantile)

    r_long = group.apply(lambda x: x.nlargest(count(x), columns="pred").label.mean())
    r_short = group.apply(lambda x: x.nsmallest(count(x), columns="pred").label.mean())
    return (r_long - r_short) / 2, group.label.mean()


def pred_autocorr(
    pred: pd.Series, lag: int = 1, inst_col: str = "instrument", date_col: str = "datetime"
) -> pd.Series:
    """How much of each date's ranking repeats the ranking ``lag`` dates earlier (correlation across names).

    If the dates are not consecutive the comparison is with the adjacent date, as upstream notes. Needs one value per
    (date, instrument).
    """
    if isinstance(pred, pd.DataFrame):
        pred = pred.iloc[:, 0]
    wide = pred.sort_index().unstack(inst_col)
    previous = wide.shift(lag)
    correlations = {
        index: current.corr(earlier)
        for (index, current), (_, earlier) in zip(wide.iterrows(), previous.iterrows(), strict=True)
    }
    return pd.Series(correlations).sort_index()


def calc_ic(
    pred: pd.Series, label: pd.Series, date_col: str = "datetime", dropna: bool = False
) -> tuple[pd.Series, pd.Series]:
    """The information coefficient on each date: Pearson and Spearman (rank) correlation of signal and outcome."""
    df = pd.DataFrame({"pred": pred, "label": label})
    by_date = df.groupby(date_col, group_keys=False)
    ic = by_date.apply(lambda g: g["pred"].corr(g["label"]))
    rank_ic = by_date.apply(lambda g: g["pred"].corr(g["label"], method="spearman"))
    if dropna:
        return ic.dropna(), rank_ic.dropna()
    return ic, rank_ic


@dataclass(frozen=True, slots=True)
class ICSummary:
    """How good and how steady a signal's per-date IC is. The ratio and t-statistic need at least 3 dates and some spread."""

    n_dates: int
    mean: float
    std: float | None
    ir: float | None
    t_stat: float | None
    positive_share: float | None


def ic_summary(ic: pd.Series) -> ICSummary:
    """Summarise a per-date IC series: its mean, spread, information ratio (mean / std) and t-statistic."""
    values = ic.dropna().to_numpy(dtype=np.float64)
    n = len(values)
    if n == 0:
        return ICSummary(0, float("nan"), None, None, None, None)
    mean = float(values.mean())
    positive = float((values > 0).mean())
    if n < MIN_DATES_FOR_RATIO:
        return ICSummary(n, mean, None, None, None, positive)
    std = float(values.std(ddof=1))
    if std <= 1e-12:
        return ICSummary(n, mean, std, None, None, positive)
    return ICSummary(n, mean, std, mean / std, mean / (std / np.sqrt(n)), positive)
