"""Deterministic governed ridge fitting and stored-state prediction replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import numpy as np

from quant_system.data.market_data_evidence import canonical_sha256, decimal_text
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.preprocessing import StandardizationStateV1
from quant_system.modeling.rows import FEATURE_NAMES_V1
from quant_system.modeling.trials import RidgeTrialStartV1


@dataclass(frozen=True, slots=True)
class RidgeFittedStateV1:
    intercept: str
    coefficients: tuple[str, ...]
    l2_penalty: str
    preprocessing_state_hash: str
    training_target_hash: str
    feature_names: tuple[str, ...] = FEATURE_NAMES_V1
    fitted_state_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if len(self.coefficients) != len(self.feature_names):
            raise ModelingError(
                ModelingFailureCode.MODEL_FIT_FAILED,
                "ridge coefficient shape does not match the feature contract",
            )
        parsed = tuple(
            _require_canonical_fitted_decimal(value)
            for value in (self.intercept, *self.coefficients, self.l2_penalty)
        )
        if parsed[-1] <= 0:
            raise ModelingError(
                ModelingFailureCode.INVALID_PARAMETER,
                "fitted l2_penalty must be positive",
            )
        if any(
            len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
            for value in (self.preprocessing_state_hash, self.training_target_hash)
        ):
            raise ModelingError(
                ModelingFailureCode.MODEL_FIT_FAILED,
                "fitted ridge dependencies must use SHA-256 identities",
            )
        object.__setattr__(self, "fitted_state_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["fitted_state_hash"] = self.fitted_state_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "coefficient_names": list(self.feature_names),
            "coefficients": list(self.coefficients),
            "intercept": self.intercept,
            "l2_penalty": self.l2_penalty,
            "preprocessing_state_hash": self.preprocessing_state_hash,
            "schema_id": "quantos.ridge_fitted_state",
            "schema_version": 1,
            "training_target_hash": self.training_target_hash,
        }


def fit_ridge_classifier(
    start: RidgeTrialStartV1,
    preprocessing: StandardizationStateV1,
    transformed_training_rows: tuple[tuple[str, ...], ...],
    targets: tuple[str, ...],
) -> RidgeFittedStateV1:
    feature_names = preprocessing.feature_names
    feature_count = len(feature_names)
    if len(transformed_training_rows) < feature_count + 2:
        raise ModelingError(
            ModelingFailureCode.INSUFFICIENT_TRAINING_ROWS,
            "ridge fit requires at least feature_count + 2 training rows",
        )
    if len(transformed_training_rows) != len(targets):
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            "training feature and target counts differ",
        )
    if set(targets) != {"DOWN", "UP"}:
        raise ModelingError(
            ModelingFailureCode.CONSTANT_TARGET,
            "ridge training requires both UP and DOWN targets",
        )
    matrix = _matrix(transformed_training_rows, feature_count)
    target_vector = np.array(
        [1.0 if target == "UP" else -1.0 for target in targets],
        dtype=np.float64,
    )
    design = np.hstack([np.ones((matrix.shape[0], 1), dtype=np.float64), matrix])
    regularizer = float(Decimal(start.l2_penalty)) * np.eye(
        feature_count + 1,
        dtype=np.float64,
    )
    regularizer[0, 0] = 0.0
    try:
        parameters = np.linalg.solve(
            design.T @ design + regularizer,
            design.T @ target_vector,
        )
    except np.linalg.LinAlgError as error:
        raise ModelingError(
            ModelingFailureCode.MODEL_FIT_FAILED,
            "ridge linear system could not be solved",
        ) from error
    if not np.isfinite(parameters).all():
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "ridge fit produced a non-finite parameter",
        )
    canonical = tuple(_float_decimal(value) for value in parameters)
    return RidgeFittedStateV1(
        intercept=canonical[0],
        coefficients=canonical[1:],
        l2_penalty=start.l2_penalty,
        preprocessing_state_hash=preprocessing.state_hash,
        feature_names=feature_names,
        training_target_hash=canonical_sha256(
            {
                "schema_id": "quantos.ridge_training_targets",
                "schema_version": 1,
                "targets": list(targets),
            }
        ),
    )


def predict_ridge_scores(
    fitted: RidgeFittedStateV1,
    transformed_rows: tuple[tuple[str, ...], ...],
) -> tuple[str, ...]:
    if not transformed_rows:
        return ()
    matrix = _matrix(transformed_rows, len(fitted.feature_names))
    coefficients = np.array([float(Decimal(value)) for value in fitted.coefficients])
    scores = matrix @ coefficients + float(Decimal(fitted.intercept))
    if not np.isfinite(scores).all():
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "ridge prediction produced a non-finite score",
        )
    return tuple(_float_decimal(value) for value in scores)


def _matrix(rows: tuple[tuple[str, ...], ...], feature_count: int) -> np.ndarray:
    if any(len(row) != feature_count for row in rows):
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            "transformed feature shape is invalid",
        )
    matrix = np.array(
        [[float(Decimal(value)) for value in row] for row in rows],
        dtype=np.float64,
    )
    if not np.isfinite(matrix).all():
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "transformed features must be finite",
        )
    return matrix


def _float_decimal(value: np.floating[Any] | float) -> str:
    fixed = format(float(value), ".12f")
    if "." in fixed:
        fixed = fixed.rstrip("0").rstrip(".")
    return "0" if fixed in {"-0", ""} else fixed


def _require_canonical_fitted_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except ArithmeticError as error:
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "fitted ridge state must use decimal text",
        ) from error
    if not parsed.is_finite() or decimal_text(parsed) != value:
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "fitted ridge state must use finite canonical decimal text",
        )
    return parsed
