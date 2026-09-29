"""Builders for a miniature evidence store in the real on-disk format, for market-index tests.

Test fixtures only: the product itself never reads synthetic prices.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

LISTINGS_HEADER = "Symbol,Company Name,ISIN Code,Instrument Key,Instrument Type,Security Type,Lot Size,Tick Size\n"


def sessions(start: date, count: int) -> list[str]:
    """``count`` weekday dates from ``start`` (holidays ignored; enough for fixtures)."""
    out: list[str] = []
    day = start
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day.isoformat())
        day += timedelta(days=1)
    return out


def write_dataset(
    market_cache: Path,
    cache_name: str,
    dataset_id: str,
    symbol: str,
    rows: list[tuple[str, float, float, float, float, int]],
    acquired_at: str,
    committed: bool = True,
    isin: str = "INE000000000",
    extra_raw_lines: tuple[str, ...] = (),
) -> None:
    store = market_cache / cache_name / "store"
    lines = [
        json.dumps(
            {
                "exchange_date": d,
                "open": f"{o}",
                "high": f"{h}",
                "low": f"{low}",
                "close": f"{c}",
                "volume": v,
                "symbol": symbol,
            }
        )
        for d, o, h, low, c, v in rows
    ]
    lines.extend(extra_raw_lines)
    payload = gzip.compress(("\n".join(lines) + "\n").encode("utf-8"))
    digest = hashlib.sha256(payload).hexdigest()
    rel = f"blobs/sha256/{digest[:2]}/{digest}.jsonl.gz"
    (store / rel).parent.mkdir(parents=True, exist_ok=True)
    (store / rel).write_bytes(payload)
    dataset_dir = store / "datasets" / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "blobs": [{"relative_path": rel}],
        "manifest_hash": f"mh-{dataset_id}",
        "metadata": {
            "symbol": symbol,
            "interval": "1",
            "acquired_at": acquired_at,
            "provider_instrument_id": f"NSE_EQ|{isin}",
            "received_range": {"start": rows[0][0], "end": rows[-1][0]},
            "row_count": len(rows),
        },
    }
    (dataset_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if committed:
        (dataset_dir / "COMMITTED").write_text("", encoding="utf-8")


def trending_rows(
    dates: list[str], start_price: float, daily_growth: float, volume: int = 100_000
) -> list[tuple[str, float, float, float, float, int]]:
    rows = []
    price = start_price
    for d in dates:
        o = round(price, 2)
        c = round(price * (1 + daily_growth), 2)
        rows.append((d, o, round(max(o, c) * 1.01, 2), round(min(o, c) * 0.99, 2), c, volume))
        price = c
    return rows


def write_reference(data_folder: Path, listings: list[str], liquid: list[str]) -> None:
    authorities = data_folder / "authorities"
    authorities.mkdir(parents=True, exist_ok=True)
    (authorities / "nse-all-listed-equities.csv").write_text(
        LISTINGS_HEADER + "".join(line + "\n" for line in listings), encoding="utf-8"
    )
    (authorities / "nse-research-universe-liquid-10y.csv").write_text(
        "# fixture universe\nSymbol,ISIN Code,InstrumentKey,YearsActive,MedianDailyTurnoverINR\n"
        + "".join(f"{s},X,NSE_EQ|X,10,1\n" for s in liquid),
        encoding="utf-8",
    )


HISTORY = "all-market-20200101-20201231"
REFRESH = "nifty500-refresh-20200101-20210131"
DATES = sessions(date(2020, 1, 1), 320)


def build_standard_store(folder: Path) -> None:
    """The shared fixture store (see ``tests/test_market_index.py`` for what each symbol covers).

    * AAA: stitched history + refresh (an older history vintage and one invalid row are ignored).
    * BBB: refresh re-adjusted (halved) against history, so only the refresh is used; demerger
      2020-06-15 (before the lab's first trade date).
    * NIFTYBEES: history-only benchmark ETF.
    * CCC: uncommitted, so absent.
    * DDD: refresh-only, PCA-flagged, demerger 2020-09-15 inside the lab window.
    """
    cache = folder / "evidence" / "market-cache"
    history_dates, refresh_dates = DATES[:300], DATES[100:]

    aaa = trending_rows(DATES, 100.0, 0.001)
    write_dataset(
        cache,
        HISTORY,
        "dset_aaa_old",
        "AAA",
        trending_rows(history_dates, 50.0, 0.0),
        "2020-01-01T00:00:00Z",
    )
    write_dataset(
        cache,
        HISTORY,
        "dset_aaa",
        "AAA",
        aaa[:300],
        "2021-01-01T00:00:00Z",
        extra_raw_lines=(
            '{"exchange_date": "2019-12-31", "open": "1", "high": "1", "low": "1", "close": "-5"}',
        ),
    )
    write_dataset(cache, REFRESH, "dset_aaa_r", "AAA", aaa[100:], "2021-02-01T00:00:00Z")

    bbb = trending_rows(DATES, 200.0, -0.0005)
    write_dataset(cache, HISTORY, "dset_bbb", "BBB", bbb[:300], "2021-01-01T00:00:00Z")
    halved = [(d, o / 2, h / 2, low / 2, c / 2, v) for d, o, h, low, c, v in bbb[100:]]
    write_dataset(cache, REFRESH, "dset_bbb_r", "BBB", halved, "2021-02-01T00:00:00Z")

    write_dataset(
        cache,
        HISTORY,
        "dset_bench",
        "NIFTYBEES",
        trending_rows(history_dates, 150.0, 0.0005),
        "2021-01-01T00:00:00Z",
        isin="INF204KB14I2",
    )
    write_dataset(
        cache,
        HISTORY,
        "dset_ccc",
        "CCC",
        trending_rows(history_dates, 10.0, 0.0),
        "2021-01-01T00:00:00Z",
        committed=False,
    )
    write_dataset(
        cache,
        REFRESH,
        "dset_ddd_r",
        "DDD",
        trending_rows(refresh_dates, 30.0, 0.002),
        "2021-02-01T00:00:00Z",
    )

    write_reference(
        folder,
        listings=[
            "AAA,ALPHA LTD,INE0AAA,NSE_EQ|INE0AAA,EQ,NORMAL,1,1.0",
            "BBB,BETA LTD,INE0BBB,NSE_EQ|INE0BBB,EQ,NORMAL,1,1.0",
            "NIFTYBEES,NIP IND ETF NIFTY BEES,INF204KB14I2,NSE_EQ|INF204KB14I2,EQ,NORMAL,1,1.0",
            "DDD,DELTA LTD,INE0DDD,NSE_EQ|INE0DDD,BE,PCA,1,1.0",
        ],
        liquid=["AAA", "BBB"],
    )
    write_actions(
        cache,
        HISTORY,
        "BBB",
        [("15-Jun-2020", "Demerger"), ("01-Mar-2020", "Dividend - Rs 2 Per Share")],
    )
    write_actions(cache, HISTORY, "AAA", [("10-Feb-2020", "Interim Dividend - Rs 5 Per Share")])
    write_actions(cache, HISTORY, "DDD", [("15-Sep-2020", "Demerger")])


def write_actions(
    market_cache: Path, cache_name: str, symbol: str, actions: list[tuple[str, str]]
) -> None:
    folder = market_cache / cache_name / "corporate-actions"
    folder.mkdir(parents=True, exist_ok=True)
    records = [{"exDate": ex, "subject": subject, "symbol": symbol} for ex, subject in actions]
    (folder / f"nse-corporate-actions-{symbol}.json").write_text(
        json.dumps(records), encoding="utf-8"
    )
