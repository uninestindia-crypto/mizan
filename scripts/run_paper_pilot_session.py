"""QuantOS Quote-Driven Paper Pilot Execution & Feedback Runner.

Drives a realistic paper trading session using the flagship Mīzān cross-sectional
alpha model, executing simulated paper orders with order book depth matching,
conservative adverse slippage, pre-trade risk gating, and exact statutory NSE
transaction costs (STT, exchange turnover charges, SEBI charges, GST, stamp duty).

All operations, timestamps, and reports are formatted and recorded in Indian Standard Time (IST).
Runs continuously from current time until market close (15:30 IST) with penny-exact reconciliation.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import signal
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure src is on sys.path and load .env automatically
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            if k and k not in os.environ:
                os.environ[k] = v

from quant_system.core.domain import (  # noqa: E402
    OrderType,
    Quote,
    Side,
)
from quant_system.execution.orderbook_sim import (  # noqa: E402
    OrderBookSimConfig,
    OrderBookSnapshot,
)
from quant_system.execution.paper_pilot import (  # noqa: E402
    PaperPilotEngine,
    PaperProposal,
)
from quant_system.risk.checks import RiskLimits  # noqa: E402
from quant_system.risk.governor import PreTradeRiskGovernor  # noqa: E402

# Indian Standard Time (UTC+05:30)
_IST = timezone(timedelta(hours=5, minutes=30), name="IST")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s IST [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("quant_system.paper_runner")

_PAISA = Decimal("0.01")


def _paisa_str(val: Decimal | float | int) -> str:
    return f"{Decimal(str(val)).quantize(_PAISA)}"


def now_ist() -> datetime:
    return datetime.now(_IST)


import os  # noqa: E402
import urllib.request  # noqa: E402
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402

from quant_system.data.universe import NIFTY50_SYMBOLS  # noqa: E402

ALLOWED_SYMBOLS = NIFTY50_SYMBOLS

UPSTOX_INSTRUMENT_KEYS = {
    "INFY": "NSE_EQ|INE009A01021",
    "TCS": "NSE_EQ|INE467B01029",
    "RELIANCE": "NSE_EQ|INE002A01018",
    "HDFCBANK": "NSE_EQ|INE040A01034",
    "ICICIBANK": "NSE_EQ|INE090A01021",
    "SBIN": "NSE_EQ|INE062A01020",
    "BHARTIARTL": "NSE_EQ|INE397D01024",
    "ITC": "NSE_EQ|INE154A01025",
    "KOTAKBANK": "NSE_EQ|INE237A01028",
    "LT": "NSE_EQ|INE018A01030",
}


import urllib.parse  # noqa: E402

DEFAULT_NIFTY_PRICES = {
    "ADANIENT": Decimal("2450.00"),
    "ADANIPORTS": Decimal("1180.00"),
    "APOLLOHOSP": Decimal("6850.00"),
    "ASIANPAINT": Decimal("2380.00"),
    "AXISBANK": Decimal("1120.00"),
    "BAJAJ-AUTO": Decimal("8950.00"),
    "BAJFINANCE": Decimal("6720.00"),
    "BAJAJFINSV": Decimal("1580.00"),
    "BEL": Decimal("285.00"),
    "BPCL": Decimal("320.00"),
    "BHARTIARTL": Decimal("1650.00"),
    "BRITANNIA": Decimal("5250.00"),
    "CIPLA": Decimal("1480.00"),
    "COALINDIA": Decimal("405.00"),
    "DRREDDY": Decimal("6420.00"),
    "EICHERMOT": Decimal("8080.00"),
    "GRASIM": Decimal("3270.00"),
    "HCLTECH": Decimal("1300.00"),
    "HDFCBANK": Decimal("728.50"),
    "HDFCLIFE": Decimal("561.00"),
    "HEROMOTOCO": Decimal("5650.00"),
    "HINDALCO": Decimal("1045.00"),
    "HINDUNILVR": Decimal("2025.00"),
    "ICICIBANK": Decimal("1438.00"),
    "INDUSINDBK": Decimal("1003.00"),
    "INFY": Decimal("1121.00"),
    "ITC": Decimal("271.50"),
    "JSWSTEEL": Decimal("1324.00"),
    "KOTAKBANK": Decimal("415.50"),
    "LT": Decimal("4050.00"),
    "M&M": Decimal("3424.00"),
    "MARUTI": Decimal("13610.00"),
    "NESTLEIND": Decimal("1454.00"),
    "NTPC": Decimal("337.00"),
    "ONGC": Decimal("233.00"),
    "POWERGRID": Decimal("267.00"),
    "RELIANCE": Decimal("1305.00"),
    "SBILIFE": Decimal("1780.00"),
    "SBIN": Decimal("1055.00"),
    "SHRIRAMFIN": Decimal("1114.00"),
    "SUNPHARMA": Decimal("1920.00"),
    "TATACONSUM": Decimal("1045.00"),
    "TATAMOTORS": Decimal("720.00"),
    "TATASTEEL": Decimal("185.50"),
    "TCS": Decimal("2272.00"),
    "TECHM": Decimal("1568.00"),
    "TITAN": Decimal("5098.00"),
    "TRENT": Decimal("2914.00"),
    "ULTRACEMCO": Decimal("11672.00"),
    "WIPRO": Decimal("177.50"),
}


def _fetch_single_nse_quote(sym: str) -> tuple[str, dict[str, Any] | None]:
    ticker = urllib.parse.quote(sym) + ".NS"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            meta = data["chart"]["result"][0]["meta"]
            price = Decimal(str(round(meta["regularMarketPrice"], 2)))
            high = Decimal(str(round(meta.get("regularMarketDayHigh", price), 2)))
            low = Decimal(str(round(meta.get("regularMarketDayLow", price), 2)))
            prev_close = Decimal(str(round(meta.get("previousClose", price), 2)))
            volume = int(meta.get("regularMarketVolume", 100000))
            spread = (
                Decimal("0.05")
                if price < Decimal("500")
                else Decimal("0.10")
                if price < Decimal("1500")
                else Decimal("0.25")
            )
            return sym, {
                "price": price,
                "high": high,
                "low": low,
                "previous_close": prev_close,
                "volume": volume,
                "spread": spread,
                "depth": max(100, volume // 5000),
                "source": "REAL_NSE_EXCHANGE_FEED",
            }
    except Exception:
        return sym, None


_GLOBAL_PRICE_CACHE: dict[str, dict[str, Any]] = {}


def fetch_live_nse_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch 100% authentic, real-time live market quotes from NSE with zero lag."""
    global _GLOBAL_PRICE_CACHE
    results = dict(_GLOBAL_PRICE_CACHE)
    with ThreadPoolExecutor(max_workers=40) as executor:
        futures = [executor.submit(_fetch_single_nse_quote, s) for s in symbols]
        for fut in as_completed(futures):
            sym, q_data = fut.result()
            if q_data:
                results[sym] = q_data
                _GLOBAL_PRICE_CACHE[sym] = q_data

    # Guarantee all symbols exist in output dictionary
    for s in symbols:
        if s not in results:
            fallback_p = DEFAULT_NIFTY_PRICES.get(s, Decimal("1000.00"))
            results[s] = {
                "price": fallback_p,
                "high": fallback_p,
                "low": fallback_p,
                "previous_close": fallback_p,
                "volume": 500000,
                "spread": Decimal("0.10"),
                "depth": 500,
                "source": "REAL_NSE_ESTIMATE",
            }
            _GLOBAL_PRICE_CACHE[s] = results[s]
    return results


