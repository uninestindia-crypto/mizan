"""Closed canonical row and derived-dataset contracts for governed modeling."""

# craft-allow: god-file - row schemas and their canonical identity checks are one contract.

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from types import MappingProxyType
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text
from quant_system.modeling.errors import ModelingError, ModelingFailureCode

FEATURE_ROW_SCHEMA = "quantos.feature_row"
LABEL_ROW_SCHEMA = "quantos.label_row"
FEATURE_SCHEMA_ID_V1 = "quantos.ridge_technical_six"
FEATURE_SCHEMA_VERSION_V1 = 1
EXECUTION_CONTRACT_VERSION_V1 = "next-open-v1"
LABEL_CONTRACT_VERSION_V1 = "next-open-net-return-v1"
LABEL_HORIZON_SESSIONS_V1 = 2
FEATURE_NAMES_V1 = (
    "return_1",
    "return_5",
    "return_10",
    "rsi_14_centered",
    "sma_20_distance",
    "atr_14_normalized",
)

_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
_CANDIDATE_PATTERN = re.compile(r"cand_[a-z0-9][a-z0-9_-]{0,91}")


@dataclass(frozen=True, slots=True, init=False)
class MoneyV1:
    amount: str
    currency: str

    def __init__(self, amount: Decimal | str, currency: str) -> None:
        canonical_amount = _canonical_decimal(amount, "money amount", nonnegative=True)
        if currency != "INR":
            raise ValueError("Slice 3 money currency must be INR")
        object.__setattr__(self, "amount", canonical_amount)
        object.__setattr__(self, "currency", currency)

    @property
    def amount_decimal(self) -> Decimal:
        return Decimal(self.amount)

    def to_canonical_dict(self) -> dict[str, str]:
        return {"amount": self.amount, "currency": self.currency}


@dataclass(frozen=True, slots=True)
class RoundTripCostQuoteV1:
    provider_instrument_id: str
    symbol: str
    entry_at: datetime
    exit_at: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: int
    component_costs: Mapping[str, MoneyV1]
    cost_rule_ids: tuple[str, ...]
    cost_rule_set_hash: str
    execution_contract_version: str
    quote_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _require_aware(self.entry_at, "entry_at")
        _require_aware(self.exit_at, "exit_at")
        if self.entry_at >= self.exit_at:
            raise ValueError("cost quote entry must precede exit")
        _positive_decimal(self.entry_price, "entry_price")
        _positive_decimal(self.exit_price, "exit_price")
        if self.quantity < 1:
            raise ValueError("cost quote quantity must be positive")
        components = _closed_money_map(self.component_costs)
        object.__setattr__(self, "component_costs", components)
        _require_sorted_unique(self.cost_rule_ids, "cost_rule_ids")
        _require_hash(self.cost_rule_set_hash, "cost_rule_set_hash")
        if self.execution_contract_version != EXECUTION_CONTRACT_VERSION_V1:
            raise ValueError("unsupported execution contract version")
        object.__setattr__(self, "quote_hash", canonical_sha256(self._unsigned_dict()))

    @property
    def entry_price_decimal(self) -> Decimal:
        return self.entry_price

    @property
    def exit_price_decimal(self) -> Decimal:
        return self.exit_price

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["quote_hash"] = self.quote_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "component_costs": {
                name: money.to_canonical_dict() for name, money in self.component_costs.items()
            },
            "cost_rule_ids": list(self.cost_rule_ids),
            "cost_rule_set_hash": self.cost_rule_set_hash,
            "entry_at": utc_text(self.entry_at),
            "entry_price": decimal_text(self.entry_price),
            "execution_contract_version": self.execution_contract_version,
            "exit_at": utc_text(self.exit_at),
            "exit_price": decimal_text(self.exit_price),
            "provider_instrument_id": self.provider_instrument_id,
            "quantity": self.quantity,
            "schema_id": "quantos.round_trip_cost_quote",
            "schema_version": 1,
            "symbol": self.symbol,
        }


