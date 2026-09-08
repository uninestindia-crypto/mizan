# QuantOS Dual-AI Executive Consensus: The Two Live Mīzān Systems
**Audit Date**: 2026-09-06 02:22:00 IST  
**Auditors**: 
- **Auditor 1**: OpenAI `gpt-6-astra` (First Opinion — Forensic & Microstructure Lead)
- **Auditor 2**: Anthropic `claude-fable-5.1` (Second Opinion — System Architect & Adversarial Critic)  
**Environment**: 100% Virtual Money / Paper Trading Simulation (Sandbox Testing & Platform Engineering)  
**Evaluated Books**:
- **System 1**: Mīzān Flagship Alpha (Intraday Paper Pilot, ₹10,00,000 Virtual Capital, 97 Holdings)
- **System 2**: Mīzān XS-Monthly Momentum (21-Day Paper Watch, ₹10,00,000 Virtual Capital, 99 Holdings)

---

## Executive Scorecard

| Dimension | System 1: Flagship Alpha | System 2: XS-Monthly Momentum | Auditor Consensus |
|---|---|---|---|
| **Underlying Premise** | 15-Feature Cross-Sectional Ridge | 21-Day Top-20% Momentum Basket | **UNANIMOUS** |
| **Statistical Signal** | Inverted (|t| > 2 on 8/14 features, negative IC) | Weak Selection (+5.3 bps edge over EW Market) | **UNANIMOUS** |
| **Friction Tolerance** | Gross 7.6 bps vs 22.25 bps NSE round-trip | DP fee alone (17–27 bps) eats 5.3 bps edge | **UNANIMOUS** |
| **Portfolio Cardinality** | 97 holdings (~₹10,300/stock) = False Diversification | 99 holdings (~₹8,700/stock) = DP Fee Disaster | **UNANIMOUS** |
| **Production Readiness** | **REJECT** in current form | **REJECT** as alpha; retain as control benchmark | **UNANIMOUS** |

---

## 1. Unanimous Points of Agreement

1. **Neither System Has Deployable Alpha in Current Form**:
   - System 1 is trading opposite to the empirical price dynamics at the 1–5 day horizon.
   - System 2's apparent profitability (+₹4,223.88) is general equity market beta, not stock-selection alpha.

2. **The 97/99 Cardinality Error on ₹10 Lakh Notional**:
   - Both systems spread ₹10,00,000 across nearly 100 stocks (~₹8,700–₹10,300 per position).
   - This creates an expensive index proxy with active management transaction costs.

3. **The Flat DP Fee Mathematical Trap**:
   - In Indian equities, selling delivery incurs flat Depository Participant (DP) debit charges of ₹15.50–₹23.60 (inclusive of GST) per ISIN sold.
   - On an ₹8,700 position, a ₹20 DP fee is **23 bps** on the exit alone.
   - Across 99 stocks, DP fees total **₹1,534 to ₹2,336 per monthly rebalance**, which is **2.9× to 4.4× the entire 10-year monthly selection edge (+₹530 / 5.3 bps)**!

4. **Negative Information Coefficients (IC) in System 1**:
   - The 8 statistically significant negative IC features (`return_1` $t=-4.2$, `return_5` $t=-3.8$, `rsi_14` $t=-2.9$, `sma_20` $t=-3.1$) indicate that Indian equities over short windows exhibit mean-reversion, not momentum.

---

## 2. Nuances and Disagreements Between Auditors

### A. Execution & Opening Auctions
* **GPT-6-Astra**: Assumed standard open execution and flagged general open-price attainability.
* **Claude Fable 5.1**: Highlighted the specific NSE Pre-Open structure (08:00–08:45 limit collection, 08:45–08:59 random close, 09:00 equilibrium print, 09:00–09:07 retail flow). Entering 97–99 names at the single open print guarantees gap slippage, circuit lockouts, and adverse selection. **Recommended**: Implement TWAP/VWAP over the first 15–30 minutes (09:15–09:45) rather than batched open prints.

### B. Intraday Cash Viability
* **GPT-6-Astra**: Strictly cautioned against switching to intraday cash merely to avoid DP fees, arguing that System 1 lacks short-horizon alpha.
* **Claude Fable 5.1**: Pointed out that intraday cash avoids DP fees entirely and drops STT from 0.1% to 0.025% on sell, lowering total round-trip friction to **13–15 bps** (vs 22.25 bps delivery). If a purpose-built contrarian reversal signal demonstrates >15 bps gross edge decaying over 1–2 hours, an intraday execution structure is mathematically testable.

### C. Mechanical Sign Inversion
* **Both Models Agree**: Do NOT merely flip the signs ($\hat{\beta} \to -\hat{\beta}$) of the existing multivariate Ridge model. A Ridge regression with collinear features will not cleanly invert into an optimal contrarian strategy. A new reversal specification must be trained with explicitly signed features and date-blocked walk-forward validation.

---

## 3. The 5-Step Actionable Engineering Roadmap

1. **Halt System 1 Active Paper Execution**:
   - Freeze `logs/paper_runs/portfolio_state.json` as a forensic audit baseline.
   - Do not re-weight or tune the current model.

2. **Fix Cost Accounting in `research_xs_monthly/paper.py`**:
   - Incorporate explicit broker-specific per-ISIN DP debit charges (₹15.50 + GST) on all delivery sell legs.
   - Ensure the benchmark equal-weight portfolio is subjected to identical rebalance and cost models.

3. **Optimize Cardinality (The $N=20$ Frontier)**:
   - Restrict System 2 portfolio size from 99 names to **15–25 names**.
   - At $N=20$, each position is ~₹50,000. The DP fee drops from 23 bps to **3.5–4.5 bps**, preserving the net selection edge.

4. **Add Execution Realism**:
   - Replace single opening print fills with a 15–30 minute TWAP/VWAP execution window.
   - Filter candidate universes by 30-day median daily turnover to ensure liquid fills without market impact.

5. **Train a Purpose-Built Contrarian Horizon Model**:
   - If pursuing 1–3 day holding periods on NSE, train a dedicated mean-reversion model using date-blocked walk-forward validation, testing whether gross alpha clears the 13–15 bps intraday hurdle.
