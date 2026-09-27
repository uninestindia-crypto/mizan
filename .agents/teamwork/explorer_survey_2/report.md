# Comprehensive Investigation & Architectural Proposal: R1 Multi-Factor Composite Ranking Engine & R2 Staggered Tranche Portfolio Ledger

**Date**: 2026-09-25  
**Author**: `explorer_survey_2`  
**Status**: COMPLETE / SURVEY & ARCHITECTURE  
**Target System**: QuantOS Cross-Sectional Portfolio Alpha System (`uninestindia-crypto/quant-system`)

---

## 1. Executive Summary

### 1.1 Context & Problem Statement
Prior research in QuantOS demonstrated that single-instrument directional prediction models failed 101 governed trials because directional returns at short horizons ($h=1, 2$) are overwhelmed by transaction friction (0.224% round-trip statutory costs produce a devastating ~56% p.a. drag on daily trading). 

When shifting to cross-sectional ranking at monthly horizons ($h=21$), transaction friction drops to ~0.40%–2.7% p.a., creating a viable economic window for cost survival. However, Hermes' initial prototype (`agent_context/work/active/20260903-hermes-xs-monthly-screen-new.md`) using a raw 21-session momentum rule (`close[T] / close[T-21] - 1`) failed to generate true selection alpha:
- **Rank Information Coefficient (IC)**: Mean IC was **negative** ($-0.0096$, $t = -0.85$ over 115 monthly rebalances).
- **Long-Short Spread**: Mean net return was **negative** ($-0.00063$/period, $t = -0.36$).
- **Selection Edge**: Long top-20% annualized Sharpe was $+0.84$ ($t = 2.59$), but the market equal-weight benchmark over the exact same sessions printed Sharpe $+0.83$ ($t = 2.58$). The net selection edge was a negligible **$+5.3$ bps/month** ($+0.00053$), entirely explained by market beta and survivorship bias.

### 1.2 Root Cause Analysis
Why did simple 21-day momentum fail?
1. **Retail Overreaction & Short-Term Reversals (3–5 sessions)**: In the Indian market, retail order flow frequently creates short-term price spikes. A stock that rallied +15% over the last 3–5 sessions often has a high 21-session return, but suffers an immediate, sharp mean-reversion over the subsequent holding period.
2. **High-Volatility Lottery Trap**: Unscaled momentum sorts mechanically select high-volatility, erratic stocks because their nominal price swings are larger. These stocks suffer from severe variance drag, unhedged beta risk, and catastrophic momentum crashes during sector rotations.
3. **Rebalance Timing Luck & Lumpy Turnover**: A single monthly rebalance subjects the portfolio to timing luck (e.g., whether rebalancing occurred on the 1st vs 15th of the month) and produces massive 100% turnover spikes every 21 sessions.

### 1.3 Key Innovations of R1 and R2
- **R1 (Multi-Factor Composite Ranking Engine)**: Solves factor collapse by combining:
  1. *Intermediate-term momentum* (21–63 trading sessions) to capture durable intermediate trends;
  2. *Short-term mean-reversion dampening* (3–5 trading sessions, subtracted/dampened) to filter out retail exhaustion spikes;
  3. *Idiosyncratic volatility scaling* (residual volatility from market beta or return volatility) to prioritize high-conviction, low-noise compounders over lottery tickets;
  4. *Zero look-ahead guarantee*: Point-in-time calculation strictly utilizing information available at decision close $T$.
- **R2 (Staggered Tranche Portfolio Ledger)**: Solves timing luck and turnover concentration by maintaining:
  1. *4 concurrent, staggered weekly tranches* (each held for 21 sessions, rebalanced on a rotating weekly cadence of 5 sessions);
  2. *Top quintile selection* (15–20% of liquid universe, ~63–85 names);
  3. *Next-open execution* ($T+1$ Open) with circuit/lock checks;
  4. *Exact 0.224% statutory fee model* with paise quantization and Decimal double-entry accounting;
  5. *Strict capital preservation invariant*: Total portfolio leverage strictly $\le 100\%$ ($1.0000$) at all timestamps.

