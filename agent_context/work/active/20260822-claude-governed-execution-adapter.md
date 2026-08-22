# Active work: governed model to execution adapter

STATUS: COMPLETE for the adapter; engine plumbing deferred — not adjudicated  
OWNER: Claude Code — governed execution adapter  
TOOL: Claude Code  
STARTED_UTC: 2026-08-22T22:15:00Z  
STARTING_REVISION: `9789fd4`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, disjoint paths)

## Founder ownership grant

The founder granted this record write ownership of `src/quant_system/execution/**` and
`src/quant_system/modeling/**` on 2026-08-22, which releases the blocker recorded in
`20260822-claude-model-execution-adapter-scope.md` ("Implementation must not begin until those are
resolved or the claim is released"). That scope record is the design input for this one; this record
is the implementation.

## Objective

Close the gap where the system that executes is not the system that was validated. Verified at
`9789fd4`: `grep -rn "RidgeFittedStateV1|predict_ridge_scores|ModelCardV1" src/` returns zero
results outside `modeling/`; `execution/` and `server/` import nothing from `modeling/`; and
`strategies/ml_equity.py:17` defines `RollingRidgeClassifier`, a second ungoverned ridge that
execution does use.

Deliver a governed adapter that lets a promoted model drive execution decisions using the **same
feature kernel** and the **same decision rule** it was validated under.

## Owned paths

- `src/quant_system/execution/governed_strategy.py` (new)
- `src/quant_system/modeling/features.py` (P1 kernel promotion)
- `src/quant_system/modeling/preprocessing.py` (P1 kernel promotion)
- `src/quant_system/modeling/__init__.py` (exports)
- `tests/test_governed_strategy.py` (new)
- `agent_context/work/active/20260822-claude-governed-execution-adapter.md` (this file)

## Non-goals, and the one that is not mine to take

- **`src/quant_system/execution/realtime_shadow.py` and `execution/paper_pilot.py` are NOT touched.**
  They are claimed by `20260822-claude-s9b2-repair-and-cadence.md`, which is `STATUS: IN_PROGRESS`
  with uncommitted work in exactly those files. The founder's grant clears the Slice 4 modeling
  claims that blocked this work; it does not make it safe to edit files a different agent is
  mid-repair in. The scope record independently reaches the same conclusion: the session-close
  cadence item "interacts with Red Team finding S9-B2 and must not be layered on top of it."
  Engine plumbing is therefore a separate step, after S9-B2 lands. See Deferred below.
- Removing `RollingRidgeClassifier` from execution paths. That requires editing the engines above.
- `tests/test_realtime_shadow.py`, `tests/test_paper_pilot.py` — same claim.
- Declaring anything PASS or CERTIFIED. No Red Team, no Verifier has seen this.

## Design decisions

**D1. One feature kernel, promoted rather than reimplemented.** `_six_features` was private at
`features.py:268`. It is now public `compute_feature_values`, and `_build_feature_row` calls it, so
training and execution share one implementation byte for byte. The same is done for the per-row
standardization arithmetic, extracted from `transform_feature_rows` into
`standardize_feature_values`, which `transform_feature_rows` now calls. Reimplementing either is how
the second ridge got here.

**D2. The adapter is long-only, because that is what was validated.** This is the most important
decision in the module and it is not cosmetic. `validation.py:132` computes
`candidate_targets = "UP" if Decimal(score) > threshold else "DOWN"`, and
`_portfolio_period_returns` (`validation.py:402`) records a return **only** where the prediction is
UP. Every Sharpe, accuracy and deflated Sharpe in the evidence store was therefore produced by a
long-or-flat rule. An adapter mapping sign-of-score to BUY/SELL would execute a decision rule the
model was never evaluated under — reintroducing, in a new form, the exact defect this work exists to
close. `GovernedModelStrategy` emits BUY or nothing.

**D3. The threshold travels with the bundle and is not defaulted to zero.** Targets encode UP `+1` /
DOWN `-1` (`ridge.py:93`), so a ridge fit on standardized features puts its intercept at the mean
target, which is negative on any DOWN-skewed instrument. A zero threshold then demands the features
overcome the entire class skew; measured on real INFY data that produced zero UP predictions in 63
sessions and a `DEGENERATE_RETURN_SERIES`. `score_threshold` is a required field on
`PromotedModelBundleV1` and must equal the value the model was validated at.

**D4. Missing plumbing raises; a weak opinion abstains.** An absent or malformed point-in-time bar
map is a configuration fault and raises a typed `GovernedExecutionError`, because returning "no
signal" would be indistinguishable from a model with no opinion and would let a misconfigured
surface look healthy. Insufficient warmup or a score inside the abstention band returns no signal,
which is a genuine model outcome.

**D5. Bundle integrity checks are only the ones that are real.** `fitted.preprocessing_state_hash`
must equal `standardization.state_hash` — a genuine binding that already exists. Verdict must be
executable for the surface. `model_card.candidate_id` must equal the bundle's declared
`candidate_id`. Deliberately **not** implemented: a "model_card_hash must re-derive" check.
`ModelCardV1.__post_init__` computes that hash from its own fields on every construction, so it
re-derives by definition and such a check would be theatre. Tamper detection for cards belongs at
the evidence-store boundary, where `load_persisted_trial_registry` already does it.

## Plan

1. COMPLETE — read scope record, P2 decision record, and every contract to be bound.
2. COMPLETE — confirm s9b2 is live and scope the engine plumbing out.
3. COMPLETE — this record.
4. P1 kernel promotion in `modeling/`.
5. New `execution/governed_strategy.py`.
6. `tests/test_governed_strategy.py` — R1 feature identity, score mapping, verdict gating, bundle
   integrity; R5 short window, missing symbol, non-executable verdict, mismatched standardization.
7. Full gate: ruff, ruff format, strict mypy, vulture, craft delta, full suite.

## Current step

All seven steps complete.

## Deferred, with reasons

| Item | Why deferred |
|---|---|
| Evidence-store reader serving point-in-time bars to execution | Needs the engines; `realtime_shadow.py` claimed and live |
| Shadow and paper engines populating `GOVERNED_BARS_KEY` | Same |
| Session-close decision cadence for daily models | Scope record: must not be layered on S9-B2 |
| Removing `RollingRidgeClassifier` from execution | Requires engine edits |
| Corporate-action authority rule for live series (scope P5) | Needs a policy decision, not code |

The adapter is complete and testable without these. What it cannot yet do is run inside a live
session, because nothing populates its bar input. That is stated plainly rather than implied away.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run pytest tests/test_governed_strategy.py -q` | **17 passed** | R1 feature identity and standardization identity, decision rule, long-only property, abstention band, metadata reconciliation, verdict gating, bundle integrity, surface faults |
| `uv run pytest -q` | **648 passed** | Includes 17 new. Note the tree also gained ~123 tests from other agents during this session; only 17 are mine. |
| `uv run ruff check src launcher.py scripts tests` | PASS | `All checks passed!` |
| `uv run ruff format --check ...` | PASS | `183 files already formatted` |
| `MYPYPATH=src uv run mypy src launcher.py` | PASS | `Success: no issues found in 117 source files` |
| `uv run vulture src launcher.py scripts --min-confidence 80` | PASS | exit 0 |
| `node scripts/check-code.mjs` | PASS for my files | `governed_strategy.py`, `features.py`, `preprocessing.py` all zero findings |
| Mutation: shift the feature window by one bar | **KILLED** | `test_adapter_features_are_identical_to_training_features` failed as required, then passed after restore |

### What the feature-identity test does and does not prove

It proves the adapter selects the same bar window as the training builder — oldest first, inclusive
of the decision bar. The one-bar mutation above confirms it is sensitive to that.

It cannot prove arithmetic identity, and the test says so. Both sides call `compute_feature_values`,
so mutating that kernel moves both sides together and the assertion stays green. That is the
intended consequence of promoting the kernel: arithmetic identity is guaranteed structurally by
there being exactly one implementation, not by an assertion. The failure mode being defended against
is a second implementation reappearing.

## Blockers and conflicts

None for the owned paths. The deferred items are blocked on `20260822-claude-s9b2-repair-and-cadence.md`.

## Files changed

- `src/quant_system/execution/governed_strategy.py`: new. `PromotedModelBundleV1`,
  `GovernedModelStrategy`, `ExecutionSurface`, `SURFACE_ALLOWED_VERDICTS`, `GOVERNED_BARS_KEY`.
- `src/quant_system/modeling/features.py`: `_six_features` promoted to public
  `compute_feature_values`; `_build_feature_row` now calls it. No arithmetic changed.
- `src/quant_system/modeling/preprocessing.py`: per-row standardization extracted to public
  `standardize_feature_values`; `transform_feature_rows` now calls it. No arithmetic changed.
- `src/quant_system/modeling/__init__.py`: exports for both kernels.
- `tests/test_governed_strategy.py`: new, 17 cases.

Not touched, and deliberately so: `execution/realtime_shadow.py`, `execution/paper_pilot.py`,
`core/ledger.py`, `modeling/holdout.py`, `strategies/ml_equity.py`, and every `advisory/` path. The
first two are claimed by a live IN_PROGRESS record; the next two were being edited by
`20260822-claude-h2-l2-repair.md` while I worked.

## Stop point

The adapter exists, is fully typed, and is covered by 17 tests. **It cannot yet run in a live
session**, because nothing populates `GOVERNED_BARS_KEY`. That is a deliberate boundary, not an
omission — see Deferred.

`RollingRidgeClassifier` is still the ridge that execution actually uses. The second-calculation-path
defect is therefore **not yet closed**; it is now closable, because a governed alternative exists.

## Next safe action

After `20260822-claude-s9b2-repair-and-cadence.md` reaches COMPLETED, wire the engines: an
evidence-store reader serving point-in-time bars, shadow and paper populating `GOVERNED_BARS_KEY`,
and a session-close decision cadence for daily models. Then remove `RollingRidgeClassifier` from
execution paths. Do not begin while S9-B2 is open.
