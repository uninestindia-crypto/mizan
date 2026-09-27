# Quant Model Governance (Local Copy)
Source: D:\quant_system\.agents\skills\quant-model-governance\SKILL.md

Treat every claimed edge as an unproven hypothesis until a time-ordered, cost-aware, reproducible evaluation rejects simpler explanations.

## Non-negotiable invariants
- Define the decision timestamp, information cutoff, order timestamp, fill convention, and prediction horizon before defining features or labels.
- A feature is legal only when its value was available to the strategy at the decision timestamp, including publication and revision lag.
- Evaluate achievable post-fill returns net of fees, spread, slippage, market impact assumptions, and turnover--not an untradeable close-to-close proxy.
- For multi-session overlapping holding periods, enforce capital-constrained tranche accounting so total portfolio exposure never exceeds 100% of available equity.
- In trending or non-zero drift markets, long-only strategies must be benchmarked against an identical-configuration pseudo-random noise control to prevent market beta from masquerading as selection skill.
- Keep discovery, tuning, validation, and final holdout roles separate. Never tune on the final holdout, including manual iteration after seeing it.
- Hyperparameter, feature, universe, and strategy trials all count toward multiple-testing burden.
- Report uncertainty and failure regimes. A point estimate is not a promotion decision.
- A model artifact is inseparable from its dataset manifest, feature/label contract, code revision, parameters, random seeds, environment, and evaluation report.
- "AI-enhanced" or "consensus" must disclose the actual provider/model and whether a deterministic fallback produced the result.
- No model promotes directly from backtest to live capital. Promotion is discovery -> locked validation -> shadow -> paper -> separately authorized live review.