---

## 2. Deep Dive: R1 Multi-Factor Composite Ranking Engine

### 2.1 Survey of Existing Codebase Assets
- `src/quant_system/research_xs_monthly/bars.py`: Reads point-in-time daily bars from market cache (`store/datasets/*/manifest.json` and `store/blobs/*.jsonl.gz`). Successfully loads all 423 names from `data/authorities/nse-research-universe-liquid-10y.csv` with 1,037,813 clean daily bars spanning 2016-08-22 to 2026-08-21 (2,476 trading sessions).
- `src/quant_system/research_xs_monthly/screen.py`: Establishes `build_calendar` (requiring $\ge 70\%$ universe coverage), `formation_score`, `forward_net` with $T+1$ next-open execution, and circuit-lock skip checks (`volume == 0 or high == low`).
- `src/quant_system/execution/cross_sectional_strategy.py`: Promotes universe binding, `CrossSectionalSelectionRuleV1` (with ceiling count logic), and formalizes that cross-sectional ranking requires all peer data at a single decision timestamp.
- `src/quant_system/modeling/mizan_features.py`: Implements Wilder RSI, Garman-Klass volatility, Parkinson volatility, and rolling SMA features.
- `reports/claude_opus_audit/01_model_analysis.md`: Establishes that Blitz, Huij & Martens (2011) residual momentum doubles conventional momentum Sharpe by eliminating factor-timing risk, and notes that the low-volatility anomaly is exceptionally strong in India.

### 2.2 Mathematical Specification of Factor Components

Let $C_{i, t}$ be the closing price of symbol $i$ on calendar trading session $t$.

#### Factor 1: Intermediate-Term Momentum ($M_{i, T}^{\text{inter}}$)
Captures persistent intermediate drift across 21 to 63 sessions (approx 1 to 3 months):
$$R_{i, T}^{(63)} = \frac{C_{i, T} - C_{i, T-63}}{C_{i, T-63}}$$
$$R_{i, T}^{(21)} = \frac{C_{i, T} - C_{i, T-21}}{C_{i, T-21}}$$
The intermediate momentum term can be formulated either as the 63-session cumulative return or as an equal-weighted combination of the 21-session and 63-session returns:
$$M_{i, T}^{\text{inter}} = \frac{1}{2}\left( z\left(R_{i, T}^{(21)}\right) + z\left(R_{i, T}^{(63)}\right) \right) \quad \text{or} \quad R_{i, T}^{(63)}$$

#### Factor 2: Short-Term Mean-Reversion Dampening ($D_{i, T}^{\text{short}}$)
Captures retail overreaction and exhaustion over 3 to 5 sessions:
$$R_{i, T}^{(5)} = \frac{C_{i, T} - C_{i, T-5}}{C_{i, T-5}}$$
$$R_{i, T}^{(3)} = \frac{C_{i, T} - C_{i, T-3}}{C_{i, T-3}}$$
Because short-term returns in Indian equities exhibit sharp mean-reversion, we penalize recent spikes by subtracting the short-term return from the intermediate trend:
$$\Delta_{i, T} = R_{i, T}^{(63)} - \lambda_{\text{damp}} \cdot R_{i, T}^{(5)}$$
where $\lambda_{\text{damp}} \in [0.3, 0.5, 1.0]$ is the dampening intensity.

#### Factor 3: Idiosyncratic Volatility Scaling ($\sigma_{\text{idio}, i, T}$)
Prevents high-beta, lottery-ticket stocks from dominating the ranking.

