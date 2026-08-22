"""Governed Option Pricing, Greeks Engine, Binomial Trees, and NSE Contract Conventions.

Implements analytical Black-Scholes and lattice Binomial (CRR) option pricing models,
Greeks (Delta, Gamma, Theta, Vega, Rho), robust IV solvers, and effective-dated
NSE expiry conventions, lot sizes, and strike increments.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import StrEnum

from quant_system.core.domain import InstrumentType

_PAISA = Decimal("0.01")
_EXPIRY_MARKET_CLOSE_TIME = time(15, 30, 0)


class ExerciseStyle(StrEnum):
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"


@dataclass(frozen=True, slots=True)
class OptionGreeks:
    """Immutable first- and second-order option Greeks."""

    price: float
    delta: float
    gamma: float
    theta: float  # 1-day calendar theta decay (per 1 day / 365)
    vega: float  # 1% volatility move sensitivity (0.01 * dV/dσ)
    rho: float  # 1% interest rate move sensitivity (0.01 * dV/dr)
    implied_volatility: float | None = None
    model: str = "BLACK_SCHOLES"


@dataclass(frozen=True, slots=True)
class NSELotSizeRecord:
    """Effective-dated lot size record for NSE derivative contracts."""

    symbol: str
    lot_size: int
    effective_from: date
    effective_to: date | None


# Canonical NSE Index lot size history
_CANONICAL_LOT_SIZES: list[NSELotSizeRecord] = [
    # NIFTY
    NSELotSizeRecord("NIFTY", 75, date(2000, 6, 12), date(2021, 10, 14)),
    NSELotSizeRecord("NIFTY", 50, date(2021, 10, 15), date(2024, 4, 25)),
    NSELotSizeRecord("NIFTY", 25, date(2024, 4, 26), date(2024, 11, 19)),
    NSELotSizeRecord("NIFTY", 75, date(2024, 11, 20), None),
    # BANKNIFTY
    NSELotSizeRecord("BANKNIFTY", 25, date(2016, 7, 1), date(2023, 6, 30)),
    NSELotSizeRecord("BANKNIFTY", 15, date(2023, 7, 1), date(2024, 11, 19)),
    NSELotSizeRecord("BANKNIFTY", 30, date(2024, 11, 20), None),
    # FINNIFTY
    NSELotSizeRecord("FINNIFTY", 40, date(2021, 1, 11), date(2024, 4, 25)),
    NSELotSizeRecord("FINNIFTY", 25, date(2024, 4, 26), date(2024, 11, 19)),
    NSELotSizeRecord("FINNIFTY", 65, date(2024, 11, 20), None),
    # MIDCPNIFTY
    NSELotSizeRecord("MIDCPNIFTY", 75, date(2022, 1, 24), date(2024, 4, 25)),
    NSELotSizeRecord("MIDCPNIFTY", 50, date(2024, 4, 26), date(2024, 11, 19)),
    NSELotSizeRecord("MIDCPNIFTY", 120, date(2024, 11, 20), None),
]

_CANONICAL_STRIKE_STEPS: dict[str, Decimal] = {
    "NIFTY": Decimal("50.00"),
    "BANKNIFTY": Decimal("100.00"),
    "FINNIFTY": Decimal("50.00"),
    "MIDCPNIFTY": Decimal("25.00"),
}


class NSEContractConventions:
    """NSE index and stock derivative specifications and expiry calculations."""

    @classmethod
    def get_lot_size(cls, symbol: str, trade_date: date) -> int:
        """Retrieves exact effective-dated lot size for an NSE underlying."""
        sym_clean = symbol.upper().split("-")[0]
        for rec in _CANONICAL_LOT_SIZES:
            if rec.symbol == sym_clean and rec.effective_from <= trade_date:
                if rec.effective_to is None or trade_date <= rec.effective_to:
                    return rec.lot_size
        # Fallback default for unknown / single stock if not in index list
        return 1

    @classmethod
    def get_strike_step(cls, symbol: str) -> Decimal:
        """Returns the canonical strike increment for an NSE underlying."""
        sym_clean = symbol.upper().split("-")[0]
        return _CANONICAL_STRIKE_STEPS.get(sym_clean, Decimal("50.00"))

    @classmethod
    def validate_strike(cls, symbol: str, strike: Decimal) -> bool:
        """Validates that a strike is positive and a multiple of the valid strike step."""
        if strike <= Decimal("0"):
            return False
        step = cls.get_strike_step(symbol)
        remainder = strike % step
        return remainder == Decimal("0.00") or remainder == Decimal("0")

    @classmethod
    def validate_quantity(cls, symbol: str, quantity: int, trade_date: date) -> bool:
        """Validates that order quantity is a positive multiple of the active lot size."""
        if quantity <= 0:
            return False
        lot_size = cls.get_lot_size(symbol, trade_date)
        return quantity % lot_size == 0

    @classmethod
    def calculate_time_to_expiry_years(
        cls,
        current_time: datetime,
        expiry_date: date,
        market_close_hour: int = 15,
        market_close_minute: int = 30,
    ) -> float:
        """Calculates exact Act/365 year fraction to expiry time (15:30 IST on expiry date)."""
        ist = timezone(timedelta(hours=5, minutes=30), name="IST")
        expiry_dt = datetime.combine(
            expiry_date,
            time(market_close_hour, market_close_minute, 0),
            tzinfo=ist,
        )
        if current_time.tzinfo is None:
            curr = current_time.replace(tzinfo=ist)
        else:
            curr = current_time.astimezone(ist)
        delta_seconds = (expiry_dt - curr).total_seconds()
        if delta_seconds <= 0:
            return 0.0
        # Act/365 year fraction
        return delta_seconds / (365.0 * 86400.0)


class BlackScholes:
    """Analytical European option pricer and Greeks engine under Black-Scholes-Merton (1973)."""

    @staticmethod
    def _norm_cdf(x: float) -> float:
        """Standard normal cumulative distribution function."""
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    @staticmethod
    def _norm_pdf(x: float) -> float:
        """Standard normal probability density function."""
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    @classmethod
    def calculate_greeks(
        cls,
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        volatility: float,
        risk_free_rate: float = 0.07,  # Default 7% benchmark (RBI Repo / MIBOR)
        option_type: InstrumentType = InstrumentType.OPTION_CALL,
    ) -> OptionGreeks:
        """Computes exact analytical Black-Scholes price and first/second-order Greeks."""
        if spot <= 0.0:
            raise ValueError(f"Spot price must be > 0, got {spot}")
        if strike <= 0.0:
            raise ValueError(f"Strike price must be > 0, got {strike}")

        # At or past expiration
        if time_to_expiry_years <= 0.0:
            if option_type == InstrumentType.OPTION_CALL:
                intrinsic = max(0.0, spot - strike)
                delta = 1.0 if spot > strike else (0.5 if spot == strike else 0.0)
            else:
                intrinsic = max(0.0, strike - spot)
                delta = -1.0 if strike > spot else (-0.5 if spot == strike else 0.0)
            return OptionGreeks(
                price=intrinsic,
                delta=delta,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
                implied_volatility=volatility,
                model="BLACK_SCHOLES",
            )

        if volatility <= 0.0:
            # Zero volatility: deterministic forward discounted payoff
            discount = math.exp(-risk_free_rate * time_to_expiry_years)
            forward = spot / discount
            if option_type == InstrumentType.OPTION_CALL:
                price = max(0.0, spot - strike * discount)
                delta = 1.0 if forward > strike else 0.0
            else:
                price = max(0.0, strike * discount - spot)
                delta = -1.0 if forward < strike else 0.0
            return OptionGreeks(
                price=price,
                delta=delta,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
                implied_volatility=volatility,
                model="BLACK_SCHOLES",
            )

        sqrt_t = math.sqrt(time_to_expiry_years)
        d1 = (
            math.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry_years
        ) / (volatility * sqrt_t)
        d2 = d1 - volatility * sqrt_t

        pdf_d1 = cls._norm_pdf(d1)
        cdf_d1 = cls._norm_cdf(d1)
        cdf_d2 = cls._norm_cdf(d2)
        cdf_neg_d1 = cls._norm_cdf(-d1)
        cdf_neg_d2 = cls._norm_cdf(-d2)

        discount = math.exp(-risk_free_rate * time_to_expiry_years)

        # Gamma and Vega are identical for Calls and Puts
        gamma = pdf_d1 / (spot * volatility * sqrt_t)
        vega = (spot * pdf_d1 * sqrt_t) / 100.0  # 1% vol shift (0.01 * dV/dσ)

        if option_type == InstrumentType.OPTION_CALL:
            price = (spot * cdf_d1) - (strike * discount * cdf_d2)
            delta = cdf_d1
            theta = (
                -(spot * pdf_d1 * volatility) / (2.0 * sqrt_t)
                - (risk_free_rate * strike * discount * cdf_d2)
            ) / 365.0  # 1-day theta
            rho = (strike * time_to_expiry_years * discount * cdf_d2) / 100.0  # 1% rate shift
        else:
            price = (strike * discount * cdf_neg_d2) - (spot * cdf_neg_d1)
            delta = cdf_d1 - 1.0
            theta = (
                -(spot * pdf_d1 * volatility) / (2.0 * sqrt_t)
                + (risk_free_rate * strike * discount * cdf_neg_d2)
            ) / 365.0
            rho = (-strike * time_to_expiry_years * discount * cdf_neg_d2) / 100.0

        return OptionGreeks(
            price=max(0.0, price),
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            implied_volatility=volatility,
            model="BLACK_SCHOLES",
        )

    @classmethod
    def implied_volatility(
        cls,
        market_price: float,
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        risk_free_rate: float = 0.07,
        option_type: InstrumentType = InstrumentType.OPTION_CALL,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> float:
        """Solves for Implied Volatility (IV) using Newton-Raphson with robust Bisection fallback."""
        if spot <= 0 or strike <= 0 or time_to_expiry_years <= 0:
            return 0.0001

        discount = math.exp(-risk_free_rate * time_to_expiry_years)
        intrinsic = (
            max(0.0, spot - strike * discount)
            if option_type == InstrumentType.OPTION_CALL
            else max(0.0, strike * discount - spot)
        )
        if market_price <= intrinsic:
            return 0.0001

        # Upper bound: spot for call, strike * discount for put
        max_theoretical = spot if option_type == InstrumentType.OPTION_CALL else strike * discount
        if market_price >= max_theoretical:
            return 5.0

        # 1. Newton-Raphson iterations
        sigma = 0.25  # Starting guess at 25% annualized volatility
        for _ in range(max_iterations):
            greeks = cls.calculate_greeks(
                spot, strike, time_to_expiry_years, sigma, risk_free_rate, option_type
            )
            diff = greeks.price - market_price

            if abs(diff) < tolerance:
                return sigma

            raw_vega = greeks.vega * 100.0  # Unscaled vega dV/dσ
            if abs(raw_vega) < 1e-10:
                break

            step = diff / raw_vega
            sigma -= step

            if sigma <= 0.0001 or sigma >= 5.0:
                break

        # 2. Bisection fallback
        low_vol = 0.0001
        high_vol = 5.0
        for _ in range(64):
            mid_vol = 0.5 * (low_vol + high_vol)
            mid_price = cls.calculate_greeks(
                spot, strike, time_to_expiry_years, mid_vol, risk_free_rate, option_type
            ).price
            diff = mid_price - market_price

            if abs(diff) < tolerance or (high_vol - low_vol) < 1e-6:
                return mid_vol

            if diff > 0:
                high_vol = mid_vol
            else:
                low_vol = mid_vol

        return 0.5 * (low_vol + high_vol)


class BinomialOptionModel:
    """Cox-Ross-Rubinstein (CRR) discrete lattice model for European and American options."""

    @classmethod
    def price(
        cls,
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        volatility: float,
        risk_free_rate: float = 0.07,
        option_type: InstrumentType = InstrumentType.OPTION_CALL,
        exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN,
        steps: int = 200,
    ) -> float:
        """Prices an option using the CRR binomial lattice with backward induction."""
        if spot <= 0.0 or strike <= 0.0:
            raise ValueError(f"Spot and strike must be > 0 (got S={spot}, K={strike})")
        if time_to_expiry_years <= 0.0:
            if option_type == InstrumentType.OPTION_CALL:
                return max(0.0, spot - strike)
            return max(0.0, strike - spot)
        if volatility <= 0.0:
            discount = math.exp(-risk_free_rate * time_to_expiry_years)
            if exercise_style == ExerciseStyle.EUROPEAN:
                if option_type == InstrumentType.OPTION_CALL:
                    return max(0.0, spot - strike * discount)
                return max(0.0, strike * discount - spot)
            else:
                if option_type == InstrumentType.OPTION_CALL:
                    return max(0.0, spot - strike)
                return max(0.0, strike - spot)

        dt = time_to_expiry_years / float(steps)
        u = math.exp(volatility * math.sqrt(dt))
        d = 1.0 / u
        disc = math.exp(-risk_free_rate * dt)
        if u == d:
            p = 0.5
        else:
            p = (math.exp(risk_free_rate * dt) - d) / (u - d)

        # CRR stability guard for very low volatility / steps
        if p < 0.0 or p > 1.0:
            if exercise_style == ExerciseStyle.EUROPEAN:
                return BlackScholes.calculate_greeks(
                    spot,
                    strike,
                    time_to_expiry_years,
                    max(0.0001, volatility),
                    risk_free_rate,
                    option_type,
                ).price
            p = max(0.0, min(1.0, p))

        # Boundary condition: terminal asset prices and payoffs
        values = [0.0] * (steps + 1)
        for i in range(steps + 1):
            s_terminal = spot * (u ** (steps - i)) * (d**i)
            if option_type == InstrumentType.OPTION_CALL:
                values[i] = max(0.0, s_terminal - strike)
            else:
                values[i] = max(0.0, strike - s_terminal)

        # Backward induction
        for step in range(steps - 1, -1, -1):
            for i in range(step + 1):
                continuation = disc * (p * values[i] + (1.0 - p) * values[i + 1])
                if exercise_style == ExerciseStyle.AMERICAN:
                    s_current = spot * (u ** (step - i)) * (d**i)
                    intrinsic = (
                        max(0.0, s_current - strike)
                        if option_type == InstrumentType.OPTION_CALL
                        else max(0.0, strike - s_current)
                    )
                    values[i] = max(continuation, intrinsic)
                else:
                    values[i] = continuation

        return max(0.0, values[0])

    @classmethod
    def calculate_greeks(
        cls,
        spot: float,
        strike: float,
        time_to_expiry_years: float,
        volatility: float,
        risk_free_rate: float = 0.07,
        option_type: InstrumentType = InstrumentType.OPTION_CALL,
        exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN,
        steps: int = 200,
    ) -> OptionGreeks:
        """Computes price and numerical Greeks (Delta, Gamma, Theta, Vega, Rho) via lattice shifts."""
        base_price = cls.price(
            spot,
            strike,
            time_to_expiry_years,
            volatility,
            risk_free_rate,
            option_type,
            exercise_style,
            steps,
        )
        if time_to_expiry_years <= 0.0:
            if option_type == InstrumentType.OPTION_CALL:
                delta = 1.0 if spot > strike else 0.0
            else:
                delta = -1.0 if strike > spot else 0.0
            return OptionGreeks(
                price=base_price,
                delta=delta,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
                model="BINOMIAL",
            )

        # For European options, analytical Black-Scholes gamma provides exact benchmark
        if exercise_style == ExerciseStyle.EUROPEAN and volatility > 0.0:
            bs = BlackScholes.calculate_greeks(
                spot, strike, time_to_expiry_years, volatility, risk_free_rate, option_type
            )
            gamma = bs.gamma
        else:
            h_s = max(0.01, spot * 0.01)
            p_up = cls.price(
                spot + h_s,
                strike,
                time_to_expiry_years,
                volatility,
                risk_free_rate,
                option_type,
                exercise_style,
                steps,
            )
            p_down = cls.price(
                spot - h_s,
                strike,
                time_to_expiry_years,
                volatility,
                risk_free_rate,
                option_type,
                exercise_style,
                steps,
            )
            gamma = (p_up - 2.0 * base_price + p_down) / (h_s * h_s)

        # Delta via central difference
        h_s = max(0.01, spot * 0.005)
        p_up = cls.price(
            spot + h_s,
            strike,
            time_to_expiry_years,
            volatility,
            risk_free_rate,
            option_type,
            exercise_style,
            steps,
        )
        p_down = cls.price(
            spot - h_s,
            strike,
            time_to_expiry_years,
            volatility,
            risk_free_rate,
            option_type,
            exercise_style,
            steps,
        )
        delta = (p_up - p_down) / (2.0 * h_s)

        # Theta via 1-day time reduction
        dt_1d = 1.0 / 365.0
        t_next = max(0.0, time_to_expiry_years - dt_1d)
        p_next = cls.price(
            spot, strike, t_next, volatility, risk_free_rate, option_type, exercise_style, steps
        )
        theta = p_next - base_price

        # Vega via 1% vol shift
        p_vol_up = cls.price(
            spot,
            strike,
            time_to_expiry_years,
            volatility + 0.01,
            risk_free_rate,
            option_type,
            exercise_style,
            steps,
        )
        vega = p_vol_up - base_price

        # Rho via 1% rate shift
        p_rate_up = cls.price(
            spot,
            strike,
            time_to_expiry_years,
            volatility,
            risk_free_rate + 0.01,
            option_type,
            exercise_style,
            steps,
        )
        rho = p_rate_up - base_price

        return OptionGreeks(
            price=base_price,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            implied_volatility=volatility,
            model="BINOMIAL",
        )
