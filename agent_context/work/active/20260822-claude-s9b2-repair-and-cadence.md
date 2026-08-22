# Repair S9-B2, then governed-model decision cadence

TASK_ID: 20260822-claude-s9b2-repair-and-cadence
AGENT: Claude Code (Opus 5)
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-22
STARTING_REVISION: c5f7874dd555e33cff1f998945a4893199baaeaa (main, install root)
WORKTREE_OR_BRANCH: D:\quant_system on main (shared checkout — see Isolation note)

## Objective

Founder-directed, in this order:

1. Repair Red Team finding S9-B2 (P&L double counted; positions never close on maturity).
2. Then implement the session-close decision cadence for governed models, per
   `agent_context/decisions/20260822-point-in-time-bars-at-execution.md`.

## Non-goals

- Not repairing S9-B3, S9-M1/M2/M3 in this task. (S9-B1 was added to scope by the founder after
  the cadence change landed; it is now repaired — see step 3.)
- Not implementing the model adapter itself.
- Not adding a maturity horizon. Maturity currently fires on the next same-symbol quote; that is a
  cadence question, addressed in step 2, not in the S9-B2 repair.
- Not touching, reverting, staging, or committing the uncommitted repairs already in the working
  tree. They belong to `20260822-antigravity-multi-agent-repairs` (COMPLETED).

## Owned paths

- `agent_context/work/active/20260822-claude-s9b2-repair-and-cadence.md` (this file)
- `agent_context/work/active/20260822-NOTICE-s9b2-repair-affects-adjudications.md`
- `src/quant_system/execution/realtime_shadow.py`
- `src/quant_system/data/live_feed.py` (added at step 4, S9-B3; unclaimed by any other record)
- `src/quant_system/execution/paper_pilot.py` (added at step 7, S10-B1)
- `tests/test_realtime_shadow.py`
- `tests/test_paper_pilot.py` (added at step 7)

## Isolation note

Shared checkout, not a worktree, and the reason is deliberate: half of S9-B2 (cost-basis weighting
in `_record_hypothetical_fill`) is already repaired in the working tree as uncommitted work by a
COMPLETED agent. A worktree branched from `c5f7874` would not contain that repair, so the fix would
be built against a tree that does not match reality and would duplicate or revert it on merge.

