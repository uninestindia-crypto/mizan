# QuantOS data correction, governed retrain, and the short-horizon program

**Session of 2026-09-10.** This is the index for the work and its verdicts. Detail lives in the
linked reports; this file says what was done, what was measured, what was refused, and — with equal
prominence — **what was not finished**.

## Verdicts at a glance

| Item | Verdict |
|---|---|
| Corporate-action gap-verification defect | **REPAIRED** — 27% of the corpus was in a blind band |
| Demerger gap-inference | **REMOVED** — it manufactured upward "corrections" |
| Independent demerger validation | **RAN, VALIDATED ZERO.** 54 of 54 unresolved. Correct outcome |
| HEG entitlement | **UNPRICED, DISCLOSED.** Not valued at zero, not reversed, not invented |
| Adjustment provenance on `DatasetManifest` | **LANDED** — existing hashes byte-identical |
| Features/labels/P&L consistency | **LANDED** — return on adjusted prices, costs on raw executable prices |
| Governed Mizan retrain | **PUBLISHED as ordinal 3.** DSR **0.2466** vs a 0.95 gate. `RESEARCH_ONLY` |
| Snapdragon Hexagon NPU | **`NPU_UNREACHABLE`** — structural, CPU retained |
| TimesFM 3.0 on this machine | **RUNS.** 116 ms/series, 2.57 GB. Throughput redesigned the study scope |
| The six short-horizon trials | **NOT RUN** — infrastructure complete, budget frozen, compute not spent |
| Flagship re-evaluation | **REFUSED** — no price source in the repository covers its holding period |
| XS-Monthly re-evaluation | **DONE** — displayed loss is dominated by one unpriceable position |

## What was found, in order of how much it changes

### 1. The previous corporate-action repair was wrong for 27% of the corpus

The rule applied a published ratio when `|observed_gap − published_factor| ≤ 0.20` — an absolute
tolerance in factor space. It cannot separate its two hypotheses when `|1 − factor| ≤ 0.40`, and it
broke ties toward "not applied", **double-adjusting series the provider had already fixed**.

**57 of 212** published-ratio structural actions sat in that band — ICICIBANK, NTPC, POWERGRID, GAIL,
LT, IOC and others, every one a bonus. Replaced with a log-space nearest-hypothesis test calibrated
from the corpus (largest observed `|ln(gap)|` is 0.1035; bound set at 0.15). All **212 of 212** now
resolve unanimously. Mutation-verified.

### 2. Gap inference for demergers would have invented corrections

Of 54 ratio-less actions, three have **positive** ex-date gaps: NMDC **+71.0%**, BAJAJELEC +32.2%,
SCI +30.0%. A demerger cannot raise the parent's price. The old rule would have scaled six years of
NMDC history *up* by 71% — erasing a genuine move and inventing a fake one.

Removed entirely. Ratio-less actions are `UNRESOLVED`; every feature and label window spanning one is
dropped. On the rebuilt store that is **56 actions on 49 symbols, 2,712 feature rows** — 0.27% of the
data, for a class of fabrication that would have looked exactly like signal.

### 3. Independent validation ran and validated nothing, which is the right answer

`scripts/validate_demerger_factors.py` checks value continuity against the resulting company's own
first traded price, with the ratio taken from the issuer filing — never inferred. Result: **0
validated, 54 refused for want of a filing ratio.**

The discovery worklist was also measured rather than trusted: ranking candidates by price fit has a
**false-discovery rate of 8.51%**, and for ABFRL it put the correct answer (ABLBL) *fourth*, behind an
unrelated name. Re-ranked on shared name stem, with price fit only breaking ties.

Detail: [`corporate_action_validation/CORPORATE-ACTION-VALIDATION.md`](corporate_action_validation/CORPORATE-ACTION-VALIDATION.md)

### 4. The governed retrain was unblocked without breaking existing evidence

Three constraints had to hold at once:

- **Existing manifest hashes unchanged.** `adjustment` defaults to `None` and reproduces the
  version-1 payload byte for byte — verified against 20 committed manifests *and* by binding the
  code's output shape to committed evidence, so a serializer change cannot pass unnoticed.
- **Derived data cannot claim to be raw.** Setting it emits a full `AdjustmentReference` — method,
  version, basis, authority id and hash, code revision, derivation time, source manifest hash, every
  factor with the evidence class that sized it, every unresolved action — at schema version 2.
- **No double-counting.** `build_label_dataset` gained `execution_acquisition`: the **return** is
  measured on adjusted prices, the **costs** stay quoted on raw executable prices at the raw
  notional. NSE charges are not all ad valorem, so a flat DP charge on a synthetic price would be
  wrong.

`modeling/rows.py` was not edited — it is claimed elsewhere, and the adjustment binds through
`source_dataset_hash` instead.

### 5. The NPU is unreachable, and the reason is not the NPU

The Hexagon NPU is **present and healthy**. The blocker is that the entire QuantOS Python environment
is an **emulated x86-64 build** (PE machine type `0x8664`, wheel tags `win_amd64`) on ARM64 hardware,
and an emulated x86-64 process cannot load the ARM64 QNN backend.

The trap this avoided: `uv pip install onnxruntime-qnn` **resolves successfully** here. It would have
installed, provided no NPU execution provider, fallen back to CPU silently, and produced timings
reading as "the NPU gives negligible benefit". That conclusion would have been false and reported as
a measurement.

Detail: [`short_horizon/NPU-FEASIBILITY.md`](short_horizon/NPU-FEASIBILITY.md)

### 6. TimesFM works, and its throughput redesigned the study

