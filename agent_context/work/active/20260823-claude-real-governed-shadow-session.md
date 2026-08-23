# Active work: attempt a real governed shadow session

STATUS: COMPLETE — attempted; refused at the promotion gate as predicted  
OWNER: Claude Code — real governed shadow session  
TOOL: Claude Code  
STARTED_UTC: 2026-08-23T01:00:00Z  
STARTING_REVISION: `9470d97`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout)

## Objective

Turn the three governed execution pieces — adapter, bar history, maturity horizon — from *tested*
into *demonstrated*, by driving them from a **real** model in the **real** evidence store rather
than from fixture acquisitions. Whatever stops it, record that verbatim.

## Owned paths

- `scripts/run_governed_shadow_session.py` (new)
- `agent_context/work/active/20260823-claude-real-governed-shadow-session.md` (this file)

## Non-goals

- Fabricating a promotion verdict to get past the gate. If the gate refuses, the refusal **is** the
  result. `.launch/reports/quarantine/README.md` records what fabricated evidence has already cost
  this project.
- Editing `execution/**` or `modeling/**` further. This exercises them; it does not change them.
- Declaring anything certified.

## What the evidence store actually holds

Verified at `9470d97` against `tmp/real-training-evidence`, which carries the 51 real trials from
the NIFTY 50 campaign:

| Bundle input | Present? |
|---|---|
| `fitted_state` (intercept, coefficients, `preprocessing_state_hash`) | YES, in the model manifest metadata |
| `preprocessing` (means, scales, `state_hash`) | YES |
| `score_threshold` | YES, on the trial start record |
| **executable verdict** | **NO — every published model is `RESEARCH_ONLY`** |

## Expected outcome, predicted before running

`PromotedModelBundleV1` refuses `RESEARCH_ONLY` on every surface, so the run should stop at the
promotion gate. That is not a defect in the wiring; it is the gate doing its job. Nothing in the
campaign is promotable — best campaign DSR `0.397794` against a `0.95` requirement.

Recording the prediction before running so the outcome cannot be quietly reinterpreted after the
fact.

## Plan

1. COMPLETE — confirm what the store holds; this record.
2. Write `scripts/run_governed_shadow_session.py`, reconstructing real artefacts from real evidence.
3. Run it. Record the outcome verbatim.

## Current step

All three steps complete.

## Commands and outcomes

`uv run python scripts/run_governed_shadow_session.py` — exit 3. Verbatim:

```
evidence store                    : tmp/real-training-evidence
published models                  : 40
selected model                    : model_b0e4e7dc4c30e2ca534b1e6c (trial trial_uni_018)
verdict in evidence               : RESEARCH_ONLY
published DSR                     : 0.696672616037
score_threshold                   : -0.13382 (from the trial start, not a default)
fitted state                      : intercept=-0.133819951338 hash=64969ae663e261d0...
preprocessing                     : state_hash=51a4f7746a546332...
binding                           : OK

REFUSED BY THE PROMOTION GATE
  model_id            : model_b0e4e7dc4c30e2ca534b1e6c
  trial_id            : trial_uni_018
  verdict in evidence : RESEARCH_ONLY
  deflated_sharpe     : 0.696672616037
  multiplicity_count  : 18
  refusal             : verdict RESEARCH_ONLY is not executable on any surface
```

The prediction recorded before running was that the gate would refuse. It did.

### What ran, and therefore is now demonstrated rather than asserted

Everything up to the gate executed against real published evidence, not fixtures:

1. **Real artefacts reconstruct.** `RidgeFittedStateV1` and `StandardizationStateV1` were rebuilt
   from a real model manifest and both passed their own `__post_init__` validation.
2. **The integrity binding holds on real evidence.** `binding: OK` is
   `fitted.preprocessing_state_hash == standardization.state_hash` — the check the adapter refuses
   on — verified against artefacts a real trial published, not a constructor call in a test.
3. **The validated decision rule is recoverable.** `score_threshold = -0.13382` came off the trial
   start record, so execution would use the rule the model was scored under.
4. **The gate refuses.** GRASIM is the strongest of the 40 published models, chosen deliberately so
   the refusal is the strongest available statement: if this one cannot execute, none can.

### An unplanned confirmation

The fitted intercept is `-0.133819951338` and the threshold is `-0.13382`. They agree to five
decimals. That is the campaign's pre-declared rule — threshold = the training-partition base rate —
showing up in real published evidence, and it is independent corroboration of design decision D3 in
`20260822-claude-governed-execution-adapter.md`: with `+1/-1` targets the ridge intercept *is* the
base rate, so a zero threshold could never fire on a DOWN-skewed name.

## Files changed

- `scripts/run_governed_shadow_session.py`: new.

## Stop point

**No governed shadow session ran, and none can, because nothing in the store is promotable.** Best
campaign DSR is `0.397794` re-deflated against all 51 attempts, against a `0.95` requirement.

Two blockers stand between here and a live governed session, in order:

1. **Promotion.** A model must pass `evaluate_promotion` against its gate policy. None does. This is
   not a wiring problem and cannot be fixed by wiring.
2. **A live feed and market hours.** Even a promoted model needs both. The script stops rather than
   implying it ran a session it did not.

## Next safe action

Nothing here is worth another sweep. If the ridge family is to be pursued, change something real —
instrument set, horizon, or feature family — and treat it as a new campaign in a fresh store. The
execution path is now ready for a promoted model whenever one legitimately exists.

## Blockers and conflicts

None for the owned paths.

