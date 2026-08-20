# Raw Red Team Report - Slice 01

REVIEWER ROLE: Adversarial QA  
DATE: 2026-08-20  
SCOPE: Governed Upstox V3 daily acquisition  
WORKSPACE: `D:\quant_system`

## Initial verdict: BLOCKED

The first review reproduced four acceptance failures when otherwise non-null authority references
were supplied:

1. A request for 2025-01-02 through 2025-01-03 accepted provider rows dated 2025-01-01 and
   2025-01-04 as `ACCEPTED`, `COMPLETE`, with no finding.
2. An acquisition timestamped 2025-01-01 accepted a row whose `available_at` was 2025-01-02,
   despite that information not being available at acquisition.
3. Endpoint-only rows for a wider range were inferred to be complete without checking internal
   exchange sessions.
4. Two daily rows with different event timestamps but the same exchange date were accepted because
   uniqueness used event time rather than daily exchange date.

Four corresponding regression tests were then observed failing before production changes:

```text
collected 27 items
tests\test_upstox_v3_acquisition.py .....FFFF..................

FAILED test_two_daily_rows_for_one_exchange_date_are_rejected_as_duplicates
FAILED test_rows_outside_requested_range_are_rejected
FAILED test_row_not_available_at_acquisition_is_rejected
FAILED test_internal_session_completeness_is_not_inferred_from_endpoints
4 failed, 23 passed
```

## Bounded recheck verdict: PASS

No unresolved Blocker or Major findings remained in the bounded recheck.

- Out-of-request-range rows: CLOSED - rejected with `OUT_OF_REQUEST_RANGE`.
- Future/unavailable rows: CLOSED - rejected with `NOT_AVAILABLE_AT_ACQUISITION`.
- Duplicate daily exchange dates: CLOSED - rejected with `DUPLICATE_KEY`, even when timestamps differ.
- Explicit calendar completeness: CLOSED - missing expected sessions remain partial; unexpected
  dates are rejected; exact expected-session coverage is accepted.
- Read-only broker authority: CONFIRMED - transport exposes GET only and the client has no place,
  modify, or cancel order methods.

Reviewer command evidence:

```text
Focused Upstox suite: 34 passed.
Seven repaired-boundary tests: 7 passed.
Final verdict: PASS.
```

Not probed: credentialed live provider behavior, multi-million-row scale, real TLS/network
interruption, and execution modules outside Slice 1.

This is a local raw report captured before the immutable evidence store exists. It is revisioned
once the repository baseline is created but is not a content-addressed Slice 2 evidence object.

