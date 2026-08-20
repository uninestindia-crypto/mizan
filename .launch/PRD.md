# PRD — QuantOS Governed Research and Paper/Shadow Readiness

STATUS: G1 candidate  
TIER: T2  
SCOPE: Professional research, governed ML training, and real-data shadow/paper readiness. Live-money execution is excluded.

## Users

Primary: an individual quantitative researcher or systematic trader on Windows 11 evaluating NSE cash-equity and NIFTY-options ideas without exposing live capital.

Secondary, ranked:

1. A quantitative model owner deciding whether a model advances from research to shadow and then bounded paper use.
2. An engineer extending strategies, data connectors, analytics, or the desktop/API contract.

Financial truth, point-in-time validity, and explicit failure take priority over throughput, model breadth, and presentation.

## Stories

- **S-1 — Start and understand:** As a researcher, I need QuantOS to disclose its supported capabilities so I cannot mistake research, shadow, or paper simulation for live execution.
- **S-2 — Obtain point-in-time data:** As a researcher, I need effective-dated provenance, completeness, and quality evidence so later information cannot enter an earlier decision.
- **S-3 — Train a governed model:** As a model owner, I need fixed inputs, time-valid features, an executable target, and recorded trials so training is reproducible and auditable.
- **S-4 — Validate and promote:** As a model owner, I need isolated holdout evidence and predeclared gates so promotion cannot depend on favorable interpretation after results are known.
- **S-5 — Run financial research:** As a researcher, I need executable timing, effective-dated costs, pre-trade risk, and Decimal reconciliation so ideas are tested without hidden favorable assumptions.
- **S-6 — Observe shadow and paper behavior:** As a researcher, I need attributable shadow decisions and quote-driven paper fills without broker order submission so unseen behavior can be observed without capital risk.
- **S-7 — Reproduce and extend:** As an engineer, I need desktop, API, export, and replay to share one evidence contract so every research claim is reproducible.

## Acceptance criteria

### Truthful capability and startup

**AC-1** GIVEN any desktop screen, API result, export, diagnostic, model card, or documentation page describes execution WHEN it is shown THEN its execution mode is exactly `RESEARCH_BACKTEST`, `SHADOW_READ_ONLY`, or `PAPER_SIMULATION`; `LIVE` and equivalent broker-routing claims do not appear.

**AC-2** GIVEN all release-critical journeys run WHEN broker traffic is captured THEN broker order-create, order-modify, and order-cancel request counts are each zero.

**AC-3** GIVEN any dataset or result is displayed or exported WHEN its provenance is inspected THEN its source is exactly `SYNTHETIC`, `USER_CSV`, `UPSTOX_HISTORICAL`, `UPSTOX_QUOTE`, `RECORDED_PROVIDER_FIXTURE`, or `VALIDATED_CACHE`, with acquisition time and age.

**AC-4** GIVEN an AI-advisor contribution is displayed or exported WHEN its provenance is inspected THEN the contributor and mode are `EXTERNAL_CLI` or `DETERMINISTIC_HEURISTIC`; heuristic output is not labeled remote analysis or external consensus.

**AC-5** GIVEN the first desktop view or an exported report is rendered WHEN the user reads its capability notice THEN it says: “Research, backtesting, paper, and shadow use only. QuantOS does not place live broker orders and does not provide investment advice.”

**AC-6** GIVEN a clean supported Windows 11 installation has no Upstox or AI credentials WHEN QuantOS starts THEN it binds only to loopback, exposes the dashboard, completes mandatory diagnostics, identifies optional unavailable capabilities, and offers a credential-free synthetic backtest.

**AC-7** GIVEN an x64 or ARM64 package is advertised as supported WHEN its evidence is inspected THEN a clean-install verification record exists for that exact build and architecture.

**AC-8** GIVEN any mandatory startup diagnostic fails WHEN startup is attempted THEN the engine does not report `HEALTHY` and displays the failed check, detection time, consequence, and recovery action.

### Point-in-time market data

