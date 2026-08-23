"""Tests for Effective-Dated Indian Exchange Rule Engine (NSE/SEBI/Tax Rules)."""

from datetime import date
from decimal import Decimal

import pytest

from quant_system.analytics.nse_rules import (
    DatedExchangeRule,
    FeeComponent,
    MarketSegment,
    NSERuleEngine,
    RateBasis,
    RoundingMethod,
    SideBasis,
)
from quant_system.core.domain import Side


def test_nse_rule_engine_catalog_validity() -> None:
    """Verifies that canonical rule engine catalog initializes and has zero date overlaps."""
    engine = NSERuleEngine()
    assert len(engine.rules) > 10
    # Catalog validation should pass without error
    engine.validate_catalog()


def test_stt_futures_effective_date_transition_2024() -> None:
    """Tests the Finance (No. 2) Act 2024 STT hike from 0.0125% to 0.02% on 2024-10-01."""
    engine = NSERuleEngine()
    qty = 100
    price = Decimal("25000.00")  # Turnover = 2,500,000

    # 1. Day before hike: 2024-09-30 (STT = 0.0125% of 2.5M = ₹312.50)
    breakdown_old = engine.calculate_costs(
        segment=MarketSegment.EQUITY_FUTURES,
        side=Side.SELL,
        quantity=qty,
        price=price,
        trade_date=date(2024, 9, 30),
    )
    assert breakdown_old.applied_rule_ids["STT"] == "STT-FUT-20160601"
    assert breakdown_old.stt == Decimal("312.50")  # 2,500,000 * 0.000125 = 312.50

    # 2. Day of hike: 2024-10-01 (STT = 0.02% of 2.5M = ₹500.00)
    breakdown_new = engine.calculate_costs(
        segment=MarketSegment.EQUITY_FUTURES,
        side=Side.SELL,
        quantity=qty,
        price=price,
        trade_date=date(2024, 10, 1),
    )
    assert breakdown_new.applied_rule_ids["STT"] == "STT-FUT-20241001"
    assert breakdown_new.stt == Decimal("500.00")  # 2,500,000 * 0.000200 = 500.00


def test_stt_options_effective_date_transition_2024() -> None:
    """Tests options STT increase from 0.0625% to 0.10% on SELL premium on 2024-10-01."""
    engine = NSERuleEngine()
    qty = 500
    premium = Decimal("200.00")  # Premium Turnover = 100,000

    # 1. 2024-09-30: 0.0625% on 100k = ₹62.50
    breakdown_old = engine.calculate_costs(
        segment=MarketSegment.EQUITY_OPTIONS,
        side=Side.SELL,
        quantity=qty,
        price=premium,
        trade_date=date(2024, 9, 30),
    )
    assert breakdown_old.applied_rule_ids["STT"] == "STT-OPT-20230401"
    assert breakdown_old.stt == Decimal("62.50")

    # 2. 2024-10-01: 0.10% on 100k = ₹100.00
    breakdown_new = engine.calculate_costs(
        segment=MarketSegment.EQUITY_OPTIONS,
        side=Side.SELL,
        quantity=qty,
        price=premium,
        trade_date=date(2024, 10, 1),
    )
    assert breakdown_new.applied_rule_ids["STT"] == "STT-OPT-20241001"
    assert breakdown_new.stt == Decimal("100.00")

    # 3. Buy side options STT should be exactly 0
    breakdown_buy = engine.calculate_costs(
        segment=MarketSegment.EQUITY_OPTIONS,
        side=Side.BUY,
        quantity=qty,
        price=premium,
        trade_date=date(2024, 10, 1),
    )
    assert breakdown_buy.stt == Decimal("0.00")


