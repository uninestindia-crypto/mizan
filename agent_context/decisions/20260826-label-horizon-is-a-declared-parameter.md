# Decision: the label horizon is a declared parameter, and 2 was below the cost break-even

DATE_UTC: 2026-08-26
DECIDED_BY: Claude Code (Mizan model build), on founder instruction
STATUS: ACCEPTED
SUPERSEDES: nothing. `LABEL_HORIZON_SESSIONS_V1 = 2` remains the default and the existing contract.

## Context

`LABEL_HORIZON_SESSIONS_V1 = 2` was hardcoded into the governed label contract from slice 4 onward.
It counts decision close -> next open (entry) -> following open (exit), so **it is a one-session
hold**, not a two-session one. Every governed trial in this repository -- 101 of them before Mizan --
was evaluated under it.

## The measurement

`scripts/screen_mizan_horizon.py` characterizes the execution contract itself: the unconditional
average return of holding every name for N sessions, against a round trip charged once. This is a
property of the contract, not a strategy search, so no evidence store is written and no multiplicity
ordinal is spent.

Over the cached NIFTY 50 decade, against the measured mean statutory round trip of 0.2225%:

| Sessions held | Mean gross | Gross/Cost | Annualized net |
|---:|---:|---:|---:|
| **1** (the shipped contract) | +0.0758% | **0.34x** | **-30.9%** |
| 2 | +0.1487% | 0.67x | -8.9% |
| 3 | +0.2229% | 1.00x | +0.0% |
| 10 | +0.7448% | 3.35x | +14.0% |

Independently corroborated from the label rows themselves (`scripts/diagnose_mizan_loss.py`): across
108,995 governed labels, mean gross +0.000776 against mean cost +0.002225, with **45 of 45 symbols
gross-positive and 0 of 45 net-positive**.

**The shipped contract was structurally loss-making before any model existed.** Break-even needs
about three sessions held, i.e. a horizon of 4.

Demonstrated rather than argued: retraining Mizan unchanged except for the horizon moved
BUY_AND_HOLD from **-38.8% to +22.0%** on identical data and an identical universe.

## Decision

Make the horizon a parameter carried by the evidence, and leave the default alone.

- `build_label_dataset(..., horizon_sessions=LABEL_HORIZON_SESSIONS_V1)`; entry stays `ordinal + 1`
  and exit becomes `ordinal + horizon_sessions`.
- `build_purged_fold(..., label_horizon_sessions=...)` records it in `FoldSpecV1`, which already had
  the field and always set it to the constant.
- `round_trip_cost_quotes(..., horizon_sessions=...)` prices the same horizon. A mismatch surfaces as
  a typed `COST_QUOTE_MISSING` rather than as a silently mispriced label.
- `validation.py` checks the fold against the label dataset's declared horizon instead of the
  constant.
- `label_contract_version_for(horizon)` returns `next-open-net-return-v1` **verbatim** for the
  default, so every previously built label dataset hashes exactly as before and the 50 published
  schema-v2 models stay reproducible. A different horizon declares itself as
  `next-open-net-return-h{N}-v1`.
- A horizon shorter than `LABEL_HORIZON_SESSIONS_V1` raises `LABEL_HORIZON_INVALID`.

## Rejected alternatives

**Change the default from 2 to 4 or 11.** Rejected. Every prior governed result was measured at 2;
silently moving the default would make 101 published trials incomparable to anything produced
afterwards, and would rewrite what those numbers mean without re-running them. The default is a
historical fact, not a recommendation.

**Add `label_horizon_sessions` to `LabelDatasetV1.metadata_dict()`.** Rejected. It would change the
dataset hash of every label dataset ever built, including the ones bound into published trial
manifests via `RidgeTrialStartV1.dataset_hash`. Encoding the horizon in the contract-version string
achieves the same auditability with no change to existing hashes.

**Leave the horizon hardcoded and treat the loss as a model problem.** Rejected by measurement: every
baseline lost at horizon 2, including BUY_AND_HOLD, which is not a strategy. A contract under which
"always long" loses 38.8% cannot diagnose a model.

## Consequence that must travel with this

Lengthening the horizon makes consecutive decision dates **overlap**, so validation rows stop being
independent observations. Purging and embargo separate train from validation but do not de-overlap
labels *within* validation. Any Sharpe or t-statistic measured at a horizon above 2 is optimistic in
its significance and must be reported as directional only.

## What this did not fix

Mizan at a 10-session hold still lost 31.6% while buy-and-hold earned 22.0%, and the corrected
specification showed a **-0.000022 selection edge (t = -0.07)** against equal-weight on 378
out-of-sample names. The horizon was a real defect in the contract; it was not the reason the model
has no edge.

Records: `agent_context/work/completed/20260825-1500Z-claude-mizan-pooled-model.md`.
