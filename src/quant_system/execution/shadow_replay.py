"""Recorded Shadow Replay execution engine with strict point-in-time and zero broker write invariants."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from quant_system.backtest.costs import IndianMarketCostModel, TransactionCostBreakdown
from quant_system.core.domain import Fill, Order, OrderType, Side
from quant_system.core.ledger import DecimalLedger
from quant_system.evidence.canonical import sha256_hex
from quant_system.execution.replay_feed import (
    ReplayFeedError,
    ReplayFeedFailureCode,
    ReplayQuote,
    ReplayQuoteFeed,
)
from quant_system.execution.shadow_models import (
    MaturedOutcome,
    RuleBasedShadowModel,
    ShadowDecisionModel,
    ShadowExecutionMode,
    ShadowProposal,
    ShadowProposalStatus,
    ShadowSessionAudit,
    ShadowSessionStatus,
    ShadowSignal,
)
from quant_system.risk.checks import RiskDecision
from quant_system.risk.governor import PreTradeRiskGovernor

_PAISA = Decimal("0.01")

__all__ = [
    "MaturedOutcome",
    "RuleBasedShadowModel",
    "ShadowDecisionModel",
    "ShadowExecutionMode",
    "ShadowProposal",
    "ShadowProposalStatus",
    "ShadowReplayEngine",
    "ShadowSessionAudit",
    "ShadowSessionStatus",
    "ShadowSignal",
]


class ShadowReplayEngine:
    """Engine executing shadow replay sessions over recorded quote feeds."""

    def __init__(
        self,
        session_id: str,
        model: ShadowDecisionModel,
        initial_cash: Decimal = Decimal("1000000.00"),
        risk_governor: PreTradeRiskGovernor | None = None,
        decision_latency: timedelta = timedelta(milliseconds=10),
        execution_latency: timedelta = timedelta(milliseconds=5),
        slippage_bps: float = 5.0,
        maturity_horizon_quotes: int = 5,
        allow_short: bool = False,
    ) -> None:
        self.session_id = session_id
        self.model = model
        self.risk_governor = risk_governor or PreTradeRiskGovernor()
        self.ledger = DecimalLedger(initial_cash=initial_cash, allow_short=allow_short)
        self.decision_latency = decision_latency
        self.execution_latency = execution_latency
        self.slippage_bps = slippage_bps
        self.maturity_horizon_quotes = maturity_horizon_quotes

        self._status: ShadowSessionStatus = ShadowSessionStatus.INITIALIZED
        self._halt_reason: str | None = None
        self._price_cache: dict[str, Decimal] = {}
        self._proposals_by_id: dict[str, ShadowProposal] = {}
        self._pending_proposals: list[ShadowProposal] = []
        self._maturity_tracking: list[tuple[str, int]] = []
        self._fills: list[Fill] = []
        self._quotes_processed: int = 0
        self._start_time: datetime | None = None
        self._end_time: datetime | None = None
        self.broker_write_calls: int = 0

    @property
    def status(self) -> ShadowSessionStatus:
        return self._status

    @property
    def proposals(self) -> list[ShadowProposal]:
        return list(self._proposals_by_id.values())

    @property
    def fills(self) -> list[Fill]:
        return list(self._fills)

    def run(self, feed: ReplayQuoteFeed) -> ShadowSessionAudit:
        if self.model.target_state != "SHADOW":
            self._status = ShadowSessionStatus.HALTED
            self._halt_reason = (
                f"MODEL_NOT_IN_SHADOW_STATE: Expected 'SHADOW', got '{self.model.target_state}'"
            )
            return self._build_audit()

        self._status = ShadowSessionStatus.RUNNING
        try:
            for quote in feed:
                self._process_tick(quote)
            self._finalize_completed_session()
        except ReplayFeedError as err:
            self._handle_feed_error(err)
        return self._build_audit()

    def _process_tick(self, quote: ReplayQuote) -> None:
        if self._start_time is None:
            self._start_time = quote.timestamp
        self._end_time = quote.timestamp
        self._quotes_processed += 1
        self._price_cache[quote.symbol] = quote.mid_price

        self._process_pending_fills(quote)
        self._attribute_matured_outcomes(quote)
        self._generate_model_signals(quote)

    def _process_pending_fills(self, quote: ReplayQuote) -> None:
        remaining: list[ShadowProposal] = []
        for prop in self._pending_proposals:
            is_match = prop.symbol == quote.symbol
            is_ready = quote.timestamp >= prop.order_timestamp + self.execution_latency
            if is_match and is_ready:
                self._execute_single_proposal(prop, quote)
            else:
                remaining.append(prop)
        self._pending_proposals = remaining

    def _execute_single_proposal(self, prop: ShadowProposal, quote: ReplayQuote) -> None:
        decision = self._evaluate_pretrade_risk(prop, quote)
        if not decision.approved:
            self._proposals_by_id[prop.proposal_id] = self._make_rejected_proposal(prop, decision)
            return

        exec_price = self._calculate_exec_price(prop.side, quote)
        costs = self._calculate_friction(prop.symbol, prop.side, prop.quantity, exec_price)
        fill = Fill(
            fill_id=f"shadow_fill_{len(self._fills) + 1}",
            order_id=prop.proposal_id,
            symbol=prop.symbol,
            side=prop.side,
            quantity=prop.quantity,
            price=exec_price,
            fee=costs.total_fee,
            timestamp=quote.timestamp,
        )
        self.ledger.process_fill(fill)
        self._fills.append(fill)

        self._proposals_by_id[prop.proposal_id] = self._make_filled_proposal(
            prop, decision, fill, costs
        )
        target_seq = quote.sequence_id + self.maturity_horizon_quotes
        self._maturity_tracking.append((prop.proposal_id, target_seq))

    def _evaluate_pretrade_risk(self, prop: ShadowProposal, quote: ReplayQuote) -> RiskDecision:
        current_equity = self.ledger.cash + sum(
            p.current_market_value(self._price_cache.get(p.symbol, p.average_price))
            for p in self.ledger.positions.values()
        )
        order = Order(
            order_id=prop.proposal_id,
            symbol=prop.symbol,
            side=prop.side,
            quantity=prop.quantity,
            order_type=OrderType.MARKET,
            created_at=prop.order_timestamp,
        )
        return self.risk_governor.evaluate_order(
            order=order,
            current_equity=current_equity,
            current_cash=self.ledger.cash,
            positions=self.ledger.positions,
            current_quote=quote.to_domain_quote(),
        )

    def _make_rejected_proposal(self, prop: ShadowProposal, dec: RiskDecision) -> ShadowProposal:
        return ShadowProposal(
            proposal_id=prop.proposal_id,
            session_id=prop.session_id,
            model_id=prop.model_id,
            symbol=prop.symbol,
            side=prop.side,
            quantity=prop.quantity,
            signal_score=prop.signal_score,
            decision_timestamp=prop.decision_timestamp,
            order_timestamp=prop.order_timestamp,
            trigger_quote_seq=prop.trigger_quote_seq,
            status=ShadowProposalStatus.REJECTED,
            risk_decision=dec,
            rejection_reason=dec.reason,
        )

    def _make_filled_proposal(
        self,
        prop: ShadowProposal,
        dec: RiskDecision,
        fill: Fill,
        costs: TransactionCostBreakdown,
    ) -> ShadowProposal:
        return ShadowProposal(
            proposal_id=prop.proposal_id,
            session_id=prop.session_id,
            model_id=prop.model_id,
            symbol=prop.symbol,
            side=prop.side,
            quantity=prop.quantity,
            signal_score=prop.signal_score,
            decision_timestamp=prop.decision_timestamp,
            order_timestamp=prop.order_timestamp,
            trigger_quote_seq=prop.trigger_quote_seq,
            status=ShadowProposalStatus.FILLED,
            risk_decision=dec,
            fill=fill,
            cost_breakdown=costs,
        )

    def _calculate_exec_price(self, side: Side, quote: ReplayQuote) -> Decimal:
        slip = Decimal(str(self.slippage_bps / 10000.0))
        if side == Side.BUY:
            return (quote.ask * (Decimal("1") + slip)).quantize(_PAISA)
        return (quote.bid * (Decimal("1") - slip)).quantize(_PAISA)

    def _calculate_friction(
        self,
        symbol: str,
        side: Side,
        quantity: int,
        price: Decimal,
    ) -> TransactionCostBreakdown:
        if symbol.endswith("CE") or symbol.endswith("PE"):
            return IndianMarketCostModel.calculate_options_friction(
                side=side, quantity=quantity, premium=price, strike=price, slippage_bps=0.0
            )
        return IndianMarketCostModel.calculate_equity_delivery(
            side=side, quantity=quantity, price=price, slippage_bps=0.0
        )

    def _attribute_matured_outcomes(self, quote: ReplayQuote) -> None:
        remaining: list[tuple[str, int]] = []
        for prop_id, target_seq in self._maturity_tracking:
            prop = self._proposals_by_id[prop_id]
            if prop.symbol == quote.symbol and quote.sequence_id >= target_seq:
                self._record_matured_outcome(prop, quote)
            else:
                remaining.append((prop_id, target_seq))
        self._maturity_tracking = remaining

    def _record_matured_outcome(self, prop: ShadowProposal, quote: ReplayQuote) -> None:
        if prop.fill is None:
            return
        entry_p = prop.fill.price
        exit_p = quote.mid_price
        delta = (exit_p - entry_p) if prop.side == Side.BUY else (entry_p - exit_p)
        ret = (delta / entry_p).quantize(Decimal("0.000001"))
        matured = MaturedOutcome(
            attribution_timestamp=quote.timestamp,
            realized_price=exit_p,
            realized_return=ret,
            attribution_quote_seq=quote.sequence_id,
            is_profitable=(delta > Decimal("0")),
        )
        self._proposals_by_id[prop.proposal_id] = ShadowProposal(
            proposal_id=prop.proposal_id,
            session_id=prop.session_id,
            model_id=prop.model_id,
            symbol=prop.symbol,
            side=prop.side,
            quantity=prop.quantity,
            signal_score=prop.signal_score,
            decision_timestamp=prop.decision_timestamp,
            order_timestamp=prop.order_timestamp,
            trigger_quote_seq=prop.trigger_quote_seq,
            status=prop.status,
            risk_decision=prop.risk_decision,
            fill=prop.fill,
            cost_breakdown=prop.cost_breakdown,
            rejection_reason=prop.rejection_reason,
            cancellation_reason=prop.cancellation_reason,
            matured_outcome=matured,
        )

    def _generate_model_signals(self, quote: ReplayQuote) -> None:
        signal = self.model.evaluate_quote(quote, self.ledger.positions, self.ledger.cash)
        if signal is None or signal.side is None or signal.quantity <= 0:
            return

        dec_time = quote.timestamp + self.decision_latency
        prop_id = f"prop_{self.session_id}_{len(self._proposals_by_id) + 1}"
        proposal = ShadowProposal(
            proposal_id=prop_id,
            session_id=self.session_id,
            model_id=self.model.model_id,
            symbol=signal.symbol,
            side=signal.side,
            quantity=signal.quantity,
            signal_score=signal.confidence,
            decision_timestamp=dec_time,
            order_timestamp=dec_time,
            trigger_quote_seq=quote.sequence_id,
            status=ShadowProposalStatus.PENDING,
        )
        self._proposals_by_id[prop_id] = proposal
        self._pending_proposals.append(proposal)

    def _finalize_completed_session(self) -> None:
        self._status = ShadowSessionStatus.COMPLETED
        self._cancel_remaining_pending("SESSION_END_UNFILLED")
        self.ledger.reconcile()

    def _handle_feed_error(self, err: ReplayFeedError) -> None:
        self._status = (
            ShadowSessionStatus.OFFLINE
            if err.code == ReplayFeedFailureCode.FEED_OFFLINE
            else ShadowSessionStatus.HALTED
        )
        self._halt_reason = str(err)
        self._cancel_remaining_pending(f"SESSION_HALTED: {self._halt_reason}")

    def _cancel_remaining_pending(self, reason: str) -> None:
        for prop in self._pending_proposals:
            self._proposals_by_id[prop.proposal_id] = ShadowProposal(
                proposal_id=prop.proposal_id,
                session_id=prop.session_id,
                model_id=prop.model_id,
                symbol=prop.symbol,
                side=prop.side,
                quantity=prop.quantity,
                signal_score=prop.signal_score,
                decision_timestamp=prop.decision_timestamp,
                order_timestamp=prop.order_timestamp,
                trigger_quote_seq=prop.trigger_quote_seq,
                status=ShadowProposalStatus.CANCELLED,
                cancellation_reason=reason,
            )
        self._pending_proposals.clear()

    def _build_audit(self) -> ShadowSessionAudit:
        counts = self._count_proposal_statuses()
        snap = self.ledger.get_portfolio_snapshot(
            self._price_cache,
            self._end_time or datetime.now(),
        )
        matured_count = sum(
            1 for p in self._proposals_by_id.values() if p.matured_outcome is not None
        )
        total_fees = sum((f.fee for f in self._fills), Decimal("0.00")).quantize(_PAISA)

        summary_text = (
            f"{self.session_id}:{self.model.model_id}:{self._status.value}:{self._quotes_processed}:"
            f"{len(self._proposals_by_id)}:{counts['FILLED']}:{self.ledger.cash}:{snap.total_equity}"
        )
        audit_hash = sha256_hex(summary_text.encode("utf-8"))

        return ShadowSessionAudit(
            session_id=self.session_id,
            mode=ShadowExecutionMode.SHADOW_READ_ONLY.value,
            model_id=self.model.model_id,
            status=self._status,
            start_timestamp=self._start_time,
            end_timestamp=self._end_time,
            quotes_processed=self._quotes_processed,
            proposals_total=len(self._proposals_by_id),
            proposals_filled=counts["FILLED"],
            proposals_rejected=counts["REJECTED"],
            proposals_pending=counts["PENDING"],
            proposals_cancelled=counts["CANCELLED"],
            proposals_unprocessed=counts["UNPROCESSED"],
            initial_cash=self.ledger.initial_cash,
            final_cash=self.ledger.cash,
            realized_pnl=self.ledger.realized_pnl,
            unrealized_pnl=snap.unrealized_pnl,
            total_equity=snap.total_equity,
            total_fees_paid=total_fees,
            reconciled=True,
            matured_decisions_count=matured_count,
            audit_hash=audit_hash,
            halt_reason=self._halt_reason,
            broker_write_calls=self.broker_write_calls,
        )

    def _count_proposal_statuses(self) -> dict[str, int]:
        counts = {
            "FILLED": 0,
            "REJECTED": 0,
            "PENDING": 0,
            "CANCELLED": 0,
            "UNPROCESSED": 0,
        }
        for prop in self._proposals_by_id.values():
            counts[prop.status.value] = counts.get(prop.status.value, 0) + 1
        return counts
