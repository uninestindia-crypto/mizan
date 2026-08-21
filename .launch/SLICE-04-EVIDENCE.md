# Slice 04 Evidence — One Governed Ridge Fold

STATUS: BLOCKED - repair round in progress; 4 Blockers and 4 Majors closed, 3 Majors and 5 Minors open
DATE: 2026-08-21
CANDIDATE REVISION: `b24b4eb2eefc689b29ed4eb8ea0e64d48dfd98f4`

This slice is **not certified and is not certifiable in its current state**. Every gate below
reproduces from an independent clean clone, and the Red Team confirmed the gate is genuinely green —
then broke the slice anyway, on that green tree. Four Blockers and seven Majors are unresolved. See
`.launch/reports/RED-TEAM-SLICE-04.md` and the "Red Team outcome" section below.

The gate figures in this document remain accurate for `b24b4eb` and are retained as the measurement
baseline. They are not, and never were, evidence that the slice is correct — that is precisely the
gap the adversarial pass exists to close.

## Outcome

Slice 4 fits the accepted six-feature ridge family across one expanding walk-forward fold built by
Slice 3. Standardization is learned from training rows only and applied unchanged to validation
rows. Every attempt — successful, failed, cancelled, or abandoned — is published as immutable
evidence before and after the fit, so the multiplicity count used to deflate the Sharpe ratio is
derived from the verified evidence catalog rather than from caller memory.

No holdout is opened and no promotion gate is evaluated. `RESEARCH_ONLY` with `UNCALIBRATED_SCORE`
outputs is the highest verdict this slice can produce.

## Contracts proved

- Preprocessing mean and population standard deviation are fitted from training feature rows only;
  validation rows cannot influence preprocessing or fitted-state hashes.
- Zero-variance features are named explicitly and take scale one; they are never silently dropped.
- The ridge fit uses one fixed six-feature order, an unregularized intercept, positive L2
  regularization, single-process execution, and no stochastic search.
- Coefficients, intercept, preprocessing state, predictions, and metrics are canonical decimal text
  and content hashed. Stored canonical coefficients drive prediction replay.
- A `STARTED` trial record is committed before any preprocessing or fitting occurs.
- A caught evaluation or publication failure still receives a typed immutable `FAILED` outcome, so
  the next ordinal remains usable and the attempt still counts toward multiplicity.
- The verified immutable trial catalog is the sole authority for the next global ordinal and the
  full multiplicity count; a caller-supplied in-memory registry is not accepted as authority.
- Every `SUCCEEDED` outcome must resolve to exactly one content-verified model evaluation sharing
  its trial, result hash, candidate, fold, multiplicity, model ID, and `RESEARCH_ONLY` verdict.
  Manifest alias identities are rejected.
- Python `bool` is rejected where an exact `int` is required, so booleans cannot poison persisted
  replay.
- A byte-identical latest open start may resume after interruption; its already-committed model is
  content-deduplicated before the terminal outcome is retried.
- The candidate and four baselines share validation rows, label timing, and already-bound net costs.
- Rows use one canonical `(candidate_id, decision_at, instrument)` order across dataset identity,
  fold construction, fitting, and evaluation.
- Simultaneous instruments are aggregated as equal weight across active longs for that decision
  time, not compounded as separate full-capital periods. Concentration is the largest active weight.
- Deflated Sharpe uses the complete immutable attempt count, converts to the 252-period scale, and
  incorporates observed skewness and Pearson kurtosis over the actual portfolio-period count. One
  trial reduces to sampling-aware PSR.

## Demo evidence

The governed training journey fixture runs end to end through fit, evaluation, and evidence
publication. Running it against two independent evidence roots produces byte-identical published
files and equal manifest hashes:

