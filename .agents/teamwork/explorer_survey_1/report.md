# Universe & Market Data Survey Report: Cross-Sectional Monthly Portfolio Alpha System

**Explorer**: explorer_survey_1  
**Working Directory**: `D:\quant_system\.agents\teamwork\explorer_survey_1`  
**Date**: 2026-09-25  
**Starting Revision**: `c270017b3b6a9d8130ad57d157886985ca4f70d5`  
**Status**: COMPLETE  

---

## 1. Executive Summary

This survey establishes the empirical, structural, and governance foundations for the Cross-Sectional Monthly Portfolio Alpha project as specified in `ORIGINAL_REQUEST.md`. 

Key survey findings:
1. **Startup & Governance Claims**: Active work claim record `agent_context/work/active/20260925-1510Z-orchestrator-xs-portfolio-alpha.md` has been created and verified. Both `scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1` pass clean (exit code 0).
2. **Research Universe**: `data/authorities/nse-research-universe-liquid-10y.csv` contains exactly **423 liquid symbols** meeting strict filters (>= 9.5 years active, median daily turnover >= Rs 5 crore, SME & PCA excluded).
3. **Market Data & Storage**: The 10-year store at `data/evidence/market-cache/all-market-20160822-20260821/store` contains all 423 universe symbols across **2,476 exchange trading sessions** (2016-08-22 to 2026-08-21), with 1,037,813 parsed bars, 0 invalid bars, and 0 missing universe symbols.
4. **Corporate Actions Policy**: Provider bars labeled `RAW` are already back-adjusted by Upstox for splits/bonuses (212 of 212 structural actions show ~1.0 ex-date ratio). Applying published split ratios results in catastrophic double adjustment (+945% fake moves). Demergers publish no ratios and cannot be sized from price gaps; unpriced demergers must remain `UNRESOLVED` or marked `UNPRICED` and excluded from equity calculations rather than zeroed.
5. **Chronological Partition Policy**: 
   - **Quarantined Final Holdout**: Exactly 252 sessions (`2025-08-14` to `2026-08-21`), strictly untouched during development and tuning.
   - **Development Period**: Exactly 2,224 sessions (`2016-08-22` to `2025-08-13`).
   - **Warmup Period**: 63 sessions (`2016-08-22` to `2016-11-21`) for intermediate momentum and volatility lookbacks.

---

## 2. Startup Sequence & Workspace Claim Verification

### 2.1 Git Status & Workspace Verification
- **Branch**: `main` (tracking `origin/main [ahead 3]`).
- **Current HEAD**: `c270017b3b6a9d8130ad57d157886985ca4f70d5`.
- **Existing Registered Worktrees**:
  - `D:/quant_system` (main)
  - `D:/quant_system_workspaces/worktrees/feature-real-journey-api-ac47d7c-20260824-102717` (`codex/real-journey-api`)
  - `D:/quant_system_workspaces/worktrees/feature-release-manifest-integrity-b084d72-20260824-111030` (`codex/release-manifest-integrity`)
- **Existing Work & Untracked Files**:
  Existing uncommitted files in `data/evidence/market-cache/` and `reports/short_horizon/` belong to other active agents and were verified as untouched and uncommitted.

### 2.2 Active Work Record Created
In strict accordance with `AGENTS.md` and `agent_context/PROTOCOL.md` Section 8, the active work claim record was staked before any project edits:
- **Record Path**: `agent_context/work/active/20260925-1510Z-orchestrator-xs-portfolio-alpha.md`
- **Owner**: Teamwork Orchestrator & Agents (XS Portfolio Alpha Project)
- **Worktree/Branch**: `D:\quant_system` on `main` (shared checkout, disjoint paths)
- **Owned Paths**:
  - `src/quant_system/research_xs_monthly/`
  - `src/quant_system/portfolio/`
  - `tests/test_xs_portfolio_alpha.py`
  - `scripts/run_xs_portfolio_alpha.py`
  - `reports/xs_portfolio_alpha/`
  - `agent_context/work/active/20260925-1510Z-orchestrator-xs-portfolio-alpha.md`
