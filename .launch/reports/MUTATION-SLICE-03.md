# Mutation Report - Slice 3

DATE: 2026-08-20  
STATUS: PASS - three dangerous mutations killed; exact implementation restored  
EVIDENCE REVISION: `7708fd797b3416326ea74ffa0de99f62aeb383f7`

## Method

The evidence revision was checked out detached in isolated clone
`tmp/mutation-slice3-7708fd7`, followed by a frozen 47-package development install. Each mutation
was applied alone with `apply_patch`, its smallest guarding test was run to a real red exit, the
exact production line was restored with `apply_patch`, and the same test was rerun green. The
final clone had an empty `git diff` and `git status --porcelain=v1`.

## Raw run 1 - point-in-time availability

Mutation:

```diff
-        if record.available_at > session.close_at:
+        if False and record.available_at > session.close_at:
```

Command and red output:

```text
> pytest -q tests/test_modeling_features.py::test_post_cutoff_input_fails_with_the_offending_record
============================= test session starts =============================
collected 1 item
tests\test_modeling_features.py F                                        [100%]
FAILED tests/test_modeling_features.py::test_post_cutoff_input_fails_with_the_offending_record
E ValueError: feature information cutoff cannot follow decision time
============================== 1 failed in 0.24s ==============================
EXIT_CODE=1
```

Restored output:

```text
> pytest -q tests/test_modeling_features.py::test_post_cutoff_input_fails_with_the_offending_record
collected 1 item
tests\test_modeling_features.py .                                        [100%]
============================== 1 passed in 0.07s ==============================
EXIT_CODE=0
```

## Raw run 2 - stored-zero label boundary

Mutation:

```diff
-        target="UP" if Decimal(net_return_text) > 0 else "DOWN",
+        target="UP" if Decimal(net_return_text) >= 0 else "DOWN",
```

Command and red output:

```text
> pytest -q tests/test_modeling_labels.py::test_zero_net_return_is_down tests/test_modeling_labels.py::test_tiny_positive_economic_return_rounds_to_zero_and_is_down
============================= test session starts =============================
collected 2 items
tests\test_modeling_labels.py FF                                         [100%]
FAILED tests/test_modeling_labels.py::test_zero_net_return_is_down
FAILED tests/test_modeling_labels.py::test_tiny_positive_economic_return_rounds_to_zero_and_is_down
E ValueError: label target does not match net return
============================== 2 failed in 0.24s ==============================
EXIT_CODE=1
```

Restored output:

```text
> pytest -q tests/test_modeling_labels.py::test_zero_net_return_is_down tests/test_modeling_labels.py::test_tiny_positive_economic_return_rounds_to_zero_and_is_down
collected 2 items
tests\test_modeling_labels.py ..                                         [100%]
============================== 2 passed in 0.08s ==============================
EXIT_CODE=0
```

## Raw run 3 - session embargo length

Mutation:

```diff
-            max(0, validation_ordinal - embargo_sessions) : validation_ordinal
+            max(0, validation_ordinal - embargo_sessions + 1) : validation_ordinal
```

Command and red output:

```text
> pytest -q tests/test_modeling_partitions.py::test_walk_forward_fold_purges_overlap_and_embargoes_two_sessions
============================= test session starts =============================
collected 1 item
tests\test_modeling_partitions.py F                                      [100%]
FAILED tests/test_modeling_partitions.py::test_walk_forward_fold_purges_overlap_and_embargoes_two_sessions
E AssertionError: assert 7 == 6
E where 7 = len(first.train_rows)
============================== 1 failed in 0.20s ==============================
EXIT_CODE=1
```

Restored output:

```text
> pytest -q tests/test_modeling_partitions.py::test_walk_forward_fold_purges_overlap_and_embargoes_two_sessions
collected 1 item
tests\test_modeling_partitions.py .                                      [100%]
============================== 1 passed in 0.08s ==============================
EXIT_CODE=0
```

## Final restoration proof

```text
> git diff --exit-code
<empty>
EXIT_CODE=0

> git status --porcelain=v1
<empty>
```

These runs independently guard the three highest-risk Slice 3 claims: information availability,
the stored-zero `DOWN` boundary, and the exact two-session embargo. The row contract provides an
additional defense for label-sign drift, but the guarding tests themselves also fail red.
