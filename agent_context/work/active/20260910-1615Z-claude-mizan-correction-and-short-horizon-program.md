# Active work: corporate-action correctness, governed Mizan retrain, and the short-horizon program

STATUS: ACTIVE
OWNER: Claude Code (Opus 5)
TOOL: Claude Code
STARTED_UTC: 2026-09-10T16:15Z
STARTING_REVISION: `5523843c1b4b0b67e3b5da363a942ed6145ee442`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; claimed paths below)
AUTHORIZATION: founder instruction, 2026-09-10 — full task brief covering (1) continuation of the
corporate-action work, (2) corporate-action correctness including HEG, (3) unblocking the governed
retrain with an explicit grant: *"I authorize the necessary governed data/label contract changes for
this task. Resolve ownership explicitly before editing claimed paths."*, (4) re-evaluation of both
existing strategies, (5) a separate 1/2/3-session experiment comparing a simple QuantOS model against
`google/timesfm-3.0-pytorch`, (6) leakage-safe validation with a frozen budget, (7) independent
verification and delivery, plus a bounded Snapdragon Hexagon NPU inference feasibility test.

## Relationship to the predecessor record

This record **continues** `20260910-claude-corporate-action-adjustment-and-mizan-retrain.md` (same
owner and tool). That record stays ACTIVE and keeps its paths; this one adds the paths its own
"Step 4 is blocked" section named as needing a contract change, which the founder has now authorized.
Nothing in the predecessor record is edited.

## Ownership resolution (PROTOCOL §2, §4, §8)

Scanned every `## Owned paths` block in `agent_context/work/active/` at `5523843c`.

| Path | Prior claim | Resolution |
|---|---|---|
| `src/quant_system/data/market_data.py` | **none** — no active record's owned-paths block names it | Claimed here |
| `src/quant_system/modeling/labels.py` | `20260821-1048Z-claude-slice4-redteam-repair.md` via glob `src/quant_system/modeling/*.py`, STATUS **HANDOFF_REQUIRED** | **Explicitly adopted** — see the adoption notice below. PROTOCOL §5 makes adoption the sanctioned route for a HANDOFF_REQUIRED record |
| `scripts/train_mizan.py`, `scripts/screen_mizan_out_of_sample.py`, `src/quant_system/modeling/pooled.py`, `src/quant_system/modeling/mizan_model.py` | `20260825-1500Z-claude-mizan-pooled-model.md`, now in `work/completed/` | Released; claimed here |
| `src/quant_system/research_xs_monthly/**` | `20260903-hermes-xs-monthly-screen-new.md`, STATUS **ACTIVE** | **Not adopted.** Edited only under the founder's explicit instruction to correct its accounting, with an additive NOTICE filed. See below |
| `src/quant_system/modeling/mizan_features.py` | `20260826-claude-mizan-canonical-window-and-kernel.md`, IN_PROGRESS | **Not touched.** Read and called only |
| `scripts/run_paper_pilot_session.py`, `src/quant_system/execution/paper_pilot.py` | Antigravity / others, ACTIVE | **Not touched.** Paper books are read, never mutated |

### Adoption notice for `20260821-1048Z-claude-slice4-redteam-repair.md`

That record is `STATUS: HANDOFF_REQUIRED` and has been since 2026-08-21T16:05Z. PROTOCOL §5: *"Leave
the active record in place until another agent explicitly adopts it."* This is that explicit
adoption, and it is **partial and named**, not a blanket takeover of its glob:

- Adopted: `src/quant_system/modeling/labels.py` only.
- Not adopted, and left entirely alone: every other file under its `src/quant_system/modeling/*.py`
  and `src/quant_system/evidence/*.py` globs, and all of its `tests/` claims except a new file.

Its record is **not edited** (PROTOCOL §3). This record is the visible declaration.

## Owned paths

Governed contract (newly claimed, per the table above):
- `src/quant_system/data/market_data.py`
- `src/quant_system/modeling/labels.py` (adopted, partial)
- `src/quant_system/data/adjustment_provenance.py` (new)
- `tests/test_adjustment_provenance.py` (new)