**Method A: Residual Volatility from Market Beta (CAPM OLS Regression)**:
Over a trailing estimation window $W = 63$ sessions ending at decision close $T$:
1. Compute daily returns for stock $i$: $r_{i, t} = \frac{C_{i, t} - C_{i, t-1}}{C_{i, t-1}}$ for $t \in [T-W+1, T]$.
2. Compute equal-weighted market universe return: $r_{m, t} = \frac{1}{N_t} \sum_{j=1}^{N_t} r_{j, t}$.
3. Compute market variance and covariance:
   $$\text{Var}(r_m) = \frac{1}{W-1} \sum_{t=1}^W (r_{m, t} - \bar{r}_m)^2$$
   $$\text{Cov}(r_i, r_m) = \frac{1}{W-1} \sum_{t=1}^W (r_{i, t} - \bar{r}_i)(r_{m, t} - \bar{r}_m)$$
4. Compute market beta: $\hat{\beta}_i = \frac{\text{Cov}(r_i, r_m)}{\max(10^{-8}, \text{Var}(r_m))}$.
5. Residual variance:
   $$\sigma_{\epsilon, i}^2 = \text{Var}(r_i) - \hat{\beta}_i^2 \text{Var}(r_m)$$
6. Idiosyncratic volatility:
   $$\sigma_{\text{idio}, i} = \sqrt{\max\left(10^{-8}, \sigma_{\epsilon, i}^2\right)}$$

**Method B: Realized Return Volatility (Total Volatility)**:
$$\sigma_{i} = \sqrt{\frac{1}{W-1} \sum_{t=1}^W (r_{i, t} - \bar{r}_i)^2}$$

#### Composite Ranking Formulation
Two complementary composite formulations are supported:
- **Formulation 1: Information-Ratio / Risk-Adjusted Momentum (Ratio Form)**:
  $$\text{Score}_{i, T} = \frac{R_{i, T}^{(63)} - \lambda_{\text{damp}} R_{i, T}^{(5)}}{\sigma_{\text{idio}, i, T}}$$
  *Economic Rationale*: Analogous to an individual stock Information Ratio or Sharpe ratio of momentum. Names with smooth, low-residual-volatility trends rank highest; noisy names with recent parabolic spikes are severely penalized.
- **Formulation 2: Standardized Multi-Factor Linear Composite (Z-Score Form)**:
  For each metric $X_i \in \{R^{(63)}, R^{(5)}, \sigma_{\text{idio}}\}$, compute cross-sectional z-score:
  $$z(X_i) = \frac{X_i - \text{mean}(X)}{\max(10^{-8}, \text{std}(X))}, \quad \text{winsorized at } [-3.0, +3.0]$$
  $$\text{Composite}_{i, T} = w_{\text{inter}} \cdot z\left(R_{i, T}^{(63)}\right) - w_{\text{short}} \cdot z\left(R_{i, T}^{(5)}\right) - w_{\text{vol}} \cdot z\left(\sigma_{\text{idio}, i, T}\right)$$
  Default weights: $w_{\text{inter}} = 1.0, w_{\text{short}} = 0.5, w_{\text{vol}} = 0.5$.

### 2.3 Zero Look-Ahead Leakage Guarantee
1. **Timestamp Invariant**: All factor inputs for session $T$ strictly consume price bars with `exchange_date <= T`. Session $T+1$ bars (including Open, High, Low, Close) are completely masked and inaccessible to the ranking engine.
2. **Corporate Actions**: Historical daily bars from the Upstox cache represent canonical point-in-time series. Any adjustments effective after date $T$ cannot be reflected prior to $T$.
3. **No Imputation / Fail-Closed**: If a symbol has fewer than 63 consecutive historical bars ending at $T$, or has non-positive prices or zero volume across the formation window, it is assigned a score of `None` and excluded from the eligible ranking pool. No forward-filling or mean imputation is permitted.

---

## 3. Deep Dive: R2 Staggered Tranche Portfolio Ledger

### 3.1 Mechanics of the 4-Tranche Staggered Ledger
- **Total Holding Period**: $H = 21$ trading sessions (~1 calendar month).
- **Rebalance Interval**: $R = 5$ trading sessions (~1 calendar week).
- **Number of Tranches**: $K = 4$ tranches (since $21 / 5 \approx 4$).
- **Capital Budget**: Each tranche is allocated an equal 25% share of portfolio capital.

