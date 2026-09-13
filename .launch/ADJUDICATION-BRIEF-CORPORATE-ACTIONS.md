# Adjudication brief — the corporate-action correction

## Why this brief exists

On 2026-09-10/11 this repository's understanding of its own market data was rewritten twice. Two
premises that had been stated to the founder with confidence were found false, and the code was
changed on the strength of those findings. **None of that work has been independently adjudicated.**

`.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md` adjudicated the governed retrain and the
short-horizon program, and explicitly excluded this work because **its author wrote it**. The other
concurrent session also authored parts of it. So neither existing agent is independent, and this
brief exists for a third.

## Independence requirement — read this first

You must not have authored any of the files in scope. If you have, stop and say so.

**Do not verify a claim by reading a work record, a report, or `CURRENT.md`.** Every one of those was
written by an author of the code. Verify from: the source, the tests, the committed data authorities,
the market cache, and commands you run yourself. Where a claim is a measurement, **re-measure it**.

Two sessions edited `src/quant_system/data/corporate_actions.py` concurrently on 2026-09-10 — it was
rewritten three times inside one 45-second window (`agent_context/CURRENT.md`, "Concurrency"). Treat
authorship of any individual line as unknown, and judge the code as it stands.

**Try to break these claims.** An adjudication that confirms everything is weaker evidence than one
that finds something, because the failure mode here is that two authors talked each other into a
shared premise. Two such premises have already been caught that way.

## Scope

| File | Lines |
|---|---:|
| `src/quant_system/data/corporate_actions.py` | 535 |
| `src/quant_system/data/adjustment_provenance.py` | 303 |
| `src/quant_system/data/adjusted_acquisition.py` | 181 |
| `src/quant_system/data/market_data.py` | 502 |
| `src/quant_system/modeling/labels.py` | 385 |
| `scripts/validate_demerger_factors.py` | 539 |
| `scripts/fetch_demerger_announcements.py` | 394 |
| `scripts/ingest_all_market_data.py` | authority cadence repair (`ee1b0cb3`) |
| `reports/mizan_ab_screen/**` | the RAW vs adjusted A/B |

Out of scope: the governed retrain, the short-horizon program, the NPU work. Those are adjudicated at
`.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md`.

## Claims to adjudicate

Each is stated as its authors state it. Mark every one **PROVEN**, **DISPROVEN**, or **NOT TESTED**,
with the command or file you used. `NOT TESTED` is a respectable verdict — prefer it to a guess.

### A. The provider already back-adjusts (the premise everything else rests on)

- **A1.** Across the 423-name research universe, **212 of 212** published-ratio structural actions
  already show an ex-date gap of ~1.0, i.e. the provider back-adjusts splits and bonuses itself.
- **A2.** Re-applying the published ratio on top corrupts the series — TATASTEEL's 10:1 split becomes
  a **+945%** day and BEL's a **+952%** day.
- **A3.** Therefore `status: RAW` in a `DatasetManifest` describes *provenance, not arithmetic*.

**This is the load-bearing claim.** If A1 is wrong in either direction the whole correction inverts.
Re-measure it from the market cache; do not accept the reported count.

### B. The log-space nearest-hypothesis test

- **B1.** The prior rule (absolute tolerance `|observed - published| <= 0.20` in factor space) could
  not separate "already applied" from "not applied" whenever `|1 - factor| <= 0.40`, and broke ties
  toward "not applied" — double-adjusting an already-correct series.
- **B2.** That blind band covered **57 of 212** actions (**27%**), **every one a bonus** (1:10, 1:5,
  1:4, 1:3, 1:2), affecting ICICIBANK, NTPC, POWERGRID, GAIL, LT, IOC among others.
- **B3.** The replacement scores the observed gap against both hypotheses in **log-return space** and
  returns `ALREADY_APPLIED` / `NOT_APPLIED` / `MATCHES_NEITHER` against `MAX_LOG_RESIDUAL = 0.15`.
- **B4.** The test is correct at the boundaries: verify it cannot be made to return `NOT_APPLIED` for
  a genuinely already-adjusted series, or vice versa, anywhere in the real corpus.

### C. Demergers are excluded, not repaired

- **C1.** Gap inference for ratio-less actions was **removed entirely**, not tuned.
- **C2.** Had it been kept, it would have inferred *upward* corrections for **NMDC (+71.04%)**,
  **BAJAJELEC (+32.21%)** and **SCI (+30.00%)** — impossible for a demerger, so those gaps are market
  movement, and "correcting" them would erase a real move and invent a fake one.
