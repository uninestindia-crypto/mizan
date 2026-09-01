# Active work: the seven open items, worked in order

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-09-01T10:30:00Z
STARTING_REVISION: 7c1aa414
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Founder instruction, 2026-09-01: work the seven items I surfaced as open, one by one.

| # | Item |
|---|---|
| 1 | The uncommitted v3->v4 portfolio migration; this morning's 09:00 session exited 2 before ordering |
| 2 | Round six's 10 P2 / 4 P3, and the unfinished part of R6-05 |
| 3 | The provider-behaviour gap: R6-01 / R6-02 / R6-15 proven as code, unproven against Upstox |
| 4 | Mizan v3 window dependence (P1); app.py live-status NameError (P2); feature explorer rows; the portfolio lock decision |
| 5 | The dirty tree: 1,409 untracked NIFTY 500 cache files and five modified macro JSONs |
| 6 | Branch protection is impossible on this plan; two files state it as a founder setting |
| 7 | The training path has never been independently adjudicated |

## Timing check performed before editing

`20260831-round4-remaining-repairs.md` forbids editing while a session runs. At start:
NSE closed 15:30 IST, local clock ~15:58 IST, and no `run_paper_pilot_session.py` process exists
(`Get-CimInstance Win32_Process`). `serve_live_dashboard.py` is running as PID 19032 since 13:43 IST;
an edit to its source does not affect the loaded process.

## Owned paths

- src/quant_system/execution/paper_portfolio.py
- tests/test_paper_portfolio.py
- agent_context/work/active/20260901-1030Z-claude-seven-item-sweep.md

Paths added per item as each is reached, recorded below with the ownership check for each.

## Ownership checks performed

- `20260826-antigravity-paper-trade-live-market-testing.md` (STATUS: ACTIVE) owns
  `scripts/serve_live_dashboard.py`, `src/quant_system/server/app.py`,
  `scripts/run_paper_pilot_session.py`, `logs/paper_runs/`, `src/quant_system/execution/paper_pilot.py`.
  It does **not** own `paper_portfolio.py`. Where I must touch a path it owns, I file an additive
  NOTICE rather than editing its record, which is the established practice here
  (three such notices already exist: 20260830 engine, 20260830 session, 20260831 dashboard).
- `20260826-claude-mizan-canonical-window-and-kernel.md` (IN_PROGRESS) owns `modeling/mizan_features.py`
  and `tests/test_mizan_features.py` only. It does not own `scripts/build_mizan_feature_store.py`.
- Worktrees `codex/real-journey-api` and `codex/release-manifest-integrity` are live. Untouched.

## Non-goals

- Live-money routing. Nothing here places an order.
- Promoting any model. Every published model remains RESEARCH_ONLY.
- Removing or pruning another agent's worktree or branch.

## Current step

All seven items worked. Two decisions raised for the founder; nothing else left open by me.

## Item 1 -- the v3->v4 migration. DONE.

### What I reported this morning was wrong in one respect, and it matters

I said a session was lost. It was not. The 09:00 run aborted at 10:09:36 IST
(`logs/paper_runs/scheduled_20260901_schema_aborted.log`) on
`PaperPortfolioError: ... declares quantos.paper_portfolio v3, expected ... v4`. A peer then wrote
the `_migrated` repair, and the 10:14:31 re-run **completed the whole day**: exit 0 at 15:30:19,
`Session Concluded & Reconciled: SUCCESS`, reconciliation 0.00 paisa, equity Rs 989,373.84,
0 fills -- correct for a hold session; the first rebalance is session 11.

So the state on disk is now v4, `sessions_completed = 2`, `daily_anchor_on = 2026-09-01`,
`daily_anchor_equity = 991882.31`, 97 holdings. The repair is proven in production. What it was
missing was a commit and a test, which is what this item added.

### Verified against the real file before writing anything

Copied `logs/paper_runs/portfolio_state.json` to the scratchpad and loaded it through
`load_portfolio`. The real book reconstructs: 97 holdings, cash 145520.31, sessions 2/2,
`last_rebalance_on 2026-08-31`. The live file was never written to.

### Six behavioural tests added

`tests/test_paper_portfolio.py`. Each drives `load_portfolio` and asserts on the returned state; none
asserts on source text, which was round six's R6-05 finding against the previous batch.

| Test | Holds |
|---|---|
| a v3 file still loads | cash, quantity, entry fee, hold clock and fees all survive |
| a migrated v3 file starts with no anchor | `daily_anchor_on is None`, equity 0.00 |
| migration does not bypass integrity | a tampered v3 payload is still refused on the hash |
| a version with no migration is refused | v2 renamed a field this loader reads; defaulting through it would resume a wrong book |
| a foreign schema id is refused | whatever its version |
| a migrated book is written back current | migration is a one-off, not a thing every morning redoes |

