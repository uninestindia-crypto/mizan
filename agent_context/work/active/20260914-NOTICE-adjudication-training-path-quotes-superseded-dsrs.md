# NOTICE: ADJUDICATION-TRAINING-PATH-20260911 quotes short-horizon DSRs that have since been re-scored

STATUS: NOTICE (additive; nothing edited)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-14T18:05:00Z
CONCERNS: `.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md`, section 3
FILER'S RECORD: `20260914-1520Z-claude-short-horizon-multiplicity-rescore.md`

## Why this is a notice and not an edit

**That report was correct on the day it was written and it has not been touched.**

It is a dated adjudication: a record of what an independent adjudicator read out of the results files
on 2026-09-11 and what they concluded from it. Its value rests entirely on being what that agent
actually found at that moment. Rewriting its numbers to today's would not update a report — it would
fabricate an adjudication that never happened, and `.launch/` is where this repository keeps evidence
precisely because it does not get rewritten.

So nothing in it is edited, and this notice exists so a reader who arrives at it from a search result
is not misled.

## What it says, and why it was right

Section 3 reads the short-horizon results and tabulates:

| Hold | Ridge DSR | TimesFM DSR | Noise control DSR |
|---|---:|---:|---:|
| 1 | 0.026515 | 0.023189 | 0.000000 |
| 2 | 0.059283 | 0.004270 | 0.148551 |
| 3 | 0.094711 | 0.191369 | 0.419649 |

and states *"`multiplicity_count = 6` matches `declared_trials = 6` in every arm, so the ledger was
honoured."*

**That was true on 2026-09-11.** The ledger held six SPENT rows on that date. Trials 7-9 (TimesFM
2.5) were declared on **2026-09-12**, the day after — see
`20260912-NOTICE-claude-timesfm25-trials-7-9-declared.md`. The adjudicator checked the count against
the ledger as it then stood and found them consistent, which is exactly the right check.

## What has changed since

On 2026-09-14, on founder instruction, every short-horizon result was re-deflated against the
ledger's current nine SPENT trials. The figures in that table are now the **as-published** values:

| Hold | Ridge | TimesFM 3.0 | Noise control |
|---|---|---|---|
| 1 | 0.026515 -> **0.015569** | 0.023189 -> **0.013464** | 0.000000 -> 0.000000 |
| 2 | 0.059283 -> **0.037419** | 0.004270 -> **0.002182** | 0.148551 -> **0.103240** |
| 3 | 0.094711 -> **0.062647** | 0.191369 -> **0.137089** | 0.419649 -> **0.336002** |

Two consequences for anyone reading that report:

1. **Its verdict is unaffected.** The adjudication's finding — *"the noise control outscores both
   real models at hold 3"*, verdict **PROVEN** — survives the re-scoring intact. Re-deflation is
   rank-preserving, and the count of noise seeds beating each model is identical before and after.
   The adjudicator's conclusion is if anything better supported now.
2. **Its "4.4x gap" and the figure `0.1914` are superseded as *current* values.** At the nine-trial
   basis the hold-3 gap between the noise control and the ridge is 0.336002 against 0.062647, and the
   best real number in that two-arm table is 0.137089. Both still point the same way.

## Two further things that report could not have known

- `run_short_horizon_experiment.py` was still hardcoding `DECLARED_TRIALS = 6` when trials 7-9 were
  published on 2026-09-13, so those three were scored against a six-trial search. Corrected at
  `056fb1c6`, and the constant is now verified against the ledger at run time.
- The evaluator itself was repaired at `056fb1c6`. **Every raw metric that report adjudicated
  predates that repair**, and the re-scoring did not correct them — see
  `20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md`. That is an open
  correction, and it bears on section 3 more than the multiplicity change does.

## Why this matters more than "a stale number in an old report"

**Corrected 2026-09-14, after a peer session (`quant-system-c2`) made the structural point on its own
adjudication.** This section originally ended *"No action is required for safety; nothing in the
repository is wrong as a result of that report existing unchanged."* **That was too strong.**

`agent_context/README.md` ranks `.launch/` **above** reconciled `CURRENT.md`, completed work records
and handoffs in the source-of-truth order. So a reader following that hierarchy *correctly* reaches
this report before reaching any evidence of the re-scoring — and this report states:

> `multiplicity_count = 6` matches `declared_trials = 6` in every arm, so the ledger was honoured.

A reader doing exactly the right thing therefore lands on `6` as the governing budget, in the
highest-ranked source, with nothing in their path telling them otherwise. That is not "nothing
wrong"; it is a superseded number reachable by correct procedure, which is the failure mode this
whole re-scoring exists to close.

Two things bound it, and both are why this is a notice rather than an edit:

- **The verdict is unaffected.** Section 3's finding — *"the noise control outscores both real models
  at hold 3"*, **PROVEN** — survives the re-scoring intact, because re-deflation is rank-preserving.
  Unlike a stale `BLOCKED`, nothing here is a gate that a reader would wrongly stop at.
- **"The ledger was honoured" is true again**, for different values: `multiplicity_count` and
  `declared_trials` are now both `9` in every arm, against a ledger of nine SPENT rows. What is stale
  is the pair of numbers, not the compliance claim.

README's own rule is the one that applies: *"Do not silently choose between conflicting sources.
Record the conflict and resolve it with evidence."* This notice is that record. It does not amend the
report, does not touch its verdict, and does not claim the conflict is harmless.

## For the coordinator

This belongs with `20260826-NOTICE-adjudication-reports-need-recheck.md` as a standing reason to
re-read adjudication reports against current evidence rather than quoting them forward. The concrete
ask: when `.launch/` state is next reconciled, either annotate section 3's basis or record the
supersession where a reader following the hierarchy will meet it.
