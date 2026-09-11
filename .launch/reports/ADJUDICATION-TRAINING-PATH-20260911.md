# Adjudication — governed Mizan retrain and the short-horizon program

ADJUDICATOR: Claude Code (Opus 5), session of 2026-09-11
REVISION_ADJUDICATED: `e9041b7b`
BRIEF: `.launch/ADJUDICATION-BRIEF-TRAINING-PATH.md`
METHOD: every number below was read from the evidence store or the results artifacts directly, with
`EvidenceStore.list_verified` / `scan_integrity`, **never from a work record**. Nothing was re-run;
no multiplicity ordinal was spent.

## Independence — the boundary, stated before any verdict

| Adjudicated here (I did not author) | Explicitly NOT adjudicated (I authored) |
|---|---|
| Governed Mizan retrain `trial_mizan_h11_003` | `src/quant_system/data/corporate_actions.py` |
| The `mizan-v1` evidence store | `reports/mizan_ab_screen/**` — the RAW vs adjusted A/B |
| Short-horizon program: ridge, TimesFM, noise control | `scripts/ingest_all_market_data.py` authority cadence repair |
| | The CI ruff/mypy repair |

**Everything in the right-hand column remains unadjudicated and must be reviewed by someone else.**
Reviewing my own work would void the left-hand column by association. That gap is not closed by this
report and should not be recorded as if it were.

---

## 1. Governed Mizan retrain — CORROBORATED

Claim, from `20260910-1615Z-…-short-horizon-program` item D: *"DONE — `trial_mizan_h11_003`,
ordinal 3, DSR 0.2466, `RESEARCH_ONLY`"*.

Read from `data/evidence/models/mizan-v1`:

| Claim | Store | Verdict |
|---|---|---|
| trial `trial_mizan_h11_003` | `trial_id = trial_mizan_h11_003` on `model_3d6f77bf36d36ff0ff7a454c` | **PROVEN** |
| ordinal 3 | `multiplicity_count = 3` | **PROVEN** |
| DSR 0.2466 | `deflated_sharpe_ratio = 0.246621454462` | **PROVEN** |
| `RESEARCH_ONLY` | `verdict = RESEARCH_ONLY` | **PROVEN** |
| nothing promotable | 3 models at ordinals 1, 2, 3; DSRs `0.000903`, `0.175990`, `0.246622`; gate `0.95` | **PROVEN** |

Store integrity: `scan_integrity()` returns **9 valid, 0 invalid, 0 orphan blobs**. Ordinals are
1, 2, 3 — one model each, with no gaps, which independently corroborates the multiplicity count.

### The headline understates how badly the candidate does

`strategy_reports` for `h11_003`, read from the manifest:

| Strategy | Sharpe | Accuracy | Trades |
|---|---:|---:|---:|
| **RIDGE (the candidate)** | **0.1672** | 0.4843 | 3,080 |
| NO_TRADE | 0.0000 | 0.4895 | 0 |
| BUY_AND_HOLD | **1.4037** | 0.5105 | 10,714 |
| PREVIOUS_SIGN | **1.6312** | 0.4957 | 5,394 |
| EQUITY_DUAL_MOMENTUM | -0.2724 | 0.4808 | 4,824 |

The candidate is **fourth of five**. Buy-and-hold beats it 8.4x on Sharpe; repeat-the-previous-sign,
which requires no model at all, beats it 9.8x. Its accuracy (48.4%) is **below not trading** (49.0%)
while it takes 3,080 positions. "Fails the gate" is true and far too gentle: it is beaten by every
non-trivial baseline on the board.

---

## 2. What the retrain evidence does NOT establish — the material finding

Item D's claim is not merely "a retrain ran"; it is *"on consistent features/labels/P&L"* — i.e. on
corporate-action-adjusted data. **That part cannot be verified from the published evidence.**

Three independent observations, each checked:

**(a) The MODEL manifest records no adjustment.** Its complete metadata key set is
`candidate_id, deflated_sharpe_ratio, evaluation_hash, feature_schema_id, feature_schema_version,
fitted_state, fold_spec_hash, model_id, multiplicity_count, preprocessing, strategy_reports,
trial_id, verdict`. There is no adjustment field, method, or authority reference.

**(b) The dataset binding does not resolve.** The TRIAL records carry `dataset_id` / `dataset_hash`:

```
trial_mizan_001      -> dset_ec9755fc707c256ce8fce27b
trial_mizan_h11_002  -> dset_d028c817188a2c39188da046
trial_mizan_h11_003  -> dset_b48a93253fabe3209621673b
```

A recursive search of `data/` finds **none of the three**. `models/mizan-v1/datasets/` is empty and
the store reports **0 DATASET resources**.

This is **systemic, not a mizan defect** — checked, and no model store publishes datasets:

```
mizan-v1                                          MODEL=3   TRIAL=6    DATASET=0
nifty50-…-schema-v2                               MODEL=50  TRIAL=100  DATASET=0
nifty50-…-schema-v2-source-bound                  MODEL=12  TRIAL=25   DATASET=0
nifty50-…-schema-v2-source-bound-v2               MODEL=50  TRIAL=100  DATASET=0
```