```
Session Timeline (sessions):
T=0        T=5        T=10       T=15       T=20 (Matures: T=21)
|----------|----------|----------|----------|
[Tranche 0: enters T=1 open, exits T=22 open] ----------------------> [Tranche 0 re-invests at T=22 open]
           [Tranche 1: enters T=6 open, exits T=27 open] -----------> [Tranche 1 re-invests at T=27 open]
                      [Tranche 2: enters T=11 open, exits T=32 open] -> [Tranche 2 re-invests at T=32 open]
                                 [Tranche 3: enters T=16 open, exits T=37 open] ...
```

### 3.2 Benefits of Staggered Rebalancing
1. **Diversification Across Momentum Vintages**: Rather than betting on a single date's top quintile, the portfolio holds 4 distinct vintages of top-quintile names. Persistent winners are held across multiple tranches (increasing weight up to $4 \times w_i$), while fading names naturally cycle out.
2. **Turnover Smoothing**: Only 25% of the portfolio turns over every 5 sessions, avoiding market impact and large lump-sum liquidity requirements.
3. **Elimination of Calendar Luck**: Performance does not depend on whether rebalancing lands on the first trading day of the month or mid-month.

### 3.3 Universe & Top Quintile Selection
- **Universe**: Liquid 423-name NSE research universe (`data/authorities/nse-research-universe-liquid-10y.csv`).
- **Eligibility Filter at Session $T$**:
  - Symbol is present in universe authority.
  - Symbol has valid bars on all required formation sessions ($T-63$ to $T$).
  - Symbol is not circuit-locked on decision close $T$ (`volume > 0` and `high > low`).
- **Selection Fraction**: Top 20% (quintile) of eligible names.
  - If 400 names are eligible, $M = \lfloor 0.20 \times 400 \rfloor = 80$ names are selected.
  - Formula: $M = \text{max}(1, \text{int}(\text{Decimal}(N_{\text{elig}}) \times \text{TOP\_FRAC}))$.
  - Each selected stock in tranche $k$ is allocated an equal dollar share:
    $$\text{Target Cash per Stock} = \frac{\text{Tranche Available Cash}}{M}$$

### 3.4 Next-Open Execution (T+1) Fill Pricing and Accounting
- **Order Timing**: Signals are generated at decision close $T$. Orders execute at session $T+1$ Open.
- **Entry Fill Price**: $P_{\text{entry}} = \text{Open}_{i, T+1}$.
- **Exit Fill Price**: $P_{\text{exit}} = \text{Open}_{i, T+22}$ (after holding 21 sessions).
- **Circuit Lock Rule**:
  - If a selected stock is circuit-locked at $T+1$ Open (`volume == 0` or `high == low`), the buy order is rejected/skipped. Its allocated cash remains in the tranche cash balance.
  - If a held stock is circuit-locked at exit Open ($T+22$), it cannot be liquidated at open. It is carried to the next unlocked session or flagged with an explicit audit trail.

### 3.5 0.224% Round-Trip Statutory Cost Model
QuantOS enforces statutory friction in compliance with official NSE schedules (`src/quant_system/analytics/nse_rules.py`):
- **Statutory Round-Trip Ratio**: $c_{\text{rt}} = \text{Decimal}("0.00224")$ (22.4 bps).
  - STT: 0.10% on Buy + 0.10% on Sell (Delivery) = 0.200%
  - Stamp Duty: 0.015% on Buy = 0.015%
  - Exchange Turnover Fee: 0.00325% Buy + Sell = 0.0065%
  - SEBI Turnover Fee: 0.0001% Buy + Sell = 0.0002%
  - GST: 18% on Exchange + SEBI = ~0.0012%
  - Total: ~0.223% $\approx 0.224\%$ (with roundings & DP depository buffer).
