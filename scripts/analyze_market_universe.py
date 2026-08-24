"""Senior Quantitative Data Science & Market Structure Analysis across the entire NSE Universe."""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
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


@dataclass(slots=True)
class StockQuantitativeProfile:
    symbol: str
    company_name: str
    isin: str
    instrument_type: str
    security_type: str
    is_nifty50: bool
    is_nifty500: bool
    status: str
    bars_count: int
    first_date: str
    last_date: str
    years_active: float
    latest_close: float
    avg_daily_volume: float
    median_daily_volume: float
    avg_daily_turnover_inr: float
    median_daily_turnover_inr: float
    annualized_volatility: float
    annualized_return: float
    skewness: float
    kurtosis: float
    max_drawdown: float
    zero_volume_days: int
    zero_volume_pct: float
    circuit_lock_days: int
    circuit_lock_pct: float
    corporate_actions_total: int
    dividends_count: int
    splits_count: int
    bonus_count: int
    rights_count: int
    liquidity_tier: str


def compute_moments(returns: list[float]) -> tuple[float, float, float, float]:
    """Compute mean, std, skewness, kurtosis for a return series."""
    n = len(returns)
    if n < 3:
        return 0.0, 0.0, 0.0, 3.0
    mean = sum(returns) / n
    var = sum((x - mean) ** 2 for x in returns) / (n - 1)
    std = math.sqrt(max(1e-12, var))

    # Skewness and kurtosis
    m3 = sum((x - mean) ** 3 for x in returns) / n
    m4 = sum((x - mean) ** 4 for x in returns) / n
    skew = m3 / (std ** 3) if std > 1e-8 else 0.0
    kurt = m4 / (std ** 4) if std > 1e-8 else 3.0
    return mean, std, skew, kurt


def compute_max_drawdown(closes: list[float]) -> float:
    """Compute maximum drawdown from a sequence of close prices."""
    if not closes:
        return 0.0
    peak = closes[0]
    max_dd = 0.0
    for price in closes:
        if price > peak:
            peak = price
        dd = (peak - price) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def assign_liquidity_tier(adtv_inr: float) -> str:
    """Classify instrument into actionable quantitative liquidity tiers."""
    if adtv_inr >= 1_000_000_000:  # >= 100 Cr
        return "Tier 1: Mega-Liquid (>100 Cr/day)"
    elif adtv_inr >= 100_000_000:  # 10 Cr to 100 Cr
        return "Tier 2: Liquid Institutional (10-100 Cr/day)"
    elif adtv_inr >= 10_000_000:   # 1 Cr to 10 Cr
        return "Tier 3: Mid-Market Tradable (1-10 Cr/day)"
    elif adtv_inr >= 1_000_000:    # 10 Lakh to 1 Cr
        return "Tier 4: SmallCap Active (10L-1 Cr/day)"
    else:
        return "Tier 5: Microcap / Illiquid (<10L/day)"


