# Active work: wire governed models into the shadow engine

STATUS: COMPLETE — wired and verified; not adjudicated  
OWNER: Claude Code — governed shadow wiring  
TOOL: Claude Code  
STARTED_UTC: 2026-08-22T23:30:00Z  
STARTING_REVISION: `11ee334`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout)

## Why this record exists, and what it found first

The founder asked me to "finish the S9-B2 repair so the engines can be wired". **S9-B2 needs no
further repair.** Verified against the code, not the record, because this repository has already
seen a COMPLETED record make a claim its own diff did not support:

| Claim | Verified at `11ee334` |
|---|---|
| Maturity closes the position | YES — `realtime_shadow.py:577-586` applies the offsetting fill via `_record_hypothetical_fill` at `exit_price` and deducts `friction_fee` |
| `DecisionCadence` exists | YES — `realtime_shadow.py:71`, config field `:211`, consumed `:391` |
| Suites green | YES — `tests/test_realtime_shadow.py` 25 passed, `tests/test_paper_pilot.py` 18 passed |

`20260822-claude-s9b2-repair-and-cadence.md` still reads `STATUS: IN_PROGRESS`, but its own text
says every directed step is complete (S9-B1, S9-B2, S9-B3, S9-M1, S9-M2, S9-M3, S10-B1). Its stated
next action was "do not commit these changes until the adjudicators have finished", and events
overtook it: the automated daily checkpoint `b9377f1` committed the tree anyway.

**That record is not edited by me.** Its status is its owner's to change. This record neither adopts
nor closes it.

## Objective

Populate the missing input the adapter needs. `GovernedModelStrategy` reads point-in-time bar
history from `MarketContext.extra_data[GOVERNED_BARS_KEY]`, and nothing supplied it, so the adapter
could not run in a live session. `realtime_shadow.py:396-403` built its context with
`historical_bars={}` and `extra_data={"current_quote": ...}`.

## Owned paths

- `src/quant_system/execution/bar_history.py` (new)
- `src/quant_system/execution/realtime_shadow.py` (founder grant of `execution/**`)
- `tests/test_governed_shadow_wiring.py` (new)
- `agent_context/work/active/20260822-claude-governed-shadow-wiring.md` (this file)

## Non-goals

- **`tests/test_realtime_shadow.py` is not touched.** It is claimed by the S9-B2 record and pins
  test counts that two adjudications cite. New coverage goes in a new file so no pinned number moves.
- `execution/paper_pilot.py` — verified it never consults a strategy (`grep generate_signals` and
  `MarketContext` both return zero), so it needs no bar plumbing. Wiring it would be motion, not work.
- Removing `RollingRidgeClassifier`. Separate change, separate risk.
- A maturity horizon. Still open, still belongs to the cadence question.
- Declaring Slice 9 certified. No adjudication has run against this tree.

## Design

**Default off, so existing behaviour is bit-identical.** `bar_history_provider` defaults to `None`;
when it is `None` the context is built exactly as before and `GOVERNED_BARS_KEY` is absent. Every
pre-existing S9 test therefore passes untouched. This follows the precedent `DecisionCadence` set.

**The provider is injected, not constructed.** The runner takes a `BarHistoryProvider` protocol
rather than an `EvidenceStore`, so the engine does not learn about evidence storage and the wiring
is testable without one. `AcquisitionBarHistory` is the concrete provider over a governed
`HistoricalAcquisition` — which is what the store yields.

**Availability is filtered at the boundary and again in the strategy.** The decision record
specifies history "filtered to `available_at <= decision_time`", so the provider filters. The
strategy filters again in `_available_window`. Defence in depth: a provider written by someone else
cannot leak a not-yet-available bar into a scored feature row.

## Plan

1. COMPLETE — verify S9-B2 in code; confirm paper pilot needs nothing; this record.
2. `execution/bar_history.py`.
3. Wire `realtime_shadow.py`.
4. `tests/test_governed_shadow_wiring.py`, including one end-to-end governed shadow decision.
5. Full gate.

## Current step

All five steps complete.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run pytest tests/test_realtime_shadow.py tests/test_paper_pilot.py -q` | **43 passed** | 25 + 18, unchanged before and after the wiring. No pinned count moved. |
| `uv run pytest tests/test_governed_shadow_wiring.py -q` | **10 passed** | 3 provider, 3 runner-driven through real `process_live_quote`, 2 config, 2 end-to-end |
| `uv run pytest -q` | **663 passed** | 653 pre-existing + 10 new |
| `uv run ruff check src/quant_system/execution src/quant_system/modeling launcher.py scripts tests` | PASS | `All checks passed!` |
| `MYPYPATH=src uv run mypy src launcher.py` | PASS | `Success: no issues found in 119 source files` |

**Repo-wide `ruff check src` currently FAILS**, in `src/quant_system/advisory/capture.py:9` (I001,
unsorted imports). That is another agent's uncommitted in-flight work, not mine, and I did not
touch it — running `ruff --fix` across `src` would have rewritten their file. Recorded so the next
gate run is not mistaken for a regression from this change.

## Files changed

- `src/quant_system/execution/bar_history.py`: new. `BarHistoryProvider` protocol and
  `AcquisitionBarHistory`, which serves point-in-time bars from governed acquisitions filtered to
  `available_at <= decision_time`.
- `src/quant_system/execution/realtime_shadow.py`: `RealtimeShadowConfig.bar_history_provider`
  (default `None`) and population of `extra_data[GOVERNED_BARS_KEY]` in `process_live_quote`.
- `tests/test_governed_shadow_wiring.py`: new, 10 cases.

## Blockers and conflicts

None for the owned paths. Two Red Teams and one Verifier pinned `c5f7874`; this tree has moved far
past that already, which the S9-B2 notice record documents.

## Stop point

A governed model can now be driven by engine-supplied point-in-time history: the runner populates
`GOVERNED_BARS_KEY` from an injected provider, and the adapter turns it into a signal. Verified
through the real `process_live_quote` path, not a mock of it.

### What is still not true

- **No live session has run one.** The wiring is proven by tests over fixture acquisitions. Nothing
  has yet sourced bars from a real `EvidenceStore` into a real shadow session.
- **`RollingRidgeClassifier` is still what execution uses by default.** A governed alternative now
  exists and is reachable; the ungoverned one has not been removed. The second-calculation-path
  defect remains open.
- **No maturity horizon.** An entry still matures on the first same-symbol quote after its fill.
  Under `ONCE_PER_SESSION` a daily model decides once per session but its position can still mature
  within that session, which is not how the model was validated. This is the largest remaining gap
  between the executing and validated systems, and it is not closed.
- **Slice 9 is not certified.** No Red Team recheck, no clean-clone Verifier against this tree.

## Next safe action

Close the maturity-horizon gap, because it is now the binding one: a daily-bar model whose position
matures intraday is not executing the strategy that was validated. That needs a holding period on
`ShadowProposal` and a maturity rule that respects it.
