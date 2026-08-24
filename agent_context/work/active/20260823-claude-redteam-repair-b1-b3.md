# Repair: Red Team Blockers 1 and 3 (governed execution path)

STATUS: REPAIRED — awaiting independent recheck  
OWNER: Claude Code — author of the defective code, acting as repair agent  
TOOL: Claude Code  
STARTED_UTC: 2026-08-23T03:00:00Z  
STARTING_REVISION: `1e5beb5`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Provenance of these findings

The Red Team agent terminated on a session limit before writing its report, so there is no
independent severity assignment. It left 19 executable probes under `tmp/redteam-governed-exec/`.
Running them produced the raw output below. **Severities here are the author's own reading of that
output, not an adjudicator's verdict.** That distinction must survive into any later citation.

## Blocker 1 — a bundle accepts artefacts from a different model

Probe: `tmp/redteam-governed-exec/probe_bundle_swap.py`

```
card model   : model_b0e4e7dc4c30e2ca534b1e6c trial=trial_uni_018 DSR=0.696672616037
artefacts    : model_0435fe025404aa7b44d6f2fd trial=trial_uni_043 DSR=0.000009669974
same candidate_id: True (cand_ridge_v1)
BUNDLE ACCEPTED. reported model_id: model_b0e4e7dc4c30e2ca534b1e6c
actual fitted_state_hash: 6da3096d7faa9e94 (belongs to model_0435fe025404aa7b44d6f2fd)
score_threshold accepted: -9.99 (validated value was -0.13382 for trial_uni_018)
```

**Where my reasoning failed.** Design decision D5 in
`20260822-claude-governed-execution-adapter.md` argued that a `model_card_hash` re-derivation check
would be "theatre" because `ModelCardV1.__post_init__` recomputes that hash from its own fields. That
is true and irrelevant. The question is not whether the card is internally consistent; it is whether
anything binds the **card** to the **fitted state**, and nothing did. `candidate_id` was doing that
job, and it cannot: every model in the 51-trial campaign shares `candidate_id = "cand_ridge_v1"`, so
the check passes for any pairing. A bundle could therefore report the best model's identity while
executing the worst model's coefficients, at a threshold from neither.

## Blocker 3 — the adapter's scorer disagrees with the validated scorer

Probe: `tmp/redteam-governed-exec/probe_score.py`

```
adapter _score (exact Decimal): -0.133819999999600000021144033953
predict_ridge_scores         : -0.13382   <- 12-decimal rounded
difference                   : 4.0E-13
threshold                    : -0.13382
validation rule  score > threshold : False -> DOWN (no return recorded)
adapter rule     score > threshold : True  -> BUY
DISAGREE: True
```

`_score` reimplemented scoring in Decimal for "exact reconciliation". `predict_ridge_scores` rounds
to 12 decimals. At the threshold boundary the two disagree on the sign of the decision, so the
adapter trades where validation recorded nothing — the executing system diverging from the validated
one, which is the defect this adapter exists to remove.

## Owned paths

- `src/quant_system/execution/governed_strategy.py`
- `scripts/run_governed_shadow_session.py`
- `tests/test_governed_bundle_binding.py` (new)
- `agent_context/work/active/20260823-claude-redteam-repair-b1-b3.md` (this file)

## Non-goals

- Blocker 2 (window-length feature divergence) — needs a founder design decision.
- Majors 4-9 — separate repair, after these two.
- Declaring anything closed. The author repairing defects the author introduced, verified by tests
  the author writes, is the same closed loop the Red Team exists to break. These repairs need an
  independent recheck.

## Repair design

**B1.** Introduce `ModelEvidenceIdentityV1`, built from one published model manifest, carrying
`model_id`, `candidate_id`, `trial_id`, `fitted_state_hash`, `preprocessing_state_hash` and the
validated `score_threshold`. `PromotedModelBundleV1` requires it and verifies every part against the
card, the fitted state, the standardization and the threshold. Forging a pairing now requires forging
the identity record too, and the factory derives that from a single manifest.

**B3.** Delete `_score` and call `predict_ridge_scores`, so the executing scorer *is* the validated
scorer by construction rather than by argument.

## Plan

1. COMPLETE — reproduce both, this record.
2. Failing-first regressions in `tests/test_governed_bundle_binding.py`.
3. Repair.
4. Gate.

## Current step

All four steps complete.

## Verification

| Check | Result |
|---|---|
| Regressions written first | `tests/test_governed_bundle_binding.py` failed on import before the repair (`cannot import name 'ModelEvidenceIdentityV1'`), 8 pass after |
| Red Team probe `probe_bundle_swap.py` | no longer constructs: `PromotedModelBundleV1.__init__() missing 1 required positional argument: 'evidence'` |
| Red Team probe `probe_score.py` | no longer imports: `_score` is gone; the parallel scorer no longer exists |
| **Both attacks re-run on REAL evidence** | refused, see below |
| `pytest` over 6 affected suites | 98 passed |
| Ruff, strict mypy | clean; 121 source files |
| `run_governed_shadow_session.py` on the real store | still refuses `RESEARCH_ONLY`, unchanged |

Re-running the swap on the real campaign store, best model against worst:

```
good model : model_b0e4e7dc4c30e2ca534b1e6c DSR 0.696672616037
bad  model : model_da7de44d07cb814ba97e4596 DSR 0.000000000001
same candidate_id: True (cand_ridge_v1)

ATTACK REFUSED: fitted state does not match the model evidence; these coefficients
                were not published by 'model_b0e4e7dc4c30e2ca534b1e6c'
THRESHOLD ATTACK REFUSED: score_threshold '-9.99' is not the value trial
                'trial_uni_018' was validated at ('-0.13382')
```

A probe failing with `TypeError` proves only that the API changed. The refusals above, on the same
real artefacts the Red Team used, are what proves the attack is caught rather than merely relocated.

## Files changed

- `src/quant_system/execution/governed_strategy.py`: `ModelEvidenceIdentityV1` added and required on
  the bundle; `_score` replaced by `score_row`, which calls `predict_ridge_scores`.
- `scripts/run_governed_shadow_session.py`: derives the identity from the same manifest.
- `tests/test_governed_bundle_binding.py`: new, 8 cases.
- `tests/test_governed_strategy.py`, `tests/test_governed_shadow_wiring.py`: helpers construct a
  bound identity. No assertion was weakened; the two direct-construction cases still test what they
  tested.

## Not closed

- **Blocker 2** (window-length feature divergence) — awaiting a founder design decision.
- **Majors 4-9** — untouched.
- **These repairs are unadjudicated.** Author-repaired, author-tested. The Red Team that found the
  defects never finished, so nothing here has been independently rechecked.
