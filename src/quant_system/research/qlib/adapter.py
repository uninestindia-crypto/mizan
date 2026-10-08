"""Adapter bridging Qlib-style cross-sectional modeling with Mizan governance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.stats import spearmanr


@dataclass(frozen=True, slots=True)
class QlibEvaluationReport:
    """Statistical performance metrics for a Qlib-style cross-sectional model."""

    ic_mean: float
    rank_ic_mean: float
    ic_ir: float
    rank_ic_ir: float
    top_decile_excess: float
    sample_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "ic_mean": round(self.ic_mean, 6),
            "rank_ic_mean": round(self.rank_ic_mean, 6),
            "ic_ir": round(self.ic_ir, 4),
            "rank_ic_ir": round(self.rank_ic_ir, 4),
            "top_decile_excess": round(self.top_decile_excess, 6),
            "sample_size": self.sample_size,
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
        return (X_arr @ self.weights) + self.intercept

    def evaluate(self, dataset: QlibRankDataset) -> QlibEvaluationReport:
        """Compute standard Qlib evaluation metrics: IC, Rank IC, and Top Decile Excess."""
        if len(dataset.y) < 10:
            raise ValueError("Insufficient evaluation samples (minimum 10 required)")

        preds = self.predict(dataset.X)
        actuals = dataset.y

        # Pearson IC
        std_p = float(np.std(preds))
        std_a = float(np.std(actuals))
        if std_p > 1e-12 and std_a > 1e-12:
            ic = float(np.corrcoef(preds, actuals)[0, 1])
        else:
            ic = 0.0

        # Rank IC (Spearman)
        res = spearmanr(preds, actuals)
        rank_ic = float(res.correlation) if not np.isnan(res.correlation) else 0.0

        # Top Decile vs Bottom Decile
        n = len(preds)
        k = max(1, n // 10)
        sorted_indices = np.argsort(preds)
        bottom_return = float(np.mean(actuals[sorted_indices[:k]]))
        top_return = float(np.mean(actuals[sorted_indices[-k:]]))
        top_decile_excess = top_return - bottom_return

        return QlibEvaluationReport(
            ic_mean=ic,
            rank_ic_mean=rank_ic,
            ic_ir=ic / 0.1 if ic != 0 else 0.0,
            rank_ic_ir=rank_ic / 0.1 if rank_ic != 0 else 0.0,
            top_decile_excess=top_decile_excess,
            sample_size=n,
        )