**(c) The feature schema does not distinguish adjusted from unadjusted.** All three models carry
`quantos.mizan_crosssectional_fifteen` **version 1** — including `trial_mizan_001`, which predates
the adjustment work, and `h11_003`, which is claimed to postdate it.

### What this does and does not mean

**It is not evidence that the retrain used the wrong data.** The three `dataset_hash` values are
*distinct*, which proves the inputs genuinely differed between trials, and the hash remains
tamper-evident: a re-run on different data would produce a different hash and be detectable.

**What is absent is auditability, not integrity.** Nothing in the published evidence records *what*
the difference was. A reader cannot confirm from the evidence that `h11_003` consumed
corporate-action-adjusted bars rather than some other change — and since `feature_schema_version`
is identical across the boundary, the schema cannot be used to infer it either.

**Verdict: `NOT TESTED`.** The DSR and verdict are PROVEN; the "on consistent features/labels/P&L"
clause is unverifiable from evidence and rests on the author's word.

**This is the same defect class the whole 2026-09-10 corporate-action effort existed to remove** —
evidence that does not record what it was computed from. It was fixed at the `DatasetManifest`
layer (item C) and does not propagate to the MODEL manifest a promoter would actually read.

---

## 3. Short-horizon program — CORROBORATED, and the negative is stronger than claimed

Claim: *"all 6 trials spent; neither model has an edge; noise control shows the DSR rewarded
exposure"*. Read from `reports/short_horizon/results-{ridge,timesfm,noise-control}.json`:

| Hold | Ridge DSR | TimesFM DSR | **Noise control DSR** | Gate |
|---|---:|---:|---:|---:|
| 1 | 0.026515 | 0.023189 | 0.000000 | 0.95 |
| 2 | 0.059283 | 0.004270 | **0.148551** | 0.95 |
| 3 | 0.094711 | 0.191369 | **0.419649** | 0.95 |

`gate_passed = False` on all nine. `multiplicity_count = 6` matches `declared_trials = 6` in every
arm, so the ledger was honoured.

**The noise control outscores both real models at hold 3, and outscores ridge at hold 2.** A
random-prediction arm scoring `0.4197` against the real model's `0.0947` is a 4.4x gap in favour of
noise. That is a decisive result and the control is what makes it decisive: without it, TimesFM's
`0.191369` at hold 3 — the best real number in the table — could have been read as a faint signal.
It is not. It is less than half of what randomness scored on the same metric, same folds, same data.

**Verdict: PROVEN, and I would state it more strongly than the record does.** At these horizons the
deflated Sharpe is rewarding exposure rather than skill, so the metric cannot distinguish either
model from noise. This is good experimental design — the control was declared in the frozen ledger
and it did its job.

**The TimesFM question is answered.** `google/timesfm-3.0-pytorch` zero-shot does not beat a simple
ridge here, and neither beats randomness on the headline metric.

### Provenance contrast worth recording

The short-horizon artifacts bind their inputs properly — `feature_store` path,
`corporate_action_authority_sha256`, `code_revision` (honestly marked `-dirty`), `noise_seed`,
`holdout_sessions`, `embargoed_rows`, `abstention_calibrated_on = walk-forward validation folds
(holdout untouched)`.

**The ungoverned research artifacts have materially better provenance than the governed evidence
store.** That inversion is worth fixing at the governed end rather than celebrating at the research
end.

---

## 4. Verdict

| Claim | Verdict |
|---|---|
| `h11_003` DSR 0.2466, ordinal 3, RESEARCH_ONLY | **PROVEN** |
| Nothing promotable in `mizan-v1` | **PROVEN** |
| `mizan-v1` store integrity | **PROVEN** — 9 valid, 0 invalid, 0 orphans |
| Retrain ran "on consistent features/labels/P&L" | **NOT TESTED** — dataset binding unresolvable, no adjustment field, schema version unchanged |
| Short-horizon: 6 trials, ledger honoured, all fail gate | **PROVEN** |
| Neither QuantOS ridge nor TimesFM has an edge | **PROVEN** — and both are beaten by the noise control |

**No claim adjudicated here was DISPROVEN.** The single material gap is auditability of the governed
retrain's inputs, and it is a provenance gap rather than a correctness finding.

## 5. What remains unadjudicated

1. **My own work** — the corporate-action adjustment, the A/B, the ingest cadence repair, the CI
   repair. Needs a different adjudicator.
2. **Brief Q5** — the brief author's own contributions (`promotion_pipeline.py`,
   `run_governed_promotion.py`, `holdout.py`, `stress.py`, `ledger.py`), review requested
   2026-08-25 and still outstanding. I am independent of these and did **not** reach them here.
3. **Brief Q3** — point-in-time honesty of the cache against the provider. An intact store proves
   nothing was altered after publication, not that publication was correct.
4. **Determinism beyond one instrument** — the four canaries cover one instrument and never visit a
   failure path.

## 6. Recommendation

**Propagate adjustment provenance into the MODEL manifest**, or publish the DATASET resource the
trial binds to. Today a promoter reading model evidence cannot tell whether the model in front of it
was fitted on adjusted or raw bars, and `feature_schema_version` will not tell them either. Nothing
is promotable right now, so the cost of fixing it is low and the window is open.