- **Explicit Non-Goals**:
  - No live-money order routing (T4 excluded by QuantOS product law).
  - No editing, moving, deleting, staging, or reformatting files owned by other active claims (e.g. Antigravity paper-trade claim `20260826-antigravity-paper-trade-live-market-testing.md`, `scripts/run_paper_pilot_session.py`, `scripts/serve_live_dashboard.py`, `src/quant_system/execution/paper_pilot.py`, `src/quant_system/server/app.py`).
  - No touching money paths under dispute/notices: `src/quant_system/execution/paper_portfolio.py`, `src/quant_system/risk/governor.py`.
  - No touching existing immutable evidence stores, authorities, or the quarantined holdout partition.

### 2.3 Automated Governance Audits
- **Agent Claims Audit**: `powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1`  
  **Result**: `PASS - every workspace has a visible claim and every claim resolves.`
- **Disk Layout Audit**: `powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1`  
  **Result**: `PASS - no stray QuantOS directories.` Canonical roots `D:\quant_system` and `D:\quant_system_workspaces` clean.

---

## 3. Universe Survey: `nse-research-universe-liquid-10y.csv`

### 3.1 Universe File Structure
- **Path**: `data/authorities/nse-research-universe-liquid-10y.csv`
- **Total Lines**: 432 lines
  - Lines 1–7: Comment header describing criteria and survivorship bias warning
  - Line 8: Header row (`Symbol,ISIN Code,InstrumentKey,YearsActive,MedianDailyTurnoverINR`)
  - Lines 9–431: Exactly **423 data records**
  - Line 432: Trailing newline
- **Columns**:
  | Column | Data Type | Example | Description |
  |---|---|---|---|
  | `Symbol` | string | `3MINDIA` | NSE trading ticker symbol |
  | `ISIN Code` | string | `INE470A01017` | International Securities Identification Number |
  | `InstrumentKey` | string | `NSE_EQ\|INE470A01017` | Upstox/NSE instrument key |
  | `YearsActive` | float/Decimal | `10.00` | Years active in the 10-year historical cache (minimum 9.50) |
  | `MedianDailyTurnoverINR` | int/int64 | `66297555` | Median daily turnover in INR (minimum Rs 5,00,00,000 / 5 crore) |

### 3.2 Universe Filtering Criteria
The universe was constructed via `scripts/build_research_universe.py` applying three non-negotiable filters:
1. **History Length**: Active for `>= 9.5 years` over the 10-year period (2016-08-22 to 2026-08-21).
2. **Liquidity / Turnover**: Median daily turnover `>= INR 5,00,00,000` (5 crore) to support the 0.224% round-trip statutory fee model without market-impact invalidation.
3. **Surveillance & Micro-Cap Exclusions**: SME platform names (`SM` series) and Promoters/Corporate Action Surveillance (`PCA`) strictly excluded.

### 3.3 Survivorship Bias Governance Notice
As documented in the file header:
> *"SURVIVORSHIP BIAS: the source universe is ACTIVE listings only, so companies that delisted or failed inside the window are absent. This cannot be corrected from this cache. Read results asymmetrically: a positive result is weak evidence because the bias pushes that way; a negative result is strong because the bias favoured the strategy and it still failed."*

---

## 4. Market Data Storage & Loading Infrastructure

### 4.1 Storage Layout & Cache Stores
Market data in QuantOS is stored under `data/evidence/market-cache/`:
- Primary Store: `data/evidence/market-cache/all-market-20160822-20260821/store/`
  - Contains content-addressed datasets in `datasets/dset_<hex_id>/manifest.json`.
  - Manifests reference compressed JSONL blobs in `blobs/<relative_path>.jsonl.gz`.
  - Each line is a JSON object: `{"symbol": "...", "exchange_date": "YYYY-MM-DD", "open": "...", "high": "...", "low": "...", "close": "...", "volume": ...}`.

