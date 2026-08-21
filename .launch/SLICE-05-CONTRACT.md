# Slice 5 Contract — Final Holdout & Deterministic Promotion

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-21

## Inputs & Invariants

- **Holdout Vault**: Cryptographic single-use token checking for final holdout dataset unlocking. Accessing the holdout a second time raises `ModelingError(ModelingFailureCode.HOLDOUT_ALREADY_CONSUMED)`.
- **Mandatory Stress Testing**: Evaluates candidates under 2x transaction costs, 1-bar execution delay, and adverse volatility/liquidity regimes.
- **Evidence-Only Promotion Engine**: Deterministic gates emitting verdicts: `REJECT`, `RESEARCH_ONLY`, `SHADOW`, `PAPER_PILOT`, `PAPER`.
- **Zero Live Authorization**: Strict invariant rejecting `LIVE` verdicts (out of scope for T2).
- **Model Card**: Content-addressed model card containing evaluation hashes, drift thresholds, and rollback criteria.
