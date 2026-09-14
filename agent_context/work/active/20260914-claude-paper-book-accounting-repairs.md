# Active work: paper-book accounting repairs (entitlement, fee display, evaluator)

STATUS: ACTIVE  
OWNER: Claude Code (Opus 5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-14T10:30:00Z  
STARTING_REVISION: f43f4f62f88440ce624dd7489780585c2e2f05dd  
WORKTREE_OR_BRANCH: `D:\quant_system`, branches `main` and `claude/paper-book-accounting-repairs`
  (shared checkout). The branch was cut at `f43f4f62` on founder instruction to commit, because this
  work crosses three ACTIVE claims (PROTOCOL §1) and `daily_auto_sync.ps1` commits to `main` on a
  schedule. It carries exactly one commit, `056fb1c6`, which was then fast-forwarded into `main` on
  founder instruction to merge. **It is fully merged and holds nothing `main` does not.** Claimed
  here because `audit-agent-claims.ps1` correctly failed on it as an unclaimed workspace; it is mine
  and safe to delete, but deletion is not done without being asked.

## Authorization

Founder instruction, 2026-09-14, in response to an explicit question naming the three items and
naming the claims each one crosses. The founder selected all three:

1. Wire the HEG entitlement end to end.
2. Fix the flagship fee/P&L display and surface model identity.
3. Repair the short-horizon evaluator.

This authorization is what permits editing under the ACTIVE claims listed in "Blockers and
conflicts". Without it these paths are not mine to touch.

## Objective

Implement items 1-3 of the repair order in `reports/loss_diagnosis_20260913/DIAGNOSIS.md`, so that:

- the XS-Monthly book never books an unvaluable corporate-action entitlement as zero, at open mark,
  at maturity, at restart, or in any renderer;
- the flagship status file cannot be read as charging zero lifetime costs against a lifetime P&L,
  and names the exact model artifact under observation;
- the short-horizon evaluator's reported statistics mean what their labels say.

Accounting correctness only. **No** claim that any of this makes a strategy profitable.

## Owned paths

- `agent_context/work/active/20260914-claude-paper-book-accounting-repairs.md` (this file)
- `src/quant_system/research_xs_monthly/paper.py`
- `scripts/run_xs_monthly_paper_watch.py`
- `scripts/run_paper_pilot_session.py`
- `scripts/view_live_pnl.py`
- `src/quant_system/server/ui/live_dashboard.py`
- `src/quant_system/research_short_horizon/evaluation.py`
- `scripts/run_short_horizon_experiment.py`
- `src/quant_system/modeling/mizan_model.py` (added during item 2 — see "Scope added" below)
- `tests/test_xs_monthly_unpriced_entitlement.py`
- `tests/test_short_horizon_evaluation.py`
- new test files created by this work

## Non-goals

- **No edit to any file under `logs/`.** Saved paper history is not rewritten. The correction takes
  effect on the next scheduled run, because `settle_positions` recomputes every open mark from
  `entry_open`/`shares`/latest bar on each run. Rewriting a saved valuation would be a different
  history, not a correction — the reasoning in `20260910-NOTICE-xs-monthly-heg-entitlement-unpriced.md`
  still binds.
- No retraining, no new trial, no multiplicity ordinal, no holdout access, no model promotion.
- No live-money routing (T4 excluded by product law).
- No change to what either book trades, to the frozen XS rule, or to any risk limit.
- No repository-wide formatter, generator, or `git add -A`.

## Plan

1. File this record. — DONE
2. Item 1: build the entitlement map from `data/authorities/nse-demerger-entitlements.json`, pass it
   from both callers, close the maturity branch, stop every consumer defaulting a missing value to
   zero. — **DONE**, verified against the real book in a scratch copy
3. Item 2: flagship fee-field semantics and model identity in status/renderers. — **DONE**
4. Item 3: short-horizon evaluator. — **DONE**
5. Tests, ruff, mypy, `audit-agent-claims.ps1`, `audit-disk-layout.ps1`. — **DONE, all green**
6. File the three PROTOCOL §3/§8.4 notices. — **DONE**

## Current step

Complete. Nothing staged, nothing committed, no file under `logs/` written.

## Scope added after the record was filed

`src/quant_system/modeling/mizan_model.py` was added to owned paths during item 2. It holds the
default weights whose identity item 2 had to surface, and it is claimed by
`20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` — the same claim the founder
authorised crossing for item 3. The change is one read-only module constant; the model card schema
and its hash payload are untouched.

## Decision rationale

**Verification before repair.** Every load-bearing number in the diagnosis was independently
reproduced from the live files before any edit (see "Commands and outcomes"). The flagship's three
accounting identities reconcile exactly; the XS HEG leg is as described; the wiring gap is real.

**Why the maturity branch is the dangerous half.** Today the fabricated HEG loss is *unrealized* and
therefore still correctable. At maturity (entry 2026-09-02 + 21 sessions) the current code would run
it through `forward_net` and `_book_closed` and convert it to realized cash. After that the book
cannot be corrected without rewriting history, which the notice forbids.

**Why an unpriced leg must not simply stay open.** `run_xs_monthly_paper_watch.py` gates new
positions on `if not state["open"]`. Holding an unvaluable leg open forever would therefore stop the
book rebalancing, permanently and silently — a worse failure than the mispricing. So a matured
unpriced leg moves to a separate `unresolved` bucket: it leaves `open`, it adds nothing to cash
(no proceeds were received), and it is reported by name.

**Why equity is reported in two parts.** Carrying an unvaluable holding at zero asserts it is
worthless; carrying it at cost asserts it broke even. Both are assertions. The book therefore
publishes `equity` (cash + priced marks, with the exclusion stated) alongside `unpriced_at_cost` and
a named leg list, so no single number silently absorbs the unknown. This is the second of the three
resolutions the notice offered its owner, now taken.

**Rejected:** inventing a price for HEGGRAPHITE; reversing the INR 6,124.30; deleting the leg;
editing the saved state file. The first three fabricate evidence, the fourth rewrites history.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`, `git worktree list`, `git branch --list` | PASS | `main` at `f43f4f62`; 2 external worktrees + 4 branches preserved, untouched |
| Independent decimal reconstruction of `logs/paper_runs/` | PASS | entry 853,407.04 + fees 1,072.65 + cash 145,520.31 = 1,000,000.00; mv 840,749.87 + cash = 986,270.18 = `total_equity`; mv − entry = −12,657.17 = `unrealized_pnl`; 97 positions, 70 losing / 27 winning |
| Read `logs/xs_monthly_new/paper_watch/state.json` | PASS | capital 1,000,000, cash 137,184.02, 99 open, 0 closed; HEG leg 13 sh @ 725, `market_value 3300.7`, `unrealized -6124.3`, `asof_date 2026-09-10`; runs 09-11/09-12/09-13 all equity 994,059.62 (cache ends 09-10) |
| Static call-path inspection | PASS | `run_xs_monthly_paper_watch.py:80,:102` pass no `unpriced_entitlements`; `:119` sums `leg.get("market_value","0")`; `_render` reads `leg['gross_mark']` unguarded; `live_dashboard.py:1130` `parseFloat(...)||0`; `paper.py` closed branch never consults the map |
| Read `mizan_model.py:552` | PASS | default weights are `trial_mizan_h11_002`, DSR 0.175990, RIDGE Sharpe −0.410755 |

| `uv run pytest` (XS suites, first attempt) | 2 FAILED | My maturity fixture used flat bars, and `screen._is_locked` treats `high == low` as a circuit lock, so `forward_net` refused to close. That is also why the pre-existing tests never reached the maturity path — every fixture in this area is flat-barred |
| `uv run pytest` (XS suites, after spread) | PASS | 44 passed across 5 XS files |
| Dry run of the real book into a scratch `--state-dir` | PASS | `equity 990758.92`, `UNPRICED 1 holding(s), entry cost 9425`; reason names the ex-date, the ratio and the resulting symbol |
| `git status --short logs/` | empty | **This proves nothing and was wrongly cited as evidence.** `logs/` is gitignored (`.gitignore:21`), so the command is empty either way. Corrected in `20260914-NOTICE-xs-entitlement-wired-under-hermes-claim.md` |
| SHA-256 of the three state files vs `reports/loss_diagnosis_20260913/snapshot.json` | 2 MATCH, 1 DIFFERS | The real evidence. `live_paper_status.json` and `portfolio_state.json` unchanged byte-for-byte; `xs_monthly_new/.../state.json` differs because the **scheduled task** rewrote it at 2026-09-14T11:46:46Z, the first production run of the repair |
| `uv run ruff check` / `ruff format --check .` | PASS | 671 files formatted, 0 failures |
| `uv run mypy src launcher.py scripts` | PASS | 208 files, no issues |
| `uv run pytest tests/ -q` | **1,519 passed** | 1,490 pre-existing + 12 (item 1) + 17 (item 3). No pre-existing test broke except the 4 asserting the `BUY_AND_HOLD` name, updated deliberately. `CURRENT.md`'s 1,473 is stale — other agents added tests since |
| `scripts/audit-agent-claims.ps1` | PASS | Every workspace has a visible claim and every claim resolves |
| `scripts/audit-disk-layout.ps1 -Fast` | PASS | No stray QuantOS directories |

## Files changed

Item 1 — XS-Monthly entitlement:

- `src/quant_system/research_xs_monthly/paper.py`: `load_unpriced_entitlements` (fail-closed authority
  reader), `book_value` (splits priced from unpriced, never sums a default), `unresolved` return key,
  and the maturity refusal in `settle_positions`
- `scripts/run_xs_monthly_paper_watch.py`: map built and passed at both call sites,
  `--entitlement-authority`, equity via `book_value`, unpriced legs rendered and printed
- `src/quant_system/server/ui/live_dashboard.py`: XS KPI block and positions table refuse an unpriced
  leg rather than zeroing it; disclosure banner
- `tests/test_xs_monthly_entitlement_wiring.py`: 12 new tests

Item 2 — flagship fee display and model identity:

- `scripts/run_paper_pilot_session.py`: `model_provenance()`, `session_fees_paid`,
  `lifetime_fees_paid`, `fees_basis`; provenance into the session JSON
- `scripts/view_live_pnl.py`: two fee lines, each naming its period
- `src/quant_system/server/ui/live_dashboard.py`: lifetime fee tile, header names the loaded trial,
  verdict and mark timestamp
- `src/quant_system/modeling/mizan_model.py`: `DEFAULT_MODEL_PROVENANCE`

Item 3 — short-horizon evaluator:

- `src/quant_system/research_short_horizon/evaluation.py`: capital-constrained tranche ledger in
  `score_decisions`, past-only per-fold abstention, `portfolio_periods`/`dropped_dates`,
  `applied_policies`, `BUY_AND_HOLD` -> `ALWAYS_TRADE`
- `scripts/run_short_horizon_experiment.py`: `DECLARED_TRIALS` 6 -> 9, DSR sample length from scored
  portfolio periods, DSR annualisation passed explicitly
- `tests/test_short_horizon_portfolio_ledger.py`: 13 new tests
- `tests/test_short_horizon_trial_count.py`: 4 new tests binding the constant to the ledger
- `tests/test_short_horizon_evaluation.py`: updated for the rename

Notices filed (additive; no other record edited):

- `20260914-NOTICE-xs-entitlement-wired-under-hermes-claim.md`
- `20260914-NOTICE-flagship-fee-display-and-model-identity-under-antigravity-claim.md`
- `20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md`
- `20260914-NOTICE-ci-split-into-parallel-jobs-under-ci-workflow-claim.md`

Follow-on, on separate founder instruction after the merge and push:

- `.github/workflows/ci.yml`: split one seven-gate serial job into `static` / `tests` (matrix
  forward+reverse) / `craft` / `gates` aggregator. Run `34839894115` was cancelled at the 30-minute
  timeout mid-suite, skipping the craft checkers and both audits. **Not caused by this record's 29
  new tests** — the run that added them passed in 28m33s, and the next run, changing one Markdown
  file, died; the margin had been 34 seconds since before this session. Owned by
  `20260821-claude-ci-workflow.md`; notice filed.
- `agent_context/CURRENT.md`: gate table re-measured at `cd57e5b0` (1,473 -> 1,519 tests, 205 -> 208
  mypy files). Header and that table only; claimed elsewhere, edited on founder instruction.

## Blockers and conflicts

Editing under three ACTIVE claims, on the founder authorization recorded above. NOTICE records will
be filed for each, per PROTOCOL §3 (their records are not edited by me):

- `20260903-hermes-xs-monthly-screen-new.md` (Hermes Agent) — owns
  `src/quant_system/research_xs_monthly/**`, `scripts/run_xs_monthly_paper_watch.py`,
  `logs/xs_monthly_new/`. Item 1 edits the first two; `logs/` is untouched.
- `20260826-antigravity-paper-trade-live-market-testing.md` (Antigravity) — owns
  `scripts/run_paper_pilot_session.py`, `scripts/view_live_pnl.py` and the dashboard. Item 2 edits
  these.
- `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` — the short-horizon program.
  Item 3 edits its evaluator, which changes reported statistics for trials already in its frozen
  ledger. That record pins those numbers as evidence, so PROTOCOL §8.4 requires a notice naming
  exactly which figures the repair invalidates.

## Stop point

All three items implemented and verified. Working tree is dirty with exactly the files listed above
plus the three notices and this record. **Nothing staged, nothing committed, no file under `logs/`
written, no trial run, no ordinal spent, no holdout touched.**

## What was measured, and what was not

Measured: the accounting identities, the wiring gaps, the effect of item 1 on the real book, and that
every gate is green after all three changes.

**Not measured: whether the corrected short-horizon evaluator changes any published conclusion.** The
repaired code has never been run against the real corpus — only fixtures. The direction of each
correction is predictable (lower total return, lower drawdown, lower DSR); the magnitude is not. No
number in `reports/short_horizon/TRIAL-LEDGER.md` has been recomputed or edited.

Also not done, and outside what was authorised: the diagnosis's items 4 and 5 are policy, not code.
Item 5's standing conclusion is unchanged by any of this work — **none of these repairs makes a
strategy profitable, and none of them was expected to.** They make the books say true things about
what already happened.

## Next safe action

The owner of `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` decides whether
re-running the nine declared trials with the corrected evaluator spends fresh ordinals, then either
re-runs them or does not. The notice states the case both ways and deliberately does not decide it.

Separately: the next scheduled XS-Monthly run will mark HEG correctly with no further action. Expect
displayed equity to fall from 994,059.62 to 990,758.92 with a disclosure of 9,425 at cost. That is
not a new loss; it is the book declining to state a number it never had evidence for.