**AC-9** GIVEN a dataset is accepted WHEN its manifest is opened THEN it records provider, provider instrument ID, mapping history, event/exchange time, provider time when supplied, ingestion time, timezone, calendar version, requested/received ranges, interval, units, currency, raw/adjusted status, transformation version, source status, row count, canonical content hash, corporate-action authority, historical-universe authority, and quality findings.

**AC-10** GIVEN governed release evidence is inspected WHEN venue scope is listed THEN it contains only NSE cash equities and NIFTY options; US equities and other venues are not release-certified.

**AC-11** GIVEN configured equities `INFY`, `TCS`, `RELIANCE`, `HDFCBANK`, and `ICICIBANK` are acquired from Upstox WHEN daily evidence is accepted THEN each contains at least five years of completed NSE sessions when provider history permits; a shorter range is `PARTIAL` and blocks governed use.

**AC-12** GIVEN Upstox cannot supply five years for a configured instrument WHEN evidence is requested THEN the result identifies requested/received dates and `PROVIDER_RANGE_UNAVAILABLE`, and is eligible only for labeled research.

**AC-13** GIVEN NIFTY-options release evidence is inspected WHEN its contract fields are checked THEN it contains underlying, call/put, strike, expiry, multiplier/lot size, tick size, bid, ask, bid/ask quantity, exchange time, ingestion time, and source provenance.

**AC-14** GIVEN an as-of decision time `T` WHEN features, labels, a backtest, or replay are constructed THEN every consumed value has an availability time at or before `T`; a post-`T` value is rejected with the offending row identified.

**AC-15** GIVEN a historical universe decision at `T` is replayed WHEN membership is calculated THEN it uses the effective-dated authority for `T`; later additions, removals, renames, suspensions, and delistings do not alter it.

**AC-16** GIVEN corporate-action or historical-universe authority is absent for a governed period WHEN training, final-holdout evaluation, `SHADOW`, `PAPER_PILOT`, or `PAPER` promotion is requested THEN promotion is blocked and affected instruments/dates are named; labeled research remains available.

**AC-17** GIVEN an alternative effective-dated authority is selected WHEN a new dataset is created THEN the new manifest identifies it and produces a new hash without rewriting prior evidence.

**AC-18** GIVEN duplicates, conflicting keys, reverse ordering, invalid OHLC, non-positive prices, invalid volume/open interest, missing sessions, timezone conflicts, crossed quotes, or unknown instruments exist WHEN validation runs THEN every category and affected count is reported and no blocking finding is silently repaired.

**AC-19** GIVEN a duplicate/conflict has an approved deterministic disposition WHEN repaired THEN the manifest records retained/discarded observations, rule, and transformation hash.

**AC-20** GIVEN daily NSE data omits the last completed exchange session or a market-hours quote is more than five seconds old WHEN it is used THEN it is `STALE` and cannot create a shadow decision or paper fill.

**AC-21** GIVEN two otherwise identical datasets differ in any consumed value, row order, schema, timestamp, provider identity, adjustment rule, universe record, quality disposition, or transformation WHEN canonical hashes are calculated THEN their hashes differ.

**AC-22** GIVEN provider timeout, 429, 5xx, malformed/HTML body, expired authorization, schema drift, empty result, partial range, or partial symbol set occurs WHEN Upstox data is requested THEN a typed outcome is shown and no synthetic/cache substitution occurs without separate affirmative user action.

### Effective-dated NSE financial rules

**AC-23** GIVEN a fee, tax, charge, calendar, lot size, tick size, expiry rule, or settlement rule is used WHEN its configuration is inspected THEN it records a primary-source document/URL, publication date, effective-from/effective-to dates, segment, basis, and rounding rule.

**AC-24** GIVEN a historical trade date WHEN costs or contract rules are calculated THEN the version effective on that date is selected and later rules are excluded.

**AC-25** GIVEN a financial result is displayed or exported WHEN friction is inspected THEN brokerage, STT, exchange charges, SEBI charges, stamp duty, GST, spread, slippage, and other configured friction are individually visible before the total.

