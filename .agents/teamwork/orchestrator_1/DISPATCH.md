# Dispatch Instructions

## 2026-09-25T15:10:41+05:30

You are the Project Orchestrator for QuantOS.

Your working directory is: D:\quant_system\.agents\teamwork\orchestrator_1
The authoritative user request is recorded at: D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md

Read ORIGINAL_REQUEST.md and the repository rules in AGENTS.md before planning or editing:
1. Follow the required startup sequence from AGENTS.md:
   - Read agent_context/README.md, agent_context/CURRENT.md, agent_context/PROTOCOL.md, and agent_context/DISK-LAYOUT.md.
   - Read .launch/STATE.md and .launch/SLICES.md for authoritative release state.
   - Run git status --short --branch and inspect existing changes.
   - Read every record in agent_context/work/active/.
   - Run git worktree list and git branch --list.
   - Create your own active-work record in agent_context/work/active/ before editing repo files.
2. Maintain your own BRIEFING.md and progress.md inside your working directory: D:\quant_system\.agents\teamwork\orchestrator_1\
3. Coordinate and dispatch specialist subagents to execute the requirements:
   - R1: Multi-Factor Composite Ranking Engine (point-in-time cross-sectional rankings across liquid 423-name NSE universe, momentum 21-63 sessions, mean-reversion dampening 3-5 sessions, idiosyncratic volatility scaling, strictly using data available at decision close T).
   - R2: Staggered Tranche Portfolio Ledger (4-tranche weekly-rebalanced, 21-session holding period, top quintile 15-20%, next-open execution T+1, full 0.224% round-trip statutory fee model, leverage <= 100%).
   - R3: Factor Monotonicity and Long-Short Diagnostic (zero-capital long-short deciles Q1-Q10, Spearman rank IC, spread returns between top/bottom deciles).
   - R4: Multiplicity Accounting and Noise Benchmarking (pre-declared evaluation budget, CASH baseline, ALWAYS_TRADE benchmark, 30-seed pseudo-random NOISE control).
4. Strictly fulfill all Acceptance Criteria (positive net Sharpe > 0 after 0.224% fees, IC t > 2.0, Q1 > Q10 monotonicity, DSR > median NOISE control, zero look-ahead leakage, capital exposure <= 1.0, pytest/ruff/mypy pass, audit-agent-claims and audit-disk-layout pass, final holdout quarantined).
5. When complete, send a message to the Sentinel with your victory claim, summary of changes, and verification evidence.

## 2026-09-25T16:34:38Z

[Message from worker_m4_rep (1beea622-21b1-4702-b089-10e09d110c77)]
Milestone 4 is complete and verified with VERIFIED_PASS across all 7 acceptance criteria:
- Deliverables: driver.py, run_xs_portfolio_alpha.py, ACCEPTANCE_REPORT.md, acceptance_results.json, test_m4_integration.py.
- AC-1: Net Annualized Sharpe = +1.2377 (> 0.0) -> PASS
- AC-2: Spearman Rank IC t-stat = +3.40 (> 2.0) -> PASS
- AC-3: Decile Monotonicity Q1 > Q10 spread = +11.98% -> PASS
- AC-4: Multiplicity DSR = 0.9630 vs 0.0155 median noise -> PASS
- AC-5: Capital Exposure Ceiling = 0.9984 (<= 1.0000) -> PASS
- AC-6: Zero Look-Ahead Next-Open Fill -> VERIFIED PASS
- AC-7: Holdout Partition Quarantine (252 sessions strictly isolated) -> VERIFIED PASS
- 270/270 passed tests, clean ruff, clean mypy, audit-agent-claims PASS, audit-disk-layout PASS.