Mizan training and evaluation (released by a completed record):
- `scripts/train_mizan.py`
- `scripts/screen_mizan_out_of_sample.py`
- `src/quant_system/modeling/pooled.py`
- `src/quant_system/modeling/mizan_model.py`

Short-horizon experiment (all new):
- `src/quant_system/research_short_horizon/**`
- `scripts/run_short_horizon_experiment.py`
- `scripts/timesfm_probe.py`
- `tests/test_short_horizon*.py`
- `reports/short_horizon/**`
- `data/evidence/derived/**` (versioned derived datasets)

Reports and records:
- `reports/corporate_action_validation/**`
- `reports/strategy_reevaluation/**`
- `agent_context/work/active/20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md`
- Any `20260910-*-NOTICE-*` record this session files

Inherited from the predecessor record (unchanged, same owner):
- `src/quant_system/data/corporate_actions.py`, `tests/test_corporate_actions.py`,
  `scripts/build_mizan_feature_store.py`, `data/evidence/feature-store/mizan/`,
  `data/evidence/market-cache/all-market-20160822-20260821/corporate-actions/`

## Non-goals

- **No live-money routing, ever.** Research and virtual money only, per the founder brief and the
  standing T4 exclusion in `AGENTS.md`.
- **No overwrite of the running models.** Both paper books, their weights, their portfolio state and
  their history are preserved. A successful retrain produces a *new versioned artifact*; it does not
  replace what is running. The founder brief states this explicitly.
- **No weakening of a governance gate** to obtain a pass. `GatePolicyV1` thresholds are untouched.
- **No overwrite of original data or evidence.** Derived datasets are published alongside, versioned.
- **No promotion.** Anything produced stays `RESEARCH_ONLY` unless it clears the existing gate on its
  own evidence.
- No edit to `.launch/STATE.md` or `agent_context/CURRENT.md` — both claimed elsewhere.

## Plan

| # | Step | State |
|---|---|---|
| A | Ownership resolution and this record | **DONE** |
| B | Corporate-action correctness: tolerance defect, independent demerger validation, HEG entitlement | **DONE except HEG paper accounting** |
| C | Adjustment provenance on `DatasetManifest`; adjusted bars reach `build_label_dataset` | **DONE** |
| D | Governed Mizan retrain (1 ordinal) on consistent features/labels/P&L | **DONE** — `trial_mizan_h11_003`, ordinal 3, DSR 0.2466, `RESEARCH_ONLY` |
| E | Re-evaluate Flagship and XS-Monthly against cash and a same-universe benchmark | **PARTIAL** — XS-Monthly done; Flagship **refused**, no price source covers its holding period |
| F | Short-horizon experiment: QuantOS simple model vs TimesFM 3.0, holds 1/2/3 | **IN PROGRESS** — budget frozen, holds mapping proven, TimesFM environment built |
| G | NPU feasibility test, bounded | **DONE — `NPU_UNREACHABLE`, documented** |
| H | Independent verification, audits, comparison report and model cards | **PARTIAL** — audits PASS, reports written; **no independent adjudication** |

## Step B findings, measured before anything was changed

### B1. The gap-verification tolerance was blind for 27% of the corpus

The predecessor record's repair tested `|observed_gap - published_factor| <= 0.20`, an **absolute
tolerance in factor space**. That test cannot separate its two hypotheses at all when
`|1 - factor| <= 0.40`, because one observation satisfies both -- and it broke the tie toward
"provider did not apply it", double-adjusting a series the provider had already fixed.

Measured across the 423-name research universe against the all-market cache:

| | Count |
|---|---:|
| Published-ratio structural actions with a bar on their ex-date | **212** |
| Of those, inside the blind band `|1 - f| <= 0.40` | **57 (27%)** |
| Kind of every one of those 57 | bonus (1:10, 1:5, 1:4, 1:3, 1:2) |

Names affected included ICICIBANK, NTPC, POWERGRID, GAIL, BEL, CONCOR, PFC, RECLTD, LT, IOC and
MOTHERSON. A double-applied 1:10 bonus rescales all prior history by 0.909, which reads as a
spurious +10% day and corrupts every trailing feature crossing it.

