"""Tests for Mizan unified model architecture, weights, preprocessing, and serialization."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.modeling.errors import ModelingError
from quant_system.modeling.mizan_model import (
    MizanConfig,
    MizanModel,
    MizanPreprocessorConfig,
    MizanWeights,
)
from quant_system.modeling.rows import FEATURE_NAMES_V3


def test_mizan_config_serialization() -> None:
    config = MizanConfig(
        candidate_id="cand_mizan_test",
        model_id="mizan-test-v1",
        model_name="Mizan Unit Test",
        l2_penalty="1.5",
        score_threshold="0.05",
        label_horizon_sessions=11,
    )
    d = config.to_dict()
    assert d["candidate_id"] == "cand_mizan_test"
    assert d["l2_penalty"] == "1.5"
    assert d["score_threshold"] == "0.05"
    assert len(d["feature_names"]) == 15

    restored = MizanConfig.from_dict(d)
    assert restored == config


def test_mizan_weights_validation_and_hashing() -> None:
    coeffs = tuple(f"0.{i}" for i in range(15))
    weights = MizanWeights(intercept="0.123", coefficients=coeffs, feature_names=FEATURE_NAMES_V3)
    assert len(weights.coefficients) == 15
    assert len(weights.weights_hash) == 64

    # Mismatch length
    with pytest.raises(ModelingError):
        MizanWeights(intercept="0.1", coefficients=("0.1", "0.2"), feature_names=FEATURE_NAMES_V3)


def test_mizan_preprocessor_standardization() -> None:
    means = tuple("0.0" for _ in range(15))
    scales = tuple("2.0" for _ in range(15))
    prep = MizanPreprocessorConfig(
        means=means,
        scales=scales,
        feature_names=FEATURE_NAMES_V3,
        zero_variance_features=("return_1",),
    )
    assert len(prep.preprocessor_hash) == 64

    # Test standardization logic
    raw_feats = {"return_1": 10.0, "return_5": 4.0}
    std = prep.standardize(raw_feats)

    # return_1 is in zero_variance, should be 0.0
    assert std["return_1"] == Decimal("0.0")
    # return_5: (4.0 - 0.0) / 2.0 = 2.0
    assert std["return_5"] == Decimal("2.0")
    # unspecified features default to 0.0
    assert std["return_21"] == Decimal("0.0")


def test_mizan_model_prediction_and_ranking() -> None:
    model = MizanModel.default_model()
    assert model.config.model_id == "mizan-v1"
    assert model.candidate_id == "cand_mizan_v1"

    # Predict single vector
    sample_features = dict.fromkeys(FEATURE_NAMES_V3, 0.1)
    score = model.predict_score(sample_features)
    assert isinstance(score, float)

    # Predict universe
    universe_feats = {
        "INFY": dict.fromkeys(FEATURE_NAMES_V3, 0.2),
        "TCS": dict.fromkeys(FEATURE_NAMES_V3, -0.1),
        "RELIANCE": dict.fromkeys(FEATURE_NAMES_V3, 0.5),
    }
    scores = model.predict_scores(universe_feats)
    assert len(scores) == 3
    assert all(isinstance(v, float) for v in scores.values())

    # Rank universe
    ranked = model.rank_universe(universe_feats, top_n=2)
    assert len(ranked) == 2
    assert ranked[0][1] >= ranked[1][1]


def test_mizan_model_save_and_load_pretrained_directory() -> None:
    model = MizanModel.default_model()

    with tempfile.TemporaryDirectory() as tmp_dir:
        save_path = Path(tmp_dir) / "mizan_test_export"
        model.save_pretrained(save_path, package_zip=False)

        assert (save_path / "config.json").exists()
        assert (save_path / "model_card.json").exists()
        assert (save_path / "preprocessor_config.json").exists()
        assert (save_path / "weights.json").exists()
        assert (save_path / "checksums.json").exists()

        # Load back
        loaded = MizanModel.from_pretrained(save_path)
        assert loaded.config.model_id == model.config.model_id
        assert loaded.weights.weights_hash == model.weights.weights_hash

        # Assert identical predictions
        test_feats = dict.fromkeys(FEATURE_NAMES_V3, 0.05)
        assert model.predict_score(test_feats) == loaded.predict_score(test_feats)


def test_mizan_model_save_and_load_pretrained_zip() -> None:
    model = MizanModel.default_model()

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "mizan_bundle.zip"
        model.save_pretrained(zip_path, package_zip=True)
        assert zip_path.exists()

        # Load from .zip
        loaded = MizanModel.from_pretrained(zip_path)
        assert loaded.config.model_id == model.config.model_id
        assert loaded.weights.weights_hash == model.weights.weights_hash

        test_feats = dict.fromkeys(FEATURE_NAMES_V3, 0.05)
        assert model.predict_score(test_feats) == loaded.predict_score(test_feats)
