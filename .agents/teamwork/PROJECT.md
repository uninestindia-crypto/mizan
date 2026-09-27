# Project: QuantOS Multi-Factor Cross-Sectional Ranking Alpha System

## Architecture
The system transitions QuantOS from single-name directional modeling to an investable, cost-surviving multi-instrument cross-sectional portfolio alpha system across the 423-name liquid NSE research universe (`data/authorities/nse-research-universe-liquid-10y.csv`).

```
                              [10-Year Market Cache Store]
                                         │
                                         ▼
                      [Cross-Sectional Point-in-Time Bar Loader]
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
     [R1 Multi-Factor Ranking Engine]              [R3 Decile Monotonicity Diagnostic]
     - Intermediate Momentum (21-63d)              - Decile Partitions Q1..Q10
     - Mean-Reversion Dampening (3-5d)             - Spearman Rank IC & t-stat (t > 2.0)
     - Idio-Vol Scaling (63d CAPM)                 - Long-Short Spread (Q1 - Q10)
     - Deterministic Tie-Breaking                                │
                 │                                               ▼
                 ▼                                 [R4 Multiplicity & Noise Control]
     [R2 Staggered Tranche Ledger]                 - Pre-declared Evaluation Budget
     - 4 Autonomous Sub-Ledgers                    - CASH & ALWAYS_TRADE Baselines
     - Weekly Rebalance (5 sessions)               - 30-Seed Pseudo-Random NOISE Control
     - 21-Session Holding Period                   - Deflated Sharpe Ratio (DSR > median noise)
     - Top Quintile Selection (15-20%)
     - Next-Open (T+1) Execution
     - 0.224% Statutory Fee Model
     - Max Leverage <= 100.0%
                 │
                 ▼
     [Portfolio P&L & Acceptance Gate]
     - Sharpe > 0 after 0.224% friction
     - Final 252-Session Holdout Quarantined
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Liquid Universe & Cache Ingestion | Ingest 423 names from authority file, load 10-year cache, handle provider splits and demerger exclusions | M1 | Survey (E1) |
| 2 | Intermediate-Term Momentum | Compute 21-63 session rolling return at decision close T | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Short-Term Reversion Dampening | Compute 3-5 session return and subtract/dampen from momentum | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Idiosyncratic Volatility Scaling | Compute residual volatility relative to market return over 63 sessions and scale composite score | M1 | ORIGINAL_REQUEST §R1 |
| 5 | PIT Composite Factor Ranking | Combine momentum, dampening, and idio-vol into composite score with deterministic symbol tie-breaking | M1 | ORIGINAL_REQUEST §R1 |
| 6 | 4-Tranche Weekly Ledger | Maintain 4 autonomous weekly tranches, each held 21 sessions, rebalanced every 5 sessions | M2 | ORIGINAL_REQUEST §R2 |
| 7 | Top Quintile Selection | Select top 15-20% (~80 names) of ranked eligible universe per tranche | M2 | ORIGINAL_REQUEST §R2 |
| 8 | Next-Open Execution (T+1) | Fill orders at session T+1 open price, checking circuit locks (volume > 0, high != low) | M2 | ORIGINAL_REQUEST §R2 |
| 9 | Statutory Fee Accounting | Apply full 0.224% round-trip statutory fee model (0.00112 entry, 0.00112 exit) using Decimal math | M2 | ORIGINAL_REQUEST §R2 |
| 10 | Leverage & Capital Invariant | Enforce and mathematically guarantee total capital exposure <= 1.0000 across all 4 tranches | M2 | ORIGINAL_REQUEST §R2 |
| 11 | Decile Portfolios Q1..Q10 | Construct 10 disjoint decile portfolios (~42 names each) across universe at each rebalance | M3 | ORIGINAL_REQUEST §R3 |
| 12 | Spearman Rank IC & t-stat | Compute cross-sectional rank IC between factor scores and 21d forward returns; verify mean IC > 0 and t > 2.0 | M3 | ORIGINAL_REQUEST §R3 |
| 13 | Monotonicity & Long-Short Spread | Verify annualized return Q1 > Q10 and compute zero-capital dollar-neutral spread returns | M3 | ORIGINAL_REQUEST §R3 |
| 14 | Pre-declared Evaluation Budget | Declare trial count in TRIAL-LEDGER.md and enforce via require_declared_trials runtime check | M3 | ORIGINAL_REQUEST §R4 |
| 15 | CASH & ALWAYS_TRADE Benchmarks | Benchmark candidate against CASH (0% return) and ALWAYS_TRADE (rebalance all names paying 0.224% fee) | M3 | ORIGINAL_REQUEST §R4 |
| 16 | 30-Seed NOISE Control | Run 30 pseudo-random Gaussian noise ranking controls through identical tranche and rebalance ledger | M3 | ORIGINAL_REQUEST §R4 |
| 17 | Deflated Sharpe Ratio (DSR) | Calculate DSR across non-overlapping periods; verify candidate DSR exceeds median NOISE control | M3 | ORIGINAL_REQUEST §R4 |
| 18 | Chronological Holdout Quarantine | Strictly quarantine final 252 sessions (2025-08-14 to 2026-08-21); tune strictly on development window | M4 | ORIGINAL_REQUEST §Criteria |
| 19 | Opaque-Box E2E Test Suite | 4-tier requirement-driven E2E test suite covering all features, boundary conditions, combinations, and application scenarios | M_TEST | Dual Track Architecture |
| 20 | Adversarial Hardening (Tier 5) | White-box stress testing, property-based tests, and fault injection | M4 | Final Milestone |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M_TEST | E2E Testing Track | Design & implement 4-tier requirement-driven test suite; publish TEST_READY.md | none | DONE (105 tests passing) |
| M1 | Multi-Factor Composite Ranking Engine | Features 1–5: Point-in-time multi-factor scoring (momentum, reversion dampening, idio-vol scaling) across 423 names | none | DONE (gate passed) |
| M2 | Staggered Tranche Portfolio Ledger | Features 6–10: 4-tranche weekly-rebalanced ledger, 21-session hold, top quintile, T+1 open execution, 0.224% fees, leverage <= 1.0 | M1 | DONE (gate passed, 35 unit + 15 empirical tests) |
| M3 | Monotonicity, Multiplicity & Noise Benchmarking | Features 11–17: Deciles Q1..Q10, Spearman IC t > 2.0, Q1 > Q10 spread, trial budget, CASH, ALWAYS_TRADE, 30-seed NOISE, DSR | M1, M2 | DONE (gate passed, 31 unit + 35 empirical tests) |
| M4 | Final Milestone: E2E Verification & Adversarial Hardening | Features 18, 20: 100% E2E test pass, adversarial coverage hardening, full acceptance criteria verification, holdout quarantine verification | M_TEST, M3 | DONE (gate passed, 270 full tests pass, ACCEPTANCE_REPORT verified) |

## Interface Contracts

### 1. Market Data Loader ↔ Ranking Engine & Ledger
- Module: `src/quant_system/research_xs_monthly/bars.py`
- Functions:
  * `read_universe_symbols(authority_path: Path) -> list[str]`
  * `load_cache_bars(store_path: Path, symbols: set[str] | None = None) -> tuple[dict[str, list[PointInTimeBar]], list[str]]`
  * `build_calendar(bars_by_symbol: dict[str, list[PointInTimeBar]]) -> list[date]`

### 2. Multi-Factor Ranking Engine ↔ Portfolio Ledger & Diagnostics
- Module: `src/quant_system/research_xs_monthly/ranking.py`
- Class: `MultiFactorRankingEngine`
- Methods:
  * `compute_factor_components(symbol: str, as_of_date: date, bars: list[PointInTimeBar]) -> FactorComponents`:
    - `intermediate_momentum_21_63: float`
    - `short_reversion_3_5: float`
    - `idiosyncratic_volatility_63: float`
    - `composite_score: float`
  * `rank_universe(as_of_date: date, eligible_symbols: list[str], bars_by_symbol: dict[str, list[PointInTimeBar]]) -> list[RankedSymbol]`:
    - Sorts descending by `composite_score`, ties broken lexicographically by `symbol`.
    - Returns list of `RankedSymbol(symbol, rank, score, components)`.

### 3. Staggered Tranche Ledger ↔ Execution & Reporting
- Module: `src/quant_system/research_xs_monthly/tranche_ledger.py`
- Classes:
  * `Tranche(tranche_id: int, allocation_capital: Decimal, entry_date: date, exit_date: date, positions: dict[str, TranchePosition], cash: Decimal)`
  * `StaggeredTrancheLedger`:
    - `rebalance_tranche(tranche_id: int, decision_date: date, execution_date: date, selected_symbols: list[str], open_prices: dict[str, Decimal]) -> TrancheRebalanceResult`
    - `mark_to_market(as_of_date: date, current_prices: dict[str, Decimal]) -> LedgerNAV`
    - `total_exposure() -> Decimal` (strictly `<= Decimal("1.0000")`)
    - `total_statutory_fees() -> Decimal`

### 4. Diagnostics & Multiplicity Benchmark ↔ Evaluation Store
- Module: `src/quant_system/research_xs_monthly/diagnostics.py`
- Classes:
  * `DecileDiagnosticEngine`:
    - `evaluate_deciles(ranked_symbols: list[RankedSymbol], forward_returns: dict[str, Decimal]) -> DecileResults`
    - `spearman_rank_ic(scores: list[float], forward_returns: list[float]) -> float`
    - `aggregate_ic(ic_series: list[float]) -> tuple[float, float, float]` (`mean_ic`, `std_ic`, `t_statistic`)
  * `MultiplicityNoiseBenchmarker`:
    - `run_30_seed_noise_control(universe: list[str], calendar: list[date], bars_by_symbol: dict[str, list[PointInTimeBar]]) -> NoiseBenchmarkResults`
    - `evaluate_dsr(candidate_returns: list[float], benchmark_returns: list[float], num_trials: int) -> float`

## Code Layout
- `src/quant_system/research_xs_monthly/`:
  * `bars.py`: Market data ingestion & cache loader
  * `ranking.py`: R1 Multi-Factor Composite Ranking Engine
  * `tranche_ledger.py`: R2 4-Tranche Weekly-Rebalanced Ledger & Next-Open Execution
  * `diagnostics.py`: R3 Decile Monotonicity, Rank IC & Spread Analysis
  * `noise_benchmarker.py`: R4 CASH, ALWAYS_TRADE, 30-seed NOISE & DSR
  * `driver.py`: End-to-end execution driver
- `tests/test_xs_portfolio_alpha/`:
  * `test_ranking_engine.py`: Unit tests for R1 momentum, mean-reversion, idio-vol, and ranking
  * `test_tranche_ledger.py`: Unit tests for R2 tranches, rebalance, execution, 0.224% fees, leverage <= 1.0
  * `test_diagnostics.py`: Unit tests for R3 deciles, rank IC, t-stat, and monotonicity
  * `test_multiplicity_noise.py`: Unit tests for R4 budget enforcement, baselines, NOISE control, DSR
  * `test_e2e_acceptance.py`: Full opaque-box E2E acceptance tests verifying all criteria
- `scripts/`:
  * `run_xs_portfolio_alpha.py`: CLI driver producing complete research report and evidence artifacts
- `reports/xs_portfolio_alpha/`:
  * `TRIAL-LEDGER.md`: Pre-declared evaluation budget
  * `ACCEPTANCE_REPORT.md`: Authoritative statistical and financial verification evidence
