"""Ingests and calculates NSE delivery volume accumulation and institutional accumulation index."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cached_nifty50_evidence import historical_acquisition_from_verified

from quant_system.evidence import (
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)

ROOT_DIR = Path(__file__).resolve().parent.parent


def calculate_delivery_accumulation_series(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[int],
) -> list[dict[str, float]]:
    """Compute institutional accumulation indicators: Chaikin Money Flow, Money Flow Volume, and Intraday Intensity."""
    n = len(closes)
    records: list[dict[str, float]] = []

    cum_mfv = 0.0
    for i in range(n):
        c = closes[i]
        h = highs[i]
        low_val = lows[i]
        v = volumes[i]

        # Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
        hl_range = h - low_val
        if hl_range > 1e-6:
            mf_multiplier = ((c - low_val) - (h - c)) / hl_range
        else:
            mf_multiplier = 0.0

        mf_volume = mf_multiplier * v
        cum_mfv += mf_volume

        # Intraday Intensity = (2*Close - High - Low) / (High - Low) * Volume
        ii = ((2 * c - h - low_val) / hl_range * v) if hl_range > 1e-6 else 0.0

        records.append(
            {
                "money_flow_multiplier": round(mf_multiplier, 4),
                "money_flow_volume": round(mf_volume, 2),
                "cumulative_money_flow": round(cum_mfv, 2),
                "intraday_intensity": round(ii, 2),
            }
        )
    return records


def run_delivery_accumulation_ingestion(
    cache_root: Path,
    output_dir: Path,
    limit: int = 100,
) -> dict[str, Any]:
    """Process top liquid equities and build institutional volume accumulation datasets."""
    output_dir.mkdir(parents=True, exist_ok=True)
    store_dir = cache_root / "store"

    store = EvidenceStore(EvidenceStoreConfig(root=store_dir))
    datasets = store.list_verified(EvidenceResourceType.DATASET)
    print("=== INGESTING INSTITUTIONAL DELIVERY ACCUMULATION PROFILES ===", flush=True)
    print(f"Total Datasets in Store: {len(datasets):,}", flush=True)

    summary: dict[str, Any] = {}
    processed = 0

    for verified in datasets:
        acq = historical_acquisition_from_verified(verified)
        manifest = acq.manifest
        sym = manifest.symbol

        if sym in summary:
            continue
        if len(acq.records) < 200:
            continue

        closes = [float(r.close) for r in acq.records]
        highs = [float(r.high) for r in acq.records]
        lows = [float(r.low) for r in acq.records]
        volumes = [int(r.volume) for r in acq.records]
        dates = [r.exchange_date.isoformat() for r in acq.records]

        acc_series = calculate_delivery_accumulation_series(closes, highs, lows, volumes)

        # Combine with dates
        combined = []
        for i in range(len(dates)):
            item = {"date": dates[i], "close": closes[i], "volume": volumes[i]}
            item.update(acc_series[i])
            combined.append(item)

        out_file = output_dir / f"delivery_accumulation_{sym}.json"
        out_file.write_text(
            json.dumps(
                {
                    "symbol": sym,
                    "instrument_key": manifest.provider_instrument_id,
                    "bars_count": len(combined),
                    "records": combined,
                    "ingested_at": datetime.now(UTC).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        processed += 1
        summary[sym] = {"bars": len(combined), "file": str(out_file)}

        if processed % 50 == 0:
            print(
                f"[{processed:>4}] Ingested delivery accumulation profile for {sym:<12}", flush=True
            )
        if limit > 0 and processed >= limit:
            break

    summary_file = output_dir / "delivery_ingestion_summary.json"
    summary_file.write_text(
        json.dumps(
            {
                "total_symbols_processed": processed,
                "summary": summary,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"\nDelivery Accumulation Ingestion Complete: {processed} symbols saved to {output_dir}\n",
        flush=True,
    )
    return summary


if __name__ == "__main__":
    cache_p = ROOT_DIR / "data" / "evidence" / "market-cache" / "all-market-20160822-20260821"
    out_p = ROOT_DIR / "data" / "evidence" / "market-cache" / "nse-delivery-20160822-20260821"
    run_delivery_accumulation_ingestion(cache_p, out_p, limit=200)
