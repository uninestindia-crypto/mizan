# Ruff repair: all 44 findings (claim overridden by founder)

STATUS: IN_PROGRESS
AGENT: Claude Code
STARTED_UTC: 2026-08-29T00:00:00Z
STARTING_REVISION: `fa9fb9fa`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout)
AUTHORIZATION: founder instruction, 2026-08-29 ("fix the 44 ruff errors")

## Why this is scoped to 5 of the 44

`main` has been gate-red since `3d120730` (GitHub Actions run `32994595056`, `ruff check .`,
44 errors). The founder asked for all 44.

**39 of them are in paths held by an ACTIVE claim**,
`20260826-antigravity-paper-trade-live-market-testing.md`, whose own `Current step` reads
"Implementing scripts/run_paper_pilot_session.py". Owned there:

| path | errors |
|---|---:|
| `scripts/run_paper_pilot_session.py` | 24 |
| `scripts/serve_live_dashboard.py` | 8 |
| `scripts/view_live_pnl.py` | 4 |
| `src/quant_system/server/app.py` | 3 |

AGENTS.md: "Never edit a path claimed by another active record. Coordinate or stop." Beyond the
rule, the practical hazard is concrete: reformatting a file another agent is actively writing either
clobbers their in-flight work or is clobbered by it, and this session has already observed a peer's
broad commit sweeping files unpredictably and tests failing mid-write.

So this record takes only the paths **no record claims**, and files
`20260829-NOTICE-app-py-live-status-endpoint-raises-nameerror.md` to reach the owner about the rest.

## Owned paths

- `tests/test_live_universe_robustness.py` (4 errors)
- `scratch/test_upstox_env.py` (1 error)
- `agent_context/work/active/20260829-claude-ruff-repair-unclaimed-files.md` (this file)

## Non-goals

- Editing any path in the Antigravity active claim, including the two real `F821` defects.
- Repository-wide `ruff --fix` or `ruff format`, which would reach claimed paths.

## Founder override, 2026-08-29

After this record was filed scoping itself to 5 findings, the founder was shown the conflict and
responded **"override the claim and fix all 39"**. AGENTS.md reserves exactly this to explicit
founder instruction. All four claimed paths were then repaired. **Owned paths extended to:**

- `scripts/run_paper_pilot_session.py`, `scripts/serve_live_dashboard.py`, `scripts/view_live_pnl.py`
- `src/quant_system/server/app.py`
- `src/quant_system/data/universe.py` (formatting only — see below)

Checked before editing: `git status` showed **no uncommitted work in flight** on any of them, so the
override did not interrupt an edit in progress.

## What was repaired

| Finding | Files | Treatment |
|---|---|---|
| **F821 Undefined name** (2) | `server/app.py` | **Real bug.** `import json` added; `PROJECT_ROOT = Path(__file__).resolve().parents[3]` defined. `/api/paper-pilot/live-status` raised `NameError` on its first statement on every call; it now returns a real session payload |
| **F841 unused local** (1) | `serve_live_dashboard.py` | **Real bug.** `halted` was assigned in two branches and never read, so the halt endpoint reported `"HALTED"` even when nothing was running. It now gates the response. Verified no consumer depends on the literal string |
| E402 (12) | `run_paper_pilot_session.py` | `# noqa: E402`, matching the existing convention in `build_mizan_feature_store.py` — these follow a deliberate `sys.path` bootstrap |
| W293 (4) | `serve_live_dashboard.py` | Trailing whitespace on blank lines **inside embedded CSS/JS string literals**, which `ruff format` cannot reach. Stripped by hand; no functional change |
| F401/I001/F541/others (20) | all four | `ruff check --fix` |

`ruff format .` was run repo-wide and reformatted 3 files, one of which — `data/universe.py` — this
record had not intended to touch. It was **already unformatted on `main`**, so CI's
`ruff format --check .` would have failed on it regardless. Change proven semantically inert:
**AST identical before and after**, and `NIFTY50_SYMBOLS` holds the same 50 symbols. Disclosed rather
than buried, because PROTOCOL 4 lists repository-wide formatters as a high-conflict operation.

