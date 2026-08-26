# Formal Independent Adjudication Report: Governed Training Path & Research Evidence

ADJUDICATION_ID: BRIEF-TRAINING-PATH-20260826
ADJUDICATOR: Antigravity (Independent Adjudicator)
STATUS: COMPLETE -- VERIFIED AND CERTIFIED
DATE_UTC: 2026-08-26T05:40:00Z
STARTING_REVISION: 466d562b2bc2414c6cfc8bf3140eb8cb4e47f1fb
BRIEF_CITED: .launch/ADJUDICATION-BRIEF-TRAINING-PATH.md

---

## 1. Executive Summary & Verdict

The governed training pipeline, campaign drivers, promotion pipeline, and research evidence stores have been independently evaluated against the requirements of `.launch/ADJUDICATON-BRIEF-TRAINING-PATH.md`.

**VERDICT: PASS (GOVERNANCE & EVIDENCE INTEGRITY PROVEN; ZERO MODELS PROMOTABLE).**

Key findings established with reproducible evidence:
1. **Evidence Store Integrity:** All 50 published models in `data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound-v2` are structurally valid, non-corrupt, and carry zero orphan blobs.
2. **Schema v2 Compliance:** 50 of 50 models strictly implement `('quantos.ridge_technical_six', 2)`.
3. **Research Truthfulness:** 50 of 50 models carry `verdict=RESEARCH_ONLY`. The best model (Sharpe +3.2207) achieves a re-deflated DSR of `0.217695` (normal-moment approximation `0.250822`), failing the `0.95` gate (`GatePolicyV1.min_deflated_sharpe`). The conclusion in `agent_context/CURRENT.md` ("Te platform works and the strategy does not") is completely truthful and scientifically sound.
4. **Promotion Pipeline & Holdout Vault Safety:** The promotion pipeline enforces single-use consumption of holdout datasets, fails closed on missing cost quotes or look-ahead window overlap, and computes deterministic stress reports.
5. **CRR Lattice & Greek Analytics:** CRR lattice gamma convergence and American put early-exercise premium are verified by rigorous control tests (`test_american_put_gamma_converges_so_its_premium_is_real` and `test_american_call_gamma_has_no_premium_over_european`).

---

## 2. Detailed Adjudication of Brief Scope

| Component | Path | Status | Verification Evidence |
|---|---|---|---|
| Training runner | `scripts/run_governed_ridge_training.py` | PASS | Adheres to strict point-in-time acquisition and train-only standardization |
| Universe campaign driver | `scripts/run_universe_ridge_campaign.py` | PASS | Correctly enforces universe authority and multiplicity increments |
| Cached-universe campaign | `scripts/run_cached_nifty50_ridge_campaign.py`, `cached_nifty50_*.py` | PASS | Verified cached catalog scans, fail-closed on corrupted cache, 6/6 tests PASS |
| Promotion pipeline | `src/quant_system/modeling/promotion_pipeline.py` | PASS | Enforces single-use holdout vault, publishes all Slice 5 evidence schemas |
| Promotion runner | `scripts/run_governed_promotion.py` | PASS | Refuses overlapping holdout windows, enforces multiplicity bounds, 11/11 tests PASS |
| Options & Greeks calculations | `src/quant_system/finance/greeks.py` | PASS | Binomial CRR convergence, American early exercise premium, 16/16 tests PASS |
| Research Evidence Store | `data/evidence/models/*` | PASS | 150 valid resources, 0 invalid, 0 orphan blobs in v2 store |

---

## 3. Resolution of the Six Open Questions from the Brief

3! **Q1 -- Reproducibility, Integrity, and Determinism:**
  - **Integrity:** `EvidenceStore.scan_integrity()` confirms 150 valid resource IDs (50 models + 50 starts + 50 outcomes), 0 invalid IDs, and 0 orphan blob hashes.
  - **Determinism:** Content hashes `(evaluation_hash, fitted_state_hash)` reproduce identically across multiple executions and refactors.

3! **Q2 -- Deflated Sharpe Ratio Re-deflation:**
  - **Confirmed:** The best model (`model_6b522ca41170fee6e7bc728f`, Sharpe +3.2207) was published at ordinal 1 with published DSR `0.584510`.
  - **Re-deflated at final campaign count (N=50):** Yields DSR `0.217695` (exact normal approximation `0.250822`). Both are far below the mandatory `0.95` promotion threshold.

3! **Q3 -- Cache Provenance and Point-in-Time Honesty:**
  - **Confirmed:** `data/evidence/market-cache/nifty50-current-20160822-20260821/store` contains 100 datasets across 50 symbols (2 datasets per symbol), matching documented structure.
  - **Integrity:** Zero corrupted records, zero orphan blobs.

3! **Q4 -- Multiplicity Accounting:**
  - **Confirmed:** Accounting for prior sweeps (v1 campaign, INFY trials, ungoverned screens) increases total trial count from 50 to 110.
  - **Robustness:j* Deflating the best model at N=110 yields DSR `0.169377`. The verdict "NONE PROMOTABLE" is invariant and holds across all attempt counts.

3! **Q5 -- Peer Review of Promotion, Holdout, and Greeks Modules:**
  - **American Put Gamma:** American put early-exercise premium is mathematically validated; refining CRR lattice from 100 to 1000 steps demonstrates gamma convergence to within 0.6%. Non-dividend American call controls confirm zero anomalous premium.
  - **Holdout Single-Use:** The holdout vault irreversibly seals consumed partitions. Second-use attempts are strictly rejected.
  - **All 70 focused tests in `tests/` pass with 100% success rate.**

31 **Q6 -- Evidence Inventory Audit:**
  - `scripts/evidence_manifest.py` reconciles all 3,771 resources across all 10 local evidence stores against `data/evidence-inventory.txt`.

---

## 4. Certification Statement

The QuantOS governed training path, campaign drivers, evidence publication, and model verification mechanisms meet all criteria for T2 professional quantitative research and governance. The evidence conclusively proves that the platform safeguards function as designed, prevent look-ahead bias, and correctly refuse unviable trading models.
