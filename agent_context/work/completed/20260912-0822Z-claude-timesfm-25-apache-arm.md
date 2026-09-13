# Active work: TimesFM 2.5 (Apache-2.0) short-horizon arm, trials 7-9

STATUS: COMPLETED  
OWNER: Claude Code (Opus 5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-12T08:22:00Z  
STARTING_REVISION: `9aa3bd8e53634415c2ec3624ea6d572f4afaca2e`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; owned paths below)  
AUTHORIZATION: founder instruction, 2026-09-12 — *"use the 2.5 weights instead"*, then *"Run all
three holds"* after being shown the three-ordinal cost, the ~3-4 hour runtime, and the alternative of
running one hold or none.

## Objective

Add a **licensing-clean** foundation-model arm to the short-horizon program by replacing
`google/timesfm-3.0-pytorch` (non-commercial, production prohibited) with
`google/timesfm-2.5-200m-pytorch` (**Apache-2.0**), evaluated at holds 1, 2 and 3 as declared trials
7, 8 and 9.

The motivation is licensing, not performance. The founder holds a commercial grant for 3.0 but
declined to share its details (privacy); the 2.5 route needs no grant, so no grant is recorded or
relied upon anywhere in this work.

## Owned paths

- `scripts/generate_timesfm_forecasts.py` (parameterisation only — see Non-goals)
- `reports/short_horizon/timesfm25-forecasts.json` (new)
- `reports/short_horizon/timesfm25-forecasts.partial.jsonl` (new)
- `reports/short_horizon/results-timesfm25.json` (new)
- `reports/model_cards/short-horizon-timesfm25.md` (new)
- `agent_context/work/active/20260912-0822Z-claude-timesfm-25-apache-arm.md`
- Any `20260912-*-NOTICE-*` record this session files

**Amended additively, not owned:** `reports/short_horizon/TRIAL-LEDGER.md` — see Blockers.

## Non-goals

- **No overwrite of the 3.0 evidence.** `timesfm-forecasts.json` and its `.partial.jsonl` are the
  evidence behind published trials 4-6 and are not written, moved or deleted.
- **No constant swap.** The checkpoint is parameterised so trials 4-6 stay reproducible from the
  same script. Replacing `CHECKPOINT` in place would have made published evidence unreproducible.
- **No weakening of a gate.** `GatePolicyV1` untouched; no threshold adjusted to obtain a pass.
- **No promotion, no live-money routing.** Whatever 2.5 scores, it stays `RESEARCH_ONLY`.
- **No edit to another session's in-flight files.** Specifically not `scripts/train_mizan.py`,
  `scripts/screen_mizan_out_of_sample.py`, `src/quant_system/data/corporate_actions.py`, or
  `src/quant_system/research_xs_monthly/**`.
- No re-run of the 3.0 arm, the ridge arm, or the noise control.

## Plan

1. Smoke the 2.5 API in the scratchpad, no repo files touched — **DONE**, 6/6 checks passed.
2. Real-data dispersion smoke, no evaluation — **DONE**.
3. File this record and the NOTICE — **DONE**.
4. Declare trials 7-9 in the frozen ledger, before any 2.5 evaluation runs — **DONE**.
5. Parameterise the checkpoint in `generate_timesfm_forecasts.py` — **DONE**, gates clean.
6. Generate 2.5 forecasts to a new output path — **DONE**, 88,385 forecasts in 183.5 min.
7. Evaluate the arm; publish `results-timesfm25.json` and a model card — **DONE**.

## Current step

Complete. Trials 7-9 are `SPENT` and recorded.

**Result: 2.5 beat 3.0 at every hold and still fails everything that matters.** DSR 0.167607 /
0.107263 / 0.394441 (as scored at 6) against a 0.95 gate; 0.118147 / 0.071891 / 0.312642 re-deflated
at the true budget of 9. The noise control still wins at holds 2 and 3 — the two holds where the
candidate actually trades. Verdict `RESEARCH_ONLY` at every hold.