### 4.2 Bar Loader Mechanics (`src/quant_system/research_xs_monthly/bars.py`)
- **Functions**:
  - `read_universe_symbols(universe_csv: Path) -> list[str]`: Reads and dedupes symbols from CSV, ignoring `#` comment lines.
  - `load_cache_bars(cache_store: Path, symbols: set[str] | None = None) -> tuple[dict[str, list[Bar]], dict[str, int]]`:
    - Scans `datasets/dset_*` manifests.
    - Decodes gzip JSONL blobs.
    - Parses prices strictly as `Decimal` (zero/negative prices rejected).
    - Preserves first bar on duplicate dates (never forward-fills or imputes).
    - Returns `{symbol: [Bar, ... sorted by date]}`.
- **Empirical Loading Verification**:
  - Universe symbols requested: 423
  - Universe symbols loaded: **423**
  - Universe symbols missing: **0**
  - Total bars loaded: **1,037,813**
  - Invalid bars: **0**
  - Duplicate date entries handled: 111,425

---

## 5. Corporate Actions Handling & Policies

### 5.1 Provider Bar Ground Truth vs. Misconceptions
Historical investigation documented in `agent_context/CURRENT.md` and `src/quant_system/data/corporate_actions.py` resolved a critical pitfall:
- **Misconception**: Provider bars with manifest status `RAW` require applying all published splits and bonuses.
- **Empirical Fact**: Measured across all 423 names in the research universe, **212 of 212 structural splits and bonuses are already back-adjusted by Upstox** (largest `|ln(ex-date gap)|` is 0.1035).
- **Consequence**: Applying published ratios on top doubles the adjustment. For example, applying TATASTEEL's 10:1 split turned a +4.6% day into a fake **+945%** day.
- **Rule**: "Measure, not assume" (`src/quant_system/data/corporate_actions.py`). Ex-date gaps are scored in log-return space against two hypotheses:
  1. Provider already applied it (`ln(gap) ~ 0`)
  2. Provider did not apply it (`ln(gap) ~ ln(published_factor)`)
  Nearest hypothesis wins if within `MAX_LOG_RESIDUAL = 0.15`.

### 5.2 Ratio-Less Demergers & Sizing Policy
- NSE publishes demergers without ratios (e.g. `Scheme Of Demerger`).
- Sizing a demerger from the price gap is **strictly prohibited**: it would infer upward jumps on NMDC (+71.0%), BAJAJELEC (+32.2%), and SCI (+30.0%), manufacturing artificial returns.
- Ratio-less demergers lacking independent external verification (`nse-validated-demerger-factors.json`) remain **`UNRESOLVED`**.
- Downstream feature and label windows spanning unresolved demergers are **dropped/refused** rather than publishing fabricated returns.

### 5.3 Unpriced Entitlements in Portfolio Ledgers
- Documented in `agent_context/work/active/20260914-NOTICE-xs-entitlement-wired-under-hermes-claim.md`:
  When a held constituent undergoes an unpriced demerger (e.g. HEG on 2026-09-07 spinning off HEGGRAPHITE), the book **declines to value** what it cannot prove.
  - The position is flagged `unpriced: true` with reason `ENTITLEMENT_UNPRICED`.
  - Its entry cost is disclosed separately.
  - The leg is **excluded from equity/NAV calculations rather than zeroed or recorded as an artificial loss**.
  - On maturity, it routes to `unresolved` positions rather than releasing fabricated cash.

### 5.4 Dividends & Total Return vs. Price Return
- Cash dividends cause the stock price to drop on the ex-date.
- Total return adjustments add back dividends via `(P - D) / P`.
- Note: Live and paper trading accounts do not automatically credit dividends in cash without settlement lag. For strategy validation, the pricing basis must be explicit and fee-aware.

---

## 6. Chronological Holdout Partition Policy

### 6.1 Calendar Boundaries
Scanning the 10-year store (`all-market-20160822-20260821`) yields **2,476 exchange trading sessions**:
- **Calendar Start**: `2016-08-22`
- **Calendar End**: `2026-08-21`