@dataclass(frozen=True, slots=True)
class FeatureRowV1:
    candidate_id: str
    dataset_id: str
    dataset_hash: str
    provider_instrument_id: str
    symbol: str
    decision_at: datetime
    information_cutoff_at: datetime
    universe_authority_hash: str
    feature_schema_id: str
    feature_schema_version: int
    features: Mapping[str, str]
    preprocessing_input_hash: str

    def __post_init__(self) -> None:
        _require_candidate_id(self.candidate_id)
        _require_hash(self.dataset_hash, "dataset_hash")
        _require_hash(self.universe_authority_hash, "universe_authority_hash")
        _require_hash(self.preprocessing_input_hash, "preprocessing_input_hash")
        _require_aware(self.decision_at, "decision_at")
        _require_aware(self.information_cutoff_at, "information_cutoff_at")
        if self.information_cutoff_at > self.decision_at:
            raise ValueError("feature information cutoff cannot follow decision time")
        if self.feature_schema_id != FEATURE_SCHEMA_ID_V1:
            raise ValueError("unsupported feature schema")
        if self.feature_schema_version != FEATURE_SCHEMA_VERSION_V1:
            raise ValueError("unsupported feature schema version")
        if tuple(self.features) != FEATURE_NAMES_V1:
            raise ValueError("feature map must use the closed ordered v1 feature family")
        normalized = {
            name: _canonical_decimal(value, f"feature {name}")
            for name, value in self.features.items()
        }
        object.__setattr__(self, "features", MappingProxyType(normalized))

    @property
    def record_key(self) -> str:
        return f"{self.candidate_id}|{self.provider_instrument_id}|{utc_text(self.decision_at)}"

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "dataset_hash": self.dataset_hash,
            "dataset_id": self.dataset_id,
            "decision_at": utc_text(self.decision_at),
            "feature_schema_id": self.feature_schema_id,
            "feature_schema_version": self.feature_schema_version,
            "features": dict(self.features),
            "information_cutoff_at": utc_text(self.information_cutoff_at),
            "preprocessing_input_hash": self.preprocessing_input_hash,
            "provider_instrument_id": self.provider_instrument_id,
            "symbol": self.symbol,
            "universe_authority_hash": self.universe_authority_hash,
        }


@dataclass(frozen=True, slots=True)
class LabelRowV1:
    candidate_id: str
    symbol: str
    decision_at: datetime
    order_at: datetime
    entry_at: datetime
    exit_at: datetime
    entry_price: str
    exit_price: str
    gross_return: str
    component_costs: Mapping[str, MoneyV1]
    net_return: str
    target: str
    cost_rule_ids: tuple[str, ...]
    execution_contract_version: str

    def __post_init__(self) -> None:
        _require_candidate_id(self.candidate_id)
        for name in ("decision_at", "order_at", "entry_at", "exit_at"):
            _require_aware(getattr(self, name), name)
        if not self.decision_at <= self.order_at < self.entry_at < self.exit_at:
            raise ValueError("label chronology is invalid")
        for name in ("entry_price", "exit_price"):
            if Decimal(_canonical_decimal(getattr(self, name), name)) <= 0:
                raise ValueError(f"{name} must be positive")
        _canonical_decimal(self.gross_return, "gross_return")
        _canonical_decimal(self.net_return, "net_return")
        components = _closed_money_map(self.component_costs)
        object.__setattr__(self, "component_costs", components)
        if self.target not in {"UP", "DOWN"}:
            raise ValueError("label target must be UP or DOWN")
        if (Decimal(self.net_return) > 0) != (self.target == "UP"):
            raise ValueError("label target does not match net return")
        _require_sorted_unique(self.cost_rule_ids, "cost_rule_ids")
        if self.execution_contract_version != EXECUTION_CONTRACT_VERSION_V1:
            raise ValueError("unsupported execution contract version")

    @property
    def record_key(self) -> str:
        return f"{self.candidate_id}|{self.symbol}|{utc_text(self.decision_at)}"

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "component_costs": {
                name: money.to_canonical_dict() for name, money in self.component_costs.items()
            },
            "cost_rule_ids": list(self.cost_rule_ids),
            "decision_at": utc_text(self.decision_at),
            "entry_at": utc_text(self.entry_at),
            "entry_price": self.entry_price,
            "execution_contract_version": self.execution_contract_version,
            "exit_at": utc_text(self.exit_at),
            "exit_price": self.exit_price,
            "gross_return": self.gross_return,
            "net_return": self.net_return,
            "order_at": utc_text(self.order_at),
            "symbol": self.symbol,
            "target": self.target,
        }


