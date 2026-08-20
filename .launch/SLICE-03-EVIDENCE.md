# Slice 03 Evidence — Executable Point-in-Time Labels

STATUS: CANDIDATE - Red Team PASS; independent clean-state verification pending
DATE: 2026-08-20

## Outcome

Slice 3 builds the accepted six-feature ridge input family from immutable daily acquisitions and
creates close-decision, first-later-open to following-open labels after an immutable round-trip
cost quote. Derived feature and label datasets have deterministic content identities and can be
committed through the Slice 2 evidence store. Chronological folds purge overlapping outcomes and
embargo at least the two-session label horizon.

No model is fitted in this slice. Effective-dated official fee/tax selection remains in Slice 7;
the label builder consumes and binds an immutable cost quote so there is only one eventual source
of financial truth.

## Contracts proved

- Content-bound `SessionCalendarV1` and `HistoricalUniverseSnapshotV1` dependencies.
- Non-empty calendar/authority identities, reconstructable HTTPS provenance, strict effective
  ranges, and duplicate-free universe membership.
- Governed input requires complete accepted acquisition, matching calendar, corporate-action
  authority, effective historical-universe authority, and eligible instrument membership.
- Date-only authority published on the decision date fails closed because intraday availability is
  ambiguous.
- The v1 feature map is closed to return-1/5/10, Wilder RSI-14, SMA-20 distance, and Wilder ATR-14.
- Feature math uses Decimal with explicit precision/half-even rounding; canonical Decimal text is
  independent of process context.
- Every feature row identifies the exact offending source record when `available_at` exceeds its
  close-time decision.
- Entry is the first eligible next-session open; exit is the following eligible open. Missing
  internal opens and missing/duplicate/mismatched cost quotes fail closed.
- A `COMPLETE` acquisition must contain every content-bound calendar session in its requested
  range, and every supplied cost quote must be consumed exactly once.
- Gross and net returns are stored as canonical decimal strings. `UP` is permitted only for stored
  `net_return > 0`; zero and negative are `DOWN`.
- Cost amounts, rule IDs, rule-set hash, fill chronology, prices, quantity, and execution-contract
  version are bound by the cost-quote hash.
- Feature and label dataset identities cover source manifest, authorities, schemas, all rows, row
  order, and consumed cost-quote hashes.
- Fold evidence records exact train/validation hashes, class balance, purge/embargo periods, counts,
  and every removed record key.
- Instrument identity is rebound to the source acquisition before labeling; embargo membership is
  invariant to timezone representation; float money is rejected.

## Demo evidence

The synthetic journey produces exact known decimal features, labels, evidence-store round trips,
and fold membership twice. A sanitized static Upstox V3 replay envelope also runs through the real
read-only provider parser twice and pins these derived identities:

```text
feature dataset hash: 5c7639255b75e0b7c91ed40c02f1b5d29d540e740e457e3a9a7b7d80ef25480a
label dataset hash:   2e65d19c0fc28304bf8b11d86975b82d38b52e317d4fe714046c44e6a5180ae2
```

The replay file is a sanitized test fixture, not live-provider evidence and not a claim about
historical market values.

## Local verification before handoff

| Gate | Current evidence |
|---|---|
| Focused Slice 3 suite | PASS - 41 tests |
| Slice 3 package coverage | PASS — 87% |
| Strict Mypy | PASS — 75 source files |
| Ruff lint | PASS |
| Code Craft | PASS — 10 Slice 3 source files |
| Test Craft | PASS — 5 Slice 3 test/support files |
| Mutation checks | PASS — three dangerous mutations killed and restored |
| Repository gate | PASS - 208 tests, 88.58% coverage (4,862 statements / 555 missed) |
| Ruff format | PASS — 174 files in the independent clean clone |
| Dead-code scan | PASS — zero findings at >=80% confidence |
| Application secret scan | PASS — zero candidates |
| Red Team | PASS - exact repair revision `be9da7f`; no unresolved Blocker or Major |
| Independent clean-state Verifier | RECHECK PENDING - substantive gates and mutations proven; exact counts corrected after attempt 3 |

Raw failing and restored mutation outputs are in `.launch/reports/MUTATION-SLICE-03.md`.
The complete initial adversarial report and repair dispositions are in
`.launch/reports/RED-TEAM-SLICE-03.md`.

The first gate attempt exposed and then repaired a forward-slash-only secret-scan exclusion in the
new script. The second attempt proved all substantive gates but found one Test Craft parser
annotation missing. The final exact invocation passed every gate; failed attempts were retained in
the active work record rather than relabeled as success.

## Explicit limits

- The cost quote is deterministic test input; production effective-dated NSE rule lookup and
  component-to-paise reconciliation are Slice 7 acceptance work.
- The replay is offline and sanitized; missing live credentials remain a typed external boundary.
- Training, learned preprocessing, trial accounting, final holdout, and promotion begin in Slice 4
  and Slice 5.
