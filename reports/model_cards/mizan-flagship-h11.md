# Model card — Mizan flagship, pooled cross-sectional ridge (h11)

## Identity

| | |
|---|---|
| Model | `model_3d6f77bf36d36ff0ff7a454c` |
| Trial | `trial_mizan_h11_003` |
| Candidate | `cand_mizan_v1` |
| Evidence store | `data/evidence/models/mizan-v1` |
| Feature schema | `quantos.mizan_crosssectional_fifteen` **v1** |
| Multiplicity ordinal | **3** of 3 |
| Verdict | **`RESEARCH_ONLY`** |

## What it is

A pooled cross-sectional ridge over 15 features, predicting an 11-session-horizon direction, long
only, with the score threshold set to the **training partition base rate** (train-only information).

```text
return_1, return_5, return_21, garman_klass_volatility, parkinson_volatility,
rsi_14_centered, sma_20_distance, sma_50_distance, volume_zscore,
money_flow_multiplier, india_vix_level, india_vix_change_5, nifty_return_5,
cs_rank_momentum_5, cs_rank_volume_surprise
```

Preprocessing is fitted on the training partition only. Folds are purged and embargoed.

## Results — the candidate is fourth of five

Read from the published manifest, not from a work record. 10,714 attributable decisions.

| Strategy | Sharpe | Accuracy | Exposure | Max DD |
|---|---:|---:|---:|---:|
| **RIDGE (the candidate)** | **0.1672** | 0.4843 | 0.7143 | 0.7229 |
| NO_TRADE | 0.0000 | 0.4895 | 0.0000 | 0.0000 |
| BUY_AND_HOLD | **1.4037** | 0.5105 | 1.0000 | 0.6607 |
| PREVIOUS_SIGN | **1.6312** | 0.4957 | 1.0000 | 0.6499 |
| EQUITY_DUAL_MOMENTUM | -0.2724 | 0.4808 | 0.9960 | 0.7543 |

**Deflated Sharpe `0.246621454462` against a `0.95` gate — FAILS.**

The three trials in this store scored `0.000903`, `0.175990`, `0.246622` at ordinals 1, 2, 3.

### Stated plainly, because "fails the gate" is too gentle

The candidate is beaten by **buy-and-hold** (8.4x on Sharpe) and by **repeat-the-previous-sign**
(9.8x), a rule that requires no model at all. Its accuracy of **48.4% is below the 49.0% obtained by
not trading**, while it takes 3,080 positions to get there. It is fourth of five on the board.

## Reproduce

```bash
.venv/Scripts/python.exe scripts/train_mizan.py --horizon-sessions 11 --multiplicity-ordinal 4
```

**Do not run that command to "check" this result.** It would spend multiplicity ordinal 4 and
deflate every future candidate harder, to reproduce a null already established. To *read* the
published evidence instead, which spends nothing:

```bash
.venv/Scripts/python.exe -c "import json,glob; [print(json.load(open(p,encoding='utf-8'))['metadata'].get('deflated_sharpe_ratio')) for p in glob.glob('data/evidence/models/mizan-v1/models/*/manifest.json')]"
```

## Known failures and limitations

- **The "trained on corporate-action-adjusted data" claim is `NOT TESTED`.** Independently
  adjudicated at `.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md`: the model manifest carries
  no adjustment field, `feature_schema_version` is identical across the adjustment boundary, and the
  trial's `dataset_id` (`dset_b48a93253fabe3209621673b`) **does not resolve** — no evidence store in
  this repository publishes DATASET resources. The three trials' dataset hashes are distinct, which
  proves the inputs differed; nothing published records *how*. This is an auditability gap, not a
  correctness finding, and it is the single material gap the adjudication found.
- **Why the binding cannot resolve is now measured, and it is not a missing call.** Publishing was
  attempted (`--publish-datasets-only`, which spends no ordinal) and the store **refuses** both
  datasets: the feature dataset's canonical evidence is 115,934,341 B against a 100 MiB limit, and
  the label dataset's canonical *metadata* is 6,948,398 B against a 1 MiB limit. The metadata field
  `cost_quote_hashes` holds one already-deduplicated hash per row — NSE statutory costs are dated, so
  distinct quotes really are ~1 per row — which makes label metadata **O(rows) against a fixed cap**,
  capping any publishable pooled label dataset at roughly 15,000 rows. Closing this needs a contract
  change under a claimed path; filed as
  `agent_context/work/active/20260911-NOTICE-governed-datasets-exceed-store-limits.md`.
- **Correcting the corporate-action data does not rescue this model.** Measured A/B: selection edge
  `-0.000022` (raw) vs `-0.000185` (adjusted), neither significant. No signal was being masked.
- Store integrity is clean: 9 valid resources, 0 invalid, 0 orphan blobs.
- The paper book running this candidate is below cash — decomposed below.

## The paper book running this candidate — marked 2026-09-11

Four-way decomposition, marked on the book's own recorded per-name marks from
`logs/paper_runs/live_paper_status.json`. The same source prices the book and its benchmark, so any
staleness in a quote moves both sides identically and cancels in the difference.

| | Amount (INR) |
|---|---:|
| Entry consideration (97 positions) | 853,407.04 |
| Marked value | 840,749.87 |
| **Gross P&L** | **-12,657.17** |
| Paid costs (lifetime fees, already out of cash) | 1,072.65 |
| Prospective exit costs (accrued, unpaid) | 1,883.28 |
| **Net P&L** | **-15,613.10** |
| Matched benchmark, net (equal-weight, same 97 names) | -15,155.72 |
| **Excess over benchmark** | **-457.38** |
| Cash alternative | **0.00** |

**Cash beat it**: -15,613.10 against 0.00. Against its own equal-weight basket it trails by 457.38
on 853,407 of notional — about **0.054%**. That is not evidence of negative skill; it is evidence of
*no measurable* skill over this window.

**Window caveat that must travel with these numbers.** The book opened 2026-08-31 against a declared
10-session hold and has not completed a full holding period. And the benchmark holds the book's own
97 names, so it isolates *weighting* and says nothing about *selection* — a book that picked 97 poor
names from the eligible universe would track its own basket closely and still have chosen badly.
Testing selection needs point-in-time universe membership at each rebalance, which is not measured
here.

Both books are live, so this is a snapshot, not a constant. Re-run:

```bash
.venv/Scripts/python.exe scripts/reevaluate_paper_books.py
```

## Must not be used for

Live-money routing, promotion, or any claim of edge. It is auditable historical research evidence.
