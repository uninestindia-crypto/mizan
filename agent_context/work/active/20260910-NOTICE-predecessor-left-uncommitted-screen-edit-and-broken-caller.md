# NOTICE: two uncommitted edits from the predecessor session, and one broken caller

STATUS: NOTICE (additive; no other record is edited)
FILED_UTC: 2026-09-10T13:20:00Z
FILED_BY: Claude Code, predecessor session
  (`20260910-claude-corporate-action-adjustment-and-mizan-retrain.md`)
ADDRESSED_TO: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (ACTIVE), which
  now claims every path named below.

## Why this exists

The successor record inherits `src/quant_system/data/corporate_actions.py`,
`scripts/build_mizan_feature_store.py`, `tests/test_corporate_actions.py` and claims
`scripts/screen_mizan_out_of_sample.py`. Two uncommitted edits from the predecessor session are
sitting in those files, and one of them no longer compiles against the rewritten module. Recording
them so they are not mistaken for stale work or silently reverted.

## 1. `scripts/build_mizan_feature_store.py` is BROKEN against the new module API

`build_adjustment_factors` now returns an `AdjustmentPlan`. The caller at line 166 still unpacks the
old two-tuple:

```python
factors, skipped = build_adjustment_factors(actions, bars, total_return=total_return)
return adjust_bars(bars, factors), len(factors), skipped
```

**This is why the full feature-store rebuild failed** (exit 1, `rebuild_adjusted.log`, 423 names, no
traceback captured because the process was redirected). `adjusted_bar_points` and
`load_corporate_actions` in that file are the predecessor's additions and are the integration point
for the adjustment; they need updating to the `AdjustmentPlan` contract before any rebuild will run.

## 2. `scripts/screen_mizan_out_of_sample.py` carries an uncommitted label-adjustment edit

`forward_returns` was changed to back-adjust the next-open prices it computes returns from, and to
take `--corporate-actions-dir` / `--no-adjust` / `--price-return`. The reason it was changed:

**Features and labels came from different places, and only one was being corrected.** The screen
reads features from the CSV store but computed forward returns straight off RAW `acquisition.records`
opens. Adjusting features while leaving labels raw is worse than adjusting neither, because the model
is then fitted on corrected inputs against uncorrected targets.

It imports `adjusted_bar_points` from `build_mizan_feature_store`, so it inherits defect 1.

## 3. What the predecessor established, that is still true and worth keeping

- **The provider already back-adjusts splits and bonuses.** 78 of 78 parsed split/bonus ex-dates in
  the NIFTY500 cache show a gap of ~1.0, not the published ratio. Applying the published ratio on top
  turned TATASTEEL's 10:1 split into a **+945%** day and BEL's into **+952%**. The regression test
  pinning this is `test_an_already_adjusted_split_is_refused_not_applied_again`.
- **Demergers are the real gap**, and the provider does not apply them.
- The all-market authority refetch is **complete**: 3,359/3,359 FETCHED, 0 stale, 0 unavailable,
  window 2016-08-22..2026-09-10.

## 4. The successor's own correction, acknowledged

The rewritten module records that gap-inference would have inferred an **upward** correction for
NMDC (+71.0%), BAJAJELEC (+32.2%) and SCI (+30.0%). A demerger cannot raise the parent's price, so
sizing a ratio-less action from its gap was wrong in the predecessor's design too, not merely
imprecise. That finding is the successor's, is not independently re-measured here, and supersedes the
predecessor's `INFERRED` demerger path.

## 5. No action taken

Nothing under the successor's claim was edited while filing this. The A/B the founder asked for
(RAW baseline vs adjusted, on `screen_mizan_out_of_sample.py`) was **not completed** and is handed to
the successor with defect 1 as its precondition.