**AC-26** GIVEN values immediately below, at, and above a cost/tax rounding boundary WHEN evaluated THEN every component and total match the effective-dated reference to its published rounding unit.

**AC-27** GIVEN an NSE option proposal is evaluated WHEN contract validation runs THEN identity, underlying, call/put, strike, expiry, effective-dated lot size, multiplier, tick size, and current status are valid or the proposal receives a typed rejection and cannot fill.

**AC-28** GIVEN a rule version changes within historical evidence WHEN fixtures immediately before and after the effective date are calculated THEN each matches an independently derived primary-source reference and records a different rule version.

### Governed model training

**AC-29** GIVEN a training row is decided at bar close `t` WHEN its label is built THEN entry is the first eligible open after `t`, exit is the following eligible open, modeled round-trip costs are deducted, and the label is `UP` only when net return is positive; zero/negative is `DOWN`.

**AC-30** GIVEN any training row is inspected WHEN chronology is reviewed THEN decision time, information cutoff, order time, entry/exit times, universe membership, and cost-rule versions are recorded and valid.

**AC-31** GIVEN any feature or learned preprocessing value is inspected WHEN lineage is reviewed THEN it uses information available at the row’s decision time and scaling, imputation, winsorization, feature selection, and calibration are fitted only on the training side of the fold.

**AC-32** GIVEN eligible chronology is partitioned WHEN the final holdout is reserved THEN it contains at least 252 completed NSE sessions and at least 20% of eligible chronology; otherwise the candidate remains `RESEARCH_ONLY`.

**AC-33** GIVEN labels overlap a later fold/holdout WHEN partitions are formed THEN overlapping training labels are purged and embargo is at least the maximum label horizon.

**AC-34** GIVEN discovery/validation is active WHEN model, feature, parameter, threshold, or universe selection occurs THEN final holdout remains locked until candidate, dataset hash, trial count, and numeric gates are frozen.

**AC-35** GIVEN a continuously refitted model artifact is opened WHEN provenance is inspected THEN it contains a frozen training-policy artifact plus per-decision training-window, preprocessing-state, fitted-state, and prediction hashes.

**AC-36** GIVEN a model artifact is reviewed WHEN required metadata is checked THEN it records model ID, creation time, source revision, environment/lock hash, dataset manifest/range, universe policy, feature schema/version, preprocessing state, label/execution contract, parameters, seeds, folds, trial count, fitted-state hash, metrics, limitations, verdict, and rollback target.

**AC-37** GIVEN identical accepted data, configuration, seed, dependency lock, source revision, and architecture WHEN training repeats THEN fold, prediction, metric, artifact, and verdict hashes match.

**AC-38** GIVEN insufficient history, zero eligible rows, invalid/constant targets, non-finite features, unknown instruments, invalid parameters, or unresolved data authority WHEN governed training is requested THEN no promotable artifact is created and every blocking condition is named.

**AC-39** GIVEN output is described as probability WHEN evaluated THEN holdout Brier score beats the training-side climatology baseline and expected calibration error is at most `0.05`; otherwise every surface says `UNCALIBRATED_SCORE`.

**AC-40** GIVEN a feature/model/parameter/threshold/universe combination finishes, fails, or is cancelled WHEN trial history is inspected THEN it has a unique immutable trial record included in multiplicity count.

### Validation and promotion

**AC-41** GIVEN a locked candidate completes walk-forward validation WHEN fold evidence is inspected THEN every fold identifies train/validation/purge/embargo periods, counts, class balance, predictions, fills, costs, predictive metrics, and trading metrics.

**AC-42** GIVEN a validation report is reviewed WHEN baselines are inspected THEN the same chronology/execution assumptions include `NO_TRADE`, `BUY_AND_HOLD`, `PREVIOUS_SIGN`, and `EquityDualMomentum`.

**AC-43** GIVEN a candidate report is opened WHEN metrics are inspected THEN it includes Brier/calibration when applicable, fold/worst-fold Sharpe, return, volatility, Sortino, drawdown/duration, turnover, exposure, concentration, attributable count, hit rate, profit factor, capacity assumptions, and cost/delay sensitivity.

