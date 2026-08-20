# Mutation Report - Slice 4

DATE: 2026-08-20  
STATUS: PASS - eleven dangerous mutations killed; exact implementation restored
BASE REVISION: `e6002d2bd73759beb8e4cb5a8354b2eb0e77f8f6`

## Method

Each mutation was applied alone with `apply_patch`, its smallest guarding test was run to a real
red exit, the production line was restored with `apply_patch`, and the same test was rerun green.
No expected-failure marker, mock pass, or edited assertion was used.

Runs 1-5 were executed against the first Slice 4 candidate. Runs 6-11 were executed after the
independent Red Team found additional release blockers at repair candidate `8d09ec4`.

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

## Raw run 5 - persisted multiplicity authority removed

Mutation: removed the evidence-store commit precondition that derives the next ordinal from the
verified immutable trial catalog while holding the global evidence lease.

```diff
     start_commit = store.commit(
         draft_from_trial_start(start),
         operation_id=f"{operation_id}-start",
-        precondition=lambda: require_next_persisted_trial(store, start),
     )
```

Command and red output:

```text
> pytest tests/test_modeling_trials.py::test_persisted_history_blocks_multiplicity_reset -q
collected 1 item
tests\test_modeling_trials.py F                                          [100%]
E Failed: DID NOT RAISE EvidenceNotFound
FAILED tests/test_modeling_trials.py::test_persisted_history_blocks_multiplicity_reset
============================== 1 failed in 0.40s ==============================
EXIT_CODE=1
```

The failure proves the mutation published a second ordinal-one start. Restored output:

```text
tests\test_modeling_trials.py .                                          [100%]
============================== 1 passed in 0.38s ==============================
EXIT_CODE=0
```

## Raw run 6 - Python boolean accepted as an integer

Mutation replaced all three exact `type(value) is int` checks with `isinstance(value, int)`, which
admits Python booleans.

```text
> pytest tests/test_modeling_trials.py::test_trial_integer_fields_reject_booleans -q
collected 3 items
tests\test_modeling_trials.py FFF                                        [100%]
E Failed: DID NOT RAISE ModelingError
FAILED ...[numpy_seed-False]
FAILED ...[multiplicity_ordinal-True]
FAILED ...[feature_schema_version-True]
============================== 3 failed in 0.40s ==============================
EXIT_CODE=1
```

Restored output: `3 passed in 0.31s`, `EXIT_CODE=0`.

## Raw run 7 - interrupted start/model cannot resume

Mutation restored the former blanket rejection of every deduplicated trial start.

```text
> pytest tests/test_modeling_trials.py::test_start_only_interruption_can_resume_same_attempt tests/test_modeling_trials.py::test_outcome_commit_failure_can_resume_same_attempt -q
collected 2 items
tests\test_modeling_trials.py FF                                         [100%]
E ModelingError: TRIAL_ALREADY_RECORDED: duplicate start cannot resume
FAILED ...::test_start_only_interruption_can_resume_same_attempt
FAILED ...::test_outcome_commit_failure_can_resume_same_attempt
============================== 2 failed in 0.48s ==============================
EXIT_CODE=1
```

Restored output: `2 passed in 0.43s`, `EXIT_CODE=0`.

## Raw run 8 - one-trial DSR becomes a sign shortcut

Mutation returned `1.0` for a positive single-trial Sharpe and `0.0` otherwise.

```text
> pytest tests/test_multiplicity.py::test_single_trial_dsr_retains_sampling_uncertainty -q
collected 1 item
tests\test_multiplicity.py F                                             [100%]
E AssertionError: assert 1.0 < 1.0
FAILED tests/test_multiplicity.py::test_single_trial_dsr_retains_sampling_uncertainty
============================== 1 failed in 0.19s ==============================
EXIT_CODE=1
```

Restored output: `1 passed in 0.12s`, `EXIT_CODE=0`.

## Raw run 9 - symbol-major dataset order returns

Mutation changed the canonical derived-row key from candidate/time/instrument back to
candidate/instrument/time.

```text
> pytest tests/test_modeling_partitions.py::test_multi_symbol_dataset_and_fold_share_chronological_order -q
collected 1 item
tests\test_modeling_partitions.py F                                      [100%]
E ModelingError: RECORD_ORDER_INVALID: derived dataset rows must use candidate, decision-time, and instrument order
FAILED ...::test_multi_symbol_dataset_and_fold_share_chronological_order
============================== 1 failed in 0.24s ==============================
EXIT_CODE=1
```

Restored output: `1 passed in 0.17s`, `EXIT_CODE=0`.

## Raw run 10 - simultaneous instruments compound sequentially

Mutation returned one full-capital period per instrument row instead of one equal-weight return per
decision time.

```text
> pytest tests/test_modeling_metrics.py::test_simultaneous_symbols_use_equal_weight_portfolio_period -q
collected 1 item
tests\test_modeling_metrics.py F                                         [100%]
E AssertionError: assert '-0.0001' == '0'
FAILED ...::test_simultaneous_symbols_use_equal_weight_portfolio_period
============================== 1 failed in 0.21s ==============================
EXIT_CODE=1
```

Restored output: `1 passed in 0.15s`, `EXIT_CODE=0`.

## Raw run 11 - successful outcome no longer resolves model evidence

Mutation removed the verified model-evidence binding from persisted registry loading.

```text
> pytest tests/test_modeling_trials.py::test_success_without_verified_model_is_rejected -q
collected 1 item
tests\test_modeling_trials.py F                                          [100%]
E Failed: DID NOT RAISE ModelingError
FAILED ...::test_success_without_verified_model_is_rejected
============================== 1 failed in 0.31s ==============================
EXIT_CODE=1
```

Restored output: `1 passed in 0.27s`, `EXIT_CODE=0`.

## Restoration proof

After runs 1-5, the first repaired gate passed 236 repository tests at 88.62% coverage and 69
focused tests. After runs 6-11, the restored local tree passed 254 repository tests with 5,806
statements / 661 missed / 88.62% coverage, 80 focused tests, strict Mypy across 82 source files,
Ruff across 196 formatted inputs, vulture, zero application secret candidates, Code Craft, and Test
Craft. The exact committed repair candidate must reproduce these claims during independent
verification.
