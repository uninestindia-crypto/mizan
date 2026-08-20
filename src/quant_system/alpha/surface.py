"""Volatility surface interpolation, skew calculations, and term structure analytics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quant_system.alpha.greeks import BlackScholes
from quant_system.core.domain import InstrumentType
from quant_system.data.option_chain import OptionChain


@dataclass(frozen=True, slots=True)
class VolatilitySurface:
    """Extracts implied volatility features across strikes and expiries."""

    @staticmethod
    def extract_atm_iv(
        chain: OptionChain,
        time_to_expiry_years: float,
        risk_free_rate: float = 0.07,
    ) -> float:
        """Extracts the At-The-Money average implied volatility from the option chain."""
        atm_strike = chain.atm_strike
        strike_data = chain.strikes.get(atm_strike)
        if not strike_data:
            return 0.0

        ivs = []
        if strike_data.call and strike_data.call.mid_price > Decimal("0"):
            call_iv = BlackScholes.implied_volatility(
                market_price=float(strike_data.call.mid_price),
                spot=float(chain.spot_price),
                strike=float(atm_strike),
                time_to_expiry_years=time_to_expiry_years,
                risk_free_rate=risk_free_rate,
                option_type=InstrumentType.OPTION_CALL,
            )
            ivs.append(call_iv)

        if strike_data.put and strike_data.put.mid_price > Decimal("0"):
            put_iv = BlackScholes.implied_volatility(
                market_price=float(strike_data.put.mid_price),
                spot=float(chain.spot_price),
                strike=float(atm_strike),
                time_to_expiry_years=time_to_expiry_years,
                risk_free_rate=risk_free_rate,
                option_type=InstrumentType.OPTION_PUT,
            )
            ivs.append(put_iv)

        return sum(ivs) / len(ivs) if ivs else 0.0

    @staticmethod
    def calculate_skew_25delta(
        chain: OptionChain,
        time_to_expiry_years: float,
    ) -> float:
        """Calculates 25-delta Put IV minus 25-delta Call IV (measure of downside fear / crash premium)."""
        # Approximated via OTM Put vs OTM Call IV
        spot = float(chain.spot_price)
        otm_put_strike = min(chain.strikes.keys(), key=lambda k: abs(float(k) - (spot * 0.95)))
        otm_call_strike = min(chain.strikes.keys(), key=lambda k: abs(float(k) - (spot * 1.05)))

        put_data = chain.strikes.get(otm_put_strike)
        call_data = chain.strikes.get(otm_call_strike)

        put_iv = 0.20
        call_iv = 0.20

        if put_data and put_data.put:
            put_iv = BlackScholes.implied_volatility(
                market_price=float(put_data.put.mid_price),
                spot=spot,
                strike=float(otm_put_strike),
                time_to_expiry_years=time_to_expiry_years,
                option_type=InstrumentType.OPTION_PUT,
            )

        if call_data and call_data.call:
            call_iv = BlackScholes.implied_volatility(
                market_price=float(call_data.call.mid_price),
                spot=spot,
                strike=float(otm_call_strike),
                time_to_expiry_years=time_to_expiry_years,
                option_type=InstrumentType.OPTION_CALL,
            )

        return put_iv - call_iv
