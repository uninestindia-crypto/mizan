# Current QuantOS snapshot

UPDATED_UTC: 2026-08-20T12:09:31Z  
SNAPSHOT_OWNER: Codex / Antigravity coordination  
BRANCH: `main`  
HEAD_AT_SNAPSHOT: `0acbca2` (independently verified evidence revision)

## Formal release state

- Tier T2, phase P4, gate G4 in progress.
- Slices 1 and 2 passed Red Team and independent clean-state verification.
- Slice 3 passed Red Team and independent clean-state verification; 208 repository tests pass at
  88.58% coverage and 41 focused Slice 3 cases pass.
- Next active slice: Slice 4 (One Governed Ridge Fold & Preprocessing).
- Live-money routing remains explicitly out of scope.
- Authoritative details: `.launch/STATE.md`, `.launch/SLICES.md`, and `.launch/SLICE-03-EVIDENCE.md`.

## Active work & coordination

- Multi-agent coordination system active in `agent_context/`.
- No collision warnings: Slice 3 work is completed and committed.
- See `START_HERE.md` for remote onboarding.

> **Editor's note, 2026-08-22.** The three sections above this note predate the current tree and are
> stale: `.launch/STATE.md` now records P5 with all 12 slices CODE_COMPLETE, not "P4, gate G4 in
> progress, next slice 4". This file is claimed by `20260820-codex-slice4-ridge-training.md` and
> `20260821-claude-ci-workflow.md`; the section below was added on explicit founder instruction and
> is **purely additive** — nothing written by those records was altered. Full reconciliation of the
> stale sections remains the coordinator's job.

## Real-data training runner (added 2026-08-22)

`scripts/run_governed_ridge_training.py` is the first production caller of the governed training
stack. Until it existed, `run_persisted_ridge_trial()`
(`src/quant_system/modeling/training_evidence.py:131`) had no caller outside tests — the stack was
implemented, tested, and unreachable. The runner chains real Upstox acquisition ->
`build_feature_dataset` -> `build_label_dataset` -> `build_purged_fold` ->
`run_persisted_ridge_trial` -> `EvidenceStore`. It imports no data generator, so it has no synthetic
fallback to take.

Status by stage. **All seven stages have now executed on real market data.**

| Stage | Status | Evidence |
|---|---|---|
| 1. Real Upstox acquisition | **PROVEN** | **498 real daily bars** for `NSE_EQ\|INE009A01021` (INFY), 2024-01-01..2025-12-31 |
| 2. Session calendar | PROVEN on the provider-derived path | 498 sessions derived from the exchange dates actually returned |
| 3. Governed re-acquisition | **PROVEN** | 498 bars, `status=ACCEPTED`, `source_status=COMPLETE` |
| 4. `build_feature_dataset` | **PROVEN** | 478 feature rows |
| 5. `build_label_dataset` | **PROVEN** | 476 label rows; real NSE statutory costs, 0.224% round trip |
| 6. `build_purged_fold` | **PROVEN** | train=411, validation=63, embargo=2 |
| 7. `run_persisted_ridge_trial` | **PROVEN — fails closed** | Trial start and terminal `FAILED` outcome both published; `failure_codes=["DEGENERATE_RETURN_SERIES"]` |

Corporate-action authority: `data/authorities/nse-corporate-actions-INFY-20240101-20251231.json`,
fetched from the NSE public API, 5 real records (dividends 2024-05-31, 2024-10-29, 2025-05-30,
2025-10-27 and the 2025-11-14 buyback), all ISIN `INE009A01021`. SHA-256
`650bd8197d8c1ac39e1c6b1f2469d96ee88e468384f07b1b3df83987544cb400`. Committed so the hash is
re-verifiable from the repository.

### No model has been successfully trained. Two trials, both refused.

`trial_real_001` (validation=8) and `trial_real_002` (validation=63) both terminated `FAILED` with
`DEGENERATE_RETURN_SERIES`. Both are recorded in the evidence store with a committed start and a
committed terminal outcome, so the multiplicity ordinal has advanced twice. **A third attempt is a
third look at the same data and must be treated as such.**

Root cause, measured rather than inferred:

- Targets are encoded UP `+1.0` / DOWN `-1.0` (`modeling/ridge.py:93`).
- The real label balance is 182 UP / 229 DOWN in the training partition, so the mean target is
  `-0.1144` and the fitted ridge intercept is `-0.114355` — they agree to five decimals.
- Validation scores over 63 sessions span `[-0.243, -0.026]`, mean `-0.140`, stdev `0.053`. The
  **maximum score is still below the `score_threshold=0`**, so the candidate predicts UP zero times
  out of 63 and takes no position at all.
- `_portfolio_period_returns` (`modeling/validation.py:402`) only records a return where
  `predicted_target == "UP"`, so every validation period is exactly `0.0`, variance is zero, and the
  deflated Sharpe is undefined.

This is **not a defect in the runner and not a defect in the model**. It is the guard behaving as
documented: it refuses to publish a probability of 0.5 for a candidate that never traded, which
would otherwise rank a do-nothing model above every genuinely losing one. The honest research
reading is that this six-feature ridge, with a zero threshold, finds no long setup on INFY over
2024-2025 that survives real statutory costs.

Changing `--score-threshold` would produce a non-degenerate result. **That is a research design
decision, not a bug fix**, and taking it after seeing two failures is precisely the multiplicity
problem this stack exists to account for. It is the founder's call, and it must carry the next
multiplicity ordinal.

Two limitations are stated rather than resolved. The session calendar, absent `--calendar-file`, is
derived from provider data, so a provider that silently omits a trading day yields a calendar
agreeing with its own gap. The default universe is the single requested instrument — content-bound
and honest, but a stated universe, not a point-in-time membership authority, so it does nothing
about survivorship bias.

Full record: `agent_context/work/completed/20260822-claude-real-data-training-runner.md`.
Outstanding work: `agent_context/handoffs/20260822-claude-real-data-training-runner-handoff.md`.

## Open program-level majors

1. Protected remote / CI integration in progress.
2. Legacy Code Craft/Test Craft baseline findings remain even though Ruff and strict Mypy are green.
3. No clean-build or artifact-to-source provenance proof.
4. Product capability claims exceed implemented live-execution behavior.

## Reference development machine

- ASUS Vivobook 14 X1407QA, Windows 11 ARM64.
- Snapdragon X X1-26-100, 8 cores/8 threads, approximately 3.0 GHz.
- 16 GB LPDDR5X-8448 RAM; 512 GB WD NVMe SSD.
- Current QuantOS virtual environment: CPython 3.13.15.

## Next safe actions

1. Clone and sync on the remote development machine using `START_HERE.md`.
2. Proceed with Slice 4 implementation (One Governed Ridge Fold) following `.launch/SLICES.md`.
3. Decide, as a research design decision, whether the `--score-threshold` of the governed ridge
   should remain `0` under `+1/-1` target encoding with an imbalanced base rate. Two trials have
   already been spent; any third carries multiplicity ordinal 3 and must be registered as such. Do
   not sweep thresholds until one produces a publishable Sharpe.
4. Reconcile the stale sections at the top of this file against `.launch/STATE.md` (coordinator).