def parse_corporate_actions(ca_file: Path) -> dict[str, int]:
    """Parse corporate action counts from JSON."""
    counts = {"total": 0, "dividends": 0, "splits": 0, "bonus": 0, "rights": 0}
    if not ca_file.is_file():
        return counts
    try:
        data = json.loads(ca_file.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return counts
        counts["total"] = len(data)
        for item in data:
            subj = str(item.get("subject", "")).upper()
            if "DIVIDEND" in subj:
                counts["dividends"] += 1
            elif "SPLIT" in subj or "SUB-DIVISION" in subj or "SUB DIVISION" in subj:
                counts["splits"] += 1
            elif "BONUS" in subj:
                counts["bonus"] += 1
            elif "RIGHTS" in subj:
                counts["rights"] += 1
    except Exception:
        pass
    return counts


def run_comprehensive_market_analysis(
    cache_root: Path,
    authorities_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Execute end-to-end quantitative market structure analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    store_dir = cache_root / "store"
    ca_dir = cache_root / "corporate-actions"

    # 1. Load Authoritative Universe and Index Tags
    all_equities_csv = authorities_dir / "nse-all-listed-equities.csv"
    nifty50_csv = authorities_dir / "nse-nifty50-constituents.csv"
    nifty500_csv = authorities_dir / "nse-nifty500-constituents.csv"

    equity_meta: dict[str, dict[str, str]] = {}
    if all_equities_csv.is_file():
        with open(all_equities_csv, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                equity_meta[r["Symbol"]] = r

    nifty50_symbols = set()
    if nifty50_csv.is_file():
        with open(nifty50_csv, encoding="utf-8-sig") as f:
            nifty50_symbols = {r["Symbol"].strip() for r in csv.DictReader(f) if "Symbol" in r}

    nifty500_symbols = set()
    if nifty500_csv.is_file():
        with open(nifty500_csv, encoding="utf-8-sig") as f:
            nifty500_symbols = {r["Symbol"].strip() for r in csv.DictReader(f) if "Symbol" in r}

    # 2. Open EvidenceStore and iterate through verified datasets
    store = EvidenceStore(EvidenceStoreConfig(root=store_dir))
    datasets = store.list_verified(EvidenceResourceType.DATASET)
    print(f"Loaded {len(datasets):,} verified datasets from EvidenceStore: {store_dir}")

    profiles: list[StockQuantitativeProfile] = []
    processed_symbols = set()

    for verified in datasets:
        acq = historical_acquisition_from_verified(verified)
        manifest = acq.manifest
        sym = manifest.symbol

        # Avoid duplicates if multiple layers exist
        if sym in processed_symbols:
            continue
        processed_symbols.add(sym)

        records = acq.records
        if not records:
            continue

        meta = equity_meta.get(sym, {})
        comp_name = meta.get("Company Name", sym)
        isin = meta.get("ISIN Code", manifest.provider_instrument_id.replace("NSE_EQ|", ""))
        inst_type = meta.get("Instrument Type", "EQ")
        sec_type = meta.get("Security Type", "NORMAL")

        # Bars & Dates
        bars_count = len(records)
        first_dt = records[0].exchange_date
        last_dt = records[-1].exchange_date
        years_active = round((last_dt - first_dt).days / 365.25, 2)

        # Microstructure & Return Series Calculation
        closes: list[float] = []
        volumes: list[int] = []
        turnovers_inr: list[float] = []
        zero_vol_days = 0
        circuit_lock_days = 0

        for r in records:
            c = float(r.close)
            o = float(r.open)
            h = float(r.high)
            l = float(r.low)
            v = int(r.volume)

            closes.append(c)
            volumes.append(v)
            turnovers_inr.append(c * v)

            if v == 0:
                zero_vol_days += 1
            # Circuit lock heuristic: High == Low == Close and traded
            if h == l == c and v > 0 and len(closes) > 1:
                circuit_lock_days += 1

        # Daily returns
        daily_returns: list[float] = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            if prev > 0:
                daily_returns.append((curr - prev) / prev)
            else:
                daily_returns.append(0.0)

        # Moments & Risk Metrics
        mean_ret, std_ret, skew, kurt = compute_moments(daily_returns)
        ann_vol = std_ret * math.sqrt(252)
        ann_ret = mean_ret * 252
        max_dd = compute_max_drawdown(closes)

        # Liquidity Metrics
        avg_vol = sum(volumes) / len(volumes) if volumes else 0.0
        sorted_vols = sorted(volumes)
        med_vol = sorted_vols[len(sorted_vols) // 2] if sorted_vols else 0.0

        avg_adtv = sum(turnovers_inr) / len(turnovers_inr) if turnovers_inr else 0.0
        sorted_turnovers = sorted(turnovers_inr)
        med_adtv = sorted_turnovers[len(sorted_turnovers) // 2] if sorted_turnovers else 0.0

        tier = assign_liquidity_tier(avg_adtv)
        ca_stats = parse_corporate_actions(ca_dir / f"nse-corporate-actions-{sym}.json")

        profile = StockQuantitativeProfile(
            symbol=sym,
            company_name=comp_name,
            isin=isin,
            instrument_type=inst_type,
            security_type=sec_type,
            is_nifty50=sym in nifty50_symbols,
            is_nifty500=sym in nifty500_symbols,
            status=manifest.status.value,
            bars_count=bars_count,
            first_date=first_dt.isoformat(),
            last_date=last_dt.isoformat(),
            years_active=years_active,
            latest_close=round(closes[-1], 2) if closes else 0.0,
            avg_daily_volume=round(avg_vol, 1),
            median_daily_volume=round(med_vol, 1),
            avg_daily_turnover_inr=round(avg_adtv, 2),
            median_daily_turnover_inr=round(med_adtv, 2),
            annualized_volatility=round(ann_vol, 4),
            annualized_return=round(ann_ret, 4),
            skewness=round(skew, 3),
            kurtosis=round(kurt, 3),
            max_drawdown=round(max_dd, 4),
            zero_volume_days=zero_vol_days,
            zero_volume_pct=round(zero_vol_days / max(1, bars_count) * 100, 2),
            circuit_lock_days=circuit_lock_days,
            circuit_lock_pct=round(circuit_lock_days / max(1, bars_count) * 100, 2),
            corporate_actions_total=ca_stats["total"],
            dividends_count=ca_stats["dividends"],
            splits_count=ca_stats["splits"],
            bonus_count=ca_stats["bonus"],
            rights_count=ca_stats["rights"],
            liquidity_tier=tier,
        )
        profiles.append(profile)

    # Sort profiles by ADTV descending
    profiles.sort(key=lambda p: p.avg_daily_turnover_inr, reverse=True)

    # 3. Aggregate Macro & Cross-Sectional Statistics
    total_symbols = len(profiles)
    total_bars = sum(p.bars_count for p in profiles)
    total_market_adtv = sum(p.avg_daily_turnover_inr for p in profiles)
    total_ca_all = sum(p.corporate_actions_total for p in profiles)
    total_div_all = sum(p.dividends_count for p in profiles)
    total_splits_all = sum(p.splits_count for p in profiles)
    total_bonus_all = sum(p.bonus_count for p in profiles)

    # Liquidity distribution
    tier_counts = Counter(p.liquidity_tier for p in profiles)
    tier_adtvs = {}
    for p in profiles:
        tier_adtvs[p.liquidity_tier] = tier_adtvs.get(p.liquidity_tier, 0.0) + p.avg_daily_turnover_inr

    # Index concentration
    n50_adtv = sum(p.avg_daily_turnover_inr for p in profiles if p.is_nifty50)
    n500_adtv = sum(p.avg_daily_turnover_inr for p in profiles if p.is_nifty500)
    top100_adtv = sum(p.avg_daily_turnover_inr for p in profiles[:100])

    n50_pct = (n50_adtv / max(1.0, total_market_adtv)) * 100
    n500_pct = (n500_adtv / max(1.0, total_market_adtv)) * 100
    top100_pct = (top100_adtv / max(1.0, total_market_adtv)) * 100

    # Tenure cohorts
    ten_year_veterans = sum(1 for p in profiles if p.bars_count >= 2400)
    five_to_nine_years = sum(1 for p in profiles if 1200 <= p.bars_count < 2400)
    one_to_four_years = sum(1 for p in profiles if 250 <= p.bars_count < 1200)
    fresh_listings = sum(1 for p in profiles if p.bars_count < 250)

    # Volatility distribution
    vols = [p.annualized_volatility for p in profiles if p.annualized_volatility > 0]
    med_vol = sorted(vols)[len(vols) // 2] if vols else 0.0
    mean_vol = sum(vols) / len(vols) if vols else 0.0

    # 4. Save outputs
    # A. Full JSON profile dataset
    profiles_dict = [asdict(p) for p in profiles]
    json_path = output_dir / "nse_all_market_profiles.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(profiles_dict, f, indent=2)

    # B. CSV Export for analytics / spreadsheets
    csv_path = output_dir / "nse_all_market_profiles.csv"
    if profiles:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(profiles[0]).keys()))
            writer.writeheader()
            writer.writerows(profiles_dict)

    summary_meta = {
        "analysis_timestamp": datetime.now().isoformat(),
        "total_symbols_analyzed": total_symbols,
        "total_historical_bars": total_bars,
        "total_daily_market_turnover_inr": total_market_adtv,
        "total_corporate_actions_recorded": total_ca_all,
        "total_dividends": total_div_all,
        "total_splits": total_splits_all,
        "total_bonuses": total_bonus_all,
        "tenure_cohorts": {
            "10_year_veterans_gt_2400_bars": ten_year_veterans,
            "5_to_9_years_1200_to_2400_bars": five_to_nine_years,
            "1_to_4_years_250_to_1200_bars": one_to_four_years,
            "recent_listings_lt_250_bars": fresh_listings,
        },
        "liquidity_concentration": {
            "nifty50_turnover_pct": round(n50_pct, 2),
            "top100_turnover_pct": round(top100_pct, 2),
            "nifty500_turnover_pct": round(n500_pct, 2),
        },
        "liquidity_tiers": {k: {"count": tier_counts[k], "total_adtv_inr": round(tier_adtvs.get(k, 0.0), 2)} for k in sorted(tier_counts.keys())},
        "volatility_profile": {
            "median_annualized_volatility": round(med_vol, 4),
            "mean_annualized_volatility": round(mean_vol, 4),
        },
    }

    summary_json_path = output_dir / "market_structure_summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_meta, f, indent=2)

    print(f"\nAnalysis complete:")
    print(f"- Total Analyzed Symbols : {total_symbols:,}")
    print(f"- Total Historical Bars  : {total_bars:,}")
    print(f"- Profiles exported to   : {json_path} and {csv_path}")
    print(f"- High-level summary to  : {summary_json_path}")

    return summary_meta


if __name__ == "__main__":
    cache_p = ROOT_DIR / "data" / "evidence" / "market-cache" / "all-market-20160822-20260821"
    auth_p = ROOT_DIR / "data" / "authorities"
    out_p = ROOT_DIR / "data" / "evidence" / "market-analysis"
    run_comprehensive_market_analysis(cache_p, auth_p, out_p)
