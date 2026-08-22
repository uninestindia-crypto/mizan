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

Status by stage, measured at `d5b21b8` plus the uncommitted dotenv fix:

| Stage | Status | Evidence |
|---|---|---|
| 1. Real Upstox acquisition | **PROVEN** | Returned **498 real daily bars** for `NSE_EQ\|INE009A01021` (INFY), 2024-01-01..2025-12-31 |
| 2. Session calendar | PROVEN on the provider-derived path | 498 sessions derived from the exchange dates actually returned |
| 3. Governed re-acquisition | NOT REACHED | blocked below |
| 4. `build_feature_dataset` | **NOT RUN on real data** | fixtures only |
| 5. `build_label_dataset` | **NOT RUN on real data** | fixtures only |
| 6. `build_purged_fold` | **NOT RUN on real data** | fixtures only |
| 7. `run_persisted_ridge_trial` | **NOT RUN on real data** | fixtures only |

**No model has been trained on real data.** No trial evidence has been published. Anyone citing this
runner as proof that the governed stack works end to end is citing stages that have never executed.

**Current blocker: no corporate-actions authority document exists in this repository.**
`build_feature_dataset` binds every feature row to a corporate-action authority hash. The runner
exits 2 with `CONFIGURATION REFUSED` rather than emit a placeholder digest for a document that does
not exist. Note that the governed code itself only checks the hash is 64 hex — it would accept an
invented one. The refusal is the runner's own guard, and it is deliberate: see
`.launch/reports/quarantine/README.md` for what fabricated evidence has already cost this project.

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
3. Supply a real NSE corporate-actions document covering the requested range, then re-run
   `scripts/run_governed_ridge_training.py` with `--corporate-actions-file <path>` to take the
   governed stack past stage 3 on real data for the first time. Do not satisfy that flag with an
   invented file.
4. Reconcile the stale sections at the top of this file against `.launch/STATE.md` (coordinator).
