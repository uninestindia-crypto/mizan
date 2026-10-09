"""Shrinkage covariance estimators copied from Microsoft Qlib (MIT), and what was fixed on the way.

The estimators are checked three ways: against the textbook sample covariance, against independent re-statements of the
published formulas (Ledoit and Wolf 2004; Chen, Wiesel, Eldar and Hero 2010), and by simulation (with a known true
covariance a shrunk estimate must on average land closer to it than the raw sample does, which is what they are for).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant_system.research.qlib.riskmodel import RiskModel, ShrinkCovEstimator


def returns(rows: int, cols: int, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, 0.01, size=(rows, cols))


def true_cov(p: int, rho: float = 0.3, sigma: float = 0.01) -> np.ndarray:
    cov = np.full((p, p), rho * sigma**2)
    np.fill_diagonal(cov, sigma**2)
    return cov


def draws(cov: np.ndarray, rows: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).multivariate_normal(np.zeros(len(cov)), cov, size=rows)


# --------------------------------------------------------------------- the plain estimator


def test_the_plain_estimate_is_the_textbook_sample_covariance() -> None:
    x = returns(80, 6)
    got = RiskModel(scale_return=False).predict(x, is_price=False)
    assert np.allclose(got, np.cov(x.T, ddof=0))


def test_scaling_returns_to_percent_scales_the_covariance_by_ten_thousand() -> None:
    x = returns(80, 4)
    plain = RiskModel(scale_return=False).predict(x, is_price=False)
    scaled = RiskModel(scale_return=True).predict(x, is_price=False)
    assert np.allclose(scaled, plain * 1e4)


def test_prices_are_turned_into_returns_first() -> None:
    prices = 100 * np.cumprod(1 + returns(81, 3), axis=0)
    from_prices = RiskModel(scale_return=False).predict(prices, is_price=True)
    from_returns = RiskModel(scale_return=False).predict(
        prices[1:] / prices[:-1] - 1, is_price=False
    )
    assert np.allclose(from_prices, from_returns)


def test_the_callers_array_is_never_changed_in_place() -> None:
    """Qlib multiplies the caller's returns by 100 in place when it scales them; this copy does not."""
    x = returns(60, 4)
    before = x.copy()
    RiskModel(scale_return=True).predict(x, is_price=False)
    ShrinkCovEstimator(alpha="lw").predict(x, is_price=False)
    assert np.array_equal(x, before)


def test_a_data_frame_comes_back_as_a_data_frame_with_its_names() -> None:
    frame = pd.DataFrame(returns(60, 3), columns=["TCS", "INFY", "HDFCBANK"])
    cov = ShrinkCovEstimator(alpha="lw").predict(frame, is_price=False)
    corr = ShrinkCovEstimator(alpha="lw").predict(frame, return_corr=True, is_price=False)
    assert list(cov.index) == list(cov.columns) == ["TCS", "INFY", "HDFCBANK"]
    assert np.allclose(np.diag(corr.to_numpy()), 1.0)


def test_nan_options_are_validated_with_a_real_error_not_an_assert() -> None:
    with pytest.raises(ValueError, match="nan_option"):
        RiskModel(nan_option="drop")


def test_filling_missing_values_gives_a_finite_covariance() -> None:
    x = returns(60, 4)
    x[5, 1] = np.nan
    cov = RiskModel(nan_option="fill", scale_return=False).predict(x, is_price=False)
    assert np.isfinite(cov).all()


# --------------------------------------------------------------------- the shrinkage estimators


@pytest.mark.parametrize("alpha", ["lw", "oas", 0.0, 0.4, 1.0])
@pytest.mark.parametrize("target", ["const_var", "const_corr", "single_factor"])
def test_every_choice_gives_a_symmetric_positive_definite_covariance(
    alpha: object, target: str
) -> None:
    if alpha == "oas" and target != "const_var":
        pytest.skip("Qlib supports oas only with the constant-variance target")
    cov = ShrinkCovEstimator(alpha=alpha, target=target, scale_return=False).predict(  # type: ignore[arg-type]
        returns(60, 12, seed=3), is_price=False
    )
    assert np.allclose(cov, cov.T)
    assert np.linalg.eigvalsh(cov).min() > 0


def test_alpha_zero_is_the_sample_covariance_and_alpha_one_is_the_target() -> None:
    x = returns(70, 5)
    sample = np.cov(x.T, ddof=0)
    assert np.allclose(
        ShrinkCovEstimator(alpha=0.0, scale_return=False).predict(x, is_price=False), sample
    )
    pure = ShrinkCovEstimator(alpha=1.0, target="const_var", scale_return=False).predict(
        x, is_price=False
    )
    assert np.allclose(pure, np.eye(5) * np.mean(np.diag(sample)))


def test_a_target_the_caller_supplies_is_used_and_not_changed() -> None:
    x = returns(70, 4)
    target = np.eye(4) * 2e-4
    kept = target.copy()
    cov = ShrinkCovEstimator(alpha=1.0, target=target, scale_return=False).predict(
        x, is_price=False
    )
    assert np.allclose(cov, kept) and np.array_equal(target, kept)


def reference_ledoit_wolf_shrinkage(x: np.ndarray) -> float:
    """Ledoit and Wolf (2004), restated independently of the code under test (the form scikit-learn uses)."""
    x = x - x.mean(axis=0)
    t, p = x.shape
    emp_trace = (x**2).sum(axis=0) / t
    mu = emp_trace.sum() / p
    beta_ = ((x**2).T @ (x**2)).sum()
    delta_ = ((x.T @ x) ** 2).sum() / t**2
    beta = (1.0 / (p * t)) * (beta_ / t - delta_)
    delta = (delta_ - 2.0 * mu * emp_trace.sum() + p * mu**2) / p
    beta = min(beta, delta)
    return 0.0 if beta == 0 else float(beta / delta)