**AC-44** GIVEN candidate/baseline financial performance is reported WHEN execution is inspected THEN it uses next-open-to-next-open timing and effective-dated round-trip costs, spread, and slippage.

**AC-45** GIVEN multiple trials exist WHEN Deflated Sharpe is calculated THEN multiplicity equals all recorded model, feature, parameter, threshold, and universe trials, including failures and abandoned/manual trials.

**AC-46** GIVEN the final holdout remains locked WHEN `SHADOW` gates are frozen THEN they require at least 252 sessions and 20% chronology, at least 100 attributable matured records, positive net return at default and twice-default costs, DSR at least `0.95`, max drawdown at most `15%`, no mandatory fold Sharpe below `-0.5`, and AC-39 for probabilities.

**AC-47** GIVEN a locked candidate is evaluated exactly once on final holdout WHEN every AC-46 and data/leakage/reproducibility/financial/risk gate passes THEN verdict becomes `SHADOW`; otherwise it is `RESEARCH_ONLY` or `REJECT` with failed gates listed.

**AC-48** GIVEN final-holdout evidence exists WHEN contract, feature, preprocessing, threshold, cost, universe, or dataset policy changes THEN a new candidate/trial is created and original evidence remains immutable.

**AC-49** GIVEN mandatory stress tests run WHEN default/twice-default costs, one-bar delay, missing bar, stale quote, 20% adverse gap, maximum spread, zero quantity, duplicate event, and out-of-order event are evaluated THEN every outcome is attributable, completed ledgers reconcile to the paisa, and blocked cases record reasons.

**AC-50** GIVEN a candidate reaches `SHADOW` WHEN its model card is opened THEN numeric limits exist for input missingness, feature/score distributions, matured-label calibration, turnover/exposure, risk rejection rates, realized/model costs, and performance envelope, each with halt/rollback behavior.

**AC-51** GIVEN a required input is missing, stale, outside schema, or tied to an unapproved authority WHEN shadow inference is requested THEN no decision is emitted and the reason is recorded.

### Critical research journeys

**AC-52** GIVEN the five-symbol, 252-daily-bar seeded synthetic fixture WHEN the equity backtest runs twice THEN input digest, decisions, risk outcomes, fills, costs, equity curve, metrics, and tearsheet hashes match.

**AC-53** GIVEN a bar-close decision at `t` WHEN a bar fill occurs THEN it uses the first eligible later open with adverse configured slippage and no post-cutoff information from `t`.

**AC-54** GIVEN active risk limits change WHEN later orders are evaluated THEN each uses the new immutable version while completed evaluations retain their original version.

**AC-55** GIVEN an order breaches position, cash-buffer, spread, drawdown, leverage, kill-switch, lot/tick, liquidity, or naked-short limits WHEN evaluated THEN it does not fill and identifies configured threshold and observed value.

**AC-56** GIVEN an equity backtest completes WHEN displayed/exported THEN it includes data/rule provenance, strategy/model identity, parameters, mode, initial/final equity, decisions, risk outcomes, fills, component costs, equity curve, reconciliation, performance, and limitations.

**AC-57** GIVEN approved NIFTY-options fixtures WHEN Options Lab runs THEN call/put prices and Greeks match independent references within `1e-6`, costs reconcile to the paisa, contract metadata is shown, and output says analytical simulation.

**AC-58** GIVEN equivalent supported desktop/API inputs WHEN both complete THEN input digest, provenance, mode, rule versions, financial results, and reconciliation match.

**AC-59** GIVEN an unsupported strategy, symbol, range, numeric value, artifact, or parameter is submitted WHEN validation runs THEN every invalid field and allowed constraint is shown and no run/update/artifact is created.

**AC-60** GIVEN a desktop operation is unfinished after 500 ms WHEN observed THEN operation ID/elapsed time are shown, progress/heartbeat updates at least every five seconds, and cancellation appears after 30 seconds without duplicate submission.

### Shadow and paper behavior

