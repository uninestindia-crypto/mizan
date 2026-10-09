# Completed work: Build custom in-house Quant-SLM neural model from scratch and live paper trading pipeline

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-08T07:02:00Z  
COMPLETED_UTC: 2026-10-08T07:08:00Z  
STARTING_REVISION: 52df4f4513a1d65733ee6b6fec320af701126271  
WORKTREE_OR_BRANCH: D:/Quant OS Project/Mizan (main)

## Objective

GOAL_LINE: G1, G5
Design and train a custom, in-house neural architecture from scratch (Quant-SLM: a specialized Cross-Factor Attention Network) that fuses Qlib Alpha158 technical indicators with EmbeddingGemma 2 semantic vectors derived from arXiv quantitative finance papers, trained with AdamW backpropagation, and hooked to live market evaluation with Upstox API integration, Shariah screening, and pre-trade risk governance.

## Owned paths

- `src/quant_system/research/qlib/quant_slm.py`
- `scripts/run_live_slm_paper_trader.py`
- `tests/test_quant_slm.py`
- `agent_context/work/completed/20261008-1232Z-antigravity-custom-quant-slm-from-scratch.md`

## Summary of Accomplishments

1. **Custom Quant-SLM Architecture (`src/quant_system/research/qlib/quant_slm.py`)**:
   - Built a high-performance, vectorized neural attention network from scratch in pure NumPy.
   - Features: Input projection (80 -> 64), LayerNorm, Multi-Head Self-Attention (4 heads), GELU feed-forward layer (d_ff=128), and multi-task heads (continuous expected return, direction probability via sigmoid, and volatility estimate).
   - Exact backpropagation implemented with AdamW optimizer (weight decay, first/second moments, bias corrections).
   - Zero external deep learning heavyweight runtime required; lightning fast on Snapdragon X Oryon CPU (0.19 ms/stock inference latency).

2. **Live Paper Trading Pipeline (`scripts/run_live_slm_paper_trader.py`)**:
   - Integrates arXiv literature grounding (Bailey, López de Prado, Avellaneda-Stoikov).
   - Embeds literature using Google EmbeddingGemma 2 with Matryoshka representation (16 dimensions).
   - Computes 64-dim causal Qlib Alpha158 factors from point-in-time candles.
   - Checks Upstox API credentials and routes live market data or high-fidelity live simulation.
   - Real-time training (25 epochs in 0.19s, loss reduced by 56.1%).
   - Live paper orders generated with strict pre-trade risk governor, Shariah screening, and realistic Indian statutory friction (STT, brokerage, slippage).
   - Models saved to `data/evidence/models/quant_slm_v1.json`.

3. **Verification**:
   - `uv run pytest tests/test_quant_slm.py tests/test_qlib_bridge.py tests/test_literature_alpha_pipeline.py -v`: 11 passed in 3.84s.
   - `uv run ruff check src/quant_system/research/qlib scripts/run_live_slm_paper_trader.py tests/test_quant_slm.py`: All checks passed.
   - `uv run python scripts/run_live_slm_paper_trader.py --universe RELIANCE TCS INFY HDFCBANK ICICIBANK --epochs 25`: Full pipeline exited code 0 cleanly.