## Result

| Gate | Before | After |
|---|---|---|
| `ruff check .` | **44 errors** | **All checks passed** |
| `ruff format --check .` | 3 files unformatted | **484 files already formatted** |
| `pytest` | 1047 passed | **1047 passed** |

## Blocker discovered, NOT fixed: `main` fails a second gate

Clearing ruff revealed that CI never reached the mypy step. `mypy src launcher.py scripts` fails:

```
scripts\serve_live_dashboard.py: error: Source file found twice under different module names:
  "serve_live_dashboard" and "scripts.serve_live_dashboard"
```

**Pre-existing, and proven so**: the identical error occurs on the unmodified `HEAD` version of that
file, with a clean cache. Cause is `src/quant_system/server/app.py:1270`:

```python
from scripts.serve_live_dashboard import HTML_DASHBOARD
```

The library imports from `scripts/`, which is not a package. mypy therefore resolves the file under
two names. It works at runtime only because the repo root sits on `sys.path` and implicit namespace
packages permit it; a packaged build would raise `ModuleNotFoundError`.

Left unrepaired deliberately: the honest fix moves `HTML_DASHBOARD` into the library (near
`server/ui/templates.py`) so the dependency points the right way. That is an architectural change to
another agent's design, not a lint repair, and it is outside what was authorised here.

## The mypy blocker was then also authorised and fixed

The founder responded **"yes move the dashboard template into the library"**.

`HTML_DASHBOARD` -- 708 lines of markup -- moved from `scripts/serve_live_dashboard.py` to a new
`src/quant_system/server/ui/live_dashboard.py`, beside the other templates in that package. The
dependency now points the right way: the library owns the asset, and the standalone script imports
it. `server/app.py` imports it at module level instead of doing a function-local
`from scripts.serve_live_dashboard import ...`.

`/ui/trading-live` serves **the same 25,976 bytes** before and after.

### Removing the blocker exposed three more errors mypy had never reached

mypy had been halting with "errors prevented further checking", so these had never been seen:

| Error | File | Nature |
|---|---|---|
| `"RiskLimits" has no attribute "kill_switch_triggered"` | `run_paper_pilot_session.py:805` | **Real bug.** `RiskLimits` carries no such field; kill-switch state is `PreTradeRiskGovernor.is_killed`. The old attribute raised `AttributeError` on the path that writes `live_paper_status.json` -- the very file the endpoint repaired above reads |
| `Missing type arguments for generic type "Popen"` | `serve_live_dashboard.py:45` | Typing; `Popen[bytes]` |
| `Returning Any from function declared to return "dict[str, Any]"` | `server/app.py:1239` | **Mine**, introduced by the `NameError` repair: `json.load` returns `Any`. Bound to a declared type |

That makes **three genuine runtime defects** surfaced by clearing lint on this branch of work: the
`NameError` endpoint, the dead `halted` flag, and this `AttributeError`. None had a test.

## Full CI gate set, run locally exactly as `.github/workflows/ci.yml` does

| Step | Result |
|---|---|
| `ruff check .` | **All checks passed** |
| `ruff format --check .` | **485 files already formatted** |
| `mypy src launcher.py scripts` | **Success, 171 source files** |
| `pytest tests/ -q` | **1047 passed** |
| pytest, reverse file order | **1047 passed** |
| `check-code.mjs --self-test` | PASS |
| `check-tests.mjs --self-test` | PASS |
| `audit-agent-claims.ps1` | **PASS** |
| `audit-disk-layout.ps1` | **PASS** |

`main` has been gate-red since `3d120730` on 2026-08-26. Every gate now passes locally.

## Next safe action

Commit and push, then confirm the GitHub Actions run goes green. The repairs to another agent's
owned paths were made under founder override and want that owner's review -- particularly the two
behavioural changes: the halt endpoint now reports `NOT_RUNNING` when nothing was halted, and
`kill_switch_active` now reads the governor rather than raising.
