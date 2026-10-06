# Active work: agentic Copilot in the new app, independent multi-model second opinions, live Upstox prices

STATUS: ACTIVE  
OWNER: Claude Code (cloud session)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-06T05:09Z  
STARTING_REVISION: 0a22d7c9ed5e896ae133c4e1824b1066a24c7157 (origin/main at start; the branch was rebased onto it)  
WORKTREE_OR_BRANCH: `/home/user/mizan` (cloud clone), branch `claude/wonderful-wozniak-6ek6zl`. No other worktree.

GOAL_LINE: G6 (real benefit to retail users), serving G2 (Mizan transparency), G5 (honest evidence: AI opinions never
presented as an edge) and G4 (the Copilot works with no AI key and no broker credentials).

## Objective

Founder instructions, 2026-10-06, in order:
1. "do A first then B with upstox": **A** a Copilot panel in the new app; **B** live Upstox prices in the new app.
2. "full fledged Copilot feature agentic type ... use it as assistant in platform and create workflow or agent",
   "when my model selects any stock ... checked and rechecked with as much ai model as I would like ... independent and
   not biased", plus "news search sentiment search and fundamental analysis".
3. "read halal investment docs from docs section and tell me what needs to change in doc and how to implement it ...
   transparency to user on halal investment and how it works ... real life time". This is a **review deliverable**
   (a findings file), not a build.

## Added instruction, 2026-10-06 (founder)

"everything should be from platform done frontend aka panel and not terminal or backend ... make it rule it should not be
repeated." Recorded as the **No-Terminal Law** (`AGENTS.md`, `GOAL.md` tripwire 9, decision
`agent_context/decisions/20261006-no-terminal-law.md`). For this work it means: the Copilot, second opinions, agents,
workflows, model choice and live prices are all set up and used from screens, in plain words, with no JSON, files or
commands; every error names the next click.

## Owned paths

- `AGENTS.md` (one bullet), `agent_context/GOAL.md` (one tripwire), `agent_context/decisions/20261006-no-terminal-law.md`
- `frontend/src/lib/noTerminalRule.test.ts`, `tests/test_no_terminal_copy.py` (guards)

- `src/quant_system/copilot/**` (new): LLM transport, tool registry, bounded agent loop, verification panel, news, saved agents
- `src/quant_system/live/**` (new): batch quote service, market-session label
- `src/quant_system/server/v2/copilot_routes.py`, `live_routes.py` (new); one `include_router` line in `server/v2/router.py`
- `frontend/src/components/copilot/**`, `frontend/src/lib/copilot.ts`, `frontend/src/lib/live.ts` (new)
- `frontend/src/components/Layout.tsx`, `frontend/src/pages/Stock.tsx`, `frontend/src/pages/Home.tsx` (mount points only)
- `tests/test_copilot_*.py`, `tests/test_live_quotes.py` (new)
- `reports/halal_docs_review/**` (new): the review deliverable

### Parallel workers (founder asked for simultaneous agents, 2026-10-06)

All run in this one checkout on **disjoint exact paths**, under the contract in
`agent_context/decisions/20261006-copilot-api-contract.md`. No worker commits, stages, formats outside its own paths,
or runs a repository-wide command; the coordinator (this session) stages explicit paths and commits.

| Worker | Exact paths |
|---|---|
| Coordinator | `src/quant_system/copilot/**`, `tests/test_copilot_*.py`, `tests/copilot_fakes.py`, `src/quant_system/server/v2/copilot_routes.py`, `tests/test_copilot_routes.py`, `src/quant_system/server/v2/router.py` (include lines only) |
| Live prices (backend) | `src/quant_system/live/**`, `src/quant_system/server/v2/live_routes.py`, `tests/test_live_quotes.py`, `tests/test_live_routes.py` |
| Copilot screens | `frontend/src/components/copilot/**`, `frontend/src/lib/copilot.ts`, `frontend/src/lib/copilot.test.ts`, `frontend/src/components/Layout.tsx` (drawer mount and an Agents menu link), `frontend/src/pages/Stock.tsx` (one Second opinion button) |
| Agents and live-price screens | `frontend/src/components/live/**`, `frontend/src/lib/live.ts`, `frontend/src/lib/agents.ts`, `frontend/src/lib/*.test.ts` for those, `frontend/src/pages/Agents.tsx`, `frontend/src/App.tsx` (the route), `frontend/src/pages/Home.tsx` (price chips), `frontend/src/pages/Stock.tsx` (price header only) |

