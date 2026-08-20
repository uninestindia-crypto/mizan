# ADR-004 — Govern one ridge family through evidence-derived promotion

STATUS: accepted  
DATE: 2026-08-20

## Context

The present rolling ridge strategy refits during signal generation, labels close-to-close movement despite next-open fills, and has no model artifact, fold evidence, calibration proof, trial registry, or promotion lifecycle. Adding model breadth would multiply an invalid experimental contract.

## Decision

Govern the existing six-feature ridge family first. Version the feature, preprocessing, label, and execution contracts. Use the next-open-to-following-open return after modeled round-trip costs; reserve a minimum 252-session/20-percent final holdout; purge overlapping labels; embargo at least the label horizon; fit preprocessing only on training folds; compare the required baselines; record every trial; and unlock final holdout only after gates freeze.

Treat scores as `UNCALIBRATED_SCORE` unless the PRD Brier/ECE gate passes. Derive `REJECT`, `RESEARCH_ONLY`, `SHADOW`, `PAPER_PILOT`, and `PAPER` only from immutable evidence, advancing no more than one state per evaluation.

## Rejected alternatives

- **Promote the current rolling strategy after its unit tests pass:** the tests do not prove label/execution alignment, out-of-sample value, or even emitted predictions.
- **Add deep learning, sentiment, or more features:** increases multiplicity and leakage surface before the base contract is valid.
- **Random train/test split or k-fold cross-validation:** violates chronology and label-overlap constraints.
- **Use the final holdout repeatedly:** turns the holdout into training information and invalidates the promotion claim.
- **Manual promotion override:** makes numeric gates advisory and unauditable. A failed candidate may only be superseded by a new candidate/trial.

## Consequences

Early candidates will probably remain research-only; that is a correct outcome. Governed training may run slower because it records folds and evidence, but inference remains bounded. New model families require a new contract version, baselines, validation plan, and multiplicity accounting.
