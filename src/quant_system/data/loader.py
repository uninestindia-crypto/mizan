"""Synthetic and real-world market data loaders for deterministic backtesting and test fixtures."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from quant_system.core.domain import InstrumentType, PriceBar
from quant_system.data.bars import BarSeries
from quant_system.data.option_chain import OptionChain, OptionContract, OptionStrike


class SyntheticDataGenerator:
    """Generates deterministic geometric Brownian motion OHLCV bars and option chains."""

    @staticmethod
    def generate_equity_bars(
        symbol: str,
        start_date: date,
        days: int,
        initial_price: float = 1000.0,
        drift: float = 0.0005,
        volatility: float = 0.015,
        seed: int = 42,
    ) -> BarSeries:
        """Generates daily OHLCV bars using a deterministic pseudo-random seed."""
        bars: list[PriceBar] = []
        price = initial_price

        # Simple deterministic LCG random generator for reproducible test data without external state
        state = seed

        def next_rand() -> float:
            nonlocal state
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            return state / 0x7FFFFFFF

        current_dt = datetime.combine(start_date, time(9, 15))

        for _ in range(days):
            # Box-Muller transform for normal distribution
            u1 = max(1e-9, next_rand())
            u2 = next_rand()
            z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

            daily_return = drift + volatility * z
            new_price = max(1.0, price * (1.0 + daily_return))

            open_p = price
            close_p = new_price
            high_p = max(open_p, close_p) * (1.0 + (next_rand() * 0.005))
            low_p = min(open_p, close_p) * (1.0 - (next_rand() * 0.005))
            vol = int(100000 + next_rand() * 50000)

            o_dec = Decimal(str(round(open_p, 2)))
            c_dec = Decimal(str(round(close_p, 2)))
            raw_h = Decimal(str(round(high_p, 2)))
            raw_l = Decimal(str(round(low_p, 2)))
            h_dec = max(raw_h, o_dec, c_dec)
            l_dec = min(raw_l, o_dec, c_dec)

            bar = PriceBar(
                symbol=symbol,
                timestamp=current_dt,
                open=o_dec,
                high=h_dec,
                low=l_dec,
                close=c_dec,
                volume=vol,
            )
            bars.append(bar)
            price = new_price
            current_dt += timedelta(days=1)

        return BarSeries(symbol=symbol, bars=bars)

    @staticmethod
    def generate_option_chain(
        underlying: str,
        spot_price: Decimal,
        timestamp: datetime,
        expiry: date,
        strike_step: int = 50,
        num_strikes: int = 7,
    ) -> OptionChain:
        """Generates a synthetic option chain around the spot price."""
        atm_strike_val = round(float(spot_price) / strike_step) * strike_step
        half = num_strikes // 2
        strikes_map: dict[Decimal, OptionStrike] = {}

        for i in range(-half, half + 1):
            k = Decimal(str(atm_strike_val + (i * strike_step)))
            intrinsic_call = max(Decimal("0"), spot_price - k)
            intrinsic_put = max(Decimal("0"), k - spot_price)
            time_val = Decimal("150.0") / (Decimal("1") + (abs(spot_price - k) / Decimal("100")))

            call_mid = intrinsic_call + time_val
            put_mid = intrinsic_put + time_val

            call_contract = OptionContract(
                symbol=f"{underlying}{expiry.strftime('%y%b').upper()}{int(k)}CE",
                underlying=underlying,
                strike=k,
                expiry=expiry,
                option_type=InstrumentType.OPTION_CALL,
                bid=round(call_mid - Decimal("1.0"), 2),
                ask=round(call_mid + Decimal("1.0"), 2),
                last_price=round(call_mid, 2),
                volume=10000,
                open_interest=50000,
                implied_volatility=0.18,
            )

            put_contract = OptionContract(
                symbol=f"{underlying}{expiry.strftime('%y%b').upper()}{int(k)}PE",
                underlying=underlying,
                strike=k,
                expiry=expiry,
                option_type=InstrumentType.OPTION_PUT,
                bid=round(put_mid - Decimal("1.0"), 2),
                ask=round(put_mid + Decimal("1.0"), 2),
                last_price=round(put_mid, 2),
                volume=12000,
                open_interest=60000,
                implied_volatility=0.19,
            )

            strikes_map[k] = OptionStrike(strike=k, call=call_contract, put=put_contract)

        return OptionChain(
            underlying=underlying,
            spot_price=spot_price,
            timestamp=timestamp,
            expiry=expiry,
            strikes=strikes_map,
        )


class CsvBarDataLoader:
    """Loads historical OHLCV price bars from standard CSV data formats."""

    @staticmethod
    def load_bars_from_csv(
        file_path: str,
        symbol: str,
        timestamp_col: str = "timestamp",
        open_col: str = "open",
        high_col: str = "high",
        low_col: str = "low",
        close_col: str = "close",
        volume_col: str = "volume",
        date_format: str = "%Y-%m-%d %H:%M:%S",
    ) -> BarSeries:
        import csv
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV data file not found: {file_path}")

        bars: list[PriceBar] = []
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row[timestamp_col].strip()
                try:
                    ts = datetime.strptime(ts_str, date_format)
                except ValueError:
                    # Fallback to date only
                    ts = datetime.strptime(ts_str, "%Y-%m-%d")

                open_p = Decimal(str(row[open_col]).strip())
                high_p = Decimal(str(row[high_col]).strip())
                low_p = Decimal(str(row[low_col]).strip())
                close_p = Decimal(str(row[close_col]).strip())
                volume_val = int(float(str(row[volume_col]).strip()))

                bars.append(
                    PriceBar(
                        symbol=symbol,
                        timestamp=ts,
                        open=open_p,
                        high=high_p,
                        low=low_p,
                        close=close_p,
                        volume=volume_val,
                    )
                )

        bars.sort(key=lambda b: b.timestamp)
        return BarSeries(symbol=symbol, bars=bars)