```text
start manifest   : a37565d0ffdad10b158628f3889efee00a340bc915c7529ca082bde516b4f907
model manifest   : 27e8e6b0bfa86e553bbfacf720fa164ae8c1b5fb3f5a018bfb15949c452decbb
outcome manifest : 4a5183af056a76552ed32aae6b7b590af5a3aa1b8ff21d22e8c94799eacf77b6

fold spec hash   : a1fc9fc71186773e7e034174520226917bc53302b32e6e29b74324b306c5b693
evaluation hash  : 69eff821d3edd726d709b522e25e02b7b17f90d29411c15adb34867dda4cc01c
feature dataset  : 912962d17d06ae3687946e81b92132eabed9dadaf0047cf803021cc3cfbea180
label dataset    : ff922843e5b8e38e5b0e340f46570a02972c215702f91ed013edd78c861c1ee1

trial            : trial_ridge_001 / candidate cand_ridge_v1
outcome state    : SUCCEEDED, result hash equals the evaluation hash
train rows       : 18
validation rows  : 8
multiplicity     : 1
deflated Sharpe probability : 0.854984141908   <- a PROBABILITY in [0,1], not a ratio
```

The deflated Sharpe is the probability that the observed Sharpe survives correction for the number
of attempts, the sample length, and the return distribution's skew and kurtosis. It is not a Sharpe
ratio and must never be compared against one. The table below reports Sharpe *ratios*; `0.855` above
is a probability and does not mean deflation reduced 6.43 to 0.855.

Baseline comparison on the same validation rows, timing, and bound net costs:

| Strategy | Sharpe | Total return |
|---|---|---|
| `RIDGE` | 6.434418102803 | 0.088304331575 |
| `NO_TRADE` | 0 | 0 |
| `BUY_AND_HOLD` | 3.27853733499 | 0.049760219831 |
| `PREVIOUS_SIGN` | -4.883509213356 | -0.045294106395 |
| `EQUITY_DUAL_MOMENTUM` | 3.27853733499 | 0.049760219831 |

**These numbers are not a financial result and must never be quoted as one.** They come from a
deterministic synthetic fixture over eight validation rows. A Sharpe ratio computed on eight
periods carries no statistical meaning, and the deflated Sharpe of 0.855 reflects a single recorded
trial. The table proves only that the candidate and its four baselines are computed on identical
rows, timing, and costs, and that the numbers reproduce exactly.

These figures also predate the repair round below. They describe `b24b4eb`, which is blocked.

## Clean-state verification

Independent detached clone of `b24b4eb`, frozen environment, run with
`scripts/run-slice4-gates.ps1 -PythonEnvironment .venv`.

| Gate | Result |
|---|---|
| Frozen install | PASS — `uv sync --frozen --extra dev`, 47 packages, uv 0.12.5, CPython 3.13.15 |
| Ruff lint | PASS — all checks passed |
| Ruff format | PASS — zero files require reformatting. The file *count* is deliberately not pinned; see the measurement note |
| Strict Mypy | PASS — no issues in 83 source files |
| Repository tests | PASS — 272 passed |
| Repository coverage | PASS — 5,830 statements / 660 missed / 88.68% |
| Focused Slice 4 suite | PASS — 80 tests, but **under-scoped as measured**; see the gate-scope note below |
| `modeling` package coverage | PASS — 1,667 statements / 194 missed / 88.36% |
| `evidence` package coverage | PASS — 922 statements / 117 missed / 87.31% |
| Dead-code scan | PASS — zero findings at >=80% confidence |
| Application secret scan | PASS — zero candidates |
| Slice 4 Code Craft | PASS — 17 files clean |
| Slice 4 Test Craft | PASS — 12 test files clean |
| Mutation checks | INHERITED from `6a17d5e`, not measured at `b24b4eb` — eleven mutations killed and restored; not re-executed by the Verifier |
| Red Team | **BLOCKED** — attempt 1 aborted on a usage limit; attempt 2 returned 4 Blockers, 7 Majors, 7 Minors. `.launch/reports/RED-TEAM-SLICE-04.md` |
| Independent clean-state Verifier | **BLOCKED** — 48 PROVEN, 0 DISPROVEN, 5 NOT TESTED. `.launch/reports/VERIFIER-SLICE-04.md` |

### Gate scope defect, found and fixed after this baseline was measured

The `80 tests` above was produced by a focused suite that named its ten test files explicitly, so
every file added later fell silently outside it. At `b24b4eb` that already excluded
`tests/test_multiplicity.py`, which holds one of the eleven mutation guards. As the repair round
added regressions, it also excluded all three of them — the Blocker 2 forgery test, the Blocker 3
publish-atomicity test, and the Major 2 campaign-deflation test.