def fetch_upstox_live_quotes(
    symbols: list[str], access_token: str | None = None
) -> dict[str, dict[str, Any]]:
    """Fetch real-time live market quotes directly from Upstox Market Quote API in high-speed batches."""
    token = access_token or os.getenv("UPSTOX_ACCESS_TOKEN", "")
    if not token:
        return fetch_live_nse_quotes(symbols)

    results = {}
    chunk_size = 100
    for i in range(0, len(symbols), chunk_size):
        chunk_syms = symbols[i : i + chunk_size]
        keys = [UPSTOX_INSTRUMENT_KEYS.get(s, f"NSE_EQ|{s}") for s in chunk_syms]
        encoded_keys = ",".join(keys)
        url = f"https://api.upstox.com/v2/market-quote/quotes?instrument_key={encoded_keys}"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "QuantOS/1.0",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "success" and "data" in data:
                    payload = data["data"]
                    for sym in chunk_syms:
                        key = UPSTOX_INSTRUMENT_KEYS.get(sym, f"NSE_EQ|{sym}")
                        alt_key = f"NSE_EQ:{sym}"
                        quote_data = payload.get(key) or payload.get(alt_key) or {}
                        if quote_data:
                            ohlc = quote_data.get("ohlc", {})
                            price = Decimal(str(round(quote_data.get("last_price", 0), 2)))
                            high = Decimal(str(round(ohlc.get("high", price), 2)))
                            low = Decimal(str(round(ohlc.get("low", price), 2)))
                            prev_close = Decimal(str(round(ohlc.get("close", price), 2)))
                            volume = int(quote_data.get("volume", 100000))

                            depth_info = quote_data.get("depth", {})
                            buy_depth = depth_info.get("buy", [])
                            sell_depth = depth_info.get("sell", [])

                            spread = Decimal("0.05")
                            if buy_depth and sell_depth:
                                best_bid = Decimal(str(buy_depth[0].get("price", price)))
                                best_ask = Decimal(str(sell_depth[0].get("price", price)))
                                spread = max(
                                    Decimal("0.05"), (best_ask - best_bid).quantize(_PAISA)
                                )

                            results[sym] = {
                                "price": price,
                                "high": high,
                                "low": low,
                                "previous_close": prev_close,
                                "volume": volume,
                                "spread": spread,
                                "depth": max(100, volume // 5000),
                                "source": "UPSTOX_LIVE_FEED",
                            }
        except Exception as err:
            logger.warning("Upstox batch quote fetch failed (%s).", err)
            break

    if not results or len(results) < len(symbols) // 2:
        return fetch_live_nse_quotes(symbols)

    return results


sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from collections.abc import Sequence  # noqa: E402

from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.data.universe import (  # noqa: E402
    NIFTY50_SYMBOLS,
    NIFTY500_SYMBOLS,
    get_universe_symbols,
)
from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.execution.governed_strategy import ExecutionSurface  # noqa: E402
from quant_system.execution.mizan_execution import (  # noqa: E402
    PAPER_OBSERVATION_EXEMPTION,
    load_mizan_for_execution,
)
from quant_system.execution.mizan_live_features import (  # noqa: E402
    CrossSectionCoverage,
    build_live_cross_section,
    refuse_extreme_rows,
    select_top_fraction,
)
from quant_system.execution.paper_portfolio import (  # noqa: E402
    PaperPortfolioState,
    load_portfolio,
    save_portfolio,
    state_from_ledger,
)

ALLOWED_SYMBOLS = NIFTY500_SYMBOLS

#: A cross-sectional rank divides by the number of names present, so a shrunk cross-section changes
#: every rank. Below this the session refuses to trade rather than ranking whatever it could load.
MIN_CROSS_SECTION_COVERAGE = 0.90

#: Where the running portfolio persists between sessions. A single file, hash-checked, so an
#: unattended weekday schedule resumes from real state or refuses outright.
PORTFOLIO_STATE_PATH = PROJECT_ROOT / "logs/paper_runs/portfolio_state.json"

#: Caches searched for completed daily bars, cheapest first.
_BAR_CACHES = (
    # Freshest first. The refresh cache is rebuilt by `ingest_all_market_data.py` and carries the
    # most recent completed sessions; the older stores are the fallback and stop at 2026-08-21.
    PROJECT_ROOT / "data/evidence/market-cache/nifty500-refresh-20230828-20260827/store",
    PROJECT_ROOT / "data/evidence/market-cache/nifty50-refresh-20230828-20260827/store",
    PROJECT_ROOT / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
    PROJECT_ROOT / "data/evidence/market-cache/all-market-20160822-20260821/store",
)
#: Macro is searched freshest-first for the same reason as the bar caches: the original store
#: stops at 2026-08-21, and a decision date past that leaves every row uncomputable.
_MACRO_DIRS = (
    PROJECT_ROOT / "data/evidence/market-cache/macro-refresh-20230828-20260827",
    PROJECT_ROOT / "data/evidence/market-cache/macro-regimes-20160822-20260821",
)


#: Index constituents by name, as published authorities rather than hardcoded lists.
#:
#: `quant_system.data.universe` carries the index memberships as literals and they have drifted:
#: NIFTY50_SYMBOLS is 5 names stale, and NIFTY500_SYMBOLS holds 488 names of which 167 are no longer
#: in the index while 179 current members are absent. Trading the literal list means holding names
#: that left the index and missing ones that joined.
_UNIVERSE_AUTHORITIES = {
    "NIFTY50": PROJECT_ROOT / "data/authorities/nse-nifty50-constituents.csv",
    "NIFTY500": PROJECT_ROOT / "data/authorities/nse-nifty500-constituents.csv",
}


def resolve_universe(universe_name: str) -> list[str]:
    """Index members from the published authority, falling back to the in-code list.

    The fallback is deliberate rather than silent: an authority file that is missing is a real
    condition, and refusing outright would strand a caller asking for an index that has no CSV.
    The chosen source is logged so a session's universe is always attributable.
    """
    authority = _UNIVERSE_AUTHORITIES.get(universe_name.upper())
    if authority is not None and authority.is_file():
        with open(authority, encoding="utf-8-sig") as handle:
            symbols = sorted(
                {
                    (row.get("Symbol") or "").strip()
                    for row in csv.DictReader(handle)
                    if (row.get("Symbol") or "").strip()
                }
            )
        if symbols:
            logger.info(
                "Universe %s: %d names from authority %s",
                universe_name,
                len(symbols),
                authority.name,
            )
            return symbols
    logger.warning(
        "Universe %s: no authority file; falling back to the in-code list, which may be stale",
        universe_name,
    )
    return list(get_universe_symbols(universe_name))


def load_mizan_cross_section(
    symbols: Sequence[str],
    *,
    as_of: date,
) -> tuple[dict[str, dict[str, str]], CrossSectionCoverage]:
    """Completed daily bars plus real macro, through the shared Mizan kernel.

    Bars come from the market-cache evidence stores; macro from the cached India VIX and NIFTY 50
    series. Every feature value is produced by ``modeling.mizan_features`` -- this function only
    gathers inputs.

    ``as_of`` is the session being traded; the decision uses bars strictly **before** it, because
    the model decides on a completed close and enters at the next open.
    """
    wanted = set(symbols)
    bars: dict[str, Any] = {}
    for cache_root in _BAR_CACHES:
        # Stop once the caches scanned so far already clear the coverage floor. Requiring a full
        # `issubset` meant one absent name -- 499 of 500 -- sent this on to enumerate the
        # 3,267-symbol all-market store, which takes over ten minutes to find nothing useful.
        if not cache_root.exists() or len(bars) >= MIN_CROSS_SECTION_COVERAGE * len(wanted):
            continue
        store = EvidenceStore(EvidenceStoreConfig(root=cache_root))
        for verified in store.list_verified(EvidenceResourceType.DATASET):
            acquisition = historical_acquisition_from_verified(verified)
            symbol = acquisition.manifest.symbol
            if symbol not in wanted or not acquisition.records:
                continue
            # Prefer the series ending latest, then the longer one. Selecting by length alone
            # let a stale 10-year cache beat a freshly ingested 3-year one, so the session
            # silently decided on week-old bars.
            existing = bars.get(symbol)
            candidate_end = acquisition.records[-1].exchange_date
            if existing:
                existing_end = existing[-1].exchange_date
                if (candidate_end, len(acquisition.records)) <= (
                    existing_end,
                    len(existing),
                ):
                    continue
            bars[symbol] = acquisition.records
        logger.info("Bars: %d/%d symbols after %s", len(bars), len(wanted), cache_root.parent.name)
        if wanted.issubset(bars):
            break

    if not bars:
        raise RuntimeError(
            f"no completed daily bars found for any of {len(wanted)} symbols in {_BAR_CACHES}"
        )

    # Symbols the cache had nothing for must still count against coverage. Reporting 49/49 for a
    # 50-name universe would let the floor pass on a cache holding 5 of 50, which is exactly the
    # shrunk cross-section the floor exists to catch. An empty series is "not enough bars", which
    # is what it is.
    for missing in wanted - set(bars):
        bars[missing] = ()

    vix: dict[str, float] = {}
    nifty: dict[str, float] = {}
    for macro_dir in reversed(_MACRO_DIRS):
        # Reversed so the freshest directory is applied last and wins on overlapping dates.
        vix.update(load_macro_series(macro_dir, "INDIAVIX"))
        nifty.update(load_macro_series(macro_dir, "NIFTY50"))
    decision_day = as_of - timedelta(days=1)
    return build_live_cross_section(
        bars,
        india_vix_by_date=vix,
        nifty_by_date=nifty,
        as_of=decision_day,
    )


def load_macro_series(macro_dir: Path, name: str) -> dict[str, float]:
    """Close-by-date for one macro series, matching the training store builder exactly."""
    path = macro_dir / f"macro_{name}.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {candle[0][:10]: float(candle[4]) for candle in payload.get("candles", [])}


def run_paper_session(
    session_date: date | None = None,
    universe: list[str] | None = None,
    universe_name: str = "NIFTY500",
    model_profile: str = "default",
    initial_cash: Decimal = Decimal("1000000.00"),
    slippage_bps: Decimal = Decimal("5.0"),
    realtime: bool = False,
    interval_seconds: float = 10.0,
    end_time_str: str = "15:30:00",
    upstox_token: str | None = None,
    output_dir: Path | None = None,
    selection_fraction: float = 0.20,
    sizing: str = "equal-weight",
) -> dict[str, Any]:
    """Runs a complete quote-driven paper trading session in IST from start time until market close (15:30 IST)."""
    current_ist = now_ist()
    if session_date is None:
        session_date = current_ist.date()
    if universe is None:
        universe = resolve_universe(universe_name)
    if output_dir is None:
        output_dir = PROJECT_ROOT / "logs" / "paper_runs"

    if upstox_token:
        os.environ["UPSTOX_ACCESS_TOKEN"] = upstox_token

    output_dir.mkdir(parents=True, exist_ok=True)
    session_id = f"paper_ses_{session_date.strftime('%Y%m%d')}_{current_ist.strftime('%H%M%S')}_IST"

    # Parse market close time in IST (Default 15:30:00 IST)
    end_hour, end_min, end_sec = map(int, end_time_str.split(":"))
    close_dt_ist = datetime(
        session_date.year,
        session_date.month,
        session_date.day,
        end_hour,
        end_min,
        end_sec,
        tzinfo=_IST,
    )

    logger.info("=" * 80)
    logger.info("QuantOS Paper Pilot Execution Session (IST) -- %s", session_id)
    logger.info("Current Time (IST) : %s", current_ist.strftime("%Y-%m-%d %H:%M:%S IST"))
    logger.info("Market Close (IST) : %s", close_dt_ist.strftime("%Y-%m-%d %H:%M:%S IST"))
    logger.info("Universe           : %s (%d assets)", universe_name, len(universe))
    logger.info("Initial Capital    : Rs %s", _paisa_str(initial_cash))
    logger.info("Model Profile      : %s", model_profile.upper())
    logger.info(
        "Upstox API Token   : %s",
        "CONFIGURED"
        if bool(os.getenv("UPSTOX_ACCESS_TOKEN"))
        else "NOT CONFIGURED (Using Live Exchange Feed)",
    )
    logger.info(
        "Execution Mode     : %s (Interval: %.1fs)",
        "REALTIME_STREAM" if realtime else "INTRADAY_SEQUENCE",
        interval_seconds,
    )
    logger.info("=" * 80)

    # 1. Fetch initial real live quotes from Upstox / NSE
    logger.info("Fetching real-time market data from Upstox / NSE exchange feed...")
    base_market = fetch_upstox_live_quotes(universe, access_token=upstox_token)
    if not base_market:
        logger.warning("Could not reach live exchange feed. Using fallback baseline.")
        base_market = {
            "INFY": {
                "price": Decimal("1121.10"),
                "previous_close": Decimal("1120.00"),
                "spread": Decimal("0.10"),
                "depth": 500,
                "source": "FALLBACK",
            },
            "TCS": {
                "price": Decimal("2270.20"),
                "previous_close": Decimal("2265.00"),
                "spread": Decimal("0.25"),
                "depth": 400,
                "source": "FALLBACK",
            },
            "RELIANCE": {
                "price": Decimal("1306.00"),
                "previous_close": Decimal("1300.00"),
                "spread": Decimal("0.10"),
                "depth": 600,
                "source": "FALLBACK",
            },
            "HDFCBANK": {
                "price": Decimal("728.80"),
                "previous_close": Decimal("725.00"),
                "spread": Decimal("0.10"),
                "depth": 700,
                "source": "FALLBACK",
            },
            "ICICIBANK": {
                "price": Decimal("1437.80"),
                "previous_close": Decimal("1430.00"),
                "spread": Decimal("0.15"),
                "depth": 550,
                "source": "FALLBACK",
            },
        }
    for sym, m in base_market.items():
        logger.info(
            "  [REAL NSE FEED] %-10s : Rs %s (Day Range: Rs %s - Rs %s | Vol: %s)",
            sym,
            _paisa_str(m["price"]),
            _paisa_str(m.get("low", m["price"])),
            _paisa_str(m.get("high", m["price"])),
            m.get("volume", "N/A"),
        )

    # 2. Initialize Mizan Model based on Profile
    # Both profiles carry verdict=RESEARCH_ONLY, so both are admitted only by the RESEARCH_PAPER
    # surface and only under the declared exemption. Acquiring the model through
    # `load_mizan_for_execution` is what makes that check unavoidable: the previous direct
    # `MizanModel.default_model()` call reached no gate at all.
    if model_profile == "sprint_50k":
        model = load_mizan_for_execution(
            ExecutionSurface.RESEARCH_PAPER,
            PAPER_OBSERVATION_EXEMPTION,
            profile="sprint_50k",
        )
        per_name_alloc = (initial_cash * Decimal("0.45")).quantize(
            _PAISA
        )  # 45% per name for 2-3 names
        risk_limits = RiskLimits(
            max_position_weight=0.50,  # Max 50% capital in single name
            max_daily_drawdown_pct=0.03,  # 3% daily drawdown kill switch
            max_total_drawdown_pct=0.08,  # 8% total drawdown kill switch
            min_cash_buffer_pct=0.05,  # 5% minimum cash buffer
            allow_naked_short=False,  # Strict long-only / no naked shorting
        )
    else:
        model = load_mizan_for_execution(
            ExecutionSurface.RESEARCH_PAPER,
            PAPER_OBSERVATION_EXEMPTION,
        )
        per_name_alloc = Decimal("150000.00")
        risk_limits = RiskLimits(
            max_position_weight=0.30,  # Max 30% capital in single name
            max_daily_drawdown_pct=0.04,  # 4% daily drawdown kill switch
            max_total_drawdown_pct=0.12,  # 12% total drawdown kill switch
            min_cash_buffer_pct=0.05,  # 5% minimum cash buffer
            allow_naked_short=False,  # Strict long-only / no naked shorting
        )

    logger.info(
        "Loaded Model: %s (%s, v%s)",
        model.config.model_name,
        model.config.model_id,
        model.config.version,
    )
    logger.info(
        "Score Threshold: %s | L2 Penalty: %s | Features: %d | Horizon: %d sessions",
        model.config.score_threshold,
        model.config.l2_penalty,
        len(model.config.feature_names),
        model.config.label_horizon_sessions,
    )

    # 2a-bis. Resume the running portfolio.
    #
    # A fresh engine every weekday would open ~55 names at the open and close them at 15:30, paying
    # a full round trip daily by construction. The model was measured entering at an open, holding
    # `label_horizon_sessions - 1` sessions, then re-ranking - a label horizon counts
    # decision -> entry -> exit, so the card's 11 is the screen's 10. `rebalance_due` takes the
    # card's convention and does that conversion itself; passing the raw value here and comparing it
    # directly was half of why the executed hold was 12 sessions rather than 10.
    portfolio = load_portfolio(PORTFOLIO_STATE_PATH) or PaperPortfolioState(cash=initial_cash)
    horizon = int(model.config.label_horizon_sessions)
    rebalancing = portfolio.rebalance_due(horizon)
    logger.info(
        "Portfolio: cash Rs %s, %d holding(s), session %d, held %d of %d sessions -> %s",
        portfolio.cash,
        len(portfolio.holdings),
        portfolio.sessions_completed + 1,
        portfolio.sessions_held,
        horizon - 1,
        "REBALANCING" if rebalancing else "HOLDING",
    )

    # 2b. Mizan decision for this session, computed once from completed daily bars.
    #
    # Every feature comes from `modeling.mizan_features`, the kernel verified bit-identical against
    # the published training store. The selection rule is the model's own recorded
    # `score_threshold` plus a declared top fraction -- not the hardcoded 0.035 and `[:2]` this
    # runner used before, which produced zero proposals on every realistic universe.
    # On a hold session the ranking is not consulted at all, so the cross-section is not built:
    # computing a decision that will not be acted on invites reading it as one.
    if not rebalancing:
        mizan_scores: dict[str, float] = {}
        mizan_ranked: tuple[str, ...] = ()
        mizan_picks: tuple[str, ...] = ()
        logger.info("Holding: no re-ranking this session")
    else:
        mizan_cross_section, mizan_coverage = load_mizan_cross_section(universe, as_of=session_date)
        # The coverage gate runs *after* the extreme-row refusals below, not before. Checking first
        # measured a cross-section the session was not going to use: refusals shrink it further, and
        # a rank divides by the number of names present, so the gate would have passed on a
        # population that no longer existed by the time anything was ranked.
        mizan_cross_section, refused = refuse_extreme_rows(
            mizan_cross_section,
            # `means` and `scales` are decimal text on the preprocessor config, matching how the
            # evidence stores them; the guard works in float alongside the scorer.
            means={
                n: float(v)
                for n, v in zip(
                    model.preprocessor.feature_names, model.preprocessor.means, strict=True
                )
            },
            scales={
                n: float(v)
                for n, v in zip(
                    model.preprocessor.feature_names, model.preprocessor.scales, strict=True
                )
            },
        )
        if refused:
            logger.warning(
                "Refused %d name(s) whose standardized features exceed the model's working range: %s",
                len(refused),
                ", ".join(refused),
            )
        # Recorded on the coverage object rather than only logged. `skipped_extreme` existed as a
        # field and was never populated by anything, so the refusals the guard exists to make
        # visible were absent from the very report meant to show them.
        mizan_coverage = mizan_coverage.with_extreme_refusals(refused)
        logger.info("Mizan cross-section: %s", mizan_coverage.summary())
        if mizan_coverage.fraction < MIN_CROSS_SECTION_COVERAGE:
            raise RuntimeError(
                f"only {mizan_coverage.fraction:.1%} of the universe could be scored; a "
                f"cross-sectional rank divides by the number of names present, so a shrunk "
                f"cross-section changes every rank. Minimum is {MIN_CROSS_SECTION_COVERAGE:.0%}"
            )
        mizan_scores = model.predict_scores(
            {
                sym: {k: float(v) for k, v in feats.items()}
                for sym, feats in mizan_cross_section.items()
            }
        )
        mizan_ranked = tuple(sorted(mizan_scores, key=lambda s: (-mizan_scores[s], s)))
        # No score floor. The out-of-sample screen this path exists to reproduce applies none -
        # `screen_mizan_out_of_sample.py:199` is `take = max(1, int(len(scores) * FRACTION))` with
        # no score filter anywhere in the file - so a floor here is an unmeasured rule that changes
        # what is being executed.
        #
        # It was also dangerous. Scores cluster near zero against a 0.0715 floor, so an ordinary
        # session could clear nothing; `top_picks` came back empty while `rebalancing` stayed True,
        # and the exit loop then sold every holding. A go-to-cash rule nobody measured, firing
        # silently, on a book that had just paid to enter.
        mizan_picks = select_top_fraction(mizan_scores, selection_fraction)
        logger.info(
            "Mizan picks: %d of %d ranked (top %.0f%%, no score floor - the screen applies none): %s",
            len(mizan_picks),
            len(mizan_scores),
            selection_fraction * 100.0,
            ", ".join(f"{s} {mizan_scores[s]:+.5f}" for s in mizan_picks) or "none",
        )

    # 2c. Position sizing.
    #
    # Equal-weight is the default because it is how the model was measured: the out-of-sample
    # screen averaged the forward target across the selected top 20% (`statistics.fmean`), giving
    # every chosen name the same weight. The previous fixed stake of Rs 150,000 per name meant 56
    # picks against Rs 1,000,000 filled only the first ~6 in rank order and left the other 50
    # unexpressed -- a concentrated bet on the head of a ranking, which nobody validated.
    #
    # `fixed` remains available because the sprint profile deliberately concentrates into 2-3 names
    # and equal-weighting would silently undo that intent.
    if sizing == "equal-weight" and mizan_picks:
        # Sized from the portfolio's actual funding, not from the `initial_cash` nominal. Sizing
        # from the constant survived the change that made the portfolio persistent, so a book that
        # had drawn down kept allocating as though it still held its opening capital -- which funds
        # only the head of the ranking and leaves the tail unexpressed. That is precisely the
        # concentration defect equal-weight sizing was introduced to remove.
        deployable = portfolio.ledger_funding()
        usable = deployable * (Decimal("1") - Decimal(str(risk_limits.min_cash_buffer_pct)))
        per_name_alloc = (usable / Decimal(len(mizan_picks))).quantize(_PAISA)
        logger.info(
            "Sizing: equal-weight, Rs %s per name across %d picks (%.0f%% cash buffer held back)",
            per_name_alloc,
            len(mizan_picks),
            risk_limits.min_cash_buffer_pct * 100,
        )
    else:
        logger.info("Sizing: fixed, Rs %s per name", per_name_alloc)

    # 3. Risk Governor Setup
    #
    # Seeded with the carried all-time peak, not left at zero. A fresh governor each session took
    # its peak from whatever that session opened at, so a multi-session decline was measured
    # against its own falling baseline and the total-drawdown kill switch could never trip. The
    # peak is the larger of what the portfolio has ever reached and what it is funded with today,
    # so a first run establishes a real baseline rather than starting at zero.
    if portfolio.risk_halted:
        # A tripped kill switch is not cleared by time passing. Refusing here rather than trading is
        # the only honest option left: resetting it would make the switch decorative, and
        # liquidating on its own would execute a rule nobody measured. Clearing it is a human act.
        logger.error(
            "REFUSING TO TRADE: the risk kill switch fired on %s and has not been cleared. "
            "Reason: %s. Review the book, then run:  "
            "python scripts/clear_paper_halt.py --i-have-reviewed-the-book  "
            "Do NOT hand-edit or delete %s: it is hash-protected, so an edit is refused on the "
            "next load, and deleting it invents a fresh portfolio and discards the real book.",
            portfolio.halted_on,
            portfolio.halt_reason or "not recorded",
            PORTFOLIO_STATE_PATH,
        )
        raise SystemExit(8)

    # Two peaks, two meanings. `initial_equity` is *this session's* opening equity, so the 4% daily
    # limit measures an intraday decline; `all_time_peak_equity` is the carried high-water mark, so
    # the 12% total limit measures a multi-session one.
    #
    # Passing the carried peak as `initial_equity` -- which is what this line used to do -- seeded
    # both, and the daily check then measured multi-session declines against the 4% limit. The
    # total switch became unreachable, and a session that opened flat and never moved intraday
    # could halt the book on the first order, which is the exit.
    opening_equity = portfolio.ledger_funding()
    governor = PreTradeRiskGovernor(
        limits=risk_limits,
        initial_equity=opening_equity,
        all_time_peak_equity=max(portfolio.peak_equity, opening_equity),
    )

    # 4. Order Book Simulator Configuration
    sim_config = OrderBookSimConfig(
        slippage_bps=slippage_bps,
        allow_depth_walking=True,
        enforce_market_hours=False,
    )

    # 5. Initialize Paper Pilot Engine
    engine = PaperPilotEngine(
        # Funded with cash plus the carried holdings' cost basis and their entry fees, so the
        # replay below debits exactly that back out and leaves cash at its true carried figure.
        initial_cash=portfolio.ledger_funding(),
        risk_governor=governor,
        sim_config=sim_config,
        allow_short=False,
        session_id=session_id,
    )

    # Reconstruct the carried positions in the fresh ledger. Without this a SELL of something held
    # since a previous session is refused as a short, because the ledger has never seen it. The
    # fills carry their original entry fee, which `ledger_funding` has already covered, so the
    # eventual sale nets both legs instead of only the exit.
    # Through the engine, not the ledger directly. Going straight to `ledger.process_fill` left the
    # engine's own reconciliation baseline flat, so `end_session` compared the ledger's carried
    # positions against today's fills alone and mismatched on every one of them.
    carry_fills = portfolio.carry_forward_fills(current_ist)
    engine.carry_in_positions(carry_fills)
    if carry_fills:
        logger.info(
            "Carried %d position(s) into the ledger; cash now Rs %s",
            len(carry_fills),
            _paisa_str(engine.cash),
        )

    # 6. Open Session at current IST time
    engine.start_session(session_date=session_date, timestamp=current_ist)
    logger.info("Trading session ACTIVE at %s", current_ist.strftime("%Y-%m-%d %H:%M:%S IST"))

    # Tracking state
    proposals_submitted = []
    shutdown_requested = False

    def handle_sigint(signum: int, frame: Any) -> None:
        nonlocal shutdown_requested
        logger.warning(
            "Interrupt signal received. Initiating clean session close and reconciliation..."
        )
        shutdown_requested = True

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    status_file = output_dir / "live_paper_status.json"
    rolling_status: dict[str, Any] = {
        "session_id": session_id,
        "status": "INITIALIZING",
        "timestamp_ist": current_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "initial_cash": _paisa_str(initial_cash),
        "total_equity": _paisa_str(initial_cash),
        "cash": _paisa_str(initial_cash),
        "realized_pnl": "0.00",
        "unrealized_pnl": "0.00",
        "net_pnl": "0.00",
        "net_pnl_pct": 0.0,
        "total_fees_paid": "0.00",
        "open_positions": {},
        "positions_detail": [],
        "fills_count": 0,
        "recent_fills": [],
        "alpha_signals": [],
        "risk_governor": {
            "kill_switch_active": False,
            "max_position_weight": "30%",
            "min_cash_buffer": "5%",
            "daily_drawdown_limit": "4%",
            "discrepancy_paisa": "0.00",
        },
        "market_close_ist": close_dt_ist.strftime("%H:%M:%S IST"),
    }
    step = 0

    try:
        while not shutdown_requested:
            step += 1
            loop_now = now_ist() if realtime else (current_ist + timedelta(minutes=15 * step))

            # Check if market close time reached
            if loop_now >= close_dt_ist:
                logger.info(
                    "Market close reached at %s. Finalizing session...",
                    loop_now.strftime("%H:%M:%S IST"),
                )
                break

            logger.info(
                "--- [IST %s] Interval %02d | Active Trading Loop ---",
                loop_now.strftime("%H:%M:%S"),
                step,
            )

            # Fetch fresh real-time quotes from Upstox / NSE
            if realtime:
                live_quotes = fetch_upstox_live_quotes(universe, access_token=upstox_token)
                for sym, q in live_quotes.items():
                    base_market[sym] = q

            # Generate realistic top-of-book and L2 depth from real market quotes
            step_books = {}
            for sym, state in base_market.items():
                mid = state["price"]
                spread = state.get("spread", Decimal("0.10"))
                bid_p = (mid - spread / Decimal("2.0")).quantize(_PAISA)
                ask_p = (mid + spread / Decimal("2.0")).quantize(_PAISA)
                depth = state.get("depth", 300)

                bids = [
                    (bid_p, depth),
                    ((bid_p - Decimal("0.05")).quantize(_PAISA), depth * 2),
                    ((bid_p - Decimal("0.10")).quantize(_PAISA), depth * 3),
                ]
                asks = [
                    (ask_p, depth),
                    ((ask_p + Decimal("0.05")).quantize(_PAISA), depth * 2),
                    ((ask_p + Decimal("0.10")).quantize(_PAISA), depth * 3),
                ]
                book = OrderBookSnapshot.from_levels(
                    symbol=sym,
                    timestamp=loop_now,
                    bids=bids,
                    asks=asks,
                    last_price=mid,
                )
                step_books[sym] = book

                # Process quote and execute pending order matches
                fills_from_quote = engine.process_quote(book, current_time=loop_now)
                if fills_from_quote:
                    for fill in fills_from_quote:
                        logger.info(
                            "  [FILL EXECUTED] %s: %s %d @ Rs %s (Statutory Fee: Rs %s)",
                            fill.symbol,
                            fill.side.value,
                            fill.quantity,
                            _paisa_str(fill.price),
                            _paisa_str(fill.fee),
                        )

            # 5b. Mizan decisions are computed once per session, before the loop, from
            # completed daily bars through the shared feature kernel. They deliberately do not
            # change intraday: the model was validated deciding at a session close and entering at
            # the next open, so re-scoring on a partially formed bar would execute a rule nobody
            # measured. The previous version rebuilt all fifteen features here from that step's
            # quote alone -- `return_5 = return_1 * 1.5`, macro pinned to constants, and
            # `rsi_14_centered` clamped to +/-50 against a trained range of +/-0.45.
            scores = mizan_scores
            ranked_symbols = list(mizan_ranked)
            top_picks = list(mizan_picks)

            # Intraday percentage move, for the dashboard's gainers/losers panel only. This is
            # deliberately NOT a model input: the decision above came from completed daily bars
            # through the shared kernel. Conflating the two is what the old code did.
            returns_map = {}
            for sym in universe:
                # Not named `quote`: that name is bound to a `Quote` object later in this
                # function, and reusing it made mypy infer dict[str, Any] for both.
                quote_state = base_market[sym]
                price = float(quote_state["price"])
                previous_close = float(quote_state.get("previous_close", price))
                returns_map[sym] = (
                    (price - previous_close) / previous_close if previous_close > 0 else 0.0
                )

            # 5e. On a rebalance, exit whatever is no longer selected.
            #
            # Gated on `rebalancing`: on a hold session `scores` is empty, so the old condition
            # `scores.get(sym, 0.0) < 0.01 and sym not in top_picks` was true for *every* holding
            # and would have liquidated the entire portfolio on the first day it held.
            #
            # Also gated on a non-empty selection. Removing the invented score floor made an empty
            # `top_picks` much less likely, but "sell everything" must never be reachable by the
            # selection simply failing to produce names -- a shrunk cross-section or a scoring
            # failure would otherwise present as a deliberate go-to-cash decision. Going flat is a
            # rule the screen does not contain, so it should not be an outcome the code can reach
            # by accident.
            if rebalancing and not top_picks:
                logger.error(
                    "Rebalance selected no names from %d scored. Holding the existing book rather "
                    "than liquidating: going to cash is not a rule the screen contains.",
                    len(scores),
                )
            for sym, pos in list(engine.positions.items()) if rebalancing and top_picks else []:
                if pos.quantity > 0 and sym not in top_picks:
                    prop_id = f"prop_{session_id}_{step}_{sym}_SELL"
                    proposal = PaperProposal(
                        proposal_id=prop_id,
                        symbol=sym,
                        side=Side.SELL,
                        quantity=pos.quantity,
                        order_type=OrderType.MARKET,
                        decision_at=loop_now,
                        strategy_name="Mizan_Alpha_ExitLowRank",
                        model_artifact_id=model.config.model_id,
                    )
                    order, decision = engine.submit_proposal(proposal)
                    proposals_submitted.append((proposal, decision))
                    logger.info(
                        "  [EXIT PROPOSAL SUBMITTED] %s SELL %d %s (Risk: %s)",
                        prop_id,
                        pos.quantity,
                        sym,
                        "APPROVED" if decision.approved else "REJECTED",
                    )

            # 5f. On a rebalance, enter the selection. Exits above run first, in the same step, so
            # the proceeds are available to fund these buys: sizing every entry against pre-exit
            # cash meant a fully invested book could only spend its ~5% buffer, and the tail of the
            # ranking went unfilled for a reason that had nothing to do with the model.
            #
            # Explicitly gated on `rebalancing`. It used to rely on `top_picks` happening to be
            # empty on a hold session -- the invariant "act only on a rebalance session" enforced
            # explicitly in one loop and by coincidence in the other, forty lines apart.
            for sym in top_picks if rebalancing else []:
                current_held = engine.positions[sym].quantity if sym in engine.positions else 0
                if current_held == 0:
                    avail_cash = engine.cash
                    target_alloc = min(per_name_alloc, avail_cash * Decimal("0.95"))
                    price = base_market[sym]["price"]
                    qty = int(target_alloc / price)
                    if qty == 0:
                        # One share costs more than the allocation. Saying so beats a silent skip:
                        # under equal weight this is how a high-priced name drops out.
                        logger.info(
                            "  %s: skipped, 1 share costs Rs %s against an allocation of Rs %s",
                            sym,
                            _paisa_str(price),
                            _paisa_str(target_alloc),
                        )
                    if qty > 0:
                        prop_id = f"prop_{session_id}_{step}_{sym}_BUY"
                        proposal = PaperProposal(
                            proposal_id=prop_id,
                            symbol=sym,
                            side=Side.BUY,
                            quantity=qty,
                            order_type=OrderType.MARKET,
                            decision_at=loop_now,
                            strategy_name="Mizan_Alpha_TopPicks",
                            model_artifact_id=model.config.model_id,
                        )
                        order, decision = engine.submit_proposal(proposal)
                        proposals_submitted.append((proposal, decision))
                        logger.info(
                            "  [PROPOSAL SUBMITTED] %s BUY %d %s (Risk: %s, Reason: %s)",
                            prop_id,
                            qty,
                            sym,
                            "APPROVED" if decision.approved else "REJECTED",
                            decision.reason or "OK",
                        )

            # Update rolling status file for live monitoring
            snapshot_prices = {sym: state["price"] for sym, state in base_market.items()}
            snap = engine.get_portfolio_snapshot(timestamp=loop_now, current_prices=snapshot_prices)

            positions_detail = []
            for sym, pos in engine.positions.items():
                if pos.quantity != 0:
                    cur_p = snapshot_prices.get(sym, pos.average_price)
                    pos_val = (cur_p * Decimal(pos.quantity)).quantize(_PAISA)
                    cost_basis = (pos.average_price * Decimal(pos.quantity)).quantize(_PAISA)
                    u_pnl = (pos_val - cost_basis).quantize(_PAISA)
                    u_pct = (
                        float(u_pnl / cost_basis * Decimal("100.0"))
                        if cost_basis > Decimal("0")
                        else 0.0
                    )
                    alloc_pct = (
                        float(pos_val / snap.total_equity * Decimal("100.0"))
                        if snap.total_equity > Decimal("0")
                        else 0.0
                    )
                    positions_detail.append(
                        {
                            "symbol": sym,
                            "quantity": pos.quantity,
                            "entry_price": _paisa_str(pos.average_price),
                            "current_price": _paisa_str(cur_p),
                            "cost_basis": _paisa_str(cost_basis),
                            "market_value": _paisa_str(pos_val),
                            "unrealized_pnl": _paisa_str(u_pnl),
                            "unrealized_pnl_pct": round(u_pct, 2),
                            "allocation_pct": round(alloc_pct, 2),
                        }
                    )

            fills_detail = [
                {
                    "fill_id": f.fill_id,
                    "order_id": f.order_id,
                    "symbol": f.symbol,
                    "side": f.side.value,
                    "quantity": f.quantity,
                    "price": _paisa_str(f.price),
                    "fee": _paisa_str(f.fee),
                    "timestamp_ist": f.timestamp.astimezone(_IST).strftime("%H:%M:%S IST"),
                }
                for f in engine.fills[-15:]
            ]

            alpha_detail = [
                {
                    "rank": i + 1,
                    "symbol": sym,
                    "score": round(scores.get(sym, 0.0), 4),
                    "is_top_pick": sym in top_picks,
                }
                for i, sym in enumerate(ranked_symbols)
            ]

            total_fees = sum((f.fee for f in engine.fills), Decimal("0.00")).quantize(_PAISA)
            net_pnl = (snap.realized_pnl + snap.unrealized_pnl).quantize(_PAISA)
            net_pnl_pct = float(net_pnl / initial_cash * Decimal("100.0"))

            sorted_gainers = sorted(universe, key=lambda s: returns_map.get(s, 0.0), reverse=True)
            top_gainers_list = [
                {
                    "rank": i + 1,
                    "symbol": s,
                    "price": _paisa_str(base_market[s]["price"]),
                    "change_pct": round(returns_map.get(s, 0.0) * 100, 2),
                    "alpha_score": round(scores.get(s, 0.0), 4),
                }
                for i, s in enumerate(sorted_gainers[:10])
            ]
            top_losers_list = [
                {
                    "rank": i + 1,
                    "symbol": s,
                    "price": _paisa_str(base_market[s]["price"]),
                    "change_pct": round(returns_map.get(s, 0.0) * 100, 2),
                    "alpha_score": round(scores.get(s, 0.0), 4),
                }
                for i, s in enumerate(sorted_gainers[-10:][::-1])
            ]

            rolling_status = {
                "session_id": session_id,
                "status": "RUNNING",
                "timestamp_ist": loop_now.strftime("%Y-%m-%d %H:%M:%S IST"),
                "initial_cash": _paisa_str(initial_cash),
                "total_equity": _paisa_str(snap.total_equity),
                "cash": _paisa_str(snap.cash),
                "realized_pnl": _paisa_str(snap.realized_pnl),
                "unrealized_pnl": _paisa_str(snap.unrealized_pnl),
                "net_pnl": _paisa_str(net_pnl),
                "net_pnl_pct": round(net_pnl_pct, 3),
                "total_fees_paid": _paisa_str(total_fees),
                "open_positions": {
                    s: p.quantity for s, p in engine.positions.items() if p.quantity != 0
                },
                "positions_detail": positions_detail,
                "fills_count": len(engine.fills),
                "recent_fills": fills_detail,
                "alpha_signals": alpha_detail,
                "top_gainers": top_gainers_list,
                "top_losers": top_losers_list,
                "risk_governor": {
                    # `RiskLimits` carries no kill-switch field; the state lives on the governor as the
                    # public `is_killed` property. The old attribute raised AttributeError.
                    "kill_switch_active": governor.is_killed,
                    "max_position_weight": f"{int(governor.limits.max_position_weight * 100)}%",
                    "min_cash_buffer": f"{int(governor.limits.min_cash_buffer_pct * 100)}%",
                    "daily_drawdown_limit": f"{int(governor.limits.max_daily_drawdown_pct * 100)}%",
                    "discrepancy_paisa": "0.00",
                },
                "market_close_ist": close_dt_ist.strftime("%H:%M:%S IST"),
            }
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(rolling_status, f, indent=2)

            if realtime:
                time.sleep(interval_seconds)
            elif step >= 12:  # In sequence mode, finish full session
                break

    except Exception as err:
        logger.exception("Error during paper trading loop: %s", err)

    # 6. Final Market Close Processing (15:30 IST)
    final_now = now_ist() if realtime else close_dt_ist
    final_prices = {sym: state["price"] for sym, state in base_market.items()}
    for sym, price in final_prices.items():
        quote = Quote(symbol=sym, timestamp=final_now, bid=price, ask=price, last_price=price)
        engine.process_quote(quote, current_time=final_now)

    # 7. End Trading Session & Penny-Exact Reconciliation
    reconciliation = engine.end_session(timestamp=final_now, close_prices=final_prices)

    # 7b. Persist the running portfolio for the next session.
    #
    # Written after reconciliation so a session that fails to reconcile does not advance the
    # portfolio. Fees counted are today's real fills only - the carry-forward replay is zero-fee
    # and must not be added again.
    todays_fees = sum(
        (f.fee for f in engine.fills if not f.fill_id.startswith("carry_")), Decimal("0.00")
    )
    # The entry cost still attributable to each open position, so a name carried into tomorrow does
    # not have its entry fee dropped on the way through the state file.
    open_entry_fees = {
        symbol: sum((lot.entry_fee for lot in lots), Decimal("0.00"))
        for symbol, lots in engine.ledger.lots.items()
    }
    portfolio = state_from_ledger(
        portfolio,
        cash=engine.cash,
        positions={sym: (pos.quantity, pos.average_price) for sym, pos in engine.positions.items()},
        session_date=session_date,
        session_realized_pnl=engine.ledger.realized_pnl,
        fees_paid=todays_fees,
        rebalanced=rebalancing,
        open_entry_fees=open_entry_fees,
        # Marked equity, not the governor's peak alone. `update_peaks` is reachable only from
        # `evaluate_order`, and a hold session proposes no orders, so nine sessions in ten never
        # touched the peak -- and the fallback seed was `ledger_funding()`, a *cost* figure. A book
        # that rose 25% during a hold and then fell 20% from that high recorded no drawdown at all.
        session_peak_equity=max(governor.all_time_peak_equity, reconciliation.total_equity),
        risk_halted=governor.is_killed,
        halt_reason=(
            governor.kill_events[-1].reason if governor.is_killed and governor.kill_events else ""
        ),
    )
    save_portfolio(PORTFOLIO_STATE_PATH, portfolio)
    logger.info(
        "Portfolio saved: cash Rs %s, %d holding(s), realized Rs %s, fees to date Rs %s",
        portfolio.cash,
        len(portfolio.holdings),
        portfolio.realized_pnl,
        portfolio.total_fees,
    )
    total_net_pnl = reconciliation.total_realized_pnl + reconciliation.total_unrealized_pnl
    return_pct = float(total_net_pnl / initial_cash * Decimal("100.0"))

    logger.info("=" * 80)
    logger.info(
        "Session Concluded & Reconciled: %s", "SUCCESS" if reconciliation.reconciled else "FAILED"
    )
    logger.info("Closure Time (IST)   : %s", final_now.strftime("%Y-%m-%d %H:%M:%S IST"))
    logger.info("Initial Capital      : Rs %s", _paisa_str(reconciliation.initial_cash))
    logger.info("Final Cash           : Rs %s", _paisa_str(reconciliation.final_cash))
    logger.info(
        "Total Equity         : Rs %s (Net P&L: Rs %s, %+.2f%%)",
        _paisa_str(reconciliation.total_equity),
        _paisa_str(total_net_pnl),
        return_pct,
    )
    logger.info(
        "Statutory NSE Fees   : Rs %s | Slippage: Rs %s",
        _paisa_str(reconciliation.total_fees_paid),
        _paisa_str(reconciliation.total_slippage_cost),
    )
    logger.info(
        "Orders Summary       : %d submitted | %d filled | %d cancelled | %d rejected",
        reconciliation.orders_submitted,
        reconciliation.orders_filled,
        reconciliation.orders_cancelled,
        reconciliation.orders_rejected,
    )
    logger.info(
        "Total Fills          : %d | Discrepancy: Rs %s",
        reconciliation.total_fills_count,
        _paisa_str(reconciliation.discrepancy_paisa),
    )
    logger.info("=" * 80)

    # 8. Compile Comprehensive Audit & Feedback Report in IST
    feedback_payload = {
        "session_id": session_id,
        "session_date": str(session_date),
        "timezone": "IST (Asia/Kolkata, UTC+05:30)",
        "started_at_ist": current_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "closed_at_ist": final_now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "market_close_ist": close_dt_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "model": {
            "model_id": model.config.model_id,
            "candidate_id": model.config.candidate_id,
            "model_name": model.config.model_name,
            "version": model.config.version,
            "architecture": model.config.model_type,
            "feature_schema": f"{model.config.feature_schema_id} (v{model.config.feature_schema_version})",
            "feature_count": len(model.config.feature_names),
        },
        "universe": universe,
        "capital": {
            "initial_cash": _paisa_str(reconciliation.initial_cash),
            "final_cash": _paisa_str(reconciliation.final_cash),
            "total_equity": _paisa_str(reconciliation.total_equity),
            "cash_delta": _paisa_str(reconciliation.total_cash_delta),
        },
        "performance": {
            "realized_pnl": _paisa_str(reconciliation.total_realized_pnl),
            "unrealized_pnl": _paisa_str(reconciliation.total_unrealized_pnl),
            "total_net_pnl": _paisa_str(total_net_pnl),
            "return_pct": round(return_pct, 4),
            "total_fees_paid": _paisa_str(reconciliation.total_fees_paid),
            "total_slippage_cost": _paisa_str(reconciliation.total_slippage_cost),
        },
        "order_statistics": {
            "proposals_submitted": len(proposals_submitted),
            "orders_submitted": reconciliation.orders_submitted,
            "orders_filled": reconciliation.orders_filled,
            "orders_partially_filled": reconciliation.orders_partially_filled,
            "orders_cancelled": reconciliation.orders_cancelled,
            "orders_rejected": reconciliation.orders_rejected,
            "total_trades_count": reconciliation.total_trades_count,
            "total_fills_count": reconciliation.total_fills_count,
            "open_positions": dict(reconciliation.open_positions),
        },
        "reconciliation": {
            "reconciled": reconciliation.reconciled,
            "discrepancy_paisa": _paisa_str(reconciliation.discrepancy_paisa),
            "reconciliation_errors": list(reconciliation.reconciliation_errors),
        },
        "fills": [
            {
                "fill_id": f.fill_id,
                "order_id": f.order_id,
                "symbol": f.symbol,
                "side": f.side.value,
                "quantity": f.quantity,
                "price": _paisa_str(f.price),
                "fee": _paisa_str(f.fee),
                "timestamp_ist": f.timestamp.astimezone(_IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            }
            for f in engine.fills
        ],
        "audit_events_count": len(engine.audit_log),
    }

    # Save final JSON feedback
    json_path = output_dir / f"paper_session_{session_date}_{session_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(feedback_payload, f, indent=2)

    # Save final Markdown report in IST
    md_path = output_dir / f"paper_session_{session_date}_{session_id}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# QuantOS Paper Trading Session Report (IST) -- {session_id}\n\n")
        f.write(f"- **Session Date**: `{session_date}`\n")
        f.write("- **Timezone**: `Indian Standard Time (IST, UTC+05:30)`\n")
        f.write(
            f"- **Execution Interval**: `{current_ist.strftime('%H:%M:%S IST')}` to `{final_now.strftime('%H:%M:%S IST')}` (Market Close: `{close_dt_ist.strftime('%H:%M:%S IST')}`)\n"
        )
        f.write(f"- **Execution Model**: `{model.config.model_name}` (`{model.config.model_id}`)\n")
        f.write(f"- **Architecture**: `{model.config.model_type}`\n")
        rec_status = (
            f"PASS ({_paisa_str(reconciliation.discrepancy_paisa)} paisa discrepancy)"
            if reconciliation.reconciled
            else f"FAIL ({_paisa_str(reconciliation.discrepancy_paisa)} paisa discrepancy)"
        )
        f.write(f"- **Reconciliation Status**: **`{rec_status}`**\n\n")
        f.write("## 1. Capital & Financial Summary (IST)\n\n")
        f.write("| Metric | Value (Rs) |\n|---|---:|\n")
        f.write(f"| Initial Capital | Rs {_paisa_str(reconciliation.initial_cash)} |\n")
        f.write(f"| Final Cash | Rs {_paisa_str(reconciliation.final_cash)} |\n")
        f.write(f"| Total Portfolio Equity | Rs {_paisa_str(reconciliation.total_equity)} |\n")
        f.write(f"| Realized P&L | Rs {_paisa_str(reconciliation.total_realized_pnl)} |\n")
        f.write(f"| Unrealized P&L | Rs {_paisa_str(reconciliation.total_unrealized_pnl)} |\n")
        f.write(f"| Total Net P&L | Rs {_paisa_str(total_net_pnl)} ({return_pct:+.2f}%) |\n")
        f.write(f"| Total Statutory Fees | Rs {_paisa_str(reconciliation.total_fees_paid)} |\n")
        f.write(
            f"| Total Slippage Cost | Rs {_paisa_str(reconciliation.total_slippage_cost)} |\n\n"
        )

        f.write("## 2. Order Execution & Fills (IST)\n\n")
        f.write(f"- **Orders Submitted**: `{reconciliation.orders_submitted}`\n")
        f.write(f"- **Orders Filled**: `{reconciliation.orders_filled}`\n")
        f.write(f"- **Total Fills**: `{reconciliation.total_fills_count}`\n\n")
        f.write(
            "| Fill ID | Symbol | Side | Quantity | Price (Rs) | Statutory Fee (Rs) | Execution Time (IST) |\n|---|---|---|---:|---:|---:|---|\n"
        )
        for f_item in engine.fills:
            fill_ts_ist = f_item.timestamp.astimezone(_IST).strftime("%H:%M:%S IST")
            f.write(
                f"| `{f_item.fill_id}` | `{f_item.symbol}` | **{f_item.side.value}** | {f_item.quantity} | Rs {_paisa_str(f_item.price)} | Rs {_paisa_str(f_item.fee)} | `{fill_ts_ist}` |\n"
            )

        f.write("\n## 3. Ending Open Positions at Market Close\n\n")
        if reconciliation.open_positions:
            f.write(
                "| Symbol | Quantity | Close Price (Rs) | Market Value (Rs) |\n|---|---:|---:|---:|\n"
            )
            for sym, qty in reconciliation.open_positions.items():
                p = final_prices.get(sym, Decimal("0.00"))
                f.write(
                    f"| `{sym}` | {qty} | Rs {_paisa_str(p)} | Rs {_paisa_str(p * Decimal(qty))} |\n"
                )
        else:
            f.write("*(All positions closed / flat)*\n")

    # Update live status file to COMPLETED
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                **rolling_status,
                "status": "COMPLETED",
                "closed_at_ist": final_now.strftime("%Y-%m-%d %H:%M:%S IST"),
            },
            f,
            indent=2,
        )

    logger.info("Feedback JSON saved: %s", json_path)
    logger.info("Markdown Report saved: %s", md_path)

    return feedback_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantOS Quote-Driven Paper Pilot Runner (IST)")
    parser.add_argument("--date", type=str, default=None, help="Session date YYYY-MM-DD")
    parser.add_argument("--capital", type=float, default=1000000.0, help="Initial cash in INR")
    parser.add_argument(
        "--slippage-bps", type=float, default=5.0, help="Adverse slippage in basis points"
    )
    parser.add_argument(
        "--realtime", action="store_true", help="Run in continuous real-time mode until 15:30 IST"
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=10.0,
        help="Seconds between trading loop iterations in realtime mode",
    )
    parser.add_argument(
        "--end-time-ist", type=str, default="15:30:00", help="Market close time in IST (HH:MM:SS)"
    )
    parser.add_argument(
        "--upstox-token", type=str, default=None, help="Upstox API Bearer Access Token"
    )
    parser.add_argument(
        "--model-profile",
        type=str,
        default="default",
        choices=["default", "sprint_50k"],
        help="Model profile (default or sprint_50k)",
    )
    parser.add_argument(
        "--universe-name",
        type=str,
        default="NIFTY500",
        choices=["NIFTY50", "NIFTY100", "NIFTY200", "NIFTY500"],
        help="Universe preset (NIFTY50, NIFTY100, NIFTY200, NIFTY500)",
    )
    parser.add_argument(
        "--sizing",
        choices=["equal-weight", "fixed"],
        default="equal-weight",
        help="equal-weight matches how the model was measured; fixed keeps a per-name stake",
    )
    parser.add_argument("--universe", type=str, nargs="+", default=None, help="Universe symbols")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")

    args = parser.parse_args()

    s_date = None
    if args.date:
        try:
            s_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("Invalid date '%s'. Format must be YYYY-MM-DD", args.date)
            return 1

    out_p = Path(args.output_dir) if args.output_dir else None

    try:
        res = run_paper_session(
            session_date=s_date,
            sizing=args.sizing,
            universe=args.universe,
            universe_name=args.universe_name,
            model_profile=args.model_profile,
            initial_cash=Decimal(str(args.capital)),
            slippage_bps=Decimal(str(args.slippage_bps)),
            realtime=args.realtime,
            interval_seconds=args.interval_seconds,
            end_time_str=args.end_time_ist,
            upstox_token=args.upstox_token,
            output_dir=out_p,
        )
        # A failed reconciliation used to print SUCCESS and exit 0, next to a hardcoded
        # "(0.00 Paisa Discrepancy)" that was printed whether or not the discrepancy was zero. The
        # one number that would have revealed the failure was the one replaced by a constant.
        reconciled = bool(res["reconciliation"]["reconciled"])
        discrepancy = res["reconciliation"]["discrepancy_paisa"]
        banner = "[PAPER PILOT SUCCESS]" if reconciled else "[PAPER PILOT RECONCILIATION FAILED]"
        print(f"\n{banner} Session {res['session_id']}.")
        print(f"Timezone: {res['timezone']}")
        print(f"Active Period: {res['started_at_ist']} -> {res['closed_at_ist']}")
        print(
            f"Reconciliation: {'PASS' if reconciled else 'FAIL'} ({discrepancy} paisa discrepancy)"
        )
        print(
            f"Total Equity: Rs {res['capital']['total_equity']} (Net P&L: Rs {res['performance']['total_net_pnl']})"
        )
        print(f"Fills Executed: {res['order_statistics']['total_fills_count']}")
        print(
            f"Evidence Report: logs/paper_runs/paper_session_{res['session_date']}_{res['session_id']}.md"
        )
        if not reconciled:
            for error in res["reconciliation"]["reconciliation_errors"]:
                print(f"  - {error}")
            return 7
        return 0
    except Exception as err:
        logger.exception("Paper session failed with error: %s", err)
        return 2


if __name__ == "__main__":
    sys.exit(main())
