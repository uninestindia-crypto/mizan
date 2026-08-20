# Mutation Report - Slice 4

DATE: 2026-08-20  
STATUS: PASS - four dangerous mutations killed; exact implementation restored  
BASE REVISION: `e6002d2bd73759beb8e4cb5a8354b2eb0e77f8f6`

## Method

Each mutation was applied alone with `apply_patch`, its smallest guarding test was run to a real
red exit, the production line was restored with `apply_patch`, and the same test was rerun green.
No expected-failure marker, mock pass, or edited assertion was used.

## Raw run 1 - score equality boundary

Mutation:

```diff
-    candidate_targets = tuple("UP" if Decimal(score) > threshold else "DOWN" for score in scores)
+    candidate_targets = tuple("UP" if Decimal(score) >= threshold else "DOWN" for score in scores)
```

Command and red output:

```text
> pytest tests/test_modeling_ridge.py::test_score_equal_to_threshold_is_down_by_contract -q
collected 1 item
tests\test_modeling_ridge.py F                                           [100%]
E AssertionError: assert 'UP' == 'DOWN'
FAILED tests/test_modeling_ridge.py::test_score_equal_to_threshold_is_down_by_contract
============================== 1 failed in 0.40s ==============================
EXIT_CODE=1
```

Restored output:

```text
tests\test_modeling_ridge.py .                                           [100%]
============================== 1 passed in 0.25s ==============================
EXIT_CODE=0
```

## Raw run 2 - validation leakage into preprocessing

Mutation:

```diff
-    preprocessing = fit_standardization(training_features)
+    preprocessing = fit_standardization((*training_features, *validation_features))
```

Command and red output:

```text
> pytest tests/test_modeling_ridge.py::test_governed_ridge_fold_is_exactly_repeatable_with_pinned_hashes -q
collected 1 item
tests\test_modeling_ridge.py F                                           [100%]
E AssertionError: assert '0029eab19d44...fed3aaecefb54' == 'a2500c0ad75d...42fa431797872'
FAILED tests/test_modeling_ridge.py::test_governed_ridge_fold_is_exactly_repeatable_with_pinned_hashes
============================== 1 failed in 0.31s ==============================
EXIT_CODE=1
```

Restored output:

```text
tests\test_modeling_ridge.py .                                           [100%]
============================== 1 passed in 0.21s ==============================
EXIT_CODE=0
```

## Raw run 3 - success-only multiplicity

Mutation:

```diff
-        return len(self.starts)
+        return sum(outcome.state == TrialState.SUCCEEDED for outcome in self.outcomes)
```

Command and red output:

```text
> pytest tests/test_modeling_validation.py::test_multiplicity_changes_dsr_but_not_predictions_or_metrics -q
collected 1 item
tests\test_modeling_validation.py F                                      [100%]
E ValueError: evaluation multiplicity must be positive
FAILED tests/test_modeling_validation.py::test_multiplicity_changes_dsr_but_not_predictions_or_metrics
============================== 1 failed in 0.32s ==============================
EXIT_CODE=1
```

Restored output:

```text
tests\test_modeling_validation.py .                                      [100%]
============================== 1 passed in 0.21s ==============================
EXIT_CODE=0
```

## Raw run 4 - trial start moved after fitting

Mutation: moved the `store.commit(draft_from_trial_start(...))` block from before evaluation to
after the evaluation exception path.

Command and red output:

```text
> pytest tests/test_modeling_trials.py::test_failure_still_persists_start_and_typed_terminal_outcome -q
collected 1 item
tests\test_modeling_trials.py F                                          [100%]
E quant_system.evidence.errors.EvidenceNotFound: evidence resource does not exist: trial_ridge_001
FAILED tests/test_modeling_trials.py::test_failure_still_persists_start_and_typed_terminal_outcome
============================== 1 failed in 0.35s ==============================
EXIT_CODE=1
```

Restored output:

```text
tests\test_modeling_trials.py .                                          [100%]
============================== 1 passed in 0.24s ==============================
EXIT_CODE=0
```

## Restoration proof

After all four restorations, the exact Slice 4 gate passed: Ruff lint/format, strict Mypy, 235
repository tests at 88.71% coverage, 68 focused tests, vulture, zero secret candidates, Code
Craft, and Test Craft. This report records raw red and restored-green markers for every mutation.
