---
name: quant-model-governance
description: Design, train, validate, review, or promote quantitative trading models where leakage, overfitting, calibration, reproducibility, or real-capital readiness matters.
---

# Quant Model Governance Summary
- Treat edge claims as unproven hypotheses until time-ordered, cost-aware evaluation rejects simpler explanations.
- Decision cutoff strictly respected; no future leakage.
- Strict quarantine of holdout partition: 2025-08-14 to 2026-08-21 (final 252 sessions) must never be accessed during development, tuning, or ranking.
- Compare against baselines: CASH, ALWAYS_TRADE, and 30-seed pseudo-random NOISE control.
- Multiple-testing correction via Deflated Sharpe Ratio (DSR).
