"""One-fold governed ridge evaluation with timing-aligned baselines and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from quant_system.analytics.errors import MultiplicityError
from quant_system.analytics.multiplicity import OverfittingDiagnostics
from quant_system.data.market_data_evidence import canonical_sha256, decimal_text
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.folds import PartitionedFoldV1
from quant_system.modeling.metrics import (
    STRATEGY_ORDER_V1,
    StrategyFoldReportV1,
    build_strategy_report,
    metric_decimal,
)
from quant_system.modeling.preprocessing import (
    StandardizationStateV1,
    fit_standardization,
    transform_feature_rows,
)
from quant_system.modeling.ridge import (
    RidgeFittedStateV1,
    fit_ridge_classifier,
    predict_ridge_scores,
)
from quant_system.modeling.rows import (
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V3,
    FeatureDatasetV1,
    FeatureRowV1,
    LabelDatasetV1,
    LabelRowV1,
    require_feature_dataset_identity,
    require_label_dataset_identity,
)
from quant_system.modeling.trials import RidgeTrialStartV1, TrialRegistryV1


@dataclass(frozen=True, slots=True)
class RidgeFoldEvaluationV1:
    trial_id: str
    candidate_id: str
    fold_spec_hash: str
    preprocessing: StandardizationStateV1
    fitted_state: RidgeFittedStateV1
    strategy_reports: tuple[StrategyFoldReportV1, ...]
    multiplicity_count: int
    deflated_sharpe_ratio: str
    evaluation_hash: str = field(init=False)
    model_id: str = field(init=False)

    def __post_init__(self) -> None:
        if tuple(report.strategy_id for report in self.strategy_reports) != STRATEGY_ORDER_V1:
            raise ValueError("evaluation must contain ridge and four baselines in contract order")
        if self.multiplicity_count < 1:
            raise ValueError("evaluation multiplicity must be positive")
        _require_decimal_text(self.deflated_sharpe_ratio, "deflated_sharpe_ratio")
        digest = canonical_sha256(self._unsigned_dict())
        object.__setattr__(self, "evaluation_hash", digest)
        object.__setattr__(self, "model_id", f"model_{digest[:24]}")

    @property
    def ridge_report(self) -> StrategyFoldReportV1:
        return self.strategy_reports[0]

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["evaluation_hash"] = self.evaluation_hash
        payload["model_id"] = self.model_id
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "deflated_sharpe_ratio": self.deflated_sharpe_ratio,
            "fitted_state": self.fitted_state.to_canonical_dict(),
            "fold_spec_hash": self.fold_spec_hash,
            "multiplicity_count": self.multiplicity_count,
            "preprocessing": self.preprocessing.to_canonical_dict(),
            "schema_id": "quantos.ridge_fold_evaluation",
            "schema_version": 1,
            "strategy_reports": [report.to_canonical_dict() for report in self.strategy_reports],
            "trial_id": self.trial_id,
            "verdict": "RESEARCH_ONLY",
        }


def evaluate_governed_ridge_fold(
    start: RidgeTrialStartV1,
    registry: TrialRegistryV1,
    feature_dataset: FeatureDatasetV1,
    label_dataset: LabelDatasetV1,
    fold: PartitionedFoldV1,
) -> RidgeFoldEvaluationV1:
    """Evaluate one governed fold and deflate its Sharpe against ``registry``.

    ``registry`` is the caller's attempt count and is NOT an authority. This is the pure
    building block; the governed entry point is ``run_persisted_ridge_trial``, which loads the
    registry from the immutable catalog itself and binds the published multiplicity to the
    trial's ordinal. Calling this directly with a fabricated registry produces a number that
    is honest about its own inputs but says nothing about a real campaign, so never quote its
    ``deflated_sharpe_ratio`` without the ``multiplicity_count`` beside it.
    """
    fold_hash = _validate_training_inputs(start, registry, feature_dataset, label_dataset, fold)
    feature_index: dict[tuple[str, str, datetime], FeatureRowV1] = {}
    for row in feature_dataset.rows:
        key = (row.candidate_id, row.symbol, row.decision_at)
        if key in feature_index:
            raise ModelingError(
                ModelingFailureCode.DATASET_INTEGRITY_INVALID,
                "two feature rows share one symbol and decision time; instrument identity is "
                "ambiguous and the fit would silently use whichever row sorted last",
                offending_record_key=row.record_key,
            )
        feature_index[key] = row
    training_features = tuple(feature_index[_label_key(row)] for row in fold.train_rows)
    validation_features = tuple(feature_index[_label_key(row)] for row in fold.validation_rows)
    preprocessing = fit_standardization(training_features)
    transformed_training = transform_feature_rows(training_features, preprocessing)
    transformed_validation = transform_feature_rows(validation_features, preprocessing)
    fitted = fit_ridge_classifier(
        start,
        preprocessing,
        transformed_training,
        tuple(row.target for row in fold.train_rows),
    )
    scores = predict_ridge_scores(fitted, transformed_validation)
    threshold = Decimal(start.score_threshold)
    candidate_targets = tuple("UP" if Decimal(score) > threshold else "DOWN" for score in scores)
    target_sets = {
        "RIDGE": candidate_targets,
        "NO_TRADE": tuple("DOWN" for _ in fold.validation_rows),
        "BUY_AND_HOLD": tuple("UP" for _ in fold.validation_rows),
        "PREVIOUS_SIGN": _previous_matured_targets(label_dataset.rows, fold.validation_rows),
        "EQUITY_DUAL_MOMENTUM": tuple(
            "UP"
            if Decimal(row.features[_momentum_feature(row)]) > 0
            and Decimal(row.features["sma_20_distance"]) > 0
            else "DOWN"
            for row in validation_features
        ),
    }
    reports = tuple(
        build_strategy_report(
            strategy_id,
            fold.validation_rows,
            target_sets[strategy_id],
            scores if strategy_id == "RIDGE" else None,
        )
        for strategy_id in STRATEGY_ORDER_V1
    )
    return RidgeFoldEvaluationV1(
        trial_id=start.trial_id,
        candidate_id=start.candidate_id,
        fold_spec_hash=fold_hash,
        preprocessing=preprocessing,
        fitted_state=fitted,
        strategy_reports=reports,
        multiplicity_count=registry.multiplicity_count,
        deflated_sharpe_ratio=deflate_ridge_report(
            reports[0],
            multiplicity_count=registry.multiplicity_count,
        ),
    )


def deflate_ridge_report(
    ridge_report: StrategyFoldReportV1,
    *,
    multiplicity_count: int,
) -> str:
    """Deflate one fold's ridge Sharpe against a given attempt count.

    The value published with a trial deflates against that trial's own ordinal, because the
    campaign is still open when the evidence is written and immutable evidence cannot be
    rewritten later. Readers who need the complete-campaign number call this again with the
    final attempt count; see ``campaign_deflated_sharpe_ratios``.
    """
    if multiplicity_count < 1:
        raise ModelingError(
            ModelingFailureCode.MULTIPLICITY_INVALID,
            "deflation requires a positive attempt count",
        )
    period_returns = _portfolio_period_returns(ridge_report)
    skewness, kurtosis = _return_moments(period_returns)
    try:
        dsr = OverfittingDiagnostics.deflated_sharpe_ratio(
            estimated_sharpe=float(Decimal(ridge_report.metrics.sharpe_ratio)),
            num_trials=multiplicity_count,
            sample_length_bars=len(period_returns),
            skewness=skewness,
            kurtosis=kurtosis,
        )
    except MultiplicityError as error:
        raise ModelingError(
            ModelingFailureCode.MOMENT_CONSTRAINT_INVALID,
            "portfolio return moments violate Pearson's skewness-kurtosis constraint",
        ) from error
    return metric_decimal(Decimal(str(dsr)))


_MOMENTUM_FEATURE_BY_SCHEMA = {
    (FEATURE_SCHEMA_ID_V3, FEATURE_SCHEMA_VERSION_V3): "return_21",
}


def _momentum_feature(row: FeatureRowV1) -> str:
    """The medium-horizon return the dual-momentum baseline reads, per feature schema.

    The baseline exists to be a fair comparator, so it must be computed from whichever family the
    candidate itself was trained on rather than from a column name that only the six-feature family
    happens to have.
    """
    return _MOMENTUM_FEATURE_BY_SCHEMA.get(
        (row.feature_schema_id, row.feature_schema_version), "return_10"
    )


def fold_spec_hash(fold: PartitionedFoldV1) -> str:
    return canonical_sha256(fold.spec.to_canonical_dict())


def _validate_training_inputs(
    start: RidgeTrialStartV1,
    registry: TrialRegistryV1,
    feature_dataset: FeatureDatasetV1,
    label_dataset: LabelDatasetV1,
    fold: PartitionedFoldV1,
) -> str:
    require_feature_dataset_identity(feature_dataset)
    require_label_dataset_identity(label_dataset)
    registry.require_ready_for_evaluation(start)
    current_fold_hash = fold_spec_hash(fold)
    if start.fold_spec_hashes != (current_fold_hash,):
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            "trial fold hash does not bind the supplied partition",
        )
    if (
        start.candidate_id != feature_dataset.candidate_id
        or start.candidate_id != label_dataset.candidate_id
        or start.dataset_id != label_dataset.dataset_id
        or start.dataset_hash != label_dataset.dataset_hash
        or start.universe_policy_hash != feature_dataset.universe_authority_hash
        or start.feature_schema_id != feature_dataset.feature_schema_id
        or start.feature_schema_version != feature_dataset.feature_schema_version
        or label_dataset.feature_dataset_id != feature_dataset.dataset_id
        or label_dataset.feature_dataset_hash != feature_dataset.dataset_hash
    ):
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            "trial, feature, label, and universe identities do not agree",
        )
    _validate_fold_integrity(label_dataset, fold)
    feature_keys = {(row.candidate_id, row.symbol, row.decision_at) for row in feature_dataset.rows}
    for row in (*fold.train_rows, *fold.validation_rows):
        if _label_key(row) not in feature_keys:
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "fold label has no exact feature row",
                offending_record_key=row.record_key,
            )
    return current_fold_hash


def _validate_fold_integrity(
    label_dataset: LabelDatasetV1,
    fold: PartitionedFoldV1,
) -> None:
    dataset_rows = {row.record_key: row for row in label_dataset.rows}
    for row in (*fold.train_rows, *fold.validation_rows):
        if dataset_rows.get(row.record_key) != row:
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "fold row is not an exact member of the label dataset",
                offending_record_key=row.record_key,
            )
    if {row.record_key for row in fold.train_rows} & {
        row.record_key for row in fold.validation_rows
    }:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "training and validation rows overlap",
        )
    if (
        fold.spec.train_hash != _label_rows_hash(fold.train_rows)
        or fold.spec.validation_hash != _label_rows_hash(fold.validation_rows)
        or fold.spec.train_row_count != len(fold.train_rows)
        or fold.spec.validation_row_count != len(fold.validation_rows)
    ):
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "fold evidence does not match its rows",
        )
    if (
        dict(fold.spec.train_class_balance) != _class_balance(fold.train_rows)
        or dict(fold.spec.validation_class_balance) != _class_balance(fold.validation_rows)
        or fold.spec.train_start != fold.train_rows[0].decision_at
        or fold.spec.train_end != fold.train_rows[-1].decision_at
        or fold.spec.validation_start != fold.validation_rows[0].decision_at
        or fold.spec.validation_end != fold.validation_rows[-1].decision_at
        or fold.spec.purge_end != fold.spec.validation_start
        or fold.spec.label_horizon_sessions != label_dataset.label_horizon_sessions
        or fold.spec.embargo_sessions < fold.spec.label_horizon_sessions
    ):
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "fold summary does not match its retained rows and timing contract",
        )
    _validate_removed_rows(label_dataset.rows, fold)


def _validate_removed_rows(
    dataset_rows: tuple[LabelRowV1, ...],
    fold: PartitionedFoldV1,
) -> None:
    train_keys = {row.record_key for row in fold.train_rows}
    validation_keys = {row.record_key for row in fold.validation_rows}
    purged_keys = fold.purged_record_keys
    embargoed_keys = fold.embargoed_record_keys
    removed_keys = (*purged_keys, *embargoed_keys)
    if (
        len(set(removed_keys)) != len(removed_keys)
        or set(removed_keys) & (train_keys | validation_keys)
        or any(key not in {row.record_key for row in dataset_rows} for key in removed_keys)
    ):
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "fold removal evidence is duplicated, unknown, or retained",
        )
    prior_rows = tuple(row for row in dataset_rows if row.decision_at < fold.spec.validation_start)
    in_window = tuple(
        row
        for row in dataset_rows
        if fold.spec.validation_start <= row.decision_at <= fold.spec.validation_end
    )
    if {row.record_key for row in prior_rows} != train_keys | set(removed_keys) or {
        row.record_key for row in in_window
    } != validation_keys:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "fold does not account for every label inside its expanding-window boundary",
        )
    for row in fold.train_rows:
        if row.exit_at >= fold.spec.validation_start:
            raise ModelingError(
                ModelingFailureCode.PARTITION_INVALID,
                "training label matures at or after the validation window opens",
                offending_record_key=row.record_key,
            )
    rows_by_key = {row.record_key: row for row in dataset_rows}
    purged_rows = tuple(rows_by_key[key] for key in purged_keys)
    embargoed_rows = tuple(rows_by_key[key] for key in embargoed_keys)
    if any(row.exit_at < fold.spec.validation_start for row in purged_rows):
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "purged rows must overlap the validation boundary",
        )
    if embargoed_rows and (
        any(row.exit_at >= fold.spec.validation_start for row in embargoed_rows)
        or any(row.decision_at <= fold.spec.train_end for row in embargoed_rows)
    ):
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "embargo rows must be the post-training, non-overlapping boundary rows",
        )
    removed = tuple(
        sorted((*purged_rows, *embargoed_rows), key=lambda row: (row.decision_at, row.symbol))
    )
    expected_purge_start = removed[0].decision_at if removed else fold.spec.validation_start
    if fold.spec.purge_start != expected_purge_start:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "fold purge boundary does not match its removed rows",
        )


def _class_balance(rows: tuple[LabelRowV1, ...]) -> dict[str, int]:
    return {
        "DOWN": sum(row.target == "DOWN" for row in rows),
        "UP": sum(row.target == "UP" for row in rows),
    }


def _previous_matured_targets(
    all_rows: tuple[LabelRowV1, ...],
    validation_rows: tuple[LabelRowV1, ...],
) -> tuple[str, ...]:
    targets: list[str] = []
    for current in validation_rows:
        matured = tuple(
            row
            for row in all_rows
            if row.symbol == current.symbol and row.exit_at <= current.decision_at
        )
        targets.append(matured[-1].target if matured else "DOWN")
    return tuple(targets)


def _require_decimal_text(value: str, field_name: str) -> None:
    parsed = Decimal(value)
    if not parsed.is_finite() or decimal_text(parsed) != value:
        raise ValueError(f"{field_name} must be finite canonical decimal text")


def _label_key(row: LabelRowV1) -> tuple[str, str, datetime]:
    return row.candidate_id, row.symbol, row.decision_at


def _label_rows_hash(rows: tuple[LabelRowV1, ...]) -> str:
    return canonical_sha256(
        {
            "records": [row.to_canonical_dict() for row in rows],
            "schema_id": "quantos.fold_label_rows",
            "schema_version": 1,
        }
    )


def _portfolio_period_returns(report: StrategyFoldReportV1) -> tuple[float, ...]:
    grouped: dict[datetime, list[float]] = {}
    for decision in report.decisions:
        grouped.setdefault(decision.decision_at, [])
        if decision.predicted_target == "UP":
            grouped[decision.decision_at].append(float(Decimal(decision.realized_net_return)))
    return tuple(sum(values) / len(values) if values else 0.0 for values in grouped.values())


def _return_moments(values: tuple[float, ...]) -> tuple[float, float]:
    """Return the skewness and kurtosis of a non-degenerate portfolio return series.

    A zero-variance series has no defined Sharpe ratio, so it has no defined deflated Sharpe
    either. Substituting the moments of a normal distribution would publish a probability of
    0.5 for a candidate that never took a position, which ranks it above every genuinely
    losing model, so this fails closed instead.
    """
    if len(values) < 2:
        raise ModelingError(
            ModelingFailureCode.PARTITION_INVALID,
            "deflated Sharpe needs at least two validation decision times",
        )
    mean = sum(values) / len(values)
    deviations = tuple(value - mean for value in values)
    second = sum(value**2 for value in deviations) / len(values)
    if second == 0.0:
        raise ModelingError(
            ModelingFailureCode.DEGENERATE_RETURN_SERIES,
            "portfolio return series has zero variance, so its deflated Sharpe is undefined",
        )
    skewness = (sum(value**3 for value in deviations) / len(values)) / second**1.5
    kurtosis = (sum(value**4 for value in deviations) / len(values)) / second**2
    return skewness, kurtosis