def test_stamp_duty_uniform_rates_and_side_applicability() -> None:
    """Verifies Stamp Duty applies strictly to BUY side and follows statutory rates."""
    engine = NSERuleEngine()
    trade_date = date(2024, 6, 15)
    qty = 100
    price = Decimal("1000.00")  # Turnover = 100,000

    # Delivery BUY: 0.015% = ₹15.00
    del_buy = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=qty,
        price=price,
        trade_date=trade_date,
    )
    assert del_buy.stamp_duty == Decimal("15.00")

    # Delivery SELL: Stamp duty = 0
    del_sell = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.SELL,
        quantity=qty,
        price=price,
        trade_date=trade_date,
    )
    assert del_sell.stamp_duty == Decimal("0.00")

    # Intraday BUY: 0.003% = ₹3.00
    int_buy = engine.calculate_costs(
        segment=MarketSegment.EQUITY_INTRADAY,
        side=Side.BUY,
        quantity=qty,
        price=price,
        trade_date=trade_date,
    )
    assert int_buy.stamp_duty == Decimal("3.00")

    # Futures BUY: 0.002% = ₹2.00
    fut_buy = engine.calculate_costs(
        segment=MarketSegment.EQUITY_FUTURES,
        side=Side.BUY,
        quantity=qty,
        price=price,
        trade_date=trade_date,
    )
    assert fut_buy.stamp_duty == Decimal("2.00")


def test_sebi_turnover_charges_transition_2021() -> None:
    """Verifies SEBI turnover fee reduction from ₹15/crore to ₹10/crore on 2021-06-01."""
    engine = NSERuleEngine()
    qty = 1000
    price = Decimal("10000.00")  # Turnover = 10,000,000 (1 crore)

    # 1. 2021-05-31: ₹15/crore = ₹15.00
    res_old = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=qty,
        price=price,
        trade_date=date(2021, 5, 31),
    )
    assert res_old.applied_rule_ids["SEBI_TURNOVER"] == "SEBI-FEE-20140401"
    assert res_old.sebi_charges == Decimal("15.00")

    # 2. 2021-06-01: ₹10/crore = ₹10.00
    res_new = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=qty,
        price=price,
        trade_date=date(2021, 6, 1),
    )
    assert res_new.applied_rule_ids["SEBI_TURNOVER"] == "SEBI-FEE-20210601-DEL"
    assert res_new.sebi_charges == Decimal("10.00")


def test_exchange_turnover_uniform_structure_2024() -> None:
    """Verifies NSE revised exchange turnover charge structure effective 2024-10-01."""
    engine = NSERuleEngine()
    qty = 100
    price = Decimal("1000.00")  # Turnover = 100,000 (1 lakh)

    # Cash Delivery:
    # Prior: 0.00345% of 100k = ₹3.45
    del_old = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=qty,
        price=price,
        trade_date=date(2024, 9, 30),
    )
    assert del_old.exchange_turnover == Decimal("3.45")

    # Post 2024-10-01: 0.00297% of 100k = ₹2.97
    del_new = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=qty,
        price=price,
        trade_date=date(2024, 10, 1),
    )
    assert del_new.exchange_turnover == Decimal("2.97")


def test_gst_component_identity() -> None:
    """Verifies GST equals exactly 18% of (Brokerage + Exchange Turnover + SEBI)."""
    engine = NSERuleEngine()
    res = engine.calculate_costs(
        segment=MarketSegment.EQUITY_INTRADAY,
        side=Side.BUY,
        quantity=100,
        price=Decimal("1500.00"),  # Turnover = 150,000
        trade_date=date(2025, 1, 15),
    )
    # Brokerage: 0.05% of 150k = 75 capped at ₹20.00
    assert res.brokerage == Decimal("20.00")
    # Expected base = Brokerage + Exchange + SEBI
    expected_base = res.brokerage + res.exchange_turnover + res.sebi_charges
    expected_gst = (expected_base * Decimal("0.18")).quantize(Decimal("0.01"))
    assert res.gst == expected_gst


def test_cost_breakdown_deterministic_hash() -> None:
    """Verifies that cost calculations produce identical cryptographic hashes for identical inputs."""
    engine = NSERuleEngine()
    res1 = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=50,
        price=Decimal("2450.00"),
        trade_date=date(2025, 2, 10),
    )
    res2 = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=50,
        price=Decimal("2450.00"),
        trade_date=date(2025, 2, 10),
    )
    assert res1.calculation_hash == res2.calculation_hash
    assert len(res1.calculation_hash) == 64