**AC-61** GIVEN a `SHADOW` model and valid read-only Upstox data WHEN a shadow session runs THEN predictions, decisions, risk outcomes, and matured outcomes are recorded while broker order traffic remains zero.

**AC-62** GIVEN a quote-driven paper decision becomes eligible WHEN simulated execution runs THEN it uses the first later valid quote: buy at ask and sell at bid before adverse slippage, quote age is at most five seconds, and full quote provenance is recorded.

**AC-63** GIVEN paper quantity exceeds displayed executable quantity WHEN processed THEN no more than captured quantity fills and the remainder is pending until a valid quote or session-end cancellation.

**AC-64** GIVEN a duplicate proposal or replayed quote event arrives WHEN processed THEN quantities, cash, fees, positions, and P&L do not change twice.

**AC-65** GIVEN a crossed, locked-without-quantity, wide, stale, out-of-order, unknown-instrument, wrong-lot, wrong-tick, or zero-liquidity quote WHEN execution is attempted THEN fill is blocked with a typed reason.

**AC-66** GIVEN a shadow/paper proposal is inspected WHEN audit fields are checked THEN it records ID, model artifact, data/quote provenance, decision/order times, side/quantity, risk version, approval, fill status, and rejection/cancellation reason.

**AC-67** GIVEN a model is not `SHADOW`, its approved schema/policy changed, or data is stale/partial WHEN shadow starts THEN the session is blocked with every failed condition.

**AC-68** GIVEN an active shadow session loses connectivity/authorization WHEN detected THEN new decisions halt, state becomes `OFFLINE`/`UNAUTHORIZED`, and no automatic cache/synthetic substitution occurs.

**AC-69** GIVEN a `SHADOW` model seeks `PAPER_PILOT` WHEN its real-time shadow campaign is reviewed THEN it contains at least 20 completed NSE sessions and 100 attributable matured decisions, continuing until both pass.

**AC-70** GIVEN AC-69 passes WHEN pilot eligibility is evaluated THEN captured data replays without hash mismatch, quote simulation reconciles, attribution is complete, monitoring alerts and halt/rollback behavior pass, and verdict becomes `PAPER_PILOT`; otherwise promotion is refused.

**AC-71** GIVEN a `PAPER_PILOT` runs WHEN promotion to `PAPER` is evaluated THEN the bounded campaign contains at least 20 completed NSE sessions and 100 attributable matured decisions/fills, meets its frozen financial/risk/monitoring gates, reconciles, and has exercised halt/rollback; otherwise it remains `PAPER_PILOT` or is demoted.

**AC-72** GIVEN a shadow/paper session ends normally, is cancelled, or is interrupted WHEN its audit opens THEN completed, rejected, pending, cancelled, and unprocessed proposals are distinguished and reconciliation status is reported.

### Reproduction and release limits

**AC-73** GIVEN a governed operation completes WHEN its evidence bundle exports THEN it contains input/model manifests, immutable configuration, rule/risk versions, predictions, decisions, risk outcomes, fills, component costs, metrics, reconciliation, warnings, and capability labels.

**AC-74** GIVEN an evidence bundle is replayed on the same verified architecture/lock WHEN verification completes THEN input, preprocessing, fitted-state, prediction, decision, fill, cost, ledger, equity-curve, and report hashes match.

**AC-75** GIVEN secrets or external-service errors occur WHEN desktop/API/log/process/export output is inspected THEN tokens, keys, authorization headers, and full credential values are absent.

**AC-76** GIVEN a governed request exceeds five symbols, ten years of daily bars, or a 100 MiB bundle WHEN submitted THEN it is rejected before calculation and actual/permitted values are shown.

**AC-77** GIVEN one governed operation is active WHEN a second is submitted THEN the second is refused as `CONCURRENT_LIMIT` and cannot mutate active data, risk, ledger, artifacts, or results.

**AC-78** GIVEN a clean verified Windows 11 installation WHEN seven critical journeys run THEN startup, governed training/validation, deterministic equity backtest, NIFTY-options simulation, risk enforcement, Upstox success-or-explicit-failure, and recorded-data shadow replay complete with zero unhandled exceptions, zero reconciliation failures, zero broker orders, and zero unlabeled sources/modes.

