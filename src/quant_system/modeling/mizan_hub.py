"""Mīzān Model Hub: Standalone packaging, export, sharing, download, and upload facilities.

Modeled after modern LLM distribution standards (like Hugging Face Hub), this module
allows Mīzān models to be exported into standard packages (`.zip` archives or directories),
verified for cryptographic integrity via SHA-256 digests, downloaded from remote URLs or
Hugging Face repositories, and uploaded to remote registries or cloud storage.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.modeling.mizan_model import (
    MizanConfig,
    MizanModel,
    MizanModelCard,
    MizanPreprocessorConfig,
    MizanWeights,
)
from quant_system.modeling.rows import (
    FEATURE_NAMES_V3,
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V3,
)

logger = logging.getLogger(__name__)

REQUIRED_BUNDLE_FILES = (
    "config.json",
    "model_card.json",
    "preprocessor_config.json",
    "weights.json",
)


class MizanHubError(RuntimeError):
    """Raised for Mizan Hub export, download, upload, or integrity errors."""


class MizanHub:
    """Hub operations for Mizan models."""

    @classmethod
    def export_package(
        cls,
        model: MizanModel,
        output_path: str | Path,
        package_zip: bool = True,
    ) -> Path:
        """Export a Mizan model to a standalone directory or `.zip` archive.

        Args:
            model: The MizanModel instance to export.
            output_path: Destination path for the directory or `.zip` file.
            package_zip: Whether to compress into a `.zip` archive.

        Returns:
            Path to the created package.
        """
        target = Path(output_path)
        return model.save_pretrained(target, package_zip=package_zip)

    @classmethod
    def load_package(cls, package_path: str | Path) -> MizanModel:
        """Load a Mizan model from a local directory or `.zip` archive with integrity checks.

        Args:
            package_path: Path to package directory or `.zip` file.

        Returns:
            Loaded MizanModel instance.
        """
        path = Path(package_path)
        if not path.exists():
            raise MizanHubError(f"Package path does not exist: {path}")

        cls.verify_package_integrity(path)
        return MizanModel.from_pretrained(path)

    @classmethod
    def verify_package_integrity(cls, package_path: str | Path) -> bool:
        """Verify that all files in the package match their recorded SHA-256 checksums."""
        path = Path(package_path)
        if not path.exists():
            raise MizanHubError(f"Cannot verify nonexistent package: {path}")

        if path.is_file() and (path.suffix == ".zip" or zipfile.is_zipfile(path)):
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(tmp_dir)
                return cls._verify_directory_checksums(Path(tmp_dir))

        if path.is_dir():
            return cls._verify_directory_checksums(path)

        raise MizanHubError(f"Unrecognized package format: {path}")

    @classmethod
    def _verify_directory_checksums(cls, directory: Path) -> bool:
        checksums_file = directory / "checksums.json"
        if not checksums_file.exists():
            raise MizanHubError(f"Package missing checksums.json: {directory}")

        try:
            checksums_data = json.loads(checksums_file.read_text(encoding="utf-8"))
        except Exception as err:
            raise MizanHubError(f"Corrupt checksums.json in {directory}: {err}") from err

        for required in REQUIRED_BUNDLE_FILES:
            if required not in checksums_data:
                raise MizanHubError(f"checksums.json missing record for required file: {required}")
            target_file = directory / required
            if not target_file.exists():
                raise MizanHubError(f"Package missing expected file: {required}")

            content = json.loads(target_file.read_text(encoding="utf-8"))
            actual_hash = canonical_sha256(content)
            expected_hash = checksums_data[required]

            if actual_hash != expected_hash:
                raise MizanHubError(
                    f"Integrity check failed for {required}: expected {expected_hash}, got {actual_hash}"
                )

        return True

    @classmethod
    def download_from_url(
        cls,
        url: str,
        output_dir: str | Path | None = None,
    ) -> MizanModel:
        """Download a Mizan model `.zip` package from a remote URL and load it."""
        dest_dir = (
            Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="mizan_download_"))
        )
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / "mizan_downloaded.zip"

        try:
            logger.info("Downloading Mizan model from %s...", url)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "QuantOS-MizanHub/1.0"},
            )
            with urllib.request.urlopen(req) as resp, open(dest_file, "wb") as out:
                shutil.copyfileobj(resp, out)
        except Exception as err:
            raise MizanHubError(f"Failed to download model from {url}: {err}") from err

        return cls.load_package(dest_file)

    @classmethod
    def download_from_hf(
        cls,
        repo_id: str,
        filename: str = "mizan_model.zip",
        revision: str = "main",
        token: str | None = None,
        local_dir: str | Path | None = None,
    ) -> MizanModel:
        """Download a Mizan model from the Hugging Face Hub."""
        import importlib

        try:
            hf_module = importlib.import_module("huggingface_hub")
            hf_hub_download = hf_module.hf_hub_download
        except (ImportError, AttributeError):
            # Fallback to direct HF resolve URL download
            hf_url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{filename}"
            return cls.download_from_url(hf_url, output_dir=local_dir)

        try:
            target_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
                token=token or os.getenv("HF_TOKEN"),
                local_dir=str(local_dir) if local_dir else None,
            )
            return cls.load_package(target_path)
        except Exception as err:
            raise MizanHubError(
                f"Failed to download Mizan model from Hugging Face repo {repo_id}: {err}"
            ) from err

    @classmethod
    def upload_to_hf(
        cls,
        model: MizanModel,
        repo_id: str,
        token: str | None = None,
        commit_message: str = "Upload Mizan model package",
        private: bool = False,
    ) -> dict[str, Any]:
        """Upload a Mizan model to Hugging Face Hub."""
        import importlib

        resolved_token = token or os.getenv("HF_TOKEN")
        if not resolved_token:
            raise MizanHubError(
                "HF_TOKEN is required to upload models to Hugging Face Hub. "
                "Provide token parameter or set HF_TOKEN environment variable."
            )

        try:
            hf_module = importlib.import_module("huggingface_hub")
            hf_api_cls = hf_module.HfApi
        except (ImportError, AttributeError) as err:
            raise MizanHubError(
                "huggingface_hub package is required for direct upload. "
                "Install with `pip install huggingface_hub`."
            ) from err

        with tempfile.TemporaryDirectory() as tmp_dir:
            model_dir = Path(tmp_dir) / "model"
            model.save_pretrained(model_dir, package_zip=False)

            api = hf_api_cls(token=resolved_token)
            api.create_repo(repo_id=repo_id, exist_ok=True, private=private)
            upload_result = api.upload_folder(
                folder_path=str(model_dir),
                repo_id=repo_id,
                commit_message=commit_message,
            )
            return {"repo_id": repo_id, "result": str(upload_result), "status": "uploaded"}

    @classmethod
    def from_evidence_manifest(
        cls, manifest_data: Mapping[str, Any], candidate_id: str = "cand_mizan_v1"
    ) -> MizanModel:
        """Construct a MizanModel directly from a QuantOS evidence manifest dictionary."""
        metadata = manifest_data.get("metadata", {})
        fitted_state = metadata.get("fitted_state", {})
        prep_state = metadata.get("preprocessing", {})
        model_id = str(metadata.get("model_id", "mizan-v1"))

        config = MizanConfig(
            candidate_id=candidate_id,
            model_id=model_id,
            model_name="Mizan Governed Model",
            feature_schema_id=str(metadata.get("feature_schema_id", FEATURE_SCHEMA_ID_V3)),
            feature_schema_version=int(
                metadata.get("feature_schema_version", FEATURE_SCHEMA_VERSION_V3)
            ),
            feature_names=tuple(prep_state.get("feature_names", FEATURE_NAMES_V3)),
            l2_penalty=str(fitted_state.get("l2_penalty", "1.0")),
            score_threshold=str(fitted_state.get("intercept", "0.0")),
            label_horizon_sessions=11,
            version="1.0.0",
        )
        weights = MizanWeights(
            intercept=str(fitted_state.get("intercept", "0.0")),
            coefficients=tuple(str(c) for c in fitted_state.get("coefficients", [])),
            feature_names=tuple(
                str(n) for n in fitted_state.get("coefficient_names", FEATURE_NAMES_V3)
            ),
        )
        preprocessor = MizanPreprocessorConfig(
            means=tuple(str(m) for m in prep_state.get("means", [])),
            scales=tuple(str(s) for s in prep_state.get("scales", [])),
            feature_names=tuple(str(n) for n in prep_state.get("feature_names", FEATURE_NAMES_V3)),
            zero_variance_features=tuple(
                str(z) for z in prep_state.get("zero_variance_features", [])
            ),
        )

        strategy_reports = metadata.get("strategy_reports", [])
        metrics_dict: dict[str, str] = {}
        for report in strategy_reports:
            if report.get("strategy_id") == "RIDGE":
                metrics_dict = {
                    k: str(v) for k, v in report.get("metrics", {}).items() if v is not None
                }
                break

        card = MizanModelCard(
            model_id=model_id,
            candidate_id=candidate_id,
            model_name="Mizan Governed Model",
            metrics=metrics_dict,
            verdict=str(metadata.get("verdict", "RESEARCH_ONLY")),
        )

        return MizanModel(
            config=config,
            weights=weights,
            preprocessor=preprocessor,
            model_card=card,
        )