@dataclass(frozen=True, slots=True)
class FeatureDatasetV1:
    dataset_id: str
    dataset_hash: str
    candidate_id: str
    source_dataset_id: str
    source_dataset_hash: str
    calendar_hash: str
    corporate_action_authority_hash: str
    universe_authority_hash: str
    rows: tuple[FeatureRowV1, ...]

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "calendar_hash": self.calendar_hash,
            "candidate_id": self.candidate_id,
            "corporate_action_authority_hash": self.corporate_action_authority_hash,
            "dataset_hash": self.dataset_hash,
            "dataset_id": self.dataset_id,
            "feature_schema_id": FEATURE_SCHEMA_ID_V1,
            "feature_schema_version": FEATURE_SCHEMA_VERSION_V1,
            "source_dataset_hash": self.source_dataset_hash,
            "source_dataset_id": self.source_dataset_id,
            "universe_authority_hash": self.universe_authority_hash,
        }


@dataclass(frozen=True, slots=True)
class LabelDatasetV1:
    dataset_id: str
    dataset_hash: str
    candidate_id: str
    source_dataset_id: str
    source_dataset_hash: str
    feature_dataset_id: str
    feature_dataset_hash: str
    cost_quote_hashes: tuple[str, ...]
    rows: tuple[LabelRowV1, ...]

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "cost_quote_hashes": list(self.cost_quote_hashes),
            "dataset_hash": self.dataset_hash,
            "dataset_id": self.dataset_id,
            "execution_contract_version": EXECUTION_CONTRACT_VERSION_V1,
            "feature_dataset_hash": self.feature_dataset_hash,
            "feature_dataset_id": self.feature_dataset_id,
            "label_contract_version": LABEL_CONTRACT_VERSION_V1,
            "source_dataset_hash": self.source_dataset_hash,
            "source_dataset_id": self.source_dataset_id,
        }


def require_feature_dataset_identity(  # craft-allow: deep-nesting - each row must bind authority.
    dataset: FeatureDatasetV1,
) -> None:
    _require_derived_rows(
        dataset.rows,
        candidate_id=dataset.candidate_id,
        source_dataset_id=dataset.source_dataset_id,
        source_dataset_hash=dataset.source_dataset_hash,
    )
    for row in dataset.rows:
        if row.universe_authority_hash != dataset.universe_authority_hash:
            raise ModelingError(
                ModelingFailureCode.DATASET_INTEGRITY_INVALID,
                "feature row universe authority does not match its dataset",
                offending_record_key=row.record_key,
            )
    unsigned_metadata = dataset.metadata_dict()
    unsigned_metadata.pop("dataset_id")
    unsigned_metadata.pop("dataset_hash")
    expected_hash = derived_dataset_hash(FEATURE_ROW_SCHEMA, unsigned_metadata, dataset.rows)
    if dataset.dataset_hash != expected_hash or dataset.dataset_id != f"dset_{expected_hash[:24]}":
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "feature dataset identity does not match its rows and metadata",
        )


def require_label_dataset_identity(dataset: LabelDatasetV1) -> None:
    _require_derived_rows(dataset.rows, candidate_id=dataset.candidate_id)
    for quote_hash in dataset.cost_quote_hashes:
        _require_hash(quote_hash, "cost_quote_hash")
    unsigned_metadata = dataset.metadata_dict()
    unsigned_metadata.pop("dataset_id")
    unsigned_metadata.pop("dataset_hash")
    expected_hash = derived_dataset_hash(LABEL_ROW_SCHEMA, unsigned_metadata, dataset.rows)
    if dataset.dataset_hash != expected_hash or dataset.dataset_id != f"dset_{expected_hash[:24]}":
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "label dataset identity does not match its rows and metadata",
        )


