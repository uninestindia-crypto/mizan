"""Tests for Black-Scholes analytical option pricing, Greeks, and option chain features."""

import math
from datetime import date, datetime
from decimal import Decimal

from quant_system.alpha.greeks import BlackScholes
from quant_system.alpha.surface import VolatilitySurface
from quant_system.core.domain import InstrumentType
from quant_system.data.loader import SyntheticDataGenerator


def test_black_scholes_call_put_parity() -> None:
    spot = 100.0
    strike = 100.0
    t = 0.5
    vol = 0.20
    r = 0.05

    call_g = BlackScholes.calculate_greeks(spot, strike, t, vol, r, InstrumentType.OPTION_CALL)
    put_g = BlackScholes.calculate_greeks(spot, strike, t, vol, r, InstrumentType.OPTION_PUT)

    # Put-Call Parity: C - P = S - K * exp(-r*T)
    discounted_strike = strike * math.exp(-r * t)
    diff = (call_g.price - put_g.price) - (spot - discounted_strike)
    assert abs(diff) < 1e-4

    # Call delta should be in (0, 1), Put delta in (-1, 0)
    assert 0.0 < call_g.delta < 1.0
    assert -1.0 < put_g.delta < 0.0
    # Delta relationship: Delta_Call - Delta_Put = 1.0
    assert abs((call_g.delta - put_g.delta) - 1.0) < 1e-4

    # Gamma and Vega should be positive and equal
    assert call_g.gamma > 0
    assert abs(call_g.gamma - put_g.gamma) < 1e-6
    assert abs(call_g.vega - put_g.vega) < 1e-6


def test_black_scholes_at_expiration() -> None:
    greeks_itm = BlackScholes.calculate_greeks(
        105.0, 100.0, 0.0, 0.20, 0.05, InstrumentType.OPTION_CALL
    )
    assert greeks_itm.price == 5.0
    assert greeks_itm.delta == 1.0

    greeks_otm = BlackScholes.calculate_greeks(
        95.0, 100.0, 0.0, 0.20, 0.05, InstrumentType.OPTION_CALL
    )
    assert greeks_otm.price == 0.0
    assert greeks_otm.delta == 0.0


def test_implied_volatility_solver() -> None:
    spot = 24000.0
    strike = 24000.0
    t = 7.0 / 365.0
    true_vol = 0.18

    call_greeks = BlackScholes.calculate_greeks(
        spot, strike, t, true_vol, 0.07, InstrumentType.OPTION_CALL
    )
    market_price = call_greeks.price

    solved_iv = BlackScholes.implied_volatility(
        market_price, spot, strike, t, 0.07, InstrumentType.OPTION_CALL
    )
    assert abs(solved_iv - true_vol) < 1e-3


def test_option_chain_properties() -> None:
    chain = SyntheticDataGenerator.generate_option_chain(
        underlying="NIFTY",
        spot_price=Decimal("24510.00"),
        timestamp=datetime(2025, 1, 1, 9, 20),
        expiry=date(2025, 1, 8),
        strike_step=50,
        num_strikes=9,
    )

    assert chain.atm_strike == Decimal("24500.00")
    assert chain.put_call_ratio > 0.0
    assert chain.max_pain_strike is not None

    atm_iv = VolatilitySurface.extract_atm_iv(chain, 7.0 / 365.0)
    assert atm_iv > 0.0