`frontend/src/pages/Stock.tsx` is shared by two workers: each re-reads it immediately before a small targeted edit.

## Non-goals

- No order placement, no order tool, no account write. The Copilot is read-only and can only *propose* a screen to open.
- No change to `src/quant_system/assistant/**` (the classic console's rule-based Copilot stays as it is).
- No new model trial, sweep or retrain. AI second opinions are explanations, never a promotion gate.
- No claim, in any user-facing text, that AI agreement is evidence of an edge (GOAL tripwire 4).
- Other brokers' data (Zerodha, Angel One, Dhan, Fyers): not started.

## Decision rationale

- **Separate package, own chat transport.** `alpha/direct_providers.py` hard-codes a system prompt, a 5 s timeout and
  1024 output tokens for advisors; an agent needs a real system/user split and longer waits. The new transport reuses
  each provider's endpoint and live model choice, and leaves the shared file untouched.
- **Text-protocol tool loop, not provider function-calling.** Eight providers, three wire shapes, three different
  tool-calling schemas. A strict JSON protocol validated on our side works on every provider and is testable with a fake.
  Bounded (max 6 steps), allowlisted, read-only tools.
- **News and headlines are untrusted text.** Delimited, never obeyed, never able to trigger an action; proposals are
  buttons the person clicks.
- **Independence by construction.** Each model gets the same fact pack in a separate call, never sees another's
  answer. A *blind* arm omits that the platform's model picked the stock; an *informed* arm includes it; a stance shift
  between arms is reported as an anchoring signal. A *recheck* repeats with the fact sections reordered; unstable models
  are flagged.
- **Halal: the deterministic screener decides, the AI only explains.** The Copilot calls the existing screener and
  quotes its ratios, thresholds, data date and verification status.
- **Honest limits stated up front:** the bundled Shariah database is 39 hand-entered FY24 sample companies labelled
  `UNVERIFIED_SAMPLE`; the app has no fundamentals feed beyond that and price statistics.

## Plan

1. Record and notice. DONE
2. Halal docs review (`reports/halal_docs_review/REVIEW.md`). DONE; founder decisions listed there are still open.
3. Copilot engine, test-first with a fake LLM. DONE
4. Independent multi-model second opinions, test-first. DONE
5. News and tone (injectable fetcher). DONE
6. Saved agents and ready-made recipes. DONE
7. Live Upstox prices, read-only. DONE (one real request while the market was open; after-hours only against invented replies)
8. Frontend: Copilot drawer, Second opinion, Agents screen, live price chips. DONE, in review (see below)
9. Gates, adversarial review, real-browser checks. DONE: adversarial backend review fixed; browser checks of the Agents
   screen, live chips, Copilot drawer and Second opinion dialog fixed and re-measured.
10. Push, PR. PUSHED to `claude/wonderful-wozniak-6ek6zl`, `main` merged in (nothing new on `main` at the last check). No PR
    opened: the founder decides on PR, merge and release (merge `main` in, never rebase).

## Workers

Parallel workers ran on disjoint paths under one coordinator (this session), as the founder asked on 2026-10-06:
live-price backend, Copilot screens, Agents and live-chip screens, an independent adversarial reviewer (read-only), three
fix workers (transport/guard/routes; verify/news/live honesty; rules/units/copy/wiring) and two browser QA workers.
No worker committed; the coordinator verified each report by re-running its gates and committed explicit paths.

## Commands and outcomes

- Backend: `uv run --frozen pytest tests -q` with the Upstox variables unset and an isolated `--basetemp`:
  3866 passed, 17 skipped (Windows-only), 0 failed, at `b643eefca`, before the last small fixes. Re-run before PR.
- Copilot and live subset after the last fixes: `pytest tests/test_copilot_*.py tests/test_live_*.py tests/test_no_terminal_copy.py`
  1203 passed.
- Static gates on every changed Python file: `ruff check`, `ruff format --check`, `mypy --platform win32`, `vulture
  --min-confidence 80`, `detect-secrets scan`, `node scripts/check-code.mjs`, `node scripts/check-tests.mjs`: clean.
- Frontend (from `frontend/`): `npx tsc --noEmit -p .` clean, `npx vitest run` 27 files / 335 tests passed, `npm run build` OK.
- Adversarial review: 4 P1, 13 P2 and a set of P3 findings, all but the unreproducible ones fixed and test-proven.
- Live smoke: one read-only request for one symbol through the live service while the market was open returned a
  `LIVE` price with a time. No key, header or body was printed.
- Browser QA (Chromium, fake AI, fake Upstox, no real network): Agents screen and live chips checked; findings below.

## Files changed

- Engine: `src/quant_system/copilot/**` (new: loop, tools, rules, guard, finalise, verify, news, agents, workflow),
  `src/quant_system/live/**` (new), `src/quant_system/server/v2/{copilot_routes,copilot_validation,copilot_wiring,live_routes}.py`
  (new), `router.py` (include lines and one import), `spa.py` (the `/agents` route), `credentials.py` (refuse a key with
  a space or line break).
- Screens: `frontend/src/components/{copilot,agents,live}/**`, `frontend/src/lib/{copilot,agents,live}.ts`,
  `frontend/src/pages/Agents.tsx`, edits to `Layout.tsx`, `Home.tsx`, `Stock.tsx`, `App.tsx`.
- Tests: `tests/test_copilot_*.py`, `tests/test_live_*.py`, `tests/copilot_fakes.py`, `tests/live_fakes.py`,
  `tests/test_no_terminal_copy.py`, `tests/test_credentials_import.py`, frontend tests beside the code.
- Records: `agent_context/decisions/20261006-{no-terminal-law,copilot-api-contract,copilot-design}.md`,
  `reports/halal_docs_review/REVIEW.md`, `AGENTS.md` (one bullet), `agent_context/GOAL.md` (tripwire 9).

## Blockers and conflicts

`20260928-claude-retail-redesign-build.md` (HANDOFF_REQUIRED) still names `frontend/**` and `src/quant_system/server/v2/**`.
Same position as the earlier notices: edits proceed on the founder's explicit instruction; additive notice filed
(`20261006-NOTICE-copilot-and-live-quotes-under-retail-redesign-claim.md`).

## Stop point

All work is committed and pushed on `claude/wonderful-wozniak-6ek6zl`; the working tree is clean. `python scripts/release_status.py`
says a release is DUE (23 user-visible changes since v2.4.0, suggested minor, v2.5.0). It is cut from `main`, so it waits
on the founder merging this branch.

Known limits, stated rather than hidden (full list in `agent_context/decisions/20261006-copilot-design.md`): the advice
and halal word lists are not a full defence and do not cover other languages; the fundamentals and halal data are the
39-company hand-entered sample; after-hours and holiday price labelling was verified only against invented replies; the
batch-splitting retry for one bad share was verified only against a stand-in transport; `live/` calls three private
helpers in `data/upstox_parsing.py`; no real AI provider was called in any test (all scripted); real screen-reader
output and the Windows desktop shell were not checked; one `mypy` message about the optional `webview` package appears
only where it is not installed (unrelated to this branch).

## Next safe action

Founder: say whether to open the PR, merge to `main`, and cut v2.5.0 (`powershell -ExecutionPolicy Bypass -File
scripts/release.ps1 -DryRun` first). Open founder decisions are in `reports/halal_docs_review/REVIEW.md` and
`agent_context/GOAL.md` section 7. When the work is accepted, move this record to `agent_context/work/completed/`.