@pytest.mark.parametrize("seed", range(6))
def test_the_ledoit_wolf_constant_variance_parameter_matches_the_published_formula(
    seed: int,
) -> None:
    x = draws(true_cov(10), rows=40, seed=seed)
    model = ShrinkCovEstimator(alpha="lw", target="const_var", scale_return=False)
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / len(xc)
    f = model._get_shrink_target(xc, s)
    assert model._get_shrink_param(xc, s, f) == pytest.approx(
        reference_ledoit_wolf_shrinkage(x), rel=1e-9
    )


def reference_oas_without_the_small_terms(x: np.ndarray) -> float:
    """The form scikit-learn uses, which drops the 2/p terms of Chen et al. (2010) equation 23."""
    x = x - x.mean(axis=0)
    t, p = x.shape
    s = x.T @ x / t
    mu = np.trace(s) / p
    a = np.mean(s**2)
    num, den = a + mu**2, (t + 1.0) * (a - mu**2 / p)
    return 1.0 if den == 0 else float(min(num / den, 1.0))


def paper_oas(x: np.ndarray) -> float:
    """Chen, Wiesel, Eldar and Hero (2010) equation 23, written out in full."""
    x = x - x.mean(axis=0)
    t, p = x.shape
    s = x.T @ x / t
    tr_s2, tr2_s = float((s**2).sum()), float(np.trace(s) ** 2)
    num = (1 - 2 / p) * tr_s2 + tr2_s
    den = (t + 1 - 2 / p) * (tr_s2 - tr2_s / p)
    return min(num / den, 1.0)


@pytest.mark.parametrize("seed", range(6))
def test_the_oas_parameter_is_the_published_formula_and_agrees_with_the_common_simplification(
    seed: int,
) -> None:
    """Qlib multiplies both terms of the numerator by (1 - 2/p) and adds where the paper subtracts. Fixed here."""
    x = draws(true_cov(60), rows=300, seed=seed)  # a large p, where the dropped 2/p terms are small
    model = ShrinkCovEstimator(alpha="oas", scale_return=False)
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / len(xc)
    got = model._get_shrink_param(xc, s, model._get_shrink_target(xc, s))
    assert got == pytest.approx(paper_oas(x), rel=1e-9)
    assert got == pytest.approx(reference_oas_without_the_small_terms(x), abs=0.05)


@pytest.mark.parametrize(
    ("alpha", "target"),
    [("lw", "const_var"), ("lw", "const_corr"), ("lw", "single_factor"), ("oas", "const_var")],
)
def test_a_shrunk_estimate_is_on_average_closer_to_the_truth_than_the_raw_sample(
    alpha: str, target: str
) -> None:
    truth = true_cov(25, rho=0.3)
    sample_error, shrunk_error = [], []
    for seed in range(40):
        x = draws(truth, rows=40, seed=seed)  # nearly as many assets as sessions: the hard case
        sample_error.append(np.linalg.norm(np.cov(x.T, ddof=0) - truth))
        shrunk = ShrinkCovEstimator(alpha=alpha, target=target, scale_return=False).predict(
            x, is_price=False
        )
        shrunk_error.append(np.linalg.norm(shrunk - truth))
    assert np.mean(shrunk_error) < np.mean(sample_error) * 0.9


def test_shrinking_makes_the_estimate_far_better_conditioned_when_assets_nearly_outnumber_sessions() -> (
    None
):
    x = draws(true_cov(30), rows=35, seed=1)
    raw = np.linalg.cond(np.cov(x.T, ddof=0))
    shrunk = np.linalg.cond(
        ShrinkCovEstimator(alpha="lw", scale_return=False).predict(x, is_price=False)
    )
    assert shrunk < raw / 10


# --------------------------------------------------------------------- degenerate input


def test_one_asset_is_just_its_variance() -> None:
    x = returns(60, 1)
    cov = ShrinkCovEstimator(alpha="lw", target="const_corr", scale_return=False).predict(
        x, is_price=False
    )
    assert cov.shape == (1, 1) and cov[0, 0] == pytest.approx(np.var(x))


def test_a_flat_price_series_does_not_produce_nan_or_a_crash() -> None:
    x = returns(60, 4)
    x[:, 2] = 0.0
    for target in ("const_var", "const_corr", "single_factor"):
        cov = ShrinkCovEstimator(alpha="lw", target=target, scale_return=False).predict(
            x, is_price=False
        )
        assert np.isfinite(cov).all(), target


def test_too_few_observations_is_refused_in_words() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        ShrinkCovEstimator(alpha="lw").predict(returns(1, 4), is_price=False)


@pytest.mark.parametrize("bad", [-0.1, 1.5, "ridge"])
def test_a_bad_shrinkage_parameter_is_refused(bad: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        ShrinkCovEstimator(alpha=bad)  # type: ignore[arg-type]


def test_oas_with_a_target_other_than_constant_variance_is_refused_as_in_qlib() -> None:
    with pytest.raises(NotImplementedError):
        ShrinkCovEstimator(alpha="oas", target="const_corr")


def test_the_shrinkage_actually_used_is_reported() -> None:
    x = draws(true_cov(20), rows=40, seed=2)
    model = ShrinkCovEstimator(alpha="lw", target="const_corr", scale_return=False)
    assert model.shrinkage_ is None
    model.predict(x, is_price=False)
    assert model.shrinkage_ is not None and 0.0 <= model.shrinkage_ <= 1.0
    fixed = ShrinkCovEstimator(alpha=0.25, scale_return=False)
    fixed.predict(x, is_price=False)
    assert fixed.shrinkage_ == 0.25