### Mutation results, and one of my own tests was caught by them

Six faithful mutants, each a reproduction of a plausible wrong migration rather than a deletion.
Source hash compared before and after; restored identically.

| Mutant | Result |
|---|---|
| M1 the historical original: no migration, strict refusal | **killed** (5 of 6 tests fail) |
| M2 migrate any version, default the new fields | **killed** |
| M3 schema_id no longer checked | **killed** |
| M4 anchor seeded from the persisted peak | **survived, then killed** |
| M5 anchor dated to the migration day | **killed** |
| M6 migrated payload keeps the old version number | **survives, and is inert** |

**M4 is the one worth recording.** It survived because `peak_equity` defaults to `Decimal("0.00")`
and my fixture never overrode it, so "seed the anchor from the peak" and "seed it with zero" produced
the same value. The test passed for a reason unrelated to what it claimed to check -- exactly the
R6-05 failure mode, in a test written in the same week that finding was filed. Fixed by giving the
fixture a real peak of 1,000,000.00, which is what the live file carries. It now kills M4.

**M6 survives and I am not claiming otherwise.** Nothing reads `payload["schema_version"]` after
migration, and `to_payload()` writes the current version on every save, so the assignment cannot
change behaviour through any path. It is a redundant line, not an untested one. Left in place as a
statement of intent.

### Gates

```
ruff check .            -> All checks passed
ruff format --check .   -> 536 files already formatted
mypy src                -> Success, 141 source files
pytest -q               -> 1211 passed, 1 warning, 85.03s
```

## Commands and outcomes

(recorded per item below)

## Stop point and next action

(updated at each checkpoint)


## Items 2 to 7

### Item 2 -- round six's 10 P2 / 4 P3, and R6-05's remainder. DONE.

All 14 addressed. 13 repaired; R6-08's behaviour half raised as a decision with a diagnostic
shipped, because correcting it changes what the pilot trades days before its first rebalance, and
the obvious partial fix is a livelock: `rebalance_executed` requiring weight conformance can never
succeed, because the entry loop cannot trim weights.

| Finding | Outcome |
|---|---|
| R6-01/02/15 quote validation | `parse_quote_payload` returns None for a payload it cannot price; depth levels validated |
| R6-03 partial-failure test | now serves one real chunk and fails the second. **M-F1-1, the mutant the report says survived, is dead** |
| R6-06 risk equity marks to cost | one expression instead of two, and it names what it could not mark, once per name |
| R6-08 weight drift | reported, not corrected. Decision raised |
| R6-09 flat-book alarm | three endings, three messages; only the one where money left says so |
| R6-11 anchor with unquoted holding | already repaired; a test now pins it |
| R6-12 data-file test | kept as the data check it is, documented, paired with a driven guard |
| R6-13 corporate-actions default | pinned to the cache the refresh owns |
| R6-16 macro cache | an empty 200 may not destroy cached bars |
| R6-19 startup retry | the opening fetch gets the loop's budget; sleep injected, no sleeping in tests |
| R6-20 false comment | the exits are staged, not filled; the comment said filled |
| R6-21 log spam | coverage logged on change, not every interval |
| R6-15 hold clock | an aborted session keeps its ledger facts and does not spend a held session |
| R6-22 token leak | out of argv entirely; the runner already reads the environment |

Also closed while here: the four `mypy` errors in the pilot runner. `mypy src launcher.py scripts`
is clean across **176 files**; it was red.

### Item 3 -- the provider-behaviour gap. DONE, and it found more than it settled.

One authenticated ten-instrument request. `.launch/reports/LIVE-PROVIDER-PROBE-20260901.md`.

- The success envelope matches R6-01's guard. Confirmed against the provider rather than assumed.
- **The primary instrument-key lookup has never matched a quote.** Request keys are the ISIN form,
  the response is keyed by symbol: primary 0 of 10, fallback 10 of 10.
- **90 of 100 depth levels were priced at zero**, top-of-book zero on all ten names. The previous
  spread computation therefore produced a spread equal to the whole share price -- RELIANCE 1309.00
  rather than 0.05 -- and the pilot's opening fetch runs at 09:00, before the open, when the ladder
  looks exactly like this.

That last point is stronger evidence for the R6-02/R6-15 repair than the finding that motivated it.

### Item 4 -- the P1 that was not one, and two repairs nothing was testing. DONE.

