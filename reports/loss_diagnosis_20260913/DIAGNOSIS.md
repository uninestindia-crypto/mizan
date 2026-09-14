# Why the virtual trading books are losing

Completed 2026-09-14 IST from the latest saved snapshots available. Code reviewed at
`f43f4f62f88440ce624dd7489780585c2e2f05dd`. This is a diagnostic review, not a release certification
or a model promotion. The user has not begun live-money trading.

The evidence does not support starting personal live trading with these candidates. There are real
marked price losses in the flagship account, a material corporate-action valuation omission in the
second book, and no demonstrated predictive edge sufficient to justify promotion. Fixing reporting
will make the results more trustworthy; it cannot by itself make a strategy profitable.

## What the latest accounts actually say

Each book starts with INR 1,000,000. Their marks are from different dates and price conventions, so
the two returns are not a synchronized performance comparison.

| Measure | Mizan flagship | XS-Monthly |
|---|---:|---:|
| Price timestamp/basis | 2026-09-11, 15:29:41 IST | 2026-09-10 daily open |
| Funded open positions | 97 | 91 |
| Entry consideration | 853,407.04 | 862,815.98 |
| Cash | 145,520.31 | 137,184.02 |
| Recorded marked value | 840,749.87 | 856,875.60, parent shares only |
| Marked price P&L | **-12,657.17** | **-5,940.38**, incomplete economic valuation |
| Paid lifetime fees | 1,072.65 | 0; costs deferred until closing |
| Recorded equity | **986,270.18** | 994,059.62, entitlement omitted |
| Recorded net P&L after paid fees | **-13,729.82 (-1.372982%)** | Full economic P&L **unknown** |

The XS watch ran on September 13, but its prices still refer to September 10. A recent processing
timestamp must not be presented as a fresh market valuation.

The flagship identities reconcile exactly using decimal arithmetic:

```text
853,407.04 entry + 1,072.65 fees + 145,520.31 cash = 1,000,000.00
840,749.87 market value + 145,520.31 cash          =   986,270.18
-12,657.17 price P&L - 1,072.65 fees              =   -13,729.82
```

Thus approximately 92% of its recorded loss is marked price movement against acquisition cost;
approximately 8% is paid fees. Acquisition prices may already include slippage. These figures do not
independently certify every dividend receivable or every quote, and closing costs have not yet been
paid. They reconcile the saved account rather than certify economic total return.

Sources: [status](../../logs/paper_runs/live_paper_status.json),
[portfolio](../../logs/paper_runs/portfolio_state.json),
[XS state](../../logs/xs_monthly_new/paper_watch/state.json).
[reconcile.ps1](reconcile.ps1) independently derives the amounts, checks accounting identities, and
records source SHA-256 hashes. Its output is retained in [snapshot.json](snapshot.json).

## Why this is happening

### 1. The portfolios do not automatically learn from virtual losses

The default paper runner loads a frozen model through
`scripts/run_paper_pilot_session.py:974` and
`src/quant_system/execution/mizan_execution.py:68`. The default weights in
`src/quant_system/modeling/mizan_model.py:548` identify **trial_mizan_h11_002**, whose embedded
research evidence reports Sharpe **-0.410755** and deflated Sharpe **0.175990** against a **0.95**
gate. The newer flagship model card describes **trial_mizan_h11_003**, a different artifact.

Training a new artifact does not replace these running weights. Repeated paper sessions exercise
the existing decision policy; they are not an online learning process. Preserving a frozen paper
experiment is appropriate, but the UI and reports need to name the exact model under observation.
Similarly, XS-Monthly is a fixed momentum-ranking rule, not a neural model being retrained daily.

The actual top-fraction portfolio policy also needs evaluation as a complete system. A related
eight-feature screen or a threshold-based model trial cannot stand in for the exact 15-feature,
top-fraction, integer-share, next-fill paper implementation.

