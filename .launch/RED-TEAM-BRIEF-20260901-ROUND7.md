# Red Team brief — round seven

DATE: 2026-09-01  
HEAD UNDER TEST: `dd280f06`  
COMMITS IN SCOPE: `d6fde28b..dd280f06` (17 commits; 11 are the round-six P1 repairs)  
PRIOR ROUND: `.launch/reports/RED-TEAM-20260831-ROUND6.md` (7 P1, 10 P2, 4 P3)  
OUTPUT: `.launch/reports/RED-TEAM-20260901-ROUND7.md`

## Why this round exists

An unattended paper session runs at 09:00 IST on 2026-09-02 against the live NSE market with a real
97-position book worth about Rs 9.9 lakh of simulated capital. Sessions until roughly 2026-09-10 are
**holds** — no orders. The rebalance on that day is the first since 2026-08-31 that will place
orders, and it is the first time these eleven repairs will be exercised on a trading path rather
than a holding one.

The question this round must answer, above any individual finding:

> **Has the defect-creation rate converged?**

Rounds two through six found **2, 3, 3, 5, 7** new P1s. Every one of those P1s was created by the
previous round's repairs. If round seven finds seven or more, the repair loop is not converging and
that conclusion is more important than any single defect in it.

## Declared conflict of interest — read this before the verdict

**The adjudicator authored all eleven repairs under test.** This is not an independent pass and its
report must not be cited as one. An author checking their own work re-checks what they already
thought about. It is being run because the alternative is no check at all before the rebalance, and
because rounds two through six establish that *behavioural probes on the running system find things
that reading does not*.

State this in the report header. The strongest verdict available to this round is "survived a
hostile pass by its author", never "adjudicated".

## Standing requirements

1. **Append each finding to the report file the moment it is confirmed.** Do not compose the report
   at the end. The first red-team run on 2026-08-30 died at an API limit and produced nothing; every
   run since has used incremental writes and every one has survived. This is a hard requirement.
2. **Do not modify live state.** Nothing under `data/evidence/`, `logs/paper_runs/`, `.env`, or the
   Windows scheduled tasks may be written. Probe scripts write to the session scratchpad only. The
   2026-09-02 09:00 session must run exactly as it would have.
3. **Mutation standard.** A test that passes against a faithful reproduction of the defect it names
   is worthless. Round six's central finding was 13 of 13 of its mutants surviving because the
   author's mutants were *deletions* while its own *preserved the strings the assertions looked
   for*. Write string-preserving mutants. A located assertion can prove a guard exists; only a
   driven one proves it decides anything.
4. **No repairs.** Adjudication only.

## The eleven claims, as testable propositions

Each is stated as the commit claims it. Your job is to find the case where it is false.

| # | Commit | Claim to break |
|---|---|---|
| C1 | `70016e6c` | `UpstoxClient` prefers `UPSTOX_ANALYTICS_TOKEN`, falls back to `UPSTOX_ACCESS_TOKEN`, and an explicit argument still wins. |
| C2 | `70016e6c` | `marks_for_open_positions` covers **every** held name; an unquoted holding is marked at cost and named in `unmarked_at_close`, and can no longer raise `LedgerInvariantViolation` at `end_session`. |
| C3 | `ad51196d` | A chunk returning HTTP 200 with a non-success body counts as a **failed** chunk against the retry budget, rather than silently losing its symbols and resetting the counter. |
| C4 | `ad51196d` | The daily drawdown anchor persists across a restart on the same session date, so N restarts cannot launder one large decline into N small ones. |
| C5 | `66e0ca3d` | `rebalance_executed` judges a rebalance by coverage of the selection (threshold 0.8), not by exits alone — so one entry fill of four is **not** a completed rebalance. |
| C6 | `66e0ca3d` | `save_portfolio` refuses to write over a file whose hash changed since load, so a concurrent session cannot silently lose the other's fills. **There is still no lock** — overlap is possible, only the silent loss is prevented. |
| C7 | `f4d9c379` | Six decisions are extracted as named functions with behavioural tests, and 10 of 10 string-preserving mutants are killed. |
| C8 | `33ed253c` | A v3 book migrates to v4 **after** the hash check, and the v4 anchor fields default to absent so the baseline comes from the first live mark rather than stale persisted equity. |
| C9 | `02cc3217` | The dashboard serves concurrently, and importing the module no longer writes the Upstox token into `os.environ` as an import side effect. |
| C10 | `780656d6` | A quote that cannot be priced returns `None` and is skipped like an omitted symbol, rather than being stamped `UPSTOX_LIVE_FEED` at Rs 0.00. An unusable depth level is dropped rather than aborting the session. |
| C11 | `2bb91be8` / `ec03b8d8` / `df11af59` | The opening fetch retries; an aborted session does not spend a held session; a 200 carrying no candles cannot replace a good macro cache. |

## Where to look first

Ranked by what would cost the most on 2026-09-10:

1. **C5 and C6 together.** The rebalance day is the only day both run. A wrong `rebalance_executed`
   resets a hold clock that should not reset; a compare-and-swap that mis-detects leaves the book
   inconsistent with its report. These have never run together on a real trading session.
2. **C2 on the *exit* path.** It was fixed for closing marks. Ninety-seven positions get **sold** on
   the rebalance. An unquoted name at exit is a different code path from an unquoted name at mark.
3. **C4 across a date boundary.** The anchor persists per session date. Test the rollover, a
   restart before 09:15, and a restart after a halt.
4. **C10 with a real pre-open payload.** `e47894b8` established that outside market hours 90 of 100
   depth levels are zero and the top-of-book bid is zero on every name. The 09:00 fetch runs in
   exactly that state. Drive the real shape, not a constructed one.
5. **C1's fallback.** `e47894b8` found the primary ISIN-keyed lookup has **never** matched a quote —
   0 of 10 — and the symbol-keyed fallback carries the entire book. Anything that makes the fallback
   look redundant empties the portfolio with no error.

## What round six left unfinished

- 10 P2 and 4 P3 from round six remain open and unrepaired. Confirm they are still live; do not
  re-report them as new.
- R6-01 and R6-02's guards are **unfalsified rather than exercised** — the live probe could not
  manufacture the malformed responses they describe. Say so again if it still holds.
- The `max_position_weight` drift raised in `ec03b8d8` is *reported, not corrected*: the entry loop
  acts only when `current_held == 0`, so `evaluate_order` never runs for a held name and a book 90%
  in one name against a 30% declared limit passes every check. That was deliberately left as a
  decision. Assess whether the rebalance day changes its severity.

## Report shape

Follow round six: a verdict summary table, a one-paragraph verdict, then findings at P1/P2/P3 with a
reproduction for each. End with an explicit answer to the convergence question and a count comparison
against 2, 3, 3, 5, 7.
