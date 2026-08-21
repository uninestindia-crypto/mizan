"""Domain models, protocols, and audit records for shadow replay sessions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from quant_system.backtest.costs import TransactionCostBreakdown
from quant_system.core.domain import Fill, Position, Side
from quant_system.execution.replay_feed import ReplayQuote
from quant_system.risk.checks import RiskDecision


class ShadowExecutionMode(StrEnum):
    SHADOW_READ_ONLY = "SHADOW_READ_ONLY"


class ShadowSessionStatus(StrEnum):
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    HALTED = "HALTED"
    OFFLINE = "OFFLINE"
    CANCELLED = "CANCELLED"


class ShadowProposalStatus(StrEnum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    UNPROCESSED = "UNPROCESSED"


@dataclass(frozen=True, slots=True)
class ShadowSignal:
    symbol: str
    side: Side | None
    quantity: int
    confidence: float = 1.0
    target_weight: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MaturedOutcome:
    attribution_timestamp: datetime
    realized_price: Decimal
    realized_return: Decimal
    attribution_quote_seq: int
    is_profitable: bool


@dataclass(frozen=True, slots=True)
class ShadowProposal:
    proposal_id: str
    session_id: str
    model_id: str
    symbol: str
    side: Side
    quantity: int
    signal_score: float
    decision_timestamp: datetime
    order_timestamp: datetime
    trigger_quote_seq: int
    status: ShadowProposalStatus
    risk_decision: RiskDecision | None = None
    fill: Fill | None = None
    cost_breakdown: TransactionCostBreakdown | None = None
    rejection_reason: str | None = None
    cancellation_reason: str | None = None
    matured_outcome: MaturedOutcome | None = None


@dataclass(frozen=True, slots=True)
class ShadowSessionAudit:
    session_id: str
    mode: str
    model_id: str
    status: ShadowSessionStatus
    start_timestamp: datetime | None
    end_timestamp: datetime | None
    quotes_processed: int
    proposals_total: int
    proposals_filled: int
    proposals_rejected: int
    proposals_pending: int
    proposals_cancelled: int
    proposals_unprocessed: int
    initial_cash: Decimal
    final_cash: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_equity: Decimal
    total_fees_paid: Decimal
    reconciled: bool
    matured_decisions_count: int
    audit_hash: str
    halt_reason: str | None = None
    broker_write_calls: int = 0


class ShadowDecisionModel(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def target_state(self) -> str: ...

    def evaluate_quote(
        self,
        quote: ReplayQuote,
        positions: Mapping[str, Position],
        cash: Decimal,
    ) -> ShadowSignal | None: ...


class RuleBasedShadowModel:
    """Deterministic shadow model strategy producing attributable test signals."""

    def __init__(
        self,
        model_id: str = "shadow_rule_v1",
        target_state: str = "SHADOW",
        spread_threshold_pct: float = 0.005,
        trade_quantity: int = 10,
    ) -> None:
        self._model_id = model_id
        self._target_state = target_state
        self._spread_threshold_pct = spread_threshold_pct
        self._trade_quantity = trade_quantity

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def target_state(self) -> str:
        return self._target_state

    def evaluate_quote(
        self,
        quote: ReplayQuote,
        positions: Mapping[str, Position],
        cash: Decimal,
    ) -> ShadowSignal | None:
        if quote.spread_pct > Decimal(str(self._spread_threshold_pct)):
            return None
        held_qty = positions[quote.symbol].quantity if quote.symbol in positions else 0
        if held_qty > 0:
            return ShadowSignal(
                symbol=quote.symbol,
                side=Side.SELL,
                quantity=held_qty,
                confidence=0.85,
            )
        if cash > Decimal("50000.00"):
            return ShadowSignal(
                symbol=quote.symbol,
                side=Side.BUY,
                quantity=self._trade_quantity,
                confidence=0.90,
            )
        return None
