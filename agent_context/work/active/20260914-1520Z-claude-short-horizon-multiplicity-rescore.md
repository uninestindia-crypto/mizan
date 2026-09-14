# Active work: re-score the short-horizon program against the frozen nine-trial budget

STATUS: ACTIVE
OWNER: Claude Code (Opus 5)
TOOL: Claude Code
STARTED_UTC: 2026-09-14T15:20:00Z
STARTING_REVISION: `a4cfa22e429aa648463297884a6ed0bfe4010a22`
WORKTREE_OR_BRANCH: `D:\quant_system`, branch `claude/short-horizon-multiplicity-rescore`
  (shared checkout; exact owned paths below). Cut from `main` at `4e3449d8` on founder
  instruction to commit, because this work crosses two ACTIVE claims and the checkout is shared
  with a concurrent session. Carries one commit, `7ad347ed`, 21 files. **Not merged into
  `main`**, so `main` still quotes the pre-rescoring DSRs until it is.

## Authorization

Founder instruction, 2026-09-14:

> "Re-score every short-horizon ridge, TimesFM 3.0, TimesFM 2.5, and noise result against the frozen
> nine-trial multiplicity budget. Fix the hardcoded declared-trial count, preserve the original raw
> metrics, regenerate the affected result/report/model-card artifacts, add regression coverage, and
> do not run any additional trial or consume a new ordinal."

This is the decision that
`20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md` deliberately left to
the owner, taken in the narrower of the two available forms — see "Decision rationale".

## Objective

Every published short-horizon deflated Sharpe was scored with `num_trials=6` while
`reports/short_horizon/TRIAL-LEDGER.md` now carries **9 SPENT rows**. Correct that one input, on the
existing stored evidence, so that no artifact in the repository quotes a DSR deflated against a
search two thirds its real size.

**Re-deflation only.** No trial is re-run, no evaluator is invoked, no ordinal is spent, no holdout
is touched, and no raw metric is recomputed.

## Owned paths

