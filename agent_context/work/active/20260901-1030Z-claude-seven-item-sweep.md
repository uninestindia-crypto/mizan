# Active work: the seven open items, worked in order

STATUS: IN_PROGRESS
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

Item 2.

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
