"""Builds institutional multi-dimensional feature store combining price, volume, micro-volatility, macro regimes, and forward targets."""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# Add workspace path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

from quant_system.evidence import (
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from cached_nifty50_evidence import historical_acquisition_from_verified


def compute_rsi(prices: list[float], period: int = 14) -> list[float]:
    """Compute Relative Strength Index."""
    n = len(prices)
    rsi = [50.0] * n
    if n <= period:
        return rsi

    gains = [max(0.0, prices[i] - prices[i - 1]) for i in range(1, n)]
    losses = [max(0.0, prices[i - 1] - prices[i]) for i in range(1, n)]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, n):
        g = gains[i - 1]
        l = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        if avg_loss < 1e-9:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = round(100.0 - (100.0 / (1.0 + rs)), 2)
    return rsi


def build_feature_store(
    cache_root: Path,
    macro_dir: Path,
    output_dir: Path,
    min_bars: int = 500,
    top_n_stocks: int = 200,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    store_dir = cache_root / "store"
    store = EvidenceStore(EvidenceStoreConfig(root=store_dir))

    # 1. Load Macro Regimes
    vix_file = macro_dir / "macro_INDIAVIX.json"
    nifty_file = macro_dir / "macro_NIFTY50.json"
    
    vix_by_date: dict[str, float] = {}
    if vix_file.is_file():
        vix_data = json.loads(vix_file.read_text(encoding="utf-8"))
        for c in vix_data.get("candles", []):
            dt_str = c[0][:10]
            vix_by_date[dt_str] = float(c[4])

    nifty_by_date: dict[str, float] = {}
    if nifty_file.is_file():
        nifty_data = json.loads(nifty_file.read_text(encoding="utf-8"))
        for c in nifty_data.get("candles", []):
            dt_str = c[0][:10]
            nifty_by_date[dt_str] = float(c[4])

    # 2. Select Top N Liquid Equities
    profiles_p = ROOT_DIR / "data" / "evidence" / "market-analysis" / "nse_all_market_profiles.json"
    target_symbols: set[str] = set()
    if profiles_p.is_file():
        profs = json.loads(profiles_p.read_text(encoding="utf-8"))
        profs.sort(key=lambda x: x.get("avg_daily_turnover_inr", 0), reverse=True)
        target_symbols = {p["symbol"] for p in profs[:top_n_stocks]}

    print(f"=== BUILDING MULTI-DIMENSIONAL FEATURE STORE ===", flush=True)
    print(f"Target Universe Size: {len(target_symbols)} Liquid Equities", flush=True)
    print(f"Macro series loaded: India VIX ({len(vix_by_date)} days), NIFTY 50 ({len(nifty_by_date)} days)", flush=True)

    datasets = store.list_verified(EvidenceResourceType.DATASET)
    all_feature_rows: list[dict[str, Any]] = []
    
    # Store daily rows grouped by date for cross-sectional ranking
    date_grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)

    processed_count = 0
    for verified in datasets:
        acq = historical_acquisition_from_verified(verified)
        manifest = acq.manifest
        sym = manifest.symbol
        
        if target_symbols and sym not in target_symbols:
            continue
        if len(acq.records) < min_bars:
            continue

        records = acq.records
        n = len(records)
        dates = [r.exchange_date.isoformat() for r in records]
        opens = [float(r.open) for r in records]
        highs = [float(r.high) for r in records]
        lows = [float(r.low) for r in records]
        closes = [float(r.close) for r in records]
        volumes = [int(r.volume) for r in records]

        rsi_14 = compute_rsi(closes, period=14)

        for i in range(50, n):
            c = closes[i]
            o = opens[i]
            h = highs[i]
            l = lows[i]
            v = volumes[i]
            dt = dates[i]

            # Returns
            ret_1d = (c / closes[i - 1] - 1.0) if closes[i - 1] > 0 else 0.0
            ret_5d = (c / closes[i - 5] - 1.0) if closes[i - 5] > 0 else 0.0
            ret_21d = (c / closes[i - 21] - 1.0) if closes[i - 21] > 0 else 0.0

            # Forward Targets
            fwd_ret_1d = (closes[i + 1] / c - 1.0) if (i + 1 < n and c > 0) else None
            fwd_ret_5d = (closes[i + 5] / c - 1.0) if (i + 5 < n and c > 0) else None
            fwd_ret_21d = (closes[i + 21] / c - 1.0) if (i + 21 < n and c > 0) else None

            # High-Frequency Volatility Estimators
            # Garman-Klass = 0.5 * ln(H/L)^2 - (2*ln(2) - 1) * ln(C/O)^2
            if h > 0 and l > 0 and o > 0 and c > 0:
                log_hl = math.log(h / l)
                log_co = math.log(c / o)
                gk_vol = math.sqrt(max(0.0, 0.5 * (log_hl ** 2) - (2.0 * math.log(2.0) - 1.0) * (log_co ** 2)))
                # Parkinson = ln(H/L) / sqrt(4 * ln(2))
                park_vol = log_hl / math.sqrt(4.0 * math.log(2.0))
            else:
                gk_vol = 0.0
                park_vol = 0.0

            # Technicals: Moving Average Ratios
            sma_20 = sum(closes[i - 20 : i]) / 20.0
            sma_50 = sum(closes[i - 50 : i]) / 50.0
            ratio_sma20 = (c / sma_20 - 1.0) if sma_20 > 0 else 0.0
            ratio_sma50 = (c / sma_50 - 1.0) if sma_50 > 0 else 0.0

            # Volume Z-score
            vol_window = volumes[i - 20 : i]
            mean_vol = sum(vol_window) / 20.0
            std_vol = math.sqrt(sum((x - mean_vol) ** 2 for x in vol_window) / 20.0) if len(vol_window) > 1 else 1.0
            vol_zscore = (v - mean_vol) / max(1.0, std_vol)

            # Money Flow Multiplier
            hl_range = h - l
            mf_multiplier = ((c - l) - (h - c)) / hl_range if hl_range > 1e-6 else 0.0

            # Macro Factors
            cur_vix = vix_by_date.get(dt, 15.0)
            vix_regime = "HIGH_VOL" if cur_vix > 20.0 else ("LOW_VOL" if cur_vix < 14.0 else "NORMAL_VOL")
            
            cur_nifty = nifty_by_date.get(dt, 0.0)
            nifty_ret_5d = 0.0
            fwd_nifty_5d = 0.0
            if cur_nifty > 0:
                # Find past 5d nifty
                past_dt = dates[i - 5]
                past_nifty = nifty_by_date.get(past_dt, cur_nifty)
                nifty_ret_5d = (cur_nifty / past_nifty - 1.0) if past_nifty > 0 else 0.0
                if i + 5 < n:
                    fwd_dt = dates[i + 5]
                    fwd_nifty = nifty_by_date.get(fwd_dt, cur_nifty)
                    fwd_nifty_5d = (fwd_nifty / cur_nifty - 1.0) if cur_nifty > 0 else 0.0

            fwd_alpha_5d = (fwd_ret_5d - fwd_nifty_5d) if fwd_ret_5d is not None else None

            row = {
                "date": dt,
                "symbol": sym,
                "close": round(c, 2),
                "volume": v,
                "ret_1d": round(ret_1d, 5),
                "ret_5d": round(ret_5d, 5),
                "ret_21d": round(ret_21d, 5),
                "gk_vol": round(gk_vol, 5),
                "park_vol": round(park_vol, 5),
                "rsi_14": round(rsi_14[i], 2),
                "ratio_sma20": round(ratio_sma20, 4),
                "ratio_sma50": round(ratio_sma50, 4),
                "vol_zscore": round(vol_zscore, 3),
                "mf_multiplier": round(mf_multiplier, 4),
                "india_vix": round(cur_vix, 2),
                "vix_regime": vix_regime,
                "nifty_ret_5d": round(nifty_ret_5d, 5),
                "fwd_ret_1d": round(fwd_ret_1d, 5) if fwd_ret_1d is not None else None,
                "fwd_ret_5d": round(fwd_ret_5d, 5) if fwd_ret_5d is not None else None,
                "fwd_ret_21d": round(fwd_ret_21d, 5) if fwd_ret_21d is not None else None,
                "fwd_alpha_5d": round(fwd_alpha_5d, 5) if fwd_alpha_5d is not None else None,
            }
            date_grouped_rows[dt].append(row)

        processed_count += 1
        if processed_count % 25 == 0:
            print(f"[{processed_count:>3}/{len(target_symbols)}] Processed features for {sym:<12}", flush=True)

    # 3. Add Point-in-Time Cross-Sectional Ranks
    print(f"\nComputing point-in-time cross-sectional rankings across {len(date_grouped_rows):,} trading sessions...", flush=True)
    for dt, rows in date_grouped_rows.items():
        if not rows:
            continue
        # Sort by ret_5d
        rows.sort(key=lambda r: r["ret_5d"])
        n_rows = len(rows)
        for rank_idx, r in enumerate(rows):
            r["cs_rank_mom5d"] = round((rank_idx + 1) / n_rows, 4)

        # Sort by vol_zscore
        rows.sort(key=lambda r: r["vol_zscore"])
        for rank_idx, r in enumerate(rows):
            r["cs_rank_vol_surprise"] = round((rank_idx + 1) / n_rows, 4)

        all_feature_rows.extend(rows)

    # Sort master feature store chronologically
    all_feature_rows.sort(key=lambda r: (r["date"], r["symbol"]))
    print(f"Total Feature Rows Generated: {len(all_feature_rows):,}", flush=True)

    # 4. Save to CSV and JSON Lines
    csv_file = output_dir / "multidim_feature_store.csv"
    if all_feature_rows:
        fieldnames = list(all_feature_rows[0].keys())
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_feature_rows)

    meta_file = output_dir / "feature_store_metadata.json"
    meta_file.write_text(json.dumps({
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(all_feature_rows),
        "total_symbols": processed_count,
        "feature_count": len(fieldnames) if all_feature_rows else 0,
        "features_list": fieldnames if all_feature_rows else [],
        "csv_path": str(csv_file),
    }, indent=2), encoding="utf-8")

    print(f"Feature Store written to: {csv_file} ({csv_file.stat().st_size / (1024*1024):.2f} MB)", flush=True)
    return csv_file


if __name__ == "__main__":
    c_root = ROOT_DIR / "data" / "evidence" / "market-cache" / "all-market-20160822-20260821"
    m_dir = ROOT_DIR / "data" / "evidence" / "market-cache" / "macro-regimes-20160822-20260821"
    out_dir = ROOT_DIR / "data" / "evidence" / "feature-store"
    build_feature_store(c_root, m_dir, out_dir, top_n_stocks=150)
