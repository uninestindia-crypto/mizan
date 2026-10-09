# Handoff: check the broker view against a real Upstox account, then Phase 2

STATUS: READY_FOR_ADOPTION  
FROM: Claude Code (Sonnet 5.5)  
TO: the founder, then any agent they supervise  
DATE_UTC: 2026-10-09T11:00:00Z  
ACTIVE_RECORD: `agent_context/work/completed/20261009-1000Z-claude-sonnet-broker-view.md`  
BRIEF: `agent_context/handoffs/20261007-broker-view-only-build-brief.md`  
DECISION: `agent_context/decisions/20261007-broker-view-only.md`

## Objective and acceptance criteria

Phase 1 is built and passes every check that can run without a real account. What is left is the part only the founder can do:
sign in to their own Upstox account once and compare what QuantOS shows with what Upstox shows. Nothing here sends an order.

## Completed

- The engine (`src/quant_system/broker_view/`), its routes, the key's own Credential Manager entry, the Copilot tool, the
  Settings tab (Broker view) and the Portfolio card. 191 Python tests and 24 screen tests, all with invented data.
- A real listener on 127.0.0.1:47610 and a real Credential Manager round trip (test prefix, dummy value) both worked.

## In progress

Nothing. Nothing is committed.

## Files and ownership

All in the working tree of the install root, uncommitted. Stage by explicit path (the list is in the active record).

## What the founder does (about ten minutes, and no terminal)

1. Open Upstox's app page, set "Redirect URL" to `http://127.0.0.1:47610/upstox/callback` (the Broker view tab shows it, with a
   Copy button) and leave "Static IP" empty. Copy the app's key and secret into Settings, then Accounts and keys.
   Upstox allows one active app per person since 2026-04-01: if the existing app's redirect address serves another tool,
   changing it may break that tool. Ask before changing it.
2. Settings, then Broker view, then Connect Upstox. Sign in on Upstox's page. Within a few seconds the screen says Connected.
3. Open Portfolio. Compare **Value of holdings** and **Invested** with Upstox's own holdings screen. Write down only
   "matched within one rupee", or the difference and what caused it. Do this once more on a day when you have shares bought
   yesterday (the "arriving" line), to settle which way the broker counts them.
4. Ask the assistant "what's in my broker account?" with the switch off, then on. Note the behaviour, not the answer.
5. Disconnect. Confirm Settings shows not connected and that your Upstox mobile app is still signed in. If the sign-out call
   signed the mobile app out, tell an agent to remove that call (`BrokerView.disconnect`, the `end_session` line).

Do not put any account figure, name, key or screenshot in the repository.

## Known failures and risks

- The exact shape of Upstox's cash reply is not confirmed (both shapes are read and tested with invented replies). If cash is
  empty on the real account, send the shape (names only, no numbers) to an agent.
- The meaning of the recently-bought quantity is not confirmed; it is shown apart and not valued as held.
- Port 47610 may be used by another program on some computers; the screen says so and nothing is opened.
- The vendored folder "Learn from open source codebase" and `skills/` make the repository-wide `ruff` check red (thousands of
  errors from code that is not ours). That is separate from this work but will keep the CI gate red until those folders are
  excluded in `pyproject.toml` or removed. Not touched here: they belong to other agents.

## Exact stop point

The last command was the final frontend rebuild and test run; all green.

## Next safe action

The founder's steps above. After they report, an agent updates `agent_context/decisions/20261007-broker-view-only.md` ("Known
limits") with what was settled, and the founder decides on Phase 2 (Zerodha Kite Personal, free) or Phase 3 (statement import
that works with every broker and needs no key).

## Do not do

- Do not send an order, or anything that looks like one, to test anything.
- Do not add any broker address to `ALLOWED_CALLS` without a decision record and the founder's word.
- Do not copy code from PyBroker (Commons Clause). Qlib is MIT and can be used with its notice, but it has nothing for this.
