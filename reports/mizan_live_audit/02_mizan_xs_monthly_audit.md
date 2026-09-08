# PHASE 2 AUDIT REPORT
## System 2 — Mīzān XS-Monthly Momentum
### Classification: **RESEARCH ARTEFACT — NOT AN INVESTMENT STRATEGY**
### Recommendation: **DO NOT DEPLOY. DE-LABEL AND UNWIND THE NOTIONAL ALLOCATION.**

---

## 0. HEADLINE VERDICT

| Metric | Value | Assessment |
|---|---|---|
| Claimed selection edge | +5.3 bps / 21-session period | t ≈ **0.60** — indistinguishable from zero |
| Rank IC (10y) | **−0.0096** | Wrong sign |
| Rank IC (3y, independent window) | **−0.0087** | Wrong sign, twice |
| Long-short net | −0.063%/period | Wrong sign |
| All-in implementable friction @ ₹10L | **~58–90 bps/period** | **11× to 17× the claimed edge** |
| Net-of-implementation Information Ratio | **≈ −2.1** | Reliable underperformance |
| Sample size needed to validate the edge | **~1,285 rebalances ≈ 108 years** | Test is unfalsifiable in practice |

The research owner (Hermes) already reached the correct conclusion — *"the long-only print is beta + survivorship, not skill… Verdict RESEARCH_ONLY."* **This audit confirms that verdict and finds the situation materially worse than the record states,** because the record's cost model omits the single largest friction line item on a small Indian delivery book.

I also note a **governance drift finding of equal severity to the quant finding**: a screen whose own author stamped it RESEARCH_ONLY, with explicit non-goals of "no promotion, no live-money," has since acquired a capital allocation figure (₹10,00,000), a P&L line, an equity curve, a Windows scheduled task, a dedicated dashboard port, and the label "**System 2**" sitting on Tab 2 next to a genuine system. That is precisely the pathway by which research artefacts get promoted by accident. **Section 6 addresses this.**

---

## 1. IS THE +₹4,223.88 ALPHA, BETA, OR NOISE?

### 1.1 First: reconcile the book

| Line | Value | Derivation |
|---|---|---|
| Notional capital | ₹10,00,000.00 | `NOTIONAL_CAPITAL_INR` |
| Cash | ₹1,37,184.02 | state.json |
| **Deployed capital** | **₹8,62,815.98** | 10,00,000 − 1,37,184.02 |
| **Cash drag** | **13.72% of book uninvested** | |
| Position market value | ₹8,67,039.86 | 10,04,223.88 − 1,37,184.02 |
| Gross gain on deployed | **+0.4896%** | 867,039.86 / 862,815.98 − 1 |
| Gain on total equity | +0.4224% | The 7 bps gap **is** the cash drag |

### 1.2 The elapsed holding period is **one session**

Entry `2026-09-02` → mark `2026-09-03`. That is **1 of 21 sessions = 4.76% of a single rotation**, on a strategy whose backtest needed 115 rotations to reach t = 2.59 on a return that turned out to be pure beta.

**n = 1.** There is no statistical content in this number whatsoever.

For scale: a 99-name equal-weighted NSE mid/small basket has a 1-day return σ of roughly 1.0–1.3%. On ₹8.63 lakh deployed, 1σ ≈ **₹8,600–₹11,200**. The +₹4,224 is **≈ 0.4 standard deviations**. It is not a signal; it is Tuesday.

### 1.3 The reported P&L is **gross of costs that have already been incurred**

`_book_open()` deliberately marks legs gross: *"cost pending, never deducted early."* That is defensible accounting inside a research module. It is **not** defensible as a headline "Net P&L" on a dashboard tab.

| Waterfall on the live book | ₹ | %  of capital |
|---|---:|---:|
| Reported "Net P&L" | **+4,223.88** | +0.4224% |
| Less: statutory round-trip already committed (0.224% × ₹8,62,816) | −1,932.71 | −0.1933% |
| Less: DP debit charges at exit (95 filled scrips × ₹23.60) | −2,242.00 | −0.2242% |
| Less: realistic round-trip spread cost (2 × 7.5 bps, conservative) | −1,294.22 | −0.1294% |
| **True liquidation-equivalent P&L** | **−₹1,245.05** | **−0.1245%** |

**The book is not up ₹4,224. If it liquidated at the next open, it is down roughly ₹1,200.** Under a ₹20+GST DP schedule and a realistic 20 bps round-trip spread on this small/midcap-heavy basket, the loss widens to **−₹3,400**.

### 1.4 The gain is not broad-based

