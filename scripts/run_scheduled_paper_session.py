"""Pre-open refresh then a paper trading session, for unattended scheduled runs.

A scheduled run has nobody watching it, so every step that could silently produce a plausible-but-
wrong session is checked and made to fail loudly instead:

* **Bars must be fresh.** The decision uses the last *completed* session. If the refresh cannot
  advance past the newest bar already cached, the run stops rather than deciding on stale data --
  which is exactly the failure mode that made an earlier version of the loader rank week-old prices.
* **Macro must cover the same date.** Missing India VIX or NIFTY makes every feature row
  uncomputable, and the session would report a clean 0-proposal run that looked like a decision.
* **Today must be a trading day.** This repository holds no NSE holiday calendar, so that cannot be
  asserted in advance. It is inferred after the fact: if the provider has no bar for the previous
  session, or the refresh returns nothing new, the run stops.

None of this makes the session *correct* -- it makes it honest about when it should not run.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))

#: Where the refreshed evidence lands. Kept distinct from the historical stores so a scheduled run
#: can never overwrite the ten-year caches other work depends on.
BARS_CACHE = PROJECT_ROOT / "data/evidence/market-cache/nifty500-refresh-20230828-20260827"
MACRO_CACHE = PROJECT_ROOT / "data/evidence/market-cache/macro-refresh-20230828-20260827"
UNIVERSE_CSV = PROJECT_ROOT / "data/evidence/market-cache/scheduled-universe-instruments.csv"

#: Bars are fetched three years back. The kernel consumes at most 400 trailing sessions, so this is
#: comfortable headroom, and it stays clear of the provider's ten-year retrieval limit.
LOOKBACK_DAYS = 3 * 365


def log(message: str) -> None:
    print(f"{datetime.now(IST):%Y-%m-%d %H:%M:%S IST} | {message}", flush=True)


def newest_cached_bar_date() -> date | None:
    """The newest exchange date already in the bars cache, or None when it is empty."""
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from cached_nifty50_evidence import historical_acquisition_from_verified

    from quant_system.evidence import EvidenceResourceType, EvidenceStore, EvidenceStoreConfig

    store_root = BARS_CACHE / "store"
    if not store_root.exists():
        return None
    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    newest: date | None = None
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        records = historical_acquisition_from_verified(verified).records
        if records and (newest is None or records[-1].exchange_date > newest):
            newest = records[-1].exchange_date
    return newest


def build_universe_csv(universe_name: str) -> int:
    """Write the instrument-key CSV the ingester needs, from the published constituent authority.

    The ingester requires an ``Instrument Key`` column; the constituent authorities do not carry
    one. Joining them here is why an earlier attempt silently ingested nothing and still exited 0.
    """
    import csv

    authority = {
        "NIFTY50": PROJECT_ROOT / "data/authorities/nse-nifty50-constituents.csv",
        "NIFTY500": PROJECT_ROOT / "data/authorities/nse-nifty500-constituents.csv",
    }[universe_name.upper()]
    with open(authority, encoding="utf-8-sig") as handle:
        wanted = {(row.get("Symbol") or "").strip() for row in csv.DictReader(handle)}
    with open(
        PROJECT_ROOT / "data/authorities/nse-all-listed-equities.csv", encoding="utf-8-sig"
    ) as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = [
            row
            for row in reader
            if (row.get("Symbol") or "").strip() in wanted
            and (row.get("Instrument Key") or "").startswith("NSE_EQ|")
        ]
    UNIVERSE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(UNIVERSE_CSV, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def refresh_bars(universe_name: str, to_day: date) -> None:
    matched = build_universe_csv(universe_name)
    log(f"universe {universe_name}: {matched} instruments with provider keys")
    if matched == 0:
        raise SystemExit("refusing to run: no instrument keys resolved for the universe")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/ingest_all_market_data.py"),
        "--universe-csv",
        str(UNIVERSE_CSV),
        "--cache-root",
        str(BARS_CACHE),
        "--from-date",
        (to_day - timedelta(days=LOOKBACK_DAYS)).isoformat(),
        "--to-date",
        to_day.isoformat(),
        "--concurrency",
        "8",
    ]
    log("refreshing bars ...")
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)


def refresh_macro(to_day: date) -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from ingest_macro_regimes import ingest_macro_series

    log("refreshing macro ...")
    ingest_macro_series(
        MACRO_CACHE,
        from_date=to_day - timedelta(days=LOOKBACK_DAYS),
        to_date=to_day,
    )


def macro_covers(day: date) -> bool:
    import json

    for name in ("INDIAVIX", "NIFTY50"):
        path = MACRO_CACHE / f"macro_{name}.json"
        if not path.is_file():
            return False
        days = {c[0][:10] for c in json.loads(path.read_text(encoding="utf-8")).get("candles", [])}
        if day.isoformat() not in days:
            return False
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe-name", default="NIFTY500", choices=["NIFTY50", "NIFTY500"])
    parser.add_argument("--capital", default="1000000.0")
    parser.add_argument("--end-time-ist", default="15:30:00")
    parser.add_argument("--interval-seconds", default="30")
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="use the cache as-is; for rehearsing the wiring outside market hours",
    )
    args = parser.parse_args()

    today = datetime.now(IST).date()
    log(f"scheduled paper session for {today:%Y-%m-%d %A}")
    if today.weekday() >= 5:
        log("refusing: NSE does not trade at weekends")
        return 2

    before = newest_cached_bar_date()
    log(f"newest cached bar before refresh: {before}")

    if not args.skip_refresh:
        target = today - timedelta(days=1)
        refresh_bars(args.universe_name, target)
        refresh_macro(target)
        after = newest_cached_bar_date()
        log(f"newest cached bar after refresh : {after}")
        if after is None:
            log("refusing: the bars cache is empty after a refresh")
            return 3
        if before is not None and after <= before:
            # A public holiday, a provider outage, or an expired token all land here. Deciding on
            # unchanged data would still produce a full session report, which is the dangerous part.
            log(f"refusing: refresh did not advance past {before}; treating today as non-trading")
            return 4
        if not macro_covers(after):
            log(f"refusing: macro does not cover {after}; every feature row would be uncomputable")
            return 5

    log("starting paper session ...")
    session = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/run_paper_pilot_session.py"),
        "--realtime",
        "--universe-name",
        args.universe_name,
        "--capital",
        args.capital,
        "--end-time-ist",
        args.end_time_ist,
        "--interval-seconds",
        args.interval_seconds,
    ]
    completed = subprocess.run(session, check=False, cwd=PROJECT_ROOT)
    log(f"paper session exited {completed.returncode}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
