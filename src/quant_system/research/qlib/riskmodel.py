"""Shrinkage covariance estimators, copied from Microsoft Qlib and corrected.

Source: ``qlib/model/riskmodel/base.py`` and ``qlib/model/riskmodel/shrink.py`` of https://github.com/microsoft/qlib
(local copy: ``Learn from open source codebase/qlib-main``). Copyright (c) Microsoft Corporation, MIT licence; the licence
text is in ``THIRD_PARTY_NOTICES.md`` at the repository root.

Why: a covariance matrix from a year of daily moves of a dozen holdings is noisy, and the noise makes the portfolio look
more diversified (or less) than it is. Shrinking it toward a simple target is the standard cure (Ledoit and Wolf 2004;
Chen, Wiesel, Eldar and Hero 2010). The platform had only the raw sample covariance.

What differs from upstream, each found by testing against the published formulas:

* The caller's array is never changed. Upstream scales returns by 100 *in place*, which silently rewrites the caller's data
  when it is already returns, and also scales a caller-supplied shrinkage target in place.
* The Oracle Approximating Shrinkage parameter follows Chen et al. (2010) equation 23. Upstream multiplies both terms of the
  numerator by ``(1 - 2/p)`` and adds where the paper subtracts in the denominator.
* A flat series (zero variance, for example a suspended share) no longer turns the whole matrix into NaN. Such a column keeps
  a zero covariance with everything and the estimator runs on the rest. One asset is just its variance.
* Bad arguments raise ``ValueError`` or ``TypeError`` instead of ``assert``, which is removed under ``python -O``.
* Qlib's decomposed-factor option (``return_decomposed_components``) and its structured and POET estimators are not copied:
  they need scikit-learn, which the installer does not carry.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

__all__ = ["RiskModel", "ShrinkCovEstimator"]

_TINY = 1e-18


class RiskModel:
    """Estimates the covariance matrix of asset returns. By default, the plain sample covariance.

    Args:
        nan_option: ``ignore`` leaves missing values alone, ``fill`` makes them 0, ``mask`` uses a masked array.
        assume_centered: whether the data already has mean zero.
        scale_return: scale returns to percent (the covariance is then in percent squared), as Qlib does.
    """

    MASK_NAN = "mask"
    FILL_NAN = "fill"
    IGNORE_NAN = "ignore"

    def __init__(
        self,
        nan_option: str = "ignore",
        assume_centered: bool = False,
        scale_return: bool = True,
    ) -> None:
        if nan_option not in (self.MASK_NAN, self.FILL_NAN, self.IGNORE_NAN):
            raise ValueError(
                f"nan_option={nan_option!r} is not supported (use ignore, fill or mask)"
            )
        self.nan_option = nan_option
        self.assume_centered = assume_centered
        self.scale_return = scale_return

    def predict(
        self,
        X: pd.Series | pd.DataFrame | np.ndarray,
        return_corr: bool = False,
        is_price: bool = True,
    ) -> pd.DataFrame | np.ndarray:
        """The covariance (or correlation) of the columns of ``X``, one row per observation.

        Args:
            X: prices or returns, variables as columns. A data frame keeps its column names in the answer.
            return_corr: answer with the correlation matrix instead.
            is_price: ``X`` holds prices (turned into simple returns first, which uses up one row).
        """
        columns = None
        if isinstance(X, pd.Series | pd.DataFrame):
            if isinstance(X.index, pd.MultiIndex):
                frame = X if isinstance(X, pd.DataFrame) else X.to_frame()
                X = frame.iloc[:, 0].unstack(level="instrument")  # as Qlib: the first column
            columns = X.columns if isinstance(X, pd.DataFrame) else None
            values = np.array(X.to_numpy(dtype=np.float64), copy=True)
        else:
            values = np.array(X, dtype=np.float64, copy=True)
        if values.ndim == 1:
            values = values.reshape(-1, 1)
        if values.ndim != 2:
            raise ValueError("X must have one row per observation and one column per asset")
        if is_price:
            values = values[1:] / values[:-1] - 1
        if len(values) < 2:
            raise ValueError("The covariance needs at least 2 observations")
        if self.scale_return:
            values = values * 100
        data = self._preprocess(values)
        cov = np.asarray(self._predict(data))
        if return_corr:
            vola = np.sqrt(np.diag(cov))
            denominator = np.outer(vola, vola)
            cov = np.divide(cov, denominator, out=np.zeros_like(cov), where=denominator > 0)
            np.fill_diagonal(cov, 1.0)
        if columns is None:
            return cov
        return pd.DataFrame(cov, index=columns, columns=columns)

    def _predict(self, X: Any) -> np.ndarray:
        """The sample covariance. Child classes replace this."""
        xtx = np.asarray(X.T.dot(X))
        n: Any = len(X)
        if isinstance(X, np.ma.MaskedArray):
            valid: Any = 1 - X.mask
            n = valid.T.dot(valid)  # each pair has its own number of samples
        return np.asarray(xtx / n)

    def _preprocess(self, X: np.ndarray) -> Any:
        """Handle missing values and centre the data."""
        if self.nan_option == self.FILL_NAN:
            X = np.nan_to_num(X)
        elif self.nan_option == self.MASK_NAN:
            X = np.ma.masked_invalid(X)
        if not self.assume_centered:
            X = X - np.nanmean(X, axis=0)
        return X


class ShrinkCovEstimator(RiskModel):
    """Shrinkage covariance estimator: ``S_hat = (1 - alpha) * S + alpha * F``.

    ``S`` is the sample covariance, ``F`` the shrinking target and ``alpha`` the shrinking parameter.

    ``alpha`` is one of:
        - ``lw``: Ledoit-Wolf's parameter.
        - ``oas``: Oracle Approximating Shrinkage (only with the ``const_var`` target).
        - a float between 0 and 1.

    ``target`` is one of:
        - ``const_var``: every asset has the same variance and no correlation.
        - ``const_corr``: each asset keeps its variance; every pair has the same correlation.
        - ``single_factor``: one common (market) factor drives everything.
        - an array: a target the caller supplies.

    References:
        [1] Ledoit, O., & Wolf, M. (2004). A well-conditioned estimator for large-dimensional covariance matrices.
            Journal of Multivariate Analysis, 88(2), 365-411.
        [2] Ledoit, O., & Wolf, M. (2004). Honey, I shrunk the sample covariance matrix.
            Journal of Portfolio Management, 30(4), 1-22.
        [3] Ledoit, O., & Wolf, M. (2003). Improved estimation of the covariance matrix of stock returns with an
            application to portfolio selection. Journal of Empirical Finance, 10(5), 603-621.
        [4] Chen, Y., Wiesel, A., Eldar, Y. C., & Hero, A. O. (2010). Shrinkage algorithms for MMSE covariance
            estimation. IEEE Transactions on Signal Processing, 58(10), 5016-5029.
    """

    SHR_LW = "lw"
    SHR_OAS = "oas"

    TGT_CONST_VAR = "const_var"
    TGT_CONST_CORR = "const_corr"
    TGT_SINGLE_FACTOR = "single_factor"

    def __init__(
        self,
        alpha: str | float = 0.0,
        target: str | np.ndarray = "const_var",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if isinstance(alpha, str):
            if alpha not in (self.SHR_LW, self.SHR_OAS):
                raise ValueError(f"shrinking method {alpha!r} is not supported (use lw or oas)")
        elif isinstance(alpha, float | np.floating):
            if not 0 <= alpha <= 1:
                raise ValueError("alpha should be between 0 and 1")
        else:
            raise TypeError("alpha must be 'lw', 'oas' or a float")
        if isinstance(target, str):
            if target not in (self.TGT_CONST_VAR, self.TGT_CONST_CORR, self.TGT_SINGLE_FACTOR):
                raise ValueError(f"shrinking target {target!r} is not supported")
        elif not isinstance(target, np.ndarray):
            raise TypeError("target must be a name or an array")
        if alpha == self.SHR_OAS and not (isinstance(target, str) and target == self.TGT_CONST_VAR):
            raise NotImplementedError("currently oas can only support const_var as target")
        self.alpha = alpha
        self.target = target

    def _predict(self, X: Any) -> np.ndarray:
        sample = super()._predict(X)
        if isinstance(X, np.ma.MaskedArray) or isinstance(self.target, np.ndarray):
            return self._shrink(X, sample)
        # a flat series has no variance to shrink: leave it out and give it zero covariance with the rest
        live = np.diag(sample) > _TINY
        if live.all():
            return self._shrink(X, sample)
        out = np.zeros_like(sample)
        if live.sum() >= 2:
            both = np.ix_(live, live)
            out[both] = self._shrink(X[:, live], sample[both])
        else:
            out = sample.copy()
        return out

    def _shrink(self, X: Any, sample: np.ndarray) -> np.ndarray:
        if len(sample) < 2:
            return sample
        sample = sample.copy()
        target = np.array(self._get_shrink_target(X, sample), dtype=np.float64, copy=True)
        alpha = self._get_shrink_param(X, sample, target)
        shrunk = (1 - alpha) * sample + alpha * target if alpha > 0 else sample
        return np.asarray((shrunk + shrunk.T) / 2)

    def _get_shrink_target(self, X: Any, S: np.ndarray) -> np.ndarray:
        if isinstance(self.target, np.ndarray):
            return self.target
        if self.target == self.TGT_CONST_VAR:
            return self._get_shrink_target_const_var(X, S)
        if self.target == self.TGT_CONST_CORR:
            return self._get_shrink_target_const_corr(X, S)
        return self._get_shrink_target_single_factor(X, S)

    def _get_shrink_target_const_var(self, X: Any, S: np.ndarray) -> np.ndarray:
        """Constant variance (the average of the sample variances) and zero correlation."""
        n = len(S)
        F = np.eye(n)
        np.fill_diagonal(F, np.mean(np.diag(S)))
        return F

    def _get_shrink_target_const_corr(self, X: Any, S: np.ndarray) -> np.ndarray:
        """Each asset keeps its sample variance; every pair gets the average pairwise correlation."""
        n = len(S)
        var = np.diag(S)
        sqrt_var = np.sqrt(var)
        covar = np.outer(sqrt_var, sqrt_var)
        r_bar = (np.sum(S / covar) - n) / (n * (n - 1))
        F = np.asarray(r_bar * covar)
        np.fill_diagonal(F, var)
        return F

    def _get_shrink_target_single_factor(self, X: Any, S: np.ndarray) -> np.ndarray:
        """A single common factor: the equal-weighted average of the assets."""
        X_mkt = np.nanmean(X, axis=1)
        var_mkt = float(np.asarray(X_mkt.dot(X_mkt) / len(X)))
        if var_mkt <= _TINY:
            return S.copy()
        cov_mkt = np.asarray(X.T.dot(X_mkt) / len(X))
        F = np.outer(cov_mkt, cov_mkt) / var_mkt
        np.fill_diagonal(F, np.diag(S))
        return F

    def _get_shrink_param(self, X: Any, S: np.ndarray, F: np.ndarray) -> float:
        if self.alpha == self.SHR_OAS:
            return self._get_shrink_param_oas(X, S, F)
        if self.alpha == self.SHR_LW:
            if isinstance(self.target, np.ndarray) or self.target == self.TGT_CONST_VAR:
                return self._get_shrink_param_lw_const_var(X, S, F)
            if self.target == self.TGT_CONST_CORR:
                return self._get_shrink_param_lw_const_corr(X, S, F)
            return self._get_shrink_param_lw_single_factor(X, S, F)
        return float(self.alpha)

    def _get_shrink_param_oas(self, X: Any, S: np.ndarray, F: np.ndarray) -> float:
        """Oracle Approximating Shrinkage (Chen et al. 2010, equation 23).

        ``alpha = ((1 - 2/p) tr(S^2) + tr(S)^2) / ((n + 1 - 2/p) (tr(S^2) - tr(S)^2 / p))``, at most 1, where ``n`` is the
        number of observations and ``p`` the number of assets.
        """
        n, p = X.shape
        tr_s2 = float(np.sum(S**2))
        tr2_s = float(np.trace(S) ** 2)
        denominator = (n + 1 - 2 / p) * (tr_s2 - tr2_s / p)
        if denominator <= 0:
            return 1.0
        return float(min(((1 - 2 / p) * tr_s2 + tr2_s) / denominator, 1.0))

    def _get_shrink_param_lw_const_var(self, X: Any, S: np.ndarray, F: np.ndarray) -> float:
        """Ledoit-Wolf, shrinking toward the constant-variance target."""
        t, _ = X.shape
        y = X**2
        phi = np.sum(y.T.dot(y) / t - S**2)
        gamma = np.linalg.norm(S - F, "fro") ** 2
        if gamma <= _TINY:
            return 0.0  # the sample already is the target: nothing to shrink
        return float(max(0.0, min(1.0, phi / gamma / t)))

    def _get_shrink_param_lw_const_corr(self, X: Any, S: np.ndarray, F: np.ndarray) -> float:
        """Ledoit-Wolf, shrinking toward the constant-correlation target."""
        t, n = X.shape
        var = np.diag(S)
        sqrt_var = np.sqrt(var)
        r_bar = (np.sum(S / np.outer(sqrt_var, sqrt_var)) - n) / (n * (n - 1))

        y = X**2
        phi_mat = y.T.dot(y) / t - S**2
        phi = np.sum(phi_mat)

        theta_mat = (X**3).T.dot(X) / t - var[:, None] * S
        np.fill_diagonal(theta_mat, 0)
        rho = np.sum(np.diag(phi_mat)) + r_bar * np.sum(
            np.outer(1 / sqrt_var, sqrt_var) * theta_mat
        )

        gamma = np.linalg.norm(S - F, "fro") ** 2
        if gamma <= _TINY:
            return 0.0
        return float(max(0.0, min(1.0, (phi - rho) / gamma / t)))

    def _get_shrink_param_lw_single_factor(self, X: Any, S: np.ndarray, F: np.ndarray) -> float:
        """Ledoit-Wolf, shrinking toward the single-factor target."""
        t, _ = X.shape
        X_mkt = np.nanmean(X, axis=1)
        var_mkt = float(np.asarray(X_mkt.dot(X_mkt) / len(X)))
        if var_mkt <= _TINY:
            return 0.0
        cov_mkt = np.asarray(X.T.dot(X_mkt) / len(X))

        y = X**2
        phi = np.sum(y.T.dot(y)) / t - np.sum(S**2)

        rdiag = np.sum(y**2) / t - np.sum(np.diag(S) ** 2)
        z = X * X_mkt[:, None]
        v1 = y.T.dot(z) / t - cov_mkt[:, None] * S
        roff1 = np.sum(v1 * cov_mkt[:, None].T) / var_mkt - np.sum(np.diag(v1) * cov_mkt) / var_mkt
        v3 = z.T.dot(z) / t - var_mkt * S
        roff3 = (
            np.sum(v3 * np.outer(cov_mkt, cov_mkt)) / var_mkt**2
            - np.sum(np.diag(v3) * cov_mkt**2) / var_mkt**2
        )
        rho = rdiag + 2 * roff1 - roff3

        gamma = np.linalg.norm(S - F, "fro") ** 2
        if gamma <= _TINY:
            return 0.0
        return float(max(0.0, min(1.0, (phi - rho) / gamma / t)))