### 2. Market exposure produces losses unless stock selection or timing compensates

The flagship has roughly 85% of its current equity invested. Its latest snapshot contains 70 losing
and 27 winning holdings. Holding many stocks reduces single-name concentration but does not remove
their shared market exposure. The short observed period cannot distinguish persistent negative
selection skill from a difficult market interval.

The existing paper benchmark equal-weights the **same selected names**. It evaluates sizing within
that basket; it cannot prove whether choosing those names from the eligible universe was useful.
It also does not provide a clean market-versus-selection decomposition of the current loss.
Do not repeat an earlier seven-session market attribution as if it explained this later snapshot.

The repaired corporate-action screen in `reports/mizan_ab_screen_v2/arm-b-adjusted.txt` still reports
selection edge **-0.000236**, about **-2.36 basis points per 10-session window**, with reported
t-statistic **-0.86**. This is a related research screen, not independent chronological validation of
the running portfolio. It does not demonstrate useful selection edge; correcting the data did not
produce a compelling positive result. Its overlapping observations and universe limitations prevent
reading the reported statistic as conclusive proof that all possible strategies lack an edge.

### 3. HEG makes the second book's apparent loss misleading

The saved XS position is 13 HEG shares, bought at INR 725, with the latest parent-share mark at
INR 253.90:

```text
HEG entry                       9,425.00
HEG parent shares marked        3,300.70
Apparent HEG loss              -6,124.30
All other funded positions       +183.92 gross
Raw displayed book loss        -5,940.38
```