- **Mizan v3 window dependence: severity corrected, with a measurement.** Worst RSI divergence at
  the canonical 400-bar window is **2.079e-11**, below the store's 1e-10 quantisation; at or below
  400 bars both sides take the identical prefix. The same method finds whole RSI points of
  divergence at 51 bars, so the negative result at 400 is evidence rather than a limitation of the
  method. Four tests now pin it.
  **I had carried the P1 severity forward to the founder without measuring it. That was wrong.**
- `app.py` live-status `NameError`: already repaired, and nothing tested it. Five tests, three
  mutants, all killed -- including `PROJECT_ROOT` resolving one level too shallow.
- Feature explorer fabricated rows: already fails closed with the certified 404, already covered.
- Two decisions raised: `agent_context/decisions/20260901-two-open-paper-pilot-decisions.md`.

### Item 5 -- the dirty tree. DONE. Tree is clean.

612 new blobs / 13.4 MB of the 2026-09-01 NIFTY 500 refresh -- 500 of 500 targets, 350,111 bars --
and the macro window roll. The macro files were checked against their committed versions **before**
committing, because R6-16 in the same sweep is the defect that silently empties them: bar counts
identical at 743, so a legitimate roll and not that failure.

### Item 6 -- and the correction was larger than the item. DONE.

**CI has not run since 2026-08-29T17:30Z.** 25 consecutive failures at about three seconds each:
`recent account payments have failed or your spending limit needs to be increased`. The gate is red
for **billing**, not for code. Both `.launch/STATE.md` and `CURRENT.md` recorded Major #1 as CLOSED
and passing, and `CURRENT.md` contradicted itself besides -- its action list said the workflow could
not be pushed for want of `workflow` scope, which the token has and the workflow is on `main`.
Branch protection is impossible on this plan: `403 Upgrade to GitHub Pro or make this repository
public`.

Both files corrected on founder instruction, with a notice filed naming exactly what changed.

### Item 7 -- Q2 of the training-path adjudication. ANSWERED.

`.launch/reports/ADJUDICATION-TRAINING-PATH-Q2-20260901.md`. The brief approximated the return
moments as normal because the return series "are not in the manifests". They are: 63 RIDGE decision
records per model carry `realized_net_return`.

- Method validated first: recomputing each model at its own stored ordinal reproduces its published
  DSR to within **2.38e-03** across all 50.
- Exact re-deflation at 50 attempts: **0.218377**. CURRENT.md's `0.217695` is corroborated to
  6.8e-04; the brief's `0.250826` was its own declared approximation error.
- The estimator was identified rather than tolerated: a 0.99202 ratio against `sqrt(62/63)` =
  0.99203 showed the pipeline uses the sample standard deviation.
- True moments are strongly non-normal, skew +1.74 and kurtosis 12.09 on 63 observations. The
  approximation was wrong about the distribution and nearly right about the DSR only because the
  margin to the gate is large. Recorded in both directions.
- Every section-3 corroboration reproduced exactly from the store. Zero of fifty reach the gate at
  any attempt count up to 110.

Not a PASS. One question of six.

## Gates at completion

```
ruff check .                             -> All checks passed
ruff format --check .                    -> 546 files already formatted
mypy src launcher.py scripts             -> Success, 176 source files
pytest -q                                -> 1292 passed  (1202 at the start of the day)
pytest, reverse file order, as CI runs it -> 1292 passed
node scripts/check-code.mjs --self-test  -> PASS
node scripts/check-tests.mjs --self-test -> PASS
check-tests.mjs on the four new files    -> clean
audit-agent-claims.ps1                   -> PASS
audit-disk-layout.ps1                    -> PASS
evidence_manifest.py --check             -> OK: 5077 resources match
```

**Every gate ran on this machine rather than in CI, because CI has been down for billing since
2026-08-29.** That is a weaker statement than a green pipeline and is not a substitute for one.

## Mutation testing

61 faithful mutants across the sweep, each a reproduction of a plausible wrong behaviour rather than
a deletion, since round six's R6-05 finding was that deletion mutants prove nothing against tests
that read source text. All killed except one, which survives because the line it changes is inert
and is recorded as such rather than counted as a pass.

Two mutants caught holes in my own tests before they shipped. The instructive one: `peak_equity`
defaults to `0.00`, so an anchor seeded from the peak was indistinguishable from one seeded with
zero until the fixture carried a real peak -- a test passing for a reason unrelated to what it
claimed, written in the same week that failure mode was filed.

## Stop point and next action

Committed on `main`, working tree clean, **nothing pushed**. Founder actions:

1. Restore GitHub Actions billing. Until then the repository has no automated gate and "the gates
   passed" is a statement about one laptop.
2. Choose GitHub Pro or a public repository, for branch protection.
3. Decide the two paper-pilot questions before session 11, about 2026-09-14.
4. Decide whether to push this sweep's commits.
