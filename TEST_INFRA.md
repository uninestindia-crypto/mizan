# Test Infrastructure Specification: Cross-Sectional Portfolio Alpha System

## 1. Test Philosophy

The testing framework for the Cross-Sectional Portfolio Alpha System adheres to an **opaque-box, requirement-driven testing methodology** derived directly from `ORIGINAL_REQUEST.md` and `PROJECT.md`. The suite treats the underlying components as black/opaque boxes, testing through interface contracts, input domains, invariants, and economic observables without coupling to private implementation state.

### Testing Methodologies Applied:
1. **Category-Partition Testing**: Input spaces (universe eligibility, return series, tranche states, fee components, volatility profiles) are partitioned into exhaustive equivalence classes.
2. **Boundary Value Analysis (BVA)**: Critical limits are rigorously probed:
   - Tranche leverage ceiling: `0.0`, `0.5`, `0.9999`, `1.0000`, and `> 1.0000` (fail-closed).
   - Universe size: `0` (empty), `1` (single name), `5` (below quintile), `20` (quintile boundaries), `423` (full liquid authority).
   - Top quintile selection: exactly `15%`, `20%`, rounding boundaries (`ceil` vs `floor`), and tie cases.
   - Execution timing: decision close $T$, order generation post-close, execution fill at $T+1$ open.
   - Circuit-locked boundary states: `volume == 0`, `high == low` (circuit limit hit), zero variance.
3. **Pairwise / Combinatorial Testing**: Combinations of momentum regimes (positive, negative, zero), mean-reversion dampening shocks (strong, neutral, opposite sign), and idiosyncratic volatility (calm, elevated, outlier) tested against market volatility regimes.
4. **Real-World Scenarios (End-to-End Acceptance)**: Full lifecycle execution across multi-session holding periods evaluating:
   - Net Sharpe ratio after deducting 0.224% statutory fees.
   - Spearman rank IC significance ($t > 2.0$).
   - Decile monotonicity ($Q_1$ annualized return $> Q_{10}$ annualized return).
   - Multiplicity control: Deflated Sharpe Ratio (DSR) exceeding median of 30 pseudo-random noise trials.
   - Strict quarantine of the final 252-session holdout partition.

---

## 2. Feature Inventory & Tier Mapping

Features defined in `PROJECT.md` are mapped across four operational test tiers:

| Feature # | Feature Name | Primary Tier | Description & Verification Focus |
|---|---|---|---|
| **F1** | Liquid Universe & Cache Ingestion | Tier 1, Tier 2 | 423-name universe ingestion, missing cache handling, empty universe, single-name universe. |
| **F2** | Intermediate-Term Momentum | Tier 1, Tier 3 | 21–63 session close-to-close rolling returns; lookback window validation; NaN handling. |
| **F3** | Short-Term Reversion Dampening | Tier 1, Tier 3 | 3–5 session short return dampening subtracted from momentum signal. |
| **F4** | Idiosyncratic Volatility Scaling | Tier 1, Tier 2 | Residual volatility relative to market proxy over 63 sessions; zero-variance handling. |
| **F5** | PIT Composite Factor Ranking | Tier 1, Tier 2 | Linear combination of momentum, dampening, and idio-vol; deterministic symbol tie-breaking. |
| **F6** | 4-Tranche Weekly Ledger | Tier 1, Tier 3 | 4 autonomous sub-ledgers, staggered 5 sessions apart, each held 21 sessions. |
| **F7** | Top Quintile Selection | Tier 1, Tier 2 | Selection of top 15–20% of eligible liquid universe; boundary size checks. |
| **F8** | Next-Open Execution (T+1) | Tier 1, Tier 4 | Orders generated at $T$ close, filled strictly at $T+1$ open; zero look-ahead invariant. |
| **F9** | Statutory Fee Accounting | Tier 1, Tier 3 | Exact 0.224% round-trip fee (0.112% entry + 0.112% exit) computed via Decimal math. |
| **F10** | Leverage & Capital Invariant | Tier 1, Tier 3 | Total capital exposure across all 4 tranches strictly $\le 1.0000$ at all times. |
| **F11** | Decile Portfolios Q1..Q10 | Tier 1, Tier 3 | 10 disjoint decile portfolios across universe; equal-weight asset allocation. |
| **F12** | Spearman Rank IC & t-statistic | Tier 1, Tier 4 | Cross-sectional rank correlation between score and 21d forward return; $t > 2.0$. |
| **F13** | Monotonicity & Spread | Tier 1, Tier 4 | Annualized return monotonicity ($Q_1 > Q_{10}$); zero-capital long-short spread return. |
| **F14** | Pre-declared Evaluation Budget | Tier 1, Tier 4 | Pre-declared trial count enforcement via trial ledger validation. |
| **F15** | CASH & ALWAYS_TRADE Benchmarks | Tier 1, Tier 4 | Benchmark comparison against 0% cash return and broad market all-in trading with fees. |
| **F16** | 30-Seed NOISE Control | Tier 1, Tier 4 | 30 pseudo-random Gaussian noise ranking trials through identical tranche ledger. |
| **F17** | Deflated Sharpe Ratio (DSR) | Tier 1, Tier 4 | DSR adjustment for multiplicity and non-normality; DSR candidate $>$ median noise. |
| **F18** | Holdout Partition Quarantine | Tier 1, Tier 4 | Strict quarantine of final 252 sessions (2025-08-14 to 2026-08-21); no tuning access. |

