# Dispatch: worker_m4_rep (Milestone 4 Replacement - Driver, Walk-Forward & Acceptance Report)

**Agent**: worker_m4_rep
**Role**: teamwork_preview_worker
**Working Directory**: D:\quant_system\.agents\teamwork\worker_m4_rep
**Parent**: orchestrator_1 (ef790e51-c69c-48ef-8a68-d5526ac54caf)
**Timestamp**: 2026-09-25T21:35:00+05:30

## MANDATORY
Read:
1. `D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md`
2. `D:\quant_system\.agents\teamwork\PROJECT.md`
3. `D:\quant_system\TEST_INFRA.md`
4. `D:\quant_system\TEST_READY.md`
5. `D:\quant_system\.agents\skills\financial-model-craft\SKILL.md`
6. `D:\quant_system\.agents\skills\quant-model-governance\SKILL.md`
7. `D:\quant_system\.agents\skills\point-in-time-market-data\SKILL.md`
8. `D:\quant_system\.agents\teamwork\worker_m4\progress.md` (interruption point: `noise_benchmarker.py` hardening completed, cache surveyed)

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Owned Files
- `src/quant_system/research_xs_monthly/driver.py`
- `scripts/run_xs_portfolio_alpha.py`
- `reports/xs_portfolio_alpha/ACCEPTANCE_REPORT.md`
- `tests/test_xs_portfolio_alpha/test_m4_integration.py`

## Interruption Point & Remaining Tasks
Predecessor `worker_m4` completed the hardening fixes in `noise_benchmarker.py`. Your job is to finish Milestone 4:
1. Implement `src/quant_system/research_xs_monthly/driver.py`:
   - Load universe from `data/authorities/nse-research-universe-liquid-10y.csv` (423 symbols).
   - Load bars from `data/evidence/market-cache/all-market-20160822-20260821/store` using `load_cache_bars` (`bars.py`).
   - Partitioning:
     * Warmup: first 63 sessions (2016-08-22 to 2016-11-21).
     * Development window: 2016-08-22 to 2025-08-13 (2,224 sessions).
     * Quarantined Holdout: 2025-08-14 to 2026-08-21 (exactly 252 sessions).
     * Fail closed if any bar with date >= 2025-08-14 is accessed during development run.
   - Simulation engine:
     * Weekly rebalance every 5 sessions through the development calendar.
     * At decision close $T$: rank universe using `MultiFactorRankingEngine.rank_universe`.
     * Select top quintile (20%, ~84 names).
     * At open $T+1$: rebalance rotating tranche in `StaggeredTrancheLedger` with circuit-lock checks.
     * Record MTM NAV and exposure (confirming <= 1.0000).
     * Deciles & IC: record forward decile returns Q1..Q10 and rank IC via `DecileDiagnosticEngine`.
   - Run Baselines:
     * CASH baseline (0% return).
     * ALWAYS_TRADE baseline (rebalancing broad market paying 0.224% fee).
     * 30-seed NOISE control on identical tranche ledger machinery.
     * Compute Deflated Sharpe Ratio (DSR) using `OverfittingDiagnostics.deflated_sharpe_ratio`.
   - Return structured results object.
2. Implement CLI script `scripts/run_xs_portfolio_alpha.py`:
   - Runs simulation and prints summary table.
   - Saves authoritative evidence report to `reports/xs_portfolio_alpha/ACCEPTANCE_REPORT.md`.
3. Verify all Acceptance Criteria from `ORIGINAL_REQUEST.md`:
   - Positive net Sharpe ratio after full 0.224% statutory fees.
   - Information Coefficient $t$-statistic $> 2.0$.
   - Factor monotonicity: $Q_1 > Q_{10}$ spread return net of fees.
   - Multiplicity: candidate DSR exceeds median NOISE control at 21-session holding horizon.
   - Zero lookahead: fills at $T+1$ open based strictly on data up to $T$ close.
   - Capital exposure strictly $\le 1.0000$ at all times.
   - Final 252-session holdout quarantined and untouched.
4. Author `reports/xs_portfolio_alpha/ACCEPTANCE_REPORT.md`.
5. Implement unit/integration tests in `tests/test_xs_portfolio_alpha/test_m4_integration.py`.
6. Run full verification:
   - `uv run pytest tests/test_xs_portfolio_alpha/ -v`
   - `uv run ruff check src/ scripts/ tests/test_xs_portfolio_alpha/`
   - `uv run mypy src/ scripts/ tests/test_xs_portfolio_alpha/`
   - `scripts/audit-agent-claims.ps1`
   - `scripts/audit-disk-layout.ps1`
7. Write 5-component handoff report to `D:\quant_system\.agents\teamwork\worker_m4_rep\handoff.md`.
8. Report completion via `send_message`.
