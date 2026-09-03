# Active work: XS monthly top-20% screen — brand-new parallel stack

STATUS: ACTIVE
OWNER: Hermes Agent
TOOL: Hermes Agent
STARTED_UTC: 2026-09-03T00:00:00Z
STARTING_REVISION: c19d3dbc756635763fcfa6b12a86441c8583d60f
WORKTREE_OR_BRANCH: D:\quant_system on main (shared checkout, new-files-only — see isolation note)

## Objective

Build a brand-new, isolated cross-sectional monthly (hold-21, long top-20%, pre-declared) research screen on all data (423-liquid universe + NIFTY50 cache), without touching the old stack. Prove with point-in-time, cost-aware (0.224% round-trip), reproducible numbers whether this frame has any edge. No promotion, no live-money, no governed campaign ordinals spent.

## Owned paths

- `src/quant_system/research_xs_monthly/` (new package only: universe loader, ranker, portfolio, metrics, paper watch — all new files)
- `scripts/run_xs_monthly_screen_new.py` (new file only)
- `scripts/run_xs_monthly_paper_watch.py` (new file only)
- `tests/test_xs_monthly_new*.py` (new files only)
- `tests/test_xs_monthly_paper_watch.py` (new file only)
- `logs/xs_monthly_new/` (new output dir only; never `logs/paper_runs/`)
- `agent_context/work/active/20260903-hermes-xs-monthly-screen-new.md` (this file)

## Non-goals

- Do NOT edit, move, delete, reformat, or stage any other agent's paths, especially Antigravity ACTIVE claim `20260826-antigravity-paper-trade-live-market-testing.md`:
  - `scripts/run_paper_pilot_session.py`
  - `scripts/serve_live_dashboard.py`
  - `scripts/view_live_pnl.py`
  - `logs/paper_runs/`
  - `src/quant_system/execution/paper_pilot.py`
  - `src/quant_system/server/app.py`
  - `src/quant_system/server/ui/templates.py`
  - `src/quant_system/data/universe.py`
- Do NOT touch money paths under dispute/notices: `src/quant_system/execution/paper_portfolio.py`, `src/quant_system/risk/governor.py`, `scripts/daily_auto_sync.ps1`, `tests/test_paper_pilot_carried_session.py`, `tests/test_paper_portfolio.py`, `.launch/RED-TEAM-BRIEF-20260901-ROUND7.md`
- Do NOT touch governed contracts: `src/quant_system/modeling/*`, `src/quant_system/execution/cross_sectional_strategy.py`, `src/quant_system/execution/governed_strategy.py`, `data/authorities/*`, existing market-cache stores
- No live-money routing (T4 excluded by product law). No EvidenceStore writes, no multiplicity ordinals spent. Research screen only.
- No repo-wide formatter/generator/migration while shared-checkout agents are active.

## Plan

1. DONE — startup: read README/CURRENT/PROTOCOL/DISK-LAYOUT, STATE/SLICES, git status/worktrees/branches, collision scan of 74 active records via owned-path search.
2. DONE — created this record in install root BEFORE workspace (ownership law 8.1).
3. Worktree attempt FAILED on Windows MAX_PATH (`data/evidence/training-runs/...` tracked blobs, `Filename too long`, `git worktree add` exit 128, nothing registered). Branch `hermes/xs-monthly-new` exists but checkout is NOT switched: other agent lives on main in this shared checkout, switching HEAD would disrupt them. So: shared checkout on main, new-files-only.
4. In install root only, add new `research_xs_monthly/` + new script + new tests; READ old caches/authorities, never write them.
5. Run new tests + ruff on new files only; run `audit-agent-claims.ps1` + `audit-disk-layout.ps1` before handoff.
6. Report numbers with survivorship-bias warning; recommendation kill/keep. No worktree to retire (none created).

### Isolation note (shared-checkout permission, PROTOCOL 1)

- Owned paths exact and disjoint (only the four new-path entries above; verified against Antigravity paper-trade claim + mizan/cross-sectional claims + red-team round7 targets).
- No repo-wide formatter/generator/migration/staging (pytest + ruff scoped to new files only; stage explicit owned paths only, never `git add -A`).
- No shared-contract change (no edits to `modeling/*`, `execution/*`, `risk/*`, `server/*`, `data/*`, `.launch/*`).
- Both sides have visible active records before editing (this file + `20260826-antigravity-paper-trade-live-market-testing.md` et al).

