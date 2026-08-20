# Mutation Report — Slice 3

DATE: 2026-08-20
STATUS: PASS — all deliberate mutations were killed and the strict implementation restored

## Method

Each mutation was applied to the working implementation, only the smallest guarding test set was
run, the expected red result was captured, and the original implementation was restored with
`apply_patch`. The complete focused suite then passed 30 tests.

## Results

| Mutation | Guard test | Red result | Restored result |
|---|---|---|---|
| Disabled the explicit `available_at > decision_at` rejection | `test_post_cutoff_input_fails_with_the_offending_record` | FAIL: the required typed `ModelingError` was not raised; the defensive row invariant later raised `ValueError` | PASS |
| Changed label classification from `net_return > 0` to `>= 0` | zero-return and tiny-positive-rounded-to-zero tests | 2 FAIL: the row invariant rejected an incorrect `UP` label for stored zero | PASS |
| Shortened the two-session embargo by one session | exact purged-fold test | FAIL: seven training rows remained instead of six and the embargo evidence was empty | PASS |

## Conclusion

The tests independently guard the three highest-risk Slice 3 claims: information availability,
the zero-return `DOWN` boundary, and the minimum embargo horizon. A second row-contract invariant
also catches label-sign drift if the builder guard changes.