**Repaired** by scoring both hypotheses in log-return space and taking the nearer, subject to a
residual bound (`MAX_LOG_RESIDUAL = 0.15`). Calibrated from the corpus, not chosen: the largest
`|ln(gap)|` across all 212 is **0.1035** (ASTRAL 2019-09-16). Under the repaired rule all 212 resolve
to ALREADY_APPLIED, unanimously.

Mutation-verified: reinstating the historical absolute-tolerance rule fails
`test_a_bonus_the_provider_already_applied_is_not_applied_a_second_time[Bonus 1:10 ...]` and
`[Bonus 1:5 ...]` plus `test_a_gap_matching_neither_hypothesis_is_unresolved_not_forced`.

### B2. Gap inference for demergers had to be removed, not tuned

The founder brief: *"A price gap alone is not proof of the adjustment amount; genuine market
movement must not disappear."* Measured, that is not a theoretical concern.

Across all **54** ratio-less actions in the universe with a measurable ex-date gap, the previous
20%-threshold inference rule would have fired on three with **positive** gaps:

| Symbol | Ex-date | Gap | Inferred factor the old rule would have applied |
|---|---|---:|---:|
| NMDC | 2022-10-27 | **+71.04%** | 1.7104 -- scaling six years of history *up* by 71% |
| BAJAJELEC | 2023-09-14 | +32.21% | 1.3221 |
| SCI | 2023-03-31 | +30.00% | 1.3000 |

A demerger cannot raise the parent's price. Those gaps are market movement or a provider adjustment,
and "correcting" them erases a genuine move and invents a fake one in its place.

**Repaired** by removing the inference path entirely. A ratio-less action is now `UNRESOLVED` unless
a caller supplies a factor validated against evidence *outside* the gap, and every feature window and
label window spanning an unresolved action is dropped.

### B3. Independent validation, and what it can honestly establish

`scripts/validate_demerger_factors.py` (new). It never derives a ratio from the parent's price. It
checks value continuity against the **resulting company's own first traded price**:

    parent_close_cum ~= parent_open_ex + ratio x resulting_first_open

The ratio is an input from the issuer filing (`data/authorities/nse-demerger-entitlements.json`),
never an inference. The script also reports each ex-date gap **next to the same-day cross-sectional
median move**, so the part of the gap that is market movement stays visible instead of being absorbed.

For **HEG specifically the honest answer is that it cannot be validated here**: the demerger ex-date
is 2026-09-07 and this cache's `received_end` is 2026-08-21, so HEG Graphite has no price anywhere in
this repository. The entitlement is therefore an **unpriced asset**, which is exactly what the loss
diagnosis concluded and what the XS-Monthly book must disclose. Recorded as an entitlement entry with
the filing cited, and expected to refuse with `RESULTING_COMPANY_NOT_IN_CACHE`.

## Step C: how the governed retrain was unblocked

Three constraints had to hold simultaneously.

1. **Existing evidence keeps its identity.** Every manifest hash committed to this repository binds
   published model evidence. `DatasetManifest.adjustment` therefore defaults to `None` and reproduces
   the version-1 payload byte for byte. Proven against 20 real committed manifests plus a test that
   compares the *code's* key set and adjustment block against committed evidence, so a change to
   `to_canonical_dict` cannot pass unnoticed.
2. **Derived data cannot claim to be raw.** Setting `adjustment` emits a full `AdjustmentReference`
   -- method, method version, basis, authority id and content hash, source URL, publication date,
   code revision, derivation time, source dataset id and manifest hash, every factor with the
   evidence class that sized it, and every unresolved action -- and switches the manifest to
   `DATASET_MANIFEST_VERSION_ADJUSTED = 2`. The raw acquisition is never mutated;
   `derive_adjusted_acquisition` produces a separate artifact with its own identity.
3. **Features, labels and P&L agree, without double-counting.** `build_label_dataset` gained
   `execution_acquisition`. The measured acquisition supplies the prices the **return** is computed
   on (adjusted); the execution acquisition supplies the prices a fill **executes** at (raw) and the
   notional the quoted costs are divided by. NSE charges are not all ad valorem -- a flat DP charge
   and a capped brokerage do not scale with a synthetic price -- so pricing costs on adjusted bars
   would misstate them. Omitting the argument reproduces today's behaviour exactly, hash included.

