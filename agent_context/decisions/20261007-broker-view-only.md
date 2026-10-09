# Broker view: a view-only connection to the person's broker

DATE: 2026-10-07 (designed), 2026-10-09 (built, Phase 1)
GOAL_LINE: G6, with G1, G2 and G4
FOUNDER INSTRUCTION: a read-only connection so the platform and its AI know where the account stands, without access to
it, at no cost (chat, 2026-10-07; "execute it", 2026-10-09)
BRIEF: `agent_context/handoffs/20261007-broker-view-only-build-brief.md`
OWNER_RECORD: `agent_context/work/completed/20261009-1000Z-claude-sonnet-broker-view.md`

## What was decided

1. **Upstox first.** The person's own free developer app, signed in daily on Upstox's own page, returning to a one-shot
   listener on `127.0.0.1:47610`. Zerodha Kite Personal is Phase 2.
2. **View-only is three locks.** Upstox refuses orders from an app with no registered static IP (its published rule since
   2026-04-01, never tested by sending an order). Our package has a closed list of broker addresses
   (`broker_view/endpoints.py`, `ALLOWED_CALLS`), reads through the GET-only transport the rest of QuantOS uses, and has one
   session transport that takes no address. The assistant sees a summary only, behind a switch that starts off.
3. **The view key has its own Credential Manager entry** (`ScopedCredentialStore`, prefix `QuantOS:BrokerView:`). It is not
   in `SECRETS`, so it is never listed by `CredentialStore.status()` and never copied into the process environment by
   `apply_to_environment()`. It is never logged, returned, prompted or written to a file.
4. **Holdings, positions and cash only.** No order book, trade book, mutual funds or P&L reports. The only non-GET calls are
   the sign-in swap and the sign-out, and both go to the broker's sign-in service.
5. **QuantOS does its own sums** (invested, value, profit or loss, today's move) in `Decimal` from prices and quantities.
   The broker's own totals and its `pnl` field are not used: their units and timing differ between accounts.
6. **Fail closed and say so.** A row that fails any check is skipped and counted. A key that says it has ended is forgotten
   without asking Upstox. A refused key is forgotten and the last figures stay with their time. The registered-address reply
   (`UDAPI1221`) is a different problem from a bad key, so the key stays.

## Why

The person needs to know where their account stands, and the evidence rule needs every figure to say where it came from and
when. Reading is free at Upstox and Zerodha and needs no static IP: since 2026-04-01 only order place, modify and cancel do.
This is not order routing (T4) and writes nothing to the account.

## Rejected alternatives

| Alternative | Why not |
|---|---|
| Upstox one-year analytics key | Read-only, but holdings need a whitelisted static IP: a paid add-on, and laptops change networks. Measured 2026-08-31: `401 UDAPI1221` |
| Upstox extended key | Only for registered business (multi-client) apps |
| Account Aggregator | Needs a regulated financial-information user |
| Angel One client code + MPIN + TOTP | The app would hold a full sign-in, the opposite of view-only |
| Cloud webhook (Upstox access-token request) | Costs money, and the key would leave the laptop |
| Reuse `UPSTOX_ACCESS_TOKEN` | It is copied into `os.environ` and shared with other features; the view key should be held by as little code as possible |
| Return address on the app's own port | The port is chosen at start-up (from 8080); a broker return address must match exactly |
| Copy code from PyBroker or Qlib (the two projects under "Learn from open source codebase") | Neither has any broker-account connector (PyBroker has market-data sources and simulated portfolios; Qlib has simulated accounts). PyBroker is also Apache 2.0 with the Commons Clause, which withholds the right to "Sell" a product whose value derives substantially from it. Nothing was copied |
| A background job that signs in by itself | Would need a stored password or a trading PIN. The person clicks once a day instead |

## Built in Phase 1

`src/quant_system/broker_view/` (endpoints, messages, model, parse, read, login, session, loopback, store, summary, service),
`server/v2/broker_routes.py`, `copilot/tools_broker.py` (the `broker_account` tool and its built-in answer), `ScopedCredentialStore`,
Settings, then Broker view, and a card on Portfolio. Tests: `tests/test_broker_view_*.py`, `tests/test_copilot_broker_tool.py`, and
two screen test files.

## Known limits, stated rather than hidden

- The person signs in once a day. Upstox ends the key at 3:30 am India time.
- Each person creates their own broker app once, on the broker's site, guided by the screen.
- The broker's lock is the broker's published rule. We do not test it, because testing it means sending an order.
- **Not yet checked against a real account**: the cash reply's exact shape (both shapes are accepted and tested with invented
  replies), the meaning of the recently-bought quantity (shown apart and not valued as held), and whether signing out also
  signs the person out of their Upstox mobile app. Brief section 12 lists the steps; the founder does the clicking.
- The listener binds with exclusive use on Windows. On other systems it relies on the port being free; a busy port is reported.
- The screens were checked in a real browser against the running server for their text and wiring; a pixel screenshot could not
  be taken because the browser pane was not drawing.
