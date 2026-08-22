"""Training-only standardization with content-bound learned state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256, decimal_text
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.rows import FEATURE_NAMES_V1, FeatureRowV1

_STATE_QUANTUM = Decimal("0.000000000000000001")


@dataclass(frozen=True, slots=True)
class StandardizationStateV1:
    feature_names: tuple[str, ...]
    means: tuple[str, ...]
    scales: tuple[str, ...]
    zero_variance_features: tuple[str, ...]
    training_feature_rows_hash: str
    state_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.feature_names != FEATURE_NAMES_V1:
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "preprocessing feature order is not the closed v1 family",
            )
        if len(self.means) != len(self.feature_names) or len(self.scales) != len(
            self.feature_names
        ):
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "preprocessing state shape does not match its feature order",
            )
        if tuple(sorted(set(self.zero_variance_features))) != self.zero_variance_features:
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "zero-variance feature names must be unique and sorted",
            )
        if any(name not in self.feature_names for name in self.zero_variance_features):
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "zero-variance state names an unknown feature",
            )
        scales = _validate_state_numbers(self.means, self.scales)
        zero_indexes = tuple(self.feature_names.index(name) for name in self.zero_variance_features)
        if any(scales[index] != 1 for index in zero_indexes):
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "zero-variance preprocessing features must use scale one",
            )
        if len(self.training_feature_rows_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.training_feature_rows_hash
        ):
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "training feature rows hash is invalid",
            )
        object.__setattr__(self, "state_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["state_hash"] = self.state_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "feature_names": list(self.feature_names),
            "means": list(self.means),
            "scales": list(self.scales),
            "schema_id": "quantos.standardization_state",
            "schema_version": 1,
            "training_feature_rows_hash": self.training_feature_rows_hash,
            "zero_variance_features": list(self.zero_variance_features),
        }


def fit_standardization(rows: tuple[FeatureRowV1, ...]) -> StandardizationStateV1:
    if not rows:
        raise ModelingError(
            ModelingFailureCode.INSUFFICIENT_TRAINING_ROWS,
            "preprocessing requires non-empty training rows",
        )
    _validate_feature_rows(rows)
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        columns = tuple(
            tuple(Decimal(row.features[name]) for row in rows) for name in FEATURE_NAMES_V1
        )
        means = tuple(sum(column) / Decimal(len(column)) for column in columns)
        variances = tuple(
            sum((value - mean) ** 2 for value in column) / Decimal(len(column))
            for column, mean in zip(columns, means, strict=True)
        )
        raw_scales = tuple(variance.sqrt() for variance in variances)
        zero_variance = tuple(
            name for name, scale in zip(FEATURE_NAMES_V1, raw_scales, strict=True) if scale == 0
        )
        scales = tuple(Decimal(1) if scale == 0 else scale for scale in raw_scales)
        return StandardizationStateV1(
            feature_names=FEATURE_NAMES_V1,
            means=tuple(_state_decimal(value) for value in means),
            scales=tuple(_state_decimal(value) for value in scales),
            zero_variance_features=tuple(sorted(zero_variance)),
            training_feature_rows_hash=feature_rows_hash(rows),
        )


def transform_feature_rows(
    rows: tuple[FeatureRowV1, ...],
    state: StandardizationStateV1,
) -> tuple[tuple[str, ...], ...]:
    if not rows:
        return ()
    _validate_feature_rows(rows)
    return tuple(standardize_feature_values(row.features, state) for row in rows)


def standardize_feature_values(
    features: Mapping[str, str],
    state: StandardizationStateV1,
) -> tuple[str, ...]:
    """Standardize one feature mapping with a fitted training-side state.

    The single standardization kernel. ``transform_feature_rows`` applies it across a training
    dataset and the execution adapter applies it to one live row, so a model never sees a live value
    scaled by different arithmetic than its training values were.
    """
    means = tuple(Decimal(value) for value in state.means)
    scales = tuple(Decimal(value) for value in state.scales)
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        return tuple(
            _state_decimal((Decimal(features[name]) - mean) / scale)
            for name, mean, scale in zip(FEATURE_NAMES_V1, means, scales, strict=True)
        )


def feature_rows_hash(rows: tuple[FeatureRowV1, ...]) -> str:
    return canonical_sha256(
        {
            "records": [row.to_canonical_dict() for row in rows],
            "schema_id": "quantos.preprocessing_training_rows",
            "schema_version": 1,
        }
    )


def _validate_feature_rows(rows: tuple[FeatureRowV1, ...]) -> None:
    keys = tuple((row.decision_at, row.symbol, row.provider_instrument_id) for row in rows)
    if keys != tuple(sorted(set(keys))):
        raise ModelingError(
            ModelingFailureCode.RECORD_ORDER_INVALID,
            "preprocessing rows must be unique and strictly chronological",
        )
    if len({row.candidate_id for row in rows}) != 1:
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            "preprocessing rows cannot mix candidate identities",
        )


def _state_decimal(value: Decimal) -> str:
    rounded = value.quantize(_STATE_QUANTUM, rounding=ROUND_HALF_EVEN)
    return decimal_text(rounded)


def _require_finite_text(value: str, field_name: str) -> Decimal:
    parsed = Decimal(value)
    if not parsed.is_finite() or decimal_text(parsed) != value:
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            f"{field_name} must be finite canonical decimal text",
        )
    return parsed


def _validate_state_numbers(means: tuple[str, ...], scales: tuple[str, ...]) -> tuple[Decimal, ...]:
    for mean in means:
        _require_finite_text(mean, "preprocessing mean")
    parsed_scales = tuple(_require_finite_text(scale, "preprocessing scale") for scale in scales)
    if any(scale <= 0 for scale in parsed_scales):
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            "preprocessing scales must be positive",
        )
    return parsed_scales