A window spanning an **unresolved** action is refused: no label, and the cost quote is accounted as
refused rather than unused so the quote-completeness guard still holds.

`src/quant_system/modeling/rows.py` was **not** edited -- it is claimed by
`20260820-codex-slice4-ridge-training.md`. The adjustment binds into label identity through
`source_dataset_hash`, which is the adjusted manifest's hash, so no change to `metadata_dict()` or
`require_label_dataset_identity` was needed.

## Step G: the NPU answer, and why it is structural

`scripts/npu_feasibility_probe.py` -> `reports/short_horizon/npu-feasibility-probe.json`, written up
in `reports/short_horizon/NPU-FEASIBILITY.md`. **Verdict `NPU_UNREACHABLE`; CPU execution retained;
accounting and risk controls untouched.**

| Check | Result |
|---|---|
| NPU hardware | **Present and OK** — `Snapdragon(R) X - X126100 - Qualcomm(R) Hexagon(TM) NPU` |
| Python interpreter PE machine type | **`0x8664` = AMD64**, for both `.venv` and the base interpreter |
| `sysconfig.get_platform()` | `win-amd64`; installed `torch` wheel tag `cp313-cp313-win_amd64` |
| QNN backend libraries | **0 of 4** found |
| CPU baseline | 5.94 ms per 512^3 float32 matmul, **45.2 GFLOP/s** |

**The whole QuantOS environment is emulated x86-64 on ARM64 hardware.** An emulated x86-64 process
cannot load ARM64 DLLs, and the QNN HTP backend is ARM64-only, so the NPU is unreachable from this
environment no matter what is installed into it.

Two things about how this was measured are worth keeping:

- **`platform.machine()` is useless for this question.** It reported `ARM64` in one shell and
  `AMD64` in another during this session, because it describes the processor and is sensitive to how
  `PROCESSOR_ARCHITECTURE` propagated. The probe reads the interpreter's own **PE header** instead,
  which is a statement about the binary rather than the silicon.
- **`uv pip install onnxruntime-qnn` resolves successfully here** (`onnxruntime-qnn==2.5.0`).
  Installing it would have appeared to work, provided no `QNNExecutionProvider` at runtime, fallen
  back to CPU silently, and produced timings that looked like "the NPU gives negligible benefit".
  That is why the probe reports interpreter architecture *before* any timing.

Unblocking it needs a native ARM64 CPython (none is installed; `uv` is itself x86-64 and enumerates
no `aarch64` build), a rebuilt environment against it, the Qualcomm QNN SDK, and model conversion
plus quantisation. The first is a machine-level decision for the founder, not something a bounded
feasibility test should do unilaterally.

## Step F so far

- **Experiment budget frozen before any result**: `reports/short_horizon/TRIAL-LEDGER.md`. Six
  published trials (2 model families x 3 holds) plus one abstention grid declared once for all six.
  Prior search is priced in: 101 governed ordinals and 7 screens already spent on this market, none
  of which found an edge surviving costs.
- **The hold mapping is proven, not assumed**: `tests/test_short_horizon_mapping.py` drives the real
  `build_label_dataset` and reads back the entry/exit timestamps. `horizon_sessions` of 2, 3 and 4
  give holds of 1, 2 and 3 sessions, and entry is always the next eligible open. This matters because
  the Flagship book already carries a documented 11-vs-10 instance of the same off-by-one, and
  getting it wrong here would halve or double every cost-per-session figure in the study.
- **TimesFM environment built and isolated**: `D:/quant_system_workspaces/scratch/timesfm-probe-20260910`
  with `torch==2.14.0` and `timesfm==3.0.2`. The QuantOS `.venv`, `pyproject.toml` and `uv.lock` are
  untouched.
- **Pretraining-overlap asymmetry declared in advance**: a negative TimesFM result stays informative;
  a positive one is not evidence of skill on unseen data, because NSE daily history is public and the
  model card establishes no exhaustive cutoff. Declared before any number exists so it cannot be
  dropped if the result is favourable.

## Test state at this checkpoint

