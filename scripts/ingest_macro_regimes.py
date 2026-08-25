"""Ingests 10-year macro benchmark regimes: NIFTY 50, India VIX, NIFTY Bank, NIFTY IT."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from quant_system.config import load_env_file

ROOT_DIR = Path(__file__).resolve().parent.parent

MACRO_INDICES = [
    {"symbol": "NIFTY50", "key": "NSE_INDEX|Nifty 50", "name": "NIFTY 50 Index (Market Benchmark)"},
    {
        "symbol": "INDIAVIX",
        "key": "NSE_INDEX|India VIX",
        "name": "India VIX (Market Volatility Index)",
    },
    {
        "symbol": "NIFTYBANK",
        "key": "NSE_INDEX|Nifty Bank",
        "name": "NIFTY Bank Index (Financials Benchmark)",
    },
    {"symbol": "NIFTYIT", "key": "NSE_INDEX|Nifty IT", "name": "NIFTY IT Index (Tech Benchmark)"},
]


def ingest_macro_series(
    output_dir: Path,
    from_date: date = date(2016, 8, 22),
    to_date: date = date(2026, 8, 21),
) -> dict[str, Any]:
    load_env_file()
    output_dir.mkdir(parents=True, exist_ok=True)
    token = os.getenv("UPSTOX_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN is required in environment.")

    results: dict[str, Any] = {}
    print(
        f"=== INGESTING MACRO BENCHMARKS & VOLATILITY REGIMES ({from_date} -> {to_date}) ===",
        flush=True,
    )

    for item in MACRO_INDICES:
        sym = item["symbol"]
        key = item["key"]
        name = item["name"]
        enc_key = urllib.parse.quote(key, safe="")
        url = f"https://api.upstox.com/v3/historical-candle/{enc_key}/days/1/{to_date.isoformat()}/{from_date.isoformat()}"

        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "QuantOS/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            candles = data.get("data", {}).get("candles", [])
            print(f"[{sym:<10}] {name} -> {len(candles):,} daily bars fetched.", flush=True)

            out_file = output_dir / f"macro_{sym}.json"
            summary_item = {
                "symbol": sym,
                "instrument_key": key,
                "name": name,
                "bars_count": len(candles),
                "received_start": candles[-1][0] if candles else None,
                "received_end": candles[0][0] if candles else None,
                "latest_close": candles[0][4] if candles else None,
                "ingested_at": datetime.now(UTC).isoformat(),
                "candles": candles,
            }
            out_file.write_text(json.dumps(summary_item, indent=2), encoding="utf-8")
            results[sym] = {
                "bars_count": len(candles),
                "latest_close": summary_item["latest_close"],
                "file": str(out_file),
            }
        except Exception as e:
            print(f"Error fetching macro {sym}: {e}", flush=True)

    summary_file = output_dir / "macro_regimes_summary.json"
    summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Macro regimes saved to: {output_dir}\n", flush=True)
    return results


if __name__ == "__main__":
    out = ROOT_DIR / "data" / "evidence" / "market-cache" / "macro-regimes-20160822-20260821"
    ingest_macro_series(out)