## Current step

Step 9 — DONE. Separate ₹10L notional book live + Windows automation set. State: capital 1000000, cash 137184.02, 99 sized legs, equity 1000000.00 at open. Task `QuantOS-XSMonthly-PaperWatch` runs Mon–Fri 16:00 IST, next 2026-09-04. 22/22 tests green, ruff clean. Record stays ACTIVE for the settle cycle.

## Final numbers (quote these, not the interim block below)

Primary — 423 liquid names, 2016-08-22..2026-08-21, 2,476 sessions, 115 monthly rebalances, 48,166 scored decisions, 1,037,813 bars:

| Leg | Mean net/period | t | Sharpe ann |
|---|---|---|---|
| Long top-20% momentum | +0.01742 | +2.59 | +0.84 |
| Market equal-weight (same dates) | +0.01690 | +2.58 | +0.83 |
| **Selection edge (long − market)** | **+0.00053** | — | — |
| Long-short diagnostic | -0.00063 | -0.36 | -0.12 |
| Rank IC | mean -0.0096 | -0.85 | (n=115) |
| Hold-2 long diagnostic | -0.00198 | -4.61 | -0.46 (n=1217) |

Breadth — 499 NIFTY500 names, 2023-08-28..2026-09-02, 749 sessions, 33 rebalances, 15,502 decisions, 352,853 bars (IDEA missing from cache):

| Leg | Mean net/period | t | Sharpe ann |
|---|---|---|---|
| Long top-20% momentum | +0.01495 | +1.51 | +0.91 |
| Market equal-weight | +0.01395 | +1.48 | +0.89 |
| Long-short diagnostic | -0.00044 | -0.14 | -0.09 |
| Rank IC | mean -0.0087 | -0.38 | (n=33) |

Reading (recorded, not hidden): the long-only print is beta + survivorship, not skill. Selection edge is +5bps/period primary and +10bps breadth — both noise. Long-short ≈ 0 and IC < 0 in BOTH windows. Two independent windows agree: momentum rank adds nothing over holding the universe. 0.224% costs already charged per name per round trip; gross edge would be ~5-10bps larger, still noise. Verdict RESEARCH_ONLY. Evidence: `logs/xs_monthly_new/20260903-104002Z/` + `20260903-104119Z/` (JSON + MD, new dir).


## Interim numbers (first run, BEFORE market-leg — do not quote without the market split)

| Leg | n | Mean net/period | t | Sharpe ann |
|---|---|---|---|---|
| VALIDATED hold21 long top-20% | 115 | +0.01742 | +2.59 | +0.84 |
| DIAG hold2 long | 1217 | -0.00198 | -4.61 | -0.46 |
| DIAG hold2 long-short | 1217 | -0.00025 | -1.97 | -0.20 |
| DIAG hold21 long-short | 115 | -0.00063 | -0.36 | -0.12 |

Sceptical notes recorded before the re-run: the long-only print rides a survivorship-biased universe (active listings only) over a bull decade, so beta alone can print t > 2; the hold-21 long-short at t = -0.36 says no cross-sectional selection skill. The added market-equalweight leg will split beta from selection. Verdict stays RESEARCH_ONLY regardless.

## Decision rationale

