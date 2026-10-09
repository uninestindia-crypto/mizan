# Active work: Broker view, a view-only connection to the person's broker (Phase 1, Upstox)

STATUS: COMPLETED  
OWNER: Claude Code (Sonnet 5.5), founder session  
TOOL: Claude Code  
STARTED_UTC: 2026-10-09T10:00:00Z  
STARTING_REVISION: `09cfa6b0a4bd15a54a88b82095f558556a33fa1e`  
WORKTREE_OR_BRANCH: the install root (the Mizan checkout), branch `main`. No worktree: the working tree was clean at start, no other record names these paths, and the Python environment and the frontend `node_modules` live in the install root, so tests in a separate worktree would import this checkout's code instead

## Objective

GOAL_LINE: G6 (primary), serving G1 (fails closed), G2 and G4 (every test runs with no broker and no key).

Execute `agent_context/handoffs/20261007-broker-view-only-build-brief.md`, Phase 1, on the founder's instruction of
2026-10-09 ("execute it"). Also look at `Learn from open source codebase/` (PyBroker and Qlib) and reuse what fits
rather than rewrite it.

## Open-source review result (2026-10-09)

- Neither codebase contains a broker-account connector. PyBroker has market-data sources (Alpaca, Yahoo, AKShare) and
  simulated portfolios. Qlib has simulated `Account`/`Position` classes. Neither reads a real Upstox or Kite account.
- Both are already ported into the research and backtest code by an earlier agent (`src/quant_system/research/qlib/`,
  `src/quant_system/backtest/pybroker_adapter.py`).
- Licence: Qlib is MIT (copying is allowed with its notice). PyBroker is **Apache 2.0 with the Commons Clause**, which
  withholds the right to "Sell" a product whose value derives substantially from the software. No code is copied from
  PyBroker here.
- **Nothing was copied from either for this feature.** What was reused is code already in this repo: the GET-only transport
  (`data/upstox_http.py`), the status mapper (`data/upstox_failures.py`), the key-expiry reader (`live/upstox_key.py`), the
  Credential Manager wrapper (`server/v2/credentials.py`), the Copilot registry, and the screens' own components.

## Owned paths

New:

- `src/quant_system/broker_view/**`
- `src/quant_system/server/v2/broker_routes.py`
- `src/quant_system/copilot/tools_broker.py`
- `frontend/src/components/BrokerViewSettings.tsx`, `BrokerViewSettings.test.tsx`
- `frontend/src/components/BrokerAccountCard.tsx`, `BrokerAccountCard.test.tsx`
- `tests/broker_fakes.py`, `tests/test_broker_view_*.py`, `tests/test_copilot_broker_tool.py`
- `agent_context/decisions/20261007-broker-view-only.md`
- `agent_context/handoffs/20261009-broker-view-phase1-real-account-check.md`

Small edits (the claimed ones are covered by `20261009-NOTICE-broker-view-under-retail-redesign-claim.md`):

- `src/quant_system/server/v2/router.py` (one import, one `include_router`)
- `src/quant_system/server/v2/credentials.py` (shared value check, `ScopedCredentialStore`, `BROKER_VIEW_KEY`)
- `src/quant_system/server/v2/copilot_wiring.py` (`_broker_account`, one field)
- `src/quant_system/copilot/registry.py` (one field), `tools.py` (one registry entry), `rules.py` (a built-in answer and a menu line)
- `tests/test_no_terminal_copy.py` (two more places scanned)
- `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Portfolio.tsx`, `frontend/src/lib/{queries,types}.ts` (appended)
- `src/quant_system/server/static/app/**` is rebuilt, but it is gitignored (`static/.gitignore`), so it is not part of any commit

## Non-goals

- Any order, GTT, conversion, payment, mutual-fund or order-book/trade-book address. Phase 2 (Zerodha) and Phase 3
  (statement import). Any change to `data/upstox*.py` or `live/*.py`. Calling the broker with the founder's account.

## Plan

1. Startup sequence, brief re-read, open-source review. DONE.
2. Notice and decision record. DONE.
3. Tests, then `broker_view/` modules. DONE.
4. Routes, vault, Copilot tool. DONE.
5. Screens and their tests; rebuild the frontend. DONE.
6. Gates, secret scan, both audits, release status, complete this record. DONE.

## Decision rationale

See `agent_context/decisions/20261007-broker-view-only.md`. Deviations from the brief, each deliberate:

- The broker's own `pnl` field is not read at all (stricter than the brief, which kept it): every figure shown is QuantOS's own
  arithmetic from prices and quantities.
- The "Updated a moment ago." message for a throttled refresh was dropped: the fetch time is always on screen, which says it
  better and with no extra state.
- `GET /broker/snapshot` never asks Upstox; the Portfolio card refreshes once by itself when the figures are old and the
  sign-in is good, and the engine's 30 second limit applies.
- A shared checkout was used instead of a worktree (reason in the header).

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`; `git worktree list`; `git branch --list` | clean start; 1 other worktree (Kronos, claimed) | left alone |
| `python scripts/release_status.py` | no release due (0 of 3) | last release v3.0.0; nothing is committed yet |
| `ruff check` and `ruff format --check` on every file I touched | PASS | repo-wide `ruff check .` reports 2,184 errors, **all under `skills/`** (not mine, not touched), and the vendored "Learn from open source codebase" folder adds thousands more: the CI gate is red for other reasons |
| `mypy src launcher.py scripts` (strict) | PASS | "Success: no issues found in 385 source files" |
| `pytest tests/ -q` (full, forwards) | PASS | 4,240 passed, 4 skipped (no symlink privilege on this laptop, a POSIX-only timezone test), 0 failed, 3m26s |
| New Python tests, reverse file order, three runs | PASS | 191 passed each time |
| `npm run typecheck`; `npx vitest run`; `npm run build` | PASS | 462 tests in 35 files; includes the existing No-Terminal guard |
| `detect-secrets scan` on every changed file | PASS | 0 findings in my files (`Settings.tsx` has 8 that are also at HEAD: provider names, not secrets) |
| Real Windows Credential Manager round trip, test-only prefix, dummy value | PASS | write, read, delete, delete again; no entry left (`cmdkey /list`) |
| Real listener on 127.0.0.1:47610 | PASS | one request got its fields, a 200 page, and the port closed |
| Isolated preview server and the real browser pane | PASS (text and wiring) | Settings, Broker view and the Portfolio card render from real routes (200), no console errors; the Copilot answers with the switch off and on. A pixel screenshot could not be taken (the pane did not draw) |
| `scripts/audit-disk-layout.ps1` | PASS | no stray directories |
| `scripts/audit-agent-claims.ps1` | no claim of mine unclaimed | its "STALE" lines are other agents' legacy `D:\quant_system` paths (not mine) |

## Files changed

See "Owned paths". New code is `src/quant_system/broker_view/` (12 modules), `broker_routes.py`, `tools_broker.py`, two screen
components, and 8 Python test files (plus shared fakes) with 191 tests, and 2 screen test files with 24 tests.

## Blockers and conflicts

None. Not done, by design: nothing is committed or pushed (the founder has not asked); nothing was checked against a real
Upstox account (that needs the founder's own sign-in; see the handoff).

## Stop point

Phase 1 is built and verified with invented data. Changes are in the working tree, uncommitted.

## Next safe action

The founder (or an agent they supervise) follows `agent_context/handoffs/20261009-broker-view-phase1-real-account-check.md`.
Commit with explicit paths only, `feat(broker): see your Upstox holdings and cash in QuantOS, view only`, then
`python scripts/release_status.py`.
