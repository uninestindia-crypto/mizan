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


def existing_bar_count(path: Path) -> int:
    """Bars already cached at `path`, or 0 when there is no readable cache there."""
    if not path.is_file():
        return 0
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    candles = cached.get("candles")
    return len(candles) if isinstance(candles, list) else 0


def may_overwrite_macro_cache(new_bar_count: int, cached_bar_count: int) -> bool:
    """Whether a fetch result may replace what is already on disk.

    The write used to be unconditional after `urlopen` returned. A **200 carrying no candles** --
    an empty envelope, a rate-limit body, a window the provider decided it had nothing for --
    therefore replaced a good `macro_INDIAVIX.json` with an empty candle list. `macro_covers` is
    then permanently false and the scheduled session refuses at exit 5 until someone re-ingests by
    hand. A 401 was safe, because it raised; a 200 was not, because it did not.

    A first ingest with nothing cached is allowed to write nothing, so an empty result is still
    recorded rather than looking like a run that never happened. What is refused is **destroying
    bars that exist** in exchange for none.
    """
    if new_bar_count > 0:
        return True
    return cached_bar_count == 0


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
            cached_bars = existing_bar_count(out_file)
            if not may_overwrite_macro_cache(len(candles), cached_bars):
                print(
                    f"REFUSED to overwrite {out_file.name}: the provider returned 0 bars and "
                    f"{cached_bars:,} are already cached. Keeping the cache; this symbol is a "
                    "failure for this run.",
                    flush=True,
                )
                continue
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
            out_file.write_text(json.dumps(summary_item, indent=2), encoding="utf-8", newline="\n")
            results[sym] = {
                "bars_count": len(candles),
                "latest_close": summary_item["latest_close"],
                "file": str(out_file),
            }
        except Exception as e:
            print(f"Error fetching macro {sym}: {e}", flush=True)

    summary_file = output_dir / "macro_regimes_summary.json"
    summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8", newline="\n")
    print(f"Macro regimes saved to: {output_dir}\n", flush=True)
    return results


if __name__ == "__main__":
    out = ROOT_DIR / "data" / "evidence" / "market-cache" / "macro-regimes-20160822-20260821"
    ingest_macro_series(out)