**The prior recorded in Amendment 4 before the run — "expect 2.5 to reproduce the 3.0 null" — was
half wrong.** 2.5 is materially the better forecaster (positive Sharpe at all three holds where 3.0
was negative at two). It is recorded as a correction, not restated as though it had been expected.

## Decision rationale

**Why 2.5 rather than a grant for 3.0.** The upstream package states the split directly in its
METADATA: source code Apache-2.0, weights **up to 2.5** Apache-2.0, 3.0 weights under
`timesfm-non-commercial-license-v1.0`. 2.5 therefore needs no grant, no record and no verification.
`reports/mizan_loss_diagnosis_20260910.md:82` reached the same conclusion independently on
2026-09-10, before this session.

**Why three ordinals and not a reclassification.** A real model with predictive content spends an
ordinal. The noise control does not, because it has none by construction. Running 2.5 as a "control"
or "replication" to avoid the cost would be exactly the manoeuvre the frozen ledger exists to
prevent, and it was explicitly refused.

**Why the smokes stopped short of measuring skill.** Dispersion and magnitude are wiring properties.
Correlating a prediction with a realised return before the trial is declared would make the
declaration worthless, because the result would already have been seen. Neither smoke computes IC,
Sharpe, hit rate or P&L.

**What the smokes established, and its limits.** Matched window (8 liquid names, 40 dates,
2026-06-29..2026-08-21, 320 forecasts each): 2.5 median cross-sectional stdev **0.001912** against
3.0's **0.001498**, both against realised dispersion 0.009777. 2.5 produces ~28% more spread and is
in the same shrinkage regime. This says the arm is runnable. It says **nothing** about whether the
spread is informative — a better model and a differently-noisy one are indistinguishable on this
statistic, which is why it is recorded as a prior and not as a finding.

**Expected outcome, stated before the run so it cannot be claimed afterwards.** 3.0 with a very
similar dispersion profile scored DSR 0.023189 / 0.004270 / 0.191369 and lost to the noise control at
every hold. The honest prior is that 2.5 reproduces that null. It is being run anyway because a
licensing-clean arm that has been properly tested is worth more than an untested one, and because the
founder chose the full three-hold run after being shown the cost.

**Rejected: one hold instead of three.** Cheaper at one ordinal, but selecting hold 3 because that is
where 3.0 scored best is a selection effect that would have to be declared as one, and partial
coverage would likely be completed later anyway at the same total cost.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| scratchpad `smoke_timesfm_25.py` | **PASS** 6/6 | shape (5,3); finite; positive; max abs ret 0.0026; deterministic; affine equivariance max rel dev 4.82e-08 |
| scratchpad `smoke_timesfm_25_real.py` | **PASS** | 8 names x 40 dates = 320 forecasts, 6.2 forecasts/sec; median cross-sec stdev 0.001912 |
| 3.0 dispersion from saved forecasts | **MEASURED** | same 8 names/40 dates: 0.001498; all names, 1,966 dates: 0.002345. No inference re-run |
| `git status --short --branch`, `git worktree list`, `git branch --list` | **RUN** | 3 worktrees, 4 branches, owning session live |
| ledger amendment | **DONE** | md5 `62aa7b1b…` -> `be16f303…`; `git diff --numstat` 70 insertions / 6 deletions, and all 6 deletions are the owning session's own pre-existing uncommitted edits |
| `ruff check` + `ruff format --check` (single file) | **PASS** | scoped to the one changed file; no repo-wide formatter run, another session is live |
| `mypy src launcher.py scripts` | **PASS** | `Success: no issues found in 208 source files`; zero errors attributable to the changed file |
| guard test: `--checkpoint 2.5` with default `--out` | **REFUSED as designed** | argparse error naming the mixed-checkpoint hazard |
| `generate_timesfm_forecasts.py --checkpoint …2.5… --out …timesfm25-forecasts.json` | **DONE** | 88,385 forecasts, 45 names, 1,967 dates, 183.5 min |
| output verification | **PASS** | checkpoint field correct; 0 rows missing a hold; 3.0 files unchanged (mtime + git); contamination check over all 88,385 shared keys found 1 step-1 float collision whose steps 2/3 differ |
| `run_short_horizon_experiment.py --arm timesfm --timesfm-forecasts …25… --out results-timesfm25.json` | **DONE** | 3 holds, all `RESEARCH_ONLY`, all gate_passed=False |
| re-deflation at 9 via `OverfittingDiagnostics` | **DONE** | 0.118147 / 0.071891 / 0.312642 |
| `ruff check` + `format --check` (single file), `mypy src launcher.py scripts` | **PASS** | Success, 208 source files |
| `pytest tests/test_short_horizon_mapping.py -q` | **PASS** | 10 passed — hold->horizon convention still pinned |
| `audit-agent-claims.ps1` | **PASS** | every workspace has a visible claim and every claim resolves |
| `audit-disk-layout.ps1` | **PASS** | no stray QuantOS directories |