| Suite | Result |
|---|---|
| `tests/test_corporate_actions.py` | 44 passed |
| `tests/test_adjustment_provenance.py` | 35 passed |
| `tests/test_adjusted_label_economics.py` | 11 passed |
| `tests/test_short_horizon_mapping.py` | 10 passed |
| Full suite | **1221 passed, 1 failed in 17m52s** |

The single failure is `tests/test_server_api.py::test_create_and_poll_backtest_operation`, a
`HEARTBEAT_TIMEOUT` at `elapsed_seconds: 10.012839` against a 10.0 s limit while two other heavy
processes were running. It passes alone in 11.13 s. Not a regression from this work and not on any
path this work touches; filed as
`20260910-NOTICE-server-api-backtest-poll-flaky-under-load.md` for the owner of that claimed file.

`tests/test_committed_evidence_integrity.py` also fails, reporting 3,359 tracked evidence files whose
bytes differ from their committed blobs. That is the **predecessor record's** corporate-action
authority refetch, present in `git status` before this session started, not something this work
caused.

## Session-2 additions

### A caller defect the peer session flagged, verified and repaired

`20260910-NOTICE-predecessor-left-uncommitted-screen-edit-and-broken-caller.md` reported
`build_mizan_feature_store.py` broken against the `AdjustmentPlan` contract. **Verified: that half
was already stale** -- the builder was repaired before the notice landed, and `AdjustmentPlan.__iter__`
keeps the old two-tuple unpacking working anyway.

The second half was **real and current**: `screen_mizan_out_of_sample.py:114` unpacked
`bars, _, _ = adjusted_bar_points(...)` from a function that now returns two values. It imported
cleanly and would have failed only at call time. Repaired, and while there the screen was brought
into line with the governed label path: it now refuses windows spanning an unresolved corporate
action instead of measuring across them, so the screen and `build_label_dataset` agree about which
observations exist.

### The store scan was rebuilt after two `MemoryError` kills

Reconstructing all 3,322 acquisitions to use 423 of them exhausted the machine twice, dying inside
`json.dumps` in `canonical_sha256`. Replaced with a two-phase design now shared by the builder and
the validator: a cached index over manifest **headers** picks the dataset per symbol (same rule as
`deduplicate_by_symbol` -- longest history, ties by provider instrument id), then only those datasets
are opened, each still through `open_verified`. ~8x less of the store is touched and integrity
checking is not skipped.

### Independent demerger validation ran, and validated nothing

| Outcome | Count |
|---|---:|
| Ratio-less actions examined | 54 |
| **Independently validated** | **0** |
| Refused `NO_FILING_RATIO` | 54 |
| Refused `NO_EX_DATE_BAR` | 2 (including **HEG**) |

Zero is the correct result. Entitlement ratios are legal facts in issuer filings and this repository
holds one. Every unvalidated action stays unresolved and its windows are refused.

**HEG returns `NO_EX_DATE_BAR`**: ex-date 2026-09-07, cache `received_end` 2026-08-21. The resulting
company has no price anywhere in this repository, so the entitlement is an **unpriced asset** -- which
is exactly what lets the XS-Monthly book disclose it rather than book a fabricated loss or recovery.

### The discovery worklist ranking was measured and found near-useless on price alone

Ranking candidates by how well their first traded price implies a clean entitlement ratio has a
**measured false-discovery rate of 8.51%** (178 of 2,091 candidate/action pairs). Concretely: for
ABFRL the correct resulting company **ABLBL ranked fourth**, behind SILKY which is unrelated;
ARVIND's top price-fit candidate was an **ETF**.

Re-ranked on **shared name stem** first, price fit only breaking ties. SKFINDIA -> SKFINDUS and
ABFRL -> ABLBL are the kind of lead that is actually informative. It remains discovery, not
validation.

### Short-horizon validation machinery, with its own tests

- `research_short_horizon/walkforward.py` -- purged, embargoed, chronological folds. The leak it
  prevents is silent: a split at session `s` scores training rows on prices inside the validation
  period whenever `k + horizon >= s`. Tested by checking **every training row of every fold**, not by
  asserting the split code was called.
