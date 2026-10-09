"""Per-date signal evaluation copied from Microsoft Qlib (MIT), and the bridge's information ratio that now uses it.

Qlib judges a signal one date at a time (how well did today's ranking line up with what happened next?) and then asks how
steady that is across dates. The bridge used to pool every date together and divide the pooled correlation by 0.1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr  # type: ignore[import-untyped]

from quant_system.research.qlib.adapter import QlibModelAdapter, QlibRankDataset
from quant_system.research.qlib.alpha_eval import (
    calc_ic,
    calc_long_short_prec,
    calc_long_short_return,
    ic_summary,
    pred_autocorr,
)


def panel(
    dates: int = 6, names: int = 20, seed: int = 0, strength: float = 0.6
) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    index = pd.MultiIndex.from_product(
        [pd.date_range("2026-01-05", periods=dates, freq="B"), [f"S{i:02d}" for i in range(names)]],
        names=["datetime", "instrument"],
    )
    pred = pd.Series(rng.normal(size=len(index)), index=index)
    label = strength * pred * 0.01 + pd.Series(rng.normal(0, 0.01, len(index)), index=index)
    return pred, label


# ------------------------------------------------------------------------------------------ calc_ic


def test_the_ic_of_each_date_is_that_dates_own_correlation() -> None:
    pred, label = panel()
    ic, rank_ic = calc_ic(pred, label)
    assert len(ic) == 6
    first = pred.index.get_level_values("datetime")[0]
    p, y = pred.xs(first, level="datetime").to_numpy(), label.xs(first, level="datetime").to_numpy()
    assert ic.loc[first] == pytest.approx(np.corrcoef(p, y)[0, 1])
    assert rank_ic.loc[first] == pytest.approx(spearmanr(p, y).correlation)


def test_a_signal_with_real_information_has_a_positive_ic_on_most_dates() -> None:
    ic, _ = calc_ic(*panel(dates=30, names=40, strength=1.0))
    assert ic.mean() > 0.3 and (ic > 0).mean() > 0.9


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_a_date_with_one_name_gives_nan_and_dropna_removes_it() -> None:
    pred, label = panel(dates=4, names=10)
    thin = pred.index[pred.index.get_level_values(0) == pred.index.get_level_values(0)[0]][1:]
    pred, label = pred.drop(thin), label.drop(thin)
    ic, _ = calc_ic(pred, label)
    assert ic.isna().sum() == 1
    assert len(calc_ic(pred, label, dropna=True)[0]) == 3


# ------------------------------------------------------------------------------------------ long and short


def test_when_the_label_is_the_signal_the_long_short_return_is_the_spread_of_the_extremes() -> None:
    pred, _ = panel(dates=3, names=10)
    spread, average = calc_long_short_return(pred, pred, quantile=0.2)
    day = pred.index.get_level_values(0)[0]
    values = np.sort(pred.xs(day, level="datetime").to_numpy())
    assert spread.loc[day] == pytest.approx((values[-2:].mean() - values[:2].mean()) / 2)
    assert average.loc[day] == pytest.approx(values.mean())


def test_long_and_short_precision_count_how_often_the_top_rose_and_the_bottom_fell() -> None:
    pred, _ = panel(dates=3, names=10)
    long_prec, short_prec = calc_long_short_prec(pred, pred, quantile=0.2)
    assert (long_prec >= 0).all() and (long_prec <= 1).all() and (short_prec <= 1).all()
    # with the label equal to the signal, the top two of ten are the largest values, so they are positive often
    assert len(long_prec) == len(short_prec) == 3


def test_too_few_names_for_the_quantile_is_refused_in_words() -> None:
    pred, label = panel(dates=2, names=4)
    with pytest.raises(ValueError, match="more instruments"):
        calc_long_short_prec(pred, label, quantile=0.2)


# ------------------------------------------------------------------------------------------ autocorrelation


def test_a_signal_that_never_changes_has_an_autocorrelation_of_one() -> None:
    pred, _ = panel(dates=5, names=15)
    still = pred.groupby(level="instrument").transform("first")
    ac = pred_autocorr(still)
    assert ac.dropna().round(10).eq(1.0).all() and len(ac.dropna()) == 4


def test_a_signal_redrawn_every_day_has_an_autocorrelation_near_zero() -> None:
    pred, _ = panel(dates=60, names=60, seed=5)
    assert abs(pred_autocorr(pred).dropna().mean()) < 0.1


# ------------------------------------------------------------------------------------------ the summary


def test_the_information_ratio_is_the_mean_over_the_spread_across_dates() -> None:
    series = pd.Series([0.1, 0.3, 0.2, 0.0, 0.4])
    summary = ic_summary(series)
    assert summary.n_dates == 5
    assert summary.mean == pytest.approx(0.2)
    assert summary.std == pytest.approx(series.std(ddof=1))
    assert summary.ir == pytest.approx(0.2 / series.std(ddof=1))
    assert summary.t_stat == pytest.approx(0.2 / (series.std(ddof=1) / np.sqrt(5)))
    assert summary.positive_share == pytest.approx(0.8)


@pytest.mark.parametrize(
    "values", [[], [0.2], [0.2, 0.1], [0.2, 0.2, 0.2], [np.nan, np.nan, np.nan]]
)
def test_with_fewer_than_three_dates_or_no_spread_the_ratio_is_not_measurable(
    values: list[float],
) -> None:
    summary = ic_summary(pd.Series(values, dtype=float))
    assert summary.ir is None and summary.t_stat is None


# ------------------------------------------------------------------------------------------ the bridge


def dataset(dates: int, names: int, seed: int = 1, strength: float = 1.0) -> QlibRankDataset:
    rng = np.random.default_rng(seed)
    rows = dates * names
    X = rng.normal(size=(rows, 4))
    y = strength * X[:, 0] * 0.01 + rng.normal(0, 0.01, rows)
    return QlibRankDataset(
        symbols=[f"S{i % names:02d}" for i in range(rows)],
        dates=[f"2026-02-{1 + i // names:02d}" for i in range(rows)],
        feature_names=["a", "b", "c", "d"],
        X=X,
        y=y,
    )


def test_the_bridge_reports_the_mean_per_date_ic_and_a_real_information_ratio() -> None:
    train, test = dataset(10, 30, seed=1), dataset(12, 30, seed=2)
    model = QlibModelAdapter(ridge_alpha=1.0)
    model.fit(train)
    report = model.evaluate(test)
    preds = model.predict(test.X)
    frame = pd.DataFrame({"d": test.dates, "p": preds, "y": test.y})
    per_date = frame.groupby("d").apply(
        lambda g: np.corrcoef(g["p"], g["y"])[0, 1], include_groups=False
    )
    assert report.n_dates == 12
    assert report.ic_mean == pytest.approx(per_date.mean())
    assert report.ic_ir == pytest.approx(per_date.mean() / per_date.std(ddof=1))
    assert report.ic_ir != pytest.approx(report.ic_mean / 0.1)  # the old made-up figure


def test_with_fewer_than_three_dates_the_bridge_says_the_ratio_cannot_be_measured() -> None:
    model = QlibModelAdapter()
    model.fit(dataset(10, 30))
    report = model.evaluate(dataset(2, 30, seed=3))
    assert report.ic_ir is None and report.rank_ic_ir is None and report.n_dates == 2
    assert report.to_dict()["ic_ir"] is None


def test_when_no_date_has_enough_names_the_bridge_falls_back_to_the_pooled_figure_without_a_ratio() -> (
    None
):
    thin = dataset(dates=40, names=1)  # one name per date: no cross-section to rank
    model = QlibModelAdapter()
    model.fit(dataset(10, 30))
    report = model.evaluate(thin)
    assert report.n_dates == 0 and report.ic_ir is None and report.sample_size == 40