No active record claims write access to `src/quant_system/execution/**`. The two Red Team records
explicitly claim only their own record and their own report ("Nothing else in the install root will
be written"). Ownership is therefore clear; visibility is the risk, and it is handled by the notice
record below.

## Pre-existing state, verified before editing

S9-B2 has two halves. Half (a) is already fixed; only half (b) remains.

| Half | Status | Evidence |
|---|---|---|
| (a) `average_price = price` overwrote cost basis instead of weighting | **already repaired**, uncommitted | `git diff src/quant_system/execution/realtime_shadow.py` shows weighted-average, partial-reduce, and flip branches added at `_record_hypothetical_fill` |
| (b) P&L double counted; positions never close on maturity | **open** | analysis below |

Half (b), read at `realtime_shadow.py:451-499`:

`_check_matured_outcomes` computes a full round-trip P&L (entry price to exit price, minus both
legs' friction), appends a `ShadowMaturedOutcome`, and pops the entry from `_open_entries`. It never
closes the position. So the same single market move is counted twice:

- once as unrealised, because `_positions` still holds the open position and `current_equity`
  (`:243-252`) marks it to market;
- again as realised, in `matured_outcomes[].net_pnl`.

Red Team probe E7 observed exactly this: `current_equity - initial = 135.00` (unrealised) while
`matured_outcomes` net P&L booked 75.28 on top, from one market event.

## Repair design

On maturity, close the position through the same fill path rather than leaving it open:

1. Apply the offsetting hypothetical fill at `exit_price` via `_record_hypothetical_fill`.
2. Deduct `friction_fee` from cash.

Arithmetic, for a BUY of quantity q at entry `p_e` maturing at exit `p_x`:

    entry:     cash -= p_e * q            position +q @ p_e
    maturity:  cash += p_x * q            position -> 0
    then:      cash -= friction_fee
    net cash delta = (p_x - p_e) * q - friction_fee = net_pnl

Equity then equals `initial + net_pnl`, counted exactly once, and the position genuinely closes.

Rejected alternative: make matured outcomes attribution-only and never let them touch equity.
Rejected because the finding is explicitly "positions never close on maturity" — leaving positions
open lets a shadow session accumulate unbounded exposure, and the risk governor reads
`current_equity` and `positions` on every decision.

## Plan

1. Create this record. (done)
2. Leave the notice record for the two in-flight adjudications. (done — see below)
3. Write failing-first regressions in `tests/test_realtime_shadow.py`; observe them fail.
4. Apply the repair; observe them pass.
5. Full suite + ruff + strict mypy.
6. Then step 2 of the objective: session-close cadence.

## Notice to in-flight adjudications

Left at `agent_context/work/active/20260822-NOTICE-s9b2-repair-affects-adjudications.md`, per
PROTOCOL 8.4. It names the pinned numbers this work invalidates. Neither adjudicator's record is
edited.

## Commands and outcomes

| Command | Outcome |
|---|---|
| `git rev-parse HEAD` | `c5f7874dd555e33cff1f998945a4893199baaeaa` |
| `git diff -- src/quant_system/execution/realtime_shadow.py` | half (a) already repaired, uncommitted, left untouched |
| `grep -c "def test_" tests/test_realtime_shadow.py` | 12 before this task, 17 after |

### Failing-first evidence (S9-B2)

Regressions were written and observed RED before the source was touched. Raw:

    AssertionError: equity moved 24995.00 but matured outcomes recorded 933.09;
    the same market move is being counted twice, or the position never closed
    AssertionError: short entry: equity moved 15995.00 but outcomes recorded 935.35
    AssertionError: equity must reflect gross P&L net of the friction recorded on the outcome
    3 failed, 12 deselected

Two harness defects in my own tests were found and corrected during this stage, both mine and
neither a product defect:

- the helper omitted `feed.symbol_map[...]`, so the symbol parsed as the ISIN `INE002A01018` and
  the strategy never matched — 0 proposals;
- the short-side test omitted `allow_naked_short=True`, so the governor **correctly** refused the
  entry with `NAKED_SHORT_FORBIDDEN`. The code was right; the test premise was wrong.

### Gate after both changes

| Gate | Result |
|---|---|
| `pytest tests/ -q` | **497 passed**, 1 warning (483 baseline + 14 added by this task) |
| `pytest tests/test_realtime_shadow.py -q` | 25 passed (12 before this task) |
| `pytest tests/test_paper_pilot.py -q` | 18 passed (17 before this task) |

Added regressions by finding: 3 S9-B2, 2 cadence, 1 S9-B1, 2 S9-B3, 3 S9-M2/M3, 2 S9-M1, 1 S10-B1.
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 287 files already formatted |
| `mypy src` | Success: no issues found in 109 source files |
| `scripts/audit-agent-claims.ps1` | RESULT: PASS, exit 0 |
| `scripts/audit-disk-layout.ps1` | RESULT: PASS, exit 0 |

Only the two files I own were formatted, by explicit path. No repository-wide formatter was run.

## Step 2 — decision cadence (COMPLETE)

Added `DecisionCadence` (`PER_QUOTE`, `ONCE_PER_SESSION`) and
`RealtimeShadowConfig.decision_cadence`, defaulting to `PER_QUOTE` so existing quote-driven
behaviour is bit-for-bit unchanged — all 12 pre-existing S9 tests pass untouched. Under
`ONCE_PER_SESSION` the strategy is consulted at most once per symbol per session; later quotes are
still processed so maturity, freshness, and halt logic keep working.

Scope honesty: this is the *mechanism* the governed model will consume. There is no governed model
in the execution path yet — that is the adapter, still blocked on the `modeling/features.py` claim.
The knob has no production consumer until then, and is dormant at its default.

## Blockers and conflicts

1. Two Red Teams and one Verifier are adjudicating this package right now. Their findings cite exact
   line numbers in `realtime_shadow.py`, which this repair will drift. Founder directed the repair
   to proceed with that understood. Notice record left.
2. `tests/test_realtime_shadow.py` count of 12 is pinned as evidence by the Verifier record.

## Step 3 — S9-B1, decision-bar execution (COMPLETE)

Founder-directed after step 2. The runner booked the hypothetical fill at `domain_quote.ask` of the
**same quote that produced the signal** — zero latency, no next-quote requirement. Slice 8's
contract calls same-quote fills structurally impossible; Slice 9 did only that.

Repair: an approved decision is queued to `_pending_fills[symbol]` instead of filling. A new
`_execute_pending_fills` runs as step 5b of `process_live_quote` — after maturity, before the
strategy is consulted. That ordering gives two guarantees at once: an entry opened on this quote
cannot also mature on it, and a decision taken later in this same quote cannot fill on it.

Failing-first evidence, before the source was touched:

    AssertionError: equity moved on the decision quote: the decision filled against its own quote
    assert Decimal('999995.00') == Decimal('1000000.00')

### An existing test asserted the defect

`test_realtime_shadow_session_successful_flow` contained:

    assert matured.entry_price == Decimal("2502.50")  # Bought at ask

2502.50 is the ask of quote 2 — the quote that produced the BUY signal. The test was passing, and
it encoded S9-B1 as expected behaviour. Repairing the defect necessarily broke it.

It was corrected rather than deleted: a fourth quote was added so the test still demonstrates
maturity (its stated purpose), and the expectation moved to 2520.50, the ask of quote 3, the first
quote later than the decision. `quotes_processed` 3 -> 4 and `proposals_approved` 2 -> 3 follow from
the added quote. The reason is written into the test body so the next reader does not mistake it for
an assertion loosened to make a suite pass.

This is the one case in this task where an existing assertion was changed. Every other change is
additive.

## Step 4 — S9-B3, dropped quotes (COMPLETE)

Founder-directed after step 3. `read_quote()` parsed every instrument in a feed message and then
returned `records[0]`, discarding the rest with no error, no counter and no log. A subscribed symbol
could go permanently unseen while the feed reported healthy.

Repair: `UpstoxLiveFeed` gained `_pending_records: deque[LiveQuoteRecord]`. `read_quote()` now hits
the transport only when the buffer is empty, queues **every** parsed record, and pops one per call.

The freshness and clock-drift checks were deliberately left on the popped record rather than on
`records[0]`, so a record reachable only from the buffer is still budget-checked. Drift is now
measured against `quote_record.received_at` instead of a fresh `clock()` read — identical for a
just-parsed record, and correct for a buffered one, which must not be able to age its own way past
a budget by sitting in the queue.

Failing-first evidence: the first regression failed with `LiveFeedTimeoutError` on the second
`read_quote()` — one record delivered from a three-instrument message, then the transport was empty.

The second regression was deliberately strengthened after it first passed. As written it staled all
three instruments, so the first record raised before any buffered record was reached — it proved
nothing about buffering. It now makes instrument 1 fresh and instrument 2 stale by 90s, so the
failure can only come from a record that exists because it was buffered. That version fails against
the obvious naive fix (early-returning a buffered record without checks).

## Step 5 — S9-M2 and S9-M3, live quote sequence integrity (COMPLETE)

Founder-directed after step 4. Slice 8's `ReplayQuoteFeed` enforces time order and duplicate
detection; Slice 9 enforced neither, so one market event could be booked repeatedly (S9-M2) and a
rewound event clock was accepted inside the freshness window (S9-M3), fabricating outcomes.

Repair: a sequence-integrity guard as step 3b of `process_live_quote`, placed **before**
`_check_matured_outcomes` so a bad quote cannot drive maturity either.

- Duplicate: signature `(symbol, event_at, bid, ask)` already seen -> halt `DUPLICATE_TICK`.
- Out of order: `event_at` earlier than the last event for **that symbol** -> halt
  `OUT_OF_ORDER_TIMESTAMP`.

Both new members of `ShadowHaltReason` deliberately reuse Slice 8's `ReplayFeedFailureCode` names,
so the recorded and live surfaces describe the same defect with the same word in the audit.

### Two design choices worth review

1. **Ordering is per symbol, not global.** Slice 8 checks order globally, which is right for a
   single recorded stream. A live multi-instrument message legitimately carries several instruments
   stamped with the same event time, and instruments interleave. A global check would halt on
   normal traffic. `test_same_timestamp_across_different_symbols_is_not_out_of_order` pins this and
   was written to fail if the guard over-fires.
2. **A duplicate halts the whole session** rather than being skipped. This follows Slice 8 and the
   fail-closed product law. It is strict: a network-level retransmission on a real feed would stop
   the session. Flagged for founder review — the alternative (skip the duplicate, count it, carry
   on) is defensible but weakens a fail-closed guarantee, so it was not chosen unilaterally.

### Known cost

`_seen_quote_signatures` grows for the life of a clean session. Bounded by one trading day and
mirroring Slice 8's `_seen_signatures`, so it was left unbounded rather than inventing an eviction
policy — an evicted signature would silently reopen the duplicate hole, which is worse than the
memory.

## Step 6 — S9-M1, fabricated zero-liquidity book (COMPLETE)

Founder-directed after step 5, and the last open Slice 9 finding.

`_parse_feed_entry` defaulted both sides to `0` when a payload carried no depth
(`market_data.get("bid", 0)`, `live_feed.py:335`). Because the crossed-quote guard is `ask < bid`,
and `0 < 0` is false, it could never catch this: an LTP-only payload was published as a valid
two-sided quote with bid=0, ask=0, mid=0.

Repaired in both layers:

1. **Parser** — `bid <= 0 or ask <= 0` raises `LiveFeedQualityError` with a new
   `FeedQualityCode.ZERO_LIQUIDITY`, reusing Slice 8's `ReplayFeedFailureCode.ZERO_LIQUIDITY`
   spelling. Placed **before** the crossed guard so a missing side is named accurately rather than
   reported as a crossed book.
2. **Runner** — step 3 quality validation now refuses a zero or negative side. Defence in depth: a
   `LiveQuoteRecord` can be constructed without passing the parser, and the runner is the layer
   that owns `ShadowHaltReason`.

The runner half is the half that mattered for operators. The failing test printed the old behaviour
verbatim:

    rejection_reason='MISSING_PRICE_FOR_RISK_VALUATION'

A data-quality fault was recorded as a risk rejection, which sends an operator debugging the risk
governor for a feed problem. It now halts `QUALITY_VIOLATION` with `proposals_rejected == 0`.

The runner's quality check was also split into two branches — absent book, then crossed book — so
the two faults no longer share one message. The previous single message read "Crossed or negative
quote" for both.

## Step 7 — S10-B1, pre-trade risk bypass in the paper pilot (COMPLETE)

Founder-directed after step 6. First finding outside Slice 9.

### The antigravity repair of this file was cosmetic

`20260822-antigravity-multi-agent-repairs` (COMPLETED) claims for `paper_pilot.py`:

> Staged unpriced market proposals under `RISK_APPROVED_STAGED` and executed full pre-trade risk
> evaluation upon quote matching and fill simulation.

`git diff -- src/quant_system/execution/paper_pilot.py` contains exactly three changes: one comment
reworded, and two `reason="RISK_APPROVED"` strings renamed to `"RISK_APPROVED_STAGED"`. **There is
no fill-time risk evaluation anywhere in that diff.** The claim is not supported by its own change.
S10-B1 was fully open when this step began, and the probe reproduced it unchanged: 9000 shares
filled at 100.11.

Recording this because that record is filed as COMPLETED evidence, and a reader trusting its summary
would believe a Blocker was closed when it was not. The rename itself is harmless and was kept.

### The repair

`evaluate_order` was never called when a symbol had no cached price and the order was MARKET, so
order value and position weight — which need a price — were **skipped rather than deferred**.

Now: such orders are recorded in `_staged_order_ids` at submission, and `process_quote` runs the
full pre-trade check against the arriving book *before* `simulate_fill`. Rejection transitions the
order to REJECTED with the governor's own reason and logs `RISK_REJECTED` with
`deferred_from_submission`.

If the book cannot value the order — either side missing, or crossed — the order is left staged and
**not filled**. Filling there is precisely the unvalued execution this guard exists to stop.

### A second existing test asserted the defect

`test_paper_pilot_session_end_cancellation_of_unfilled_remainder` ordered 500 RELIANCE at 2501 =
**1,250,500 against 1,000,000 equity** — 125% of the portfolio, more than the account's entire cash,
against `max_position_weight` 0.25. It then asserted a 200-share fill, itself 50% concentration. The
test passed only because the bypass existed.

Resized to 80 shares (200,080 = 20.0% of equity) with ask depth 30, so it still exercises exactly
what it was written for — partial fill, then cancellation of the unfilled remainder at session end.
Reason recorded in the test body.

That is the second pre-existing test in this task found asserting the defect it covered. Both are
named here rather than quietly amended.

## Stop point

Both directed steps are complete and green. Working tree is dirty and **nothing is committed** —
this session has not staged or committed anything, and the uncommitted repairs belonging to
`20260822-antigravity-multi-agent-repairs` are still present and untouched alongside my changes.

Files changed by me:

- `src/quant_system/execution/realtime_shadow.py` (maturity closes position; `DecisionCadence`)
- `tests/test_realtime_shadow.py` (+5 regressions, 12 -> 17)
- this record, the notice record, the adapter scope record, and the decision record

## What is NOT fixed

**Every Slice 9 finding in the Red Team record is now closed**: S9-B1, S9-B2, S9-B3, S9-M1, S9-M2,
S9-M3.

Explicitly NOT closed, and not claimed to be:

- **No maturity horizon.** An entry still matures on the first same-symbol quote after its fill, so
  minimum-holding behaviour is unmodelled. This is the cadence question deferred at step 2 and
  belongs to the adapter slice.
- **Slice 9 is not certified.** These are repairs with regressions, measured in a dirty shared
  checkout on top of another agent's uncommitted work. Certification requires an independent Red
  Team recheck and a clean-clone Verifier, neither of which has run against this tree. Nothing here
  may be cited as a passing gate.

Outside Slice 9, only **S10-B1** is closed (step 7).

Still open from the API/shadow/paper Red Team record: S8-B1, S8-B2, S8-B3, S8-M1..M4,
S10-M1..M7, and the Slice 6 items listed there as under investigation (hardcoded endpoint
responses, supervisor idempotency key not bound to endpoint or payload, `testserver`/`testclient`
accepted in the production Host allowlist).

Still open from the money-paths Red Team record, entirely untouched: L-1, L-2, H-1, H-2, P-1, P-2,
S-1, R-1..R-4, G-1..G-6, N-1, N-2, X-1.

Also untouched: every finding in the Verifier record, including CLAIM 3 (7 secret-scan candidates
fail the documented gate), CLAIM 5 (the shipped artifact does not contain the modules it is
certified for, and the build is not reproducible), and the four open program-level Majors.

## Next safe action

Await the three adjudication reports, then consolidate. Do not commit these changes until the
adjudicators have finished or explicitly released the tree — committing now would move the
revision under three runs that pinned `c5f7874`.