- `research_short_horizon/abstention.py` -- the cash rule, scored **per decision rather than per
  trade**, because per-trade scoring rewards abstaining down to a handful of lucky decisions. A
  threshold leaving fewer than `minimum_trades` acted-on decisions is refused: "never trade" is the
  cash baseline, not a model result. Ties prefer the *less* selective threshold.

16 tests. Total across this session's suites: **116 passing**.

## TimesFM 3.0: it runs, and the throughput redesigned the study

`scripts/timesfm_probe.py` -> `reports/short_horizon/timesfm-probe.json`, written up in
`reports/short_horizon/TIMESFM-FEASIBILITY.md`.

| Measure | Value |
|---|---:|
| Checkpoint | `google/timesfm-3.0-pytorch`, revision **`43046b85ec22d584a13f8098c2ed39c889e129c2`** |
| Load | 5.2 s |
| **Peak working set** | **2,568.8 MiB** |
| Single-series forecast, holds 1/2/3 | 283 / 264 / 291 ms |
| Batched (>=8 series) | **~116 ms/series** |

**The throughput is a design constraint, not a footnote.** 423 names x 2,427 decision dates x 0.116 s
is about **33 days** of compute. The scope was therefore declared in the trial ledger *before any
TimesFM trial ran*: 50 highest-turnover names, full history, ~3.9 hours -- and **both** arms
restricted to the identical subset, because a full-universe simple model against a subset TimesFM
would confound model quality with sample size.

Two probe defects worth recording, both of which produced plausible-looking wrong output:

1. **The 2.5 loader read as a 3.0 platform failure.** `TimesFM_2p5_200M_torch.from_pretrained`
   against the 3.0 checkpoint raises `Missing key(s) in state_dict: "tokenizer.hidden_layer.weight"`,
   which looks like "3.0 is broken here". It is not -- 3.0 has its own class, `TimesFM3Forecaster`,
   and loads in 5 seconds. The probe now dumps the module's attributes on a load failure.
2. **Peak memory printed `None` beside real timings.** `GetProcessMemoryInfo` was called without
   explicit `argtypes`, so ctypes marshalled the process HANDLE as a 32-bit int and the call failed
   silently on 64-bit Windows. "None MiB" next to genuine latencies reads as "used no memory". The
   real answer is 2.57 GB.

## The multiplicity guard fired, and the honest fix was to obey it

The first retrain attempt targeted a **fresh** evidence root and passed `--multiplicity-ordinal 3`.
`require_next_persisted_trial` refused it: `MULTIPLICITY_INVALID: trial ordinal must be 1 from
persisted history`.

The tempting reading is "use ordinal 1 then". That would have been wrong. `data/evidence/models/
mizan-v1` already holds **two terminal trials** on the same candidate `cand_mizan_v1`, so a fresh
store at ordinal 1 would deflate a third attempt as if it were a first. The retrain was re-pointed at
the existing store as **ordinal 3**, which is what the guard was protecting.

## Operational note: two jobs, one 16 GB machine

A governed retrain was lost to memory exhaustion while the TimesFM probe held 2.57 GB. The store scan
had already been rebuilt once for the same reason. TimesFM work and training work must not be
scheduled concurrently on this machine, and that is now stated in the TimesFM report rather than
rediscovered.

## Experiment budget (frozen here, before any result is seen)

Declared in advance so it cannot be widened after a disappointing number. Counted in
`reports/short_horizon/TRIAL-LEDGER.md`; every entry is recorded whether or not it is published.

| Family | Trials |
|---|---:|
| Short-horizon simple model — holds {1,2,3} | 3 |
| TimesFM 3.0 zero-shot — holds {1,2,3} | 3 |
| Abstention threshold, calibrated on train/validation only | 1 grid, declared once, not per hold |
| **Total short-horizon budget** | **6 published trials + 1 declared calibration grid** |
| Governed Mizan retrain | 1 ordinal |

A final chronological holdout is reserved and stays untouched until a candidate is frozen.

## Decision rationale

**Why the contract change is the right unblock rather than another screen.** The predecessor record
substituted `screen_mizan_out_of_sample.py` for the governed retrain because correcting the label
path meant editing a claimed governed contract. The founder brief forbids that substitution
outright: *"Do not substitute screen_mizan_out_of_sample.py for the requested governed retrain."* The
grant of authority and the refusal of the substitute arrive together, so the contract change is now
the only compliant route.