Of the 37 legs visible in the extract, **20 are marked down and 17 up**, for a net of approximately **+₹134**. The headline gain therefore sits almost entirely in the 62 truncated legs — and the single largest visible contributor, **NUVAMA at +₹425, is 10.1% of total reported P&L from a position that is 0.89% of the book.**

That is a right-tail-driven, idiosyncratic P&L from a handful of names. It is the statistical signature of **noise**, not of a diversified edge.

### 1.5 Sector concentration — there is no factor control anywhere in this design

Visible in the extract alone: **NUVAMA, MOTILALOFS, IIFL, MCX, CUB, MAHABANK, LICI, PAYTM, SAGILITY**. That is a heavy, unconstrained **capital-markets / financials cluster**. The code contains:

- no sector cap
- no beta neutralisation
- no volatility scaling
- no correlation constraint
- no ADV / liquidity check at position level
- no single-name cap beyond 1/N

Equal-weighting the top 20% of a trailing-return score in a market where momentum clusters violently by sector produces a **concentrated thematic bet wearing 99 tickers as camouflage**. The diversification is nominal, not economic.

Separately, the book holds **LENSKART, URBANCO, ATHERENERG, OLAELEC, SAGILITY, PAYTM** — recent listings. A 21-session formation window on a stock with limited post-IPO history is not a momentum signal; it is an anchor-investor unwind, a lock-up expiry, and a stabilisation-agent artefact. IPO momentum is a documented trap and the code applies no minimum-listing-history filter beyond `WARMUP_SESSIONS`.

### 1.6 The formal answer: **neither alpha nor beta — it is one session of noise on top of a strategy whose backtested excess was itself noise**

The decomposition from the backtest is unambiguous:

| Component | Sharpe | Reading |
|---|---|---|
| Top-20% momentum long | +0.84 | |
| Market equal-weight, same dates, same costs | +0.83 | |
| **Attributable to stock selection** | **+0.01** | **1.2% of the total** |

98.8% of the Sharpe is the benchmark. And the residual +0.01 is not even a real +0.01 — see §1.7.

Furthermore, both Sharpes are computed against a **zero risk-free rate**. At an Indian 91-day T-bill of ~6.0%:

- Long leg excess Sharpe: (20.7% − 6.0%) / 24.9% = **0.59**
- Market EW excess Sharpe: (20.1% − 6.0%) / 24.2% = **0.58**

The "+0.84 Sharpe" headline is a **raw-return Sharpe in a 6% rate environment**. Restated correctly, the strategy delivers 0.59 — the same as its unselected benchmark, and below a plain NIFTY 500 index fund on a risk-adjusted basis once you account for the small-cap volatility it is carrying.

### 1.7 Statistical power: this test cannot be won

Deriving the dispersion of the selection edge two independent ways:

**Method A — from the long-short diagnostic.** SE(L−S) = 0.00063/0.36 = 0.00175 → σ(L−S) = 0.00175 × √115 = **1.877%/period**. If the bottom quintile mirrors the top around the mean, σ(L−M) ≈ **0.94%/period**.

**Method B — from portfolio theory.** Tracking error of a random ~85-name subset against a 423-name equal-weight parent, at σ_idio ≈ 35% p.a.:
σ_TE = 0.35 × √(1/85 − 1/423) = 3.39% p.a. = **0.98% per 21-session period**.

The two methods agree. Take **σ(L−M) ≈ 0.95%/period**.

| Quantity | Value |
|---|---|
| Selection edge | +0.053%/period |
| σ of the edge | 0.95%/period |
| **t-statistic (n=115)** | **+0.60** |
| **Annualised IR of the selection edge** | **+0.19** |
| n required for t = 2.0 | (2 × 0.95 / 0.053)² = **1,285 periods** |
| **Calendar time required** | **≈ 108 years** |
| Same calc, 3-year breadth window (+10 bps edge) | 361 periods ≈ **30 years** |

**This is the single most important number in the audit.** Even under the most generous framing, the forward paper watch on Port 8091 **can never accumulate enough observations to reject the null**. Running it as a "test" is not a decision procedure — it is a P&L display with an implicit optional-stopping bias. Someone will eventually look at a good month and call it validation.

An annualised IR of +0.19 would not clear the hiring bar for an external manager (≥0.5 minimum). And that +0.19 is **before** implementation costs, which take it to **−2.1** (§2.6).

### 1.8 Where the +5.3 bps actually comes from — and why it is an artefact

Both windows show **negative Rank IC** and **negative long-short**. Those two facts are mathematically incompatible with genuine monotone selection skill. If the momentum rank carried information, IC would be positive and the L−S spread would