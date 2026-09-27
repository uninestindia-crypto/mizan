# Dispatch: worker_m4 (Milestone 4 - Driver, Full Walk-Forward, Adversarial Hardening & Acceptance Report)

**Agent**: worker_m4
**Role**: teamwork_preview_worker
**Working Directory**: D:\quant_system\.agents\teamwork\worker_m4
**Parent**: orchestrator_1 (ef790e51-c69c-48ef-8a68-d5526ac54caf)
**Timestamp**: 2026-09-25T21:15:00+05:30

## MANDATORY
Read:
1. `D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md`
2. `D:\quant_system\.agents\teamwork\PROJECT.md`
3. `D:\quant_system\TEST_INFRA.md`
4. `D:\quant_system\TEST_READY.md`
5. `D:\quant_system\.agents\skills\financial-model-craft\SKILL.md`
6. `D:\quant_system\.agents\skills\quant-model-governance\SKILL.md`
7. `D:\quant_system\.agents\skills\point-in-time-market-data\SKILL.md`

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Owned Files
- `src/quant_system/research_xs_monthly/driver.py`
- `scripts/run_xs_portfolio_alpha.py`
- `reports/xs_portfolio_alpha/ACCEPTANCE_REPORT.md`
- `tests/test_xs_portfolio_alpha/test_m4_integration.py`

## Mission & Tasks
1. Hardening fixes in `src/quant_system/research_xs_monthly/noise_benchmarker.py`:
   - In `evaluate_dsr`: add `if not math.isfinite(candidate_sharpe): return 0.0` to guard against NaN/Inf.
   - In `run_empirical_noise_control`: verify step cadence.
2. Implement `src/quant_system/research_xs_monthly/driver.py` and `scripts/run_xs_portfolio_alpha.py`:
   - Ingest 423-name liquid NSE research universe (`data/authorities/nse-research-universe-liquid-10y.csv`).
   - Load point-in-time daily bars from cache store using `load_cache_bars` (`bars.py`).
   - Enforce development window boundary: `2016-08-22` to `2025-08-13` (warmup = 63 sessions).
   - Strict holdout quarantine: Verify that bars with date >= `2025-08-14` (the final 252 sessions) are strictly excluded from all training, parameter tuning, ranking decisions, and development evaluation.
   - Step through development calendar at weekly interval (every 5 trading sessions):
     * Decision at close $T$: rank universe using `MultiFactorRankingEngine.rank_universe`.
     * Select top quintile (20%, ~84 names).
     * Execution at open $T+1$: rebalance rotating tranche in `StaggeredTrancheLedger` with circuit-lock checks.
     * Record MTM NAV and exposure (confirming <= 1.0000).
     * Evaluate deciles Q1..Q10, Spearman rank IC, and t-statistic via `DecileDiagnosticEngine`.
   - Run baseline and noise controls:
     * CASH baseline (0% return).
     * ALWAYS_TRADE baseline (rebalancing broad market with 0.224% fee).
     * 30-seed pseudo-random NOISE control on identical tranche ledger machinery.
     * Compute Deflated Sharpe Ratio (DSR) using `OverfittingDiagnostics.deflated_sharpe_ratio`.
3. Verify all Acceptance Criteria from `ORIGINAL_REQUEST.md`:
   - Positive net Sharpe ratio after full 0.224% statutory fees.
   - Information Coefficient $t$-statistic $> 2.0$.
   - Factor monotonicity: $Q_1 > Q_{10}$ spread return net of fees.
   - Multiplicity: candidate DSR exceeds median NOISE control at 21-session holding horizon.
   - Zero lookahead: fills at $T+1$ open based strictly on data up to $T$ close.
   - Capital exposure strictly $\le 1.0000$ at all times.
   - Final 252-session holdout quarantined and untouched.
4. Author comprehensive evidence report `reports/xs_portfolio_alpha/ACCEPTANCE_REPORT.md` documenting:
   - Executive summary and strategy architecture.
   - Walk-forward performance statistics (CAGR, Annualized Volatility, Net Sharpe after 0.224% fees, Max Drawdown).
   - Decile returns table Q1..Q10, spread return, Spearman rank IC mean, std, and t-statistic.
   - Multiplicity benchmark comparison table: Candidate vs CASH, ALWAYS_TRADE, and 30-seed NOISE control (median Sharpe, median DSR, candidate DSR).
   - Capital preservation and leverage audit log (maximum observed leverage <= 1.0000).
   - Verification of holdout quarantine (exact dates, session counts, zero access proof).
5. Add integration tests in `tests/test_xs_portfolio_alpha/test_m4_integration.py`.
6. Run full verification:
   - `uv run pytest tests/test_xs_portfolio_alpha/ -v`
   - `uv run ruff check src/ scripts/ tests/test_xs_portfolio_alpha/`
   - `uv run mypy src/ scripts/ tests/test_xs_portfolio_alpha/`
   - `scripts/audit-agent-claims.ps1`
   - `scripts/audit-disk-layout.ps1`
7. Write 5-component handoff report to `D:\quant_system\.agents\teamwork\worker_m4\handoff.md`.
8. Send completion message to orchestrator via `send_message`.