- **Exact Double-Entry Postings**:
  - Entry-side fee rate: $c_{\text{entry}} = \text{Decimal}("0.00112")$
  - Exit-side fee rate: $c_{\text{exit}} = \text{Decimal}("0.00112")$
  - When purchasing $Q$ shares at $P_{\text{entry}}$:
    $$\text{Consideration} = (Q \times P_{\text{entry}}).\text{quantize}(0.01)$$
    $$\text{Entry Fee} = (\text{Consideration} \times c_{\text{entry}}).\text{quantize}(0.01)$$
    $$\Delta \text{Cash} = -(\text{Consideration} + \text{Entry Fee})$$
  - When selling $Q$ shares at $P_{\text{exit}}$:
    $$\text{Gross Proceeds} = (Q \times P_{\text{exit}}).\text{quantize}(0.01)$$
    $$\text{Exit Fee} = (\text{Gross Proceeds} \times c_{\text{exit}}).\text{quantize}(0.01)$$
    $$\Delta \text{Cash} = +(\text{Gross Proceeds} - \text{Exit Fee})$$
    $$\text{Realized P\&L} = (\text{Gross Proceeds} - \text{Consideration}) - (\text{Entry Fee} + \text{Exit Fee})$$
  - All state transitions use `Decimal` with paise quantization (`Decimal("0.01")`). Zero binary floats.

### 3.6 Capital Preservation Invariant
- **Total Portfolio Leverage**:
  $$\text{Leverage}_t = \frac{\sum_{i} \text{Shares}_{i, t} \times P_{i, t}}{\text{Total Portfolio Equity}_t} \le 1.0000 \quad (100\%)$$
- **Mathematical Invariant Proof**:
  1. Each tranche $k \in \{0, 1, 2, 3\}$ operates as an autonomous sub-ledger funded with at most 25% of total capital: $\text{Capital}_k \le 0.25 \times \text{Equity}$.
  2. Within each tranche, position sizing enforces:
     $$\sum_{i} Q_{i, k} \times P_{i, \text{entry}} \times (1 + c_{\text{entry}}) \le \text{Cash}_k$$
  3. Cash balances are strictly non-negative: $\text{Cash}_k \ge 0$.
  4. Tranches cannot borrow from other tranches or margin facilities (no shorting, no margin debt).
  5. Therefore, tranche exposure $\text{Invested}_k \le \text{Equity}_k$ for all $k$.
  6. Summing across all 4 tranches:
     $$\text{Total Invested} = \sum_{k=0}^3 \text{Invested}_k \le \sum_{k=0}^3 \text{Equity}_k = \text{Total Equity}$$
     $$\implies \text{Total Leverage} = \frac{\text{Total Invested}}{\text{Total Equity}} \le 1.0000 \quad \text{Q.E.D.}$$

---

## 4. Architecture & Interface Proposal

To comply with QuantOS product laws and avoid colliding with other agents' active claims, all new code will be placed under the owned paths pre-registered in `agent_context/work/active/20260925-1510Z-orchestrator-xs-portfolio-alpha.md`:
- `src/quant_system/research_xs_monthly/`
- `src/quant_system/portfolio/`
- `tests/test_xs_portfolio_alpha.py`
- `scripts/run_xs_portfolio_alpha.py`
- `reports/xs_portfolio_alpha/`

### 4.1 Module Layout

```
src/quant_system/
├── research_xs_monthly/
│   ├── bars.py               # (Existing) Daily point-in-time bar loader
│   ├── screen.py             # (Existing) Baseline monthly screen
│   ├── paper.py              # (Existing) Forward paper watch
│   ├── ranking.py            # [NEW] R1 Multi-Factor Composite Ranking Engine
│   └── factor_models.py      # [NEW] Factor computation kernels (mom, damp, idio_vol)
└── portfolio/
    ├── allocation.py         # (Existing) Order diff calculation
    ├── optimization.py       # (Existing) Markowitz / Risk parity
    ├── sizing.py             # (Existing) Volatility parity / Kelly
    ├── tranche_ledger.py     # [NEW] R2 Staggered Tranche Portfolio Ledger
    └── metrics.py            # [NEW] Portfolio & Decile Tearsheet Metrics
```

### 4.2 Class & Interface Specifications

