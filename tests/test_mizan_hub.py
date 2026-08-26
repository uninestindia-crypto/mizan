"""Tests for MizanHub packaging, export, integrity verification, and CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from quant_system.modeling.mizan_cli import (
    build_parser,
    handle_export,
    handle_info,
    handle_predict,
    handle_verify,
)
from quant_system.modeling.mizan_hub import MizanHub, MizanHubError
from quant_system.modeling.mizan_model import MizanModel
from quant_system.modeling.rows import FEATURE_NAMES_V3


def test_mizan_hub_export_and_load_package() -> None:
    model = MizanModel.default_model()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_zip = Path(tmp_dir) / "mizan_export.zip"
        MizanHub.export_package(model, pkg_zip, package_zip=True)

        assert pkg_zip.exists()
        assert MizanHub.verify_package_integrity(pkg_zip) is True

        loaded = MizanHub.load_package(pkg_zip)
        assert loaded.model_id == model.model_id
        assert loaded.weights.weights_hash == model.weights.weights_hash


def test_mizan_hub_detects_tampered_package() -> None:
    model = MizanModel.default_model()

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_dir = Path(tmp_dir) / "mizan_dir"
        MizanHub.export_package(model, pkg_dir, package_zip=False)

        # Tamper with weights.json
        weights_file = pkg_dir / "weights.json"
        w_data = json.loads(weights_file.read_text(encoding="utf-8"))
        w_data["intercept"] = "999.999"
        weights_file.write_text(json.dumps(w_data), encoding="utf-8")

        with pytest.raises(MizanHubError, match="Integrity check failed"):
            MizanHub.load_package(pkg_dir)


def test_mizan_cli_info_and_verify() -> None:
    parser = build_parser()
    args_info = parser.parse_args(["info"])
    assert handle_info(args_info) == 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "mizan_test.zip"
        args_export = parser.parse_args(["export", "-o", str(zip_path)])
        assert handle_export(args_export) == 0
        assert zip_path.exists()

        args_verify = parser.parse_args(["verify", str(zip_path)])
        assert handle_verify(args_verify) == 0

        # Predict CLI
        test_feats = json.dumps(dict.fromkeys(FEATURE_NAMES_V3, 0.1))
        args_predict = parser.parse_args(["predict", "--features", test_feats])
        assert handle_predict(args_predict) == 0
