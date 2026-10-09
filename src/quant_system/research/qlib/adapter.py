"""Adapter bridging Qlib-style cross-sectional modeling with Mizan governance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from scipy.stats import spearmanr  # type: ignore[import-untyped]

from quant_system.research.qlib.alpha_eval import calc_ic, ic_summary

MIN_NAMES_PER_DATE = 3  # a ranking of fewer names than this says nothing


@dataclass(frozen=True, slots=True)
class QlibEvaluationReport:
    """Statistical performance metrics for a Qlib-style cross-sectional model."""

    ic_mean: float
    rank_ic_mean: float
    ic_ir: float | None
    rank_ic_ir: float | None
    top_decile_excess: float
    sample_size: int
    n_dates: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ic_mean": round(self.ic_mean, 6),
            "rank_ic_mean": round(self.rank_ic_mean, 6),
            "ic_ir": None if self.ic_ir is None else round(self.ic_ir, 4),
            "rank_ic_ir": None if self.rank_ic_ir is None else round(self.rank_ic_ir, 4),
            "top_decile_excess": round(self.top_decile_excess, 6),
            "sample_size": self.sample_size,
            "n_dates": self.n_dates,
        }


@dataclass(slots=True)
class QlibRankDataset:
    """Tabular cross-sectional dataset container matching Qlib's DatasetH format."""

    symbols: list[str]
    dates: list[str]
    feature_names: list[str]
    X: np.ndarray  # shape: (N, D)
    y: np.ndarray  # shape: (N,)


class QlibModelAdapter:
    """Governed model evaluator for Qlib cross-sectional factor ranking models."""

    def __init__(self, ridge_alpha: float = 1.0) -> None:
        self.ridge_alpha = float(ridge_alpha)
        self.weights: np.ndarray | None = None
        self.intercept: float = 0.0

    def fit(self, dataset: QlibRankDataset) -> None:
        """Fit a regularized cross-sectional model on the dataset features."""
        if len(dataset.y) == 0:
            raise ValueError("Cannot fit on empty dataset")

        X = np.asarray(dataset.X, dtype=np.float64)
        y = np.asarray(dataset.y, dtype=np.float64)

        # Standardize features (Z-score)
        means = np.nanmean(X, axis=0)
        stds = np.nanstd(X, axis=0)
        stds[stds < 1e-12] = 1.0
        X_norm = np.nan_to_num((X - means) / stds, nan=0.0)

        # Ridge regression closed-form solution: w = (X^T X + alpha * I)^(-1) X^T y
        n_features = X_norm.shape[1]
        xt_x = X_norm.T @ X_norm
        reg_matrix = xt_x + self.ridge_alpha * np.eye(n_features)
        xt_y = X_norm.T @ y

        try:
            self.weights = np.linalg.solve(reg_matrix, xt_y)
        except np.linalg.LinAlgError:
            self.weights = np.linalg.pinv(reg_matrix) @ xt_y

        self.intercept = float(np.mean(y) - np.mean(X_norm @ self.weights))

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate continuous ranking predictions for feature rows."""
        if self.weights is None:
            raise RuntimeError("Model has not been fitted")
        X_arr = np.asarray(X, dtype=np.float64)
        res = (X_arr @ self.weights) + self.intercept
        return np.asarray(res, dtype=np.float64)

    def evaluate(self, dataset: QlibRankDataset) -> QlibEvaluationReport:
        """Judge the signal the way Qlib does: one date at a time, then how steady that is across dates.

        The IC and Rank IC are the means of the per-date correlations between the signal and what followed. The information
        ratio is that mean divided by its spread across dates, and needs at least 3 dates; with fewer it is ``None``
        (not measurable), never a made-up number. If no date has at least 3 names, the pooled correlation is reported
        instead and the ratio is ``None``.
        """
        if len(dataset.y) < 10:
            raise ValueError("Insufficient evaluation samples (minimum 10 required)")

        preds = self.predict(dataset.X)
        actuals = dataset.y

        ic, rank_ic, ic_ir, rank_ic_ir, n_dates = self._per_date_ic(dataset, preds)
        if n_dates == 0:
            ic, rank_ic = self._pooled_ic(preds, actuals)

        # Top Decile vs Bottom Decile
        n = len(preds)
        k = max(1, n // 10)
        sorted_indices = np.argsort(preds)
        bottom_return = float(np.mean(actuals[sorted_indices[:k]]))
        top_return = float(np.mean(actuals[sorted_indices[-k:]]))

        return QlibEvaluationReport(
            ic_mean=ic,
            rank_ic_mean=rank_ic,
            ic_ir=ic_ir,
            rank_ic_ir=rank_ic_ir,
            top_decile_excess=top_return - bottom_return,
            sample_size=n,
            n_dates=n_dates,
        )

    @staticmethod
    def _per_date_ic(
        dataset: QlibRankDataset, preds: np.ndarray
    ) -> tuple[float, float, float | None, float | None, int]:
        frame = pd.DataFrame(
            {
                "datetime": dataset.dates,
                "instrument": dataset.symbols,
                "pred": preds,
                "label": dataset.y,
            }
        )
        sizes = frame.groupby("datetime")["pred"].transform("size")
        usable = frame[sizes >= MIN_NAMES_PER_DATE].set_index(["datetime", "instrument"])
        if usable.empty:
            return 0.0, 0.0, None, None, 0
        ic, rank_ic = calc_ic(usable["pred"], usable["label"], dropna=True)
        pearson, spearman = ic_summary(ic), ic_summary(rank_ic)
        return (
            0.0 if np.isnan(pearson.mean) else pearson.mean,
            0.0 if np.isnan(spearman.mean) else spearman.mean,
            pearson.ir,
            spearman.ir,
            pearson.n_dates,
        )

    @staticmethod
    def _pooled_ic(preds: np.ndarray, actuals: np.ndarray) -> tuple[float, float]:
        ic = 0.0
        if float(np.std(preds)) > 1e-12 and float(np.std(actuals)) > 1e-12:
            ic = float(np.corrcoef(preds, actuals)[0, 1])
        res = spearmanr(preds, actuals)
        rank_ic = float(res.correlation) if not np.isnan(res.correlation) else 0.0
        return ic, rank_ic
