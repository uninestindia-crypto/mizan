# NOTICE: the No-Terminal Law added to AGENTS.md and GOAL.md on founder instruction

STATUS: NOTICE (additive; no other record is edited)  
FILED_UTC: 2026-10-06  
FILED_BY: Claude Code, `20261006-claude-copilot-agent-and-live-quotes.md`  
FOR: `20260821-claude-concurrent-workspace-rule.md` (STATUS `HANDOFF_REQUIRED`), which lists `AGENTS.md` among its
owned paths. Also the author of `agent_context/GOAL.md` (`20261005-NOTICE-goal-file-added-and-agents-md-edited.md`).  
FILED UNDER: PROTOCOL sections 3 and 4 (shared root guidance files)

## Founder instruction

"everything should be from platform done frontend aka panel and not terminal or backend since trader, investor are non
technical person in terms of coding and development, and make it rule it should not be repeated" (2026-10-06).

## What changed

| File | Change |
|---|---|
| `AGENTS.md` | One new bullet under "QuantOS product laws": the **No-Terminal Law**. Nothing else touched. |
| `agent_context/GOAL.md` | One new tripwire, number 9, in section 4. `GOAL.md` forbids editing tripwires without the founder's instruction; this is that instruction. No goal line or "Done when" test was changed. |
| `agent_context/decisions/20261006-no-terminal-law.md` | New: the decision, a five-point checklist, the guard tests, and the debt found on the day. |
| `frontend/src/lib/noTerminalRule.test.ts`, `tests/test_no_terminal_copy.py` | New guards. Existing violations are listed as known debt that may only shrink. |

## What it does not change

No existing rule in `AGENTS.md` or `PROTOCOL.md` is altered, removed or reworded. Existing violations (the AI-assistants
terminal section and the orders-reminder setting names) are **not** removed by this change; they are recorded as debt for
the founder to schedule.
