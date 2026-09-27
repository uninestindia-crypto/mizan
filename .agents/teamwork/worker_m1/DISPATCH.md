## 2026-09-25T09:57:23Z
You are worker_m1.
Your working directory is: D:\quant_system\.agents\teamwork\worker_m1

MANDATORY: You MUST read D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md before doing anything else.
Read D:\quant_system\.agents\teamwork\PROJECT.md for architecture, interfaces, and code layout.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Relevant skills & references:
- D:\quant_system\.agents\skills\point-in-time-market-data\SKILL.md
- D:\quant_system\.agents\skills\financial-model-craft\SKILL.md
- D:\quant_system\.agents\teamwork\explorer_survey_2\report.md (contains exact mathematical formulas, rolling CAPM beta/idio-vol kernel prototype, and benchmark performance)

Owned files:
- `src/quant_system/research_xs_monthly/ranking.py`
- `tests/test_xs_portfolio_alpha/test_ranking_engine.py`

Tasks:
1. Implement `src/quant_system/research_xs_monthly/ranking.py`:
   - Point-in-time calculation at decision close T (zero look-ahead, only bars with exchange date <= T).
   - Intermediate momentum: 21 to 63 session return ($R_{21..63}$).
   - Short-term mean-reversion dampening: 3 to 5 session return ($R_{3..5}$).
   - Idiosyncratic volatility scaling: 63-session residual volatility relative to universe equal-weighted market return.
   - Composite factor scoring: normalize/standardize components and combine: e.g. Score = (z(mom) - 0.5 * z(rev)) / idio_vol (or robust z-score equivalent proven in explorer_survey_2).
   - Rank universe descending by composite score with deterministic tie-breaking (lexicographic by symbol name).
   - Expose clean typed dataclasses: `FactorComponents`, `RankedSymbol`, and `MultiFactorRankingEngine`.
2. Implement unit tests in `tests/test_xs_portfolio_alpha/test_ranking_engine.py` verifying:
   - Intermediate momentum calculation against known values.
   - Mean-reversion dampening calculation and effect.
   - Idiosyncratic volatility computation and positive scaling.
   - Strict point-in-time isolation (future bars are rejected or inaccessible).
   - Deterministic tie-breaking by symbol.
   - Handling of missing/insufficient history fail-closed.
3. Run test and lint verification:
   - `uv run pytest tests/test_xs_portfolio_alpha/test_ranking_engine.py -v`
   - `uv run ruff check src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`
   - `uv run mypy src/quant_system/research_xs_monthly/ranking.py tests/test_xs_portfolio_alpha/test_ranking_engine.py`
4. Write your 5-component handoff report to `D:\quant_system\.agents\teamwork\worker_m1\handoff.md`.
5. Report completion to the orchestrator via send_message.
