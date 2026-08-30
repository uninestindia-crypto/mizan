# Active work: declared RESEARCH_ONLY exemption for the paper observation surface

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-30T00:00:00Z
STARTING_REVISION: c5593cae
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Close P1-1 of `.launch/reports/RED-TEAM-20260829-LIVE-PAPER-PATH.md`: a `RESEARCH_ONLY` model
executes daily on the paper surface while three docstrings assert it cannot, because
`scripts/run_paper_pilot_session.py` calls `MizanModel.default_model()` directly and never
constructs the strategy class where the verdict gate lives.

Founder decision, 2026-08-30: **option (b)** -- do not stop the pilot, and do not weaken the
existing gate. Introduce a narrow, declared exemption so that running an unpromotable model on a
paper-only surface is a stated policy with a decision record behind it, rather than the accidental
consequence of bypassing a guard.

## Scope

- A new `ExecutionSurface.RESEARCH_PAPER` admitting **only** `PromotionState.RESEARCH_ONLY`.
- A required `ResearchPaperExemptionV1` acknowledgement naming the decision record.
- One gated entry point in `execution/` for obtaining a model for execution.
- A test that detects an execution script importing `default_model` directly.

## Non-goals

- Live-money routing. Unchanged and still excluded.
- Weakening `SURFACE_ALLOWED_VERDICTS` for SHADOW, PAPER_PILOT or PAPER. Those ceilings are
  untouched and `REJECT` remains admissible nowhere.
- Promoting any model. Nothing here changes a verdict or a gate threshold.
- The other seven P1s in the report. Separate work.

## Owned paths

- src/quant_system/execution/governed_strategy.py
- src/quant_system/execution/cross_sectional_strategy.py
- src/quant_system/execution/mizan_execution.py (new)
- scripts/run_paper_pilot_session.py (see conflict note below)
- tests/test_research_paper_exemption.py (new)
- agent_context/decisions/20260830-paper-surface-research-only-exemption.md (new)
- agent_context/work/active/20260830-claude-research-paper-exemption.md

## Blockers and conflicts

`agent_context/work/active/20260826-antigravity-paper-trade-live-market-testing.md` is ACTIVE and
claims `scripts/run_paper_pilot_session.py`. Editing it here is a founder-instructed override, the
second on this file. Their record is not edited; an additive notice is left at
`agent_context/work/active/20260830-NOTICE-paper-pilot-session-edited-under-antigravity-claim.md`
per PROTOCOL section 8.4.

## Current step

Implementing.

## Commands and outcomes

```
.venv/Scripts/python.exe -m ruff check .        -> All checks passed!
.venv/Scripts/python.exe -m ruff format --check -> 500 files already formatted
.venv/Scripts/python.exe -m mypy src            -> Success: no issues found in 141 source files
.venv/Scripts/python.exe -m pytest -q           -> 1135 passed (was 1104; 31 added)
.venv/Scripts/python.exe scripts/run_paper_pilot_session.py --help -> import chain clean
```

## Files changed

- `src/quant_system/execution/governed_strategy.py` -- `ExecutionSurface.RESEARCH_PAPER`;
  `SURFACE_ALLOWED_VERDICTS[RESEARCH_PAPER] = {RESEARCH_ONLY}`; `ResearchPaperExemptionV1`;
  `require_surface_admits`, now the single implementation both strategies call.
- `src/quant_system/execution/cross_sectional_strategy.py` -- accepts `research_exemption`, records
  it in `params`, and delegates the gate. `_EXECUTABLE_VERDICTS` is now the union over surfaces
  rather than SHADOW's set, which stopped being the widest when RESEARCH_PAPER was added.
- `src/quant_system/execution/mizan_execution.py` (new) -- the gated chokepoint.
- `scripts/run_paper_pilot_session.py` -- both model acquisition sites go through it; the direct
  `MizanModel` import is gone.
- `tests/test_research_paper_exemption.py` (new, 28 tests), plus updates to
  `tests/test_governed_strategy.py` and `tests/test_cross_sectional_strategy.py`.

## Behaviour changed, stated plainly

`RESEARCH_ONLY` was previously refused at *bundle construction* ("not executable on any surface").
It is now bundleable, and refused at the surface instead. Two tests that pinned the old rule were
rewritten rather than deleted, and a test was added for what still stops it. `REJECT` is unchanged
and remains executable nowhere.

## Verification that the detector can fail

The new `test_no_executing_script_obtains_a_model_outside_the_gate` was run against the pre-fix
source from `HEAD:scripts/run_paper_pilot_session.py`, which reported
`['default_model', 'sprint_50k_model']` -- so it fails on the defect it exists to catch, and passes
now. A guard that cannot fail would have been worth nothing here, since all 8 P1 findings passed
ruff, mypy and 1104 tests.

## Still open

The other seven P1 findings are untouched. `Disable-ScheduledTask` was run on
`QuantOS Mizan Paper Session` (State: Disabled) and it must stay disabled until at least P1-2
(realized P&L), P1-3 (hold length), P1-5 (sizing base) and P1-6 (holiday inversion) are repaired.

## Stop point

Complete for P1-1. Gates green. Nothing committed at the time of writing.

## Next safe action

Repair P1-2 and P2-3 in `execution/paper_portfolio.py` -- accumulate realized P&L, and stop the
zero-fee carry-forward hiding the entry cost.