- **C3.** `scripts/validate_demerger_factors.py` returns **0 validated / 56 refused**.
- **C4.** Windows spanning an unresolved action are **dropped**, not published with a fabricated
  return. Verify a consumer actually drops them rather than silently passing them through.

### D. Adjustment provenance

- **D1.** `DatasetManifest` gained an optional `adjustment: AdjustmentReference | None`, and when it
  is `None` the canonical dict emits the **original literal**, so every previously committed manifest
  hash is **byte-for-byte unchanged**. Verify by recomputing committed hashes, not by reading a test.
- **D2.** When set, the manifest reports `DATASET_MANIFEST_VERSION_ADJUSTED = 2`, so derived data
  **cannot declare itself RAW**.
- **D3.** `derive_adjusted_acquisition()` produces a *separate* artifact with its own `dataset_id`,
  `manifest_hash` and `canonical_content_hash` — the original is preserved, not mutated.
- **D4.** The reference binds method, authorities, timestamps, hashes and code revision.

### E. Label economics — adjusted for returns, raw for fills

- **E1.** `build_label_dataset(..., execution_acquisition=...)` measures `gross_return` on
  **adjusted** bars while computing `entry_notional` from the **raw** fill price.
- **E2.** There is **no double-counting** of a cash or share entitlement.
- **E3.** Refused quotes are tracked separately rather than silently dropped.
- **E4.** **Look for leakage.** Every value used at a decision must be available at that decision
  time. The adjustment factors are derived from an authority with a publication date — confirm a
  future-dated corporate action cannot influence a past decision.

### F. The A/B screen

- **F1.** Arm A (RAW) reproduces the previously published selection edge **`-0.000022, t = -0.07`**
  to the digit, which is what makes Arm B interpretable.
- **F2.** Arm B (adjusted) gives **`-0.000185, t = -0.66`**.
- **F3.** Conclusion drawn: **no signal was being masked by bad corporate-action handling**, and
  correcting the data does not rescue the model.
- **F4.** No evidence store was written and **no multiplicity ordinal was spent**. Verify this.

### G. The authority cadence repair (`ee1b0cb3`)

- **G1.** Three defects existed: hardcoded `effective_from` / `effective_to` / `publication_date`; a
  fetch that returned any existing file unconditionally; and a failed fetch writing `[]` which was
  then trusted forever.
- **G2.** Fixing only the first would have been **worse** than leaving all three — the window would
  then claim to cover today while holding weeks-old content.
- **G3.** Freshness now requires `status=FETCHED`, `effective_from <= start`, `effective_to >= end`,
  age <= 24h.
- **G4.** All **3,359** all-market authorities were re-pulled: 3,359 FETCHED, 0 stale, 0 unavailable.

### H. Demerger issuer citations

- **H1.** **18 of 56** unresolved actions are named from the issuer's own filing text; 49 issuers
  queried, 0 fetch failures.
- **H2.** RELIANCE 2023-07-20 is **rejected** as `FILER_IS_RESULTING_COMPANY` — the filing describes
  an inbound merger that fell inside the +/-540-day window, not the demerger being priced.
- **H3.** SCI is flagged `NAME_MAY_BE_TRUNCATED` and **not repaired**.
- **H4.** **No entitlement ratio is extracted anywhere**, and nothing writes a factor. Verify this by
  grep, not by trusting the docstring.
- **H5.** Spot-check several of the 18 names against the quoted filing text. Report any that are
  wrong — a wrong citation is worse than no citation, and that is this tool's whole risk.

### I. Tests

- **I1.** `pytest tests/test_corporate_actions.py tests/test_adjustment_provenance.py
  tests/test_adjusted_label_economics.py` collects **90** tests and all pass.
- **I2.** **Do the tests encode the same premises as the code?** This is the most important question
  in this brief. Both defects already found here passed 28 unit tests, ruff and mypy — because the
  tests asserted what the code did, not what was true. Mutate the source and confirm the suite
  actually fails. A test that cannot fail is not evidence.

## Deliverable

Write `.launch/reports/ADJUDICATION-CORPORATE-ACTIONS-20260911.md` containing:

1. An independence statement — what you did and did not author.
2. A verdict table: every claim above, PROVEN / DISPROVEN / NOT TESTED, with the evidence.
3. Raw command output for anything you re-measured.
4. Any defect you found, with a reproduction.
5. A final verdict of **PASS** or **BLOCKED**, with no middle option.

Do not repair anything you find. Report it. Spend no multiplicity ordinal and write no evidence
store — this is a read-only adjudication.
