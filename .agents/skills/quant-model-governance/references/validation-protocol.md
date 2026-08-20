# Validation Protocol

Read this before implementing or reviewing quantitative model training, selection, or promotion.

## Contract first

Record:

| Field | Required meaning |
|---|---|
| Decision time | Exact timestamp at which the strategy may use features |
| Information cutoff | Latest event/publication/revision included |
| Order time | When an order can first be submitted |
| Fill rule | Price source, delay, spread/slippage/impact behavior |
| Horizon | Start and end of the return the model predicts |
| Label | Formula, units, missing/flat behavior, and class threshold |
| Universe | Point-in-time inclusion/exclusion rule |

Reject any dataset that cannot prove these fields row by row.

## Evaluation design

- Use expanding or rolling walk-forward folds that preserve chronology.
- Purge training observations whose label horizon overlaps validation; apply an embargo after validation when adjacent information can leak.
- Perform parameter and feature selection inside the training side of each fold. If selection is substantial, use nested walk-forward evaluation.
- Reserve a final chronological holdout behind an explicit freeze. Record a dataset hash before opening it.
- Count every evaluated combination as a trial. Apply a multiple-testing correction such as Deflated Sharpe and report assumptions; when selection breadth is large, add a probability-of-backtest-overfitting analysis.
- Evaluate by regime and subperiod, including volatility, trend/range, liquidity, and material market-structure changes.

## Minimum evidence

Predictive metrics, as applicable:

- log loss or Brier score;
- calibration curve/error;
- ROC-AUC or precision/recall only with class balance and decision threshold;
- rank/information coefficient with uncertainty;
- fold dispersion and worst fold.

Trading metrics, net of modeled friction:

- return and volatility;
- Sharpe/Sortino with sample length and benchmark;
- drawdown magnitude and duration;
- turnover, exposure, concentration, trade count, hit rate, profit factor;
- capacity/liquidity assumptions and sensitivity to costs/delay;
- comparison with naive baselines.

Never promote on a single metric.

## Artifact manifest

An artifact must identify:

- stable model ID and creation time;
- source revision;
- environment/lock hash;
- dataset manifest hash and date range;
- universe and point-in-time policy;
- feature schema/version and preprocessing state;
- label/execution contract version;
- parameters, seeds, training folds, and trial count;
- fitted parameters or serialized model hash;
- fold metrics, holdout metrics, and promotion decision;
- known limitations and rollback target.

For a continuously refit model, replace a single serialized-model assumption with a frozen training-policy artifact plus per-decision training-window, preprocessing-state, fitted-state, and prediction hashes.

## Promotion gates

`REJECT`: evidence does not yet satisfy the `RESEARCH_ONLY` gate, or the candidate failed a predeclared data, leakage, statistical, financial, risk, or reproducibility gate.

`RESEARCH_ONLY`: reproducible training and walk-forward evidence exist, but final holdout or operational evidence is incomplete.

`SHADOW`: final holdout passed predeclared thresholds; the model runs on current data without placing simulated orders, with provenance and drift monitoring.

`PAPER_PILOT`: a model-specific shadow campaign passed its predeclared duration/sample requirement and authorizes only a bounded paper campaign with fixed exposure, duration/sample, monitoring, reconciliation, attribution, abort, and rollback criteria.

`PAPER`: the bounded paper campaign completed and met its predeclared duration/sample requirement; paper fills reconcile; data, prediction, and realized outcomes are attributable; rollback/kill controls were exercised. The existence of a generic paper broker or its unit tests is not promotion evidence.

Any contract, feature, preprocessing, threshold, or dataset-policy change returns the candidate to `RESEARCH_ONLY` unless a documented compatibility rule proves otherwise.

## Drift and rollback

Monitor input missingness/range, feature distribution, score distribution, calibration once labels mature, turnover/exposure, rejection reasons, realized cost versus modeled cost, and realized performance versus the validation envelope. Predeclare thresholds and require a safe fallback such as no new positions or the previous approved artifact.
