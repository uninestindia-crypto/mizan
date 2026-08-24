# Repair: Red Team Blockers 1 and 3, then Majors 4-9 (governed execution path)

STATUS: REPAIRED (B1, B3, M4-M9) — awaiting independent recheck
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
- `src/quant_system/execution/maturity.py`
- `src/quant_system/execution/realtime_shadow.py`
- `scripts/run_governed_shadow_session.py`
- `tests/test_governed_bundle_binding.py` (new)
- `tests/test_governed_execution_majors.py` (new)
- `tests/test_governed_shadow_wiring.py`
- `tests/test_governed_strategy.py`
- `tests/test_maturity_horizon.py`
- `agent_context/work/completed/20260823-claude-redteam-repair-b1-b3.md` (this file)
- `agent_context/handoffs/20260824-governed-execution-majors-4-9-recheck.md`

## Non-goals

- Blocker 2 (window-length feature divergence) — needs a founder design decision.
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

1. REPRODUCED — B1/B3 raw evidence recorded.
2. IMPLEMENTED — failing-first B1/B3 regressions and repairs.
3. REPRODUCED — Majors 4-9 with failing-first regressions.
4. IMPLEMENTED — Majors 4-9 repairs and local gates.
5. AWAITING — independent Red Team recheck.

## Current step

Repair and local checks performed; independent recheck remains.

## Verification

| Check | Result |
|---|---|
| Regressions written first | `tests/test_governed_bundle_binding.py` failed on import before the repair (`cannot import name 'ModelEvidenceIdentityV1'`), 8 pass after |
| Red Team probe `probe_bundle_swap.py` | no longer constructs: `PromotedModelBundleV1.__init__() missing 1 required positional argument: 'evidence'` |
| Red Team probe `probe_score.py` | no longer imports: `_score` is gone; the parallel scorer no longer exists |
| **Both attacks re-run on REAL evidence** | refused, see below |
| `pytest` over 6 affected suites | 98 passed |
| Ruff, strict mypy | clean; 121 source files |
| `run_governed_shadow_session.py` on the real store | verified 40 models, derived `GRASIM` from the selected model's published decisions, then refused `RESEARCH_ONLY` with exit 3; no session ran |

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
- `scripts/run_governed_shadow_session.py`: uses verified evidence-store reads, derives the single
  bound symbol from the selected model's published decisions, and supplies it to the identity.
- `tests/test_governed_bundle_binding.py`: new, 8 cases.
- `tests/test_governed_strategy.py`, `tests/test_governed_shadow_wiring.py`: helpers construct a
  bound identity. No assertion was weakened; the two direct-construction cases still test what they
  tested.

## Majors 4-9 — repaired

Failing-first: 15 of the initial 17 cases in `tests/test_governed_execution_majors.py` failed before
the repairs. A public `run_session()` maturity-halt case was added during final review; all 18 pass.

| # | Defect | Repair |
|---|---|---|
| 4 | An INFY-fitted model emitted BUY for `RELIANCE` and `TOTALLY_MADE_UP` | `ModelEvidenceIdentityV1` carries `symbol`; the strategy refuses any other instrument. The governed dataset contract is single-instrument, so a model applied to another price series has no meaning |
| 5 | `None`/`str`/`int` history raised `TypeError`/`AttributeError` | `_require_bar_sequence` raises `GovernedExecutionError`. An **empty** sequence stays a legal no-signal: served-nothing is a real outcome, malformed is not, and they must not collapse |
| 6 | `MaturityPolicyError` escaped `run_session`; state RUNNING, no halt reason, decision lost, no audit | Caught and halted as `MATURITY_UNRESOLVABLE`; the audit survives. The halt detail carries no outcome figures, and a test asserts they are absent |
| 7 | Pre-open entry 09:05 matured 09:15 the same morning, held 10 minutes | Entry session is now the first session whose `close_at >= entry_time` — the session actually held through. Plus a coverage floor so an entry predating the calendar fails closed instead of silently resolving to session 0 |
| 8 | Duplicate exchange dates silently changed feature values | Refused at the adapter boundary, matching training's `RECORD_ORDER_INVALID` |
| 9 | A held position was invisible in the audit | `open_entries` and `open_symbols` on `ShadowAuditReport`, **defaulted** so the addition is additive and no existing caller breaks |

Red Team probes re-run against the repaired code:

```
probe_symbol        : GovernedExecutionError: this model was fitted on 'INFY' and cannot score 'RELIANCE'
probe_failopen      : None/str/int/dict -> GovernedExecutionError (was TypeError/AttributeError)
                      empty tuple -> [] (SILENT), deliberately unchanged
probe_preopen       : held 3 days 0:10:00, same calendar day? False  (was 10 minutes, same day)
probe_maturity_crash: run_session returned SHADOW_HALTED MATURITY_UNRESOLVABLE  (was an unhandled escape)
probe_open_entry_invisible: fields mentioning open exposure: ['open_entries', 'open_symbols']  (was [])
```

The real evidence runner initially exposed a missed caller after the symbol field was added. That
caller now obtains the symbol from the verified model decisions rather than accepting a CLI value.
Against `tmp/real-training-evidence` it reported:

```
published models                  : 40
selected model                    : model_b0e4e7dc4c30e2ca534b1e6c (trial trial_uni_018)
model symbol                      : GRASIM (from verified published decisions)
REFUSED BY THE PROMOTION GATE
  verdict in evidence : RESEARCH_ONLY
SCRIPT_EXIT=3
```

No session or order ran.

`probe_duplicates` still shows `compute_feature_values` producing different values for overlapping
bars. That is expected and is **not** a remaining hole: the probe calls the kernel directly, and the
kernel behaves identically for training. The guard sits at the adapter boundary, where execution
enters, which is where training's own validator sits too. Stating this rather than presenting the
probe as passing.

### One test I corrected rather than accommodated

`test_entry_session_is_resolved_by_instant_not_by_calendar_date` asserted that a post-close entry
belonged to the session that had already closed. That assertion encoded the defect: resolving an
entry to a session not open at that instant is exactly what let a 09:05 fill mature at 09:15. It now
asserts the next session, with the reason written into the test body so a later reader does not
mistake it for an assertion loosened to make a suite pass.

## Not closed

- **Blocker 2** (window-length feature divergence) — awaiting a founder design decision.
- **These repairs are unadjudicated.** Author-repaired, author-tested. The Red Team that found the
  defects never finished, so nothing here has been independently rechecked.

## Full suite

`uv run pytest -q` -> **855 passed, 1 dependency deprecation warning** in the shared checkout. This
count includes another agent's unstaged DSR tests and is recorded as checkout evidence, not claimed
as this repair's test contribution.

The five owned suites ran twice concurrently in opposite file orders: **68 passed** in each run.
The available pytest plugins were `anyio` and `cov`; no random-order plugin was installed. Ruff,
Ruff format, strict mypy, `check-code.mjs`, and `check-tests.mjs` were clean on the exact owned paths.
`scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1` both exited 0.

## Stop point

Repair commit `deccec1` is pushed to `origin/main`. No independent adjudicator has rechecked it.
Unrelated DSR boundary changes remained unstaged and were not included in the commit.

## Next safe action

An independent Red Team should adopt
`agent_context/handoffs/20260824-governed-execution-majors-4-9-recheck.md`, rerun the original
probes and attempt bypasses around symbol identity, malformed history, maturity resolution,
duplicate dates, and open-exposure auditing. Blocker 2 must remain open until the founder chooses a
canonical feature-window policy.
