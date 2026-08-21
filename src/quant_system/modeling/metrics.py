"""Canonical strategy decisions and financial metrics for governed fold evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from itertools import groupby
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text
from quant_system.modeling.rows import LabelRowV1
from quant_system.modeling.trials import SCORE_KIND_V1

STRATEGY_ORDER_V1 = (
    "RIDGE",
    "NO_TRADE",
    "BUY_AND_HOLD",
    "PREVIOUS_SIGN",
    "EQUITY_DUAL_MOMENTUM",
)
_METRIC_QUANTUM = Decimal("0.000000000001")
_DECISION_RECORD_KEYS = frozenset(
    {
        "actual_target",
        "decision_at",
        "predicted_target",
        "realized_net_return",
        "score",
        "score_kind",
        "strategy_id",
        "symbol",
    }
)
ALLOCATION_CONTRACT_V1 = "EQUAL_WEIGHT_ACTIVE_LONGS_PER_DECISION_TIME"


@dataclass(frozen=True, slots=True)
class FoldDecisionV1:
    strategy_id: str
    symbol: str
    decision_at: datetime
    predicted_target: str
    actual_target: str
    realized_net_return: str
    score: str | None
    score_kind: str

    def __post_init__(self) -> None:
        if self.strategy_id not in STRATEGY_ORDER_V1:
            raise ValueError("unknown fold strategy")
        if self.predicted_target not in {"UP", "DOWN"}:
            raise ValueError("predicted target must be UP or DOWN")
        if self.actual_target not in {"UP", "DOWN"}:
            raise ValueError("actual target must be UP or DOWN")
        if self.decision_at.tzinfo is None or self.decision_at.utcoffset() is None:
            raise ValueError("decision_at must be timezone-aware")
        _require_decimal_text(self.realized_net_return, "realized_net_return")
        self._validate_score_contract()

    def _validate_score_contract(self) -> None:
        if self.strategy_id == "RIDGE":
            if self.score is None or self.score_kind != SCORE_KIND_V1:
                raise ValueError("ridge decisions require an uncalibrated score")
            _require_decimal_text(self.score, "score")
            return
        if self.score is not None or self.score_kind != "RULE":
            raise ValueError("baseline decisions must use RULE without a score")

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "actual_target": self.actual_target,
            "decision_at": utc_text(self.decision_at),
            "predicted_target": self.predicted_target,
            "realized_net_return": self.realized_net_return,
            "score": self.score,
            "score_kind": self.score_kind,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
        }


@dataclass(frozen=True, slots=True)
class StrategyMetricsV1:
    accuracy: str
    balanced_accuracy: str | None
    total_return: str
    annualized_volatility: str
    sharpe_ratio: str
    sortino_ratio: str
    max_drawdown: str
    max_drawdown_duration_rows: int
    turnover: str
    exposure: str
    concentration: str
    attributable_count: int
    trade_count: int
    hit_rate: str
    profit_factor: str | None

    def __post_init__(self) -> None:
        decimal_fields = (
            self.accuracy,
            self.total_return,
            self.annualized_volatility,
            self.sharpe_ratio,
            self.sortino_ratio,
            self.max_drawdown,
            self.turnover,
            self.exposure,
            self.concentration,
            self.hit_rate,
        )
        optional_fields = (self.balanced_accuracy, self.profit_factor)
        if any(not _is_canonical_decimal(value) for value in decimal_fields) or any(
            value is not None and not _is_canonical_decimal(value) for value in optional_fields
        ):
            raise ValueError("strategy metrics must use finite canonical decimal text")
        for name in ("max_drawdown_duration_rows", "attributable_count", "trade_count"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an exact integer")
        if min(self.max_drawdown_duration_rows, self.attributable_count, self.trade_count) < 0:
            raise ValueError("strategy metric counts cannot be negative")
        if self.trade_count > self.attributable_count:
            raise ValueError("trade count cannot exceed attributable count")
        if Decimal(self.annualized_volatility) == 0 and Decimal(self.sharpe_ratio) != 0:
            raise ValueError(
                "a published Sharpe ratio requires a non-zero published volatility; "
                "otherwise the ratio cannot be reconstructed from the published metrics"
            )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "accuracy": self.accuracy,
            "annualized_volatility": self.annualized_volatility,
            "attributable_count": self.attributable_count,
            "balanced_accuracy": self.balanced_accuracy,
            "concentration": self.concentration,
            "exposure": self.exposure,
            "hit_rate": self.hit_rate,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration_rows": self.max_drawdown_duration_rows,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "total_return": self.total_return,
            "trade_count": self.trade_count,
            "turnover": self.turnover,
        }


@dataclass(frozen=True, slots=True)
class StrategyFoldReportV1:
    strategy_id: str
    decisions: tuple[FoldDecisionV1, ...]
    metrics: StrategyMetricsV1
    prediction_hash: str = field(init=False)
    metrics_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.strategy_id not in STRATEGY_ORDER_V1 or not self.decisions:
            raise ValueError("strategy report is invalid")
        if any(decision.strategy_id != self.strategy_id for decision in self.decisions):
            raise ValueError("strategy decisions do not match their report")
        keys = tuple((decision.decision_at, decision.symbol) for decision in self.decisions)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("strategy decisions must be unique and chronological")
        object.__setattr__(self, "prediction_hash", _prediction_hash(self.decisions))
        object.__setattr__(self, "metrics_hash", _metrics_hash(self.strategy_id, self.metrics))

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "allocation_contract": ALLOCATION_CONTRACT_V1,
            "decisions": [decision.to_canonical_dict() for decision in self.decisions],
            "metrics": self.metrics.to_canonical_dict(),
            "metrics_hash": self.metrics_hash,
            "prediction_hash": self.prediction_hash,
            "strategy_id": self.strategy_id,
        }


def build_strategy_report(
    strategy_id: str,
    labels: tuple[LabelRowV1, ...],
    predicted_targets: tuple[str, ...],
    scores: tuple[str, ...] | None,
) -> StrategyFoldReportV1:
    decisions = tuple(
        FoldDecisionV1(
            strategy_id=strategy_id,
            symbol=label.symbol,
            decision_at=label.decision_at,
            predicted_target=predicted,
            actual_target=label.target,
            realized_net_return=label.net_return if predicted == "UP" else "0",
            score=scores[index] if scores is not None else None,
            score_kind=SCORE_KIND_V1 if strategy_id == "RIDGE" else "RULE",
        )
        for index, (label, predicted) in enumerate(zip(labels, predicted_targets, strict=True))
    )
    return StrategyFoldReportV1(
        strategy_id=strategy_id,
        decisions=decisions,
        metrics=calculate_strategy_metrics(decisions),
    )


def strategy_report_from_records(
    strategy_id: str,
    records: tuple[Mapping[str, Any], ...],
) -> StrategyFoldReportV1:
    """Re-derive one strategy report from its published decision records.

    Every metric, the metrics hash, and the prediction hash are recomputed from the decisions
    themselves, so a caller can reject published summaries that no longer bind their content.
    """
    decisions = tuple(_decision_from_record(strategy_id, record) for record in records)
    return StrategyFoldReportV1(
        strategy_id=strategy_id,
        decisions=decisions,
        metrics=calculate_strategy_metrics(decisions),
    )


def _decision_from_record(strategy_id: str, record: Mapping[str, Any]) -> FoldDecisionV1:
    if set(record) != _DECISION_RECORD_KEYS:
        raise ValueError("decision record does not match the published contract")
    if record["strategy_id"] != strategy_id:
        raise ValueError("decision record belongs to another strategy")
    for name in (
        "actual_target",
        "decision_at",
        "predicted_target",
        "realized_net_return",
        "score_kind",
        "symbol",
    ):
        if not isinstance(record[name], str):
            raise TypeError(f"{name} must be text")
    score = record["score"]
    if score is not None and not isinstance(score, str):
        raise TypeError("score must be text or null")
    return FoldDecisionV1(
        strategy_id=strategy_id,
        symbol=record["symbol"],
        decision_at=datetime.fromisoformat(record["decision_at"].replace("Z", "+00:00")),
        predicted_target=record["predicted_target"],
        actual_target=record["actual_target"],
        realized_net_return=record["realized_net_return"],
        score=score,
        score_kind=record["score_kind"],
    )


def _prediction_hash(decisions: tuple[FoldDecisionV1, ...]) -> str:
    return canonical_sha256(
        {
            "records": [decision.to_canonical_dict() for decision in decisions],
            "schema_id": "quantos.fold_strategy_decisions",
            "schema_version": 1,
        }
    )


def _metrics_hash(strategy_id: str, metrics: StrategyMetricsV1) -> str:
    return canonical_sha256(
        {
            "allocation_contract": ALLOCATION_CONTRACT_V1,
            "metrics": metrics.to_canonical_dict(),
            "schema_id": "quantos.fold_strategy_metrics",
            "schema_version": 1,
            "strategy_id": strategy_id,
        }
    )


def calculate_strategy_metrics(decisions: tuple[FoldDecisionV1, ...]) -> StrategyMetricsV1:
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN
        count = Decimal(len(decisions))
        correct = sum(decision.predicted_target == decision.actual_target for decision in decisions)
        portfolio_returns, active_counts = _portfolio_period_returns(decisions)
        mean = sum(portfolio_returns) / Decimal(len(portfolio_returns))
        volatility = _sample_deviation(portfolio_returns, mean)
        trades = tuple(
            Decimal(decision.realized_net_return) if decision.predicted_target == "UP" else None
            for decision in decisions
        )
        active_trades = tuple(value for value in trades if value is not None)
        return _assemble_metrics(
            decisions,
            portfolio_returns,
            active_trades,
            active_counts,
            Decimal(correct) / count,
            volatility,
        )


def _assemble_metrics(
    decisions: tuple[FoldDecisionV1, ...],
    returns: tuple[Decimal, ...],
    trades: tuple[Decimal, ...],
    active_counts: tuple[int, ...],
    accuracy: Decimal,
    volatility: Decimal,
) -> StrategyMetricsV1:
    period_count = Decimal(len(returns))
    mean = sum(returns) / period_count
    annualized = volatility * Decimal(252).sqrt()
    sharpe = mean / volatility * Decimal(252).sqrt() if volatility > 0 else Decimal(0)
    downside_deviation = (
        sum(min(Decimal(0), value) ** 2 for value in returns) / period_count
    ).sqrt()
    sortino = (
        mean / downside_deviation * Decimal(252).sqrt() if downside_deviation > 0 else Decimal(0)
    )
    drawdown, duration = _maximum_drawdown(returns)
    gross_profit = sum((value for value in trades if value > 0), start=Decimal(0))
    gross_loss = -sum((value for value in trades if value < 0), start=Decimal(0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    trade_count = len(trades)
    active_periods = sum(count > 0 for count in active_counts)
    concentration = max(
        (Decimal(1) / Decimal(count) for count in active_counts if count > 0),
        default=Decimal(0),
    )
    return StrategyMetricsV1(
        accuracy=metric_decimal(accuracy),
        balanced_accuracy=_optional_metric(_balanced_accuracy(decisions)),
        total_return=metric_decimal(_compound_return(returns)),
        annualized_volatility=metric_decimal(annualized),
        sharpe_ratio=metric_decimal(sharpe),
        sortino_ratio=metric_decimal(sortino),
        max_drawdown=metric_decimal(drawdown),
        max_drawdown_duration_rows=duration,
        turnover=metric_decimal(Decimal(2 * active_periods) / period_count),
        exposure=metric_decimal(Decimal(active_periods) / period_count),
        concentration=metric_decimal(concentration),
        attributable_count=len(decisions),
        trade_count=trade_count,
        hit_rate=metric_decimal(Decimal(sum(value > 0 for value in trades)) / Decimal(trade_count))
        if trade_count
        else "0",
        profit_factor=_optional_metric(profit_factor),
    )


def _portfolio_period_returns(
    decisions: tuple[FoldDecisionV1, ...],
) -> tuple[tuple[Decimal, ...], tuple[int, ...]]:
    returns: list[Decimal] = []
    active_counts: list[int] = []
    for _, grouped in groupby(decisions, key=lambda decision: decision.decision_at):
        active = tuple(
            Decimal(decision.realized_net_return)
            for decision in grouped
            if decision.predicted_target == "UP"
        )
        active_counts.append(len(active))
        returns.append(
            sum(active, start=Decimal(0)) / Decimal(len(active)) if active else Decimal(0)
        )
    return tuple(returns), tuple(active_counts)


def _balanced_accuracy(decisions: tuple[FoldDecisionV1, ...]) -> Decimal | None:
    recalls: list[Decimal] = []
    for target in ("DOWN", "UP"):
        matching = tuple(decision for decision in decisions if decision.actual_target == target)
        if not matching:
            return None
        correct = sum(decision.predicted_target == target for decision in matching)
        recalls.append(Decimal(correct) / Decimal(len(matching)))
    return sum(recalls) / Decimal(2)


def _compound_return(returns: tuple[Decimal, ...]) -> Decimal:
    equity = Decimal(1)
    for value in returns:
        equity *= Decimal(1) + value
    return equity - Decimal(1)


def _sample_deviation(values: tuple[Decimal, ...], mean: Decimal) -> Decimal:
    if len(values) < 2:
        return Decimal(0)
    return (sum((value - mean) ** 2 for value in values) / Decimal(len(values) - 1)).sqrt()


def _maximum_drawdown(returns: tuple[Decimal, ...]) -> tuple[Decimal, int]:
    equity = Decimal(1)
    peak = equity
    maximum = Decimal(0)
    duration = 0
    current_duration = 0
    for value in returns:
        equity *= Decimal(1) + value
        if equity >= peak:
            peak = equity
            current_duration = 0
            continue
        drawdown = (peak - equity) / peak
        maximum = max(maximum, drawdown)
        current_duration += 1
        duration = max(duration, current_duration)
    return maximum, duration


def metric_decimal(value: Decimal) -> str:
    rounded = value.quantize(_METRIC_QUANTUM, rounding=ROUND_HALF_EVEN)
    return decimal_text(rounded)


def _optional_metric(value: Decimal | None) -> str | None:
    return metric_decimal(value) if value is not None else None


def _is_canonical_decimal(value: str) -> bool:
    try:
        parsed = Decimal(value)
    except ArithmeticError:
        return False
    return parsed.is_finite() and decimal_text(parsed) == value


def _require_decimal_text(value: str, field_name: str) -> None:
    if not _is_canonical_decimal(value):
        raise ValueError(f"{field_name} must be finite canonical decimal text")
