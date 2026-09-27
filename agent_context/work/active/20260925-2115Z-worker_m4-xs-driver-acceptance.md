# Active work: Milestone 4 XS Portfolio Alpha Driver, Adversarial Hardening & Acceptance Report

STATUS: ACTIVE  
OWNER: worker_m4 (teamwork subagent)  
TOOL: Antigravity  
STARTED_UTC: 2026-09-25T15:45:00Z  
STARTING_REVISION: c270017b3b6a9d8130ad57d157886985ca4f70d5  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, disjoint paths with written claims)

## Objective

Implement the end-to-end execution driver, CLI script, adversarial hardening fixes, integration tests, and authoritative acceptance report for the QuantOS Multi-Factor Cross-Sectional Ranking Alpha System across the liquid 423-name NSE research universe.

Core deliverables:
1. Apply hardening fixes to `src/quant_system/research_xs_monthly/noise_benchmarker.py`.
2. Implement end-to-end driver in `src/quant_system/research_xs_monthly/driver.py` and CLI script in `scripts/run_xs_portfolio_alpha.py`.
3. Verify all Acceptance Criteria (Net Sharpe > 0 after 0.224% fees, IC t > 2.0, Decile Monotonicity Q1 > Q10, Multiplicity DSR > median NOISE, Zero lookahead, Exposure <= 1.0, 252-session holdout quarantined).
4. Author authoritative report in `reports/xs_portfolio_alpha/ACCEPTANCE_REPORT.md`.
5. Implement integration tests in `tests/test_xs_portfolio_alpha/test_m4_integration.py`.

## Owned paths

- `src/quant_system/research_xs_monthly/driver.py`
- `scripts/run_xs_portfolio_alpha.py`
- `reports/xs_portfolio_alpha/ACCEPTANCE_REPORT.md`
- `tests/test_xs_portfolio_alpha/test_m4_integration.py`
- `src/quant_system/research_xs_monthly/noise_benchmarker.py`
- `agent_context/work/active/20260925-2115Z-worker_m4-xs-driver-acceptance.md`

## Non-goals

- No modification of immutable authorities under `data/authorities/`.
- No modification of market data cache stores under `data/evidence/`.
- No touching or accessing final 252-session holdout (`date >= 2025-08-14`) during training, parameter tuning, ranking decisions, or development evaluation.
- No live-money order routing (T4 strictly excluded).
- No editing files owned by other agents outside the XS portfolio alpha scope.

## Plan

1. Create active work claim and establish teamwork briefing and heartbeat. (DONE)
2. Apply hardening fixes to `src/quant_system/research_xs_monthly/noise_benchmarker.py`.
3. Survey existing modules (`bars.py`, `ranking.py`, `tranche_ledger.py`, `diagnostics.py`, `noise_benchmarker.py`).
4. Implement `src/quant_system/research_xs_monthly/driver.py` and `scripts/run_xs_portfolio_alpha.py`.
5. Run walk-forward simulation on development window (`2016-08-22` to `2025-08-13`).
6. Generate `reports/xs_portfolio_alpha/ACCEPTANCE_REPORT.md`.
7. Implement integration tests in `tests/test_xs_portfolio_alpha/test_m4_integration.py`.
8. Run full test suite, ruff, mypy, and audit scripts.
9. Deliver handoff report and notify parent orchestrator.

## Current step

Setting up workspace briefing and applying hardening fixes in `noise_benchmarker.py`.

## Decision rationale

- Follow strictly the interface contracts defined in `PROJECT.md` and `TEST_INFRA.md`.
- Ensure zero look-ahead: decisions at $T$ close, executions strictly at $T+1$ open.
- Ensure strict Decimal arithmetic for capital, NAV, fees (0.00112 entry + 0.00112 exit), and exposure tracking <= 1.0000.
- Holdout partition (2025-08-14 to 2026-08-21, 252 sessions) is quarantined and must never be touched during development evaluation.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch` | PASS | On main ahead of origin/main by 3 |
| `git worktree list` | PASS | Worktrees checked and respected |

## Files changed

- `agent_context/work/active/20260925-2115Z-worker_m4-xs-driver-acceptance.md`: Active work record created

## Blockers and conflicts

None.

## Stop point

Work record created; ready to implement hardening fixes and driver.

## Next safe action

Inspect and apply hardening fixes to `noise_benchmarker.py`.
