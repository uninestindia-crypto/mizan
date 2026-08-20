"""Train-only preprocessing state and replay tests."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from quant_system.modeling import (
    FEATURE_NAMES_V1,
    ModelingError,
    ModelingFailureCode,
    fit_standardization,
    transform_feature_rows,
)
from tests.modeling_training_fixtures import fold_feature_rows, governed_training_journey


def test_standardization_is_deterministic_and_centered_on_training_rows(  # test-allow: loop-in-test - the closed feature contract is guaranteed non-empty.
) -> None:
    journey = governed_training_journey()
    training_rows = fold_feature_rows(journey, validation=False)

    first = fit_standardization(training_rows)
    second = fit_standardization(training_rows)
    transformed = transform_feature_rows(training_rows, first)

    assert first == second
    assert (
        first.state_hash
        == "e2eebf92114fb456ba6c59c8a0d10860266e17ec66c762247e71e9890418704b"  # pragma: allowlist secret - deterministic public test hash.
    )
    assert len(transformed) == len(training_rows)
    assert all(
        abs(sum((Decimal(row[index]) for row in transformed), start=Decimal(0)))
        <= Decimal("0.0000000000000002")
        for index in range(len(FEATURE_NAMES_V1))
    )


def test_validation_values_are_transformed_but_never_fit_into_state() -> None:
    journey = governed_training_journey()
    training_rows = fold_feature_rows(journey, validation=False)
    validation_rows = fold_feature_rows(journey, validation=True)
    state = fit_standardization(training_rows)
    changed = replace(
        validation_rows[0],
        features=dict.fromkeys(FEATURE_NAMES_V1, "99"),
    )

    original_values = transform_feature_rows(validation_rows, state)
    changed_values = transform_feature_rows((changed, *validation_rows[1:]), state)

    assert state == fit_standardization(training_rows)
    assert original_values[0] != changed_values[0]
    assert state.state_hash != fit_standardization(validation_rows).state_hash


def test_zero_variance_features_are_explicit_and_scaled_by_one() -> None:
    journey = governed_training_journey()
    training_rows = fold_feature_rows(journey, validation=False)
    constant_rows = tuple(
        replace(row, features=dict.fromkeys(FEATURE_NAMES_V1, "0.5")) for row in training_rows
    )

    state = fit_standardization(constant_rows)
    transformed = transform_feature_rows(constant_rows, state)

    assert state.zero_variance_features == tuple(sorted(FEATURE_NAMES_V1))
    assert state.scales == ("1",) * len(FEATURE_NAMES_V1)
    assert set(transformed) == {("0",) * len(FEATURE_NAMES_V1)}


def test_preprocessing_rejects_reordered_rows() -> None:
    journey = governed_training_journey()
    training_rows = fold_feature_rows(journey, validation=False)

    with pytest.raises(ModelingError) as captured:
        fit_standardization(tuple(reversed(training_rows)))

    assert captured.value.code == ModelingFailureCode.RECORD_ORDER_INVALID
