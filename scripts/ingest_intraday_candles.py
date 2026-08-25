"""High-resolution multi-year intraday market data ingestion pipeline for top liquid Indian equities."""

from __future__ import annotations

import concurrent.futures
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from quant_system.config import load_env_file

ROOT_DIR = Path(__file__).resolve().parent.parent


def read_liquid_symbols(profiles_json: Path, limit: int = 50) -> list[dict[str, Any]]:
    """Load top liquid instruments from market profiles."""
    if not profiles_json.is_file():
        raise FileNotFoundError(f"Profiles JSON not found: {profiles_json}")
    with open(profiles_json, encoding="utf-8") as f:
        profiles = json.load(f)
    # Sort by ADTV descending
    profiles.sort(key=lambda p: p.get("avg_daily_turnover_inr", 0), reverse=True)
    selected: list[dict[str, Any]] = []
    for p in profiles[:limit]:
        selected.append(
            {
                "symbol": p["symbol"],
                "isin": p["isin"],
                "instrument_key": f"NSE_EQ|{p['isin']}",
                "company_name": p["company_name"],
                "adtv_inr": p["avg_daily_turnover_inr"],
            }
        )
    return selected


def fetch_intraday_chunked(
    instrument_key: str,
    symbol: str,
    interval: str,
    from_date: date,
    to_date: date,
    token: str,
    rate_limit_sleep: float = 0.03,
) -> list[list[Any]]:
    """Fetch intraday candles in 30-day chunks and stitch chronologically."""
    encoded_key = urllib.parse.quote(instrument_key, safe="")
    all_candles: list[list[Any]] = []

    current_end = to_date
    while current_end > from_date:
        current_start = max(from_date, current_end - timedelta(days=28))
        url = f"https://api.upstox.com/v3/historical-candle/{encoded_key}/{interval}/{current_end.isoformat()}/{current_start.isoformat()}"

        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "QuantOS/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            candles = data.get("data", {}).get("candles", [])
            all_candles.extend(candles)
        except Exception:
            pass

        if rate_limit_sleep > 0:
            time.sleep(rate_limit_sleep)
        current_end = current_start - timedelta(days=1)

    # Sort strictly ascending by timestamp
    all_candles.sort(key=lambda c: c[0])
    return all_candles


def run_intraday_ingestion(
    profiles_json: Path,
    output_dir: Path,
    interval: str = "15minute",
    from_date: date = date(2025, 8, 22),
    to_date: date = date(2026, 8, 21),
    limit: int = 50,
    concurrency: int = 4,
) -> dict[str, Any]:
    """Ingest intraday candles for top liquid symbols."""
    load_env_file()
    output_dir.mkdir(parents=True, exist_ok=True)
    token = os.getenv("UPSTOX_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN is required in environment.")

    targets = read_liquid_symbols(profiles_json, limit=limit)
    days_count = (to_date - from_date).days

    print(f"=== INTRADAY DATA INGESTION ({interval}) ===", flush=True)
    print(f"Universe Source : {profiles_json} ({len(targets)} liquid targets)", flush=True)
    print(f"Range           : {from_date} -> {to_date} ({days_count} days)", flush=True)
    print(f"Output Directory: {output_dir.resolve()}", flush=True)
    print(f"Concurrency     : {concurrency} worker threads\n", flush=True)

    results: dict[str, Any] = {}
    lock = threading.Lock()
    completed = 0
    total_bars = 0
    start_time = time.time()

    def process_one(item: dict[str, Any]) -> tuple[str, int, str]:
        sym = item["symbol"]
        key = item["instrument_key"]
        candles = fetch_intraday_chunked(
            instrument_key=key,
            symbol=sym,
            interval=interval,
            from_date=from_date,
            to_date=to_date,
            token=token,
        )
        out_file = output_dir / f"intraday_15m_{sym}.json"
        payload = {
            "symbol": sym,
            "instrument_key": key,
            "interval": interval,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "bars_count": len(candles),
            "received_start": candles[0][0] if candles else None,
            "received_end": candles[-1][0] if candles else None,
            "ingested_at": datetime.now(UTC).isoformat(),
            "candles": candles,
        }
        out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return sym, len(candles), str(out_file)

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process_one, t): t for t in targets}
        for f in concurrent.futures.as_completed(futures):
            target = futures[f]
            try:
                sym, count, path = f.result()
                with lock:
                    completed += 1
                    total_bars += count
                    results[sym] = {"bars": count, "file": path}
                    print(
                        f"[{completed:>2}/{len(targets)}] {sym:<12} -> {count:>5,} intraday bars saved. (Total: {total_bars:,})",
                        flush=True,
                    )
            except Exception as e:
                print(f"Error processing {target['symbol']}: {e}", flush=True)

    elapsed = time.time() - start_time
    summary_path = output_dir / "intraday_ingestion_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "interval": interval,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "total_targets": len(targets),
                "total_intraday_bars": total_bars,
                "elapsed_seconds": round(elapsed, 2),
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"\nIntraday Ingestion Complete: {total_bars:,} bars across {len(targets)} stocks in {elapsed:.1f}s.",
        flush=True,
    )
    return results


if __name__ == "__main__":
    prof_p = ROOT_DIR / "data" / "evidence" / "market-analysis" / "nse_all_market_profiles.json"
    out_p = ROOT_DIR / "data" / "evidence" / "market-cache" / "intraday-liquid-20230822-20260821"
    run_intraday_ingestion(prof_p, out_p, limit=50)
