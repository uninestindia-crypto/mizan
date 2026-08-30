# Red Team brief — the live paper-trading path (2026-08-26 .. 2026-08-29)

STATUS: OPEN
AUTHOR OF THE WORK UNDER TEST: Claude Code (this brief's author). **You did not write any of it.**
ADJUDICATOR REQUIREMENT: an agent with no stake in the outcome. Do not defend these claims. Your
job is to break them.

## Why this brief exists

Every claim below was made by the agent that wrote the code. Earlier in this same programme an
author-written subsystems report was rejected on exactly that ground, and that rejection is void if
the same author then self-certifies this work. So the claims are listed here unproven.

## Commits in scope

| Commit | What it claims to do |
|---|---|
| `c5143c90` | cross-sectional execution strategy (`execution/cross_sectional_strategy.py`) |
| `fa9fb9fa` | canonical 400-bar window + shared Mizan v3 kernel (`modeling/mizan_features.py`) |
| `e18a0e0e` | clears 44 ruff findings, "three real defects among them" |
| `7fb85e83` | live cross-section built by the shared kernel (`execution/mizan_live_features.py`) |
| `1ca08813` | unattended pre-open refresh + scheduled session (`scripts/run_scheduled_paper_session.py`) |
| `21b604ac` | `.gitattributes` autocrlf fix; equal-weight selection |
| `3b9b265a` | test that opens a committed evidence store |
| `b3e626b5` | portfolio held across sessions (`execution/paper_portfolio.py`) |

## Claims to adjudicate — PROVEN / DISPROVEN / NOT TESTED

Work in this order. **Append your verdict to the report file after each claim**, so that if you are
cut off mid-run the evidence you did gather survives. Do not batch the write to the end.

1. **The 400-bar canonical window is derived, not chosen.** `MIZAN_CANONICAL_WINDOW_BARS = 400` is
   justified by Wilder RSI seed influence decaying as `(13/14)^n`. Check the arithmetic yourself.
   Then check the harder half: `MIZAN_WINDOW_BARS` was deliberately left at 51. The author's stated
   reason is that raising it would move the loop start in `build_mizan_feature_dataset`, drop
   published rows, and change every `preprocessing_input_hash`. Is that true, or is it a
   rationalisation for leaving an inconsistency in place?

2. **Kernel fidelity.** `compute_mizan_feature_values` is claimed to reproduce what training
   computed, for the published store. Verify against the actual published feature rows, not against
   the author's tests. The kernel is deliberately float, not Decimal. Attack that choice.

3. **Carry-forward arithmetic** (`paper_portfolio.py`). `ledger_funding()` = cash + holdings at cost,
   and the replayed zero-fee buys are claimed to debit exactly that back out, reconstructing cash
   *exactly*. Attack adversarially: quantisation at `Decimal("0.01")`, an odd average cost, a
   holding whose `cost_basis` rounds, many small holdings, a holding large enough to matter. Any
   drift compounds every session. Also: is the zero-fee replay honest, or does it hide a cost?

4. **The rebalance clock.** `rebalance_due` returns `sessions_since_rebalance >= horizon_sessions`.
   The screen held 10 sessions; the model card declares `label_horizon_sessions = 11`. Determine
   whether the executed hold length equals the measured one, or is off by one. State which.

5. **Exit rule gating.** The author found and fixed a defect where the exit rule would liquidate every
   holding on a hold session. Confirm the fix is complete in `scripts/run_paper_pilot_session.py`,
   and look for the same class of bug elsewhere in that script.

6. **The extreme-row guard.** `refuse_extreme_rows` with `MAX_STANDARDIZED_DEVIATION = 25.0`. Where
   does 25 come from? The author's earlier stated justification for a related claim was withdrawn as
   wrong once measured. Decide whether 25 is derived or picked.

7. **Equal-weight sizing** is claimed to be faithful to what was measured. Check against the screen's
   own construction.

8. **The autocrlf fix** (`data/evidence/** -text`) is claimed verified after a full checkout cycle.
   Reproduce that, or show it is unverified.

9. **The scheduled runner's guards** (exit 2 weekend, 3 empty cache, 4 bars not advancing, 5 macro not
   covering). Find a path where the session runs and produces a plausible-but-wrong report without
   tripping any guard.

10. **Anything the author overstated and did not catch.** This is the open-ended one and it matters
    most. Two self-corrections are already on record (a cost hypothesis falsified by measurement; an
    out-of-domain claim whose mechanism was wrong). Assume there are more.

## Rules

- Cite file:line and paste raw command output. An assertion without evidence is NOT TESTED.
- Do not repair anything. Report.
- Rank findings P1 Critical / P2 Major / P3 Minor.
- Write to `.launch/reports/RED-TEAM-20260829-LIVE-PAPER-PATH.md`.
