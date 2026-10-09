# Sanitized conversation: Candidate Time-Series Foundation Models for Quant OS

DATE: 2026-10-07  
STATUS: Captured; evaluation pool declared by founder for future research  
SOURCE: Founder instruction of October 7, 2026 ("note it we will also test this model also")  
PRIVACY: Sanitized; no credentials or private identifiers retained  

---

## 1. Founder instruction & declared evaluation pool

The founder specified a prioritized shortlist of Time-Series Foundation Models (TSFMs) to evaluate and test for future quantitative forecasting within Quant OS:

| Rank | Model | Why I care about it for Quant OS | Parameters | Realistic hardware for inference | License / production |
|---|---|---|---:|---|---|
| 🥇 | **TimesFM 3.0** | Best general zero-shot forecasting performance I found today; #1 on current FEV-Bench | ~331M | **4–8 GB VRAM workable**, 8–16 GB comfortable; CPU possible but slower* | ⚠️ Local weights non-commercial |
| 🥈 | **Chronos-2** | Best combination of accuracy + efficiency + commercial usability | 120M | CPU works; **2–4 GB VRAM workable**, 8 GB plenty* | ✅ Apache 2.0 |
| 🥉 | **Granite PatchTST-FM-r2** | Very strong permissively licensed zero-shot model | ~385M | **4–8 GB VRAM workable**, 8–16 GB for long contexts* | ✅ Commercial-friendly |
| 4 | **TiRex-2** | Excellent for streaming/multivariate/covariates; extremely efficient | 38.4M active + 44.1M multivariate | CPU or **~4 GB VRAM**; CUDA requires Ampere+ | ✅ Apache 2.0 |
| 5 | **Toto 2.0 1B/2.5B** | Excellent large forecasting model; multivariate | 1B / 2.5B | 1B: ~8–12 GB; **2.5B: 16 GB min-ish, 24 GB comfortable*** | ✅ Apache 2.0 |
| ⭐ Finance | **Moirai-2.0-small** | Especially interesting because it performed very well in the direct 2026 stock-return study | **11.4M** | CPU easily; <2 GB VRAM easily | ⚠️ CC BY-NC |
| Heavy | **Timer-S1** | Big MoE model; interesting research model but unnecessary for your first Quant OS | 8.3B total / 0.75B active | **40 GB+ VRAM officially recommended** | ✅ Apache 2.0 |

---

## 2. Platform alignment & hardware analysis

### A. Factory-New Laptop Standard (Edge / Local Inference)
Quant OS enforces the **Factory-New Laptop Standard** (`AGENTS.md`): the system must be capable of running self-contained on standard client laptops without dedicated high-end GPU workstations.
- **Top Local Tier**:
  - **Moirai-2.0-small (11.4M)**: Extremely lightweight. Runs on standard laptop CPU with < 2 GB RAM/VRAM. Ideal for local edge screening or real-time feature generation.
  - **TiRex-2 (38.4M/44.1M)**: Very fast and compact. Operates on CPU or light GPU (~4 GB VRAM). Note requirement: CUDA requires Ampere+ when GPU acceleration is targeted.
  - **Chronos-2 (120M)**: Best balance of accuracy and efficiency. Can run on local CPU or light GPU (2–4 GB VRAM).
- **Intermediate / Developer Rig Tier**:
  - **TimesFM 3.0 (~331M)** & **Granite PatchTST-FM-r2 (~385M)**: Require 4–8 GB VRAM. Workable on modest GPUs, though CPU inference will be significantly slower.
- **Cloud-Only / Heavy Tier**:
  - **Toto 2.0 (1B / 2.5B)**: Requires 8–24 GB VRAM.
  - **Timer-S1 (8.3B MoE)**: Demands 40 GB+ VRAM. Unsuited for desktop packaging; strictly cloud/container research.

### B. Licensing and Production Distribution Viability
- **Production-Ready & Commercial-Friendly**:
  - **Chronos-2** (`Apache 2.0`)
  - **Granite PatchTST-FM-r2** (Permissive / Commercial-friendly)
  - **TiRex-2** (`Apache 2.0`)
  - **Toto 2.0** (`Apache 2.0`)
  - **Timer-S1** (`Apache 2.0`)
- **Research-Only / Non-Commercial Constraints**:
  - **TimesFM 3.0**: Local model weights carry non-commercial restrictions (`⚠️ Non-commercial`). (Note: TimesFM 2.5-200m was Apache 2.0, whereas 3.0 local weights require careful licensing adherence).
  - **Moirai-2.0-small**: Released under `CC BY-NC 4.0` (`⚠️ Non-commercial`). Useful for research benchmarks, but cannot be distributed in a commercial binary without licensing arrangements.

---

## 3. Governance and Scientific Trial Protocol

Per Quant OS laws (`agent_context/GOAL.md` Tripwire 3, `CURRENT.md`, and `reports/short_horizon/TRIAL-LEDGER.md`):
1. **Candidate Pool vs. Active Trial**: Listing these models records them as prospective research candidates. It does **not** declare an active trial and does **not** spend an evaluation multiplicity ordinal.
2. **Prior Declaration Required**: Before executing any backtest or forward paper test with any candidate model:
   - A formal, dated trial declaration must be frozen (e.g. `reports/<trial_name>/TRIAL-LEDGER.md`).
   - The trial budget and ordinal index must be locked prior to observing out-of-sample data.
   - The test must use point-in-time NSE features, next-bar executable opens, and statutory trading costs (0.224% round trip).
   - Deflated Sharpe Ratio (DSR) must be deflated against the cumulative count of all historical trials.
