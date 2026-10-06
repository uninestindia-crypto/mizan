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

1. Record and notice. IN PROGRESS
2. Halal docs review (findings file). 
3. Copilot engine, test-first (fake LLM). 
4. Multi-model verification, test-first.
5. News and sentiment (injectable fetcher).
6. Saved agents and built-in recipes.
7. Live Upstox quotes (B).
8. Frontend.
9. Gates, real-browser run, minimal live smoke with the environment's keys (names only logged, never values).
10. Commit explicit paths, push, PR. Merge and release are the founder's call.

## Commands and outcomes

(updated at checkpoints)

## Files changed

(updated at checkpoints)

## Blockers and conflicts

`20260928-claude-retail-redesign-build.md` (HANDOFF_REQUIRED) still names `frontend/**` and `src/quant_system/server/v2/**`.
Same position as the earlier notices: edits proceed on the founder's explicit instruction; additive notice filed
(`20261006-NOTICE-copilot-and-live-quotes-under-retail-redesign-claim.md`).

## Stop point

Record filed; no product code edited yet.

## Next safe action

Halal docs review, then the Copilot engine tests.