def test_overlapping_catalog_rejection() -> None:
    """Verifies that an ambiguous or overlapping rule set is strictly rejected on validation."""
    rule1 = DatedExchangeRule(
        rule_id="RULE-1",
        component=FeeComponent.STT,
        source_ref="Ref 1",
        publication_date=date(2020, 1, 1),
        effective_from=date(2020, 1, 1),
        effective_to=date(2023, 12, 31),
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.001"),
        rate_basis=RateBasis.TURNOVER,
    )
    rule2_overlapping = DatedExchangeRule(
        rule_id="RULE-2",
        component=FeeComponent.STT,
        source_ref="Ref 2",
        publication_date=date(2023, 6, 1),
        effective_from=date(2023, 6, 1),  # Overlaps with rule1 (effective until end of 2023)
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.002"),
        rate_basis=RateBasis.TURNOVER,
    )
    with pytest.raises(ValueError, match="overlap/ambiguity detected"):
        NSERuleEngine(rules=[rule1, rule2_overlapping])


# -------------------------------------------------------------------------
# Ring 5: N-1 / N-2 regressions — declared rule fields must govern, and
# registration must not bypass the catalog validator
# -------------------------------------------------------------------------


def _brokerage_rule(
    *,
    minimum: Decimal | None = None,
    rounding_method: RoundingMethod = RoundingMethod.ROUND_HALF_UP_PAISA,
    rate: Decimal = Decimal("0.0000001"),
) -> DatedExchangeRule:
    return DatedExchangeRule(
        rule_id="brk_test_v1",
        component=FeeComponent.BROKERAGE,
        source_ref="test",
        publication_date=date(2024, 1, 1),
        effective_from=date(2024, 1, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=rate,
        rate_basis=RateBasis.TURNOVER,
        minimum=minimum,
        rounding_method=rounding_method,
    )


def test_declared_minimum_is_applied_not_merely_hashed() -> None:
    """N-1: `minimum` was hashed into rule_hash and never read, so a 1000.00 floor computed 0.33."""
    engine = NSERuleEngine()
    breakdown = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=100,
        price=Decimal("33.00"),
        trade_date=date(2024, 6, 1),
        custom_brokerage_rule=_brokerage_rule(minimum=Decimal("1000.00")),
    )
    assert breakdown.brokerage >= Decimal("1000.00"), (
        f"declared minimum of 1000.00 was ignored; brokerage came out {breakdown.brokerage}"
    )


def test_declared_rupee_rounding_is_applied() -> None:
    """N-1: `rounding_method` was declared and hashed, but every component rounded to the paisa."""
    engine = NSERuleEngine()
    breakdown = engine.calculate_costs(
        segment=MarketSegment.EQUITY_DELIVERY,
        side=Side.BUY,
        quantity=100,
        price=Decimal("33.33"),
        trade_date=date(2024, 6, 1),
        custom_brokerage_rule=_brokerage_rule(
            rate=Decimal("0.001"), rounding_method=RoundingMethod.ROUND_HALF_UP_RUPEE
        ),
    )
    assert breakdown.brokerage == breakdown.brokerage.quantize(Decimal("1")), (
        f"ROUND_HALF_UP_RUPEE was declared but brokerage kept paisa: {breakdown.brokerage}"
    )


def test_register_rule_refuses_a_rule_that_breaks_the_catalog() -> None:
    """N-2: register_rule bypassed validate_catalog, leaving the engine in a state it rejects."""
    engine = NSERuleEngine()
    existing = next(r for r in engine.rules if r.component == FeeComponent.STT)
    overlapping = DatedExchangeRule(
        rule_id="stt_overlap_test",
        component=existing.component,
        source_ref="test",
        publication_date=existing.effective_from,
        effective_from=existing.effective_from,
        effective_to=existing.effective_to,
        venue=existing.venue,
        segment=existing.segment,
        side_basis=existing.side_basis,
        rate=existing.rate,
        rate_basis=existing.rate_basis,
    )
    with pytest.raises(ValueError):
        engine.register_rule(overlapping)
    engine.validate_catalog()
