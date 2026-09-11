# Active work: maturity horizon for governed models

STATUS: COMPLETE — implemented and mutation-verified; not adjudicated  
OWNER: Claude Code — maturity horizon  
TOOL: Claude Code  
STARTED_UTC: 2026-08-23T00:15:00Z  
STARTING_REVISION: `e6f42b1`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout)

## Objective

Close the last structural divergence between the executing and validated systems on the shadow
surface. `_check_matured_outcomes` (`realtime_shadow.py:550-554`) matures an open entry on the
**first same-symbol quote after its fill**. A governed model is validated on a two-session label —
decision at a session close, entry at the next open, exit at the following open — so under the
current rule a daily-bar model can open and close a position inside a single session, which is not
the strategy the evidence store measured.

## Owned paths

- `src/quant_system/execution/maturity.py` (new)
- `src/quant_system/execution/realtime_shadow.py` (founder grant of `execution/**`)
- `tests/test_maturity_horizon.py` (new)
- `agent_context/work/active/20260822-claude-maturity-horizon.md` (this file)

## Non-goals

- `tests/test_realtime_shadow.py` — claimed by the S9-B2 record, and its count is pinned by two
  in-flight adjudications. New coverage goes in a new file.
- `paper_pilot.py` — it has no maturity concept; it fills orders.
- Removing `RollingRidgeClassifier`.
- Declaring Slice 9 certified.

## Design, and the honest limit of it

**What the validated contract actually says.** `LABEL_HORIZON_SESSIONS_V1 = 2` counts
decision -> entry -> exit. The decision is taken at the close of session T, the entry executes at
the open of T+1, and the exit at the open of T+2. So measured from the **entry**, the position is
held across exactly **one** session boundary and exits on the session after it opened. The policy is
therefore parameterised as `holding_sessions`, defaulting to 1, and its docstring states the
relationship to the label constant so the two cannot drift apart silently.

**What a shadow surface cannot reproduce, and I will not pretend it does.** The validated label
enters and exits at session *opens*. The shadow runner fills on quotes — after the S9-B1 repair, the
first quote later than the decision — so entry and exit instants are intraday, not opens. This
policy therefore does **not** make shadow P&L equal to backtest P&L. What it restores is the
structural property the current code violates: a position opened on one session cannot be closed on
that same session. That is the difference between a two-session strategy and an intraday one, and it
is the part that made the executing system a different strategy rather than merely a noisier
measurement of the same one.

**Session resolution is by instant, not by date.** The entry session is the latest session whose
`open_at` is at or before the entry instant. Comparing aware datetimes avoids converting a UTC entry
time into an exchange-local date, which is where timezone bugs live. The runner works in UTC and the
calendar is IST; for NSE hours those dates coincide, but relying on that coincidence would be a
latent defect.

**Unresolvable sessions fail closed, loudly.** If the calendar does not cover the entry instant, or
runs out of sessions before the horizon, the policy raises `MaturityPolicyError` rather than
returning a maturity instant. Silently maturing would restore exactly the unvalidated behaviour this
work removes; silently never maturing would strand an open position with no signal to the operator.

**Default is current behaviour.** `maturity_policy` defaults to `None`, which preserves
mature-on-next-quote exactly, so every existing S9 test passes untouched and no pinned count moves.
Governed use is opt-in, consistent with `decision_cadence` and `bar_history_provider`.

## Plan

1. COMPLETE — read the maturity path, session tracking, and the label contract; this record.
2. `execution/maturity.py`.
3. Guard in `_check_matured_outcomes`.
4. `tests/test_maturity_horizon.py`, failing-first on the intraday-close defect.
5. Full gate.

## Current step

All five steps complete.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run pytest tests/test_maturity_horizon.py -q` | **12 passed** | 5 runner-driven, 7 policy |
| `uv run pytest` over my scope (8 files) | **106 passed** | maturity, wiring, adapter, shadow, paper pilot, dotenv, preprocessing, ridge |
| `uv run pytest tests/test_realtime_shadow.py tests/test_paper_pilot.py -q` | **43 passed** | unchanged; no pinned count moved |
| **Mutation: remove the horizon guard** | **KILLED by 3 tests** | `refuses_to_mature_inside_the_entry_session`, `not_permitted_one_instant_before_the_next_open`, `longer_horizon_holds_across_more_sessions`. Restored after. |
| `uv run ruff check` over my paths | PASS | `All checks passed!` |

### The full suite is NOT green, and it is not this change

`uv run pytest -q` reports **15 failed, 689 passed**, and `mypy src` reports one error:
`strategies/ai_enhanced_ml.py:109: Name "capture_panel_members" is not defined`.

Every failure is in `tests/test_advisory_capture_wiring.py`, `tests/test_advisory_records.py`, or
`tests/test_server_api.py`, and belongs to the advisory agent's in-flight work: `advisory/` is
untracked and `strategies/ai_enhanced_ml.py` is modified, neither by me. `grep -rln advisory` over
every file I changed returns nothing, so there is no path from this change to those failures.

I did not stash to prove it, because stashing untracked files would have moved another agent's
uncommitted work. The reasoning above is the evidence instead. **Do not read this commit as
restoring a green suite; the suite is not green.**

## Files changed

- `src/quant_system/execution/maturity.py`: new. `MaturityPolicy`, `ImmediateMaturity`,
  `SessionHorizonMaturity`, `MaturityPolicyError`.
- `src/quant_system/execution/realtime_shadow.py`: `RealtimeShadowConfig.maturity_policy`
  (default `None`) and the `_may_mature` guard in `_check_matured_outcomes`.
- `tests/test_maturity_horizon.py`: new, 12 cases.

## Blockers and conflicts

None for the owned paths.

## Stop point

A governed model can no longer open and close a position inside one session when a
`SessionHorizonMaturity` is configured. Default behaviour is unchanged.

### Still not true

- **Shadow P&L still does not equal backtest P&L.** The validated label enters and exits at session
  opens; the shadow runner fills on quotes. This change closes the structural gap, not the pricing
  one, and the module docstring says so.
- **`RollingRidgeClassifier` is still what execution uses by default.** The second calculation path
  is reachable-past, not removed.
- **No live session has run a governed model.** All three governed pieces — adapter, bar history,
  maturity horizon — are proven by tests over fixture acquisitions, never against a real
  `EvidenceStore` in a live session.
- **Slice 9 is uncertified.** No Red Team recheck, no clean-clone Verifier against this tree.

## Next safe action

Either remove `RollingRidgeClassifier` from the execution path, which closes the
second-calculation-path defect outright, or run one real end-to-end governed shadow session sourcing
bars from a real `EvidenceStore` — the first thing that would turn all three governed pieces from
tested into demonstrated.
