# Slice 01 Evidence - Governed Upstox V3 Acquisition

STATUS: Red Team passed; independent verification in progress  
DATE: 2026-08-20  
SCOPE: Read-only NSE cash-equity daily history. No broker order authority.

## Outcome

The slice now has a strict Upstox V3 acquisition boundary that produces either:

- point-in-time daily bars plus a deterministic provenance and quality manifest; or
- a typed failure with retryability and recovery behavior.

No access token was configured during verification. The required real-environment five-year
INFY request therefore proved the typed unavailable path:

```text
HistoricalAcquisitionFailure
PROVIDER_UNAUTHORIZED
False
Configure a valid UPSTOX_ACCESS_TOKEN and retry.
```

The client made no transport call in this condition. A credentialed real-data acceptance run
remains required before claiming provider-live readiness.

## Provider contract

- Official endpoint: `GET /v3/historical-candle/:instrument_key/:unit/:interval/:to_date/:from_date`
- Daily request: `unit=days`, `interval=1`
- Official documentation:
  https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/
- Official error catalogue: https://upstox.com/developer/api-documentation/error-codes/
- Official rate limits: https://upstox.com/developer/api-documentation/rate-limiting/

## Verification

| Gate | Result | Evidence |
|---|---|---|
| Focused behavior suite | PASS | 34 tests across the two Upstox files |
| Repository suite | PASS | 105 tests |
| Repository coverage | PASS | 88.94%, required minimum 80% |
| Ruff | PASS | All files |
| Mypy strict | PASS | 57 source files |
| Code Craft, slice files | PASS | 6 source files, zero findings |
| Test Craft, slice files | PASS | 2 test files, zero findings |
| Mutation proof | PASS | Weakening NSE-only validation to admit BSE caused the boundary test to fail; strict rule restored and test passed |
| Live credentialed provider pull | NOT TESTED | `UPSTOX_ACCESS_TOKEN` is not configured |
| Broker-write authority | PASS | Narrow GET-only transport; no place, modify, or cancel order methods |

The focused total is five compatibility tests plus twenty-nine V3 acquisition test cases.

## Red Team

The first review reproduced four Major acceptance defects: out-of-request rows, rows not yet
available at acquisition, duplicate daily exchange dates with differing timestamps, and internal
session gaps could reach governed eligibility. Four failing regression tests were observed before
production changes. The implementation now rejects or marks partial as appropriate and requires
an explicit expected-session set from a versioned calendar for governed eligibility.

A fresh bounded recheck closed all four findings, confirmed the GET-only/no-order boundary, and
returned `PASS` with no unresolved Blocker or Major.

## Covered failure behavior

- missing or rejected authentication;
- rate limiting with bounded `Retry-After` and capped attempts;
- timeout, connection failure mapping, provider 5xx, and oversized response;
- malformed HTML/JSON, envelope drift, and candle schema drift;
- empty and partial ranges;
- duplicate keys and invalid OHLC, volume, or timestamp values;
- reverse provider order as an explicit recorded repair;
- missing calendar, corporate-action, or historical-universe authority;
- non-NSE instruments and requests beyond the provider ten-year retrieval limit.

## Remaining evidence before Slice 1 closes

- Independent clean-state Verifier verdict.
- Credentialed five-year request is deferred until a token is supplied; the typed failure path
  satisfies the slice demo boundary but does not prove live provider acceptance.

## Repository debt observed outside this slice

- Code Craft: 53 pre-existing findings across 18 files.
- Test Craft: 10 pre-existing loop-in-test findings across 5 files.
- No Git repository or CI evidence exists yet.
