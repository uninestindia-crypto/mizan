"""Comprehensive Quantitative Data Science & Predictive Information Coefficient (IC) Analysis Engine."""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent


def calc_mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def calc_std(vals: list[float], mean_val: float | None = None) -> float:
    n = len(vals)
    if n < 2:
        return 0.0
    m = mean_val if mean_val is not None else calc_mean(vals)
    var = sum((x - m) ** 2 for x in vals) / (n - 1)
    return math.sqrt(max(0.0, var))


def calc_skew_kurt(vals: list[float]) -> tuple[float, float]:
    n = len(vals)
    if n < 3:
        return 0.0, 0.0
    m = calc_mean(vals)
    s = calc_std(vals, m)
    if s < 1e-9:
        return 0.0, 0.0
    m3 = sum((x - m) ** 3 for x in vals) / n
    m4 = sum((x - m) ** 4 for x in vals) / n
    skew = m3 / (s ** 3)
    kurt = (m4 / (s ** 4)) - 3.0
    return round(skew, 4), round(kurt, 4)


def calc_spearman_rank_ic(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 5:
        return 0.0

    def get_ranks(arr: list[float]) -> list[float]:
        sorted_pairs = sorted(enumerate(arr), key=lambda p: p[1])
        ranks = [0.0] * n
        for rank_idx, (orig_idx, _) in enumerate(sorted_pairs):
            ranks[orig_idx] = rank_idx + 1
        return ranks

    rx = get_ranks(x)
    ry = get_ranks(y)

    mean_rx = (n + 1) / 2.0
    mean_ry = (n + 1) / 2.0

    cov = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    var_rx = sum((rx[i] - mean_rx) ** 2 for i in range(n))
    var_ry = sum((ry[i] - mean_ry) ** 2 for i in range(n))

    denom = math.sqrt(var_rx * var_ry)
    return cov / denom if denom > 1e-9 else 0.0


def analyze_feature_store(csv_path: Path, output_file: Path) -> dict[str, Any]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"Feature store CSV not found: {csv_path}")

    print(f"=== QUANTITATIVE FEATURE & PREDICTIVE SIGNAL ANALYSIS ===", flush=True)
    print(f"Reading: {csv_path}", flush=True)

    rows: list[dict[str, Any]] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    total_obs = len(rows)
    print(f"Loaded {total_obs:,} multi-factor observations.", flush=True)

    numeric_features = [
        "ret_1d", "ret_5d", "ret_21d", "gk_vol", "park_vol", "rsi_14",
        "ratio_sma20", "ratio_sma50", "vol_zscore", "mf_multiplier",
        "india_vix", "nifty_ret_5d", "cs_rank_mom5d", "cs_rank_vol_surprise"
    ]
    targets = ["fwd_ret_1d", "fwd_ret_5d", "fwd_ret_21d", "fwd_alpha_5d"]

    # 1. Descriptive Moments
    moments: dict[str, Any] = {}
    for feat in numeric_features:
        vals = [float(r[feat]) for r in rows if r.get(feat) not in ("", None)]
        if not vals:
            continue
        vals.sort()
        m = calc_mean(vals)
        s = calc_std(vals, m)
        skew, kurt = calc_skew_kurt(vals)
        moments[feat] = {
            "count": len(vals),
            "mean": round(m, 5),
            "std": round(s, 5),
            "min": round(vals[0], 5),
            "q25": round(vals[int(len(vals) * 0.25)], 5),
            "median": round(vals[int(len(vals) * 0.50)], 5),
            "q75": round(vals[int(len(vals) * 0.75)], 5),
            "max": round(vals[-1], 5),
            "skewness": skew,
            "kurtosis": kurt,
        }

    # 2. Daily Information Coefficient (IC) Timeseries & Information Ratio (IR)
    # Group rows by date
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_date[r["date"]].append(r)

    ic_results: dict[str, dict[str, Any]] = {}
    for target in targets:
        ic_results[target] = {}
        for feat in numeric_features:
            daily_ics: list[float] = []
            for dt, dt_rows in by_date.items():
                valid_pairs = [
                    (float(r[feat]), float(r[target]))
                    for r in dt_rows
                    if r.get(feat) not in ("", None) and r.get(target) not in ("", None)
                ]
                if len(valid_pairs) >= 10:
                    xs = [p[0] for p in valid_pairs]
                    ys = [p[1] for p in valid_pairs]
                    ic = calc_spearman_rank_ic(xs, ys)
                    daily_ics.append(ic)

            if daily_ics:
                mean_ic = calc_mean(daily_ics)
                std_ic = calc_std(daily_ics, mean_ic)
                ir = (mean_ic / std_ic * math.sqrt(252)) if std_ic > 1e-6 else 0.0
                pct_positive = (sum(1 for x in daily_ics if x > 0) / len(daily_ics)) * 100.0
                ic_results[target][feat] = {
                    "mean_rank_ic": round(mean_ic, 4),
                    "ic_std": round(std_ic, 4),
                    "information_ratio_annualized": round(ir, 2),
                    "pct_positive_ic_days": round(pct_positive, 1),
                    "days_evaluated": len(daily_ics),
                }

    # 3. Macro Regime Analysis
    regimes: dict[str, Any] = {}
    for r_label in ["LOW_VOL", "NORMAL_VOL", "HIGH_VOL"]:
        reg_rows = [r for r in rows if r.get("vix_regime") == r_label and r.get("fwd_ret_5d") not in ("", None)]
        if reg_rows:
            fwd_rets = [float(r["fwd_ret_5d"]) for r in reg_rows]
            gk_vols = [float(r["gk_vol"]) for r in reg_rows]
            regimes[r_label] = {
                "observations": len(reg_rows),
                "mean_forward_5d_return": round(calc_mean(fwd_rets) * 100, 3),
                "mean_gk_volatility": round(calc_mean(gk_vols) * 100, 3),
                "median_forward_5d_return": round(sorted(fwd_rets)[len(fwd_rets)//2] * 100, 3),
            }

    summary = {
        "analysis_timestamp": datetime.now(UTC).isoformat(),
        "total_observations": total_obs,
        "unique_sessions": len(by_date),
        "feature_moments": moments,
        "information_coefficients": ic_results,
        "market_regimes": regimes,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Data Science Summary exported to: {output_file}\n", flush=True)
    return summary


if __name__ == "__main__":
    feat_csv = ROOT_DIR / "data" / "evidence" / "feature-store" / "multidim_feature_store.csv"
    out_json = ROOT_DIR / "data" / "evidence" / "feature-store" / "feature_analysis_summary.json"
    analyze_feature_store(feat_csv, out_json)
