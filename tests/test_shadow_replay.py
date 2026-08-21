"""Comprehensive tests for recorded shadow replay, quote feed integrity, and zero broker write invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant_system.core.domain import Quote
from quant_system.execution.replay_feed import (
    FeedState,
    ReplayFeedError,
    ReplayFeedFailureCode,
    ReplayQuote,
    ReplayQuoteFeed,
)
from quant_system.execution.shadow_models import (
    RuleBasedShadowModel,
    ShadowExecutionMode,
    ShadowProposalStatus,
    ShadowSessionStatus,
)
from quant_system.execution.shadow_replay import ShadowReplayEngine
from quant_system.risk.checks import RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor

_BASE_TIME = datetime(2026, 8, 20, 9, 15, 0, tzinfo=UTC)


def _make_quotes(count: int = 10, spread_bps: int = 10) -> list[dict[str, object]]:
    """Helper to generate a clean chronological recorded quote stream."""
    quotes: list[dict[str, object]] = []
    base_price = Decimal("1000.00")
    spread_delta = (base_price * Decimal(str(spread_bps)) / Decimal("10000.0")).quantize(
        Decimal("0.01")
    )

    for i in range(count):
        ts = _BASE_TIME + timedelta(seconds=i)
        mid = base_price + Decimal(str(i * 0.5))
        bid = (mid - (spread_delta / Decimal("2"))).quantize(Decimal("0.01"))
        ask = (mid + (spread_delta / Decimal("2"))).quantize(Decimal("0.01"))
        quotes.append(
            {
                "symbol": "INFY",
                "timestamp": ts,
                "bid": bid,
                "ask": ask,
                "bid_size": 100,
                "ask_size": 100,
                "last_price": mid,
            }
        )
    return quotes


def _make_spaced_quotes(count: int = 5, spacing_ms: int = 100) -> list[dict[str, object]]:
    """Helper to generate quotes spaced by milliseconds."""
    quotes: list[dict[str, object]] = []
    for i in range(count):
        quotes.append(
            {
                "symbol": "INFY",
                "timestamp": _BASE_TIME + timedelta(milliseconds=i * spacing_ms),
                "bid": Decimal("1000.00"),
                "ask": Decimal("1001.00"),
                "bid_size": 100,
                "ask_size": 100,
            }
        )
    return quotes


def _make_option_quotes(count: int = 5) -> list[dict[str, object]]:
    """Helper to generate option quotes."""
    quotes: list[dict[str, object]] = []
    for i in range(count):
        quotes.append(
            {
                "symbol": "NIFTY24AUG24500CE",
                "timestamp": _BASE_TIME + timedelta(seconds=i),
                "bid": Decimal("150.00"),
                "ask": Decimal("151.00"),
                "bid_size": 25,
                "ask_size": 25,
            }
        )
    return quotes


def test_replay_feed_valid_stream() -> None:
    raw = _make_quotes(5)
    feed = ReplayQuoteFeed(raw)
    ticks = list(feed)

    assert len(ticks) == 5
    assert ticks[0].sequence_id == 1
    assert ticks[4].sequence_id == 5
    assert ticks[0].symbol == "INFY"
    assert ticks[0].bid == Decimal("999.50")
    assert ticks[0].ask == Decimal("1000.50")
    assert ticks[0].mid_price == Decimal("1000.00")
    assert ticks[0].spread == Decimal("1.00")
    assert ticks[0].spread_pct > Decimal("0")
    assert ticks[0].payload_digest != ""
    assert feed.state == FeedState.EXHAUSTED
    assert feed.total_emitted == 5


def test_replay_feed_to_domain_quote() -> None:
    quote = ReplayQuote(
        symbol="NIFTY",
        timestamp=_BASE_TIME,
        bid=Decimal("24000.00"),
        ask=Decimal("24005.00"),
        bid_size=50,
        ask_size=50,
        last_price=Decimal("24002.50"),
        sequence_id=1,
    )
    domain_q = quote.to_domain_quote()
    assert isinstance(domain_q, Quote)
    assert domain_q.symbol == "NIFTY"
    assert domain_q.bid == Decimal("24000.00")
    assert domain_q.ask == Decimal("24005.00")


def test_replay_feed_direct_quote_and_replayquote_inputs() -> None:
    domain_q = Quote(
        symbol="TCS",
        timestamp=_BASE_TIME,
        bid=Decimal("3500.00"),
        ask=Decimal("3502.00"),
    )
    replay_q = ReplayQuote(
        symbol="TCS",
        timestamp=_BASE_TIME + timedelta(seconds=1),
        bid=Decimal("3501.00"),
        ask=Decimal("3503.00"),
        sequence_id=2,
    )
    feed = ReplayQuoteFeed([domain_q, replay_q])
    ticks = list(feed)
    assert len(ticks) == 2
    assert ticks[0].symbol == "TCS"
    assert ticks[1].symbol == "TCS"


def test_replay_feed_schema_violation_missing_fields() -> None:
    bad_dict = {"symbol": "INFY", "timestamp": _BASE_TIME}
    feed = ReplayQuoteFeed([bad_dict])
    with pytest.raises(ReplayFeedError) as exc_info:
        feed.next_tick()
    assert exc_info.value.code == ReplayFeedFailureCode.SCHEMA_VIOLATION


def test_replay_feed_schema_violation_unsupported_type() -> None:
    feed = ReplayQuoteFeed([12345])  # type: ignore[list-item]
    with pytest.raises(ReplayFeedError) as exc_info:
        feed.next_tick()
    assert exc_info.value.code == ReplayFeedFailureCode.SCHEMA_VIOLATION


def test_replay_feed_out_of_order_timestamp() -> None:
    raw = _make_quotes(3)
    raw[1]["timestamp"] = _BASE_TIME - timedelta(seconds=10)

    feed = ReplayQuoteFeed(raw)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)

    assert exc_info.value.code == ReplayFeedFailureCode.OUT_OF_ORDER_TIMESTAMP
    assert feed.state == FeedState.HALTED
    assert feed.halt_reason is not None


def test_replay_feed_duplicate_tick() -> None:
    raw = _make_quotes(3)
    raw[1]["timestamp"] = raw[0]["timestamp"]
    raw[1]["bid"] = raw[0]["bid"]
    raw[1]["ask"] = raw[0]["ask"]

    feed = ReplayQuoteFeed(raw)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)

    assert exc_info.value.code == ReplayFeedFailureCode.DUPLICATE_TICK
    assert feed.state == FeedState.HALTED


def test_replay_feed_crossed_book() -> None:
    raw = _make_quotes(2)
    raw[0]["bid"] = Decimal("1005.00")
    raw[0]["ask"] = Decimal("1000.00")

    feed = ReplayQuoteFeed(raw)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)

    assert exc_info.value.code == ReplayFeedFailureCode.CROSSED_BOOK
    assert feed.state == FeedState.HALTED


def test_replay_feed_zero_liquidity() -> None:
    raw = _make_quotes(2)
    raw[0]["bid"] = Decimal("0.00")
    raw[0]["ask"] = Decimal("0.00")

    feed = ReplayQuoteFeed(raw)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)

    assert exc_info.value.code == ReplayFeedFailureCode.ZERO_LIQUIDITY
    assert feed.state == FeedState.HALTED


def test_replay_feed_corrupted_payload_float_rejected() -> None:
    raw = _make_quotes(2)
    raw[0]["bid"] = 999.50

    feed = ReplayQuoteFeed(raw)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)

    assert exc_info.value.code == ReplayFeedFailureCode.CORRUPTED_PAYLOAD
    assert feed.state == FeedState.HALTED


def test_replay_feed_corrupted_payload_negative_price() -> None:
    raw = _make_quotes(2)
    raw[0]["bid"] = Decimal("-10.00")

    feed = ReplayQuoteFeed(raw)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)

    assert exc_info.value.code == ReplayFeedFailureCode.CORRUPTED_PAYLOAD


def test_replay_feed_corrupted_payload_negative_size() -> None:
    raw = _make_quotes(2)
    raw[0]["bid_size"] = -5

    feed = ReplayQuoteFeed(raw)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)

    assert exc_info.value.code == ReplayFeedFailureCode.CORRUPTED_PAYLOAD


def test_replay_feed_max_spread_pct_breach() -> None:
    raw = _make_quotes(2, spread_bps=500)
    feed = ReplayQuoteFeed(raw, max_spread_pct=0.02)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)
    assert exc_info.value.code == ReplayFeedFailureCode.CROSSED_BOOK


def test_replay_feed_staleness_detection() -> None:
    raw = _make_quotes(3)
    raw[1]["timestamp"] = _BASE_TIME + timedelta(seconds=60)

    feed = ReplayQuoteFeed(raw, max_allowed_staleness_seconds=5.0)
    with pytest.raises(ReplayFeedError) as exc_info:
        list(feed)

    assert exc_info.value.code == ReplayFeedFailureCode.STALE_QUOTE
    assert feed.state == FeedState.HALTED


def test_replay_feed_manual_halt_and_reset() -> None:
    raw = _make_quotes(5)
    feed = ReplayQuoteFeed(raw)
    t1 = feed.next_tick()
    assert t1.sequence_id == 1

    feed.halt("OPERATOR_INTERRUPT")
    assert feed.state == FeedState.HALTED
    with pytest.raises(ReplayFeedError) as exc_info:
        feed.next_tick()
    assert exc_info.value.code == ReplayFeedFailureCode.FEED_HALTED

    feed.reset()
    assert feed.state.value == FeedState.READY.value
    assert feed.total_emitted == 0
    t1_again = feed.next_tick()
    assert t1_again.sequence_id == 1


def test_replay_feed_disconnect_simulation() -> None:
    raw = _make_quotes(5)
    feed = ReplayQuoteFeed(raw)
    tick1 = feed.next_tick()
    assert tick1.sequence_id == 1

    feed.simulate_disconnect("SIMULATED_CARRIER_DROP")
    with pytest.raises(ReplayFeedError) as exc_info:
        feed.next_tick()

    assert exc_info.value.code == ReplayFeedFailureCode.FEED_OFFLINE
    assert feed.state == FeedState.OFFLINE


def test_shadow_replay_zero_broker_writes() -> None:
    raw = _make_quotes(10)
    feed = ReplayQuoteFeed(raw)
    model = RuleBasedShadowModel(model_id="rule_v1", target_state="SHADOW")
    engine = ShadowReplayEngine(session_id="sess_zero_write", model=model)

    audit = engine.run(feed)

    assert audit.mode == ShadowExecutionMode.SHADOW_READ_ONLY.value
    assert audit.broker_write_calls == 0
    assert engine.broker_write_calls == 0
    assert audit.status == ShadowSessionStatus.COMPLETED
    assert len(engine.proposals) > 0
    assert len(engine.fills) > 0


def test_shadow_replay_unapproved_model_state_halt() -> None:
    raw = _make_quotes(5)
    feed = ReplayQuoteFeed(raw)
    model = RuleBasedShadowModel(model_id="rule_v1", target_state="RESEARCH_ONLY")
    engine = ShadowReplayEngine(session_id="sess_unapproved", model=model)

    audit = engine.run(feed)

    assert audit.status == ShadowSessionStatus.HALTED
    assert audit.halt_reason is not None
    assert "MODEL_NOT_IN_SHADOW_STATE" in audit.halt_reason
    assert audit.proposals_total == 0


def test_shadow_replay_point_in_time_sequencing_and_latency() -> None:
    quotes = _make_spaced_quotes(count=5, spacing_ms=100)
    feed = ReplayQuoteFeed(quotes)
    model = RuleBasedShadowModel(
        model_id="rule_v1",
        target_state="SHADOW",
        spread_threshold_pct=0.01,
        trade_quantity=10,
    )
    engine = ShadowReplayEngine(
        session_id="sess_pit_latency",
        model=model,
        decision_latency=timedelta(milliseconds=20),
        execution_latency=timedelta(milliseconds=10),
    )

    audit = engine.run(feed)

    assert audit.status == ShadowSessionStatus.COMPLETED
    assert len(engine.proposals) > 0
    p0 = engine.proposals[0]
    assert p0.trigger_quote_seq == 1
    assert p0.decision_timestamp == _BASE_TIME + timedelta(milliseconds=20)
    assert p0.status == ShadowProposalStatus.FILLED
    assert p0.fill is not None
    assert p0.fill.timestamp == _BASE_TIME + timedelta(milliseconds=100)


def test_shadow_replay_pretrade_risk_rejection() -> None:
    raw = _make_quotes(5)
    feed = ReplayQuoteFeed(raw)
    tight_limits = RiskLimits(max_position_weight=0.0001)
    gov = PreTradeRiskGovernor(limits=tight_limits)

    model = RuleBasedShadowModel(
        model_id="rule_v1",
        target_state="SHADOW",
        trade_quantity=1000,
    )
    engine = ShadowReplayEngine(
        session_id="sess_risk_rej",
        model=model,
        risk_governor=gov,
        initial_cash=Decimal("100000.00"),
    )

    audit = engine.run(feed)

    assert audit.status == ShadowSessionStatus.COMPLETED
    assert audit.proposals_rejected > 0
    rej_props = [p for p in engine.proposals if p.status == ShadowProposalStatus.REJECTED]
    assert len(rej_props) > 0
    assert rej_props[0].rejection_reason is not None
    assert "POSITION_WEIGHT_LIMIT_EXCEEDED" in rej_props[0].rejection_reason


def test_shadow_replay_options_friction_calculation() -> None:
    quotes = _make_option_quotes(count=5)
    feed = ReplayQuoteFeed(quotes)
    model = RuleBasedShadowModel(
        model_id="opt_rule_v1",
        target_state="SHADOW",
        spread_threshold_pct=0.02,
        trade_quantity=25,
    )
    engine = ShadowReplayEngine(
        session_id="sess_options",
        model=model,
        initial_cash=Decimal("500000.00"),
    )
    audit = engine.run(feed)

    assert audit.status == ShadowSessionStatus.COMPLETED
    assert audit.proposals_filled > 0
    filled_prop = [p for p in engine.proposals if p.status == ShadowProposalStatus.FILLED][0]
    assert filled_prop.cost_breakdown is not None
    assert filled_prop.cost_breakdown.brokerage == Decimal("20.00")
    assert filled_prop.cost_breakdown.total_fee > Decimal("0.00")


def test_shadow_replay_exact_decimal_ledger_reconciliation() -> None:
    raw = _make_quotes(15)
    feed = ReplayQuoteFeed(raw)
    model = RuleBasedShadowModel(
        model_id="rule_v1",
        target_state="SHADOW",
        trade_quantity=5,
        spread_threshold_pct=0.01,
    )
    engine = ShadowReplayEngine(
        session_id="sess_reconcile",
        model=model,
        initial_cash=Decimal("500000.00"),
    )

    audit = engine.run(feed)

    assert audit.reconciled is True
    assert engine.ledger.reconcile() is True
    computed_cash = engine.ledger.initial_cash + sum(
        tx.cash_delta for tx in engine.ledger.transactions
    )
    assert computed_cash == engine.ledger.cash
    assert audit.total_equity == audit.final_cash + sum(
        pos.current_market_value(Decimal("1007.00")) for pos in engine.ledger.positions.values()
    )


def test_shadow_replay_matured_outcome_attribution() -> None:
    raw = _make_quotes(12)
    feed = ReplayQuoteFeed(raw)
    model = RuleBasedShadowModel(
        model_id="rule_v1",
        target_state="SHADOW",
        trade_quantity=10,
        spread_threshold_pct=0.01,
    )
    engine = ShadowReplayEngine(
        session_id="sess_matured",
        model=model,
        maturity_horizon_quotes=3,
    )

    audit = engine.run(feed)

    assert audit.matured_decisions_count > 0
    matured_proposals = [p for p in engine.proposals if p.matured_outcome is not None]
    assert len(matured_proposals) > 0
    mat = matured_proposals[0].matured_outcome
    assert mat is not None
    assert mat.attribution_quote_seq >= matured_proposals[0].trigger_quote_seq + 3
    assert mat.realized_price > Decimal("0")


def test_shadow_replay_fail_closed_on_corrupted_feed_mid_session() -> None:
    raw = _make_quotes(10)
    raw[5]["bid"] = Decimal("-50.00")

    feed = ReplayQuoteFeed(raw)
    model = RuleBasedShadowModel(model_id="rule_v1", target_state="SHADOW")
    engine = ShadowReplayEngine(session_id="sess_corrupt_stream", model=model)

    audit = engine.run(feed)

    assert audit.status == ShadowSessionStatus.HALTED
    assert audit.halt_reason is not None
    assert "CORRUPTED_PAYLOAD" in audit.halt_reason
    assert audit.quotes_processed == 5
    assert audit.proposals_pending == 0
    assert engine.ledger.reconcile() is True


def test_shadow_replay_deterministic_reproducibility() -> None:
    raw = _make_quotes(10)
    model1 = RuleBasedShadowModel(model_id="rule_v1", target_state="SHADOW")
    model2 = RuleBasedShadowModel(model_id="rule_v1", target_state="SHADOW")

    feed1 = ReplayQuoteFeed(raw)
    engine1 = ShadowReplayEngine(session_id="sess_det_1", model=model1)
    audit1 = engine1.run(feed1)

    feed2 = ReplayQuoteFeed(raw)
    engine2 = ShadowReplayEngine(session_id="sess_det_1", model=model2)
    audit2 = engine2.run(feed2)

    assert audit1.audit_hash == audit2.audit_hash
    assert audit1.final_cash == audit2.final_cash
    assert audit1.proposals_total == audit2.proposals_total
    assert audit1.proposals_filled == audit2.proposals_filled
    assert len(engine1.fills) == len(engine2.fills)
