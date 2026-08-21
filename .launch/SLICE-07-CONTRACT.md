# Slice 7 Contract — Governed Financial Research & Ledgers

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-22  

## 1. Scope & Purpose

Slice 7 establishes the governed financial accounting and analytical foundation for QuantOS:
1. **Effective-Dated Indian Exchange Rule Engine (`quant_system.analytics.nse_rules`)**: Point-in-time statutory and exchange fee schedules (STT, GST, SEBI turnover, Exchange turnover, Stamp Duty, Brokerage) selected strictly by trade date with no timeless constants.
2. **Exact Double-Entry Decimal Ledger (`quant_system.core.ledger`)**: Exact Decimal / integer paise accounting kernel tracking cash, positions, FIFO inventory lots, and realized/unrealized P&L with stable idempotency keys, strict binary float rejection, and SHA-256 cryptographic state reconciliation.
3. **Option Pricing & Greeks Engine (`quant_system.analytics.greeks`)**: Analytical Black-Scholes and lattice Binomial CRR option pricing models, numerical/analytical Greeks (Delta, Gamma, Theta, Vega, Rho), robust IV solver, and effective-dated NSE contract metadata (lot sizes, strike steps, Act/365 expiry year fraction).
4. **Pre-Trade Risk Governor (`quant_system.risk.governor`)**: Deterministic pre-trade limit enforcement with session peak equity tracking, daily and trailing max drawdown circuit breakers, concentration caps, cash buffers, spread gates, naked short prohibition, fail-closed kill switches, and full state recovery.

---

## 2. Invariants & Financial Law

### A. Exchange & Statutory Cost Engine
- **Strict Trade Date Selection**: Every statutory charge is bound to an immutable `DatedExchangeRule` with verified `effective_from` and `effective_to` dates, primary legal authority citations, and canonical SHA-256 rule hashes.
- **Separate Component Postings**: STT, Stamp Duty, Exchange Turnover, SEBI Turnover, GST, and Brokerage are computed on their statutory bases (turnover vs. premium turnover vs. service charge sum) and quantized to exact paisa before aggregation.
- **Zero Timeless Constants**: Historical and revised statutory rules (e.g. Finance (No. 2) Act 2024 STT hikes on futures/options, SEBI 2021 fee reduction, Uniform Stamp Duty 2020, NSE 2024 uniform charge structure) are selected strictly by trade date.

### B. Ledger & Inventory Accounting
- **Exact Decimal Kernel**: All money, prices, fees, and cash deltas use `Decimal` quantized to `Decimal("0.01")`. Binary floats are strictly rejected with `TypeError`.
- **Pure Single-Path Idempotency**: Processing an event with an existing idempotency key and identical payload is an atomic no-op returning the cached transaction. Conflicting payloads raise `IdempotencyConflictError`.
- **FIFO Lot Management**: Inventory lots (`PositionLot`) track cost basis and entry fees. Closures and partial fills realize P&L per closed lot. Position flips (Long → Short or Short → Long) execute atomically in a single transaction.
- **Validation Before Mutation**: Insufficient cash, forbidden short sales, or invariant breaches fail closed with zero modification to balances, positions, lots, or journal history.
- **State Reconciliation Hash**: A deterministic SHA-256 hash is computed over initial cash, cash, sorted positions, sorted lots, realized P&L, and transaction hashes.

### C. Options & Greeks Engine
- **Model Duality**: Analytical Black-Scholes for European contracts; Binomial Cox-Ross-Rubinstein (CRR) lattice for European and American exercise styles with convergence verification.
- **NSE Derivatives Conventions**: Exact effective-dated lot sizes (e.g. NIFTY 75/50/25/75 transitions, BANKNIFTY 25/15/30), strike step validation (50 pt NIFTY, 100 pt BANKNIFTY), and Act/365 day-count fraction to 15:30 IST market close.
- **Robust IV Inversion**: Hybrid Newton-Raphson with analytical Vega and robust Bisection search fallback.

### D. Pre-Trade Risk Governor
- **Deterministic Evaluation**: Every proposed order and fill is evaluated against immutable `RiskLimits` bound to a `limits_id` and SHA-256 `limits_hash`.
- **Peak Equity & Drawdown Breakers**: Tracks daily session peak and all-time peak equity monotonically. Breaches trigger automatic fail-closed kill switches.
- **Liquidity & Sizing Gates**: Enforces bid-ask spread limits, maximum single position weight, minimum cash buffer percentage, max order value, and portfolio leverage limits.
- **State Serialization**: Full state dictionary export and restoration across application restarts.

---

## 3. Explicit Limits

- QuantOS promotion remains capped at `RESEARCH_ONLY` / `PAPER_PILOT`; no live broker write capabilities exist.
- Options pricing assumes standard constant risk-free rate and continuous/discrete volatility models without stochastic jump diffusion.
- Exact numeric reproducibility is guaranteed under the frozen lock and test suite.