## Non-goals — the cut line

- Live broker order creation/modification/cancellation, autonomous execution, or unattended capital deployment; separately charter as T4.
- US equities, other exchanges, non-NIFTY derivatives, futures, commodities, currencies, or crypto in release certification.
- Guaranteed profitability, investment advice, suitability, regulatory certification, or unsupported “institutional-grade” claims.
- New model families before the current rolling model passes governed evidence.
- Fundamental, news, social-sentiment, FinBERT, and alternative-data roadmap features.
- Cloud deployment, remote access, accounts, tenancy, collaboration, or additional brokers.
- Tick/HFT/colocation or market-impact claims beyond disclosed quote size, spread, and slippage.
- Overnight NIFTY-options exercise, assignment, and settlement; paper evidence is intraday and unresolved positions close/cancel at session end.
- A database/migration subsystem; immutable file evidence and restart-safe replay are sufficient.
- AI authority over promotion, size, risk limits, or execution.
- General visual redesign outside the seven critical journeys.
- A claim that statistical gates establish future alpha.
- Advertising an architecture without an architecture-specific clean-install record.

## Failure states

Every failure includes operation ID, typed status, detection time, data/execution mode, last confirmed result where available, and recovery action. Partial or failed outcomes are never labeled complete.

### S-1 — Start and understand

- **EMPTY:** Show unavailable optional capabilities and offer synthetic research.
- **LOADING:** Show startup checks and elapsed time after 500 ms.
- **ERROR:** Prevent `HEALTHY`, name the failed mandatory check, preserve diagnostics.
- **OFFLINE:** Start local research and mark external services unavailable.
- **UNAUTHORIZED:** Mark Upstox unavailable without exposing credentials.
- **SLOW:** After 30 seconds identify unfinished check and expose cancellation.
- **PARTIAL/STALE:** Report `DEGRADED`, never `HEALTHY`.
- **TOO MUCH DATA:** Reject recovery artifacts above 100 MiB with actual/limit shown.
- **CONCURRENT:** Identify the active instance or use a separate loopback port without corruption.

### S-2 — Obtain point-in-time data

- **EMPTY:** Report zero accepted rows, requested range, source, recovery action.
- **LOADING:** Show provider, instruments, range, elapsed time, heartbeat.
- **ERROR:** Preserve last accepted manifest and identify failure.
- **OFFLINE/UNAUTHORIZED:** Halt provider acquisition without source substitution.
- **SLOW:** End at bounded provider deadline with typed timeout, not partial success.
- **PARTIAL/STALE:** Name instruments/dates/counts/age and block governed use.
- **TOO MUCH DATA:** Reject above five symbols/ten years before acquisition.
- **CONCURRENT:** Refuse second governed acquisition.

### S-3 — Train a governed model

- **EMPTY:** Create no artifact and state why zero eligible rows remain.
- **LOADING:** Show trial, stage, elapsed time, heartbeat.
- **ERROR:** Preserve prior artifacts and record failed trial.
- **OFFLINE:** Continue only from complete accepted local data.
- **UNAUTHORIZED:** Halt unavailable external dependencies without relabeling heuristics.
- **SLOW:** Expose cancellation after 30 seconds and retain trial record.
- **PARTIAL/STALE:** Block governed training; allow labeled research only.
- **TOO MUCH DATA:** Reject above release limits before fitting.
- **CONCURRENT:** Refuse second run; forbid shared mutable model state.

### S-4 — Validate and promote

- **EMPTY:** Zero folds, short holdout, or fewer than 100 records yields `INSUFFICIENT_EVIDENCE`.
- **LOADING:** Show candidate, fold, counts, elapsed time, heartbeat.
- **ERROR:** Keep unpromoted and preserve prior reports.
- **OFFLINE:** Continue only from complete accepted evidence.
- **UNAUTHORIZED:** Keep holdout locked when its lock is unverifiable.
- **SLOW:** Expose cancellation; incomplete folds do not count.
- **PARTIAL/STALE:** Invalidate promotion and name missing dependencies.
- **TOO MUCH DATA:** Reject above limits before evaluation.
- **CONCURRENT:** Refuse second request while locked evaluation runs.