**Why `DatasetManifest` must change and not just be worked around.** `to_canonical_dict` emits the
literal `"adjustment": {"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}`. Any evidence produced
from adjusted bars through the current contract would declare itself RAW, immutably. That is the
exact defect class this work exists to remove, so routing around it would be self-defeating.

## Commands and outcomes

| Command | Result |
|---|---|
| `git rev-parse HEAD` | `5523843c` |
| `git worktree list` | 3 worktrees; the 2 Codex ones untouched (PROTOCOL §8.3) |
| Owned-paths scan across 83 active records | Resolutions in the table above |

## Blockers and conflicts

- `src/quant_system/research_xs_monthly/**` is under a live Hermes claim. Handled by NOTICE plus
  founder authorization, never by adopting their record.
- `torch`, `pandas`, `transformers` and `huggingface_hub` are absent from `.venv`, and the machine is
  Windows ARM64. TimesFM 3.0 viability on this platform is an open measurement, not an assumption.

## Step D result: the retrain ran, and the candidate loses money

`trial_mizan_h11_003` in `data/evidence/models/mizan-v1`, **ordinal 3** (appended to the existing
Mizan history, not a fresh store, so deflation counts all three attempts). 598 factors applied,
7 unresolved actions had their label windows refused. Horizon 11, matching what the live Flagship
book runs.

| Strategy | Sharpe | Total return | Accuracy | Trades |
|---|---:|---:|---:|---:|
| **RIDGE (candidate)** | **+0.1672** | **-5.82%** | 0.4843 | 3,080 |
| NO_TRADE | 0.0000 | 0.00% | 0.4895 | 0 |
| BUY_AND_HOLD | +1.4037 | +64.03% | 0.5105 | 10,714 |
| PREVIOUS_SIGN | **+1.6312** | **+71.48%** | 0.4957 | 5,394 |
| EQUITY_DUAL_MOMENTUM | -0.2724 | -15.98% | 0.4808 | 4,824 |

`deflated_sharpe_ratio = 0.246621` against a `0.95` gate. Verdict **`RESEARCH_ONLY`**.

**What the correction bought:** DSR 0.176 -> 0.247 *while deflating against a harsher attempt count*
(3 rather than 2). A real improvement attributable to the data, and nowhere near enough.

Two guards fired correctly and were obeyed rather than worked around: `MULTIPLICITY_INVALID` on a
fresh store (which would have deflated a third attempt as a first), and `EvidenceConflict` refusing a
duplicate commit of the same trial id.

## Step E result: one refused, one reframed

**Flagship: REFUSED.** It opened on 2026-08-31; the deepest research cache ends 2026-08-27 and its
session reports carry only aggregate performance. **No price source in this repository covers its
holding period**, so no matched benchmark can be computed. Precise external blocker: it needs either a
cache refresh covering 2026-08-31 onward, or per-name marks persisted in the session reports.

