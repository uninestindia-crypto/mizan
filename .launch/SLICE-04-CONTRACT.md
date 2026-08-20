# Slice 4 Contract - One Governed Ridge Fold

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-20

## Inputs

- One identity-verified `FeatureDatasetV1`, `LabelDatasetV1`, and `PartitionedFoldV1` from Slice 3.
- The accepted closed six-feature schema and next-open-to-following-open net-cost label contract.
- A valid ridge request with positive exact-decimal L2 penalty, exact score threshold, immutable
  source/lock/architecture identities, fixed seed policy, and a unique multiplicity ordinal.

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
- Duplicate trial IDs or ordinals, missing outcomes, outcome/start mismatches, stale caller state,
  and uncounted starts fail closed.

## Fold evaluation

The candidate and four required baselines use the same validation rows, label timing, and already
bound net costs:

- `NO_TRADE`: no exposure and zero return;
- `BUY_AND_HOLD`: long every matured validation label;
- `PREVIOUS_SIGN`: uses only the latest label matured by each decision time;
- `EQUITY_DUAL_MOMENTUM`: long only when return-10 and SMA-20-distance features are positive.

Each report binds prediction and metric hashes and records accuracy, return, volatility, Sharpe,
Sortino, drawdown magnitude/duration, turnover, exposure, concentration, attributable count, hit
rate, and profit factor. Deflated Sharpe uses the complete immutable trial multiplicity.

## Explicit limits

- No final holdout is opened and no promotion gate is evaluated.
- No score is called a probability; Brier/calibration are not applicable in this slice.
- Exact numeric reproducibility is claimed only for the same verified architecture and lock.
- `RESEARCH_ONLY` is the highest possible Slice 4 verdict.
