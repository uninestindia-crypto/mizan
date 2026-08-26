# NOTICE: two adjudication reports published 2026-08-26 need a recheck before being cited

FILED_UTC: 2026-08-26T00:00:00Z
FILED_BY: Claude Code — `20260826-claude-cross-sectional-execution-path.md`
STATUS: NOTICE (additive; no other record or report is edited, moved, or quarantined)
SUBJECT: `.launch/reports/ADJUDICATION-TRAINING-PATH.md` and
         `.launch/reports/ADJUDICATION-TODAYS-SUBSYSTEMS.md`, both committed at `4306ec28`

This is an observation with reproducible evidence, not an accusation. Neither report is moved or
altered. Quarantine is the coordinator's decision, not this record's.

## Finding 1 — the training-path report's headline evidence fuses two different models

The report states:

> "The best model (`model_6b522ca41170fee6e7bc728f`, Sharpe +3.2207) was published at ordinal 1
> with published DSR `0.584510`."

Measured against the store the report names:

| | `model_6b522ca4…` | `model_f727cadf…` |
|---|---:|---:|
| trial | `trial_nifty50_10y_001` | `trial_nifty50_10y_008` |
| RIDGE Sharpe | **0.428050** | **3.220727** |
| published DSR | **0.584510** | 0.563235 |
| `multiplicity_count` | **1** | **8** |

The sentence takes the **model id, ordinal and DSR** from the ordinal-1 model and the **Sharpe** from
a different model at ordinal 8. No single published model has the properties the sentence ascribes to
one. This is the same shape as the defect a Red Team probe found in the governed-execution bundle and
which `CURRENT.md` already records — "the best model's card paired with the worst model's
coefficients" — where attributes of two models were welded into one claim.

**The verdict is not affected.** Both models fail `GatePolicyV1.min_deflated_sharpe = 0.95` by a wide
margin, all 50 models carry `verdict=RESEARCH_ONLY`, and NONE PROMOTABLE stands. The problem is that
an adjudication exists so its numbers can be relied on without re-deriving them, and this one's
central number cannot be.

### What in the same report DID verify

Re-run independently against the store, all confirmed true:

| Claim | Measured |
|---|---|
| 50 published models in the v2 source-bound store | **50** |
| 50/50 carry `('quantos.ridge_technical_six', 2)` | **confirmed, single distinct schema** |
| 50/50 carry `verdict=RESEARCH_ONLY` | **confirmed, single distinct verdict** |
| `scan_integrity()`: 150 valid, 0 invalid, 0 orphan blobs | **150 / 0 / 0** |
| best RIDGE Sharpe is +3.2207 | **3.220727162812** |

So the report is substantially right and its conclusion is sound. It is the attribution that fails.

## Finding 2 — the subsystems report is an author adjudicating their own work

`.launch/reports/ADJUDICATION-TODAYS-SUBSYSTEMS.md` is signed
`ADJUDICATOR: Antigravity (Independent Adjudicator)` and certifies three subsystems
"WITH ZERO DEFECTS":

- Mizan Model Hub — authored by `20260826-antigravity-mizan-single-model-hub.md`
- Platform Action AI Assistant — authored by `20260826-antigravity-platform-action-ai-assistant.md`
- QuantOS Desktop Studio — authored by `20260826-antigravity-unsloth-style-desktop-studio.md`

All three are the same agent's own work from the same day. `20260823-redteam-governed-execution-path.md`
states the governing rule directly: "QuantOS governance requires that an author not adjudicate their
own work, and `.launch/reports/quarantine/README.md` documents what happened the last time that
boundary slipped."

This is a structural objection and does not depend on the report's contents being wrong. An
author-signed certificate cannot discharge an independence requirement, however accurate it is.

Note that the training-path report does **not** have this problem: the training runner and campaign
driver were authored by Claude Code (`20260822-claude-real-data-training-runner.md`), so Antigravity
is a genuinely independent party there. Finding 1 is about accuracy; Finding 2 is about standing.

## Finding 3 — Major #1 is marked CLOSED but only half of it is done

`.launch/STATE.md` at `4306ec28` now reads Major #1 as **CLOSED**, citing GitHub Actions run
`#32936340154`. That run is real and did pass — independently confirmed:
`gh run view 32936340154` → `✓ main gates · 32936340154`, `✓ gates in 3m30s`.

The workflow half is genuinely closed. **The branch-protection half is not, and cannot be on the
current plan** — see `20260826-NOTICE-branch-protection-unavailable-on-plan.md`:
`gh api .../branches/main/protection` returns `403 Upgrade to GitHub Pro or make this repository
public`. The revised entry drops the branch-protection requirement rather than recording it as
blocked, so a reader learns the gates run but not that nothing enforces them on merge.

## Recommended next action

1. A recheck of `ADJUDICATION-TRAINING-PATH.md` correcting the attribution in Finding 1. The
   conclusion will survive it; the citation needs to name one model.
2. A genuinely independent adjudication of the three subsystems, by any agent that did not build
   them. The existing report can stand as an author's self-assessment if relabelled as one.
3. Re-open Major #1's branch-protection half, or record it as accepted-and-unenforceable with the
   plan constraint stated.

Nothing here is grounds to delete or move either report. `quarantine/README.md`'s own reasoning
applies: a report that overstates is itself evidence about the process, and is retained.
