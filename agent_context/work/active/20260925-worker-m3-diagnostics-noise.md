# Active work: worker_m3 - R3 Decile Monotonicity & R4 Multiplicity Noise Benchmarking

STATUS: COMPLETED  
OWNER: worker_m3  
TOOL: Antigravity  
STARTED_UTC: 2026-09-25T15:30:00Z  
COMPLETED_UTC: 2026-09-25T15:35:00Z  
STARTING_REVISION: c270017b3b6a9d8130ad57d157886985ca4f70d5  
WORKTREE_OR_BRANCH: D:\quant_system on `main` (shared checkout, disjoint paths with written claims)  

## Objective

Implement Milestone 3 deliverables for XS Portfolio Alpha system:
1. `src/quant_system/research_xs_monthly/diagnostics.py` (R3):
   - Expose `DecileResults`, `ICSummary`, and `DecileDiagnosticEngine`.
   - `evaluate_deciles`: Partition into 10 disjoint deciles Q1 (top) to Q10 (bottom) (~42 names each for 423 universe). Calculate decile returns, top-bottom spread (`Q1 - Q10`), and monotonicity (`Q1 > Q10`).
   - `spearman_rank_ic`: Cross-sectional Spearman rank correlation between factor composite scores and realized forward returns.
   - `aggregate_ic`: Compute mean IC, std IC, and Student's t-statistic (`t_stat = mean_ic / (std_ic / sqrt(N))`). Verify t > 2.0.
2. `src/quant_system/research_xs_monthly/noise_benchmarker.py` (R4):
   - Expose `NoiseBenchmarkResults`, `MultiplicityNoiseBenchmarker`, and `require_declared_trials`.
   - Trial ledger budget: read and enforce `reports/xs_portfolio_alpha/TRIAL-LEDGER.md`.
   - CASH baseline: return 0.0 Sharpe ratio.
   - ALWAYS_TRADE baseline: broad market baseline rebalancing all names paying 0.224% round-trip statutory fee.
   - 30-seed pseudo-random NOISE control:
     * Seeds 1..30 generating standard Gaussian random cross-sectional rankings.
     * Evaluates through the identical `StaggeredTrancheLedger` machinery.
     * Computes Sharpe ratio for each seed at 21-session holding horizon, along with distribution median.
   - Deflated Sharpe Ratio (DSR):
     * Integrate with `from quant_system.analytics.multiplicity import OverfittingDiagnostics`.
     * Compute candidate DSR vs median NOISE control over 21-session horizon.
     * Verify candidate DSR > median NOISE control DSR.
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

## Owned paths

- `src/quant_system/research_xs_monthly/diagnostics.py`
- `src/quant_system/research_xs_monthly/noise_benchmarker.py`
- `tests/test_xs_portfolio_alpha/test_diagnostics.py`
- `tests/test_xs_portfolio_alpha/test_multiplicity_noise.py`
- `reports/xs_portfolio_alpha/TRIAL-LEDGER.md`
- `tests/test_xs_portfolio_alpha/test_e2e_acceptance.py` (QA typing fix for bridge imports)
- `agent_context/work/active/20260925-worker-m3-diagnostics-noise.md`

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run pytest tests/test_xs_portfolio_alpha/ -v` | PASS | 229 passed in 2.03s |
| `uv run ruff check src/quant_system/research_xs_monthly/ tests/test_xs_portfolio_alpha/` | PASS | All checks passed! |
| `uv run mypy src/quant_system/research_xs_monthly/ tests/test_xs_portfolio_alpha/` | PASS | Success: no issues found in 18 source files |
| `powershell scripts/audit-agent-claims.ps1` | PASS | Exit 0 |
| `powershell scripts/audit-disk-layout.ps1` | PASS | Exit 0 |

## Files changed

- `src/quant_system/research_xs_monthly/diagnostics.py`: Implemented `DecileResults`, `ICSummary`, `DecileDiagnosticEngine` with decile evaluation, Spearman rank IC, and t-statistic aggregation.
- `src/quant_system/research_xs_monthly/noise_benchmarker.py`: Implemented `NoiseBenchmarkResults`, `MultiplicityNoiseBenchmarker`, `require_declared_trials`, CASH baseline, ALWAYS_TRADE baseline, 30-seed NOISE control, and DSR calculation.
- `reports/xs_portfolio_alpha/TRIAL-LEDGER.md`: Pre-declared evaluation budget of 5 candidate trials and non-candidate controls.
- `tests/test_xs_portfolio_alpha/test_diagnostics.py`: Comprehensive test suite for R3 diagnostics (16 unit tests).
- `tests/test_xs_portfolio_alpha/test_multiplicity_noise.py`: Comprehensive test suite for R4 noise benchmarking (15 unit tests).
- `tests/test_xs_portfolio_alpha/test_e2e_acceptance.py`: Updated fallback bridge imports to use importlib dynamic resolution and removed unused type ignore comment.

## Blockers and conflicts

None.

## Stop point

All R3 and R4 requirements implemented, tested, and verified against all criteria.