- `agent_context/work/active/20260914-1520Z-claude-short-horizon-multiplicity-rescore.md` (this file)
- `scripts/rescore_short_horizon_multiplicity.py` (new)
- `scripts/run_short_horizon_experiment.py`
- `src/quant_system/research_short_horizon/ledger.py` (new)
- `reports/short_horizon/results-ridge.json`
- `reports/short_horizon/results-timesfm.json`
- `reports/short_horizon/results-timesfm25.json`
- `reports/short_horizon/results-noise-control.json`
- `reports/short_horizon/TRIAL-LEDGER.md`
- `reports/short_horizon/COMPARISON-REPORT.md`
- `reports/short_horizon/SHORT-HORIZON-COMPARISON.md` (Antigravity's; DSR cells only, NOTICE filed)
- `reports/model_cards/short-horizon-ridge.md`
- `reports/model_cards/short-horizon-timesfm.md`
- `reports/model_cards/short-horizon-timesfm25.md`
- `reports/model_cards/noise-control.md`
- `reports/model_cards/README.md`
- `tests/test_short_horizon_rescoring.py` (new)
- `tests/test_short_horizon_trial_count.py`

## Non-goals

- **No trial, no ordinal, no holdout, no evidence store.** The re-scoring tool imports
  `OverfittingDiagnostics` and `json` and nothing from the evaluation path. A test enforces that.
- **No recomputation of any raw metric.** Sharpe, hit rate, trades, exposure, drawdown, total and
  mean net return are copied through byte-identical. They are the output of an evaluator that has
  since been repaired, and re-deriving them is the *other* correction — see below.
- **No re-run under the repaired evaluator.** That is a different decision with a different cost and
  it is not what was instructed.
- No edit to `results-noise-control.superseded-20260911T061355.json` — a superseded archive.
- No repository-wide formatter, generator, or `git add -A`.

## Decision rationale

### Two corrections are outstanding; this record performs exactly one

`20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md` names two
independent reasons every published short-horizon DSR is wrong:

1. **the multiplicity count** — scored at 6 against a ledger with 9 SPENT rows;
2. **the evaluator repair** — compounding, past-only abstention, DSR sample length and annualisation
   all moved at `056fb1c6`.

Correction 1 is a closed-form re-deflation of numbers already in the repository. Correction 2
requires re-running nine trials through the repaired evaluator, which produces genuinely new figures.
The founder instructed correction 1 and explicitly forbade the run that correction 2 needs.

**So this record does not make the published raw metrics true.** It makes the *deflation* honest at
the raw metrics that were actually published. Every artifact states both corrections and says which
one has been applied. That is a smaller claim than "these numbers are now correct" and it is the only
one the evidence supports.

### Why the raw metrics are preserved rather than re-derived

Preserving them is what makes the correction auditable: the published Sharpe is the input, the only
changed input is `num_trials`, so each delta is attributable to multiplicity alone. Re-deriving them
would confound the two corrections and destroy the comparison the founder asked for.

### Recovering the sample length, and why it is not guesswork

The pre-repair `summarise()` (`6131d84a:scripts/run_short_horizon_experiment.py:200-208`) called
`deflated_sharpe_ratio(sharpe, num_trials=DECLARED_TRIALS, sample_length_bars=max(sample_periods,3))`
with `periods_per_year` defaulting to 252. `sample_periods` was never serialised, so it must be
recovered before anything can be re-deflated.

The tool recovers it by inversion and **refuses to write unless it is pinned three ways**:

- **Unique per arm.** For each (arm, hold) it solves for the integer sample length reproducing the
  published DSR at the published `multiplicity_count`, to the 6 decimal places the artifact records,
  with a one-unit-in-last-place envelope because the stored Sharpe is itself rounded to 6 dp.
- **Consensus across arms.** The four arms must agree on one value per hold. They do: 2173 / 2172 /
  2171 at holds 1 / 2 / 3 — one fewer decision date per extra held session, which is the arithmetic
  the harness would produce.
- **Exact on unrounded data.** The 30-seed noise draws store **unrounded** Sharpe. All **90** of them
  reproduce their published DSR exactly at the recovered lengths — zero mismatches. That is the
  strongest of the three checks, because nothing about it is fitted.

Independent corroboration, not produced by this session: the 2026-09-12 filer hand-computed the
re-deflation of trials 7-9 at 9 and wrote `0.118147 / 0.071891 / 0.312642` into the ledger. All three
reproduce **exactly** from the recovered lengths. A different agent, before this session existed,
using its own arithmetic, landed on the same sample lengths and the same convention.

### Two of the twelve candidate rows reproduce one ulp off, and that is expected

`ridge hold2` recomputes `0.059284` against a published `0.059283`, and `timesfm25 hold3` recomputes
`0.394440` against `0.394441`. Both are explained rather than tolerated: the stored Sharpe is rounded
to 6 dp, and perturbing it inside its own rounding envelope (+/-5e-7) moves the result across exactly
that boundary. Demonstrated, not asserted — see "Commands and outcomes". The other 10 candidate rows
and all 90 noise draws are exact.

This is disclosed in every artifact rather than smoothed over. A re-deflation that silently absorbed
a discrepancy it could not explain would be the same class of error this program exists to avoid.

### Why the declared-trial count stops being a literal anyone can desynchronise

`DECLARED_TRIALS` was `6` against a ledger of 9 until `056fb1c6` set it to `9`. The founder's
instruction to "fix the hardcoded declared-trial count" is therefore already satisfied as to its
*value*; what is not fixed is the *mechanism* that let it drift for two days across three published
trials.

`tests/test_short_horizon_trial_count.py` catches drift, but only in CI, and only after a run may
already have published a wrong number. So the ledger becomes the runtime authority:
`research_short_horizon.ledger.declared_spent_trials()` parses the SPENT rows, and the experiment
script **refuses to start** when its constant disagrees. The constant stays greppable and explicit;
it simply can no longer be wrong at the moment a result is produced. Fail-closed, consistent with
every other authority in this repository.

**Rejected:** deleting the constant and computing the count inline. It would make every DSR depend on
an unpinned parse of a Markdown file with no declared expectation, so a careless ledger edit would
silently re-score published work instead of failing.

## Plan

1. File this record. — DONE
2. Recover and triple-verify the scoring parameters of the published artifacts. — DONE
3. `research_short_horizon/ledger.py` + fail-closed binding in the experiment script. — DONE
4. `scripts/rescore_short_horizon_multiplicity.py`; re-score the four results JSONs. — DONE
5. Regenerate ledger, comparison reports and the five model cards. — DONE
6. `tests/test_short_horizon_rescoring.py`. — DONE, 48 tests
7. Gates: pytest, ruff, mypy, `audit-agent-claims.ps1`, `audit-disk-layout.ps1`. — DONE, all green
8. File the PROTOCOL §8.4 notices. — DONE

## Current step

Complete. Nothing staged, nothing committed.

## Result

Every deflated Sharpe in the short-horizon program is now deflated against the ledger's nine SPENT
trials. The originals are preserved in each results file under `*_as_published` keys and are printed
beside the corrected value in every regenerated table.

| # | Arm | Hold | As published (6) | Re-scored (9) | Delta |
|---|---|---:|---:|---:|---:|
| 1 | ridge | 1 | 0.026515 | **0.015569** | -0.010946 |
| 2 | ridge | 2 | 0.059283 | **0.037419** | -0.021864 |
| 3 | ridge | 3 | 0.094711 | **0.062647** | -0.032064 |
| 4 | TimesFM 3.0 | 1 | 0.023189 | **0.013464** | -0.009725 |
| 5 | TimesFM 3.0 | 2 | 0.004270 | **0.002182** | -0.002088 |
| 6 | TimesFM 3.0 | 3 | 0.191369 | **0.137089** | -0.054280 |
| 7 | TimesFM 2.5 | 1 | 0.167607 | **0.118147** | -0.049460 |
| 8 | TimesFM 2.5 | 2 | 0.107263 | **0.071891** | -0.035372 |
| 9 | TimesFM 2.5 | 3 | 0.394441 | **0.312642** | -0.081799 |
| NOISE | control | 1 | 0.000000 | 0.000000 | +0.000000 |
| NOISE | control | 2 | 0.148551 | 0.103240 | -0.045311 |
| NOISE | control | 3 | 0.419649 | 0.336002 | -0.083647 |

Noise median over 30 seeds: `0.0000 / 0.1615 / 0.5504` -> `0.0000 / 0.1134 / 0.4626`. Worst draw at
hold 3: `0.3197` -> `0.2454`. All 90 per-seed values were re-deflated individually and the order
statistics rebuilt from them.

**The program's best figure is now `0.312642`, not `0.394441`, against a `0.95` gate.**

### No conclusion moved, and it was verified rather than assumed

Re-deflation applies the same monotone map to every row at a hold, so it is rank-preserving. The
count of noise seeds beating each model is identical before and after: 0/30 at hold 1; at hold 3 all
30 beat the ridge and TimesFM 3.0 while 29 of 30 beat TimesFM 2.5. This is what licensed relabelling
the numbers inside the reports' narrative sentences without rewriting the sentences, and it is pinned
by `test_the_rescoring_preserves_every_comparison_against_the_control`.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`, `git worktree list`, `git branch --list` | PASS | clean at `a4cfa22e`; 2 external worktrees + 4 branches observed and untouched |
| Read all 86 records in `work/active/` | PASS | Ownership resolved under "Blockers and conflicts" |
| Invert published DSR for 12 candidate rows at `num_trials=6` | PASS | Unique consensus 2173 / 2172 / 2171 per hold across all four arms |
| Re-deflate 90 noise draws (unrounded Sharpe) at `num_trials=6` | **90/90 exact** | Confirms both the recovered lengths and `periods_per_year=252` |
| Reproduce the ledger's hand-computed re-deflations of trials 7-9 at 9 | **3/3 exact** | `0.118147 / 0.071891 / 0.312642`, computed by a different agent on 2026-09-12 |
| Perturb the two off-by-one-ulp rows within their rounding envelope | PASS | `+/-5e-7` on the stored Sharpe crosses the boundary in both cases |
| `rescore_short_horizon_multiplicity.py --check`, then write | PASS | 12 candidate rows + 90 draws re-scored; 0 gate passes |
| Raw-metric preservation, field by field vs `git show HEAD:` | **0 fields changed** | 4 files, all top-level keys, all trial keys, all 90 draws' seed/sharpe/exposure |
| Second `--check` run after writing | Identical output | Idempotent: `*_as_published` is the baseline, not the value just written |
| **Mutation:** restore `results-ridge.json` to its pre-rescoring state | **9 tests FAIL** | The artifact tests are real, not tautological |
| **Mutation:** set `DECLARED_TRIALS = 6` | **2 tests FAIL** | Both the new and the pre-existing binding test fire |
| **Demonstration:** `run()` with the constant forced to 6 and a nonexistent market-cache path | **Refused on the count** | It never reached the bad path, which is the proof it stops first |
| `uv run ruff check .` / `ruff format --check .` | PASS | All checks passed; 680 files already formatted |
| `uv run mypy src launcher.py scripts` | PASS | 210 source files, no issues |
| `uv run pytest tests/ -q` | **1,577 passed** | 1,519 baseline + 48 mine + peer session's additions |
| `uv run pytest` reverse file order | **1,578 passed** | Run as the CI matrix does; exit 0 in 532s |
| `scripts/audit-agent-claims.ps1` | PASS | Every workspace has a visible claim and every claim resolves |
| `scripts/audit-disk-layout.ps1 -Fast` | PASS | No stray QuantOS directories |

A peer session (`quant-system-c2`) independently measured a mypy failure on
`scripts/rescore_short_horizon_multiplicity.py:135` and reported it by cross-session message before I
reached the gate. Real, and mine: `candidate_score` returned an `Any` out of a `dict[str, Any]`.
Fixed by annotating the local. Recorded because it is the concurrency protocol working — their
measurement, my file, no edit by them.

## Files changed

Under the short-horizon program's claim:

- `reports/short_horizon/results-ridge.json`, `results-timesfm.json`, `results-timesfm25.json`,
  `results-noise-control.json` — re-deflated; raw metrics byte-identical; originals preserved
- `reports/short_horizon/TRIAL-LEDGER.md` — rows 1-9 and NOISE re-scored, the noise-control tables
  rebuilt, the stale "quoted at 6 and the budget is now 9" section closed, and a dated
  "Re-scoring, 2026-09-14" section added
- `reports/short_horizon/COMPARISON-REPORT.md` — DSR tables and the headline
- `scripts/run_short_horizon_experiment.py` — ledger binding in `run()` and the `DECLARED_TRIALS`
  docstring. **No scoring logic touched**
- `src/quant_system/research_short_horizon/__init__.py` — re-exports

Under the Antigravity delivery claim (NOTICE filed):

- `reports/short_horizon/SHORT-HORIZON-COMPARISON.md` — nine DSR cells, two prose lines and the
  budget header. Every other column, every narrative sentence and the authorship line untouched

Model cards:

- `reports/model_cards/short-horizon-ridge.md`, `short-horizon-timesfm.md`,
  `short-horizon-timesfm25.md`, `noise-control.md`, `README.md`

New, and mine:

- `src/quant_system/research_short_horizon/ledger.py` — the frozen ledger as a runtime authority
- `scripts/rescore_short_horizon_multiplicity.py` — the re-deflation tool
- `tests/test_short_horizon_rescoring.py` — 48 tests

Notices filed (additive; no other record edited):

- `20260914-NOTICE-short-horizon-rescored-to-nine-trials.md`
- `20260914-NOTICE-antigravity-comparison-dsr-cells-rescored.md`
- `20260914-NOTICE-adjudication-training-path-quotes-superseded-dsrs.md`

### One affected report was deliberately NOT regenerated

`.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md` section 3 tabulates six of the DSRs this
work moved. **It was not edited**, and that is a decision rather than an oversight.

It is a dated adjudication — a record of what an independent agent read out of the results files on
2026-09-11 and concluded from it. Its value is that it says what that agent actually found on that
date. Rewriting its numbers to today's would not update a report; it would fabricate an adjudication
that never took place, and `.launch/` is where this repository keeps evidence precisely because it is
not rewritten.

It was also **correct when written**: the ledger held six SPENT rows on 2026-09-11, and trials 7-9
were declared the following day. Its verdict is unaffected either way — re-deflation is
rank-preserving, so "the noise control outscores both real models at hold 3" survives intact.

A notice is filed instead, naming the exact superseded figures.

**That notice was strengthened after filing.** It originally closed with *"nothing in the repository
is wrong as a result of that report existing unchanged"*, which was too strong and is corrected in
place. `agent_context/README.md` ranks `.launch/` **above** `CURRENT.md`, completed records and
handoffs, so a reader following the hierarchy correctly reaches that report's
*"`multiplicity_count = 6` matches `declared_trials = 6` ... so the ledger was honoured"* before
reaching any evidence of this re-scoring. A superseded number reachable by correct procedure in the
highest-ranked source is not harmless. It is bounded — the verdict is rank-preserving and survives,
and "the ledger was honoured" is true again at 9/9 — but the notice now records the conflict under
README's own rule rather than dismissing it. Credit to the peer session `quant-system-c2`, which made
the structural argument about its own adjudication first.

`reports/loss_diagnosis_20260913/DIAGNOSIS.md` was also left alone and needs no notice: its statement
*"best reported DSR is 0.394441 using six trials; its card gives 0.312642 when re-deflated for nine"*
is still true, and is now simply describing the published basis.

## Blockers and conflicts

Editing under two ACTIVE claims, on the founder authorization recorded above. Their records are not
edited (PROTOCOL §3); additive notices are filed instead (PROTOCOL §8.4):

- `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` — owns
  `reports/short_horizon/**`, `scripts/run_short_horizon_experiment.py`,
  `src/quant_system/research_short_horizon/**`, `tests/test_short_horizon*.py`. This work changes
  numbers that record pins as evidence.
- `20260911-antigravity-short-horizon-and-windows-delivery.md` — owns
  `reports/short_horizon/SHORT-HORIZON-COMPARISON.md`.

Concurrent session, observed not inferred: `quant-system-c2` is working
`src/quant_system/data/corporate_actions.py`, `tests/test_corporate_actions.py` and
`reports/corporate_action_validation/**` under a partial, named adoption of the same 20260910-1615Z
record. **Disjoint from every path above**, confirmed by message in both directions. Its changes were
present in this shared checkout as uncommitted working-tree edits throughout my measurements and were
left strictly alone; the suite count moved 1,577 -> 1,578 between two of my runs because that session
added a test mid-run.

That session later stated its work was "already committed at `e0f0c316` when you measured". Checked
rather than accepted: `e0f0c316` has committer timestamp `2026-09-14T21:22:14+05:30`, my last gate run
completed at approximately that same minute with every earlier run before it, and `git status --short`
taken during the work listed both of its source files as `M` (modified, unstaged).

**The other session then re-checked and withdrew the correction**, supplying a sharper datum than I
had: its own final gate run finished at `21:21:17`, **57 seconds** before the commit. So both of us
measured a tree in which those edits were uncommitted, and the uncommitted framing above stands.

Its own diagnosis of the error is worth carrying forward, because it is a trap in every shared
checkout: it reasoned from when my *message* arrived rather than from when my *measurement* was taken,
and those are different events. Pytest reads the working tree rather than the index, so **no number in
this record moves either way**; this is recorded only so the record does not carry a false statement
about when a peer's work landed.

Reported by that session and recorded as their measurement, not mine: their corporate-action change
produces 0 differences across all 19,941 authority records in the all-market cache, and no committed
`factor_set_hash` exists anywhere under `data/` or `reports/`, so no evidence hash moves.

## Stop point

All eight plan steps complete, and the work is committed.

`7ad347ed` on `claude/short-horizon-multiplicity-rescore`, 21 files, 2,533 insertions / 243
deletions. Staged as an explicit path list, never `git add -A` (PROTOCOL §4). Working tree clean.
**No trial run, no ordinal spent, no holdout touched, no evidence store or paper book written.**

**`main` is unchanged and still carries the pre-rescoring figures.** Fast-forwarding this branch into
`main` is the step that makes the correction take effect for anyone reading the repository, and it is
a founder decision rather than one taken here.

Two notes for whoever is next in this shared checkout:

- The checkout's HEAD is currently on this branch, not `main`. `scripts/daily_auto_sync.ps1` commits
  its allowlist (`data/evidence`, `data/authorities`) to whatever branch is checked out, so if it
  runs before the branch is resolved those commits land here rather than on `main`.
- The concurrent session `quant-system-c2` committed its own disjoint work to `main` at `e0f0c316`
  and `4e3449d8` before this branch was cut, so nothing of its work is stranded by it.

Every gate is green, including the reverse-file-order run that was still executing when the rest of
this record was written: **1,578 passed in 532.05s, exit 0**. The forward run passed at 1,577 and a
second forward run at 1,578; the difference is the peer session adding a test mid-run in this shared
checkout, not instability.

## What was measured, and what was not

**Measured:** that the recovery reproduces the published artifacts three independent ways; that no
raw-metric field changed; that the tool is idempotent; that both mutations are caught by the new
tests; that the runtime refusal fires before any data is read; that every comparison against the
noise control is preserved; and that every gate is green.

**Not measured, and it is the important limitation:** whether any of these raw metrics is correct.
They are the output of an evaluator repaired at `056fb1c6` and they predate that repair. This work
makes the *deflation* honest at the metrics that were published; it does not make the metrics true.
Every regenerated artifact says so in those words, and each results file carries
`raw_metrics_predate_evaluator_repair: "056fb1c6"` per trial with a test asserting it is present.

## Next safe action

For the owner of `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md`: the decision
left open by `20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md` is
**still open and still theirs** — whether to re-run the nine declared trials under the repaired
evaluator, and whether that spends fresh ordinals. This work deliberately did not pre-empt it.

Nothing in this record requires further action to be safe. If the re-scoring is unwanted, it is
reversible: every original figure is preserved in the results files.