## Files changed

- `agent_context/work/active/20260912-0822Z-claude-timesfm-25-apache-arm.md`: this record.
- `agent_context/work/active/20260912-NOTICE-claude-timesfm25-trials-7-9-declared.md`: NOTICE to the
  owning record; names the `multiplicity_count` 6 -> 9 change it invalidates.
- `reports/short_horizon/TRIAL-LEDGER.md`: **additive only** — 3 rows (7/8/9 `DECLARED`) plus
  Amendment 4. No existing row altered.
- `reports/short_horizon/timesfm25-forecasts.json` + `.partial.jsonl`: the 2.5 forecast set.
- `reports/short_horizon/results-timesfm25.json`: trials 7-9 evidence.
- `reports/model_cards/short-horizon-timesfm25.md`: the 2.5 card.
- `reports/model_cards/README.md`: index row **and a correction to the "one-line result" paragraph**,
  which trials 7-9 falsified (it claimed a best DSR of 0.2466). Flagged in the NOTICE.
- `scripts/generate_timesfm_forecasts.py`: `--checkpoint` flag (default unchanged at 3.0, so trials
  4-6 stay reproducible), `build_predictor` normalising the two incompatible model APIs to one
  callable, `args.checkpoint` recorded in the payload, and a **fail-closed refusal** of
  non-default-checkpoint-with-default-output.

## Blockers and conflicts

**`reports/short_horizon/TRIAL-LEDGER.md` is claimed by
`20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (STATUS `ACTIVE`), whose
session is running right now** (`screen_mizan_out_of_sample.py` observed live), and which holds
**uncommitted edits** to that file — trials 4-6 filled in, the noise control row added, and a `33
days -> 33.1 hours` errata. Baseline md5 at amendment time: `62aa7b1b10e3d94f710e6c016f94a3f6`.

Per PROTOCOL §3 their record is not edited. The ledger amendment is **additive** — new rows and a
new dated amendment section, changing no existing row and none of their uncommitted content. A
NOTICE is filed naming the record and the exact addition. The file is re-hashed immediately before
and after the edit; a changed hash means their session wrote concurrently and the edit is reapplied
onto their content rather than over it.

`scripts/generate_timesfm_forecasts.py` is **not** named in any active record's owned-paths block and
carries no uncommitted changes (mtime 2026-09-11 11:42).

## Stop point

Arm complete and recorded. Working tree is dirty and **nothing is committed** — this session made no
commit, because the checkout is shared with a live session whose own uncommitted work sits in
neighbouring files and a broad `git add` here is exactly the §4 violation that produced `3d120730`.

Files this session owns are listed above. `multiplicity_count` for the short-horizon family is now
**9**.

## Next safe action

Stage and commit **only** the paths listed under Files changed, explicitly and by name, once the
founder decides. Do not use `git add -A`.

**Do not run a tenth trial.** The foundation-model direction has now been tested under both a
non-commercial and a permissive checkpoint and has no edge under either; ordinal 10 would deflate
everything further to search checkpoints for a number.

Open for the owning record, not for this session: `run_short_horizon_experiment.py:63` hardcodes
`DECLARED_TRIALS = 6`, so every trial in that file — theirs included — is quoted at its scoring-time
count rather than the current budget of 9.
