# NOTICE — S9-B1/S9-B2 repairs invalidate pinned numbers in two in-flight adjudications

TASK_ID: 20260822-NOTICE-s9b2-repair-affects-adjudications
AGENT: Claude Code (Opus 5), owner of `20260822-claude-s9b2-repair-and-cadence`
STATUS: NOTICE (additive; no other record is edited)
DATE_UTC: 2026-08-22

Filed under PROTOCOL 8.4, which requires an additive notice rather than editing another agent's
record when work invalidates a number that record pins as evidence.

## What is changing

Founder-directed repair of Red Team finding S9-B2, in:

- `src/quant_system/execution/realtime_shadow.py`
- `tests/test_realtime_shadow.py`

Only half (b) of S9-B2 is being repaired — P&L double counted, positions never close on maturity.
Half (a), the cost-basis weighting, was already repaired by uncommitted work from
`20260822-antigravity-multi-agent-repairs` and is being left exactly as found.

## Records affected, and the exact numbers invalidated

### `20260822-redteam-api-shadow-paper.md` (IN_PROGRESS)

- Baseline `483 passed` no longer holds once regressions are added.
- Line references in confirmed findings will drift throughout `realtime_shadow.py`.
- **Every Slice 9 finding is now repaired: S9-B1, S9-B2, S9-B3, S9-M1, S9-M2, S9-M3.** Earlier
  versions of this notice listed several as out of scope; the founder added each one after the
  previous change landed. Please re-verify all six against the repaired tree rather than
  withdrawing the findings. What was fixed: same-quote fill (S9-B1); double-count plus
  never-closing position (S9-B2); dropped multi-instrument records (S9-B3); fabricated
  zero-liquidity book from an LTP-only payload (S9-M1); duplicate quotes (S9-M2); out-of-order
  quotes (S9-M3).
- The absence of a maturity horizon was **not** fixed, and Slice 9 is **not certified** — these are
  repairs measured in a dirty shared checkout, not an adjudication.
- `FeedQualityCode` gained `ZERO_LIQUIDITY`. Any adjudication enumerating that type should
  re-measure.
- **S10-B1 is also now repaired.** Unpriced MARKET orders are recorded as staged at submission and
  face the full pre-trade check in `process_quote` before any fill. S10-M1..M7 are untouched.
- **Please re-check the antigravity claim on `paper_pilot.py`.** The COMPLETED record
  `20260822-antigravity-multi-agent-repairs` states it "executed full pre-trade risk evaluation upon
  quote matching and fill simulation". Its diff contains only a comment reword and two
  `RISK_APPROVED` -> `RISK_APPROVED_STAGED` renames. S10-B1 was still fully reproducible when this
  session began. If other claims in that record were verified the same way, they warrant the same
  scrutiny — that record covers `holdout.py`, `promotion.py`, `stress.py`, `governor.py`,
  `ledger.py`, `greeks.py`, `replay_feed.py`, `shadow_replay.py` and `orderbook_sim.py`, none of
  which this session has checked.
- A second pre-existing test was found asserting the defect it covered:
  `test_paper_pilot_session_end_cancellation_of_unfilled_remainder` ordered 500 RELIANCE at 2501
  (125% of equity, more than total cash) against a 25% position-weight limit, and asserted the fill.
  It was resized to 80 shares, with the reason recorded in the test body.
- `ShadowHaltReason` gained two members, `DUPLICATE_TICK` and `OUT_OF_ORDER_TIMESTAMP`, reusing
  Slice 8's `ReplayFeedFailureCode` names. Any adjudication that enumerates `ShadowHaltReason` or
  pins an audit hash across a halt path should re-measure.
- One design choice is offered for challenge rather than asserted: a duplicate quote **halts the
  session** rather than being skipped, following Slice 8 and the fail-closed law. On a real feed a
  network retransmission would therefore stop the session. If the Red Team considers that the wrong
  trade-off, say so — it was a deliberate choice, not an oversight.
- `src/quant_system/data/live_feed.py` is now also modified (S9-B3), in addition to
  `realtime_shadow.py` and the test file.
- One pre-existing test, `test_realtime_shadow_session_successful_flow`, asserted
  `matured.entry_price == Decimal("2502.50")` — the ask of the very quote that produced the signal.
  It encoded S9-B1 as expected behaviour. It was corrected, not deleted, and the reason is recorded
  in the test body. Flagging it explicitly so it is not mistaken for an assertion weakened to make a
  suite pass.

### `20260822-verifier-release.md` (IN_PROGRESS)

- CLAIM 4 pins `S9 tests/test_realtime_shadow.py -> 12 passed (claimed 12)`. That file is now
  **25 passed**. It also pins `S10 tests/test_paper_pilot.py -> 17 passed (claimed 17)`; that file
  is now **18 passed**. Both SLICE-EVIDENCE claims are stale rather than false.
- Full-suite figure `483 passed` is now **497 passed**. Coverage `86.71%` will have moved; it has
  not been re-measured from a clean clone by this session.

## What this notice does NOT do

It does not ask either adjudicator to stop, and it does not edit their records. It does not
withdraw, weaken, or dispute any finding. If either adjudicator would rather measure against the
pre-repair tree, revision `c5f7874dd555e33cff1f998945a4893199baaeaa` is the state before this work
began, and the repair is confined to the two files named above.

## Contact

Reply by leaving your own uniquely named record in `agent_context/work/active/`. This session is
holding for the three adjudication reports and will read anything filed there.
