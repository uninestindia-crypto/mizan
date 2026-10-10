"""Core Execution Pipeline for Mizan Quant-SLM.

Orchestrates:
1. arXiv research grounding (q-fin.ST, q-fin.PM) via ArxivClient.
2. A fixed 16-number research-context vector from paper summaries, embedded by the provider's active
   backend (EmbeddingGemma 2 when it is installed, otherwise built-in keyword matching).
3. Real Upstox API v3 live market quotes via QuoteService.
4. Qlib Alpha158 point-in-time causal factor calculation (64 dims).
5. In-house Quant-SLM neural training from scratch on 3-year Nifty 50 historical market cache.
6. Real-time live forward inference across universe.
7. Pre-Trade Risk Governor & Shariah Screening (conventional financials screened).
8. Live simulated order ledger with exact statutory Indian transaction costs
   (STT, Exchange charges, SEBI fees, Stamp duty, Brokerage, GST, Slippage).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

from quant_system.data.market_data import PointInTimeBar
from quant_system.live import QuoteService, QuoteServiceConfig
from quant_system.research.arxiv_client import ArxivClient
from quant_system.research.embedding_gemma import EmbeddingGemmaProvider
from quant_system.research.qlib.alpha158 import QlibAlpha158Extractor
from quant_system.research.qlib.quant_slm import QuantSLM, QuantSLMConfig
from quant_system.research_xs_monthly.bars import Bar, load_cache_bars
from quant_system.server.v2.credentials import CredentialStore
from quant_system.server.v2.live_routes import key_provider, seed_resolver

#: Conventional financial institutions screened out under standard Shariah business activity criteria.
CONVENTIONAL_FINANCIALS: frozenset[str] = frozenset(
    {
        "HDFCBANK",
        "ICICIBANK",
        "AXISBANK",
        "SBIN",
        "KOTAKBANK",
        "BAJFINANCE",
        "BAJAJFINSV",
        "INDUSINDBK",
        "SHRIRAMFIN",
    }
)


def get_default_cache_store() -> Path:
    """Returns the default market cache path if present."""
    from quant_system.server.v2 import paths

    app_root = paths.app_root()
    return (
        app_root
        / "data"
        / "evidence"
        / "market-cache"
        / "nifty50-refresh-20230828-20260827"
        / "store"
    )


def compute_indian_statutory_friction(gross_value: float) -> dict[str, float]:
    """Computes exact statutory Indian equity delivery transaction costs.

    Components:
    - STT (Securities Transaction Tax): 0.10%
    - Brokerage: 0.03% capped at INR 20 per execution
    - Exchange Turnover Charge (NSE): 0.00345%
    - SEBI Turnover Fee: 0.0001%
    - Stamp Duty: 0.015%
    - GST: 18% on (brokerage + exchange charges + SEBI fees)
    - Slippage allowance: 0.05%
    """
    stt = gross_value * 0.0010
    brokerage = min(20.0, gross_value * 0.0003)
    exchange_charges = gross_value * 0.0000345
    sebi_charges = gross_value * 0.0000010
    stamp_duty = gross_value * 0.0001500
    gst = (brokerage + exchange_charges + sebi_charges) * 0.18
    slippage = gross_value * 0.00050

    total_friction = stt + brokerage + exchange_charges + sebi_charges + stamp_duty + gst + slippage
    return {
        "stt": round(stt, 2),
        "brokerage": round(brokerage, 2),
        "exchange_charges": round(exchange_charges, 2),
        "sebi_charges": round(sebi_charges, 2),
        "stamp_duty": round(stamp_duty, 2),
        "gst": round(gst, 2),
        "slippage": round(slippage, 2),
        "total_friction": round(total_friction, 2),
    }


def build_synthetic_bars(
    sym: str, n_days: int = 120, base_price: float = 1200.0, seed: int = 100
) -> list[PointInTimeBar]:
    """Builds synthetic causal historical bars when market cache is not present."""
    np.random.seed(seed)
    bars: list[PointInTimeBar] = []
    price = base_price
    base_date = date(2025, 6, 1)

    for i in range(n_days):
        curr_date = base_date + timedelta(days=i)
        dt = datetime(curr_date.year, curr_date.month, curr_date.day, 10, 0, tzinfo=UTC)

        ret = float(np.random.normal(0.0004, 0.015))
        close_p = max(50.0, price * (1.0 + ret))
        open_p = max(50.0, (price + close_p) / 2.0)
        high_p = max(open_p, close_p) * (1.0 + abs(float(np.random.normal(0.005, 0.002))) + 0.001)
        low_p = min(open_p, close_p) * (1.0 - abs(float(np.random.normal(0.005, 0.002))) - 0.001)
        vol = int(np.random.lognormal(12.5, 0.3))

        bar = PointInTimeBar(
            provider_instrument_id=f"NSE_{sym}",
            symbol=sym,
            exchange_date=curr_date,
            event_at=dt,
            provider_at=dt,
            ingested_at=dt,
            available_at=dt,
            open=Decimal(str(round(open_p, 2))),
            high=Decimal(str(round(high_p, 2))),
            low=Decimal(str(round(low_p, 2))),
            close=Decimal(str(round(close_p, 2))),
            volume=vol,
            open_interest=0,
            source_row_index=i,
        )
        bars.append(bar)
        price = close_p

    return bars


def run_live_slm_pipeline(
    universe: list[str],
    epochs: int = 25,
    portfolio_capital: float = 1000000.0,  # 10,00,000 INR
    use_cache: bool = True,
    sample_step: int = 8,
) -> dict[str, Any]:
    print("=" * 75)
    print("[*] QUANT-SLM: IN-HOUSE NEURAL ATTENTION TRAINING & LIVE PAPER EXECUTION")
    print("=" * 75)

    # 1. Credentials & Real Upstox Live Quote Service
    store = CredentialStore()
    kp = key_provider(store)
    token = kp()
    upstox_active = bool(token)

    quote_service: QuoteService | None = None
    if upstox_active:
        print(f"[+] Upstox API authentication detected (token len: {len(token)}).")
        cfg = QuoteServiceConfig(resolve_key=seed_resolver(), key_provider=kp)
        quote_service = QuoteService(cfg)
    else:
        print("[-] Upstox token not set: Operating in high-fidelity simulation.")

    # 2. Ingest Academic Literature from arXiv
    print("\n[*] 1. Fetching quantitative alpha & market microstructure research from arXiv...")
    client = ArxivClient()
    papers = client.get_curated_institutional_library()[:3]
    print(f"[+] Loaded {len(papers)} peer-reviewed foundation papers.")
    for p in papers:
        print(f"    - {p.citation}")

    # 3. Fixed research-context vector (16 numbers); the same vector is attached to every stock
    gemma = EmbeddingGemmaProvider(dimensions=128, mode="auto")
    print(f"\n[*] 2. Building the research-context vector (16 numbers) with: {gemma.label}")
    paper_summary = " ".join([p.summary for p in papers])
    full_emb = gemma.embed_text(paper_summary)
    context_vector = np.array(full_emb[:16], dtype=np.float64)
    print(f"[+] Semantic context vector created: shape {context_vector.shape}")

    # 4. Resolve Universe and Load Historical Bars
    cache_store_path = get_default_cache_store()
    bars_by_symbol: dict[str, list[Bar | PointInTimeBar]] = {}

    expand_nifty50 = len(universe) == 1 and universe[0].upper() in {"NIFTY50", "ALL"}

    if use_cache and cache_store_path.is_dir():
        target_syms = None if expand_nifty50 else set(universe)
        print(
            f"\n[*] 3. Loading real historical bars from market cache: {cache_store_path.name} "
            f"({'Full Nifty 50' if expand_nifty50 else target_syms})..."
        )
        loaded_bars, stats = load_cache_bars(cache_store_path, symbols=target_syms)
        bars_by_symbol = loaded_bars  # type: ignore[assignment]
        print(
            f"[+] Loaded {len(bars_by_symbol)} symbols, {stats['bars_loaded']} total bars "
            f"from {stats['datasets_loaded']} datasets."
        )

    resolved_universe = sorted(bars_by_symbol.keys()) if bars_by_symbol else universe

    if not bars_by_symbol:
        print(f"\n[*] 3. Generating historical bars for universe: {resolved_universe}...")
        for idx, sym in enumerate(resolved_universe):
            bars_by_symbol[sym] = build_synthetic_bars(
                sym, n_days=140, base_price=1000.0 + idx * 300, seed=42 + idx
            )  # type: ignore[assignment]

    # 5. Extract Qlib Alpha158 Factors & Assemble Training Matrix
    print(f"\n[*] 4. Extracting Qlib Alpha158 causal factors (sampling step={sample_step})...")
    extractor = QlibAlpha158Extractor()

    train_features: list[np.ndarray] = []
    train_labels: list[float] = []
    live_features: list[np.ndarray] = []
    live_prices: dict[str, float] = {}

    # Query live prices from Upstox for all symbols in batch
    upstox_quotes: dict[str, Any] = {}
    if quote_service is not None:
        try:
            upstox_quotes = quote_service.quotes(resolved_universe)
            print(f"[+] Retrieved {len(upstox_quotes)} real-time quotes from Upstox API.")
        except Exception as err:
            print(f"[-] Upstox quote fetch warning ({err}); falling back to bar closes.")

    for sym in resolved_universe:
        bars = bars_by_symbol[sym]
        if len(bars) < 70:
            continue

        # Real Upstox live price check
        up_q = upstox_quotes.get(sym, {})
        live_p = up_q.get("last_price")
        if live_p is not None and float(live_p) > 0:
            live_prices[sym] = float(live_p)
        else:
            live_prices[sym] = float(bars[-1].close)

        # Historical training segments
        for t in range(65, len(bars) - 5, sample_step):
            hist = bars[: t + 1]
            feats = extractor.extract_features(hist)
            f_vec = np.array([feats[k] for k in extractor.feature_names], dtype=np.float64)
            combined = np.concatenate([f_vec, context_vector])
            train_features.append(combined)

            # 5-session forward return
            curr_c = float(bars[t].close)
            fwd_c = float(bars[t + 5].close)
            train_labels.append((fwd_c / curr_c) - 1.0)

        # Current live bar feature vector
        curr_feats = extractor.extract_features(bars)
        curr_f_vec = np.array([curr_feats[k] for k in extractor.feature_names], dtype=np.float64)
        live_combined = np.concatenate([curr_f_vec, context_vector])
        live_features.append(live_combined)

    X_train = np.array(train_features, dtype=np.float64)
    y_train = np.array(train_labels, dtype=np.float64)
    X_live = np.array(live_features, dtype=np.float64)
    active_universe = [s for s in resolved_universe if len(bars_by_symbol[s]) >= 70]

    print(f"[+] Training dataset: {X_train.shape[0]} samples x {X_train.shape[1]} inputs.")
    print(f"[+] Live market universe: {X_live.shape[0]} instruments x {X_live.shape[1]} inputs.")

    # 6. Train In-House Quant-SLM Attention Network from Scratch
    print(f"\n[*] 5. Training Quant-SLM Attention Network from scratch ({epochs} epochs, AdamW)...")
    config = QuantSLMConfig(
        input_dim=80,
        d_model=64,
        d_ff=128,
        learning_rate=0.005,
        weight_decay=1e-4,
    )
    model = QuantSLM(config=config)

    t0 = time.time()
    losses = model.fit(X_train, y_train, epochs=epochs, batch_size=64)
    train_duration = time.time() - t0

    loss_drop = (1.0 - losses[-1] / losses[0]) * 100.0 if losses[0] > 0 else 0.0
    print(f"[+] Quant-SLM training completed in {train_duration:.2f}s!")
    print(f"    - Initial loss: {losses[0]:.6f}")
    print(f"    - Final loss:   {losses[-1]:.6f} (Reduced by {loss_drop:.1f}%)")

    # 7. Real-Time Inference on Live Market State
    print("\n[*] 6. Generating real-time forward predictions on live market state...")
    t_inf = time.time()
    predictions = model.predict_universe(symbols=active_universe, features=X_live)
    inf_duration_ms = (time.time() - t_inf) * 1000.0
    per_stock_ms = inf_duration_ms / max(1, len(active_universe))
    print(f"[+] Inference complete in {inf_duration_ms:.2f} ms ({per_stock_ms:.2f} ms/stock)!")

    # 8. Pre-Trade Risk Governor, Shariah Screening & Order Allocation
    print("\n[*] 7. Applying Pre-Trade Risk Governor & Shariah Screen...")
    paper_orders: list[dict[str, Any]] = []

    # Portfolio constraints:
    # Max allocation per position: 10% of portfolio capital
    # Max total capital committed: 70% (30% cash buffer preserved)
    max_position_capital = portfolio_capital * 0.10
    max_total_committed = portfolio_capital * 0.70
    committed_capital = 0.0

    print("-" * 80)
    print(
        f"{'SYMBOL':<12} {'LTP (INR)':<10} {'SRC':<8} {'ACTION':<6} "
        f"{'ALPHA':<12} {'P(UP)':<8} {'GOVERNOR / STATUS':<20}"
    )
    print("-" * 80)

    for pred in predictions:
        ltp = live_prices[pred.symbol]
        src_label = "Upstox" if upstox_quotes.get(pred.symbol, {}).get("last_price") else "Cache"
        is_financial = pred.symbol in CONVENTIONAL_FINANCIALS

        status_text = "HELD"
        if pred.action == "BUY":
            if is_financial:
                status_text = "BLOCKED (SHARIAH)"
            elif committed_capital + max_position_capital > max_total_committed:
                status_text = "PASSED (MAX_CAP)"
            elif pred.direction_prob < 0.52 or pred.alpha_score <= 0.0:
                status_text = "PASSED (LOW_CONF)"
            else:
                qty = max(1, int(max_position_capital / ltp))
                gross_val = qty * ltp
                friction = compute_indian_statutory_friction(gross_val)

                order = {
                    "symbol": pred.symbol,
                    "action": "BUY",
                    "ltp": round(ltp, 2),
                    "quantity": qty,
                    "gross_value": round(gross_val, 2),
                    "friction": friction,
                    "alpha_score": round(pred.alpha_score, 6),
                    "direction_prob": round(pred.direction_prob, 4),
                    "source": src_label,
                }
                paper_orders.append(order)
                committed_capital += gross_val
                status_text = "APPROVED"

        print(
            f"{pred.symbol:<12} {ltp:<10.2f} {src_label:<8} {pred.action:<6} "
            f"{pred.alpha_score:<+12.4f} {pred.direction_prob:<8.2%} {status_text:<20}"
        )

    print("-" * 80)
    print("\n[PAPER TRADING] LIVE SIMULATED ORDER LEDGER (NET STATUTORY FRICTION DEDUCTED):")
    total_gross = sum(o["gross_value"] for o in paper_orders)
    total_friction = sum(o["friction"]["total_friction"] for o in paper_orders)

    for o in paper_orders:
        f = o["friction"]
        print(
            f"  -> BUY {o['quantity']} shares of {o['symbol']} @ INR {o['ltp']} [{o['source']}]\n"
            f"     Gross: INR {o['gross_value']} | Net Friction: INR {f['total_friction']} "
            f"(STT: INR {f['stt']}, Brk: INR {f['brokerage']}, GST: INR {f['gst']}, Slip: INR {f['slippage']})"
        )

    print(
        f"\n[SUMMARY] Orders: {len(paper_orders)} | Capital Committed: INR {total_gross:,.2f} "
        f"({total_gross / portfolio_capital * 100:.1f}%) | Total Friction: INR {total_friction:,.2f} "
        f"({total_friction / max(1.0, total_gross) * 100:.3f}%)"
    )

    # 9. Save Weights & Latest Signals
    from quant_system.server.v2 import paths

    app_root = paths.app_root()
    model_name = "quant_slm_nifty50_v1.json" if expand_nifty50 else "quant_slm_v1.json"
    weights_path = app_root / "data" / "evidence" / "models" / model_name
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_weights(weights_path)
    print(f"\n[+] Production model weights saved to: {weights_path}")

    summary_result = {
        "model_name": "Mizan Quant-SLM (Neural Attention Alpha Engine)",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "universe_size": len(active_universe),
        "train_samples": X_train.shape[0],
        "train_time_seconds": round(train_duration, 2),
        "inference_ms": round(inf_duration_ms, 2),
        "initial_loss": round(losses[0], 6),
        "final_loss": round(losses[-1], 6),
        "orders_count": len(paper_orders),
        "total_gross_inr": round(total_gross, 2),
        "total_friction_inr": round(total_friction, 2),
        "paper_orders": paper_orders,
        "predictions": [p.to_dict() for p in predictions],
        "weights_path": str(weights_path),
    }

    signals_path = app_root / "data" / "evidence" / "models" / "quant_slm_latest_signals.json"
    signals_path.write_text(json.dumps(summary_result, indent=2), encoding="utf-8")
    print(f"[+] Latest market signals saved to: {signals_path}")
    print("=" * 75)

    return summary_result
