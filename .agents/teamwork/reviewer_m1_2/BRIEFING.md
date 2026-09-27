# BRIEFING — 2026-09-25T10:11:45Z

## Mission
Objectively and adversarially review the mathematical soundness of factor calculations in `src/quant_system/research_xs_monthly/ranking.py`.

## 🔒 My Identity
- Archetype: reviewer_critic
- Roles: reviewer, critic
- Working directory: D:\quant_system\.agents\teamwork\reviewer_m1_2
- Original parent: ef790e51-c69c-48ef-8a68-d5526ac54caf
- Milestone: M1
- Instance: 2 of 2

## 🔒 Key Constraints
- Review-only — do NOT modify implementation code
- Objective and adversarial review of factor calculations in src/quant_system/research_xs_monthly/ranking.py
- Verify edge cases, run pytest, ruff, mypy verification commands
- Issue clear verdict: APPROVE or REQUEST_CHANGES

## Current Parent
- Conversation ID: ef790e51-c69c-48ef-8a68-d5526ac54caf
- Updated: not yet

## Review Scope
- **Files to review**: `src/quant_system/research_xs_monthly/ranking.py`, `tests/test_xs_portfolio_alpha/test_ranking_engine.py`
- **Interface contracts**: `PROJECT.md` § Interface Contracts 2
- **Review criteria**: Mathematical soundness (intermediate momentum 21-63 sessions, short reversion dampening 3-5 sessions, idio-vol scaling via CAPM regression against market return, deterministic tie-breaking by symbol name), edge cases (zero division, NaN, empty arrays, insufficient history <63 bars), code quality, test verification.

## Key Decisions Made
- Executed unit tests (`pytest`), linter (`ruff`), and static typing (`mypy`). All baseline tests passed.
- Conducted adversarial mathematical stress-testing. Discovered 2 Critical and 2 Major defects in factor calculation logic.
- Formulated verdict: `REQUEST_CHANGES`.

## Artifact Index
- D:\quant_system\.agents\teamwork\reviewer_m1_2\DISPATCH.md — Recorded dispatch message
- D:\quant_system\.agents\teamwork\reviewer_m1_2\BRIEFING.md — Working memory
- D:\quant_system\.agents\teamwork\reviewer_m1_2\progress.md — Liveness heartbeat
- D:\quant_system\.agents\teamwork\reviewer_m1_2\handoff.md — Final review and handoff report

## Review Checklist
- **Items reviewed**:
  - `src/quant_system/research_xs_monthly/ranking.py`
  - `tests/test_xs_portfolio_alpha/test_ranking_engine.py`
  - `worker_m1/handoff.md`
- **Verdict**: REQUEST_CHANGES
- **Unverified claims**:
  - Worker claimed: "In full universe ranking via `rank_universe`, the equal-weighted universe market return is computed across all eligible constituents and used for true CAPM residual volatility." -> INVALIDATED: In mixed-history universes where any symbol has 63 bars, CAPM regression is silently aborted for all symbols with >=64 bars due to array length mismatch (62 vs 63).

## Attack Surface
- **Hypotheses tested**:
  - H1: Behavior under universe with mixed bar counts (e.g. 63 bars vs 64+ bars). Result: FAILED (CAPM regression silently bypassed for all >=64 bar symbols).
  - H2: Behavior under `lag > 0` with insufficient history. Result: FAILED (clamping `idx_start = 0` calculates truncated window rather than failing closed with `None`).
  - H3: Behavior under NaN / non-finite prices. Result: FAILED (NaN poisons universe mean/std, producing all-NaN z-scores and non-deterministic Timsort).
  - H4: Calendar date alignment across symbols. Result: FAILED (offset-based slicing assumes identical trading calendar without date verification).
- **Vulnerabilities found**:
  - V1 (Critical): Silent CAPM regression bypass on length mismatch ($62 \ne 63$).
  - V2 (Critical): Window truncation and silent `idx_start = 0` clamping violating fail-closed invariant.
  - V3 (Major): Unhandled NaN / non-finite floats corrupting cross-sectional standardization.
  - V4 (Moderate): Unchecked calendar date alignment in equal-weighted market return series.
- **Untested angles**: Full 10-year Upstox dataset cache ingestion (store datasets not present in local test tree).