The figure is not wrong; it does not mean what its name implies. A focused suite that omits the
slice's highest-value regressions is worse than no focused suite, because it reads as reassurance.

Fixed in `5200741`: selection is now by pattern (`test_modeling_*.py`, `test_multiplicity.py`,
`test_evidence_publish_atomicity.py`), so new regressions fail open into the suite rather than out of
it, and the gate throws if the patterns match nothing. Ten files became fourteen.

Measured effect on the shared working tree at the time of the fix:

```text
old ten-file focused suite  :  91 passed, GREEN
new pattern-based suite     : 107 passed, 2 FAILED
```

Both failures were in-flight lease-contention regressions from the Major 4 repair. The old suite
could not have seen them. This is the second time in this slice that a green gate concealed a real
defect, which is the pattern the Red Team round exists to break.

### Measurement note

Every figure above was measured inside the detached clone, not in the install root.

**Correction.** An earlier revision of this document explained an install-root ruff-format count of
208 against the clone's 205 as local build artifacts plus another agent's edits to
`scripts/check-code.mjs`, `scripts/check-tests.mjs`, and three test files. The Verifier showed that
explanation is unsound and it is withdrawn: `.mjs` is not a ruff input at all, modifying an existing
file cannot change a count of inputs, and `build`/`dist`/`tmp`/`.venv` are excluded and contribute
zero.

The actual cause is that Ruff 0.16.3 formats **Markdown as well as Python**. The count is therefore a
property of the document set, not of the code. At `b24b4eb` the tracked content is 135 Python + 70
Markdown = 205. Adding files raises it: the Verifier observed 206 in its own clone, caused solely by
the claim sheet seeded there, and the install root now reports 217 after this evidence file and the
two adjudication reports were committed.

This makes any pinned ruff-format *count* self-invalidating — recording the number in a document
that is itself an input changes the number. The row above therefore records the stable fact, that
zero files require reformatting, and does not pin a count. Future slices should do the same.

### Drift after the candidate revision

`main` advanced past `b24b4eb` while this evidence was being prepared. Checked, not assumed:

| Commit | Effect on this evidence |
|---|---|
| `34c0683` fix(tooling): repair test-craft body scanning and checker encoding | Changes `check-code.mjs` and `check-tests.mjs`, which produce the two craft lines above |
| `66fb04d` test(craft): replace assertion loops with violation-collecting assertions | Changes craft test files only |
| `6f2b3c9` ci: add pinned Windows workflow | No effect on the gate |

`git diff b24b4eb..HEAD -- src/quant_system/modeling src/quant_system/evidence src/quant_system/analytics/multiplicity.py` is **empty**: the code this slice certifies is unchanged.

Because the craft checkers themselves changed, the Code Craft and Test Craft lines above were
re-measured with the corrected checkers against the same Slice 4 code. Both still pass with
identical counts — `code-craft: clean, 17 file(s)` and `test-craft: clean, 12 test file(s)` — so the
checker repair does not disturb this evidence. This was the specific risk of measuring a gate whose
tooling another agent was concurrently repairing.

Eight test files outside the Slice 4 set changed in that range, so repository-wide test and coverage
counts on current `main` will differ from the figures above. Those figures describe `b24b4eb` and
reproduce there; they are not a claim about `main` at any later revision.

Raw mutation output is in `.launch/reports/MUTATION-SLICE-04.md`. Runs 1-5 were executed against the
first candidate; runs 6-11 were executed after the Red Team found additional Blockers at `8d09ec4`
and were committed together with their repairs in `6a17d5e`. The `modeling` and `evidence` packages
are byte-identical between `6a17d5e` and this candidate revision, so that mutation evidence binds to
the code measured above.

## Red Team outcome

Attempt 1 aborted on an account usage limit with no findings. Attempt 2 ran to completion against
`b24b4eb` in an isolated clone and returned **BLOCKED**: 4 Blockers, 7 Majors, 7 Minors. It first
confirmed the gate is real — 133 tests pass in its clone, and the eleven mutation kills do bind the
attacked code — then broke the slice on that green tree. Full report and reproductions:
`.launch/reports/RED-TEAM-SLICE-04.md`.

### The six repairs from `6a17d5e`, adjudicated

| # | Repair | Verdict |
|---|---|---|
| 1 | `bool` into exact-`int` trial fields | HOLDS, scope gap — `FoldSpecV1`, `StrategyMetricsV1`, `EvidenceDraft.schema_version` uncovered |
| 2 | Interrupted model/outcome publication recovery | PARTIALLY HOLDS — fails after outcome *publication*; the FAILED-outcome guarantee itself breaks |
| 3 | DSR sampling uncertainty and moments | HOLDS |
| 4 | Dataset vs fold order for multiple instruments | HOLDS, scope gap — features key on `provider_instrument_id`, labels on `symbol`, evaluator joins on `symbol` |
| 5 | Simultaneous instruments and concentration | HOLDS |
| 6 | `SUCCEEDED` resolves verified model, aliases rejected | HOLDS — but model *content* is never re-derived |

Five hold on their stated scope, one partially. Three of the four new Blockers are variants the
repairs did not reach.

### Blockers

1. **Look-ahead leakage into the fit.** `evaluate_governed_ridge_fold` never checks that a training
   label matures before validation opens. A fold with zero purge and zero embargo, while declaring
   `embargo_sessions=2`, is accepted and published as a normal `RESEARCH_ONLY` model.
   `validation.py:250-305` constrains purged and embargoed rows but never `train_rows`.
2. **Forged model evidence passes verification.** `metrics_hash` and `prediction_hash` are copied
   verbatim on read and never re-derived (`persisted_trials.py:294-328`); the private
   `_metrics_hash` / `_prediction_hash` helpers have no read-side call site. A record rewritten in
   place to claim Sharpe 99 and DSR 0.999999999999 is accepted as content-verified, and
   `rebuild_index()` reports zero invalid resources.
3. **Publish-before-verify bricks the store.** `EvidenceStore._publish` publishes at `store.py:328`
   and only verifies readback at `:330`. Two legal inputs — metadata over `max_manifest_bytes`, and
   `EvidenceDraft(schema_version=True)`, which is mypy-clean because `models.py:74` tests `!= 1` —
   leave a permanently unreadable resource that breaks `list_verified` for its entire resource type
   and blocks every future trial. Unrecoverable.
4. **Legal `trial_id` deadlocks the store.** A `trial_id` ending in `_outcome` collides with another
   trial's outcome resource id (`trials.py:24`, `:78`). The failing commit sits at
   `training_evidence.py:190`, outside the try/except, so no `FAILED` fallback fires.

### Majors

1. Deleting trailing trial/outcome/model directories silently rolls multiplicity back — 5 attempts
   to 1, `rebuild_index()` clean, DSR 0.4528 to 0.7072.
2. Published DSR is frozen at the trial's own ordinal and never re-deflated. Attempt 1 of an
   8-attempt sweep publishes 0.855 forever against an honest 0.351 — a 2.4x overstatement.
   `_parse_model_link:266` actively pins it.
3. Two `provider_instrument_id`s sharing one `symbol` silently collapse to one feature row
   (`validation.py:97-99`); coefficients went to all-zero and Sharpe 6.43 to 3.28 with no error.
4. The FAILED-outcome guarantee breaks under lease contention: no terminal outcome is written, the
   original `MODEL_FIT_FAILED` is replaced by `EvidenceBusy`, and the store blocks all later trials.
   `LeaseManager.acquire` has no retry.
5. A legal large `l2_penalty` aborts the fit with a false `NON_FINITE_VALUE` — `ridge.py:169` emits
   `"-0"`, which the model then rejects as non-canonical. The same defect crashes the report for any
   score in `(-5e-13, 0)`.
6. A never-trading candidate publishes `deflated_sharpe_ratio = 0.5`: zero volatility forces Sharpe
   to 0 and fabricates kurtosis 3.0, ranking a degenerate model above every losing one.
7. `label_horizon_sessions` is never checked against `LABEL_HORIZON_SESSIONS_V1`, so a fold can
   declare a 1-session horizon to justify a 1-session embargo.

Blockers 1 and 2 and Major 2 are the same class of defect: each lets a bad model look good, which is
the specific risk this slice's governance exists to prevent.

### Not probed

Real crash/SIGKILL/disk-full injection, Slice 3 feature and point-in-time correctness, `net_return`
versus cost arithmetic, scale beyond 70 rows, Windows PID reuse in lease recovery, cross-filesystem
`os.replace`, second-architecture reproducibility, and whether Slice 5's holdout inherits Blocker 1.
These are open questions, not passes.

## Verifier outcome

Attempt 1 aborted on a usage limit. Attempt 2 returned **BLOCKED** — but on a very different basis
from the Red Team: **48 PROVEN, 0 DISPROVEN, 5 NOT TESTED**. Nothing in this document was shown to
be false. The verdict is BLOCKED only because the Verifier contract treats `NOT TESTED` as failing.
Full report: `.launch/reports/VERIFIER-SLICE-04.md`.

Every headline gate figure reproduced exactly: 272 tests, 5,830/660/88.68% coverage, 80 focused
tests, strict Mypy across 83 source files, `modeling` 1,667/194/88.36%, `evidence` 922/117/87.31%,
vulture clean at >=80 (120 findings at >=60, proving it actually scanned), zero secret candidates,
Code Craft 17 files, Test Craft 12 files, frozen install at 47 packages.

Every pinned replay identity reproduced character-for-character through a driver the Verifier wrote
itself against `run_persisted_ridge_trial` across two independent evidence roots — all three manifest
hashes, the fold spec, evaluation, feature and label dataset hashes, 18/8 rows, multiplicity 1,
deflated Sharpe `0.854984141908`, and all five baseline rows. Published files were byte-identical
across roots.

The honesty claims held under source inspection: zero `holdout` references in the modeling package or
Slice 4 tests; `RESEARCH_ONLY` is the only verdict value that exists, sits inside the hashed
evaluation payload (`validation.py:85`) so a substitute cannot hash-match, and is re-enforced on read
(`persisted_trials.py:267`); RIDGE carries `UNCALIBRATED_SCORE` while baselines carry `RULE` and are
forbidden a score (`metrics.py:55`); the string "probab" does not occur anywhere in Slice 4 source or
tests.

### The five NOT TESTED claims

| # | Claim | Why |
|---|---|---|
| 38 | Mutation checks — eleven mutations killed | Not re-executed; re-running a mutation requires editing source, which the Verifier's scope forbade. Corroborated but not proven. The Slice 3 Verifier *did* re-execute its mutations, so this pass is weaker there. The row above is restated as INHERITED. |
| 43 | Install root reports 208 formatted files | Install root off-limits. Superseded by the correction above. |
| 44 | Stated cause of the 208 vs 205 delta | Off-limits, **and unsound on its own terms**. Withdrawn and corrected above. |
| 45 | No untracked Python in the install root | Off-limits. Proven for the clone: 139 tracked `.py`, 139 on disk. |
| 53 | `main` is ahead of `origin/main` | Requires querying the install root. |

Four of the five are artefacts of walling the Verifier out of the install root — the correct
trade, since a verifier that reads a working tree three other agents are editing verifies nothing
reproducible. The fifth, the mutation row, is a real weakness relative to Slice 3 and is now labelled
as inherited rather than measured.

### Two findings beyond the adjudication

1. **No Slice 4 baseline existed in `.launch/COMMANDS.md` at `b24b4eb`** — it stopped at Slice 3, so
   the only baseline was the claim sheet under adjudication, which is not independent. Nothing
   failed, so nothing needed attribution, but the Verifier could not have separated pre-existing from
   new failures had one occurred. The baseline has since been added.
2. **`test_single_trial_dsr_retains_sampling_uncertainty` lives in `tests/test_multiplicity.py`**,
   which `scripts/run-slice4-gates.ps1` does not include in the focused Slice 4 suite. One of the
   eleven mutation guards therefore sits outside the focused gate, though it is inside the 272.

## Repair round

Underway in a separate session, which owns `src/**` and `tests/**`; this document owns `.launch/**`.
Every repair below began with a failing regression that reproduces the Red Team's documented attack.
The tracker is recorded here because the evidence sheet is where the slice's status is read from; the
authoritative detail lives in that session's work record.

| Finding | Status | Repair |
|---|---|---|
| Blocker 1 | CLOSED | A training label maturing at or after `validation_start` fails closed with `PARTITION_INVALID` |
| Blocker 2 | CLOSED | Strategy summaries re-derived from published decisions; a forged Sharpe of 99 is rejected. Mutation-killed |
| Blocker 3 | CLOSED | Staged resource verified before publish; metadata bounded against `max_manifest_bytes`; `bool` `schema_version` rejected at write time |
| Blocker 4 | CLOSED | `trial_id` may not end with the reserved `_outcome` suffix |
| Major 3 | CLOSED | An ambiguous `(candidate_id, symbol, decision_at)` fails `DATASET_INTEGRITY_INVALID` instead of letting the last row in sort order win. Mutation-killed |
| Major 5 | CLOSED | `_float_decimal` no longer emits non-canonical `"-0"` |
| Major 6 | CLOSED | A zero-variance return series fails closed rather than publishing a deflated Sharpe of 0.5 |
| Major 7 | CLOSED | `label_horizon_sessions` must equal `LABEL_HORIZON_SESSIONS_V1` |
| Minor 6 | CLOSED | A one-period fold fails closed with a typed code |
| Minor 7 | CLOSED | Fixed in this document: the deflated Sharpe is now labelled a probability wherever it is quoted |
| Major 1 | OPEN | Tail-deletion multiplicity rollback |
| Major 2 | OPEN | Deflated Sharpe frozen at the trial's own ordinal |
| Major 4 | OPEN | `FAILED`-outcome guarantee under lease contention |
| Minors 1-5 | OPEN | Crash-after-publish replay, caller-invented registry, `bool` in exact-int fields, metric precision, unbounded `dataset_id` |

New regression files added by the repair round: `tests/test_modeling_evidence_tamper.py` and
`tests/test_evidence_publish_atomicity.py`.

**No baseline is pinned at the current working tree.** It is green but incomplete, and the shared
checkout also carries unrelated uncommitted work under `src/quant_system/alpha/` that inflates the
repository test count. The gate table above still describes `b24b4eb`. When the repair round is
complete, the whole table will be re-measured from a fresh detached clone at the exact repair
revision, and only then may a Red Team recheck and an independent Verifier run.

## Evidence re-baseline

The Slice 4 work record pins 254 repository tests and 5,806 statements. Those figures no longer
reproduce. Commits `1148b99` and `ebded8c` (runtime data provenance) and `b24b4eb` (workspace
governance) landed after the final Slice 4 modeling commit `6a17d5e`, moving repository-wide counts
to 272 tests and 5,830 statements. No Slice 4 source file changed:

```text
git diff 6a17d5e..b24b4eb -- src/quant_system/modeling src/quant_system/evidence   # empty
```

The figures in this document supersede the work-record figures. The Verifier should reproduce
against `b24b4eb`.

## Outstanding before certification

1. Independent Red Team pass against `b24b4eb`, re-attacking the six Blockers repaired at `6a17d5e`:
   boolean-for-integer trial fields, unrecoverable interrupted model/outcome publication, deflated
   Sharpe ignoring sampling uncertainty and moments, contradictory dataset/fold order for multiple
   instruments, simultaneous instruments compounded as separate full-capital periods, and
   `SUCCEEDED` outcomes not resolving verified model evidence.
2. Independent clean-state Verifier pass adjudicating every claim in this document.
3. On two passes: set this file to `PASS`, add the Slice 4 row to `.launch/SLICES.md`, close G4 in
   `.launch/STATE.md`, and retire both Slice 4 work records.

`main` is ahead of `origin/main`. Push before any remote-based verification, or pin `b24b4eb` and
clone locally as Slices 1-3 did.

## Explicit limits

- No final holdout is opened and no promotion gate is evaluated; that is Slice 5.
- No score is called a probability. Brier and calibration do not apply in this slice.
- Exact numeric reproducibility is claimed only for the same verified architecture and lock file.
- The training journey is a synthetic fixture. It is not live-provider evidence and carries no
  claim about any traded instrument.
- Effective-dated official NSE fee and tax selection remains Slice 7; this slice consumes the
  immutable cost-bound labels produced by Slice 3.
