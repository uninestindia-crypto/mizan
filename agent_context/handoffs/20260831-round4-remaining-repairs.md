# Handoff: the four items round four left open

CREATED_UTC: 2026-08-31T04:35:00Z
CREATED_BY: Claude Code
STARTING_REVISION: d6f421e3
SCHEDULED_FOR: after NSE close today, 2026-08-31 15:30 IST. Founder instruction: do not touch the
tree before then -- `d6f421e3` is the only revision anyone has driven end to end, and today's
session runs on it.
DEADLINE: session 11, the first rebalance, roughly 2026-09-14. All four fire there, none before.
SOURCE: `.launch/reports/RED-TEAM-20260830-ROUND4.md`

## Do not start before market close

Today's 09:00 session is running on `d6f421e3`. Round four verified that exact path end to end and
nothing found fires on a first session. Editing before the close would swap a verified revision for
an unverified one for no gain, because none of these four items can bite until session 11.

## 1. P1-3 (Blocker) — a refused rebalance is recorded as one that happened

`scripts/run_paper_pilot_session.py:1272` passes `rebalanced=rebalancing` — the **intent**. Round
four's session 21: `fills=0 rejected=228`, book unchanged, and the state records `sessions_held=1`
with `last_rebalance_on` advanced.

Repair: derive the flag from the **outcome**. A rebalance happened only if at least one order
actually filled this session. `rebalancing and reconciliation.total_fills_count > 0` is the obvious
form; check it against a rebalance that legitimately fills nothing because the selection equals the
current book, which must **not** reset the clock either — that is arguably the same bug.

Test: drive a session whose orders are all refused and assert `sessions_held` does not reset and
`last_rebalance_on` does not advance.

## 2. P2-5 — risk marks to market, sizing still measures cost

`d6f421e3` marked the risk baseline to market and left `deployable = portfolio.ledger_funding()` at
`:763`, forty lines above. On a drawn-down book that over-allocates and silently drops a selected
name — measured: `TMPV` absent, 9.87% cash against a declared 5% buffer.

Repair: size from the same marked opening equity the governor is seeded with. Compute it once,
above both call sites, and pass it to both. Two call sites deriving the same quantity independently
is what produced this.

Test: a drawn-down book must allocate every selected name and hold the declared buffer.

## 3. P2-6 — the halt never reaches the artifacts

Exit code and console report it; the markdown still prints `Reconciliation Status: PASS` with no
mention of a halt, and `live_paper_status.json` still says `COMPLETED`.

Repair: carry `res["risk"]` into the markdown header and the status file. Round three's P2-1 also
applies — a session refused at the exit-8 gate writes no status update at all, so the dashboard
serves the last completed session indefinitely. Fix both together or the dashboard stays wrong.

## 4. P2-7 — my detector is worthless, for the third time in two rounds

`test_the_governor_is_seeded_from_marked_equity_not_a_cost_figure` asserts
`"ledger_funding" not in ast.unparse(...)`. At `46c7bb67` the defect was written through a local, so
`ast.unparse` returns `'opening_equity'` and the check passes against the very commit it names.
Four of five mutants survive, including a verbatim reintroduction of P1-1 and
`initial_equity=Decimal('0.00')`, which disables the daily rule outright.

Repair: stop asserting on source text. Test the **behaviour** — construct the governor the way the
runner does and assert that a pure multi-session decline does not trip the daily rule while a
genuine intraday fall does. If a source-level check is still wanted, resolve the local rather than
grepping the rendered expression.

**This is the third near-worthless test from the same author in two rounds, all the same failure
mode: a substring check standing in for a semantic one.** Any replacement must be mutation-tested
before it is claimed to work — revert the repair, watch the test fail, restore it.

## Also recorded, lower priority

- P3-3: the unpriced-carried-name fallback biases the drawdown toward **blindness**, not a spurious
  halt — a 9.48% true drawdown reports as 8.54%. The error cancels in the numerator and survives in
  the denominator.
- P2-1: an unreachable quote falls back to a hardcoded Rs 1000.00 labelled and logged as a real
  exchange price. This can put a fabricated price into today's record.
- Round four's `NOT PROBED`: the real NIFTY500 realtime path has never been run, and a totally
  failed bar refresh passes the staleness gate at exactly 4 days.

## After the repairs

Round five, against the repairs. Four rounds have each found defects created by the previous round's
repairs — 8, then 2, then 3, then 3. Assume a fifth.