### S-5 — Run financial research

- **EMPTY:** Produce no metrics without bars/eligible option legs.
- **LOADING:** Show type, observations processed, elapsed time, heartbeat.
- **ERROR:** Preserve prior complete result; do not label partial ledger reconciled.
- **OFFLINE:** Keep accepted local-data journeys with actual source labels.
- **UNAUTHORIZED:** Halt broker input; alternates require affirmative selection.
- **SLOW:** Expose cancellation after 30 seconds without duplicate submission.
- **PARTIAL/STALE:** Exclude affected result from governance.
- **TOO MUCH DATA:** Reject above release limits.
- **CONCURRENT:** Refuse second governed run and preserve frozen state.

### S-6 — Observe shadow and paper

- **EMPTY:** Show no proposals and reason; manufacture no trades.
- **LOADING:** Show mode, connection, last quote, campaign counts, elapsed time.
- **ERROR:** Halt proposals, preserve audit, show reconciliation.
- **OFFLINE/UNAUTHORIZED:** Halt provider use without fallback.
- **SLOW:** Treat quotes older than five seconds as stale.
- **PARTIAL/STALE:** Block affected proposals and name dependencies.
- **TOO MUCH DATA:** Reject above five instruments/100 MiB.
- **CONCURRENT:** Refuse second governed session and isolate state.

### S-7 — Reproduce and extend

- **EMPTY:** Return named not-found outcome, not placeholder success.
- **LOADING:** Show bundle/run, verification stage, elapsed time, heartbeat.
- **ERROR:** Report first hash mismatch and preserve both records.
- **OFFLINE:** Replay only with all declared local dependencies.
- **UNAUTHORIZED:** Hide protected inputs and name missing authority.
- **SLOW:** Expose cancellation while retaining last verified stage.
- **PARTIAL/STALE:** Mark missing-manifest bundle non-reproducible.
- **TOO MUCH DATA:** Reject bundles above 100 MiB.
- **CONCURRENT:** Refuse second replay and prevent cross-run mutation.

## Success metric

**100% (7/7)** of the release-critical journeys pass from a clean verified Windows 11 installation with zero unhandled exceptions, zero Decimal Ledger reconciliation failures, zero broker order submissions, and zero missing source/mode labels.

## Ambiguity log

| # | Ambiguity | Decision/assumption | Owner before affected gate | Blocking G1? |
|---|---|---|---|---:|
| 1 | Corporate-action authority | Pluggable effective-dated authority; missing authority blocks promotion, not research | Data owner | No |
| 2 | Historical-universe authority | Same contract; present-day constituents cannot be backfilled | Data owner | No |
| 3 | Provider timeout/retry budget | Bounded, visible, typed, and `Retry-After` aware; exact values set/tested at architecture | API owner | No |
| 4 | External AI advisors | Optional; provenance mandatory; cannot replace quant gates | Founder | No |
| 5 | Session persistence | Resumable real-time sessions excluded; immutable audit/replay required | Founder | No |
| 6 | Flat net return | Conservatively `DOWN` because costs were not overcome | Model owner | No |
| 7 | 100-record definition | Freeze either matured decisions or round trips before holdout; never double-count | Model owner | No |
| 8 | ARM64 timing | Unadvertised until native clean-install evidence exists | Release owner | No |
| 9 | Overnight options | Excluded; expansion is a separate slice | Founder | No |
| 10 | Provider history unavailable | Typed limitation blocks promotion but not truthful research launch | Data owner | No |

## External source basis

- Upstox Historical Candle Data V3 documents daily history and bounded retrieval windows: https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/
- NSE circular NSE/FA/73061 demonstrates effective-dated transaction-charge changes: https://nsearchives.nseindia.com/content/circulars/FA73061.pdf
- NSE publishes effective-period levy references: https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies
