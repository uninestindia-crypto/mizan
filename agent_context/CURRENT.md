# Current QuantOS snapshot

UPDATED_UTC: 2026-09-14T11:31:00Z  
SNAPSHOT_OWNER: the gate table below was re-measured by Claude Code on founder instruction ("update
CURRENT.md with the test count"). **Only that table and this header changed.** `CURRENT.md` is
claimed by `20260820-codex-slice4-ridge-training.md` (ACTIVE) and `20260821-claude-ci-workflow.md`;
nothing either record wrote elsewhere in this file is altered, and no narrative section below was
re-verified by this pass. The 2026-09-11 reconciliation note it replaces said the same of its own
scope  
BRANCH: `main`  
HEAD_AT_SNAPSHOT: `cd57e5b0`

## Formal release state

Measured at `cd57e5b0`, not restated from another document.

| | State |
|---|---|
| Tier / phase | T2, P5 per `.launch/STATE.md` |
| Slices | All 12 CODE_COMPLETE |
| Tests | **1,519 passing**, forwards and in reverse file order |
| Static gate | Ruff lint and format clean across **671 files**; strict Mypy clean across **208 source files** |
| CI | **GREEN**, run `34836160971`, every step, 28m29s. See Major #1 |
| Live-money routing | Explicitly out of scope. Nothing has ever placed an order |

**Where the +46 tests came from.** The previous snapshot recorded 1,473 at `2e28d76e`. 29 were added
by `20260914-claude-paper-book-accounting-repairs.md` (12 entitlement-wiring, 13 portfolio-ledger,
4 trial-count). The remaining 17 predate that work and were added by other agents between `2e28d76e`
and `f43f4f62`; this pass did not attribute them further. The mypy surface grew 205 -> 208 with the
`research_short_horizon` and `research_xs_monthly` additions.

**This is a gate measurement, not a change of release state.** The phase contradiction recorded in
the next section is untouched and still unresolved, and no model became promotable. Read P5 exactly
as that section says to read it.

### The phase label and the adjudication record contradict each other

`.launch/STATE.md` records `PHASE: P5 (Release Certified)`, `G9 passed (Release Candidate Ready)`
and `Blocked on: Nothing`. The same file's adjudication section says **"Zero slices beyond 3 have a
valid independent adjudication."** Both cannot be true: a release cannot be certified on slices that
were never independently adjudicated.

That contradiction is recorded here rather than resolved, because `.launch/STATE.md` is claimed by
`20260821-0530Z-claude-slice4-certification.md` and the phase label is that owner's to change. Until
it is, **read P5 as "code complete and statically green", not as "certified"**.

What has genuinely been independently adjudicated, by an agent that did not write the code:

- Slices 1-3, per the original Red Team and Verifier passes.
- The **governed execution path** — Majors 4-9 rechecked, which found 2 P1 Critical and 1 P2 Major in
  the author's own repairs; Phase 2 closed all three. Verdict READY *within that scope only*.
- The **canonical feature window** (schema v2), rechecked twice, each pass finding a further defect
  that was repaired (`8f29564`, `88a7ac9`).

What has **not**: the training runner, the campaign driver, and every research result they produced.
`verdict=RESEARCH_ONLY` is the model's own label, not a certification.

## Open program-level majors, current

| # | Was | Now |
|---|---|---|
| 1 | CI workflow and branch protection | **GATE CLOSED 2026-09-11; branch protection still open.** The billing failure is gone -- runs execute normally. It was then red for a *different* reason for over a week, and that is now fixed too: run **`34570564419` passed every step in 26m18s**, the first fully green run since 2026-09-02 (35 of the 40 runs before it failed). Detail below. Branch protection remains impossible on this plan (`403 Upgrade to GitHub Pro or make this repository public`) and is the only part of this major still open |
| 2 | Craft baseline regressed ~4x | **Test-craft 100% clean.** 87/87 test files pass with 0 `sleep-in-test` flakiness risks and 0 unannotated loops. Code craft has 240 structural lines/nesting primarily in UI HTML templates |
| 3 | Provenance mechanism closed, artifact stale | **CLOSED.** Artifact rebuilt at `dab7f7b3`; 125 `quant_system` modules verified in archive, SBOM matches `uv.lock`, provenance binds HEAD |
| 4 | Capability claims exceed behaviour | **CLOSED.** Corrected at `5a0447b`; unsupported US Equities & Fundamental claims removed; honest boundaries established |

## Active work & coordination

- **91 active work records** (43 at the previous snapshot), 3 registered worktrees, 4 local branches.
  Multi-agent coordination remains live in `agent_context/`; assume any registered worktree or
  non-default branch is an agent whose claim you cannot see (PROTOCOL §8).
- **Two Claude Code sessions worked the same files simultaneously on 2026-09-10.** It was survivable
  only because both filed records and neither reverted the other; see "Concurrency" below for what it
  actually cost.
- 35 adjudication reports under `.launch/reports/`. One is **quarantined** as unreproducible —
  `.launch/reports/quarantine/README.md` — and nothing there may be cited as a passing gate.
- `CURRENT.md` is claimed by `20260820-codex-slice4-ridge-training.md` and
  `20260821-claude-ci-workflow.md`. The sections above were reconciled on explicit founder
  instruction; nothing those records wrote elsewhere in this file was altered.

## Corporate actions, 2026-09-10/11: two wrong premises, both measured and both corrected

This is the largest single correction in this file. It began as a paper-book loss and ended up
rewriting what "RAW bars" means in this repository. Both premises below were *my own*, stated to the
founder with confidence, and both were false. They are recorded in full because each was caught by
measurement rather than by any gate, and the gates would have passed either way.

### What started it: one unadjusted demerger cost a book more than its entire P&L

The XS-Monthly paper book showed a loss. The whole of it was one position:

| | Value |
|---|---:|
| Book gross return | **-0.2235%** |
| `HEG` leg alone (demerged 2026-09-07, quoted -64.3% overnight on 3.6M shares) | **-0.608 pp of NAV** |
| Book gross **excluding HEG** | **+0.4870%** |
| Legs positive | 57 / 99, median +0.597% |

The flagship Mizan book's loss over the same window was **not** a model failure either. Decomposed:
market -1.34 pp, fees -0.11 pp, and the model's own stock selection **-0.13 pp** — with the sign of
that selection term flipping depending on whether it is measured from the 08-31 open or close, which
is what "indistinguishable from zero" looks like at seven sessions.

### Root cause: the corporate-action authority could not see the event

`scripts/ingest_all_market_data.py` carried three compounding defects, repaired at **`ee1b0cb3`**:

1. `build_corporate_action_authority` hardcoded `effective_from`/`effective_to`/`publication_date`,
   so every dataset ingested on any date claimed coverage to 2026-08-21;
2. `fetch_or_load_corporate_actions` returned any existing file unconditionally, freezing a symbol's
   record permanently on first write;
3. every fetch failure wrote `[]`, which (2) then trusted forever — one network blip permanently
   poisoning a symbol.

Fixing (1) alone would have been *worse* than leaving it: the window would then have claimed to
cover today while holding weeks-old content. A provenance sidecar now records what was fetched and
when; freshness requires `status=FETCHED`, `effective_from <= start`, `effective_to >= end`, age
<= 24h. A failed fetch reports the window it can stand behind and retries next run.

All **3,359** all-market authorities were then re-pulled: 3,359 FETCHED, 0 stale, 0 unavailable,
window 2016-08-22..2026-09-10.

### Wrong premise 1 — "the bars are RAW, so every published action needs applying"

**False, and acting on it is destructive rather than merely useless.** The manifest's `status: RAW`
describes provenance, not arithmetic. Measured across the 423-name research universe: **212 of 212
published-ratio structural actions already show an ex-date gap of ~1.0** — the provider back-adjusts
splits and bonuses itself.

Applying the published ratio on top turned TATASTEEL's 10:1 split into a **+945%** day and BEL's into
**+952%**. A full feature-store rebuild on that logic would have silently corrupted every row, and
the corruption would have looked like signal.

It was caught by a **five-symbol smoke build**, before the full rebuild and before any ordinal was
spent. No gate would have caught it: 28 unit tests, ruff and mypy all passed, because they encoded
the same wrong premise as the code.

**The figure "250 structural actions pollute the training data, affecting ~59% of names" was given to
the founder and is withdrawn.**

### Wrong premise 2 — "a ratio-less action can be sized from its ex-date gap when the gap is big"

Also false, and found by the concurrent session rather than by me. A gap is the corporate action
*plus* whatever the market did that day, and nothing separates the two. On the real corpus that rule
would have inferred an **upward** correction for **NMDC (+71.0%), BAJAJELEC (+32.2%) and SCI
(+30.0%)** — a demerger cannot raise the parent's price, so those gaps are market movement, and
"correcting" them would have erased a genuine move *and* invented a fake one.

The contract now: score the ex-date gap against both provider hypotheses in log-return space and
apply a published ratio only when the data says it is missing; **never** size a ratio-less action
from price; accept one only when a caller validated it against independent evidence; treat dividends
as a return-definition choice rather than a repair. Anything unsized is reported **unresolved** and
consumers drop the window instead of publishing a fabricated return.

`scripts/validate_demerger_factors.py` attempts that independent validation via value-continuity
against the resulting company's first traded price. On this corpus it returns **0 validated /
56 refused** across 54 ratio-less actions. So demergers are currently handled by **exclusion, not
repair** — a stated limitation, not a solved problem.

### The A/B: correcting the data does not rescue the model

Ungoverned screen, **no evidence store written and no multiplicity ordinal spent**. Full evidence and
raw output: `reports/mizan_ab_screen/`.

| | Arm A — RAW | Arm B — corporate-action adjusted |
|---|---:|---:|
| Labels | RAW opens | adjusted, total return |
| Test rows (380 names) | 902,582 | 899,840 |
| Model: mean / t / Sharpe | +0.006528 / +5.86 / +0.60 | +0.007249 / +6.61 / +0.68 |
| Equal-weight: mean / t / Sharpe | +0.006550 / +6.80 / +0.69 | +0.007433 / +7.73 / +0.79 |
| **Selection edge** | **-0.000022** | **-0.000185** |
| **t** | **-0.07** | **-0.66** |

**Arm A reproduces the published `-0.000022, t = -0.07` to the digit**, which is what makes Arm B
interpretable rather than a statement about the harness. The edge stays negative and drifts slightly
further negative; neither figure is significant. Equal-weight beats the candidate in both arms, and
by more after correction. Fitted coefficients are stable across arms, every sign preserved
(`sma_20_distance` +0.008082 -> +0.008177, still the only positive of eight): **no signal was being
masked by bad corporate-action handling.**

Both absolute levels rose (+0.65% -> +0.72% per period) purely from the dividend add-back in the
total-return basis. It lifts model and benchmark together and cancels in the difference, which is why
the selection edge is the number to read and the absolute return is not.

**Conclusion: do not spend the ordinal on a governed retrain of this candidate.** It would publish
another `RESEARCH_ONLY` model to reproduce a null now established on ~900,000 test rows per arm.

### A cost figure given to the founder, corrected

The governed Mizan retrain costs **one** multiplicity ordinal, not the "~50" first reported here in
conversation. That figure came from the old per-instrument campaigns (51, then 50 trials, one ordinal
per name). `scripts/train_mizan.py` is a single pooled study.

Records: `20260910-claude-corporate-action-authority-refresh-cadence.md`,
`20260910-claude-corporate-action-adjustment-and-mizan-retrain.md`, and the NOTICEs dated 2026-09-10.

## CI: green for the first time since 2026-09-02

The billing failure recorded under Major #1 is **gone**. It was then red for a different reason for
over a week, and that reason mattered more than it looked:

**`Ruff format` is step 2 of the workflow, so its failure skipped `Strict mypy` and both test steps.**
The repository was not failing a lint check — **it was running no tests at all**, including on the
commits pushed during that window.

| Gate | Before | After |
|---|---:|---:|
| `ruff format --check .` | 12 files | **633 formatted, 0 failures** |
| `mypy src launcher.py scripts` | 41 errors, 13 files | **Success, 205 files** |
| `pytest tests/ -q` | never reached in CI | **1,473 passed** |
| `pytest` reverse file order | never reached in CI | **1,473 passed** |

None of the 41 mypy errors were defects: 24 bare `dict` generics, 5 optional dependencies imported
inside guarded functions and deliberately absent from the lock file, 5 suppressions mypy no longer
needs on `windows-latest`, and 7 `sys.stdout.reconfigure` / `json.loads` `Any`-returns. The suite
passed at 1,473 forwards and backwards before and after; the baseline moved 1,455 -> 1,473 during the
work because the concurrent session added 18 tests.

Every failing path belonged to another agent's claim, so the repair was made only after explicit
founder instruction. Record: `20260910-claude-ci-gate-green.md`. Notice:
`20260910-NOTICE-ci-gate-red-blocks-all-verification.md`.

**Branch protection is still not possible on this plan** and remains the open half of Major #1.

## Concurrency: two sessions, same files, one afternoon

Recorded because it is a live operational risk, not a historical curiosity.

Two Claude Code sessions worked `corporate_actions.py`, `build_mizan_feature_store.py` and
`screen_mizan_out_of_sample.py` simultaneously on 2026-09-10. `corporate_actions.py` was rewritten
three times inside one 45-second observation window. What it cost, concretely:

- A 25-minute screen run died on `ValueError: not enough values to unpack` because the module's
  return signature changed mid-run.
- A feature-store rebuild died at exit 1 for the same reason.
- One session's uncommitted repairs were swept into the other's commit (`6131d84a`), so the CI fix
  is in the history under a commit whose message does not mention it.

What made it survivable: both sessions filed records, neither reverted the other, and the second
session's work was **better** — it caught wrong premise 2 and fixed a `MemoryError` that had killed
two rebuilds. PROTOCOL §8 worked as designed; the cost was wasted compute, not lost work.

**The lesson for the next founder instruction that spans sessions:** ownership resolves *who may
edit*, but it does not make concurrent edits to one file safe. A separate worktree is the only real
lock.

## The research result, in one line

Two governed campaigns totalling 101 trials and seven pre-declared screens found **no edge that
survives real costs**. Best deflated Sharpe 0.398 against a 0.95 gate. The detail is below; the
summary is that the platform works and the strategy does not.

## Real-data training runner (added 2026-08-22)

`scripts/run_governed_ridge_training.py` is the first production caller of the governed training
stack. Until it existed, `run_persisted_ridge_trial()`
(`src/quant_system/modeling/training_evidence.py:131`) had no caller outside tests — the stack was
implemented, tested, and unreachable. The runner chains real Upstox acquisition ->
`build_feature_dataset` -> `build_label_dataset` -> `build_purged_fold` ->
`run_persisted_ridge_trial` -> `EvidenceStore`. It imports no data generator, so it has no synthetic
fallback to take.

Status by stage. **All seven stages have now executed on real market data.**

| Stage | Status | Evidence |
|---|---|---|
| 1. Real Upstox acquisition | **PROVEN** | **498 real daily bars** for `NSE_EQ\|INE009A01021` (INFY), 2024-01-01..2025-12-31 |
| 2. Session calendar | PROVEN on the provider-derived path | 498 sessions derived from the exchange dates actually returned |
| 3. Governed re-acquisition | **PROVEN** | 498 bars, `status=ACCEPTED`, `source_status=COMPLETE` |
| 4. `build_feature_dataset` | **PROVEN** | 478 feature rows |
| 5. `build_label_dataset` | **PROVEN** | 476 label rows; real NSE statutory costs, 0.224% round trip |
| 6. `build_purged_fold` | **PROVEN** | train=411, validation=63, embargo=2 |
| 7. `run_persisted_ridge_trial` | **PROVEN — both paths** | Trials 1-2 published a terminal `FAILED` outcome (`DEGENERATE_RETURN_SERIES`); trial 3 published `SUCCEEDED` with full model evidence |

Corporate-action authority: `data/authorities/nse-corporate-actions-INFY-20240101-20251231.json`,
fetched from the NSE public API, 5 real records (dividends 2024-05-31, 2024-10-29, 2025-05-30,
2025-10-27 and the 2025-11-14 buyback), all ISIN `INE009A01021`. SHA-256
`650bd8197d8c1ac39e1c6b1f2469d96ee88e468384f07b1b3df83987544cb400`. Committed so the hash is
re-verifiable from the repository.

### Three trials. The model trains, and it loses money.

| Trial | Ordinal | Threshold | Validation | Outcome |
|---|---:|---:|---:|---|
| `trial_real_001` | 1 | `0` | 8 | `FAILED` — `DEGENERATE_RETURN_SERIES` |
| `trial_real_002` | 2 | `0` | 63 | `FAILED` — `DEGENERATE_RETURN_SERIES` |
| `trial_real_003` | 3 | `-0.1144` | 63 | **`SUCCEEDED`** — model evidence published |

Trial 3 result, `model_06ae80823d3b66ac8405b9eb`, 315 attributable decision records,
`verdict=RESEARCH_ONLY`, `multiplicity_count=3`:

| Strategy | Sharpe | Accuracy | Trades | Max DD |
|---|---:|---:|---:|---:|
| **RIDGE (the candidate)** | **-0.704** | 0.524 | 22 | 0.060 |
| NO_TRADE | 0.000 | 0.587 | 0 | 0.000 |
| BUY_AND_HOLD | -0.547 | 0.413 | 63 | 0.068 |
| PREVIOUS_SIGN | **+0.144** | 0.556 | 26 | 0.064 |
| EQUITY_DUAL_MOMENTUM | -3.684 | 0.397 | 42 | 0.139 |

**The candidate is the second-worst strategy on the board.** Its Sharpe is negative. It is beaten by
doing nothing, by buy-and-hold, and by a trivial repeat-the-previous-sign rule — the only baseline
with a positive Sharpe. Its 52.4% accuracy is below the 58.7% obtained by never trading: it trades
22 times and destroys value doing so.

`deflated_sharpe_ratio = 0.120566231116`. **This is a probability, not a Sharpe** — the
multiplicity- and sampling-adjusted probability that the true Sharpe beats the selection benchmark,
deflated against all three attempts. `GatePolicyV1.min_deflated_sharpe` defaults to `0.95`, so this
fails `GATE_DEFLATED_SHARPE` by a wide margin. Nothing here is promotable and the machinery reports
that itself.

**Honest reading: this six-feature ridge has no edge on INFY over 2024-2025 after real statutory
costs.** Trials 1-2 could not measure that because the candidate never traded; trial 3 made it
legible. The threshold change bought a measurable result, not a good one — the same underlying
finding either way.

Caveat that must travel with these numbers: the trial-3 threshold `-0.1144` was chosen as the
training-partition mean target (train-only information, consistent with train-only preprocessing),
but it was chosen **after** the trial-1/2 diagnostic had already revealed the validation score
distribution. It is an informed choice, not a blind one. That is precisely why it carries ordinal 3
and deflates against three attempts. Do not sweep further thresholds hoping for a publishable
number; a fourth attempt inherits ordinal 4 and a harsher deflation, and the evidence above does not
suggest one is warranted.

Root cause of the trials 1-2 degeneracy, measured rather than inferred:

- Targets are encoded UP `+1.0` / DOWN `-1.0` (`modeling/ridge.py:93`).
- The real label balance is 182 UP / 229 DOWN in the training partition, so the mean target is
  `-0.1144` and the fitted ridge intercept is `-0.114355` — they agree to five decimals.
- Validation scores over 63 sessions span `[-0.243, -0.026]`, mean `-0.140`, stdev `0.053`. The
  **maximum score is still below the `score_threshold=0`**, so the candidate predicts UP zero times
  out of 63 and takes no position at all.
- `_portfolio_period_returns` (`modeling/validation.py:402`) only records a return where
  `predicted_target == "UP"`, so every validation period is exactly `0.0`, variance is zero, and the
  deflated Sharpe is undefined.

This is **not a defect in the runner and not a defect in the model**. It is the guard behaving as
documented: it refuses to publish a probability of 0.5 for a candidate that never traded, which
would otherwise rank a do-nothing model above every genuinely losing one.

### NIFTY 50 campaign — 51 trials, nothing promotable

`scripts/run_universe_ridge_campaign.py` ran the same governed trial across all 50 real NIFTY 50
constituents, 2024-01-01..2025-12-31, into the same evidence store as the three INFY trials.
Universe authority is the real NSE constituent list
(`data/authorities/nse-nifty50-constituents.csv`); membership is genuinely enforced against it by
`modeling/features.py:135`. Every instrument used one pre-declared rule — threshold = that
instrument's own training-partition base rate, train-only information, no per-name tuning.

**Campaign totals: 51 trials, `multiplicity_count = 51`, 40 published models, 11 terminal
`FAILED` outcomes (10 `DEGENERATE_RETURN_SERIES`, 1 `TRIAL_EXECUTION_FAILED`), 2 instruments
skipped for having no NSE corporate-actions record (ETERNAL, M&M).**

| Statistic | Value |
|---|---:|
| Published models | 40 |
| Positive Sharpe | **14 of 40** |
| Median Sharpe | **-1.1791** |
| Mean Sharpe | -0.7756 |
| Best / worst Sharpe | +4.3143 (GRASIM) / -5.7716 (APOLLOHOSP) |

How often the candidate beat each baseline on Sharpe, across the 40 published models:

| Baseline | Ridge wins | Baseline median Sharpe |
|---|---:|---:|
| BUY_AND_HOLD | 28 / 40 | -1.8756 |
| EQUITY_DUAL_MOMENTUM | 26 / 40 | -2.2591 |
| PREVIOUS_SIGN | 20 / 40 | -1.1549 |
| **NO_TRADE** | **14 / 40** | +0.0000 |

The candidate beats doing nothing on 14 names out of 40 — the wrong side of a coin flip.

**The deflation is what matters here.** GRASIM is the best name at Sharpe +4.3143, and its *published*
DSR is `0.696673`, which read alone looks close to promotable. Re-deflated against the final attempt
count of 51 it is `0.397794`. The gate `GatePolicyV1.min_deflated_sharpe` requires `>= 0.95`. It was
never close; the published figure was an artifact of being scored while the campaign was still open,
exactly as `campaign_deflated_sharpe_ratios` documents.

**Best campaign DSR across all 51 trials: `0.397794`. VERDICT: NONE PROMOTABLE.**

Two properties of the winners are worth recording, because they are how a sweep manufactures a
false positive. First, the top names trade almost nothing — GRASIM 9 trades, TECHM 4, BHARTIARTL 3,
TCS exactly 1 — so those Sharpes rest on a handful of decisions. Second, searching fifty names finds
the tail of a noise distribution by construction, which is the precise thing deflation exists to
discount. Neither observation requires believing the model has no edge; both mean this evidence
cannot establish that it does.

**Survivorship warning on the summary statistics above.** They cover the 40 *published* models. The
10 degenerate names are excluded — and they became degenerate by declining to trade, which on this
evidence was the better decision. The honest denominator is 50, not 40; the table flatters the
candidate by dropping its most conservative outcomes.

### Defect raised by this campaign — now CLOSED

`agent_context/work/completed/20260822-NOTICE-dsr-two-point-boundary-crash.md`. A two-point
validation return series sits on the `kurtosis >= skewness**2 + 1` boundary in
`analytics/multiplicity.py`, where an uncaught `ValueError` that no caller could type-match was
decided by floating-point rounding. One NIFTY 50 constituent hit it and it killed the whole sweep.

Sharpened during triage by a peer session: for **any** two-point distribution
`kurtosis - skewness**2 = 1` is an *exact algebraic identity*, with equality iff two-point. The guard
therefore tested a strict inequality against an exact tie for a whole legitimate class of input,
which makes a tolerance the correct implementation of the constraint rather than a workaround.

It was also worse than first reported, and the reason is now provable rather than suggestive.
Measured against the pre-repair condition over p = 0.01..0.99, **39 of 99 two-point series would
have fired — roughly 40% of that legitimate parameter space**, not a rare tie.

Measurements across different constructions gave 31, 34, 36, 37 and 39 firings out of 99, with
firing sets overlapping only about half. The decisive argument: skewness and kurtosis are location-
and scale-invariant, so the same distribution written as `[0, 1]` or as `[-3.5, 11.25]` has
mathematically identical moments — verified equal in **99 of 99** cases by two independent
implementations — yet the guard rejected substantially different sets of them. A transformation that
provably cannot change the mathematics changed which inputs were rejected, which proves the
rejection was decided by float residue in the arithmetic path rather than by anything about the
distribution.

**Cite the proportion and the mechanism, never a specific p, and nothing finer-grained than that.**
Two lessons were learned the hard way here and are recorded in full in the notice:

- A count of *bit-identical* moment pairs was briefly cited as the headline evidence (8 of 99).
  A peer's independent implementation of the same experiment gave 39 of 99. Only the mathematical
  equality reproduces across implementations; the bit-identical count is a property of an arithmetic
  path, exactly like every firing list. Withdrawn.
- A generous explanation of an earlier p=0.10 error — that it "was correct for an unpinned
  construction" — was withdrawn at the peer's own insistence. The observation is true but was not
  the cause: they evaluated `kurt - skew**2` against 1 rather than the guard's
  `kurtosis < 1.0 + skewness**2`. Recording luck as cause would have put a false causal story into
  three records.

**Repaired at `ac47d7c`** by another agent, and independently verified by the filer, who did not
write the repair: the guard now compares with a tolerance of `64 * sys.float_info.epsilon` and raises
a typed `MultiplicityError(MOMENT_CONSTRAINT_INVALID)`. The case previously rejected (29 zeros plus
one 0.05, `kurt - bound = -7.105e-15`) is accepted; genuinely impossible moments (skew 2.0,
kurt 1.0) are still refused. The tolerance admits the exact-tie class without admitting real
inconsistency.

Trail note recorded by a peer, observation rather than accusation:
`20260820-codex-slice4-ridge-training.md` still reads `STATUS: ACTIVE` and still lists
`analytics/multiplicity.py` among its owned paths, so the file changed under a claim never formally
released.

### Limitations stated rather than resolved

- **This is not a portfolio.** The governed dataset contract is single-instrument
  (`modeling/labels.py:135`), so the campaign is 40 independent single-name studies, not one
  cross-sectional strategy. `_portfolio_period_returns` (`validation.py:402`) averages decisions
  sharing a `decision_at` and would support a portfolio, but nothing can build a multi-instrument
  dataset to feed it. Closing that needs `modeling/**` changes.
- The session calendar, absent `--calendar-file`, is derived from provider data, so a provider that
  silently omits a trading day yields a calendar agreeing with its own gap.
- Neither Red Team nor an independent clean-clone Verifier has adjudicated the training runner, the
  campaign driver, or any of these research results. The governed *execution* path has since been
  independently adjudicated — see the next section — but these training numbers have not.

Full record: `agent_context/work/completed/20260822-claude-real-data-training-runner.md`.
Outstanding work: `agent_context/handoffs/20260822-claude-real-data-training-runner-handoff.md`.

## Governed execution path (added 2026-08-23/24)

The system that executed was not the system that was validated. Verified at `9789fd4`: nothing
outside `modeling/` consumed `RidgeFittedStateV1`, `ModelCardV1` or `predict_ridge_scores`;
`execution/` and `server/` imported nothing from `modeling/`; and `strategies/ml_equity.py:17`
carried `RollingRidgeClassifier`, a second ungoverned ridge with no purging, multiplicity or
evidence — the one execution actually used. Every governed guarantee in `.launch/` described code
that no live path called.

| Commit | What landed |
|---|---|
| `9789fd4` | **Nothing loaded `.env`.** No `python-dotenv`, no `load_dotenv` anywhere in `src/`. `UpstoxClient`, `provenance` and `alpha/key_pool` all read `os.getenv`, so a correctly filled `.env` was invisible and every run failed `PROVIDER_UNAUTHORIZED` before issuing a request. Dependency-free loader, wired at the launcher entry point |
| `11ee334` | Governed adapter: `PromotedModelBundleV1`, `GovernedModelStrategy`. Long-only, because that is what `validation.py` measured; the threshold travels with the bundle and never defaults to zero. Training kernels promoted to public so training and execution share one implementation |
| `e6f42b1` | Point-in-time bar history supplied to the shadow engine, default off |
| `9470d97` | Maturity horizon, so a two-session model cannot open and close inside one session |
| `1e5beb5` | Real governed shadow session attempted against the real evidence store |
| `97fcc4b` | Red Team Blockers 1 and 3 repaired |
| `deccec1` | Red Team Majors 4-9 repaired |
| `85ff535` | The ungoverned ridge refused at the execution surface — second calculation path closed |

### This path is adjudicated. The research results are not.

This is the first work in this repository carrying an independent verdict rather than its author's.

**Blockers 1 and 3** both landed on judgment calls the author had defended in writing. B1: a bundle
accepted the best model's card paired with the worst model's coefficients, because `candidate_id` was
doing the binding and all 51 campaign trials share `cand_ridge_v1`. B3: the adapter reimplemented
scoring in Decimal and disagreed with `predict_ridge_scores` by 4e-13, flipping a decision at the
threshold. Repaired by binding the bundle to one published manifest through `ModelEvidenceIdentityV1`,
and by calling the validated scorer rather than a parallel one.

**Majors 4-9** were repaired at `deccec1`, then **independently rechecked, which broke them**: 2 P1
Critical and 1 P2 Major. The sharpest is instructive — the author's symbol binding checked the
`extra_data` map *key* but not each bar's own `PointInTimeBar.symbol`, so bars whose symbol was
RELIANCE passed under the key INFY. The author bound the label, not the data. Phase 2 closed all
three; verdict **READY within the governed-execution Majors 4-9 scope**, explicitly not authorising
live-money routing, promotion, or legacy model execution. Reports:
`.launch/reports/RED-TEAM-GOVERNED-EXECUTION-MAJORS-4-9-RECHECK.md` and `-PHASE2.md`.

### Feature schema v2, and what it costs the existing evidence

The remaining Blocker was that feature values depended on how much history was supplied: Wilder
RSI-14 and ATR-14 seed at the start of the sequence, so training's expanding prefix and execution's
retained prefix produced different values for the same decision bar. Adopted in
`agent_context/decisions/20260824-canonical-feature-window.md`: **schema v2 consumes exactly the
trailing 21 point-in-time-available bars**, enforced at the shared kernel boundary so the two sides
cannot diverge by accident. Its own recheck then found two further defects, both repaired — the
exported evaluator omitted the schema match (`8f29564`), and the exported kernel accepted reverse
chronology (`88a7ac9`).

**Consequence, stated plainly: all 40 published models are pre-v2.** They remain auditable historical
research evidence but cannot execute. `scripts/run_governed_shadow_session.py` refuses the selected
GRASIM artifact with typed missing-schema detail and exit 3. Those fitted states would have to be
retrained under v2 before any of them could run.

### Retrained under feature schema v2 — still nothing promotable

The v2 retraining is **done**, by another agent, and independently verified here from the evidence
store rather than from its record. Store:
`data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound-v2`, 50 published
models, every one carrying `('quantos.ridge_technical_six', 2)`.

| | v1 campaign | **v2 campaign** |
|---|---:|---:|
| Published models | 40 | **50** |
| `multiplicity_count` | 51 | **50** |
| Positive Sharpe | 14 of 40 (35%) | **21 of 50 (42%)** |
| Median Sharpe | -1.1791 | **-0.2278** |
| Mean Sharpe | -0.7756 | **-0.6834** |
| Best / worst | +4.3143 / -5.7716 | **+3.2207 / -5.2615** |
| Best campaign DSR | 0.397794 | **0.217695** |
| Verdict | NONE PROMOTABLE | **NONE PROMOTABLE** |

**The honest reading is that v2 is a better measurement of the same absence of edge.** The
distribution is markedly better centred — the median name loses 0.23 instead of 1.18, and 42% beat
zero instead of 35%. But the *best* name is further from promotable than before: 0.2177 against
0.3978, both against a 0.95 gate.

Those two movements are consistent rather than contradictory, and the reason matters. Schema v1's
window dependence let the same decision bar take different feature values depending on how much
history happened to be retained, which is noise. Removing it tightened the distribution and shrank
the tails — and the v1 best case sat in that tail. Some of what made GRASIM look strong under v1 was
the artifact, not the model.

So the six-feature ridge has now been tested on this universe under both a defective and a corrected
feature computation, and has no edge under either. That is a real finding, and it is a stronger one
than the v1 campaign alone supported.

**Do not re-run this.** A repeat would spend 50 fresh multiplicity ordinals, produce no information
that these 50 trials have not already produced, and make any future candidate harder to promote.

Record: `agent_context/work/completed/20260824-1216Z-codex-nifty50-ten-year-v2-training.md`
(`STATUS: RETIRED_RESEARCH_ONLY`).

### A different feature family was screened, and is worse (2026-08-24)

Three pre-declared research screens against the real cached ten-year NIFTY 50 data. **No
`EvidenceStore` written, no multiplicity ordinal spent, no model published — not governed evidence.**
Recorded anyway, because an unrecorded search is invisible multiplicity to whoever screens the same
family next.

| Screen | Result |
|---|---|
| New family: gap, close-location, range expansion, volume z, dollar-volume, price position | mean IC +0.00732, **t = 1.08**, 31/50 positive |
| **Control: the existing v1/v2 close-only six** | mean IC +0.01556, **t = 2.34**, 35/50 positive |

**The new family is worse than the one that already failed.** That is the direct answer to trying a
different feature set: tried, pre-declared, no improvement.

The control was more informative than the thing it controlled for. The existing family has a
*detectable gross* signal yet produced nothing promotable in 101 governed trials, with best-name
gross edge about 0.2% against a 0.224% round trip. That suggested "edge roughly equal to cost", which
predicts that a longer hold should turn net edge positive as the fixed cost amortises. Tested on a
pre-declared grid, labels net of cost:

| Hold | t(IC) | Mean net return | t(net) |
|---:|---:|---:|---:|
| 2 | +2.34 | -0.002100 | -13.57 |
| 5 | +0.60 | -0.001900 | -3.72 |
| 10 | +0.44 | -0.002117 | -1.99 |
| 21 | +0.93 | **-0.000264** | **-0.13** |

Net return climbs toward zero as cost amortises but **never turns positive**; at hold 21 it is
indistinguishable from zero. The diagnosis is falsified: removing the cost drag revealed nothing
underneath, so the gross signal at hold 2 is most likely short-horizon microstructure that does not
survive as tradeable return.

**Nothing here justifies feature schema v3.** Extending the governed contract for a family the cheap
test already rejects would spend engineering and multiplicity on a dead hypothesis — which is why the
screen came before the governance work rather than after it.

One correction recorded in full: the first run of screen 1 reported t = 1.53. The cache holds two
DATASET resources per symbol and counting both doubled n, shrinking the standard error by sqrt(2). A
40% inflation of my own headline number from a bookkeeping artifact, in a screen whose purpose was
scepticism.

What would justify another look is **not** another feature family on the same data. Every attempt so
far shares one frame: single-instrument, daily, long-only, 2-21 sessions. A genuinely different
attempt changes the frame — a cross-sectional design ranking names against each other — and the
governed dataset contract cannot currently express it (`modeling/labels.py:135` is
single-instrument). That is a modelling-contract change, not a feature change.

Record: `agent_context/work/completed/20260824-claude-alternative-feature-screens.md`.

### Cross-sectional screen — the first positive point estimate, and it is not a result

The one frame never varied across 101 governed trials and three screens: model each name alone,
long-or-flat on its own score. A cross-sectional design ranks names against each other on the same
date, cancelling the market factor. Screened, pre-declared, both holds reported. **Not governed
evidence** — no store written, no ordinal spent.

| Hold | Construction | Mean net | t | Sharpe | Rebalances |
|---:|---|---:|---:|---:|---:|
| 2 | long top 10 | -0.000868 | -1.09 | -0.70 | 307 |
| 2 | long-short (diagnostic) | -0.003505 | **-5.68** | -3.64 | 307 |
| 21 | **long top 10** | **+0.009365** | **+1.18** | **+0.76** | **29** |
| 21 | long-short (diagnostic) | +0.007606 | +1.04 | +0.67 | 29 |

At a monthly horizon this is the first positive point estimate in the whole line of work. It is
**not** a result, for three reasons stated together so it cannot be quoted as one:

- **Not significant.** t = 1.18 on 29 rebalances. Reaching t = 2.0 at the same effect size needs
  about 83 — roughly **4.5 more years** of non-overlapping periods than the ten-year cache holds. No
  re-slicing of this data creates the missing years.
- **The strongest number in the grid says it loses.** Hold-2 long-short is t = **-5.68**, five times
  more significant than the hold-21 positive. Reading the +0.76 while ignoring that is cherry-picking
  by horizon.
- **The sign flips with horizon**, which is the signature of noise rather than a stable effect.

**The asymmetry being refused:** the prior record stopped after three negative screens and argued
stopping was disciplined. That argument does not expire because a result finally came out positive.
Stopping on negatives and continuing on a positive is precisely how false positives are manufactured
— the same mechanism as "iterate until satisfied" in a better hat.

This does **not** justify building a multi-instrument governed dataset contract
(`modeling/labels.py:135` binds each feature row to one acquisition manifest, so the change reaches
the dataset, label, fold and evidence-identity paths). The case for that work would rest on a t
of 1.18.

What it does change is the ranking of untried directions: every single-name variation is flatly
negative, while the cross-sectional frame at a monthly horizon is merely **inconclusive**. If another
attempt is wanted, this is the direction with the least bad evidence — and the correct next step is
**more independent data**, a different universe or market or a genuine out-of-sample period, not more
looks at these ten years.

Search accounting: six pre-declared configurations have now been screened against this cached data
outside the governed store. All recorded so a future campaign can price the search that preceded it.

Record: `agent_context/work/completed/20260824-claude-cross-sectional-screen.md`.

### The cross-sectional result did not replicate on 8.5x the universe (2026-08-25)

The all-market cache (3,267 currently-listed NSE symbols, 4.6M bars, ingested by another agent)
made the test possible that the cross-sectional t = 1.18 needed: more independent data rather than
more looks at the same fifty names.

**A defensible universe had to be built first.** The raw cache is not usable as delivered — 437 SME
names whose liquidity cannot support the 0.224% cost model, 19 under surveillance, 22% of the market
with >5% circuit-locked days, and only 1,289 of 3,267 with a full ten-year history.
`scripts/build_research_universe.py` applies a declared filter (>= 9.5y history, median daily
turnover >= Rs 5 crore, SME and PCA excluded) giving
`data/authorities/nse-research-universe-liquid-10y.csv`, **423 names**.

The configuration was carried over unchanged. The only translation was holding the selection
*fraction* at the top 20% rather than the absolute top 10, so a 423-name universe is not silently
made 8x more selective.

| | 50 names | **423 names** |
|---|---:|---:|
| hold 21, long-only Sharpe | **+0.76** | **+0.12** |
| hold 21, long-only t | +1.18 | **+0.19** |
| hold 21, long-short mean net | +0.007606 | **-0.006449** |
| hold 21, cross-sectional IC | +0.04494 | **-0.02212** |
| hold 2, long-short t | -5.68 | **-7.85** |

**The positive vanished.** Sharpe fell from +0.76 to +0.12, t from 1.18 to 0.19, and both the
long-short return and the cross-sectional IC flipped sign. **The one thing that replicated is the
loss:** hold-2 long-short went from t = -5.68 to **-7.85**. Getting stronger with more data is what a
real effect looks like, and the real effect is that this strategy loses at short horizons.

**Read this as a strong negative, not an inconclusive one.** The universe is survivorship-biased by
construction — active listings only, so companies that delisted inside the window are absent. That
bias pushes in the strategy's favour, and it failed anyway. A negative under a favourable bias is
stronger than a negative under a neutral one. The bias is documented in the universe file header
because it cannot be corrected from this cache.

This closes the last untried direction. Across 101 governed trials and seven screens, no variation of
this model class on this market has survived contact with more data.

Record: `agent_context/work/active/20260825-claude-expanded-universe-authority.md`.

### The second calculation path is closed (`85ff535`)

`strategies/ml_equity.py` defines `RollingRidgeClassifier` — a ridge with no purging, no
multiplicity accounting and no evidence. Measured before deciding: it was **not wired** into any
live surface. Both server paths (`app.py:670`, `supervisor.py:157`) run `BacktestEngine` over
`SyntheticDataGenerator`, which is research; `PaperPilot` takes no strategy; `ShadowReplayEngine`
takes a `ShadowDecisionModel`. The one reachable execution surface was `RealtimeShadowRunner`, which
accepted any `BaseStrategy` with no guard — so an operator could run the ungoverned ridge in a
shadow session.

**Blocked at the surface rather than deleted.** Deleting the classifier would break
`AIEnhancedMLEquityStrategy`, which the advisory layer wires into, and would remove a legitimate
research capability. An ungoverned ridge in a backtest is research; the violation is that it could
*execute*. So both ungoverned strategies declare `research_only = True` and the shadow runner
refuses anything so marked. Research, backtest and registry paths are untouched — verified by
demonstration, not assertion.

Residual, stated rather than hidden: this reads a **declaration, not a detector**. A future strategy
that embeds an ungoverned model without declaring it will not be caught. The bounded guarantee is
that the two known ungoverned-ridge strategies can no longer reach a shadow session.

Record: `agent_context/work/active/20260824-claude-remove-ungoverned-ridge-from-execution.md`.

### Still not true

- **No governed shadow session has ever run.** The runner reaches the promotion gate and is refused:
  every published model is `RESEARCH_ONLY`, and the best campaign DSR is `0.397794` against a `0.95`
  requirement. Promotion is not a wiring problem and cannot be fixed by wiring.
- ~~`RollingRidgeClassifier` is still what execution uses by default.~~ **Closed at `85ff535`** —
  see below.
- Shadow P&L does not equal backtest P&L. The validated label enters and exits at session *opens*
  while the runner fills on quotes; the maturity horizon closes the structural gap, not the pricing
  one.

Records: `agent_context/work/completed/20260823-claude-redteam-repair-b1-b3.md`,
`20260822-claude-governed-execution-adapter.md`, `20260822-claude-maturity-horizon.md`,
`20260822-claude-dotenv-loading.md`, `20260823-claude-real-governed-shadow-session.md`.

## In flight, not reconciled here (2026-09-11)

A concurrent session is running a **short-horizon program** under
`20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (ACTIVE): holds {1,2,3},
QuantOS model versus `google/timesfm-3.0-pytorch` zero-shot, with a trial ledger **frozen before any
result was seen** (`reports/short_horizon/TRIAL-LEDGER.md`, 6 published trials + 1 calibration grid).
Governed Mizan retrain trials `trial_mizan_h11_002` and `_003` exist in
`data/evidence/models/mizan-v1/trials/`.

**None of its results are restated in this file, because this snapshot's author did not verify them.**
Read that record and its reports directly; do not cite numbers from them as reconciled state until
someone has checked them. The ledger's own rule applies: a trial not listed there cannot be added
after a result is seen.

One caveat carried forward from the TimesFM assessment, which is a licensing fact rather than a
measurement: `timesfm-non-commercial-license-v1.0` permits research and **prohibits production
deployment and revenue generation**. A commercial licence from Google is a separate grant. Any
QuantOS path toward live money cannot route through those weights as licensed.

## Reference development machine

- ASUS Vivobook 14 X1407QA, Windows 11 ARM64.
- Snapdragon X X1-26-100, 8 cores/8 threads, approximately 3.0 GHz.
- 16 GB LPDDR5X-8448 RAM; 512 GB WD NVMe SSD.
- Current QuantOS virtual environment: CPython 3.13.15.

## Next safe actions

**Research is closed, and that is a conclusion rather than a pause.** 101 governed trials and seven
pre-declared screens found no edge that survives real costs. The last untried direction — the
cross-sectional frame — was tested on 8.5x the universe and did not replicate. Do not open a new
campaign on this model class and this market without genuinely new information; every additional
attempt raises the multiplicity bar for whatever comes next.

Engineering, in priority order:

1. **Decide branch protection** — the only part of Major #1 still open, and it needs the founder.
   The billing failure is fixed and the gate is green (run `34570564419`), but branch protection
   returns `403 Upgrade to GitHub Pro or make this repository public`; the repository is `private`,
   plan `User`. That is a paid-plan decision or a disclosure decision, not an engineering one. See
   `20260826-NOTICE-branch-protection-unavailable-on-plan.md`.

   **Keep the gate green.** It was red for over a week on `ruff format` alone, and because that is
   step 2, *no tests ran at all* in that window. A red format check is not cosmetic here; it silently
   disables verification for every agent.
2. **Independently adjudicate the training path** (largest remaining evidence gap). The brief is
   written at `.launch/ADJUDICATION-BRIEF-TRAINING-PATH.md`. It must be run by an agent that did not
   author the training runner or the campaign driver.
3. **Craft baseline** (Major #2), still open at 207 code / 33 test findings. The 8 `sleep-in-test`
   findings in `tests/test_server_supervisor.py` are the urgent subset: they are a flakiness risk to
   every gate measurement, which makes every other number in this file slightly less trustworthy.
4. **Coordinator items on `.launch/STATE.md`**, which this file cannot change because that path is
   claimed elsewhere:
   - Resolve `PHASE: P5 (Release Certified)` against the same file's "Zero slices beyond 3 have a
     valid independent adjudication". One of the two must move.
   - Mark Major #3 closed — the artifact was rebuilt at `1762b229`.
   - Mark Major #4 closed — capability claims corrected at `5a0447b`; audit in
     `20260824-claude-capability-claims-audit.md`.

Standing constraints that outlive any of the above:

- No model is promotable. Best deflated Sharpe `0.397794` against a `0.95` gate, and every published
  model is pre-schema-v2 or `RESEARCH_ONLY`. **Corporate-action correction does not change this** —
  measured, not assumed: selection edge `-0.000022` -> `-0.000185`.
- **Demergers are excluded, not corrected.** 0 of 54 ratio-less actions could be validated against
  independent evidence, so windows spanning one are dropped. Any result computed across a demerger is
  refused rather than published, and that refusal is the current state of the art here.
- **Bars are not RAW in the way the manifest says.** The provider back-adjusts splits and bonuses
  (212/212 measured). Re-applying a published ratio corrupts the series. Never adjust without first
  checking whether the provider already did.
- Nothing has ever placed an order, by design.
- A strategy embedding an ungoverned model without declaring `research_only` is still not detected.
  The guard reads a declaration, not the code.
