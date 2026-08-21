"""Tests for Black-Scholes, Binomial CRR Greeks, IV Solver, and NSE Option Specifications."""

import math
from datetime import date, datetime
from decimal import Decimal

from quant_system.analytics.greeks import (
    BinomialOptionModel,
    BlackScholes,
    ExerciseStyle,
    NSEContractConventions,
)
from quant_system.core.domain import InstrumentType


def test_black_scholes_call_put_parity() -> None:
    """Verifies Black-Scholes European Call-Put Parity: C - P = S - K * exp(-r*T)."""
    spot = 24500.0
    strike = 24500.0
    t = 30.0 / 365.0
    vol = 0.15
    r = 0.07

    call_g = BlackScholes.calculate_greeks(spot, strike, t, vol, r, InstrumentType.OPTION_CALL)
    put_g = BlackScholes.calculate_greeks(spot, strike, t, vol, r, InstrumentType.OPTION_PUT)

    discounted_strike = strike * math.exp(-r * t)
    parity_diff = (call_g.price - put_g.price) - (spot - discounted_strike)
    assert abs(parity_diff) < 1e-4

    # Delta identity: Delta_Call - Delta_Put = 1.0
    assert abs((call_g.delta - put_g.delta) - 1.0) < 1e-4
    assert 0.0 < call_g.delta < 1.0
    assert -1.0 < put_g.delta < 0.0

    # Gamma and Vega equality
    assert call_g.gamma > 0
    assert abs(call_g.gamma - put_g.gamma) < 1e-7
    assert abs(call_g.vega - put_g.vega) < 1e-7


def test_black_scholes_at_expiration() -> None:
    """Verifies payoff at expiration (T=0)."""
    call_itm = BlackScholes.calculate_greeks(
        105.0, 100.0, 0.0, 0.20, 0.05, InstrumentType.OPTION_CALL
    )
    assert call_itm.price == 5.0
    assert call_itm.delta == 1.0
    assert call_itm.gamma == 0.0

    call_otm = BlackScholes.calculate_greeks(
        95.0, 100.0, 0.0, 0.20, 0.05, InstrumentType.OPTION_CALL
    )
    assert call_otm.price == 0.0
    assert call_otm.delta == 0.0

    put_itm = BlackScholes.calculate_greeks(95.0, 100.0, 0.0, 0.20, 0.05, InstrumentType.OPTION_PUT)
    assert put_itm.price == 5.0
    assert put_itm.delta == -1.0


def test_binomial_crr_convergence_to_black_scholes() -> None:
    """Verifies that Binomial CRR price converges closely to Black-Scholes European price."""
    spot = 24000.0
    strike = 24200.0
    t = 45.0 / 365.0
    vol = 0.18
    r = 0.065

    bs_call = BlackScholes.calculate_greeks(spot, strike, t, vol, r, InstrumentType.OPTION_CALL)
    crr_call_price = BinomialOptionModel.price(
        spot, strike, t, vol, r, InstrumentType.OPTION_CALL, ExerciseStyle.EUROPEAN, steps=250
    )

    # CRR price should be within 0.1% of analytical Black-Scholes price
    assert abs(bs_call.price - crr_call_price) < 1.0


def test_binomial_american_early_exercise_premium() -> None:
    """Verifies that American Put with high interest rate is worth >= European Put."""
    spot = 80.0
    strike = 100.0  # Deep ITM Put
    t = 1.0
    vol = 0.20
    r = 0.10

    euro_put = BinomialOptionModel.price(
        spot, strike, t, vol, r, InstrumentType.OPTION_PUT, ExerciseStyle.EUROPEAN, steps=200
    )
    amer_put = BinomialOptionModel.price(
        spot, strike, t, vol, r, InstrumentType.OPTION_PUT, ExerciseStyle.AMERICAN, steps=200
    )

    # American put >= European put (due to early exercise right)
    assert amer_put >= euro_put
    assert amer_put >= (strike - spot)  # Immediate exercise value


def test_implied_volatility_solver() -> None:
    """Verifies Newton-Raphson + Bisection IV solver recovers true parameter within tight tolerance."""
    spot = 24500.0
    strike = 24500.0
    t = 14.0 / 365.0
    true_vol = 0.165
    r = 0.07

    greeks = BlackScholes.calculate_greeks(spot, strike, t, true_vol, r, InstrumentType.OPTION_CALL)
    market_price = greeks.price

    solved_iv = BlackScholes.implied_volatility(
        market_price, spot, strike, t, r, InstrumentType.OPTION_CALL
    )
    assert abs(solved_iv - true_vol) < 1e-4


def test_nse_contract_conventions_and_lot_sizes() -> None:
    """Verifies NSE effective-dated lot sizes and strike step validation."""
    # NIFTY lot sizes across eras
    assert NSEContractConventions.get_lot_size("NIFTY", date(2021, 1, 1)) == 75
    assert NSEContractConventions.get_lot_size("NIFTY", date(2023, 6, 1)) == 50
    assert NSEContractConventions.get_lot_size("NIFTY", date(2024, 6, 1)) == 25
    assert NSEContractConventions.get_lot_size("NIFTY", date(2024, 11, 25)) == 75

    # BANKNIFTY lot sizes
    assert NSEContractConventions.get_lot_size("BANKNIFTY", date(2023, 1, 1)) == 25
    assert NSEContractConventions.get_lot_size("BANKNIFTY", date(2024, 1, 1)) == 15
    assert NSEContractConventions.get_lot_size("BANKNIFTY", date(2024, 11, 25)) == 30

    # Strike step checks
    assert NSEContractConventions.validate_strike("NIFTY", Decimal("24500.00")) is True
    assert (
        NSEContractConventions.validate_strike("NIFTY", Decimal("24525.00")) is False
    )  # NIFTY step is 50
    assert NSEContractConventions.validate_strike("BANKNIFTY", Decimal("51200.00")) is True
    assert (
        NSEContractConventions.validate_strike("BANKNIFTY", Decimal("51250.00")) is False
    )  # BANKNIFTY step is 100

    # Lot quantity validation
    assert (
        NSEContractConventions.validate_quantity("NIFTY", 50, date(2024, 6, 1)) is True
    )  # 50 % 25 == 0
    assert NSEContractConventions.validate_quantity("NIFTY", 30, date(2024, 6, 1)) is False


def test_nse_time_to_expiry_act365() -> None:
    """Verifies Act/365 time-to-expiry calculation down to market close time."""
    now = datetime(2025, 1, 1, 9, 15, 0)
    expiry = date(2025, 1, 8)  # 7 days + 6h 15m
    t_years = NSEContractConventions.calculate_time_to_expiry_years(now, expiry)
    assert t_years > 0.0
    # Expected ~ 7.2604 days / 365
    assert abs(t_years - (7.0 + 6.25 / 24.0) / 365.0) < 1e-4
