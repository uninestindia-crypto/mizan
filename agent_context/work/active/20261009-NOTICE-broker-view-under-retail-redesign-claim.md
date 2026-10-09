# NOTICE: Broker view edits small parts of paths claimed by the retail-redesign record

STATUS: NOTICE (additive; no other record is edited)  
FILED_BY: Claude Code (Sonnet 5.5), `20261009-1000Z-claude-sonnet-broker-view.md`  
FILED_UTC: 2026-10-09  
FOR: `20260928-claude-retail-redesign-build.md` (`HANDOFF_REQUIRED`)  
AUTHORIZATION: founder instruction in chat, 2026-10-09 ("execute it"), carrying out
`agent_context/handoffs/20261007-broker-view-only-build-brief.md`  
FILED UNDER: PROTOCOL section 8.4

## Paths edited that your record names

- `src/quant_system/server/v2/router.py`: one `include_router(broker_router, prefix="/api/v2")`.
- `src/quant_system/server/v2/credentials.py`: a new `ScopedCredentialStore` class. `SECRETS`, `status()` and
  `apply_to_environment()` do not change.
- `src/quant_system/server/v2/copilot_wiring.py`: one more field in `tool_context()`.
- `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Portfolio.tsx`, `frontend/src/lib/{api,queries,types}.ts`:
  a new Settings tab, a card on Portfolio, and their types and hooks.
- `src/quant_system/server/static/app/**`: rebuilt by the frontend build.
- New files under `src/quant_system/server/v2/` and `frontend/src/components/`.

## Section 8.4 preconditions checked

Your record says `HANDOFF_REQUIRED (branch complete and verified; awaiting founder review before any merge)`. It names
no gate that must land before these files change, and the founder asked for this work directly. The numbers it pins
that this could move are test counts: this work adds tests and removes none.

## What this does not change

Existing routes, existing secrets and their handling, hand-entered holdings, paper books, and the Copilot's existing
tools and their guard tests.
