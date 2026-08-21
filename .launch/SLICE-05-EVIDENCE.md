# Slice 5 Evidence — Final Holdout & Deterministic Promotion

STATUS: PASS  
DATE: 2026-08-21  
REVISION: Current Main

## Verification Results

- `tests/test_modeling_holdout.py`: 5 passed.
- `tests/test_modeling_stress.py`: 4 passed.
- `tests/test_modeling_promotion.py`: 6 passed.
- Total Slice 5 suite: **15 passed in 0.18s (100% PASS)**.

## Key Claims Verified

1. **Single-Use Vault Invariant**: Attempting to reuse an unlocked holdout token raises `ModelingError(HOLDOUT_ALREADY_CONSUMED)` and fails closed.
2. **Stress Sensitivity**: Candidate Sharpe ratio and max drawdown correctly recomputed under 2x costs and 1-bar execution delay.
3. **Promotion State Machine**: Rejects unauthorized state skips or `LIVE` authorization; requires all stress gates to pass before advancing to `SHADOW` or `PAPER_PILOT`.
4. **Content-Addressed Model Card**: SHA-256 model card hashes bind the exact evaluation outputs, fold hashes, and monitoring limits.
