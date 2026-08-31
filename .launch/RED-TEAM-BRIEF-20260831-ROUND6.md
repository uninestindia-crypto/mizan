# Red Team brief — round six: the round-five repairs

STATUS: OPEN
AUTHOR OF THE WORK UNDER TEST: Claude Code. **You did not write any of it.**

## The pattern is not converging

| Round | New P1s | Where they came from |
|---|---:|---|
| 1 | 8 | pre-existing |
| 2 | 2 | created by round 1's repairs |
| 3 | 3 | created by round 2's repairs |
| 4 | 3 | created by round 3's repairs |
| 5 | 5 | created by round 4's repairs |

Round five found **more** than round four. Five rounds in, the repair rate and the defect-creation
rate are roughly matched. Do not assume this batch is cleaner because the last one was smaller; it
was not smaller.

## What is specifically different about this batch

**Every fix was mutation-tested before being claimed.** F7 1 mutant, F1 2, F23 4, F4 3, F20 4 --
all killed. That is a real improvement in method and it is also the thing most worth attacking:
**a mutation set chosen by the author tests what the author imagined.** Write your own mutants. If
one survives, the fix is unguarded whatever the commit message says.

**The author's tests have been worthless seven times in this sequence**, always passing, only ever
caught by mutation. F23's test took six attempts. If any test in this batch can be satisfied by code
that reproduces the defect, that is a finding regardless of what the mutants said.

**A live session ran today** — 12:17 to 14:21, 97 real Upstox-priced holdings, then an abort.
`logs/paper_runs/` holds the artifacts and three deliberately preserved aborted attempts. Running
things has found more than reading them, five rounds running.

## Commits in scope

`739859a1` .. `d6fde28b` — four fixes plus one auto-sync checkpoint whose contents you should not
assume were deliberate.

## Known-open, do not rediscover

Round five's 15 P2 / 9 P3; the auto-sync committing whatever is in the tree; round two's three false
commit-message claims; the drawdown evaluated only inside `evaluate_order`.

## Claims to adjudicate — PROVEN / DISPROVEN / NOT TESTED

Skeleton first with everything `NOT TESTED`; rewrite each section as you finish it. Five earlier
runs hit API limits and the incremental ones survived.

1. **F7, the summary file.** Does the refresh now write only its own? Does anything else still
   default to the all-market path? Is the restored 3,359-entry file actually the right content, or
   just the right length?
2. **F1, the quote-batch failure.** Transport failure vs genuine absence. Can a feed return HTTP 200
   with empty or garbage payloads indefinitely and never trip either path? What happens when every
   chunk fails on the very first poll of a session?
3. **F23, the quote lookups.** Four located assertions replaced a failed analysis. Find a fifth
   consumer, or a way to reintroduce the crash that all four assertions still pass.
4. **F4, the rebalance flag.** `bool(engine.positions) and (bool(entry_fills) or holds_the_selection)`.
   Attack it: a partial entry fill, a rebalance that legitimately ends flat, a book that holds names
   outside the selection, quantities that differ while the symbol sets match.
5. **F20, the daily peak anchor.** Anchored to the first live mark before any order. What if the
   first poll fails and the anchor is skipped — does it anchor late, or never? What if the session
   starts mid-day, or the market gaps *up*? Does `reset_session_peak` interact correctly with the
   carried `peak_equity`?
6. **The mutation sets themselves.** For each of the five fixes, write mutants the author did not.
   Report every survivor.
7. **Concurrency on `portfolio_state.json`** — round five's largest `NOT PROBED`. No lock, no
   compare-and-swap, and the dashboard's start control permits two sessions. Build the repro the
   last round did not: does the second session to finish discard the first's whole trading day?
8. **Tomorrow's 09:00 hold session**, on this code, resuming 97 holdings with `sessions_held: 1`.
   Walk it. What is the first thing that goes wrong?
9. **Anything this batch introduced, overstated, or broke.** Check the commit messages against the
   code; rounds two, four and five all found false claims in them.

## Rules

- Cite file:line and paste raw output. An assertion without evidence is NOT TESTED.
- Do not repair. Report. Rank P1/P2/P3.
- Do not modify `data/evidence/`, `logs/paper_runs/`, or `.env`.
- Earlier rounds are evidence, not scripture. Say so if one is wrong.
- Write to `.launch/reports/RED-TEAM-20260831-ROUND6.md`.
