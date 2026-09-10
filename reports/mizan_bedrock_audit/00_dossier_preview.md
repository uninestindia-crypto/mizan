# QuantOS Institutional Audit Dossier: Dual Mizan Systems

## TESTING PREMISE
- This is **100% VIRTUAL MONEY (paper trading simulation)**. No real capital is at risk.
- We are engineering an institutional algorithmic trading platform for Indian equities (NSE).
- Each system is allocated Rs 10,00,000 of virtual test capital.
- The objective is an unsparing audit: find the flaws, and establish whether any genuine,
  cost-surviving edge exists at all.

## DATA PROVENANCE
Every live figure below was read from the running paper books at audit time, not transcribed.
Source files: `data/evidence/paper/portfolio_state.json` and
`logs/xs_monthly_new/paper_watch/state.json`. Each number carries its own as-of date. Where a
figure is a cost basis rather than a mark, it says so.

---

## SYSTEM 1: Mizan Flagship Alpha (multi-session paper pilot)

**Live state, as of 2026-09-09:**
- Allocated virtual capital: Rs 10,00,000.00
- Daily anchor equity: Rs 992,276.07 (recorded 2026-09-09)
- Implied drawdown against notional: -0.772%
- Cash available: Rs 145,520.31
- Open holdings: 97
- Cost basis of open holdings: Rs 853,407.04
- Average position size: Rs 8,798.01
- Last rebalance: 2026-08-31; last completed session: 2026-09-09
- Halted: no

**Model architecture:** Ridge classifier over 15 pooled cross-sectional features
(`quantos.mizan_crosssectional_fifteen`): `return_1`, `return_5`, `return_21`,
`garman_klass_volatility`, `parkinson_volatility`, `rsi_14_centered`, `sma_20_distance`,
`sma_50_distance`, `volume_zscore`, `money_flow_multiplier`, `india_vix_level`,
`india_vix_change_5`, `nifty_return_5`, `cs_rank_momentum_5`, `cs_rank_volume_surprise`.

**Governed trial evidence (historical, fixed):**
- `trial_mizan_001` (1-session hold): gross mean return +0.076% across all 45 symbols, but after
  NSE statutory friction of 0.2225% round trip, **45 of 45 symbols turned negative**.
  Sharpe -3.2427, total return -41.57%.
- `trial_mizan_h11_002` (10-session hold): Sharpe -0.4108, total return -31.57%, while buy-and-hold
  returned +22.0% over the same window. DSR 0.1760 against a 0.95 gate.
- **Feature IC inversion:** of 14 measurable features, 8 carry statistically significant
  **negative** IC (|t| > 2, all negative): `return_1` t = -4.2, `return_5` t = -3.8,
  `rsi_14_centered` t = -2.9, `sma_20_distance` t = -3.1, `cs_rank_momentum_5` t = -2.7.
  The model bets on continuation at horizons where these names mean-revert.

---

## SYSTEM 2: Mizan XS-Monthly Momentum (21-day paper watch)

**Live state, as of 2026-09-09 (last run 2026-09-10T04:09:04Z):**
- Allocated virtual capital: Rs 1,000,000.00
- **Marked equity: Rs 998,071.67**
- **Net P&L: Rs -1,928.33 (-0.193%)**
- Cash available: Rs 137,184.02
- Open legs: 99 (closed so far: 0)
- Entry value: Rs 862,815.98; current market value: Rs 860,887.65
- Average position size: Rs 8,715.31

**Frozen rule:** formation 21 sessions, hold 21
sessions, top 0.20 by momentum across NIFTY 500, cost ratio 0.00224.

**10-year backtest evidence (2016-2026, 423 liquid NSE names, 115 rebalances):**
- Top-20% momentum longs: net mean +1.74%/period, Sharpe **+0.84**
- Market equal-weight benchmark: net mean +1.69%/period, Sharpe **+0.83**
- **Selection edge over the unselected market: +5.3 bps/period (+0.053%)**
- Rank IC: -0.0096 (t = -0.85)
- 3-year breadth test (499 names, 2023-2026): longs Sharpe +0.91 vs market +0.89 (+10 bps/period)

**Friction and microstructure drag:**
- Indian delivery selling incurs a flat Depository Participant (DP) debit of Rs 13-20 plus 18% GST
  (about Rs 15.50-23.60) **per scrip per day**, independent of position size.
- At 99 legs averaging
  Rs 8,715.31, a Rs 20 DP fee is roughly
  **22.9 bps**
  on the sell leg alone, before STT (0.1%), exchange fees, SEBI turnover fees, stamp duty, and
  brokerage.
- That flat charge is several times the entire measured selection edge of +5.3 bps.

---

## THE CENTRAL QUESTION

Both books are now **below** their notional capital. Neither system has yet demonstrated an edge
that survives real Indian statutory friction. The audit must establish whether either architecture
can be repaired, or whether this model class on this market is simply dead.
