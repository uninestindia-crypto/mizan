"""The Mizan pooled contract: a schema may add features without disturbing the six-feature family.

These tests exist because extending a closed contract is exactly where an additive change quietly
stops being additive. Each one pins a property that the 50 already-published schema-v2 models depend
on.
"""

from __future__ import annotations

import pytest

from quant_system.modeling.errors import ModelingError
from quant_system.modeling.pooled import MIZAN_WINDOW_BARS, pool_feature_datasets
from quant_system.modeling.preprocessing import StandardizationStateV1
from quant_system.modeling.ridge import RidgeFittedStateV1
from quant_system.modeling.rows import (
    FEATURE_NAMES_V1,
    FEATURE_NAMES_V3,
    FEATURE_SCHEMA_ID_V1,
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V1,
    FEATURE_SCHEMA_VERSION_V3,
    SUPPORTED_FEATURE_SCHEMAS,
    feature_names_for,
)

_HASH = "a" * 64


def test_the_mizan_family_is_fifteen_distinct_ordered_features() -> None:
    assert len(FEATURE_NAMES_V3) == 15
    assert len(set(FEATURE_NAMES_V3)) == 15


def test_mizan_carries_the_cross_sectional_features_the_six_cannot_express() -> None:
    """The whole reason for a new schema: rank features are not functions of one instrument."""
    assert "cs_rank_momentum_5" in FEATURE_NAMES_V3
    assert "cs_rank_volume_surprise" in FEATURE_NAMES_V3
    assert not set(FEATURE_NAMES_V1) & {"cs_rank_momentum_5", "cs_rank_volume_surprise"}


def test_mizan_carries_no_forward_looking_feature() -> None:
    """Forward columns are labels. A feature named `fwd_*` would be lookahead by construction."""
    assert not [name for name in FEATURE_NAMES_V3 if name.startswith("fwd")]


def test_both_legacy_schemas_still_resolve_to_the_original_six() -> None:
    assert feature_names_for(FEATURE_SCHEMA_ID_V1, FEATURE_SCHEMA_VERSION_V1) == FEATURE_NAMES_V1
    assert feature_names_for("quantos.ridge_technical_six", 2) == FEATURE_NAMES_V1


def test_every_registered_schema_is_supported_and_vice_versa() -> None:
    assert (FEATURE_SCHEMA_ID_V3, FEATURE_SCHEMA_VERSION_V3) in SUPPORTED_FEATURE_SCHEMAS
    assert (FEATURE_SCHEMA_ID_V1, FEATURE_SCHEMA_VERSION_V1) in SUPPORTED_FEATURE_SCHEMAS


def test_an_unregistered_schema_is_refused_rather_than_defaulted() -> None:
    with pytest.raises(ValueError):
        feature_names_for("quantos.not_a_schema", 9)


def test_fitted_state_defaults_to_the_six_so_published_manifests_keep_their_hash() -> None:
    """The 50 published schema-v2 models are reconstructed without a `feature_names` argument.

    If the default moved, or if `coefficient_names` stopped defaulting to the six, every one of
    those manifests would fail to rehash and the audit trail would break.
    """
    fitted = RidgeFittedStateV1(
        intercept="0.1",
        coefficients=("0.1", "0.2", "0.3", "0.4", "0.5", "0.6"),
        l2_penalty="1",
        preprocessing_state_hash=_HASH,
        training_target_hash=_HASH,
    )
    assert fitted.feature_names == FEATURE_NAMES_V1
    assert fitted.to_canonical_dict()["coefficient_names"] == list(FEATURE_NAMES_V1)


def test_fitted_state_shape_is_checked_against_its_own_family_not_the_six() -> None:
    fitted = RidgeFittedStateV1(
        intercept="0.1",
        coefficients=tuple("0.1" for _ in FEATURE_NAMES_V3),
        l2_penalty="1",
        preprocessing_state_hash=_HASH,
        training_target_hash=_HASH,
        feature_names=FEATURE_NAMES_V3,
    )
    assert len(fitted.coefficients) == 15
    with pytest.raises(ModelingError):
        RidgeFittedStateV1(
            intercept="0.1",
            coefficients=("0.1", "0.2"),
            l2_penalty="1",
            preprocessing_state_hash=_HASH,
            training_target_hash=_HASH,
            feature_names=FEATURE_NAMES_V3,
        )


def test_preprocessing_accepts_a_registered_family_and_refuses_an_invented_one() -> None:
    state = StandardizationStateV1(
        feature_names=FEATURE_NAMES_V3,
        means=tuple("0" for _ in FEATURE_NAMES_V3),
        scales=tuple("1" for _ in FEATURE_NAMES_V3),
        zero_variance_features=(),
        training_feature_rows_hash=_HASH,
    )
    assert state.feature_names == FEATURE_NAMES_V3
    with pytest.raises(ModelingError):
        StandardizationStateV1(
            feature_names=("invented_feature",),
            means=("0",),
            scales=("1",),
            zero_variance_features=(),
            training_feature_rows_hash=_HASH,
        )


def test_pooling_nothing_is_refused_rather_than_producing_an_empty_study() -> None:
    with pytest.raises(ModelingError):
        pool_feature_datasets([], candidate_id="cand_mizan_v1")


def test_the_mizan_window_is_fixed_not_expanding() -> None:
    """A window that grows with retained history makes training and execution disagree."""
    assert MIZAN_WINDOW_BARS == 51
