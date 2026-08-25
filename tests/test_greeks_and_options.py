"""Tests for Black-Scholes, Binomial CRR Greeks, IV Solver, and NSE Option Specifications."""

import math
from datetime import date, datetime
from decimal import Decimal

import pytest

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


# -------------------------------------------------------------------------
# Ring 5: G-4 regression — the lattice must compute its own gamma
# -------------------------------------------------------------------------


def test_binomial_american_call_gamma_matches_analytic() -> None:
    """G-4: the lattice gamma was wrong, and delegating European gamma to Black-Scholes hid it.

    An American call on a non-dividend-paying underlying is never optimally exercised early, so
    its gamma must equal the European analytic value. This case is not covered by the delegation,
    which is why it exposes the defective lattice.
    """
    spot, strike, t, vol, r = 100.0, 100.0, 1.0, 0.20, 0.05
    analytic = BlackScholes.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_CALL
    ).gamma
    american = BinomialOptionModel.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_CALL, ExerciseStyle.AMERICAN, 200
    ).gamma

    relative_error = abs(american - analytic) / analytic
    assert relative_error < 0.02, (
        f"American lattice gamma {american:.8f} differs from analytic {analytic:.8f} "
        f"by {relative_error * 100:.1f}%"
    )


def test_binomial_european_gamma_is_produced_by_the_lattice() -> None:
    """G-4: European gamma must come from the tree, not be substituted from Black-Scholes.

    A lattice approximation agreeing with the closed form to every bit is not an approximation;
    it is the closed form wearing the lattice's name.
    """
    spot, strike, t, vol, r = 100.0, 100.0, 1.0, 0.20, 0.05
    analytic = BlackScholes.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_CALL
    ).gamma
    european = BinomialOptionModel.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_CALL, ExerciseStyle.EUROPEAN, 200
    ).gamma

    assert abs(european - analytic) / analytic < 0.02, "lattice gamma must be accurate"
    assert european != analytic, "gamma was delegated to Black-Scholes rather than computed"


def test_binomial_put_gamma_matches_analytic() -> None:
    """G-4: gamma is symmetric across option type; puts must be right too."""
    spot, strike, t, vol, r = 100.0, 105.0, 0.5, 0.25, 0.05
    analytic = BlackScholes.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_PUT
    ).gamma
    lattice = BinomialOptionModel.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_PUT, ExerciseStyle.EUROPEAN, 200
    ).gamma
    assert abs(lattice - analytic) / analytic < 0.02


# -------------------------------------------------------------------------
# Ring 5: G-5 regression — an unknown lot size must not default to 1
# -------------------------------------------------------------------------


def test_lot_size_refuses_an_unknown_symbol() -> None:
    """G-5: unknown symbols returned lot size 1, so every quantity looked like a valid lot.

    A silent 1 means `validate_quantity` waves through 7 shares of an F&O contract whose real
    lot is 75.
    """
    with pytest.raises(ValueError, match="RELIANCE"):
        NSEContractConventions.get_lot_size("RELIANCE", date(2024, 6, 1))


def test_lot_size_refuses_a_date_before_the_table_starts() -> None:
    """G-5: a date the effective-dated table does not cover is unknown, not lot size 1."""
    with pytest.raises(ValueError, match="NIFTY"):
        NSEContractConventions.get_lot_size("NIFTY", date(1990, 1, 1))


def test_validate_quantity_refuses_an_unknown_symbol_rather_than_approving() -> None:
    """G-5: the fail-open default made validate_quantity return True for anything."""
    assert NSEContractConventions.validate_quantity("RELIANCE", 7, date(2024, 6, 1)) is False


def test_validate_quantity_still_accepts_a_correct_index_lot() -> None:
    """The repair must not refuse quantities that are genuinely valid."""
    assert NSEContractConventions.validate_quantity("NIFTY", 75, date(2024, 11, 25)) is True
    assert NSEContractConventions.validate_quantity("NIFTY", 70, date(2024, 11, 25)) is False


def test_american_put_gamma_converges_so_its_premium_is_real() -> None:
    """The American put's gamma differs from the European analytic value by ~22%.

    That is a large gap, and the honest question is whether it is the early-exercise premium or
    simply lattice error. Convergence separates the two: if refining the tree twentyfold barely
    moves the value, the number is what the model says and the gap is the premium.

    Written because this claim was flagged for independent review as one I was most likely to have
    got wrong. A converging value is evidence; an assertion in a commit message is not.
    """
    spot, strike, t, vol, r = 100.0, 100.0, 1.0, 0.20, 0.05

    coarse = BinomialOptionModel.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_PUT, ExerciseStyle.AMERICAN, 100
    ).gamma
    fine = BinomialOptionModel.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_PUT, ExerciseStyle.AMERICAN, 1000
    ).gamma

    drift = abs(fine - coarse) / fine
    assert drift < 0.01, (
        f"a tenfold refinement moved gamma by {drift:.2%}; the lattice has not converged, "
        "so no claim about the early-exercise premium can rest on it"
    )

    european = BlackScholes.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_PUT
    ).gamma
    premium = abs(fine - european) / european
    assert premium > 0.15, (
        f"American put gamma is only {premium:.2%} from the European value; if early exercise "
        "carried no premium here the comparison in the record would be wrong"
    )


def test_american_call_gamma_has_no_premium_over_european() -> None:
    """The control for the test above: a non-dividend American call is never exercised early.

    Without this, a converging American *put* number proves only that the lattice is stable, not
    that it is tracking early exercise. The call must show no premium for the put's premium to mean
    what the record says it means.
    """
    spot, strike, t, vol, r = 100.0, 100.0, 1.0, 0.20, 0.05
    american = BinomialOptionModel.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_CALL, ExerciseStyle.AMERICAN, 1000
    ).gamma
    european = BlackScholes.calculate_greeks(
        spot, strike, t, vol, r, InstrumentType.OPTION_CALL
    ).gamma
    assert abs(american - european) / european < 0.02