---

## 3. Test Tiers Structure

The test suite is structured into 4 distinct verification tiers:

### Tier 1: Feature Coverage (Unit & Subsystem Acceptance)
- Minimum of 5 test cases per core feature category (R1 Ranking, R2 Tranche Ledger, R3 Diagnostics, R4 Multiplicity & Governance).
- Verifies functional correctness, formulas, sorting invariants, Decimal fee deductions, tranche rotation schedules, and metric computations under nominal conditions.

### Tier 2: Boundary & Corner Cases
- Probes edge cases and extreme inputs:
  - Empty universe and single-constituent universe.
  - Circuit-locked trading sessions (`volume == 0` or `high == low` upper/lower limit locks).
  - Identical scores requiring deterministic lexicographical tie-breaking.
  - Constant price / zero variance assets (infinite Sharpe / zero volatility edge cases).
  - Extreme volatility shocks (+20% / -20% consecutive limit moves).

### Tier 3: Cross-Feature Interactions
- Tests multi-component integration points:
  - Interaction between composite ranking output and tranche portfolio rebalancer.
  - Interaction between fee deduction, cash reservation, and the $\le 1.0000$ leverage cap.
  - Interaction between factor decile partitions and changing market volatility regimes.
  - Staggered rebalancing cash flow reconciliation across simultaneous tranche entries and exits.

### Tier 4: Real-World Acceptance Scenarios
- End-to-end acceptance tests asserting all primary criteria from `ORIGINAL_REQUEST.md`:
  1. **Net Positive Sharpe**: Annualized net Sharpe ratio strictly $> 0$ after deducting 0.224% fees.
  2. **Statistically Significant IC**: Cross-sectional Spearman rank IC with $t$-statistic $> 2.0$.
  3. **Decile Monotonicity**: Top decile ($Q_1$) annualized return strictly exceeds bottom decile ($Q_{10}$).
  4. **Multiplicity & Noise Hurdle**: Candidate DSR strictly exceeds median DSR of 30-seed NOISE control.
  5. **Leverage Ceiling**: Combined portfolio leverage strictly $\le 1.0000$ across all evaluation days.
  6. **Zero Look-Ahead**: Mathematical verification that decision at $T$ cannot access prices at $T+1$ open.
  7. **Holdout Quarantine**: Verification that holdout dates remain sealed from parameter tuning.

---

## 4. Test Architecture & CLI Runner

### Directory Layout
```
tests/test_xs_portfolio_alpha/
├── __init__.py
└── test_e2e_acceptance.py      # Master 4-tier opaque-box acceptance test suite
```

### Pytest Markers
- `@pytest.mark.tier1`: Core feature coverage tests.
- `@pytest.mark.tier2`: Boundary, edge condition, and degenerate case tests.
- `@pytest.mark.tier3`: Cross-feature subsystem interaction tests.
- `@pytest.mark.tier4`: End-to-end real-world acceptance criteria tests.

### Execution Commands
```bash
# Run the entire E2E acceptance suite
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v

# Run specific tier
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -m tier1 -v
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -m tier2 -v
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -m tier3 -v
uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -m tier4 -v

# Run linter and type checker
uv run ruff check tests/test_xs_portfolio_alpha/
uv run mypy tests/test_xs_portfolio_alpha/
```

---

## 5. Coverage & Quality Thresholds

| Metric | Target Threshold | Rationale |
|---|---|---|
| **Tier 1 Feature Tests** | $\ge 5$ cases per requirement | Ensures all constituent formulas and operations are covered. |
| **Pass Rate** | 100% | Zero tolerance for test failures or unhandled edge cases in financial pathways. |
| **Linting Compliance** | 0 warnings / 0 errors (`ruff`) | Enforces standard repository formatting and import hygiene. |
| **Type Checking** | Strict mode 100% clean (`mypy`) | Prevents type confusion between float and Decimal in financial calculations. |
| **Leverage Invariant** | Total exposure $\le 1.0000$ | Capital preservation invariant; no leverage or overdraft permitted. |
| **Fee Deduction** | Exactly 0.224% round trip | 11.2 bps entry + 11.2 bps exit computed in Decimal arithmetic. |
| **Execution Timing** | $T+1$ Open | Zero look-ahead leakage allowed. |
