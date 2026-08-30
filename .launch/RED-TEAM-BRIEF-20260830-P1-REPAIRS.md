# Red Team brief — the repairs to the live paper-trading path (2026-08-30)

STATUS: OPEN
AUTHOR OF THE WORK UNDER TEST: Claude Code. **You did not write any of it.**
PRIOR REPORT: `.launch/reports/RED-TEAM-20260829-LIVE-PAPER-PATH.md` — 8 P1, 11 P2, 2 P3, NOT READY.

## Why this brief exists

The agent that wrote the code under test is also the agent that repaired every finding in the prior
report. That is the situation in which an author is least able to judge whether a defect was fixed
or merely moved. Nothing here is confirmed until you confirm it.

**The prior report is evidence, not scripture.** It was written by another agent under time
pressure. If one of its findings is wrong, say so.

## Commits in scope

| Commit | Claims |
|---|---|
| `2d5f6d31` | P1-1: `RESEARCH_PAPER` surface + `ResearchPaperExemptionV1` + gated loader |
| `bb62bc58` | P1-2..P1-8 and P2-3, P2-6, P2-9, 5.2, 5.4 |
| `c45ee6f8` | P2-1(recorded), P2-2, P2-5, P2-8, P3-1, P3-2 |

## Claims to adjudicate — PROVEN / DISPROVEN / NOT TESTED

Write the report skeleton with every claim `NOT TESTED` as your **first** action, then rewrite each
claim's section the moment you finish it. A previous run of this task died mid-way and produced
nothing because it batched the write.

1. **The carry-forward P&L repair.** Holdings now carry `entry_fee`; the replay charges it;
   `ledger_funding` covers it. Verify cash is still exact *and* that P&L now nets both legs. Attack
   it: many holdings, quantisation at `0.01`, a partial sell, a position bought across two sessions,
   a holding whose entry fee rounds. Does anything double-count now?

2. **Cumulative realized P&L.** Now `previous.realized_pnl + session_realized_pnl`. Does that
   double-count when a carried position is sold — is the carried gain counted once or twice?

3. **The hold length.** Claimed to be exactly 10 sessions. Simulate it independently. Check the
   `sessions_held = 1 on rebalance` convention against a resumed-from-disk portfolio, and across a
   session where the rebalance produced no trades.

4. **The score floor removal.** Claimed faithful to `screen_mizan_out_of_sample.py`. Verify the
   screen really has no threshold. Then check the empty-selection guard cannot be bypassed.

5. **Sizing from `ledger_funding()`.** Does this now double-count carried holdings — funding is
   cash + basis + fees, so is the book being sized against equity it has already deployed?

6. **The trading-day authority.** `data/authorities/nse-trading-holidays.json`, fetched live from
   NSE. Is it the right segment? Complete? Does the guard fail closed on every path you can find?
   Is the staleness bound (4 days) right, or does it refuse legitimate sessions?

7. **Exits before entries.** The blocks were physically swapped. Verify nothing broke: variables
   defined in one block and used in the other, ordering assumptions, the 25-times-per-session loop.

8. **`peak_equity`.** Monotonic and persisted. Can a multi-session decline now actually trip the
   12% total-drawdown switch? Demonstrate it tripping, or show it still cannot.

9. **The RESEARCH_PAPER exemption.** Is it genuinely narrow? Find a way to execute a `REJECT` model,
   or to reach any surface without the verdict check. The AST detector: can you defeat it?

10. **The rank-sort repair and its self-correction.** The author claimed the fix made 244 published
    rows reproducible, then retracted it. Is the *retraction* correct, or is there a way to recover
    the builder's order? Is `test_mizan_store_fidelity.py` actually able to fail?

11. **The 264 restored evidence files.** Verify byte-equality against blobs independently. Did the
    restore lose anything? Is the new guard defeatable?

12. **Anything the author overstated, missed, or broke while repairing.** The open-ended one, and
    the most important. Repairs made under time pressure to close a critical report are exactly
    where new defects enter. Assume some did.

## Rules

- Cite file:line and paste raw command output. An assertion without evidence is NOT TESTED.
- Do not repair anything. Report.
- Rank P1 Critical / P2 Major / P3 Minor.
- Write to `.launch/reports/RED-TEAM-20260830-P1-REPAIRS.md`.
