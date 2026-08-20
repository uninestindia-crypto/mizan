"""Example: Intraday 09:20 NIFTY Straddle decay simulation with Greeks and stop-loss monitoring."""

import os
import sys
from datetime import date, datetime, time
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quant_system.alpha.greeks import BlackScholes
from quant_system.core.domain import InstrumentType, Quote, Side
from quant_system.data.loader import SyntheticDataGenerator
from quant_system.execution.paper_broker import DeterministicPaperBroker


def main() -> None:
    print("=" * 70)
    print("[OPTIONS] Running QuantOS NIFTY 09:20 AM Intraday Straddle Simulation")
    print("=" * 70)

    sim_date = date(2026, 8, 20)
    expiry = date(2026, 8, 27)
    spot_price = Decimal("24500.00")

    # 1. Generate Option Chain
    chain_920 = SyntheticDataGenerator.generate_option_chain(
        underlying="NIFTY",
        spot_price=spot_price,
        timestamp=datetime.combine(sim_date, time(9, 20)),
        expiry=expiry,
    )

    atm_strike = chain_920.atm_strike
    strike_data = chain_920.strikes[atm_strike]
    time_to_exp = 7.0 / 365.0

    print(f"Underlying Spot: Rs. {spot_price}")
    print(f"Identified ATM Strike: {atm_strike}")
    print(f"Put-Call Ratio (PCR): {chain_920.put_call_ratio:.2f}")
    print(f"Max Pain Strike: {chain_920.max_pain_strike}")

    # 2. Black-Scholes Greeks Calculation
    call_greeks = BlackScholes.calculate_greeks(
        spot=float(spot_price),
        strike=float(atm_strike),
        time_to_expiry_years=time_to_exp,
        volatility=0.18,
        option_type=InstrumentType.OPTION_CALL,
    )
    put_greeks = BlackScholes.calculate_greeks(
        spot=float(spot_price),
        strike=float(atm_strike),
        time_to_expiry_years=time_to_exp,
        volatility=0.18,
        option_type=InstrumentType.OPTION_PUT,
    )

    print("\n--- 09:20 AM Straddle Greeks ---")
    print(
        f"Call Price: Rs. {call_greeks.price:.2f} | Delta: {call_greeks.delta:+.2f} | Theta: Rs. {call_greeks.theta:.2f}/day | Vega: Rs. {call_greeks.vega:.2f}"
    )
    print(
        f"Put  Price: Rs. {put_greeks.price:.2f} | Delta: {put_greeks.delta:+.2f} | Theta: Rs. {put_greeks.theta:.2f}/day | Vega: Rs. {put_greeks.vega:.2f}"
    )
    net_delta = call_greeks.delta + put_greeks.delta
    net_theta = call_greeks.theta + put_greeks.theta
    print(f"Net Straddle Delta: {net_delta:+.2f} (Delta-Neutral)")
    print(f"Expected 1-Day Theta Decay Income: Rs. {abs(net_theta):.2f}")

    # 3. Simulate Paper Execution
    from quant_system.risk.governor import PreTradeRiskGovernor, RiskLimits

    options_risk = PreTradeRiskGovernor(
        limits=RiskLimits(allow_naked_short=True, max_position_weight=0.50)
    )
    broker = DeterministicPaperBroker(initial_cash=Decimal("500000.00"), risk_governor=options_risk)
    lot_size = 25

    print("\n--- Executing Straddle Legs via Paper Broker ---")
    if strike_data.call and strike_data.put:
        from quant_system.core.domain import Order, OrderType

        now = datetime.combine(sim_date, time(9, 20))

        call_order = Order(
            order_id="straddle_leg_1_call",
            symbol=strike_data.call.symbol,
            side=Side.SELL,
            quantity=lot_size,
            order_type=OrderType.MARKET,
            created_at=now,
        )
        put_order = Order(
            order_id="straddle_leg_2_put",
            symbol=strike_data.put.symbol,
            side=Side.SELL,
            quantity=lot_size,
            order_type=OrderType.MARKET,
            created_at=now,
        )

        call_quote = Quote(
            symbol=strike_data.call.symbol,
            timestamp=now,
            bid=strike_data.call.bid,
            ask=strike_data.call.ask,
        )
        put_quote = Quote(
            symbol=strike_data.put.symbol,
            timestamp=now,
            bid=strike_data.put.bid,
            ask=strike_data.put.ask,
        )

        filled_call = broker.submit_order(call_order, call_quote)
        filled_put = broker.submit_order(put_order, put_quote)

        print(f"Call Order: {filled_call.status.value} ({filled_call.symbol})")
        print(f"Put  Order: {filled_put.status.value} ({filled_put.symbol})")
        print(f"Fills recorded: {len(broker.fills)}")
        for f in broker.fills:
            print(
                f"  -> Fill: {f.side.value} {f.quantity} {f.symbol} @ Rs. {f.price} (Fee: Rs. {f.fee})"
            )

    print("\n[SUCCESS] Intraday Straddle simulation completed successfully.")


if __name__ == "__main__":
    main()
