"""Mīzān: The flagship, unified Machine Learning model architecture for QuantOS.

Mīzān represents the sole, standardized, professional-grade ML model architecture in QuantOS.
It combines pooled cross-sectional feature engineering, standardization, L2 ridge scoring,
and comprehensive model card governance into a single, portable, Hugging Face-style model
object that can be serialized (`save_pretrained`), loaded (`from_pretrained`), shared,
downloaded, and uploaded to any registry or remote storage.
"""

from __future__ import annotations

import json
import re
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final

from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.rows import (
    FEATURE_NAMES_V3,
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V3,
)

_HASH_REGEX = re.compile(r"^[0-9a-f]{64}$")


def _canonical_decimal_str(val: Decimal | float | int | str, name: str) -> str:
    try:
        d = Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError) as err:
        raise ModelingError(
            ModelingFailureCode.INVALID_PARAMETER,
            f"Field '{name}' must be a valid decimal representation, got: {val!r}",
        ) from err
    if not d.is_finite():
        raise ModelingError(
            ModelingFailureCode.INVALID_PARAMETER,
            f"Field '{name}' must be finite, got: {val!r}",
        )
    return decimal_text(d)


#: Where the weights returned by :meth:`MizanModel.default_model` actually came from.
#:
#: This was stated only in that method's docstring, which meant nothing that ran could repeat it. A
#: reader watching the paper book saw "Mizan Flagship Alpha (NSE 50) v1.0.0" -- a product name shared
#: by every retrain -- while a *newer* flagship card described a different artifact entirely
#: (`trial_mizan_h11_003`). Training a new artifact does not replace these running weights; only
#: editing this file does. So the identity is published as data the session can print.
#:
#: The deflated Sharpe is the field that actually distinguishes one trial from the next, which is why
#: it travels with the name rather than being left in a metrics blob.
DEFAULT_MODEL_PROVENANCE: Final[dict[str, str]] = {
    "source_trial_id": "trial_mizan_h11_002",
    "source_evidence_model_id": "model_1f936eadcb8d44154f28af13",
    "verdict": "RESEARCH_ONLY",
    "deflated_sharpe_ratio": "0.175990",
    "gate_min_deflated_sharpe": "0.95",
    "ridge_sharpe": "-0.410755",
    "note": (
        "Frozen research weights. Not promotable and not expected to become so; the paper book "
        "observes execution behaviour, not edge. Retraining publishes a new artifact and does not "
        "change what this book runs."
    ),
}


def validate_mizan_model_only(candidate_id: str, model_id: str | None = None) -> None:
    """Enforce that Mizan is the sole authorized ML model architecture across QuantOS.

    Rejects any non-Mizan model candidate ID.
    """
    if not candidate_id.startswith("cand_mizan"):
        raise ModelingError(
            ModelingFailureCode.INVALID_PARAMETER,
            f"Unauthorized model architecture '{candidate_id}'. QuantOS strictly standardizes on Mizan as the single ML model.",
        )