The [company's August 24 filing, reproduced with its document text](https://bazaarwatch.com/announcement/88270/heg-ltd-attached)
sets the September 7 record date and a one-for-one HEG Graphite entitlement. The simulated holding
predates that date. Its 13 resulting-company shares must be represented; a missing price must remain
explicitly unknown. The issuer website was inaccessible during direct retrieval; the filing text was
read from the republication, not its AI summary.

The helper in `src/quant_system/research_xs_monthly/paper.py:196` accepts an
`unpriced_entitlements` map, but **neither scheduled caller supplies it**:
`scripts/run_xs_monthly_paper_watch.py:80` and `:102`. The current state therefore still records the
whole parent-price drop as a loss. The maturity/close branch at `paper.py:227` also ignores that map.

Passing the map alone would be an incomplete repair: the runner totals missing values as zero at
`:119`, its renderer assumes `gross_mark` exists at `:158`, and the dashboard defaults a missing
gross mark to zero at `src/quant_system/server/ui/live_dashboard.py:1130`. The complete fix must
preserve the entitlement through open valuation, reporting, restart, and eventual disposal.

Excluding HEG is only a diagnostic. The other positions' **+183.92 gross** becomes approximately
**-1,727.68** after reserving the simulator's existing 0.224% round-trip cost on their entry notional.
That assumption is not a newly verified broker fee schedule. Full-book economic P&L remains unknown;
neither deleting HEG nor reversing INR 6,124.30 would be a valid correction.

### 4. Some research reports overstate what their numbers establish

These findings affect confidence in the proposed remedy as well as the headline loss:

| Finding | Consequence and repair |
|---|---|
| `reevaluate_paper_books.py:288` applies a full 0.224% round-trip proxy to marked value as prospective exit costs, after flagship entry fees were already paid | Its **-15,613.10** is not the actual saved account loss. Recompute remaining sell-side components from the same dated fee contract used by the book; keep paid and prospective costs separate. |
| Its own-marks benchmark at `:394` charges zero entry fees, while flagship bears INR 1,072.65 | The reported **-457.38 excess** is not cost-matched. Gross sizing difference is approximately **+616.65**; neither number tests stock selection. |
| `research_short_horizon/evaluation.py:176-189` averages multi-session outcomes by decision date and compounds them as sequential returns | Overlapping holdings lack an explicit capital allocation and daily mark-to-market path. Published total-return and drawdown figures are not yet proven realizable portfolio statistics. |
| `evaluation.py:273-293` selects abstention thresholds and reports scores on the same pooled validation observations | These are development results after selection, not a separate untouched performance test. Use nested/past-only calibration and preserve the final holdout. |
| `run_short_horizon_experiment.py:63` still declares six trials; the ledger now has nine. `:356` uses all development dates for DSR sample length, and the DSR call does not receive the holding-period annualization convention | Correct trial accounting, actual scored sample and dependence treatment, and annualization before interpreting the evidence statistic. |
| The short-horizon `BUY_AND_HOLD` baseline at `evaluation.py:326` takes every costed holding-period label | It is a repeated-trade baseline, not a buy-once passive portfolio. Different signs at different horizons do not alone prove different market regimes. |

The newer TimesFM 2.5 report contains positive candidate Sharpe values, so it would be inaccurate to
say every model always loses. Its best reported DSR is **0.394441** using six trials; its card gives
**0.312642** when re-deflated for nine, still below 0.95. These are reported screening statistics,
subject to the measurement issues above, and are not probabilities of winning a trade. The record
does not establish a deployable edge over appropriate simple baselines.

## Concrete repair order

1. **Finish economic accounting end to end.** Represent corporate-action entitlements and dividend
   receivables; carry unknown valuations explicitly; reconcile cash, parent shares, resulting shares,
   paid costs and projected closing costs. Never turn an unknown into zero. Verify the complete
   watch-to-dashboard-to-close journey, including restart and duplicate events.
2. **Make the test and the running strategy identical.** Bind weights, preprocessing, features,
   universe, ranking, holding policy, sizing and fills to a versioned artifact. Display the loaded
   trial and mark timestamp. Replay recorded decisions to demonstrate backtest/paper equivalence.
3. **Repair the evaluator before starting another model campaign.** Use a capital-constrained daily
   portfolio ledger, true matched passive and cash baselines, full-universe selection attribution,
   correct effective costs, and dependence-aware validation. Compare the model against a shuffled
   signal under identical exposure and turnover. Keep all existing trials and failed results counted.
4. **Require a new economic hypothesis to justify new training.** Lower turnover and abstention can
   reduce cost drag, but do not manufacture predictive information. Repeating the same failed search
   or buying more compute has no demonstrated benefit. Predeclare any materially new information,
   candidate, search budget and success/failure criteria before evaluating it.
5. **Keep personal capital out until the evidence changes.** A candidate needs positive net results
   under the corrected validation contract, meaningful improvement over simple baselines, credible
   performance under increased costs and execution delay, and multiple completed paper rebalance
   cycles with exact reconciliation. Apply the existing numeric governance gates; a few green days
   or one favorable backtest is insufficient. No calendar duration alone proves an edge.

The current flagship loss is below its configured 4% daily and 12% total pre-trade drawdown limits;
it is not evidence that a limit was breached. Those controls constrain risk and do not generate
profits or guarantee liquidation on every adverse quote. A separate risk-policy change should be
evaluated against the strategy rather than tightened after observing this one loss.

## Verification and boundaries

- Independent decimal reconstruction reproduced flagship cash/equity/P&L and XS component totals.
- Static call-path inspection confirmed the missing entitlement wiring and report/evaluator issues.
- No new trial, final-holdout evaluation, market-data ingestion, model replacement or runtime book
  mutation was performed. Existing evidence and other agents' changes were preserved.
- The repository Python shim could not launch in this environment (`Access is denied`); the
  diagnostic uses PowerShell decimal arithmetic. No claim of a passing production test suite is made.
- Claims audit and disk-layout audit (`-Fast`) passed. A release or repaired accounting path would
  still need its own regression, integration and independent verification evidence.

The diagnosis is complete. The repair order above is a reviewable follow-on implementation plan;
the production fixes have not been implemented by this task.
