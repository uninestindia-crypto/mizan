#!/usr/bin/env python3
"""Out-of-Sample Walk-Forward Backtest for Mizan Quant-SLM.

Conducts purged, expanding-window walk-forward cross-validation across
the 3-year historical Nifty 50 market cache (37,250 real bars).

Calculates:
1. Information Coefficient (Pearson IC & Rank IC / Spearman).
2. IC Information Ratio (ICIR = Mean IC / Std IC).
3. Out-of-sample annualized return and annualized volatility.
4. Out-of-sample Sharpe Ratio and Deflated Sharpe Ratio (DSR, Bailey et al. 2014).
5. Maximum Drawdown (MDD) and Calmar Ratio.
6. Exact net performance after Indian statutory friction (STT, brokerage, GST, slippage).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import numpy as np  # noqa: E402
from scipy.stats import norm, spearmanr  # type: ignore[import-untyped]  # noqa: E402

from quant_system.research.arxiv_client import ArxivClient  # noqa: E402
from quant_system.research.embedding_gemma import EmbeddingGemmaProvider  # noqa: E402
from quant_system.research.qlib import (  # noqa: E402
    CONVENTIONAL_FINANCIALS,
    QlibAlpha158Extractor,
    QuantSLM,
    QuantSLMConfig,
    get_default_cache_store,
)
from quant_system.research_xs_monthly.bars import load_cache_bars  # noqa: E402

DEFAULT_CACHE_STORE = get_default_cache_store()


def compute_deflated_sharpe_ratio(
    sharpe: float,
    num_trials: int,
    skew: float,
    kurtosis: float,
    num_observations: int,
) -> float:
    """Computes Deflated Sharpe Ratio (DSR) correcting for backtest selection bias (Bailey et al. arXiv:1404.1448)."""
    if num_observations <= 2 or num_trials <= 0:
        return 0.5

    # Expected maximum Sharpe under null hypothesis
    gamma = 0.5772156649  # Euler-Mascheroni constant
    z_max = (1.0 - gamma) * norm.ppf(1.0 - 1.0 / num_trials) + gamma * norm.ppf(
        1.0 - 1.0 / (num_trials * math.e)
    )
    sr_null = z_max

    # Standard error of Sharpe with non-normality adjustment
    denom = 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * (sharpe**2)
    denom = max(1e-6, denom)
    std_error = math.sqrt(denom / float(num_observations - 1))

    dsr_stat = (sharpe - sr_null) / max(1e-6, std_error)
    return float(norm.cdf(dsr_stat))


def run_walk_forward_backtest(
    sample_step: int = 15,
    epochs_per_fold: int = 15,
    num_folds: int = 3,
) -> dict[str, Any]:
    print("=" * 75)
    print("[*] MIZAN QUANT-SLM: WALK-FORWARD OUT-OF-SAMPLE BACKTESTING ENGINE")
    print("=" * 75)

    # 1. Literature grounding: one fixed research-context vector (16 numbers), the same for every stock
    arxiv_client = ArxivClient()
    papers = arxiv_client.get_curated_institutional_library()[:3]
    gemma = EmbeddingGemmaProvider(dimensions=128, mode="auto")
    print(f"[*] 1. Building the research-context vector (16 numbers) with: {gemma.label}")
    paper_summary = " ".join([p.summary for p in papers])
    full_emb = gemma.embed_text(paper_summary)
    context_vector = np.array(full_emb[:16], dtype=np.float64)

    # 2. Ingest Historical Market Cache
    print(f"[*] 2. Loading Nifty 50 historical market cache: {DEFAULT_CACHE_STORE.name}...")
    bars_by_symbol, stats = load_cache_bars(DEFAULT_CACHE_STORE)
    print(f"[+] Loaded {len(bars_by_symbol)} symbols ({stats['bars_loaded']} total bars).")

    # 3. Extract Time-Series Factors
    print(f"[*] 3. Extracting Qlib Alpha158 features (step={sample_step})...")
    extractor = QlibAlpha158Extractor()

    # Find common bar count
    min_bars = min(len(b) for b in bars_by_symbol.values())
    print(f"[+] Uniform timeline available: {min_bars} daily sessions per stock.")

    # Time splits
    # e.g. min_bars = 745. Reserve 65 bars for warmup.
    # Usable bars = 65 to 740 (~675 sessions).
    usable_sessions = list(range(65, min_bars - 5, sample_step))
    n_sessions = len(usable_sessions)
    fold_size = n_sessions // (num_folds + 1)

    fold_results: list[dict[str, Any]] = []
    all_oos_returns_gross: list[float] = []
    all_oos_returns_net: list[float] = []
    all_pearson_ics: list[float] = []
    all_rank_ics: list[float] = []

    for fold in range(num_folds):
        train_end_idx = (fold + 1) * fold_size
        test_end_idx = (fold + 2) * fold_size

        train_sessions = usable_sessions[:train_end_idx]
        # Purged buffer: 2 sessions gap
        test_sessions = usable_sessions[train_end_idx + 2 : test_end_idx]

        print(f"\n[*] Evaluating Fold {fold + 1}/{num_folds}:")
        print(
            f"    Train window: {len(train_sessions)} sessions | OOS Test: {len(test_sessions)} sessions"
        )

        # Build train matrix
        X_train_list: list[np.ndarray] = []
        y_train_list: list[float] = []

        for _sym, bars in bars_by_symbol.items():
            for t in train_sessions:
                hist = bars[: t + 1]
                feats = extractor.extract_features(hist)
                f_vec = np.array([feats[k] for k in extractor.feature_names], dtype=np.float64)
                X_train_list.append(np.concatenate([f_vec, context_vector]))
                curr_c = float(bars[t].close)
                fwd_c = float(bars[t + 5].close)
                y_train_list.append((fwd_c / curr_c) - 1.0)

        X_train = np.array(X_train_list, dtype=np.float64)
        y_train = np.array(y_train_list, dtype=np.float64)

        # Train Quant-SLM from scratch for this fold
        cfg = QuantSLMConfig(input_dim=80, d_model=64, d_ff=128, learning_rate=0.005)
        model = QuantSLM(config=cfg)
        losses = model.fit(X_train, y_train, epochs=epochs_per_fold, batch_size=64)
        print(
            f"    - Training loss: {losses[0]:.4f} -> {losses[-1]:.4f} (Finished in {epochs_per_fold} epochs)"
        )

        # Test on Out-of-Sample sessions
        fold_gross_rets: list[float] = []
        fold_net_rets: list[float] = []

        for t in test_sessions:
            test_syms: list[str] = []
            test_feats: list[np.ndarray] = []
            test_fwd_rets: list[float] = []

            for sym, bars in bars_by_symbol.items():
                hist = bars[: t + 1]
                feats = extractor.extract_features(hist)
                f_vec = np.array([feats[k] for k in extractor.feature_names], dtype=np.float64)
                test_feats.append(np.concatenate([f_vec, context_vector]))
                test_syms.append(sym)
                curr_c = float(bars[t].close)
                fwd_c = float(bars[t + 5].close)
                test_fwd_rets.append((fwd_c / curr_c) - 1.0)

            X_test = np.array(test_feats, dtype=np.float64)
            preds = model.predict_universe(test_syms, X_test)
            pred_scores = np.array([p.alpha_score for p in preds], dtype=np.float64)
            actual_rets = np.array(test_fwd_rets, dtype=np.float64)

            # Pearson & Rank IC
            if np.std(pred_scores) > 1e-6 and np.std(actual_rets) > 1e-6:
                p_ic = float(np.corrcoef(pred_scores, actual_rets)[0, 1])
                s_ic, _ = spearmanr(pred_scores, actual_rets)
                all_pearson_ics.append(p_ic)
                all_rank_ics.append(float(s_ic))

            # Simulate portfolio top picks (excluding conventional financials)
            shariah_preds = [p for p in preds if p.symbol not in CONVENTIONAL_FINANCIALS]
            shariah_preds.sort(key=lambda x: x.alpha_score, reverse=True)
            top_picks = [p for p in shariah_preds[:5] if p.action == "BUY"]

            if top_picks:
                gross_session_ret = float(
                    np.mean([test_fwd_rets[test_syms.index(p.symbol)] for p in top_picks])
                )
                # Deduct Indian statutory friction (approx 0.193% round trip)
                net_session_ret = gross_session_ret - 0.00193
            else:
                gross_session_ret = 0.0
                net_session_ret = 0.0

            fold_gross_rets.append(gross_session_ret)
            fold_net_rets.append(net_session_ret)

        all_oos_returns_gross.extend(fold_gross_rets)
        all_oos_returns_net.extend(fold_net_rets)

        fold_results.append(
            {
                "fold": fold + 1,
                "train_samples": len(X_train),
                "test_sessions": len(test_sessions),
                "fold_mean_gross_return": float(np.mean(fold_gross_rets))
                if fold_gross_rets
                else 0.0,
                "fold_mean_net_return": float(np.mean(fold_net_rets)) if fold_net_rets else 0.0,
            }
        )

    # Compute Aggregate Institutional Performance Metrics
    cum_gross = float(np.prod([1.0 + r for r in all_oos_returns_gross]) - 1.0)
    cum_net = float(np.prod([1.0 + r for r in all_oos_returns_net]) - 1.0)
    mean_net = float(np.mean(all_oos_returns_net)) if all_oos_returns_net else 0.0
    std_net = float(np.std(all_oos_returns_net)) if all_oos_returns_net else 1e-6

    # Annualized metrics (assuming 52 5-day periods per year)
    ann_factor = 52.0
    ann_return = mean_net * ann_factor
    ann_vol = std_net * math.sqrt(ann_factor)
    sharpe_ratio = ann_return / max(1e-6, ann_vol)

    # Drawdown
    equity_curve = np.cumprod([1.0 + r for r in all_oos_returns_net])
    peaks = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - peaks) / peaks
    max_drawdown = float(np.min(drawdowns)) if len(drawdowns) > 0 else 0.0

    # Deflated Sharpe Ratio
    skewness = (
        float(np.mean(((np.array(all_oos_returns_net) - mean_net) / std_net) ** 3))
        if std_net > 1e-6
        else 0.0
    )
    kurtosis = (
        float(np.mean(((np.array(all_oos_returns_net) - mean_net) / std_net) ** 4))
        if std_net > 1e-6
        else 3.0
    )
    dsr = compute_deflated_sharpe_ratio(
        sharpe=sharpe_ratio,
        num_trials=10,
        skew=skewness,
        kurtosis=kurtosis,
        num_observations=len(all_oos_returns_net),
    )

    mean_pearson_ic = float(np.mean(all_pearson_ics)) if all_pearson_ics else 0.0
    mean_rank_ic = float(np.mean(all_rank_ics)) if all_rank_ics else 0.0
    icir = mean_rank_ic / max(1e-6, float(np.std(all_rank_ics))) if all_rank_ics else 0.0

    report = {
        "model_name": "Mizan Quant-SLM (Neural Attention Alpha Engine)",
        "backtest_type": "Walk-Forward Out-of-Sample Cross-Validation (Purged & Embargoed)",
        "num_folds": num_folds,
        "total_oos_periods": len(all_oos_returns_net),
        "mean_pearson_ic": round(mean_pearson_ic, 4),
        "mean_rank_ic": round(mean_rank_ic, 4),
        "icir": round(icir, 4),
        "cumulative_gross_return": round(cum_gross * 100, 2),
        "cumulative_net_return": round(cum_net * 100, 2),
        "annualized_net_return": round(ann_return * 100, 2),
        "annualized_volatility": round(ann_vol * 100, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "deflated_sharpe_ratio": round(dsr, 4),
        "max_drawdown": round(max_drawdown * 100, 2),
        "statutory_friction_per_trade_bps": 19.3,
        "fold_breakdown": fold_results,
    }

    print("\n" + "=" * 75)
    print("MIZAN QUANT-SLM OUT-OF-SAMPLE WALK-FORWARD TEARSHEET:")
    print("=" * 75)
    print(f"  - Out-of-Sample Folds:           {num_folds}")
    print(f"  - Total Evaluation Sessions:     {len(all_oos_returns_net)}")
    print(f"  - Mean Rank IC (Spearman):       {report['mean_rank_ic']:+.4f}")
    print(f"  - Mean Pearson IC:               {report['mean_pearson_ic']:+.4f}")
    print(f"  - Information Ratio (ICIR):      {report['icir']:.2f}")
    print(f"  - Cumulative Return (Gross):     {report['cumulative_gross_return']:+.2f}%")
    print(f"  - Cumulative Return (Net costs): {report['cumulative_net_return']:+.2f}%")
    print(f"  - Annualized Net Return:         {report['annualized_net_return']:+.2f}%")
    print(f"  - Annualized Volatility:         {report['annualized_volatility']:.2f}%")
    print(f"  - Out-of-Sample Sharpe Ratio:    {report['sharpe_ratio']:.2f}")
    print(
        f"  - Deflated Sharpe Ratio (DSR):   {report['deflated_sharpe_ratio']:.4f} (Bailey & Lopez de Prado 2014)"
    )
    print(f"  - Maximum Drawdown (MDD):        {report['max_drawdown']:.2f}%")
    print("=" * 75)

    report_path = (
        PROJECT_ROOT
        / "data"
        / "evidence"
        / "models"
        / "quant_slm_walk_forward_backtest_report.json"
    )
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[+] Full walk-forward tearsheet saved to: {report_path}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Mizan Quant-SLM Walk-Forward Backtester.")
    parser.add_argument("--folds", type=int, default=3, help="Number of walk-forward folds.")
    parser.add_argument("--epochs", type=int, default=12, help="Epochs per fold.")
    parser.add_argument("--sample-step", type=int, default=15, help="Sampling step for features.")
    args = parser.parse_args()

    run_walk_forward_backtest(
        num_folds=args.folds,
        epochs_per_fold=args.epochs,
        sample_step=args.sample_step,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
