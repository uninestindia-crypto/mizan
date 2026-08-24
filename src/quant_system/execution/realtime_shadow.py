# craft-allow: god-file — one fail-closed shadow-session state machine and its audit contracts.
"""Read-only Real-Time Shadow execution runner with strict freshness budget and risk gating."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from quant_system.core.domain import Order, OrderType, Position, Quote, Side
from quant_system.data.live_feed import (
    FeedState,
    LiveFeedClockDriftError,
    LiveFeedConnectionError,
    LiveFeedError,
    LiveFeedQualityError,
    LiveFeedStaleQuoteError,
    LiveFeedTimeoutError,
    LiveFeedUnauthorizedError,
    LiveQuoteRecord,
    UpstoxLiveFeed,
)
from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text
from quant_system.data.upstox_failures import require_aware_utc
from quant_system.execution.bar_history import BarHistoryProvider
from quant_system.execution.governed_strategy import GOVERNED_BARS_KEY
from quant_system.execution.maturity import MaturityPolicy, MaturityPolicyError
from quant_system.risk.governor import PreTradeRiskGovernor
from quant_system.strategies.base import BaseStrategy, MarketContext

_PAISA = Decimal("0.01")


class ShadowSessionState(StrEnum):
    """Lifecycle states of the real-time shadow session."""

    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    SHADOW_HALTED = "SHADOW_HALTED"
    COMPLETED = "COMPLETED"
    UNAUTHORIZED = "UNAUTHORIZED"
    OFFLINE = "OFFLINE"


class ShadowHaltReason(StrEnum):
    """Explicit typed reasons for halting a shadow session."""

    STALE_QUOTE = "STALE_QUOTE"
    DISCONNECTED = "DISCONNECTED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    CLOCK_DRIFT = "CLOCK_DRIFT"
    QUALITY_VIOLATION = "QUALITY_VIOLATION"
    FEED_TIMEOUT = "FEED_TIMEOUT"
    FEED_ERROR = "FEED_ERROR"
    RISK_KILL_SWITCH = "RISK_KILL_SWITCH"
    MANUAL_HALT = "MANUAL_HALT"
    # Names deliberately match ReplayFeedFailureCode so the recorded (Slice 8) and live
    # (Slice 9) surfaces describe the same defect with the same word in the audit.
    DUPLICATE_TICK = "DUPLICATE_TICK"
    OUT_OF_ORDER_TIMESTAMP = "OUT_OF_ORDER_TIMESTAMP"
    # A maturity horizon could not be resolved for an open entry. Halting keeps the audit;
    # letting the error escape lost the whole session report along with it.
    MATURITY_UNRESOLVABLE = "MATURITY_UNRESOLVABLE"


class ShadowDecisionStatus(StrEnum):
    """Status of a generated shadow proposal/decision."""

    APPROVED = "APPROVED"
    REJECTED_BY_RISK = "REJECTED_BY_RISK"
    HALTED = "HALTED"
    NO_SIGNAL = "NO_SIGNAL"


class DecisionCadence(StrEnum):
    """How often the strategy is consulted for a given symbol within one session.

    `PER_QUOTE` is the quote-driven behaviour this runner was built for. `ONCE_PER_SESSION`
    exists for governed models, which decide on a completed daily bar: scoring one unchanged
    feature row on every tick would emit the same signal all session and stack position on
    each one. See `agent_context/decisions/20260822-point-in-time-bars-at-execution.md`.
    """

    PER_QUOTE = "PER_QUOTE"
    ONCE_PER_SESSION = "ONCE_PER_SESSION"


@dataclass(frozen=True, slots=True)
class ShadowProposal:
    """Immutable record of an attributable shadow trading decision."""

    proposal_id: str
    model_id: str
    symbol: str
    side: Side | None
    quantity: int
    signal_strength: float
    quote_bid: Decimal
    quote_ask: Decimal
    quote_mid: Decimal
    quote_timestamp: datetime
    decision_at: datetime
    quote_latency_seconds: float
    risk_approved: bool
    status: ShadowDecisionStatus
    rejection_reason: str | None = None
    resulting_leverage: float = 0.0
    risk_version: str = "PRE_TRADE_GOVERNOR_V1"
    mode: str = "SHADOW_READ_ONLY"

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "model_id": self.model_id,
            "symbol": self.symbol,
            "side": self.side.value if self.side else None,
            "quantity": self.quantity,
            "signal_strength": round(self.signal_strength, 6),
            "quote_bid": decimal_text(self.quote_bid),
            "quote_ask": decimal_text(self.quote_ask),
            "quote_mid": decimal_text(self.quote_mid),
            "quote_timestamp": utc_text(self.quote_timestamp),
            "decision_at": utc_text(self.decision_at),
            "quote_latency_seconds": round(self.quote_latency_seconds, 4),
            "risk_approved": self.risk_approved,
            "status": self.status.value,
            "rejection_reason": self.rejection_reason,
            "resulting_leverage": round(self.resulting_leverage, 4),
            "risk_version": self.risk_version,
            "mode": self.mode,
        }


@dataclass(frozen=True, slots=True)
class ShadowMaturedOutcome:
    """Matured performance outcome for an approved shadow decision."""

    outcome_id: str
    proposal_id: str
    symbol: str
    side: Side
    quantity: int
    entry_price: Decimal
    exit_price: Decimal
    gross_pnl: Decimal
    friction_fee: Decimal
    net_pnl: Decimal
    entry_at: datetime
    matured_at: datetime
    holding_seconds: float

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "proposal_id": self.proposal_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": decimal_text(self.entry_price),
            "exit_price": decimal_text(self.exit_price),
            "gross_pnl": decimal_text(self.gross_pnl),
            "friction_fee": decimal_text(self.friction_fee),
            "net_pnl": decimal_text(self.net_pnl),
            "entry_at": utc_text(self.entry_at),
            "matured_at": utc_text(self.matured_at),
            "holding_seconds": round(self.holding_seconds, 2),
        }


@dataclass(frozen=True, slots=True)
class ShadowAuditReport:
    """Complete audit record and evidence of a real-time shadow execution session."""

    session_id: str
    model_id: str
    started_at: datetime
    ended_at: datetime
    final_state: ShadowSessionState
    halt_reason: ShadowHaltReason | None
    halt_details: str | None
    quotes_processed: int
    proposals_generated: int
    proposals_approved: int
    proposals_rejected: int
    broker_orders_submitted: int
    max_quote_latency_seconds: float
    avg_quote_latency_seconds: float
    decisions: tuple[ShadowProposal, ...]
    matured_outcomes: tuple[ShadowMaturedOutcome, ...]
    audit_hash: str
    execution_mode: str = "SHADOW_READ_ONLY"
    # Open exposure, added after a Red Team probe found a held position invisible in the audit:
    # matured_outcomes read 0 and no field reported the position still on the book. Defaulted
    # so existing constructions stay valid — this is an additive change to a public contract.
    open_entries: int = 0
    open_symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.broker_orders_submitted != 0:
            raise ValueError(
                "ZERO ORDER ENDPOINT EXPOSURE INVARIANT VIOLATED: "
                f"{self.broker_orders_submitted} broker orders submitted!"
            )
        if self.execution_mode != "SHADOW_READ_ONLY":
            raise ValueError(
                f"Shadow execution mode must be SHADOW_READ_ONLY, got {self.execution_mode}"
            )


@dataclass(frozen=True, slots=True)
class RealtimeShadowConfig:
    """Configuration parameters for the real-time shadow session."""

    session_id: str
    model_id: str
    freshness_budget_seconds: float = 5.0
    max_clock_drift_seconds: float = 1.0
    default_order_quantity: int = 10
    initial_cash: Decimal = Decimal("1000000.00")
    execution_mode: str = "SHADOW_READ_ONLY"
    decision_cadence: DecisionCadence = DecisionCadence.PER_QUOTE
    maturity_policy: MaturityPolicy | None = None
    """When an open entry may mature.

    Defaults to ``None``, preserving mature-on-the-next-same-symbol-quote exactly, so existing
    quote-driven sessions are unchanged. A governed model needs
    :class:`~quant_system.execution.maturity.SessionHorizonMaturity`, because it was validated on a
    two-session label and must not open and close inside one session.
    """
    bar_history_provider: BarHistoryProvider | None = None
    """Supplies point-in-time bar history to governed models.

    Defaults to ``None``, in which case the market context is built exactly as before and
    ``GOVERNED_BARS_KEY`` is absent — so every quote-driven strategy behaves bit-for-bit
    identically. A governed model requires this; a hand-written strategy does not.
    """


class RealtimeShadowRunner:
    """Executes a strictly read-only shadow session bound to a real-time feed with zero broker write endpoints."""

    def __init__(
        self,
        config: RealtimeShadowConfig,
        live_feed: UpstoxLiveFeed,
        strategy: BaseStrategy | None = None,
        risk_governor: PreTradeRiskGovernor | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self.live_feed = live_feed
        self.strategy = strategy
        self.risk_governor = risk_governor or PreTradeRiskGovernor()
        self._clock = clock or (lambda: datetime.now(UTC))

        self.state: ShadowSessionState = ShadowSessionState.INITIALIZING
        self.halt_reason: ShadowHaltReason | None = None
        self.halt_details: str | None = None

        self._started_at: datetime | None = None
        self._ended_at: datetime | None = None
        self._quotes_processed: int = 0
        self._latencies: list[float] = []
        self._decisions: list[ShadowProposal] = []
        self._matured_outcomes: list[ShadowMaturedOutcome] = []

        # Internal shadow book state (for mark-to-market simulation)
        self._cash: Decimal = self.config.initial_cash
        self._positions: dict[str, Position] = {}
        self._last_quotes: dict[str, Quote] = {}
        self._open_entries: dict[str, tuple[ShadowProposal, Decimal, datetime]] = {}
        self._decided_symbols: set[str] = set()
        self._pending_fills: dict[str, list[ShadowProposal]] = {}
        # Sequence integrity state. The signature set mirrors ReplayQuoteFeed._seen_signatures;
        # it grows for the life of a clean session, which is bounded by one trading day.
        self._seen_quote_signatures: set[tuple[str, datetime, Decimal, Decimal]] = set()
        self._last_event_at_by_symbol: dict[str, datetime] = {}

        # Zero broker orders tracking (strictly remains 0)
        self._broker_orders_submitted: int = 0

        # Enforce no order endpoints exist
        assert not hasattr(self, "submit_broker_order")
        assert not hasattr(self, "place_order")
        assert not hasattr(self, "cancel_broker_order")

    @property
    def broker_orders_submitted(self) -> int:
        return self._broker_orders_submitted

    @property
    def current_equity(self) -> Decimal:
        position_value = sum(
            p.current_market_value(
                self._last_quotes[p.symbol].mid_price
                if p.symbol in self._last_quotes
                else p.average_price
            )
            for p in self._positions.values()
        )
        return self._cash + position_value

    def _halt(
        self,
        reason: ShadowHaltReason,
        details: str,
        state: ShadowSessionState = ShadowSessionState.SHADOW_HALTED,
    ) -> None:
        """Atomically transition to halted state."""
        self.state = state
        self.halt_reason = reason
        self.halt_details = details
        self._ended_at = require_aware_utc(self._clock())

    # craft-allow: long-function — validation order is the fail-closed quote state machine.
    def process_live_quote(  # craft-allow: deep-nesting — guards and risk branches are ordered.
        self, live_quote: LiveQuoteRecord
    ) -> ShadowProposal | None:
        """Process one real-time quote: freshness check, risk gating, and shadow attribution."""
        now = require_aware_utc(self._clock())
        if self._started_at is None:
            self._started_at = now

        # Reject processing if already halted or offline
        if self.state in {
            ShadowSessionState.SHADOW_HALTED,
            ShadowSessionState.OFFLINE,
            ShadowSessionState.UNAUTHORIZED,
        }:
            return None

        # 1. Enforce Freshness Budget (AC-20, AC-62)
        latency = (now - live_quote.event_at).total_seconds()
        self._latencies.append(latency)
        self._quotes_processed += 1

        if latency > self.config.freshness_budget_seconds:
            self._halt(
                ShadowHaltReason.STALE_QUOTE,
                f"Quote latency {latency:.3f}s exceeds freshness budget "
                f"{self.config.freshness_budget_seconds:.1f}s for {live_quote.symbol}",
            )
            return None

        # 2. Enforce Clock Drift Budget
        drift = (live_quote.event_at - now).total_seconds()
        if drift > self.config.max_clock_drift_seconds:
            self._halt(
                ShadowHaltReason.CLOCK_DRIFT,
                f"Quote timestamp is {drift:.3f}s in the future, exceeding clock drift allowance "
                f"of {self.config.max_clock_drift_seconds:.1f}s",
            )
            return None

        # 3. Quality Validation
        # A zero or negative side is an absent book, not a tradable price. Without this the
        # quote reached the risk governor, which refused it as MISSING_PRICE_FOR_RISK_VALUATION
        # and so blamed risk for what is a data-quality fault (S9-M1). Defence in depth: the
        # parser refuses these too, but a record can reach the runner without passing it.
        if live_quote.bid <= Decimal("0") or live_quote.ask <= Decimal("0"):
            self._halt(
                ShadowHaltReason.QUALITY_VIOLATION,
                f"Quote for {live_quote.symbol} carries no usable book: "
                f"bid={live_quote.bid}, ask={live_quote.ask}",
            )
            return None

        if live_quote.ask < live_quote.bid:
            self._halt(
                ShadowHaltReason.QUALITY_VIOLATION,
                f"Crossed quote: bid={live_quote.bid}, ask={live_quote.ask} for {live_quote.symbol}",
            )
            return None

        # 3b. Sequence integrity: a live stream must neither replay an event nor rewind a
        # symbol's clock. Both fabricate outcomes from a single market event (S9-M2, S9-M3).
        # Ordering is per symbol, because one multi-instrument message legitimately carries
        # several instruments stamped with the same event time.
        signature = (live_quote.symbol, live_quote.event_at, live_quote.bid, live_quote.ask)
        if signature in self._seen_quote_signatures:
            self._halt(
                ShadowHaltReason.DUPLICATE_TICK,
                f"Duplicate quote for {live_quote.symbol} at {live_quote.event_at.isoformat()}",
            )
            return None

        last_event_at = self._last_event_at_by_symbol.get(live_quote.symbol)
        if last_event_at is not None and live_quote.event_at < last_event_at:
            self._halt(
                ShadowHaltReason.OUT_OF_ORDER_TIMESTAMP,
                f"Quote for {live_quote.symbol} at {live_quote.event_at.isoformat()} "
                f"precedes the previous event at {last_event_at.isoformat()}",
            )
            return None

        self._seen_quote_signatures.add(signature)
        self._last_event_at_by_symbol[live_quote.symbol] = live_quote.event_at

        # 4. Check Risk Governor Kill Switch
        if self.risk_governor.is_killed:
            self._halt(
                ShadowHaltReason.RISK_KILL_SWITCH,
                "PreTradeRiskGovernor kill-switch triggered",
            )
            return None

        domain_quote = live_quote.to_domain_quote()
        self._last_quotes[domain_quote.symbol] = domain_quote

        # 5. Check Matured Outcomes on Existing Open Shadow Entries
        self._check_matured_outcomes(domain_quote, now)

        # 5b. Fill decisions taken on an earlier quote (never on their own quote — S9-B1)
        self._execute_pending_fills(domain_quote, now)

        # 6. Generate Strategy Signal & Shadow Decision
        if self.strategy is None:
            return None

        if (
            self.config.decision_cadence == DecisionCadence.ONCE_PER_SESSION
            and domain_quote.symbol in self._decided_symbols
        ):
            return None

        extra_data: dict[str, Any] = {"current_quote": domain_quote}
        provider = self.config.bar_history_provider
        if provider is not None:
            # Governed models score a completed daily bar, not the quote. The history is
            # point-in-time and already filtered to what was available by `now`; the strategy
            # filters again on receipt.
            extra_data[GOVERNED_BARS_KEY] = {
                domain_quote.symbol: provider(domain_quote.symbol, now)
            }
        context = MarketContext(
            current_time=now,
            current_bars={},
            historical_bars={},
            current_positions=dict(self._positions),
            available_cash=self._cash,
            extra_data=extra_data,
        )
        signals = self.strategy.generate_signals(context)
        if not signals:
            return None

        primary_signal = signals[0]
        if primary_signal.side is None:
            return None

        proposal_id = f"shadow_prop_{len(self._decisions) + 1}"
        quantity = self.config.default_order_quantity

        # Create theoretical Order object for pre-trade risk evaluation ONLY
        hypothetical_order = Order(
            order_id=proposal_id,
            symbol=domain_quote.symbol,
            side=primary_signal.side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            created_at=now,
            limit_price=domain_quote.ask if primary_signal.side == Side.BUY else domain_quote.bid,
        )

        risk_decision = self.risk_governor.evaluate_order(
            order=hypothetical_order,
            current_equity=self.current_equity,
            current_cash=self._cash,
            positions=self._positions,
            current_quote=domain_quote,
        )

        if risk_decision.approved:
            status = ShadowDecisionStatus.APPROVED
            risk_approved = True
            rejection_reason = None
        else:
            status = ShadowDecisionStatus.REJECTED_BY_RISK
            risk_approved = False
            rejection_reason = risk_decision.reason

        proposal = ShadowProposal(
            proposal_id=proposal_id,
            model_id=self.config.model_id,
            symbol=domain_quote.symbol,
            side=primary_signal.side,
            quantity=quantity,
            signal_strength=primary_signal.strength,
            quote_bid=domain_quote.bid,
            quote_ask=domain_quote.ask,
            quote_mid=domain_quote.mid_price,
            quote_timestamp=domain_quote.timestamp,
            decision_at=now,
            quote_latency_seconds=latency,
            risk_approved=risk_approved,
            status=status,
            rejection_reason=rejection_reason,
            resulting_leverage=risk_decision.resulting_leverage,
        )
        self._decisions.append(proposal)
        self._decided_symbols.add(domain_quote.symbol)

        if risk_approved:
            # A decision never fills against the quote that produced it. The fill is deferred
            # to the first later quote for this symbol, executed in _execute_pending_fills.
            self._pending_fills.setdefault(domain_quote.symbol, []).append(proposal)

        return proposal

    def _execute_pending_fills(self, current_quote: Quote, now: datetime) -> None:
        """Fill decisions taken on an earlier quote, at this quote's prices.

        Called after maturity and before the strategy is consulted, so an entry opened here
        cannot also mature here, and a decision taken later in this same quote cannot fill here.
        """
        pending = self._pending_fills.pop(current_quote.symbol, [])
        for proposal in pending:
            if proposal.side is None:
                continue
            exec_price = current_quote.ask if proposal.side == Side.BUY else current_quote.bid
            self._record_hypothetical_fill(
                symbol=proposal.symbol,
                side=proposal.side,
                quantity=proposal.quantity,
                price=exec_price,
            )
            self._open_entries[proposal.proposal_id] = (proposal, exec_price, now)

    def _record_hypothetical_fill(
        self, symbol: str, side: Side, quantity: int, price: Decimal
    ) -> None:
        """Update internal hypothetical shadow position and cash."""
        current_pos = self._positions.get(
            symbol, Position(symbol=symbol, quantity=0, average_price=Decimal("0"))
        )
        signed_qty = quantity if side == Side.BUY else -quantity
        new_qty = current_pos.quantity + signed_qty

        if side == Side.BUY:
            self._cash -= price * Decimal(quantity)
        else:
            self._cash += price * Decimal(quantity)

        if new_qty != 0:
            if current_pos.quantity == 0 or (
                (current_pos.quantity > 0 and signed_qty > 0)
                or (current_pos.quantity < 0 and signed_qty < 0)
            ):
                # Adding to position in same direction: weighted average price
                total_val = current_pos.average_price * Decimal(
                    abs(current_pos.quantity)
                ) + price * Decimal(quantity)
                avg_price = (total_val / Decimal(abs(new_qty))).quantize(_PAISA)
            elif (current_pos.quantity > 0 and new_qty > 0) or (
                current_pos.quantity < 0 and new_qty < 0
            ):
                # Partially reducing position: average price stays the same
                avg_price = current_pos.average_price
            else:
                # Position flipped: new average price is the fill price
                avg_price = price

            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=new_qty,
                average_price=avg_price,
            )
        else:
            self._positions.pop(symbol, None)

    def _may_mature(self, entry_time: datetime, now: datetime) -> bool:
        """Whether the configured horizon has elapsed for an entry filled at ``entry_time``.

        With no policy configured this is the pre-existing behaviour: any later same-symbol quote
        matures the entry.
        """
        policy = self.config.maturity_policy
        if policy is None:
            return True
        return now >= policy.matures_at(entry_time)

    def _halt_unresolvable_maturity(self, error: MaturityPolicyError) -> None:
        """Halt on a maturity that cannot be resolved, preserving the audit.

        The policy raises so a direct caller fails closed. Inside a session that raise escaped
        ``run_session`` entirely: state stayed RUNNING, no halt reason was set, decisions already
        taken were never written, and ``build_audit_report`` was never reached. Catching to report
        and halt is correct; catching to continue would not be.

        The detail deliberately carries no outcome figures. A handler that exists to report a
        failure must not emit a partial result, because the tempting later edit is to recover
        something computable under cover of the same handler.
        """
        self._halt(ShadowHaltReason.MATURITY_UNRESOLVABLE, str(error))

    # craft-allow: long-function — maturity settlement is one atomic Decimal accounting change.
    def _check_matured_outcomes(  # craft-allow: deep-nesting — loop, eligibility, and typed halt.
        self, current_quote: Quote, now: datetime
    ) -> None:
        """Mature open shadow entries against latest quote."""
        to_remove = []
        for prop_id, (prop, entry_price, entry_time) in self._open_entries.items():
            try:
                eligible = prop.symbol == current_quote.symbol and self._may_mature(entry_time, now)
            except MaturityPolicyError as error:
                self._halt_unresolvable_maturity(error)
                return
            if eligible:
                exit_price = current_quote.bid if prop.side == Side.BUY else current_quote.ask
                if prop.side == Side.BUY:
                    gross_pnl = (exit_price - entry_price) * Decimal(prop.quantity)
                else:
                    gross_pnl = (entry_price - exit_price) * Decimal(prop.quantity)

                from quant_system.backtest.costs import IndianMarketCostModel

                entry_cost = IndianMarketCostModel.calculate_equity_delivery(
                    side=prop.side or Side.BUY,
                    quantity=prop.quantity,
                    price=entry_price,
                    slippage_bps=0.0,
                )
                exit_side = Side.SELL if prop.side == Side.BUY else Side.BUY
                exit_cost = IndianMarketCostModel.calculate_equity_delivery(
                    side=exit_side,
                    quantity=prop.quantity,
                    price=exit_price,
                    slippage_bps=0.0,
                )
                friction_fee = entry_cost.total_fee + exit_cost.total_fee
                net_pnl = gross_pnl - friction_fee
                holding_seconds = (now - entry_time).total_seconds()

                outcome = ShadowMaturedOutcome(
                    outcome_id=f"outcome_{len(self._matured_outcomes) + 1}",
                    proposal_id=prop_id,
                    symbol=prop.symbol,
                    side=prop.side or Side.BUY,
                    quantity=prop.quantity,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    gross_pnl=gross_pnl,
                    friction_fee=friction_fee,
                    net_pnl=net_pnl,
                    entry_at=entry_time,
                    matured_at=now,
                    holding_seconds=holding_seconds,
                )
                # Close the hypothetical position the entry opened. Without this the same
                # market move is counted twice: once as unrealised mark-to-market on a
                # position that never closes, and again as realised net_pnl here.
                self._record_hypothetical_fill(
                    symbol=prop.symbol,
                    side=exit_side,
                    quantity=prop.quantity,
                    price=exit_price,
                )
                self._cash -= friction_fee

                self._matured_outcomes.append(outcome)
                to_remove.append(prop_id)

        for prop_id in to_remove:
            self._open_entries.pop(prop_id, None)

    # craft-allow: long-function — ordered feed failures map to distinct terminal session states.
    def run_session(  # craft-allow: deep-nesting — the streaming loop contains typed feed guards.
        self, max_quotes: int | None = None
    ) -> ShadowAuditReport:
        """Run the real-time shadow session loop, streaming from live feed and enforcing budgets."""
        self._started_at = require_aware_utc(self._clock())
        self.state = ShadowSessionState.RUNNING

        try:
            if not self.live_feed.is_authenticated:
                self._halt(
                    ShadowHaltReason.AUTH_EXPIRED,
                    "Live feed authentication is missing or expired.",
                    ShadowSessionState.UNAUTHORIZED,
                )
                return self.build_audit_report()

            if self.live_feed.state == FeedState.DISCONNECTED:
                self.live_feed.connect()
        except LiveFeedUnauthorizedError as err:
            self._halt(ShadowHaltReason.AUTH_EXPIRED, str(err), ShadowSessionState.UNAUTHORIZED)
            return self.build_audit_report()
        except LiveFeedConnectionError as err:
            self._halt(ShadowHaltReason.DISCONNECTED, str(err), ShadowSessionState.OFFLINE)
            return self.build_audit_report()
        except Exception as err:
            self._halt(ShadowHaltReason.FEED_ERROR, str(err), ShadowSessionState.SHADOW_HALTED)
            return self.build_audit_report()

        while max_quotes is None or self._quotes_processed < max_quotes:
            try:
                live_quote = self.live_feed.read_quote()
            except LiveFeedUnauthorizedError as err:
                self._halt(ShadowHaltReason.AUTH_EXPIRED, str(err), ShadowSessionState.UNAUTHORIZED)
                break
            except LiveFeedStaleQuoteError as err:
                self._halt(ShadowHaltReason.STALE_QUOTE, str(err), ShadowSessionState.SHADOW_HALTED)
                break
            except LiveFeedClockDriftError as err:
                self._halt(ShadowHaltReason.CLOCK_DRIFT, str(err), ShadowSessionState.SHADOW_HALTED)
                break
            except LiveFeedTimeoutError as err:
                self._halt(
                    ShadowHaltReason.FEED_TIMEOUT, str(err), ShadowSessionState.SHADOW_HALTED
                )
                break
            except LiveFeedConnectionError as err:
                self._halt(ShadowHaltReason.DISCONNECTED, str(err), ShadowSessionState.OFFLINE)
                break
            except LiveFeedQualityError as err:
                self._halt(
                    ShadowHaltReason.QUALITY_VIOLATION, str(err), ShadowSessionState.SHADOW_HALTED
                )
                break
            except LiveFeedError as err:
                self._halt(ShadowHaltReason.FEED_ERROR, str(err), ShadowSessionState.SHADOW_HALTED)
                break

            self.process_live_quote(live_quote)
            if self.state in {
                ShadowSessionState.SHADOW_HALTED,
                ShadowSessionState.OFFLINE,
                ShadowSessionState.UNAUTHORIZED,
            }:
                break

        if self.state == ShadowSessionState.RUNNING:
            self.state = ShadowSessionState.COMPLETED
            self._ended_at = require_aware_utc(self._clock())

        return self.build_audit_report()

    # craft-allow: long-function — hash payload and returned audit must remain visibly paired.
    def build_audit_report(self) -> ShadowAuditReport:
        """Construct canonical audit report with cryptographic digest."""
        now = require_aware_utc(self._clock())
        started_at = self._started_at or now
        ended_at = self._ended_at or now

        max_lat = max(self._latencies) if self._latencies else 0.0
        avg_lat = (sum(self._latencies) / len(self._latencies)) if self._latencies else 0.0

        approved_count = sum(1 for d in self._decisions if d.risk_approved)
        rejected_count = sum(1 for d in self._decisions if not d.risk_approved)

        manifest_data = {
            "session_id": self.config.session_id,
            "model_id": self.config.model_id,
            "started_at": utc_text(started_at),
            "ended_at": utc_text(ended_at),
            "final_state": self.state.value,
            "halt_reason": self.halt_reason.value if self.halt_reason else None,
            "halt_details": self.halt_details,
            "quotes_processed": self._quotes_processed,
            "proposals_generated": len(self._decisions),
            "proposals_approved": approved_count,
            "proposals_rejected": rejected_count,
            "broker_orders_submitted": self._broker_orders_submitted,
            "max_quote_latency_seconds": round(max_lat, 4),
            "avg_quote_latency_seconds": round(avg_lat, 4),
            "decisions": [d.canonical_dict() for d in self._decisions],
            "matured_outcomes": [m.canonical_dict() for m in self._matured_outcomes],
            "open_entries": len(self._open_entries),
            "open_symbols": sorted({p.symbol for p, _, _ in self._open_entries.values()}),
            "execution_mode": self.config.execution_mode,
        }
        audit_hash = canonical_sha256(manifest_data)

        return ShadowAuditReport(
            session_id=self.config.session_id,
            model_id=self.config.model_id,
            started_at=started_at,
            ended_at=ended_at,
            final_state=self.state,
            halt_reason=self.halt_reason,
            halt_details=self.halt_details,
            quotes_processed=self._quotes_processed,
            proposals_generated=len(self._decisions),
            proposals_approved=approved_count,
            proposals_rejected=rejected_count,
            broker_orders_submitted=self._broker_orders_submitted,
            max_quote_latency_seconds=max_lat,
            avg_quote_latency_seconds=avg_lat,
            decisions=tuple(self._decisions),
            matured_outcomes=tuple(self._matured_outcomes),
            open_entries=len(self._open_entries),
            open_symbols=tuple(sorted({p.symbol for p, _, _ in self._open_entries.values()})),
            audit_hash=audit_hash,
            execution_mode=self.config.execution_mode,
        )