Loads in 5.2 s at revision `43046b85ec22d584a13f8098c2ed39c889e129c2`; **116 ms/series** batched;
**2.57 GB** peak. Full universe × full history ≈ **33 days** of compute — infeasible.

Scope declared in the ledger **before any TimesFM trial ran**: 50 highest-turnover names, full
history, ~3.9 hours, **both arms on the identical subset**. Restricting only one arm would confound
model quality with sample size.

Detail: [`short_horizon/TIMESFM-FEASIBILITY.md`](short_horizon/TIMESFM-FEASIBILITY.md)


## 7. The governed retrain ran, and the candidate still loses money

`trial_mizan_h11_003` published into `data/evidence/models/mizan-v1` at **ordinal 3** — appended to
the existing Mizan history rather than a fresh store, so the deflation counts all three attempts.
598 corporate-action factors applied; 7 unresolved actions had their label windows refused.
43 instruments pooled, 103,393 label rows, 2,413 decision dates, fold train 92,206 / validation
10,714 / embargo 11.

| Strategy | Sharpe | Total return | Accuracy | Trades | Max DD |
|---|---:|---:|---:|---:|---:|
| **RIDGE (the candidate)** | **+0.1672** | **−5.82%** | 0.4843 | 3,080 | 0.723 |
| NO_TRADE | 0.0000 | 0.00% | 0.4895 | 0 | 0.000 |
| BUY_AND_HOLD | +1.4037 | +64.03% | 0.5105 | 10,714 | 0.661 |
| **PREVIOUS_SIGN** | **+1.6312** | **+71.48%** | 0.4957 | 5,394 | 0.650 |
| EQUITY_DUAL_MOMENTUM | −0.2724 | −15.98% | 0.4808 | 4,824 | 0.754 |

**The candidate loses 5.8% while buy-and-hold makes 64% and a repeat-the-previous-sign rule makes
71%.** Its accuracy (48.4%) is below never trading (49.0%). It is fourth of five on Sharpe.

`deflated_sharpe_ratio = 0.246621`, against `GatePolicyV1.min_deflated_sharpe = 0.95`.
Verdict **`RESEARCH_ONLY`**. Not promotable.

### What the data correction actually bought

| Trial | Basis | Multiplicity | Deflated Sharpe |
|---|---|---:|---:|
| `trial_mizan_001` | RAW | 1 | 0.000903 |
| `trial_mizan_h11_002` | RAW, horizon 11 | 2 | 0.175990 |
| **`trial_mizan_h11_003`** | **ADJUSTED, horizon 11** | **3** | **0.246621** |

The corrected corporate-action data moved the deflated Sharpe from **0.176 to 0.247 while being
deflated against a *harsher* attempt count** — three trials instead of two. That is a real
improvement attributable to the data, not to the search.

It is also nowhere near enough. 0.247 against 0.95 is not a near miss, and the candidate's total
return is negative in a window where holding the index returned 64%.

### The horizon was matched to what paper actually runs

`--horizon-sessions 11`, because that is what the live Flagship book uses (its portfolio policy
converts 11 to 10 held sessions). The brief required the tested holding horizon to be the one used in
paper inference, and 11 is it.

### Two guards fired correctly and are worth recording

- **`MULTIPLICITY_INVALID`.** The first attempt targeted a fresh evidence root at ordinal 3 and was
  refused: a fresh store's next ordinal is 1. Obeying it by using ordinal 1 would have deflated a
  third attempt as if it were a first. The run was re-pointed at the existing store instead.
- **`EvidenceConflict: immutable resource ID already has different content`.** A duplicate run
  attempted to re-commit `trial_mizan_h11_003` and was refused. The evidence store would not let the
  same trial id be written twice with different content.

## What was NOT finished

Stated plainly, because a program report that buries this is worse than useless.

| Not done | Why, and what it needs |
|---|---|
| **The six short-horizon trials** | Infrastructure, budget and feasibility are complete; the trials themselves need an evaluation harness that is not written, plus ~4 hours of TimesFM compute. **No short-horizon result exists.** Nothing in this report claims one |
| **53 of 54 demerger entitlement ratios** | Filing-reading work, not code. Their windows stay refused meanwhile |
| **HEG corrected inside the XS-Monthly book** | The book is live under a Hermes claim and a scheduled task writes it. Correction published alongside with a notice filed, rather than mutating a running book |
| **Forward-paper observation for any candidate** | Requires a candidate that clears a gate. None does |
| **Independent adjudication** | This session's work is author-verified, not independently adjudicated. The training path was already the largest evidence gap in `CURRENT.md` and still is |

## Gates

| Gate | Result |
|---|---|
| `scripts/audit-agent-claims.ps1` | **PASS** — every workspace has a visible claim, every claim resolves |
| `scripts/audit-disk-layout.ps1` | **PASS** — no stray QuantOS directories |
| Ruff check + format, all owned files | **clean** (34 files) |
| Mypy, all owned `src/` files | **clean** (9 files) |
| This session's test suites | **116 passing** |
| Full repository suite | 1,221 passing, 1 failing — a pre-existing load-sensitive heartbeat timeout in a claimed file, notice filed |

## Standing constraints, unchanged by any of this

- **No model is promotable.** Best deflated Sharpe in the repository remains `0.397794` against a
  `0.95` gate. Nothing here promotes anything.
- **Nothing has ever placed an order**, by design.
- **Both paper books are untouched** — weights, portfolio state and history all preserved. The
  re-evaluation is read-only and opens no file for writing under `logs/`.
- **No gate threshold was adjusted.** `GatePolicyV1` is as it was.
