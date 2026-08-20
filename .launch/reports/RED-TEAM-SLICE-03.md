# Red Team Report - Slice 3

STATUS: PASS  
DATE: 2026-08-20  
ATTACKED REVISION: `5c461e2a6818ff7adfe8bf04503f7cb43563d591`
RECHECKED REVISION: `be9da7f482b5d6fbb03037460b180169c7ee03bf`

## Initial verdict

BLOCKED. The independent Red Team reproduced five Blockers, one Major, and one Minor against the
exact clean candidate. Its clean-clone gate itself passed: 194 repository tests, 30 focused tests,
88.59% coverage, and all static, secret, dead-code, and craft scans.

## Findings and dispositions

| Severity | Finding | Repair and regression |
|---|---|---|
| Blocker | A complete acquisition could omit an internal calendar session and still build features | Exact requested-range sessions are compared with content-bound calendar sessions; the first missing date now raises `CALENDAR_SESSION_MISSING` |
| Blocker | Coherently rehashed INFY feature rows could be relabeled as TCS | Feature rows, universe authority, source dataset, provider instrument ID, and symbol now bind the supplied acquisition before quote lookup |
| Blocker | A timezone-equivalent decision instant could bypass the session embargo | Embargo membership now compares exact aware session-close instants instead of representational `.date()` values |
| Blocker | `MoneyV1(0.1, "INR")` persisted a binary-float artifact | Money and price evidence now rejects runtime values other than exact `Decimal` or canonical decimal text |
| Blocker | Empty calendar and universe authority identities counted as governed | Calendar IDs/versions and authority IDs/versions/reconstructable HTTPS sources now fail closed; corporate-action references use the same identity validation |
| Major | An extra mismatched cost quote was silently ignored and absent from output identity | The supplied and consumed quote-hash multisets must match exactly |
| Minor | The universe factory silently deduplicated members | Duplicate membership now raises instead of performing an unrecorded repair |

Each production repair began with a regression that failed on the attacked revision. The focused
suite now has 41 tests and includes the original adversarial cases.

## Repair revision evidence (`be9da7f`)

```text
repository tests: 205 passed
coverage: 88.53%
focused Slice 3 tests: 41 passed
strict mypy: 75 source files
ruff lint/format: pass
vulture: zero findings at >=80% confidence
application secret scan: zero candidates
Code Craft: 10 files clean
Test Craft: 5 files clean
```

## Verified protections from the initial attack

- Cutoff equality is accepted and post-cutoff evidence is rejected with its record.
- Same-day date-only authority fails closed; effective boundaries behave as documented.
- Duplicate/out-of-order sessions and bars fail closed.
- Missing, duplicate, price-mismatched, and chronology-mismatched quotes fail closed.
- Negative and non-finite costs fail.
- Future opens change labels but not earlier feature values.
- Stored zero net return is `DOWN`.
- Candidate, dataset hash, and row-order tampering fail closed.
- Empty/small partitions fail and one-class balances are explicitly recorded.
- Equivalent calendar instants hash identically.
- Sanitized provider replay reproduces pinned hashes.

## Not probed in Slice 3

- Official effective-dated NSE fee/tax and paise reconciliation, owned by Slice 7.
- Training, learned preprocessing, final holdout, and promotion, owned by Slices 4-5.
- Live Upstox history; the test uses a sanitized recorded replay.
- Physical memory exhaustion from adversarial million-digit Decimals.
- Corporate-action adjustment correctness; no content-bearing adjustment authority exists yet.

## Independent post-repair recheck

PASS - no unresolved Blocker or Major. The recheck used an isolated clean clone and left the shared
root untouched and the clone clean.

```text
focused repair selection: 13 passed
repository tests: 205 passed
coverage: 88.53%
focused Slice 3 tests: 41 passed
strict mypy: 75 source files
ruff lint and format: pass
vulture and application secret scans: zero findings
Code Craft and Test Craft: pass
exact gate result: Slice 3 gates passed
```

The counts above are revision-scoped to the repair recheck. Subsequent daily-pipeline and drive
isolation commits changed the repository-wide baseline. The later certification baseline is 208
tests at 88.58% coverage (4,862 statements / 555 missed) and 174 Ruff-formatted files; the repaired
Slice 3 contracts and 41 focused tests are unchanged.

Observed repair outcomes:

- Missing internal session: `CALENDAR_SESSION_MISSING`, with the exact missing session key.
- Rehashed instrument/quote swap: `DATASET_INTEGRITY_INVALID`, with the tampered row key.
- Timezone-equivalent embargo attack: both representations retained train 6, embargoed 1,
  purged 1.
- Float money: `TypeError` requiring Decimal or string.
- Empty calendar and universe identities: explicit `ValueError` outcomes.
- Unused quote: `COST_QUOTE_MISMATCH`.
- Duplicate universe member: explicit uniqueness `ValueError`.
- Empty, HTTP, credential-bearing, and inverted-range corporate authorities:
  `CORPORATE_ACTION_AUTHORITY_INVALID`.
