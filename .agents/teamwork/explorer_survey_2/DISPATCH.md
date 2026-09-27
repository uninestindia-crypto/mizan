# Explorer Survey 2 Dispatch Note
Assigned to explorer_survey_2.

## 2026-09-25T09:42:22Z
You are explorer_survey_2.
Your working directory is: D:\quant_system\.agents\teamwork\explorer_survey_2

MANDATORY: You MUST read D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md before doing anything else.

Relevant skills to read/use:
- D:\quant_system\.agents\skills\point-in-time-market-data\SKILL.md
- D:\quant_system\.agents\skills\financial-model-craft\SKILL.md
- D:\quant_system\.agents\skills\nse-execution-craft\SKILL.md

Tasks:
1. Investigate R1 (Multi-Factor Composite Ranking Engine):
   - Search the codebase for existing cross-sectional implementations, screening scripts, or factor models (look at `research_xs_monthly`, `screens`, `20260903-hermes-xs-monthly-screen-new.md`, `strategies/`, `modeling/`).
   - Determine how to compute point-in-time cross-sectional rankings at decision close T:
     * Intermediate-term momentum (21-63 sessions return)
     * Short-term mean-reversion dampening (3-5 sessions return, subtracted/dampened)
     * Idiosyncratic volatility scaling (e.g. residual volatility from market beta or return volatility scaling)
     * Zero look-ahead leakage guarantee: strictly using data available at decision close T.
2. Investigate R2 (Staggered Tranche Portfolio Ledger):
   - Determine how to construct and maintain a 4-tranche weekly-rebalanced portfolio ledger (each tranche held 21 trading sessions).
   - Top quintile selection (15-20% of liquid universe, ~63-85 names).
   - Next-open execution (T+1) fill pricing and accounting.
   - 0.224% round-trip statutory fee model (check existing fee implementation in `src/quant_system/`).
   - Capital preservation invariant: total portfolio leverage strictly <= 100% (e.g. each tranche 25% max).
3. Architecture & Interface Proposal:
   - Propose exact modular architecture, classes, interfaces, and file paths.
4. Report:
   - Write your complete findings to `D:\quant_system\.agents\teamwork\explorer_survey_2\report.md`.
   - Use send_message to report completion to the orchestrator.