@dataclass(frozen=True, slots=True)
class MizanConfig:
    """Configuration and architecture parameters for a Mizan model."""

    candidate_id: str = "cand_mizan_v1"
    model_id: str = "mizan-v1"
    model_name: str = "Mizan Cross-Sectional Alpha"
    feature_schema_id: str = FEATURE_SCHEMA_ID_V3
    feature_schema_version: int = FEATURE_SCHEMA_VERSION_V3
    feature_names: tuple[str, ...] = FEATURE_NAMES_V3
    l2_penalty: str = "1.0"
    score_threshold: str = "0.0"
    label_horizon_sessions: int = 11
    version: str = "1.0.0"
    model_type: str = "mizan_cross_sectional_ridge"
    description: str = (
        "Mīzān — Flagship QuantOS pooled cross-sectional equity ranking and alpha model"
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ModelingError(
                ModelingFailureCode.INVALID_PARAMETER, "candidate_id cannot be empty"
            )
        validate_mizan_model_only(self.candidate_id, self.model_id)
        if not self.model_id:
            raise ModelingError(ModelingFailureCode.INVALID_PARAMETER, "model_id cannot be empty")
        if not self.feature_names:
            raise ModelingError(
                ModelingFailureCode.INVALID_PARAMETER, "feature_names cannot be empty"
            )
        _canonical_decimal_str(self.l2_penalty, "l2_penalty")
        _canonical_decimal_str(self.score_threshold, "score_threshold")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "description": self.description,
            "feature_names": list(self.feature_names),
            "feature_schema_id": self.feature_schema_id,
            "feature_schema_version": self.feature_schema_version,
            "l2_penalty": self.l2_penalty,
            "label_horizon_sessions": self.label_horizon_sessions,
            "metadata": dict(self.metadata),
            "model_id": self.model_id,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "score_threshold": self.score_threshold,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MizanConfig:
        return cls(
            candidate_id=str(data.get("candidate_id", "cand_mizan_v1")),
            model_id=str(data.get("model_id", "mizan-v1")),
            model_name=str(data.get("model_name", "Mizan Cross-Sectional Alpha")),
            feature_schema_id=str(data.get("feature_schema_id", FEATURE_SCHEMA_ID_V3)),
            feature_schema_version=int(
                data.get("feature_schema_version", FEATURE_SCHEMA_VERSION_V3)
            ),
            feature_names=tuple(str(f) for f in data.get("feature_names", FEATURE_NAMES_V3)),
            l2_penalty=_canonical_decimal_str(data.get("l2_penalty", "1.0"), "l2_penalty"),
            score_threshold=_canonical_decimal_str(
                data.get("score_threshold", "0.0"), "score_threshold"
            ),
            label_horizon_sessions=int(data.get("label_horizon_sessions", 11)),
            version=str(data.get("version", "1.0.0")),
            model_type=str(data.get("model_type", "mizan_cross_sectional_ridge")),
            description=str(data.get("description", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class MizanWeights:
    """Fitted coefficients and intercept for Mizan."""

    intercept: str
    coefficients: tuple[str, ...]
    feature_names: tuple[str, ...] = FEATURE_NAMES_V3
    weights_hash: str = ""

    def __post_init__(self) -> None:
        canon_intercept = _canonical_decimal_str(self.intercept, "intercept")
        canon_coeffs = tuple(
            _canonical_decimal_str(c, f"coefficients[{i}]") for i, c in enumerate(self.coefficients)
        )
        canon_names = tuple(str(n) for n in self.feature_names)

        if len(canon_coeffs) != len(canon_names):
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                f"Coefficient length ({len(canon_coeffs)}) does not match feature_names length ({len(canon_names)})",
            )

        payload = {
            "coefficient_names": list(canon_names),
            "coefficients": list(canon_coeffs),
            "intercept": canon_intercept,
        }
        computed_hash = canonical_sha256(payload)

        object.__setattr__(self, "intercept", canon_intercept)
        object.__setattr__(self, "coefficients", canon_coeffs)
        object.__setattr__(self, "feature_names", canon_names)
        object.__setattr__(self, "weights_hash", computed_hash)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coefficient_names": list(self.feature_names),
            "coefficients": list(self.coefficients),
            "intercept": self.intercept,
            "weights_hash": self.weights_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MizanWeights:
        names = tuple(str(n) for n in data.get("coefficient_names", FEATURE_NAMES_V3))
        coeffs = tuple(str(c) for c in data.get("coefficients", []))
        intercept = str(data.get("intercept", "0.0"))
        return cls(intercept=intercept, coefficients=coeffs, feature_names=names)


@dataclass(frozen=True, slots=True)
class MizanPreprocessorConfig:
    """Standardization parameters (means and scales) for feature transformation."""

    means: tuple[str, ...]
    scales: tuple[str, ...]
    feature_names: tuple[str, ...] = FEATURE_NAMES_V3
    zero_variance_features: tuple[str, ...] = ()
    preprocessor_hash: str = ""

    def __post_init__(self) -> None:
        canon_names = tuple(str(n) for n in self.feature_names)
        canon_means = tuple(
            _canonical_decimal_str(m, f"means[{i}]") for i, m in enumerate(self.means)
        )
        canon_scales = tuple(
            _canonical_decimal_str(s, f"scales[{i}]") for i, s in enumerate(self.scales)
        )
        canon_zv = tuple(sorted(str(zv) for zv in self.zero_variance_features))

        if len(canon_means) != len(canon_names):
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                f"Means length ({len(canon_means)}) != feature names length ({len(canon_names)})",
            )
        if len(canon_scales) != len(canon_names):
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                f"Scales length ({len(canon_scales)}) != feature names length ({len(canon_names)})",
            )

        payload = {
            "feature_names": list(canon_names),
            "means": list(canon_means),
            "scales": list(canon_scales),
            "zero_variance_features": list(canon_zv),
        }
        computed_hash = canonical_sha256(payload)

        object.__setattr__(self, "feature_names", canon_names)
        object.__setattr__(self, "means", canon_means)
        object.__setattr__(self, "scales", canon_scales)
        object.__setattr__(self, "zero_variance_features", canon_zv)
        object.__setattr__(self, "preprocessor_hash", computed_hash)

    def standardize(self, raw_features: Mapping[str, float | Decimal | str]) -> dict[str, Decimal]:
        """Standardize raw feature values: (x - mean) / scale."""
        standardized: dict[str, Decimal] = {}
        for idx, name in enumerate(self.feature_names):
            val_raw = raw_features.get(name, Decimal("0.0"))
            try:
                val = Decimal(str(val_raw))
            except (InvalidOperation, TypeError, ValueError):
                val = Decimal("0.0")

            if name in self.zero_variance_features:
                standardized[name] = Decimal("0.0")
                continue

            mean = Decimal(self.means[idx])
            scale = Decimal(self.scales[idx])
            if scale == Decimal("0.0"):
                standardized[name] = Decimal("0.0")
            else:
                standardized[name] = (val - mean) / scale
        return standardized

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_names": list(self.feature_names),
            "means": list(self.means),
            "preprocessor_hash": self.preprocessor_hash,
            "scales": list(self.scales),
            "zero_variance_features": list(self.zero_variance_features),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MizanPreprocessorConfig:
        names = tuple(str(n) for n in data.get("feature_names", FEATURE_NAMES_V3))
        means = tuple(str(m) for m in data.get("means", []))
        scales = tuple(str(s) for s in data.get("scales", []))
        zv = tuple(str(z) for z in data.get("zero_variance_features", []))
        return cls(means=means, scales=scales, feature_names=names, zero_variance_features=zv)


@dataclass(frozen=True, slots=True)
class MizanModelCard:
    """Rich governance metadata and evaluation card for Mizan."""

    model_id: str
    candidate_id: str
    model_name: str = "Mizan Flagship Alpha"
    version: str = "1.0.0"
    author: str = "QuantOS Research Team"
    license: str = "Proprietary / QuantOS Governance Contract"
    created_at: str = field(default_factory=lambda: utc_text(datetime.now(UTC)))
    tags: tuple[str, ...] = ("quantos", "mizan", "cross-sectional", "alpha", "ridge", "equities")
    metrics: dict[str, str] = field(default_factory=dict)
    monitoring_limits: dict[str, str] = field(
        default_factory=lambda: {
            "max_drawdown_limit": "0.15",
            "min_hit_rate": "0.48",
            "staleness_bars_limit": "5",
        }
    )
    limitations: tuple[str, ...] = (
        "Designed strictly for cross-sectional ranking across liquid equity universes.",
        "Requires point-in-time clean feature inputs with zero lookahead.",
        "Must be executed under effective exchange cost models (STT, brokerage, exchange fees).",
    )
    halt_and_rollback_policy: str = (
        "Halt immediately if rolling Sharpe breaches -1.5 or data freshness budget expires."
    )
    verdict: str = "RESEARCH_ONLY"
    model_card_hash: str = field(init=False)

    def __post_init__(self) -> None:
        payload = {
            "author": self.author,
            "candidate_id": self.candidate_id,
            "created_at": self.created_at,
            "halt_and_rollback_policy": self.halt_and_rollback_policy,
            "license": self.license,
            "limitations": list(self.limitations),
            "metrics": dict(self.metrics),
            "model_id": self.model_id,
            "model_name": self.model_name,
            "monitoring_limits": dict(self.monitoring_limits),
            "tags": list(self.tags),
            "verdict": self.verdict,
            "version": self.version,
        }
        object.__setattr__(self, "model_card_hash", canonical_sha256(payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "author": self.author,
            "candidate_id": self.candidate_id,
            "created_at": self.created_at,
            "halt_and_rollback_policy": self.halt_and_rollback_policy,
            "license": self.license,
            "limitations": list(self.limitations),
            "metrics": dict(self.metrics),
            "model_card_hash": self.model_card_hash,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "monitoring_limits": dict(self.monitoring_limits),
            "tags": list(self.tags),
            "verdict": self.verdict,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MizanModelCard:
        return cls(
            model_id=str(data.get("model_id", "mizan-v1")),
            candidate_id=str(data.get("candidate_id", "cand_mizan_v1")),
            model_name=str(data.get("model_name", "Mizan Flagship Alpha")),
            version=str(data.get("version", "1.0.0")),
            author=str(data.get("author", "QuantOS Research Team")),
            license=str(data.get("license", "Proprietary / QuantOS Governance Contract")),
            created_at=str(data.get("created_at", utc_text(datetime.now(UTC)))),
            tags=tuple(str(t) for t in data.get("tags", ())),
            metrics=dict(data.get("metrics", {})),
            monitoring_limits=dict(data.get("monitoring_limits", {})),
            limitations=tuple(str(item) for item in data.get("limitations", ())),
            halt_and_rollback_policy=str(data.get("halt_and_rollback_policy", "")),
            verdict=str(data.get("verdict", "RESEARCH_ONLY")),
        )


class MizanModel:
    """The unified, standalone Mizan Machine Learning Model.

    Supports prediction, cross-sectional ranking, serialization (`save_pretrained`),
    deserialization (`from_pretrained`), and package export/import.
    """

    def __init__(
        self,
        config: MizanConfig,
        weights: MizanWeights,
        preprocessor: MizanPreprocessorConfig,
        model_card: MizanModelCard | None = None,
    ) -> None:
        self.config = config
        self.weights = weights
        self.preprocessor = preprocessor
        self.model_card = model_card or MizanModelCard(
            model_id=config.model_id,
            candidate_id=config.candidate_id,
            model_name=config.model_name,
            version=config.version,
        )
        self._intercept_dec = Decimal(self.weights.intercept)
        self._coeffs_dec = tuple(Decimal(c) for c in self.weights.coefficients)
        self._threshold_dec = Decimal(self.config.score_threshold)

    @property
    def model_id(self) -> str:
        return self.config.model_id

    @property
    def candidate_id(self) -> str:
        return self.config.candidate_id

    def predict_score(self, features: Mapping[str, float | Decimal | str]) -> float:
        """Score a single feature vector: dot(coeffs, standardized_x) + intercept."""
        std = self.preprocessor.standardize(features)
        total = self._intercept_dec
        for idx, name in enumerate(self.config.feature_names):
            total += self._coeffs_dec[idx] * std[name]
        return float(total)

    def predict_scores(
        self, universe_features: Mapping[str, Mapping[str, float | Decimal | str]]
    ) -> dict[str, float]:
        """Score multiple instruments across the universe."""
        return {
            symbol: self.predict_score(features) for symbol, features in universe_features.items()
        }

    def rank_universe(
        self,
        universe_features: Mapping[str, Mapping[str, float | Decimal | str]],
        top_n: int | None = None,
    ) -> list[tuple[str, float]]:
        """Rank universe instruments by Mizan predictive score, descending."""
        scores = self.predict_scores(universe_features)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if top_n is not None and top_n > 0:
            return ranked[:top_n]
        return ranked

    def to_dict(self) -> dict[str, Any]:
        """Convert full model structure to a serializable dictionary."""
        return {
            "config": self.config.to_dict(),
            "model_card": self.model_card.to_dict(),
            "preprocessor": self.preprocessor.to_dict(),
            "weights": self.weights.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MizanModel:
        """Instantiate MizanModel from structured dictionary."""
        config = MizanConfig.from_dict(data.get("config", {}))
        weights = MizanWeights.from_dict(data.get("weights", {}))
        preprocessor = MizanPreprocessorConfig.from_dict(data.get("preprocessor", {}))
        card_data = data.get("model_card")
        model_card = MizanModelCard.from_dict(card_data) if card_data else None
        return cls(
            config=config,
            weights=weights,
            preprocessor=preprocessor,
            model_card=model_card,
        )

    def save_pretrained(self, save_directory: str | Path, package_zip: bool = False) -> Path:
        """Export model in standard Hugging Face-style format.

        Writes:
        - `config.json`
        - `model_card.json`
        - `preprocessor_config.json`
        - `weights.json`
        - `checksums.json`

        If `package_zip` is True, bundles them into a `.zip` archive.
        """
        save_path = Path(save_directory)
        if package_zip or save_path.suffix == ".zip":
            zip_target = save_path if save_path.suffix == ".zip" else save_path.with_suffix(".zip")
            zip_target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                self._write_files_to_dir(tmp_path)
                with zipfile.ZipFile(zip_target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for file_path in tmp_path.iterdir():
                        if file_path.is_file():
                            zf.write(file_path, arcname=file_path.name)
            return zip_target

        save_path.mkdir(parents=True, exist_ok=True)
        self._write_files_to_dir(save_path)
        return save_path

    def _write_files_to_dir(self, directory: Path) -> dict[str, str]:
        files_data = {
            "config.json": json.dumps(self.config.to_dict(), indent=2, sort_keys=True),
            "model_card.json": json.dumps(self.model_card.to_dict(), indent=2, sort_keys=True),
            "preprocessor_config.json": json.dumps(
                self.preprocessor.to_dict(), indent=2, sort_keys=True
            ),
            "weights.json": json.dumps(self.weights.to_dict(), indent=2, sort_keys=True),
        }
        checksums: dict[str, str] = {}
        for filename, content in files_data.items():
            file_bytes = content.encode("utf-8")
            (directory / filename).write_bytes(file_bytes)
            checksums[filename] = canonical_sha256(json.loads(content))

        checksum_bytes = json.dumps(checksums, indent=2, sort_keys=True).encode("utf-8")
        (directory / "checksums.json").write_bytes(checksum_bytes)
        return checksums

    @classmethod
    def from_pretrained(cls, pretrained_model_name_or_path: str | Path) -> MizanModel:
        """Load a MizanModel from a directory, `.zip` archive, or package file."""
        model_path = Path(pretrained_model_name_or_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model path does not exist: {model_path}")

        if model_path.is_file() and (model_path.suffix == ".zip" or zipfile.is_zipfile(model_path)):
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(model_path, "r") as zf:
                    zf.extractall(tmp_dir)
                return cls._load_from_directory(Path(tmp_dir))

        if model_path.is_dir():
            return cls._load_from_directory(model_path)

        raise ValueError(
            f"Unsupported model path '{model_path}'. Must be a directory or a .zip archive."
        )

    @classmethod
    def _load_from_directory(cls, directory: Path) -> MizanModel:
        config_file = directory / "config.json"
        weights_file = directory / "weights.json"
        prep_file = directory / "preprocessor_config.json"
        card_file = directory / "model_card.json"

        if not config_file.exists():
            raise FileNotFoundError(f"Missing config.json in {directory}")
        if not weights_file.exists():
            raise FileNotFoundError(f"Missing weights.json in {directory}")
        if not prep_file.exists():
            raise FileNotFoundError(f"Missing preprocessor_config.json in {directory}")

        config_data = json.loads(config_file.read_text(encoding="utf-8"))
        weights_data = json.loads(weights_file.read_text(encoding="utf-8"))
        prep_data = json.loads(prep_file.read_text(encoding="utf-8"))
        card_data = (
            json.loads(card_file.read_text(encoding="utf-8")) if card_file.exists() else None
        )

        config = MizanConfig.from_dict(config_data)
        weights = MizanWeights.from_dict(weights_data)
        preprocessor = MizanPreprocessorConfig.from_dict(prep_data)
        model_card = MizanModelCard.from_dict(card_data) if card_data else None

        return cls(
            config=config,
            weights=weights,
            preprocessor=preprocessor,
            model_card=model_card,
        )

    @classmethod
    def default_model(cls) -> MizanModel:
        """Return the default Mizan-V1 weights.

        **These are RESEARCH_ONLY weights and are not certified.** They are the coefficients
        published by `model_1f936eadcb8d44154f28af13` (`trial_mizan_h11_002`), whose own evidence
        records `verdict=RESEARCH_ONLY`, a deflated Sharpe of 0.175990 against a 0.95 gate, a RIDGE
        Sharpe of -0.410755, and a max drawdown of 0.732650. The returned card carries that verdict.

        Nothing here enforces the verdict -- it is carried as data. Enforcement lives at the
        execution boundary, so this model is legitimate for research, packaging and backtesting and
        is refused for execution.
        """
        config = MizanConfig(
            candidate_id="cand_mizan_v1",
            model_id="mizan-v1",
            model_name="Mizan Flagship Alpha (NSE 50)",
            feature_schema_id=FEATURE_SCHEMA_ID_V3,
            feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
            feature_names=FEATURE_NAMES_V3,
            l2_penalty="1.0",
            score_threshold="0.071454840454",
            label_horizon_sessions=11,
            version="1.0.0",
            description="Mizan Flagship pooled cross-sectional alpha ranking model",
        )
        # Default calibrated weights from historical governed NIFTY pooled run
        coeffs = (
            "0.002853151507",
            "0.011861138955",
            "0.036290611825",
            "-0.041717626469",
            "0.027193955727",
            "0.009337674077",
            "0.006008442147",
            "-0.048937728253",
            "0.005705535699",
            "-0.002151349763",
            "0.049350462433",
            "-0.001828738324",
            "-0.030790687336",
            "-0.018811607945",
            "-0.005078895093",
        )
        means = (
            "0.000829065946974581",
            "0.004152037775347756",
            "0.017460113233264467",
            "0.016370868902507301",
            "0.01596794593231152",
            "0.026933785179233099",
            "0.007381960751705787",
            "0.01768106924441536",
            "0.131564461060446728",
            "-0.031665406399737155",
            "0.168489441860465116",
            "0.005700474755023256",
            "0.002810617611302326",
            "0.016702818779247161",
            "0.006850415371412655",
        )
        scales = (
            "0.019877725275523217",
            "0.044428962578434506",
            "0.092633273103265554",
            "0.010422751655302223",
            "0.010490704866701275",
            "0.12234317000623059",
            "0.053514198218262445",
            "0.083295052157258993",
            "2.078771990374827821",
            "0.540336963606607485",
            "0.066611430649527806",
            "0.11928921745385032",
            "0.023053931315940579",
            "0.261085947335330571",
            "0.296850186159355894",
        )
        weights = MizanWeights(
            intercept="0.071454840454",
            coefficients=coeffs,
            feature_names=FEATURE_NAMES_V3,
        )
        preprocessor = MizanPreprocessorConfig(
            means=means,
            scales=scales,
            feature_names=FEATURE_NAMES_V3,
        )
        card = MizanModelCard(
            model_id="mizan-v1",
            candidate_id="cand_mizan_v1",
            model_name="Mizan Flagship Alpha (NSE 50)",
            version="1.0.0",
            metrics={
                "accuracy": "0.4920",
                "annualized_volatility": "0.5518",
                "deflated_sharpe_ratio": "0.1760",
                "sharpe_ratio": "-0.4108",
                "total_return": "-0.3157",
            },
        )
        return cls(
            config=config,
            weights=weights,
            preprocessor=preprocessor,
            model_card=card,
        )

    @classmethod
    def sprint_50k_model(cls) -> MizanModel:
        """Constructs the high-momentum 50K Sprint profile for concentrated pure-stock swing trading."""
        config = MizanConfig(
            candidate_id="cand_mizan_50k_sprint",
            model_id="mizan-50k-sprint",
            model_name="Mizan 50K Momentum Sprint",
            feature_schema_id=FEATURE_SCHEMA_ID_V3,
            feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
            feature_names=FEATURE_NAMES_V3,
            l2_penalty="0.5",
            score_threshold="0.050000000000",
            label_horizon_sessions=5,
            version="1.0.0",
            description="Mizan concentrated high-conviction 50K equity momentum swing model (Pure Stocks)",
            metadata={"target_capital_inr": 50000, "max_positions": 3, "instrument": "CASH_EQUITY"},
        )
        coeffs = (
            "0.015000000000",
            "0.035000000000",
            "0.045000000000",
            "-0.020000000000",
            "0.015000000000",
            "0.025000000000",
            "0.020000000000",
            "-0.010000000000",
            "0.030000000000",
            "0.020000000000",
            "-0.015000000000",
            "-0.005000000000",
            "0.010000000000",
            "0.050000000000",
            "0.035000000000",
        )
        means = (
            "0.000829065946974581",
            "0.004152037775347756",
            "0.017460113233264467",
            "0.016370868902507301",
            "0.01596794593231152",
            "0.026933785179233099",
            "0.007381960751705787",
            "0.01768106924441536",
            "0.131564461060446728",
            "-0.031665406399737155",
            "0.168489441860465116",
            "0.005700474755023256",
            "0.002810617611302326",
            "0.016702818779247161",
            "0.006850415371412655",
        )
        scales = (
            "0.019877725275523217",
            "0.044428962578434506",
            "0.092633273103265554",
            "0.010422751655302223",
            "0.010490704866701275",
            "0.12234317000623059",
            "0.053514198218262445",
            "0.083295052157258993",
            "2.078771990374827821",
            "0.540336963606607485",
            "0.066611430649527806",
            "0.11928921745385032",
            "0.023053931315940579",
            "0.261085947335330571",
            "0.296850186159355894",
        )
        weights = MizanWeights(
            intercept="0.050000000000",
            coefficients=coeffs,
            feature_names=FEATURE_NAMES_V3,
        )
        preprocessor = MizanPreprocessorConfig(
            means=means,
            scales=scales,
            feature_names=FEATURE_NAMES_V3,
        )
        card = MizanModelCard(
            model_id="mizan-50k-sprint",
            candidate_id="cand_mizan_50k_sprint",
            model_name="Mizan 50K Momentum Sprint",
            version="1.0.0",
            metrics={
                "target_capital_inr": "50000",
                "max_drawdown_limit": "0.025",
                "strategy": "CONCENTRATED_EQUITY_SWING_BREAKOUT",
            },
        )
        return cls(
            config=config,
            weights=weights,
            preprocessor=preprocessor,
            model_card=card,
        )