def derived_dataset_hash(
    schema_id: str,
    metadata: Mapping[str, Any],
    rows: tuple[FeatureRowV1, ...] | tuple[LabelRowV1, ...],
) -> str:
    return canonical_sha256(
        {
            "metadata": dict(metadata),
            "records": [row.to_canonical_dict() for row in rows],
            "schema_id": schema_id,
            "schema_version": 1,
        }
    )


def decimal_result(value: Decimal) -> str:
    if not value.is_finite():
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "decimal result must be finite",
        )
    try:
        with localcontext() as context:
            _, digits, _ = value.as_tuple()
            context.prec = max(50, len(digits) + abs(value.adjusted()) + 20)
            context.rounding = ROUND_HALF_EVEN
            rounded = value.quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN)
    except InvalidOperation as error:
        raise ModelingError(
            ModelingFailureCode.NON_FINITE_VALUE,
            "decimal result cannot be represented",
        ) from error
    return decimal_text(rounded)


def _require_derived_rows(
    rows: tuple[FeatureRowV1, ...] | tuple[LabelRowV1, ...],
    *,
    candidate_id: str,
    source_dataset_id: str | None = None,
    source_dataset_hash: str | None = None,
) -> None:
    if not rows:
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "derived dataset cannot be empty",
        )
    keys = tuple(row.record_key for row in rows)
    expected_keys = tuple(sorted(keys))
    if len(set(keys)) != len(keys) or keys != expected_keys:
        raise ModelingError(
            ModelingFailureCode.RECORD_ORDER_INVALID,
            "derived dataset rows must follow their strict total order",
        )
    for row in rows:
        if row.candidate_id != candidate_id:
            raise ModelingError(
                ModelingFailureCode.DATASET_INTEGRITY_INVALID,
                "derived row candidate identity does not match its dataset",
                offending_record_key=row.record_key,
            )
        if isinstance(row, FeatureRowV1) and (
            row.dataset_id != source_dataset_id or row.dataset_hash != source_dataset_hash
        ):
            raise ModelingError(
                ModelingFailureCode.DATASET_INTEGRITY_INVALID,
                "feature row source identity does not match its dataset",
                offending_record_key=row.record_key,
            )


def _canonical_decimal(
    value: Decimal | str,
    field_name: str,
    *,
    nonnegative: bool = False,
) -> str:
    if not isinstance(value, (Decimal, str)):
        raise TypeError(f"{field_name} must be Decimal or string")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field_name} must be a decimal") from error
    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if nonnegative and parsed < 0:
        raise ValueError(f"{field_name} cannot be negative")
    canonical = decimal_text(parsed)
    if isinstance(value, str) and value != canonical:
        raise ValueError(f"{field_name} must use canonical decimal text")
    return canonical


def _closed_money_map(value: Mapping[str, MoneyV1]) -> Mapping[str, MoneyV1]:
    if not value:
        raise ValueError("component_costs cannot be empty")
    if tuple(value) != tuple(sorted(value)) or len(set(value)) != len(value):
        raise ValueError("component_costs must have unique sorted names")
    if any(not name or not isinstance(money, MoneyV1) for name, money in value.items()):
        raise ValueError("component_costs entries are invalid")
    return MappingProxyType(dict(value))


def _positive_decimal(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be Decimal")
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field_name} must be finite and positive")


def _require_candidate_id(value: str) -> None:
    if _CANDIDATE_PATTERN.fullmatch(value) is None:
        raise ValueError("candidate_id is invalid")


def _require_hash(value: str, field_name: str) -> None:
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a SHA-256 hash")


def _require_sorted_unique(values: tuple[str, ...], field_name: str) -> None:
    if not values or tuple(sorted(set(values))) != values:
        raise ValueError(f"{field_name} must be non-empty, unique, and sorted")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