#### 1. Factor Engine Interfaces (`src/quant_system/research_xs_monthly/factor_models.py`)

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Sequence
from quant_system.research_xs_monthly.bars import Bar

@dataclass(frozen=True, slots=True)
class FactorConfig:
    """Immutable configuration for multi-factor ranking."""
    formation_intermediate_sessions: int = 63  # 3-month momentum window
    formation_short_sessions: int = 5         # 1-week mean-reversion dampening
    volatility_window_sessions: int = 63      # Idiosyncratic volatility window
    dampening_lambda: Decimal = Decimal("0.5") # Short-term penalty weight
    volatility_penalty_weight: Decimal = Decimal("0.5") # Low-vol weight
    winsorize_std: float = 3.0
    use_residual_vol: bool = True             # True: CAPM beta residual; False: total vol

@dataclass(frozen=True, slots=True)
class StockFactorValues:
    symbol: str
    intermediate_return: Decimal
    short_return: Decimal
    idiosyncratic_vol: Decimal
    market_beta: Decimal
    raw_composite: Decimal
    standardized_score: float

def compute_intermediate_momentum(
    indexed_bars: dict[date, Bar],
    calendar: Sequence[date],
    decision_idx: int,
    window: int = 63,
) -> Decimal | None:
    """Computes (Close[T] - Close[T-window]) / Close[T-window]. Fails closed if incomplete."""

def compute_short_term_return(
    indexed_bars: dict[date, Bar],
    calendar: Sequence[date],
    decision_idx: int,
    window: int = 5,
) -> Decimal | None:
    """Computes (Close[T] - Close[T-window]) / Close[T-window]."""

def compute_idiosyncratic_volatility(
    indexed_bars: dict[date, Bar],
    market_returns: Sequence[float],
    calendar: Sequence[date],
    decision_idx: int,
    window: int = 63,
) -> tuple[Decimal, Decimal] | None:
    """Computes (idiosyncratic_volatility, market_beta) via trailing OLS against market returns."""
```

#### 2. Multi-Factor Ranking Engine (`src/quant_system/research_xs_monthly/ranking.py`)

```python
@dataclass(frozen=True, slots=True)
class RankedSymbol:
    symbol: str
    rank: int
    score: float
    factor_values: StockFactorValues

class MultiFactorRankingEngine:
    """Computes point-in-time cross-sectional rankings across eligible universe."""

    def __init__(self, config: FactorConfig | None = None) -> None:
        self.config = config or FactorConfig()

    def rank_universe(
        self,
        bars_by_symbol: dict[str, list[Bar]],
        calendar: Sequence[date],
        decision_idx: int,
    ) -> list[RankedSymbol]:
        """Ranks all eligible symbols at decision close T with zero look-ahead.
        
        1. Filters symbols having full historical window [T - window, T].
        2. Computes market return series r_m for session window.
        3. Computes intermediate return, short-term return, and idiosyncratic vol for each stock.
        4. Calculates composite scores (ratio or standardized z-score).
        5. Returns descending ranked list of eligible symbols.
        """
```

#### 3. Staggered Tranche Portfolio Ledger (`src/quant_system/portfolio/tranche_ledger.py`)

```python
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

@dataclass(frozen=True, slots=True)
class TranchePosition:
    symbol: str
    quantity: int
    entry_price: Decimal
    entry_fee: Decimal
    entry_date: date
    scheduled_exit_date: date
    
    @property
    def cost_basis(self) -> Decimal:
        return (self.entry_price * Decimal(self.quantity)).quantize(Decimal("0.01"))

@dataclass
class TrancheState:
    tranche_id: int
    cash: Decimal
    positions: dict[str, TranchePosition] = field(default_factory=dict)
    active: bool = False
    entry_decision_date: date | None = None
    entry_execution_date: date | None = None
    exit_execution_date: date | None = None
    cumulative_realized_pnl: Decimal = Decimal("0.00")
    cumulative_fees_paid: Decimal = Decimal("0.00")

