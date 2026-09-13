# Mizan corporate-action A/B, rerun on the repaired parser (v2)

Ungoverned screen. **No evidence store written, no multiplicity ordinal spent.**

This rerun exists because an independent adjudication
(`.launch/reports/ADJUDICATION-CORPORATE-ACTIONS-20260911.md`, verdict **BLOCKED**) found three
defects in the corporate-action parser. The original A/B — `reports/mizan_ab_screen/`, which belongs
to another agent's record and is **left untouched** — was computed before those repairs, so its
figures describe data the parser no longer produces.

```bash
.venv/Scripts/python.exe scripts/build_mizan_feature_store.py --out-dir data/evidence/feature-store/mizan-adjusted-v2
```

```bash
.venv/Scripts/python.exe scripts/screen_mizan_out_of_sample.py --feature-store data/evidence/feature-store/mizan/mizan_feature_store.csv.gz --no-adjust
```

```bash
.venv/Scripts/python.exe scripts/screen_mizan_out_of_sample.py --feature-store data/evidence/feature-store/mizan-adjusted-v2/mizan_feature_store.csv.gz
```

## What changed in the data

`mizan-adjusted-v1` is preserved; `mizan-adjusted-v2` is a new versioned artifact built from the
**same authority** (`e68c8e1c…`, byte-identical input) with only the parser repaired.

| | v1 | **v2** | Δ |
|---|---:|---:|---:|
| Factors applied | 4,590 | **5,028** | **+438** dividends the `/-` and `Per Sh` forms had hidden |
| Unresolved actions | 56 | **99** | **+43** — 40 rights issues, 3 unparsed bonuses |
| Symbols with unresolved actions | 49 | 78 | +29 |
| Blacked-out session rows | 2,712 | **4,905** | +2,193 |
| Total feature rows | 1,013,170 | 1,010,987 | −2,183 |

The +43 is the P1 defect being closed: those actions previously produced **no factor and no
unresolved record**, so `spans_unresolved` returned `False` and the ex-rights gap was published as a
real return.

## Result

| | Arm A — RAW (control) | | Arm B — adjusted | |
|---|---:|---:|---:|---:|
| | **original** | **rerun** | **v1** | **v2** |
| Test rows (380 names) | 902,582 | **902,582** | 899,840 | 897,724 |
| Windows refused | 0 | 0 | 532 | **962** |
| Model: mean / t | +0.006528 / +5.86 | **+0.006528 / +5.86** | +0.007249 / +6.61 | +0.007273 / +6.65 |
| Equal-weight: mean / t | +0.006550 / +6.80 | **+0.006550 / +6.80** | +0.007433 / +7.73 | +0.007510 / +7.81 |
| **Selection edge** | **-0.000022** | **-0.000022** | **-0.000185** | **-0.000236** |
| **t** | **-0.07** | **-0.07** | **-0.66** | **-0.86** |

### Arm A reproduces to the digit, and that is what makes Arm B readable

The control is RAW features and RAW labels, so the parser repair cannot reach it. It returns
`-0.000022, t = -0.07` on 902,582 rows — **identical** to the original run and to the figure
published at `20260825-1500Z-claude-mizan-pooled-model.md:313`. The repairs did not disturb the
harness; every difference in Arm B is the data.

### The conclusion is unchanged, and now measured rather than expected

Before rerunning, the expectation on record was: *no change to the conclusion, because a dividend
add-back lifts the model and its benchmark together and cancels in the selection edge, and 40 refused
windows out of ~900,000 rows is immaterial.* That was explicitly flagged as an expectation, not a
measurement. It now holds as a measurement:

- **The selection edge stays negative and stays insignificant**: -0.000185 → **-0.000236**, t -0.66 →
  **-0.86**. It drifts slightly further negative, exactly as it did from Arm A to Arm B originally.
- **Equal-weight still beats the candidate**, and by slightly more (+0.007510 vs +0.007273).
- **All eight fitted coefficients keep their sign**, `sma_20_distance` still the only positive
  (+0.008177 → +0.008435). The model learns the same thing from better-corrected data.

**Read it the same way as before: correcting the data changed nothing that matters.** It is not
"correction made the model worse" — neither figure is significant, and the movement from -0.66 to
-0.86 is well inside noise on overlapping 10-session rebalances.

## What this rerun does *not* cover

- **The six short-horizon trials still read `mizan-adjusted-v1`** (`results-{ridge,timesfm,noise-control}.json`
  all record that path). They are stale in the same way. **They were deliberately not rerun**: the
  frozen ledger declared six trials and six are spent, so re-running on corrected data is a *new*
  experiment with a fresh multiplicity ordinal, not a refresh. That is a decision for the ledger's
  owner, not a side effect of a data repair. The noise control beat both models by more than 2x, and
  a ±0.2% shift in inputs does not plausibly reverse that — but nobody has measured it.
- **The governed retrain `trial_mizan_h11_003` also used v1.** Re-running it would spend ordinal 4 to
  reproduce a null, which the standing guidance forbids.
- **Demergers remain exclusion, not repair.** `validate_demerger_factors.py` still returns 0
  validated. Arm B measures *"dividends added back, contaminated windows dropped"*, and v2 simply
  drops more of them.

## Conclusion

Unchanged from the original A/B, and now resting on corrected data: **do not spend a multiplicity
ordinal on a governed retrain of this candidate.**
