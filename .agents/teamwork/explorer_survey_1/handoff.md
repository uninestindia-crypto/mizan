# Handoff Report: Phase 1 Survey (explorer_survey_1)

**Filer**: explorer_survey_1  
**Working Directory**: `D:\quant_system\.agents\teamwork\explorer_survey_1`  
**Date**: 2026-09-25  
**Type**: Hard Handoff  

---

## 1. Observation

1. **Git Status & HEAD**:
   - `git status --short --branch` showed `## main...origin/main [ahead 3]`.
   - `git rev-parse HEAD` returned `c270017b3b6a9d8130ad57d157886985ca4f70d5`.
   - Two external registered worktrees observed: `feature-real-journey-api-ac47d7c-20260824-102717` and `feature-release-manifest-integrity-b084d72-20260824-111030`.
2. **Active Work Record Staked**:
   - `agent_context/work/active/20260925-1510Z-orchestrator-xs-portfolio-alpha.md` created with status `ACTIVE`, owning:
     `src/quant_system/research_xs_monthly/`, `src/quant_system/portfolio/`, `tests/test_xs_portfolio_alpha.py`, `scripts/run_xs_portfolio_alpha.py`, `reports/xs_portfolio_alpha/`.
   - `scripts/audit-agent-claims.ps1` returned:
     `RESULT: PASS - every workspace has a visible claim and every claim resolves.`
   - `scripts/audit-disk-layout.ps1` returned:
     `RESULT: PASS - no stray QuantOS directories.`
3. **Research Universe**:
   - `data/authorities/nse-research-universe-liquid-10y.csv` has 432 lines. Lines 1–7 are `#` comments, line 8 is header `Symbol,ISIN Code,InstrumentKey,YearsActive,MedianDailyTurnoverINR`, lines 9–431 are 423 data records. Line 432 is a trailing newline.
   - Header includes explicit survivorship bias disclosure: active listings only; positive results are weak evidence, negative results are strong.
4. **Market Data Storage & Bar Loader**:
   - Store path: `data/evidence/market-cache/all-market-20160822-20260821/store/`.
   - Loader: `load_cache_bars` in `src/quant_system/research_xs_monthly/bars.py`.
   - 3,322 datasets scanned; all 423 universe symbols loaded; 0 symbols missing; 1,037,813 bars loaded; 0 invalid bars; 2,476 exchange trading sessions.
5. **Corporate Actions Ground Truth**:
   - `src/quant_system/data/corporate_actions.py` lines 10–23 notes that 212 of 212 structural splits/bonuses are already back-adjusted in provider bars.
   - Demergers have no published ratios; gap-based ratio inference is prohibited (leads to +71% fake moves on NMDC).
   - Unpriced demergers in portfolios (e.g. HEG spinning off unpriced HEGGRAPHITE per `data/authorities/nse-demerger-entitlements.json`) must be marked `unpriced` and excluded from equity calculation rather than zeroed.
6. **Chronological Partition Policy**:
   - Total calendar sessions: 2,476 (from `2016-08-22` to `2026-08-21`).
   - Quarantined Final Holdout: Exactly 252 sessions from `2025-08-14` to `2026-08-21` (`cal[-252]` to `cal[-1]`).
   - Development Period: 2,224 sessions from `2016-08-22` to `2025-08-13`.
   - Warmup Period: 63 sessions (`2016-08-22` to `2016-11-21`) for intermediate momentum and volatility calculation.

---

## 2. Logic Chain

1. From **Observation 1 & 2**:
   Under `AGENTS.md` and `agent_context/PROTOCOL.md` Section 8, any active project must declare an active work record before modifying files. Creating `20260925-1510Z-orchestrator-xs-portfolio-alpha.md` with explicit owned paths and non-goals satisfies this requirement and prevents workspace collision. Both claim and disk audits passing proves workspace governance compliance.
2. From **Observation 3 & 4**:
   The 423 names in `nse-research-universe-liquid-10y.csv` are 100% covered by the 10-year market cache `all-market-20160822-20260821/store`. The existing `load_cache_bars` function in `src/quant_system/research_xs_monthly/bars.py` correctly parses all 1,037,813 bars as `Decimal` across 2,476 sessions with zero missing symbols and zero invalid rows. Thus, this loader serves as the validated data ingestion interface for cross-sectional ranking.
3. From **Observation 5**:
   Because the provider already back-adjusts splits/bonuses, raw bars should not have published structural ratios re-applied. Because demergers cannot be inferred from price gaps, any holding undergoing an unpriced demerger must be treated fail-closed: disclosed at cost, excluded from NAV marks, and routed to an unresolved bucket on exit without crediting fake cash proceeds.
4. From **Observation 6**:
   QuantOS governance mandates strict temporal separation. Slicing off the final 252 sessions (`2025-08-14` to `2026-08-21`) prior to factor evaluation guarantees zero look-ahead bias and protects the holdout from p-hacking. The remaining 2,224 sessions (`2016-08-22` to `2025-08-13`) provide ample sample size (~8.8 years, >100 monthly rebalance periods) for walk-forward validation and tranche ledger simulation.

---

## 3. Caveats

1. **Survivorship Bias**: As disclosed in `nse-research-universe-liquid-10y.csv`, the universe contains currently active listings only. Companies that delisted during 2016–2026 are absent from this historical cache. Any positive performance findings must be interpreted with this favourable bias in mind.
2. **Dividends**: The paper ledger does not credit real-time cash dividends. Calculations evaluate capital appreciation net of statutory execution costs (0.224% round trip).
3. **SME/PCA Exclusions**: The 423-name universe strictly excludes SME series and surveillance stocks; findings apply to this liquid institutional universe only.

---

## 4. Conclusion

The repository environment and data infrastructure are fully surveyed, validated, and ready for Phase 2 (Architecture & Implementation):
- Active claim is active and passing audits.
- Universe of 423 liquid names is complete and verified against the 10-year store (1,037,813 bars, 2,476 sessions).
- Corporate action handling rules (splits already adjusted, demergers excluded/unpriced) are verified.
- The 252-session holdout partition (`2025-08-14` to `2026-08-21`) is identified and quarantined.

---

## 5. Verification Method

To independently verify the survey findings:
1. **Agent Claim & Disk Layout Audits**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
   powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
   ```
   Both must exit with code 0.
2. **Universe Verification**:
   Inspect line count and header of `data/authorities/nse-research-universe-liquid-10y.csv`:
   - Non-comment lines = 424 (1 header + 423 data rows).
3. **Market Cache Ingestion & Calendar Verification**:
   Run:
   ```powershell
   uv run python -c "from pathlib import Path; from quant_system.research_xs_monthly.bars import load_cache_bars, read_universe_symbols; from quant_system.research_xs_monthly.screen import build_calendar; u = read_universe_symbols(Path('data/authorities/nse-research-universe-liquid-10y.csv')); bars, _ = load_cache_bars(Path('data/evidence/market-cache/all-market-20160822-20260821/store'), symbols=set(u[:5])); cal = build_calendar(bars); print('Sessions:', len(cal), 'Start:', cal[0], 'End:', cal[-1], 'Holdout boundary:', cal[-252])"
   ```
   Must output: `Sessions: 2476 Start: 2016-08-22 End: 2026-08-21 Holdout boundary: 2025-08-14`.