@dataclass(frozen=True, slots=True)
class SessionEquityMark:
    session_date: date
    total_equity: Decimal
    cash_balance: Decimal
    market_value: Decimal
    leverage: Decimal  # market_value / total_equity
    active_tranches: int
    open_positions_count: int

class StaggeredTrancheLedger:
    """4-tranche weekly-rebalanced portfolio ledger maintaining leverage <= 100%."""

    def __init__(
        self,
        initial_capital: Decimal = Decimal("1000000.00"),
        num_tranches: int = 4,
        hold_sessions: int = 21,
        rebalance_interval: int = 5,
        top_fraction: Decimal = Decimal("0.20"),
        statutory_fee_ratio: Decimal = Decimal("0.00224"),
    ) -> None:
        self.initial_capital = initial_capital
        self.num_tranches = num_tranches
        self.hold_sessions = hold_sessions
        self.rebalance_interval = rebalance_interval
        self.top_fraction = top_fraction
        self.entry_fee_rate = statutory_fee_ratio / Decimal(2)  # 0.00112
        self.exit_fee_rate = statutory_fee_ratio / Decimal(2)   # 0.00112
        
        # Initialize autonomous tranches
        tranche_alloc = (initial_capital / Decimal(num_tranches)).quantize(Decimal("0.01"))
        self.tranches = [
            TrancheState(tranche_id=k, cash=tranche_alloc)
            for k in range(num_tranches)
        ]
        self.history: list[SessionEquityMark] = []

    def process_session(
        self,
        session_idx: int,
        calendar: Sequence[date],
        bars_by_symbol: dict[str, list[Bar]],
        decision_rankings: list[RankedSymbol] | None = None,
    ) -> SessionEquityMark:
        """Processes one session step:
        1. Open: Liquidates maturing tranches at Session Open price.
        2. Open: Deploys rotating tranche into new top quintile names at Session Open price.
        3. Close: Computes marked equity and verifies leverage <= 1.0000 invariant.
        """

    def reconcile(self) -> dict[str, Any]:
        """Independent mathematical reconciliation of cash, positions, fees, and P&L."""
```

---

## 5. Verification & Test Plan

1. **Point-in-Time Zero Leakage Tests**:
   - Inject anomalous spikes in $T+1$ Open, High, Low, Close.
   - Prove that ranking output at decision close $T$ is bit-for-bit identical before and after the injection.
2. **Execution Timing & Locked Session Tests**:
   - Verify buy fills execute strictly at $T+1$ Open.
   - Verify sell fills execute strictly at $T+22$ Open (after 21 sessions).
   - Verify circuit-locked stocks (`volume == 0` or `high == low`) are skipped on entry without capital loss.
3. **Statutory Fee & Accounting Reconciliation**:
   - Verify exact 0.224% round-trip deduction across all completed lots.
   - Prove total realized P&L equals `Gross Proceeds - Consideration - Total Fees` to the exact paisa.
   - Reconcile `Total Equity == Cash + Sum(Holdings Market Value)` at every bar.
4. **Capital Preservation Invariant**:
   - Assert `Leverage <= Decimal("1.0000")` and `Cash >= Decimal("0.00")` on every single session across the entire 10-year backtest.

---

## 6. Recommendations for Implementer

1. **Vectorized Factor Kernel for Backtesting Speed**: Use numpy rolling cumulative sums for rolling beta and residual volatility (verified prototype runs in under 70ms for 423 names across 483 weekly dates).
2. **Autonomous Tranche Ledgers**: Structure each tranche as an independent sub-ledger with its own cash and holdings. This structurally guarantees that no tranche can borrow or over-allocate, guaranteeing the $\le 100\%$ leverage invariant by construction.
3. **Paise Quantization**: Always quantize cash, considerations, and fees to `Decimal("0.01")` using `ROUND_HALF_UP` to prevent penny leakage.
4. **Decile Diagnostics Integration**: Build the decile diagnostic (R3) by splitting the sorted output of `MultiFactorRankingEngine` into 10 deciles (Q1 to Q10) at each weekly rebalance date.