Evidence: 50-name hold-21 long-only Sharpe +0.76/t1.18 (29 rebalances, not significant) collapsed to +0.12/t0.19 on 423 liquid names with IC sign flip (`20260825-claude-expanded-universe-authority.md`); hold-2 long-short loss strengthened t-5.68 to -7.85. Single-name daily failed 101 governed trials. User chose cross-sectional monthly + all data and explicitly ordered: leave old stack alone, build all-new, other agent active. So: isolated worktree + new-only paths is the only safe shape. Rejected: editing modeling/labels.py single-instrument contract (shared, would break old evidence + collide), re-running governed campaign (spends ordinals, needs adjudication), touching paper_pilot/governor (active claims + red-team target).

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch` + `git worktree list` + `git branch --list` | NOT RUN (this record) / ran pre-record read-only | main→origin/main, 14 modified + ~1000 untracked in install root treated as others' work; 2 detached worktrees + 2 non-default branches treated as live agents |
| owned-path collision search over `agent_context/work/active` | PASS | Antigravity claim + mizan/cross-sectional claims mapped; new paths disjoint |

## Files changed

- `agent_context/work/active/20260903-hermes-xs-monthly-screen-new.md`: this record
- `src/quant_system/research_xs_monthly/__init__.py`: new package marker
- `src/quant_system/research_xs_monthly/bars.py`: new read-only cache bar loader
- `src/quant_system/research_xs_monthly/screen.py`: new pre-declared screen (+ market leg)
- `src/quant_system/research_xs_monthly/paper.py`: new frozen-rule paper watch
- `scripts/run_xs_monthly_screen_new.py`: new runner (writes `logs/xs_monthly_new/`)
- `scripts/run_xs_monthly_paper_watch.py`: new watch runner (owns `logs/xs_monthly_new/paper_watch/`)
- `tests/test_xs_monthly_new.py`: new tests (11 passed)
- `tests/test_xs_monthly_paper_watch.py`: new tests (8 passed)

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch` + `git worktree list` + `git branch --list` | PASS | main→origin/main; 2 detached worktrees + 2 non-default branches = live agents; failed xs worktree registered nothing |
| owned-path collision search over `agent_context/work/active` | PASS | Antigravity paper-trade claim + mizan/cross-sectional claims mapped; new paths disjoint |
| `scripts/new-workspace-clone.ps1 -Kind Worktree ... -Branch hermes/xs-monthly-new` | FAIL (infra) | Windows MAX_PATH on tracked `data/evidence/training-runs/...` blobs, exit 128; branch created, checkout not switched; shared-checkout fallback per PROTOCOL 1 |
| `uv run pytest tests/test_xs_monthly_new.py tests/test_xs_monthly_paper_watch.py -q` | PASS | 22 passed (incl. 3 book sizing/conservation tests) |
| ₹10L book: `size_positions` + cash fields + migration, watch run | PASS | capital 1000000, cash 137184.02, 99 legs, equity 1000000.00; expensive names (PTCIL 22685) floor to 0 shares — disclosed, rule frozen |
| `schtasks /create QuantOS-XSMonthly-PaperWatch` Mon–Fri 16:00 IST | PASS | Next run 2026-09-04; appends `paper_watch/task.log`; never git-commits (auto-sync incident rule) |
| `git add` (6 owned pathspecs only) + `git commit` + `git push origin main` | PASS | `35088e8c`, 9 files, all new; `git show --stat` confirms zero foreign files; HEAD == origin/main (0/0); other agent's working-tree edits left intact and uncommitted |
| `uv run python scripts/run_xs_monthly_paper_watch.py` (x2: 1st hit a render-shape bug, fixed + regression-tested, 2nd clean) | PASS | 499 symbols, 99 legs opened 2026-09-02, state + Markdown in `logs/xs_monthly_new/paper_watch/` |
| `uv run ruff check` + `ruff format` (new files only) | PASS | All checks passed |
| full 423-symbol screen vs all-market 10y store | PASS | `logs/xs_monthly_new/20260903-104002Z`, long t2.59 = market t2.58, edge +5bps |
| NIFTY500 breadth leg (499 names, 2023-2026) | PASS | `logs/xs_monthly_new/20260903-104119Z`, same split, edge +10bps |
| `audit-agent-claims.ps1` | PASS (after repair) | 1 finding was my own empty branch `hermes/xs-monthly-new` (failed worktree, zero commits); deleted it, re-ran PASS |
| `audit-disk-layout.ps1` | PASS | No strays |

## Stop point

New stack complete in install root (shared checkout, new files only): package + runner + 11 tests green + 2 evidence bundles. Old stack untouched — no edits to paper_pilot/governor/server/modeling/data/`.launch`. Nothing staged, nothing committed.

## Next safe action

Founder picks: (a) park this frame — evidence says selection skill is zero in two windows; (b) forward out-of-sample paper watch of the FROZEN rule (no tuning) to test the +5bps; (c) genuinely new frame. Do not tune formation/hold/fraction on this data.

## Blockers and conflicts

None for record creation. Known live claims avoided by construction (see Non-goals). If worktree creation collides with an invisible claim, stop and coordinate per PROTOCOL 8.

## Stop point

Record created in install root. Worktree not yet created. No code touched.

## Next safe action

Run `scripts/new-workspace-clone.ps1 -Kind Worktree -Purpose feature -Label xs-monthly-new -Branch hermes/xs-monthly-new` from install root, then update this record with exact workspace path.