### 6.2 Partition Breakdown
| Partition | Number of Sessions | Date Range | Purpose / Policy |
|---|---|---|---|
| **Warmup Period** | 63 sessions | `2016-08-22` to `2016-11-21` | Feature warmup for intermediate-term momentum (21–63d) and idiosyncratic volatility lookbacks. |
| **Development Period** | 2,224 sessions | `2016-08-22` to `2025-08-13` | Subdivided into Train and Validation for factor tuning, rank aggregation, and tranche ledger simulation. |
| **Quarantined Final Holdout** | **252 sessions** | **`2025-08-14` to `2026-08-21`** | **STRICTLY QUARANTINED.** Exactly 1 trading year. Untouched during development, tuning, and evaluation budget allocation. |

### 6.3 Quarantine Invariants & Anti-Leakage Rules
1. **Pre-Declaration**: The holdout boundary (`cal[-252]` = `2025-08-14`) must be sliced off **before** any ranking, feature standardisation, or portfolio tranche simulation is run (`split_holdout` pattern).
2. **Untouched Guarantee**: The holdout partition must never be handed to factor search, cross-sectional ranking grids, or threshold tuning.
3. **Single-Use Execution**: Once a model/strategy candidate is frozen with all parameters fixed, holdout evaluation is performed exactly once, reporting deflated Sharpe and multiplicity penalties.

---

## 7. Architectural Requirements for Next Phases

Based on the survey findings and `ORIGINAL_REQUEST.md`, Phase 2 (Architecture & Implementation) must satisfy:

1. **Multi-Factor Composite Ranking Engine (`R1`)**:
   - Intermediate momentum: 21–63 session close-to-close returns.
   - Short-term reversal dampener: 3–5 session return dampening to penalize over-extended moves.
   - Idiosyncratic volatility scaling: scale raw momentum by trailing 21–63 session residual/daily volatility.
   - Point-in-time calculation at decision close T (using data available at or before T).
2. **Staggered 4-Tranche Weekly-Rebalanced Portfolio Ledger (`R2`)**:
   - 4 independent tranches (each holding 25% of capital).
   - Rebalance one tranche every 5 sessions (weekly cadence); each tranche held for 21 sessions.
   - Next-session open execution (T+1) at actual executable opens.
   - Deduct 0.224% round-trip statutory transaction costs (STT, exchange fees, SEBI charges, stamp duty, GST).
   - Enforce invariant: Total capital exposure `sum(weights) <= 1.0` at all timestamps.
3. **Decile Monotonicity & Diagnostics (`R3`)**:
   - Zero-capital long-short decile diagnostic (Q1 top quintile/decile down to Q10 bottom decile).
   - Cross-sectional Spearman rank Information Coefficient (IC) computed at each rebalance.
   - Target acceptance criteria: Mean IC positive with `t > 2.0`, Q1 annualized return > Q10 return.
4. **Multiplicity Accounting & Benchmarks (`R4`)**:
   - Pre-declared validation evaluation budget.
   - Benchmarking against:
     - `CASH` / No-trade baseline (0% return, 0 risk).
     - `ALWAYS_TRADE` broad market equal-weight benchmark.
     - 30-seed pseudo-random NOISE control distribution.
   - Target acceptance criteria: Strategy deflated Sharpe ratio exceeds median of the 30-seed NOISE control.

---

## 8. Verification & Audit Trail

| Verification Item | Command / Source | Observed Outcome |
|---|---|---|
| Active Work Claim | `scripts/audit-agent-claims.ps1` | `RESULT: PASS - every workspace has a visible claim and every claim resolves.` |
| Disk Layout Law | `scripts/audit-disk-layout.ps1` | `RESULT: PASS - no stray QuantOS directories.` |
| Universe Row Count | `data/authorities/nse-research-universe-liquid-10y.csv` | Exactly 423 data rows (lines 9 to 431). |
| 10y Market Data Store | `load_cache_bars` over `all-market-20160822-20260821/store` | 423/423 symbols, 1,037,813 bars, 2,476 trading sessions. |
| Calendar Boundaries | `cal[0]` to `cal[-1]`, `cal[-252]` | 2016-08-22 to 2026-08-21; Holdout starts 2025-08-14. |
