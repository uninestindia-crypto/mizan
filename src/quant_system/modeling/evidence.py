"""Immutable evidence adapters for derived feature and label datasets."""

from __future__ import annotations

from quant_system.evidence import EvidenceDraft, EvidenceResourceType
from quant_system.modeling.rows import (
    FEATURE_ROW_SCHEMA,
    LABEL_ROW_SCHEMA,
    FeatureDatasetV1,
    LabelDatasetV1,
    require_feature_dataset_identity,
    require_label_dataset_identity,
)

FEATURE_TOTAL_ORDER = ("candidate_id", "provider_instrument_id", "decision_at")
LABEL_TOTAL_ORDER = ("candidate_id", "symbol", "decision_at")


def draft_from_feature_dataset(dataset: FeatureDatasetV1) -> EvidenceDraft:
    require_feature_dataset_identity(dataset)
    return EvidenceDraft(
        resource_type=EvidenceResourceType.DATASET,
        resource_id=dataset.dataset_id,
        schema_id=FEATURE_ROW_SCHEMA,
        schema_version=1,
        metadata=dataset.metadata_dict(),
        records=tuple(row.to_canonical_dict() for row in dataset.rows),
        total_order=FEATURE_TOTAL_ORDER,
    )


def draft_from_label_dataset(dataset: LabelDatasetV1) -> EvidenceDraft:
    require_label_dataset_identity(dataset)
    return EvidenceDraft(
        resource_type=EvidenceResourceType.DATASET,
        resource_id=dataset.dataset_id,
        schema_id=LABEL_ROW_SCHEMA,
        schema_version=1,
        metadata=dataset.metadata_dict(),
        records=tuple(row.to_canonical_dict() for row in dataset.rows),
        total_order=LABEL_TOTAL_ORDER,
    )
