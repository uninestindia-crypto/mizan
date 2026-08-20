"""Black-Scholes analytical option pricing, Greeks calculations, and Newton-Raphson IV solver."""

from __future__ import annotations

import math
from dataclasses import dataclass

from quant_system.core.domain import InstrumentType


@dataclass(frozen=True, slots=True)
class OptionGreeks:
    price: float
    delta: float
    gamma: float
    theta: float  # 1-day theta decay
    vega: float  # 1% vol change impact
    rho: float


class BlackScholes:
    """Analytical European option pricer and Greeks engine."""

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
        risk_free_rate: float = 0.07,  # Default 7% RBI / US Treasury benchmark
        option_type: InstrumentType = InstrumentType.OPTION_CALL,
    ) -> OptionGreeks:
        """Computes exact analytical Black-Scholes price and first/second-order Greeks."""
        if time_to_expiry_years <= 0:
            # At expiration
            if option_type == InstrumentType.OPTION_CALL:
                intrinsic = max(0.0, spot - strike)
                delta = 1.0 if spot > strike else 0.0
            else:
                intrinsic = max(0.0, strike - spot)
                delta = -1.0 if strike > spot else 0.0
            return OptionGreeks(
                price=intrinsic, delta=delta, gamma=0.0, theta=0.0, vega=0.0, rho=0.0
            )

        if volatility <= 0 or spot <= 0 or strike <= 0:
            raise ValueError(
                f"Spot, strike, and volatility must be > 0 (got S={spot}, K={strike}, vol={volatility})"
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
        vega = spot * pdf_d1 * sqrt_t / 100.0  # 1% vol shift

        if option_type == InstrumentType.OPTION_CALL:
            price = (spot * cdf_d1) - (strike * discount * cdf_d2)
            delta = cdf_d1
            theta = (
                -(spot * pdf_d1 * volatility) / (2.0 * sqrt_t)
                - (risk_free_rate * strike * discount * cdf_d2)
            ) / 365.0
            rho = (strike * time_to_expiry_years * discount * cdf_d2) / 100.0
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
        tolerance: float = 1e-5,
    ) -> float:
        """Solves for Implied Volatility (IV) using Newton-Raphson with robust bisection fallback."""
        if spot <= 0 or strike <= 0 or time_to_expiry_years <= 0:
            return 0.001

        intrinsic = (
            max(0.0, spot - strike)
            if option_type == InstrumentType.OPTION_CALL
            else max(0.0, strike - spot)
        )
        if market_price <= intrinsic:
            return 0.001  # Lower bound

        # 1. First attempt: Newton-Raphson
        sigma = 0.25  # Initial 25% guess
        for _ in range(max_iterations):
            greeks = cls.calculate_greeks(
                spot, strike, time_to_expiry_years, sigma, risk_free_rate, option_type
            )
            diff = greeks.price - market_price

            if abs(diff) < tolerance:
                return sigma

            vega_raw = greeks.vega * 100.0  # Unscaled vega
            if abs(vega_raw) < 1e-8:
                # Flat derivative; switch to bisection
                break

            step = diff / vega_raw
            sigma -= step
            if sigma <= 0.001 or sigma >= 5.0:
                # Out of bounds; switch to bisection
                break

        # 2. Robust Bisection Fallback
        low_vol = 0.001
        high_vol = 5.0
        for _ in range(60):
            mid_vol = 0.5 * (low_vol + high_vol)
            mid_price = cls.calculate_greeks(
                spot, strike, time_to_expiry_years, mid_vol, risk_free_rate, option_type
            ).price
            diff = mid_price - market_price

            if abs(diff) < tolerance or (high_vol - low_vol) < 1e-5:
                return mid_vol

            if diff > 0:
                high_vol = mid_vol
            else:
                low_vol = mid_vol

        return 0.5 * (low_vol + high_vol)
