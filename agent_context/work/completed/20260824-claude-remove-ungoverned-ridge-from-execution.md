# Active work: remove the ungoverned ridge from the execution path

STATUS: COMPLETE — implemented and verified; not independently adjudicated  
OWNER: Claude Code — governed execution  
TOOL: Claude Code  
STARTED_UTC: 2026-08-24T12:00:00Z  
STARTING_REVISION: `13e289a`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

Close the second-calculation-path defect. `strategies/ml_equity.py:17` defines
`RollingRidgeClassifier`, an ungoverned ridge with no purging, no multiplicity accounting and no
evidence. A governed alternative now exists (`execution/governed_strategy.py`), but nothing stops
the ungoverned one reaching an execution surface, which is SLICES.md slice rule 2: a slice "may not
introduce a second calculation path".

## What the exposure actually is, measured before deciding

| Consumer | Path | Live? |
|---|---|---|
| `MLEquityStrategy` | uses `RollingRidgeClassifier` directly | — |
| `AIEnhancedMLEquityStrategy` | uses `RollingRidgeClassifier` directly | — |
| `StrategyRegistry` | exposes both by name | — |
| `server/app.py:670` | `BacktestEngine` over `SyntheticDataGenerator` | **No — research** |
| `server/supervisor.py:157` | `BacktestEngine` over `SyntheticDataGenerator` | **No — research** |
| `RealtimeShadowRunner.__init__` | accepts any `BaseStrategy`, **no guard** | **Yes** |
| `PaperPilot` | takes no strategy (`grep BaseStrategy` -> 0) | n/a |
| `ShadowReplayEngine` | takes a `ShadowDecisionModel`, not a `BaseStrategy` | separate contract |

So the ungoverned ridge is **not currently wired** into a live surface. The defect is that nothing
prevents it: `RealtimeShadowRunner` accepts any `BaseStrategy`, so an operator can hand it
`MLEquityStrategy` and run an ungoverned ridge in a shadow session. That is a real, reachable path,
and it is the one to close.

## Decision: block at the surface, do not delete

The adapter scope record offered both options — "Remove `RollingRidgeClassifier` from every
execution path, **or** relabel `MLEquityStrategy` research-only and block it at the surface." I am
taking the second, and the reason is not convenience.

Deleting `RollingRidgeClassifier` would break `AIEnhancedMLEquityStrategy`, which the advisory layer
wires into (`tests/test_advisory_capture_wiring.py`) — another agent's committed work. It would also
remove a legitimate research capability: an ungoverned ridge in a **backtest over synthetic data** is
research, not a governance violation. The violation is specifically that it can *execute*.

So: the ungoverned strategies declare themselves research-only, and the execution surface refuses
anything so declared. Research and backtest paths are untouched.

## Owned paths

- `src/quant_system/strategies/ml_equity.py`
- `src/quant_system/strategies/ai_enhanced_ml.py` (one class attribute only — the advisory wiring in
  that file is another agent's and is not modified)
- `src/quant_system/execution/realtime_shadow.py`
- `tests/test_ungoverned_strategy_refused.py` (new)
- `agent_context/work/active/20260824-claude-remove-ungoverned-ridge-from-execution.md` (this file)

## Non-goals

- Deleting `RollingRidgeClassifier` or either strategy. See the decision above.
- Touching `tests/test_realtime_shadow.py` (claimed by the S9-B2 record) or any `advisory/` path.
- Changing `BaseStrategy`. The marker is read with `getattr(..., default)` so no existing strategy
  needs to know about it, and the pre-existing S9 test strategies keep working unchanged.
- Claiming this closes the gap for a strategy that embeds an ungoverned model without declaring it.
  A marker is a declaration, not a detector. Stated as a residual below.

## Plan

1. COMPLETE — measure the real exposure; this record.
2. Failing-first regressions.
3. Mark both ungoverned strategies; refuse them at the shadow surface.
4. Gate.

## Current step

All four steps complete.

## Verification

| Check | Result |
|---|---|
| Failing-first | 3 of 6 cases failed before the change; all 6 pass after |
| `uv run pytest -q` | **881 passed** (875 + 6). No regressions |
| Advisory and Slice 9 suites | pass unchanged — the guard did not over-reach |
| Ruff, strict mypy | clean across 121 source files |

Demonstrated behaviour change:

```
EXECUTION SURFACE:
  REFUSED: MLEquityStrategy is marked research_only and cannot drive an execution session...

RESEARCH USE, deliberately untouched:
  RollingRidgeClassifier constructs : True
  MLEquityStrategy constructs       : True
  still in the strategy registry    : True
```

Two tests exist specifically to catch an over-broad guard: a hand-written strategy with no embedded
model, and a runner with no strategy at all, are both still accepted. Those are the shapes the
pre-existing Slice 9 sessions use, and breaking them would have traded one defect for another.

## Files changed

- `src/quant_system/strategies/ml_equity.py`: `research_only = True` on `MLEquityStrategy`.
- `src/quant_system/strategies/ai_enhanced_ml.py`: same marker on `AIEnhancedMLEquityStrategy`. The
  advisory wiring in that file belongs to another agent and was not touched.
- `src/quant_system/execution/realtime_shadow.py`: `_refuse_ungoverned_strategy` at construction.
- `tests/test_ungoverned_strategy_refused.py`: new, 6 cases.

## Residual risk, stated rather than hidden

This blocks strategies that **declare** themselves research-only. A future strategy that embeds an
ungoverned model and does not declare it will not be caught, because nothing here inspects a
strategy's internals. The honest scope is: the two known ungoverned-ridge strategies can no longer
reach a shadow session, and the mechanism to mark any future one exists. Detecting an undeclared
one is a different and much harder problem.
