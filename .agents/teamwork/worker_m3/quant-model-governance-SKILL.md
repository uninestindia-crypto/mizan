---
name: quant-model-governance
description: Design, train, validate, review, or promote quantitative trading models where leakage, overfitting, calibration, reproducibility, or real-capital readiness matters. Use for ML alpha, parameter searches, backtest model selection, shadow/paper promotion, drift, and model-risk decisions; do not use for ordinary business ML without market-time or trading concerns.
---

# Quant Model Governance

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
- A model artifact is inseparable from its dataset manifest, feature/label contract, code revision, parameters, random seeds, environment, and evaluation report. Dataset hashes cover every consumed field, row order, schema, adjustment status, source version, and availability timestamp.
- "AI-enhanced" or "consensus" must disclose the actual provider/model and whether a deterministic fallback produced the result.
- No model promotes directly from backtest to live capital. Promotion is discovery -> locked validation -> shadow -> paper -> separately authorized live review.

## Workflow

1. Write the feature/label/execution contract and list every possible leakage path.
2. Establish naive baselines: no-trade/cash, previous-sign, simple momentum or mean reversion, and the existing production/paper model. For directional strategies in drifting markets, add a seeded pseudo-random noise control across identical folds and execution rules.
3. Select a time-aware validation design. For overlapping labels or event horizons, use purging and an embargo; use nested tuning when model selection is material.
4. Fit preprocessing on each training fold only. Treat imputation, scaling, winsorization, feature selection, and calibration as learned state.
5. Evaluate both statistical quality and trading utility. Read [references/validation-protocol.md](references/validation-protocol.md) before implementing or approving training/validation.
6. Freeze a candidate and evaluate exactly once on the final holdout. Any subsequent change creates a new candidate and consumes another trial.
7. Emit a model card and immutable artifact manifest. For rolling or online models, freeze the training policy and retain each decision's training-window hash, preprocessing state, fitted-state hash, and prediction provenance. Refuse promotion if required evidence is missing.
8. Define shadow/paper monitoring, drift thresholds, kill criteria, and rollback before promotion.

## Required review questions

- Could any row contain data published, revised, or selected after its decision time?
- Does the target measure the return available after the specified fill?
- Were universe membership, delistings, corporate actions, and failed data fetches point-in-time correct?
- Were all trials counted, including abandoned notebooks and manual threshold changes?
- Would the conclusion survive worse costs, a one-bar execution delay, and major market regimes?
- Are probabilities calibrated out of sample, or are they merely scores?
- Can an independent run reproduce the exact artifact and metrics from the manifest?
- What observable condition prevents promotion or triggers rollback?

## Refusal conditions

Do not call a model validated or ready when any of these is true:

- The final holdout influenced feature, parameter, threshold, or universe selection.
- Only synthetic data or one favorable period was evaluated.
- Data lineage or timestamp availability cannot be reconstructed.
- The benchmark, costs, trial count, or failure regimes are omitted.
- A classification test only proves that code returns a value, not that predictions or promotion criteria are correct.
- External model calls are nondeterministic but provider/model/prompt/response provenance is not retained.

## Outputs

For implementation work, produce or update the artifacts below. For review-only work, report missing artifacts without editing the repository:

- feature/label/execution contract;
- dataset and trial manifest;
- fold-level evaluation with baselines and uncertainty;
- final-holdout report;
- model card and promotion verdict: `REJECT`, `RESEARCH_ONLY`, `SHADOW`, `PAPER_PILOT`, or `PAPER`;
- monitoring and rollback criteria.

`REJECT` means the evidence is below the `RESEARCH_ONLY` gate or the candidate failed a predeclared gate. `PAPER_PILOT` authorizes only a bounded, predeclared paper campaign after shadow validation. `PAPER` means that campaign itself passed its duration/sample, reconciliation, attribution, monitoring, and rollback criteria. Paper-broker code or generic broker unit tests satisfy neither gate.

Never issue a `LIVE` verdict; live-money authorization is a separate high-risk process.