The near-miss is the important part. The first version of the script did **not** refuse -- it marked
positions at the last price on or before 2026-08-21, *ten days before the positions existed*, and
produced entirely plausible numbers (gross +9,229.09, net +6,224.14, "underperforms its benchmark by
8,269.25"). Nothing about the output looked wrong. It now raises `MarkDateBeforeEntry`.

**XS-Monthly: the displayed loss is dominated by one unpriceable position.** Marked 2026-09-09 on the
book's own recorded marks, HEG excluded from **both** entry consideration and marked value:

| | INR |
|---|---:|
| Gross P&L (91 priced legs) | **+4,155.67** |
| Paid costs | 0.00 |
| Prospective exit costs | 1,920.90 |
| **Net P&L** | **+2,234.77** |
| Matched benchmark, net | -4,182.41 |
| **Excess over benchmark** | **+6,417.18** |
| Unpriced: HEG | 9,425.00 of capital, no defensible value |

The **+4,155.67 reproduces the loss diagnosis exactly** ("other 98 selected legs combined =
INR +4,155.67"), by a different route -- an independent check that the decomposition reads the book
correctly.

A defect caught in my own script during this: excluding HEG's *value* while keeping its *entry cost*
implicitly marks the position at zero, which is a larger error than the one being corrected. Both
sides are now excluded and the entry cost reported separately.

## Step F: the harness, and three defects it caught before they mattered

Built: `research_short_horizon/evaluation.py` (purged walk-forward, train-only standardisation,
closed-form ridge, per-decision scoring, five baselines on the identical decision set),
`scripts/run_short_horizon_experiment.py`, `scripts/generate_timesfm_forecasts.py`.

**41 tests**, including a **leak control**: it plants the target as a feature and asserts the harness
reports Sharpe > 3. That direction is deliberate -- if a *known* leak did not show up, the harness
could not detect an unknown one and none of its honest-looking numbers would mean anything.

Labels come from the governed `build_label_dataset` against derived adjusted acquisitions, so the
return is on the adjusted basis, the costs are dated NSE rules on raw executable opens, and a window
spanning an unsized corporate action produces no label.

### Defect 1: the subset selector dropped the largest names

Selecting each symbol's **longest** acquisition and then filtering for universe authority reduced the
subset to **19 names**, losing RELIANCE, HDFCBANK, ICICIBANK and SBIN -- precisely what a turnover
rule exists to select. Several symbols carry two datasets where the longer one is *unbound*. Fixed to
select the longest **among the bound ones**, which is what `train_mizan.governed_acquisitions`
already did. Subset is **45 names**. Both the experiment and the forecast generator now share that
one selector: two scripts disagreeing about the subset would mean the arms were not evaluating the
same experiment.

### Defect 2: a stale run silently overwrote a good result

Two ridge runs wrote to one output path. The **older** one, carrying the defective selector, finished
last and replaced the corrected output. It was caught only because the payload records its own subset
and a 19-name result sat where a 45-name one belonged.

The contaminated numbers were directionally consistent with the clean ones, which is exactly why this
is worth recording: a plausible wrong result is harder to notice than an implausible one. The runner
now moves an incumbent aside rather than replacing it.

### Defect 3: every hold was about to read the 1-step forecast

`_load_forecasts` returned a single `predicted_return` regardless of hold, so a 3-session hold would
have been scored against a **1-session** forecast -- testing a model nobody proposed, silently. One
`horizon=3` pass returns steps 1, 2 and 3; each hold now reads its own. Verified against a synthetic
payload before the 2.5-hour forecast run could make it expensive.

### Declared scope, amended twice and both times before results

- **45 names**, not 50: only 45 research-universe names have a universe-bound governed acquisition.
  A data-availability fact, not a choice.
- **Both arms on the identical subset.** The ridge could have used the full universe in minutes;
  letting it would confound model quality with sample size.

## Verification state

| Gate | Result |
|---|---|
| `scripts/audit-agent-claims.ps1` | **PASS** |
| `scripts/audit-disk-layout.ps1` | **PASS** |
| Ruff check + format, all owned files | clean |
| Mypy, owned `src/` | **Success, 22 source files** |
| This session's suites | **116 passing** |

**No independent adjudication.** Everything here is author-verified. The training path was already
the largest evidence gap in `CURRENT.md` and this work does not close it -- it adds to it.

## Stop point

Steps A, B, C, D, G complete. E partial (Flagship refused for want of data). F has complete
infrastructure and a frozen budget but **none of its six trials has run**. H has passing audits and
written reports but **no independent adjudication**.

Working tree carries this session's edits; the auto-sync commits on its own schedule.

## Next safe action

The short-horizon trials, in this order:

1. Build the evaluation harness that joins `walk_forward_folds`, `calibrate_threshold` and the
   governed cost path into a runnable trial. It does not exist yet.
2. Materialise the declared 50-name subset from the universe authority.
3. Run the three simple-model holds (minutes), then the three TimesFM holds (~3.9 hours, and **not**
   concurrently with anything else -- 2.57 GB peak cost a governed retrain to OOM in this session).
4. Only after all six are recorded in the ledger, evaluate the frozen candidate once on the reserved
   holdout.

Do **not** start step 4 before steps 1-3 are complete and logged. And nothing here justifies changing
either running book: Flagship's re-evaluation is still blocked on data, not on analysis.
