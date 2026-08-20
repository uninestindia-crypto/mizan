# Slice 4 Contract - One Governed Ridge Fold

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-20

## Inputs

- One identity-verified `FeatureDatasetV1`, `LabelDatasetV1`, and `PartitionedFoldV1` from Slice 3.
- The accepted closed six-feature schema and next-open-to-following-open net-cost label contract.
- A valid ridge request with positive exact-decimal L2 penalty, exact score threshold, immutable
  source/lock/architecture identities, fixed seed policy, and a unique multiplicity ordinal.
  Integer fields require exact Python integers; booleans and integer-like substitutes are invalid.

Feature, label, fold, candidate, source dataset, calendar, universe, instrument, and decision-time
identities must agree. Non-finite values, missing feature/label pairs, invalid parameters,
insufficient training rows, and constant targets fail closed with typed codes.

## Learned state and fit

- Mean and population standard deviation are fitted from training feature rows only.
- Zero-variance feature names are explicit and use scale one; they are never silently dropped.
- Validation rows cannot affect preprocessing or fitted-state hashes.
- The governed ridge fit uses one fixed six-feature order, an unregularized intercept, positive L2
  regularization, single-process numerical execution, and no stochastic search.
- Coefficients, intercept, preprocessing state, predictions, metrics, and records are canonical
  decimal text and content hashed. Stored canonical coefficients are used for prediction replay.
- Scores are always `UNCALIBRATED_SCORE`; Slice 4 never claims probability or promotion.

## Trial and multiplicity evidence

- A `STARTED` trial record is committed before preprocessing or fitting.
- A terminal `SUCCEEDED`, `FAILED`, `CANCELLED`, or `ABANDONED` outcome is a separate immutable
  evidence resource bound to the start hash.
- Every unique start increments multiplicity, regardless of terminal outcome.
- The verified immutable trial catalog is the sole authority for the global next ordinal and full
  multiplicity count; a caller-supplied in-memory registry is not accepted as authority.
- A later start is admitted only while the evidence-store lease is held, at the next global ordinal,
  and after every preceding start has exactly one valid terminal outcome. This applies across all
  candidate, feature, parameter, threshold, universe, and source identities.
- A byte-identical latest open start may resume after interruption. Its already-committed model is
  content-deduplicated before the terminal outcome is retried. A terminal start, non-latest start,
  or different start behind an existing ID cannot resume.
- A caught evaluation or model-publication failure receives a typed immutable `FAILED` outcome so
  the next ordinal remains usable. If terminal-outcome publication itself is interrupted, replay of
  that exact open start is the supported recovery transition.
- Canonical trial manifest IDs, total orders, versions, and closed metadata must bind their record.
  Every `SUCCEEDED` outcome must resolve to exactly one content-verified model evaluation with the
  same trial, result hash, candidate, fold, multiplicity, model ID, and `RESEARCH_ONLY` verdict.
- Duplicate trial IDs or ordinals, missing outcomes, outcome/start/model mismatches, alias manifest
  identities, stale caller state, and uncounted starts fail closed.

## Fold evaluation

The candidate and four required baselines use the same validation rows, label timing, and already
bound net costs:

- `NO_TRADE`: no exposure and zero return;
- `BUY_AND_HOLD`: long every matured validation label;
- `PREVIOUS_SIGN`: uses only the latest label matured by each decision time;
- `EQUITY_DUAL_MOMENTUM`: long only when return-10 and SMA-20-distance features are positive.

Each report binds prediction and metric hashes and records accuracy, return, volatility, Sharpe,
Sortino, drawdown magnitude/duration, turnover, exposure, concentration, attributable count, hit
rate, and profit factor.

Rows use one canonical `(candidate_id, decision_at, instrument)` order throughout dataset identity,
fold construction, fitting, and evaluation. When several instruments share a decision time, the
frozen allocation contract is equal weight across active longs for that time. Return, volatility,
Sharpe, Sortino, and drawdown operate on those portfolio-period returns; exposure and turnover use
portfolio periods; concentration is the largest active equal weight. Instrument rows are not
silently compounded as separate full-capital periods.

Deflated Sharpe uses the complete immutable attempt count and the Bailey/López de Prado selection
benchmark. Annualized Sharpe is converted to the 252-period scale used by the report. Sampling
uncertainty uses the actual number of portfolio periods plus observed skewness and Pearson
kurtosis. One trial reduces to sampling-aware PSR. When empirical cross-trial dispersion is not
available, the declared null sampling dispersion `1 / sqrt(T - 1)` is used; callers may supply
annualized cross-trial dispersion when governed evidence supports it.

## Explicit limits

- No final holdout is opened and no promotion gate is evaluated.
- No score is called a probability; Brier/calibration are not applicable in this slice.
- Exact numeric reproducibility is claimed only for the same verified architecture and lock.
- `RESEARCH_ONLY` is the highest possible Slice 4 verdict.
