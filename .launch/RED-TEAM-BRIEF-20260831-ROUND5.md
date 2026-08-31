# Red Team brief — round five: everything since the round-four repairs

STATUS: OPEN
AUTHOR OF THE WORK UNDER TEST: Claude Code. **You did not write any of it.**

## The pattern, four rounds deep

| Round | Outcome |
|---|---|
| 1 | 8 P1 |
| 2 | round-1 repairs held; **2 new P1s created by them** |
| 3 | round-2 repairs held; **3 new P1s created by them** |
| 4 | round-3 repairs held; **3 new P1s created by them** |
| 5 | ? |

Four for four. Every round the repairs closed what they aimed at and created something new by
composing with code they did not touch. **Assume it again.** A defect that exists only because of
this batch is worth more than a fresh sweep.

## What is different this time, and should change how you work

**The pilot ran live.** For the first time, on 2026-08-31, and three defects were found *by running
it* that four rounds of reading had missed: a permanently no-op bar refresh, a single quote timeout
ending the session, and Upstox never actually serving the pilot at all. **Weight running the thing
over reading it.** `logs/paper_runs/` holds real artifacts from today, including two aborted
attempts kept deliberately (`_fallback_aborted`, `_keyerror_aborted`, `_pre_pnl_fix`).

**A second agent is editing the same files.** `88b78b9d` and `416f560c` are not mine. A peer session
wired Upstox token resolution and carried in dashboard work while I was mid-edit. Two agents on one
path is a defect surface of its own -- check for lost edits, contradictory comments, and behaviour
neither author intended.

**The auto-sync commits whatever is in the tree.** `e853376a` swept my mid-edit working tree and,
earlier, a half-written adjudication. Treat commit boundaries as unreliable.

## Commits in scope

`d6f421e3` .. `a6f3e6f1` (twelve, listed by `git log --oneline 46c7bb67..HEAD`). Note `14ec91da`
and `44583ba4` carry identical subjects -- worth understanding why.

## Known-open, do not rediscover

Round four's remaining P2s/P3s; the auto-sync behaviour; the three false commit-message claims from
round two section 12.1; `reset_session_peak` still has no caller; the drawdown is evaluated only
inside `evaluate_order`.

## Claims to adjudicate — PROVEN / DISPROVEN / NOT TESTED

Skeleton first with everything `NOT TESTED`, then rewrite each section as you finish it. Four
earlier runs hit API limits; the ones that wrote incrementally survived.

1. **The quote-failure tolerance.** `MAX_CONSECUTIVE_QUOTE_FAILURES = 5`, timeout 3s -> 15s. Does a
   transient failure genuinely skip and resume? Can the tolerance mask a real outage -- a feed
   returning stale or partial data indefinitely without ever raising?
2. **The abort path.** Exit 10, `[PAPER PILOT ABORTED]`, `aborted` in the payload, `ABORTED` in the
   status file and the markdown. Find a failure that still reports clean.
3. **The date-aware cache hit.** `_is_current` compares `received_end` to `to_date`. Does the
   refresh now actually fetch? Does it re-download ten years every morning? What happens on a
   symbol that legitimately has no new bars?
4. **`MAX_MISSED_SESSIONS = 0`.** Too strict? Walk real 2026 dates around holidays and long
   weekends and find a legitimate morning it refuses.
5. **`executed_rebalance`.** Both clauses. Is `set(engine.positions) == set(mizan_picks)` the right
   equality -- what about quantities, or a partial fill that leaves the sets equal?
6. **Marked equity shared by sizing and risk.** One number now feeds both. Verify neither consumer
   wanted something different, and that lifting it above the sizing block did not move it before
   something it depends on.
7. **The halt reaches every artifact.** Report, status file, exit code, dashboard.
8. **The resolving AST test.** It was mutation-tested and killed five mutants. **Try to defeat it
   anyway** -- a mutation set chosen by the author tests what the author imagined.
9. **The peer session's token work** (`88b78b9d`). Is preferring `UPSTOX_ANALYTICS_TOKEN` sound? Did
   it interact badly with my `assert_upstox_usable`, or with the single-source removal?
10. **The single-source removal.** Yahoo, the price table and the Rs 1000.00 constant are gone. Find
    a consumer that still assumes full universe coverage, as `base_market[sym]` did.
11. **Anything this batch introduced, overstated, or broke.** Check the commit messages against the
    code; rounds two and four both found false claims in them.

## Rules

- Cite file:line and paste raw output. An assertion without evidence is NOT TESTED.
- Do not repair. Report. Rank P1/P2/P3.
- Do not modify `data/evidence/`, `logs/paper_runs/`, or `.env`.
- Earlier rounds are evidence, not scripture. If one is wrong, say so.
- Write to `.launch/reports/RED-TEAM-20260831-ROUND5.md`.
