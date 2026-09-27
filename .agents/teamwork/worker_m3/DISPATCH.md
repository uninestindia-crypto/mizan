# Dispatch: worker_m3 (Milestone 3 - R3 Decile Monotonicity & R4 Multiplicity Noise Benchmarking)

**Agent**: worker_m3
**Role**: teamwork_preview_worker
**Working Directory**: D:\quant_system\.agents\teamwork\worker_m3
**Parent**: orchestrator_1 (ef790e51-c69c-48ef-8a68-d5526ac54caf)
**Timestamp**: 2026-09-25T20:58:00+05:30

## MANDATORY
Read:
1. `D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md`
2. `D:\quant_system\.agents\teamwork\PROJECT.md`
3. `D:\quant_system\.agents\skills\quant-model-governance\SKILL.md`
4. `D:\quant_system\.agents\skills\financial-model-craft\SKILL.md`

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Owned Files
- `src/quant_system/research_xs_monthly/diagnostics.py`
- `src/quant_system/research_xs_monthly/noise_benchmarker.py`
- `tests/test_xs_portfolio_alpha/test_diagnostics.py`
- `tests/test_xs_portfolio_alpha/test_multiplicity_noise.py`
- `reports/xs_portfolio_alpha/TRIAL-LEDGER.md`

## Mission & Tasks
1. Implement `src/quant_system/research_xs_monthly/diagnostics.py` (R3):
   - Expose `DecileResults`, `ICSummary`, and `DecileDiagnosticEngine`.
   - `evaluate_deciles(ranked_symbols: list[RankedSymbol], forward_returns: dict[str, Decimal]) -> DecileResults`:
     * Partition into 10 disjoint deciles Q1 (top) to Q10 (bottom) (~42 names each for 423 universe).
     * Calculate average return per decile.
     * Calculate top-bottom spread: `decile_returns[1] - decile_returns[10]`.
     * Check monotonicity: `decile_returns[1] > decile_returns[10]`.
   - `spearman_rank_ic(scores: list[float], forward_returns: list[float]) -> float`:
     * Cross-sectional Spearman rank correlation using exact rank ordering with average ranks on ties.
   - `aggregate_ic(ic_series: list[float]) -> tuple[float, float, float]`:
     * Returns `(mean_ic, std_ic, t_statistic)` where `t_stat = mean_ic / (std_ic / sqrt(N))`.
2. Implement `src/quant_system/research_xs_monthly/noise_benchmarker.py` (R4):
   - Expose `NoiseBenchmarkResults`, `MultiplicityNoiseBenchmarker`, and `require_declared_trials`.
   - Trial ledger budget: read and enforce `reports/xs_portfolio_alpha/TRIAL-LEDGER.md`.
   - CASH baseline: return 0.0 Sharpe ratio.
   - ALWAYS_TRADE baseline: equal-weighted portfolio rebalanced across all universe names paying 0.224% statutory fees.
   - 30-seed pseudo-random NOISE control:
     * Seeds 1..30 generating standard Gaussian random cross-sectional rankings.
     * Evaluates through the identical `StaggeredTrancheLedger` machinery.
     * Returns list of 30 Sharpes, median noise Sharpe, and distribution parameters.
   - Deflated Sharpe Ratio (DSR):
     * Integrate with `from quant_system.analytics.multiplicity import OverfittingDiagnostics`.
     * Compute candidate DSR vs median NOISE control over 21-session horizon.
     * Require candidate DSR > median NOISE control DSR.
3. Create `reports/xs_portfolio_alpha/TRIAL-LEDGER.md` declaring the evaluation budget.
4. Implement comprehensive unit tests:
   - `tests/test_xs_portfolio_alpha/test_diagnostics.py`
   - `tests/test_xs_portfolio_alpha/test_multiplicity_noise.py`
5. Verification:
   - `uv run pytest tests/test_xs_portfolio_alpha/ -v`
   - `uv run ruff check src/quant_system/research_xs_monthly/ tests/test_xs_portfolio_alpha/`
   - `uv run mypy src/quant_system/research_xs_monthly/ tests/test_xs_portfolio_alpha/`
   - `scripts/audit-agent-claims.ps1`
   - `scripts/audit-disk-layout.ps1`
6. Write 5-component handoff report to `D:\quant_system\.agents\teamwork\worker_m3\handoff.md`.
7. Report completion to orchestrator via `send_message`.
