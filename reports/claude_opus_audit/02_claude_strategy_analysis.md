# QuantOS Institutional Audit — Phase 2
## Trading Strategy, Transaction Economics & Execution Realism

**Reviewer:** Head of Quantitative Strategy & Execution Economics
**Scope:** Strategy mechanics, cost drag, horizon economics, portfolio construction, execution simulation fidelity
**Verdict:** **NO DEPLOYABLE STRATEGY. RESEARCH_ONLY is the correct disposition and should be enforced at the capital-allocation layer, not merely the code layer.**

---

## 0. Findings Summary

| # | Finding | Severity |
|---|---|---|
| F-1 | Cost ledger does not reconcile: quoted gross (+0.15%) minus quoted cost (0.224%) ≠ quoted net (−0.21%). Three different hold-2 L/S t-stats are in circulation (−5.68, −7.85, −1.97). | **P0 — Evidence integrity** |
| F-2 | At hold-2 the signal is *statistically real and economically irrelevant*: implied IC ≈ 0.009 against a break-even IC of ≈ 0.057. Off by ~6×. | **P0 — Strategy viability** |
| F-3 | At hold-21 cost is **not** the binding constraint (hurdle ≈ 2.7%/yr). Signal absence is. Rank IC is negative in two independent windows with adequate statistical power. | **P0 — Evidence of absence, not absence of evidence** |
| F-4 | Selection edge over equal-weight is +5.3 bps/period, implied t ≈ 0.32, implied IR ≈ 0.10. Would require ~370 years to reach significance. | **P0 — Kill** |
| F-5 | 0.224% omits DP charges, spread, impact, delay, circuit/ASM non-execution, and STCG tax wedge. Real all-in is 35–60 bps at retail-mid size, 60–300 bps at institutional size in the 423-name tail. | **P0 — Cost model understated** |
| F-6 | `GOVERNED_BARS_KEY` is populated by nothing. The governed execution path has **never run live**. Meanwhile a scheduled ₹10L paper book runs off `research_xs_monthly` — an ungoverned package. The "second system" defect has recurred in a new location. | **P0 — Governance** |
| F-7 | `evaluate_fill` values non-traded positions at `average_price` (cost basis), re-introducing the exact R-3 mark-to-cost defect the pre-trade path documents as fixed. | **P1 — Risk integrity** |
| F-8 | No pre-trade alpha-vs-cost gate anywhere in `governor.py`. No horizon declaration, no hysteresis; `ml_equity` turnover is score-churn-driven, structurally guaranteeing hold-2 economics. | **P1 — Mechanics** |
| F-9 | Promotion gates are Sharpe-based. A monthly strategy's Sharpe cannot be distinguished from zero within a career. Gates are structurally under-powered and will promote noise. | **P1 — Governance design** |
| F-10 | Unreconciled residual on the hold-2 long-short leg is large and *positive in gross*. May be concealing a genuine short-horizon reversal signal. Requires reconciliation before the file is closed. | **P1 — Possible unrealised asset** |

---

## 1. The Cost Barrier: Mathematical Proof of the Hurdle

### 1.1 The 0.224% figure verifies — as a *statutory floor only*

| Component | Rate | Round trip |
|---|---|---|
| STT (delivery) | 0.10% buy + 0.10% sell | 20.00 bps |
| NSE exchange transaction charge | 0.00297% / side | 0.59 bps |
| SEBI turnover fee | 0.0001% / side | 0.02 bps |
| Stamp duty | 0.015% buy only | 1.50 bps |
| GST 18% on (txn + SEBI + brokerage) | — | 0.11 bps |
| **Statutory total (zero brokerage)** | | **22.2 bps ≈ 0.224%** ✔ |

**What it excludes, and must not:**

| Omitted component | Magnitude |
|---|---|
| DP / demat debit charge (₹13–20 + GST per scrip per sell) | **On a ₹10,000 leg = 15–20 bps.** On the disclosed ₹10L / 99-leg book this roughly *doubles* the statutory cost |
| Half-spread × 2 | 4–10 bps NIFTY 50; **20–60 bps** in the 423-liquid tail |
| Market impact | ~0 at ₹10k/leg; **50–300 bps** at ₹1 cr/leg against tail ADV |
| Delay / adverse selection (close-signal → open-fill) | 30–60% of gross edge on daily-horizon momentum |
| Non-execution (upper circuit, ASM/GSM call-auction, F&O ban) | Systematically removes the *best* momentum names |
| STCG at 20% vs LTCG 12.5% | An economic, not transactional, penalty on sub-12-month horizons |

**Institutional all-in round trip: 35–60 bps at moderate size; 22.4 bps is the smallest term in the real cost function, not the whole of it.**

### 1.2 The annual hurdle

Fully-invested single sleeve, turnover τ per holding period H:

**Annual cost drag = c · τ · (252/H)**

| H | Trades/yr | Statutory (22.4 bps) | All-in (45 bps) | Sharpe units lost @15% vol (statutory / all-in) |
|---|---|---|---|---|
| 1 | 252 | **56.4%** | 113.4% | 3.76 / 7.56 |
| 2 | 126 | **28.2%** | 56.7% | **1.88 / 3.78** |
| 5 | 50.4 | 11.3% | 22.7% | 0.75 / 1.51 |
| 10 | 25.2 | 5.6% | 11.3% | 0.37 / 0.76 |
| 21 | 12 | **2.7%** | 5.4% | **0.18 / 0.36** |
| 63 | 4 | 0.9% | 1.8% | 0.06 / 0.12 |
| 252 | 1 | 0.22% | 0.45% | 0.01 / 0.03 |

**To net a Sharpe of 1.0 at hold-2 you must produce a gross Sharpe of 2.9 (statutory) or 4.8 (all-in).** No six-feature daily ridge on OHLCV has ever done this. The hold-2 frame is not marginal; it is arithmetically closed.

### 1.3 Break-even IC — the decisive calculation

For a long-only top-quintile screen, expected gross spread over the universe mean is:

**E[r_spread] = IC · σ_cs · λ**, where λ = E[z | top 20%] = φ(z₀.₈)/0.20 = **1.40**

Therefore **IC\* = c·τ / (σ_cs · 1.40)**.

| H | σ_cs (NSE ~420 names, est.) | Break-even IC (τ=1) | Break-even IC (τ=0.4) |
|---|---|---|---|
| 2 | 2.8% | **0.057** | 0.023 |
| 5 | 4.4% | 0.036 | 0.015 |
| 10 | 6.2% | 0.026 | 0.010 |
| 21 | 9.0% | **0.018** | **0.007** |
| 63 | 15.0% | 0.011 | 0.004 |

Now overlay the observed evidence:

- **Hold-2:** t(IC) = +2.34 over n≈1,217 daily cross-sections. With SD(daily IC) ≈ 0.13, SE ≈ 0.0037, so **IC ≈ 0.009**. Required: 0.057. **The signal is real. It is 6.5× too small to pay the toll.** This is the single most important sentence in the audit. A statistically significant t does not confer economic significance; you have discovered a genuine but sub-threshold effect.
- **Hold-21:** observed mean rank IC = **−0.0096**. Required: **+0.018**. The gap is 2.8 IC points *in the wrong direction*.

Reconciliation via the Fundamental Law: with N_eff ≈ 25 independent bets per cross-section (423 names, ~10 sectors, high common-factor loading in India), BR at H=2 = 126 × 25 = 3,150. IR_gross = 0.009 × √3,150 = **0.50**. Subtract 1.88 Sharpe units of cost drag → **net ≈ −1.4**. The observed hold-2 long-only Sharpe of −0.46 sits inside this envelope once partial turnover is allowed. **The theory and the tape agree.**

### 1.4 F-1: The ledger does not close

`+0.15% gross − 0.224% cost = −0.074%`, not `−0.21%`. Either the gross is a conditional/selected figure while the net is unconditional, or costs are being charged more than once per round trip. Separately, the hold-2 long-short diagnostic shows mean net −0.00025 at t=−1.97 over 1,217 periods. A dollar-neutral quintile book at 2-day hold charges **two** legs; at even 60% turnover that is ~27 bps per period, i.e. ~34%/yr. A net of −3.2%/yr against a 34%/yr toll implies a **gross of roughly +31%/yr** on the *reversed* momentum sign.

**I will not sign off on the "no edge" conclusion until the gross → cost → net decomposition is published per leg, per horizon.** Either the cost accounting is wrong (most likely), or you have a large, highly significant short-horizon reversal signal in your data that has been booked as a failure. Both outcomes matter. This is F-10.

---

## 2. The Single-Instrument Constraint: Structural Self-Sabotage

`governed_strategy.py` hard-fails on any symbol ≠ `bundle.evidence.symbol`. `modeling/labels.py` enforces a single-instrument dataset contract. This is defensible as a *governance* boundary and indefensible as a *strategy* boundary.

**2.1 Breadth annihilation.** IR = IC · √BR. Single-name long-or-flat daily: BR = 252/yr. Cross-sectional 423-name monthly with N_eff ≈ 25: BR = 300/yr — comparable in count but *the bets are residual, not directional*, which is the point that matters. Single-name breadth is 1 bet wide and correlated 1.0 with itself; you cannot diversify a timing call on one stock by taking it more often.

**2.2 Alpha and beta are inseparable.** A single-name long-or-flat rule's P&L is `β·r_mkt·(time in market) + idiosyncratic`. Over 2016–2026 the market leg alone produces positive Sharpe. **Every single-name Sharpe in the evidence store is therefore uninterpretable as skill.** A cross-sectional rank is beta-neutral by construction relative to the universe mean; that is precisely why the Hermes market-equal-weight leg was the correct diagnostic and why it destroyed the result.

**2.3 The estimation arithmetic is hopeless.** `ml_equity.RollingRidgeClassifier` fits 7 parameters (6 features + bias) on a 60-row window. Ten observations per parameter, with a per-observation signal-to-noise ratio of ~0.01–0.05. Expected in-sample R² from pure noise ≈ k/n = 0.10 — larger than any true R² on daily equity returns. **The model will confidently fit noise every window and the fit will be uncorrelated with the next window's.** Pooling across 423 names for the same 6 features gives ~25,000 rows per window: a 400× improvement in coefficient precision at zero cost in parameters. This is free, and the single-instrument contract forbids it.

**2.4 The `score_threshold` machinery is a symptom, not a solution.** The docstring's account is diagnostically perfect: with targets in {−1, +1}, a ridge fit on standardized features places its intercept at the mean target, which on a DOWN-skewed name is negative — producing zero UP predictions and `DEGENERATE_RETURN_SERIES`. The fix chosen (a required, per-bundle, validated `score_threshold`) is engineering discipline applied to a modelling error. **A cross-sectional model does not need an absolute threshold because it ranks.** You have built a careful governance apparatus around a defect that the correct portfolio construction eliminates.

**2.5 Multiplicity explodes.** Single-instrument means one trial per name. 101 governed trials were burned reaching a null. With 423 names the campaign is unbounded, each trial evaluated on ~63 sessions where SE(Sharpe) ≈ √(252/63) ≈ 2.0 — a ±2 Sharpe measurement instrument. You are spending scarce multiplicity ordinals on tests that cannot resolve the effect they are looking for.

**2.6 Concentration.** `top_n: 2` produces a two-name book at 50% weight each, directly against `max_position_weight`. Portfolio vol ≈ 30–45% annualised. Even a *true* Sharpe of 0.4 delivers a 25–35% peak drawdown at that vol — outside any institutional mandate.

---

## 3. The Survivorship & Beta Illusion

### 3.1 Why 50 names printed +0.76 Sharpe

The 50-name universe is almost certainly **today's NIFTY 50, backfilled**. That embeds two biases:

- **Survivorship:** names deleted from the index over the decade (Zee, Vedanta-era exits, PSU laggards) are absent. Index turnover runs ~5 names/yr; over 10 years that is ~40–50 name-changes excluded.
- **Inclusion look-ahead (the larger bias):** names *added* during the window are present for their entire pre-inclusion run-up. NIFTY 50 inclusion is itself a momentum-and-size screen applied with hindsight. **You back-tested a momentum strategy on a universe selected by momentum.**

Then the sample: **n = 29 monthly rebalances = 2.4 years.**

SE(SR_monthly) = √((1 + SR²/2)/n) = √((1 + 0.024)/29) = 0.188 → SE(SR_annual) = 0.651.
**Sharpe 0.76 ± 1.28 → 95% CI = [−0.52, +2.04].** Reported t = 1.18 ✔.

Power required to detect a *true* Sharpe of 0.76 at 80%: n = 7.84/0.0480 = **163 months = 13.6 years.** You had 2.4. For a realistic factor IR of 0.3: **87 years.**

> **F-9 restated:** you cannot validate a monthly strategy on its own return series. Ever. Promotion gates keyed to Sharpe/DSR on realised returns are structurally under-powered and will promote noise at a rate governed by how many strategies you test, not by whether any works.

### 3.2 Why 423 names exposed it

Three effects compound: (i) the mega-cap tailwind that drove the 10-name top quintile is diluted across an 85-name quintile; (ii) the mid/small tail is where Indian price momentum is weakest and short-horizon reversal strongest; (iii) survivorship bias *increases* in the wider universe (delistings, suspensions, and ASM/GSM casualties are concentrated below the top 100) — so the paradox is that the wider universe is both more honest about selection and more contaminated in level.

### 3.3 The market-equal-weight leg — the correct and decisive test

The Hermes agent's decision to add the market leg is the single best piece of research judgement in this file. Let me finish the arithmetic it left open.

Primary window, n=115:
- Long leg: μ = 1.742%/mo, SR 0.84 → σ = 7.18%/mo
- Market EW: μ = 1.690%/mo, SR 0.83 → σ = 7.05%/mo
- ρ(long, market) ≈ 0.97 for a top-quintile of the same universe
- **Tracking error = √(7.18² + 7.05² − 2·0.97·7.18·7.05) = 1.75%/mo**

| Metric | Value |
|---|---|
| Selection edge | **+5.3 bps/month** |
| Implied t-statistic | **≈ 0.32** |
| Implied selection IR (annualised) | **≈ 0.10** |
| Months to reach t = 2.0 at this effect size | **≈ 4,490 (374 years)** |

Breadth window (n=33, edge +10 bps, TE ≈ 1.8%): **t ≈ 0.32.** Identical. Two independent windows produce the same non-result.

**Conclusion: the +0.84 Sharpe is 99.4% market beta on a survivorship-biased universe and 0.6% selection, and the 0.6% is indistinguishable from zero.** The long-short leg (t = −0.36 and −0.14) and the negative rank IC in both windows confirm it from the other direction.

### 3.4 The IC test *does* have power — this is evidence of absence

Back out the noise level: mean IC = −0.0096, t = −0.85, n = 115 → **SD(monthly IC) = 0.121**. To detect a respectable IC of +0.035 at t = 2 requires n = (2 × 0.121/0.035)² = **48 months**. You have 115.

> **This is the most important scientific statement available to you: the monthly IC test was adequately powered to detect a real momentum effect, ran for 115 rebalances, and returned a negative point estimate. This is not "we need more data." This is "this signal family does not work on this universe in this window."** Kill it and free the capital and the multiplicity budget. Do not re-parameterise it.

### 3.5 Two benchmark objections that must be resolved before filing

1. **Is the market-EW leg charged the same 0.224%?** Monthly equal-weight rebalancing on 423 names is not free. If the long leg is charged and the market leg is not, the +5.3 bps is *understated* and the true selection edge is negative. State this explicitly.
2. **Equal-weight is not a neutral benchmark in India** — it is a size + illiquidity factor bet that has historically beaten cap-weight. The correct benchmark pair is (a) NIFTY 500 TR cap-weighted and (b) PIT equal-weight of the same universe. Report against both.

---

## 4. Execution Simulation Realism

### 4.1 F-6: The governed path has never executed

The module's own docstring: *"Nothing populates `GOVERNED_BARS_KEY` yet."* Simultaneously, `ml_equity.py` is `research_only = True` and refused by execution surfaces. Yet there is a scheduled Windows task running a paper watch Mon–Fri at 16:00 IST against a ₹10L book with 99 legs, a live dashboard on :8091, and a cash ledger.

**Something is trading and it is not the governed adapter.** It is `research_xs_monthly.paper` — a package created six days ago, outside `modeling/*`, outside the evidence store, with no multiplicity accounting. The defect `governed_strategy.py` was written to eliminate ("the system that executed was not the system that was validated") has reappeared one directory over. The `RESEARCH_PAPER` surface and `ResearchPaperExemptionV1` are a well-designed containment mechanism that this book is routing around entirely, because it never enters the surface at all.

**Required:** every non-zero-notional book, including paper, must be reachable only through `ExecutionSurface`. If a research watch wants to run, it presents a `ResearchPaperExemptionV1` like everything else.

### 4.2 Fill model — absent

Nothing in the extracts shows a fill simulator. The following must exist and be adversarial by default:

| Assumption | Reality on NSE | Required treatment |
|---|---|---|
| Decision at close *t* → fill at open *t+1* | Overnight gap is ~55–65% of daily variance for the index, more for single names, and is **adversely selected**: your momentum score preferentially picks names that gap up | Model open fill explicitly; report gross-at-close vs gross-at-open. Expect 30–60% edge decay |
| "The open" is a tradable price | It is a call-auction print (pre-open 09:00–09:08) with thin depth and no continuous book | Fill at auction price + adverse offset; cap participation at a fraction of auction volume |
| All selected names are purchasable | 2/5/10/20% price bands; ASM/GSM stages force periodic call auctions and 100% margin; F&O ban periods | Simulate rejection. Names locked at upper circuit are *exactly* the ones a momentum screen selects — this is a systematic, one-directional loss |
| Adjusted closes | Signals on adjusted series, fills on unadjusted prices | Single adjusted panel for signal, unadjusted for execution and cash accounting; reconcile |
| T+2 | India is **T+1** since Jan 2023, with T+0 optional | Correct the capital-turn model |
| Integer share flooring is cosmetic | "PTCIL 22685 floors to 0 shares" | This imposes an uncontrolled **anti-price / anti-large-cap tilt** on a ₹10k-per-leg book. Disclosed ≠ neutralised. Either raise leg size or use fractional-equivalent notional accounting in research and disclose the gap |

### 4.3 Turnover mechanics — F-8

`ml_equity.generate_signals` exits a name when it leaves `top_n`. **There is no declared holding horizon.** Turnover is driven entirely by score churn. With a score that is ~99% noise, a top-2 set from a 400-name universe turns over near-completely every session. The strategy therefore realises hold-1/hold-2 cost economics (28–56%/yr drag) while its research documentation discusses monthly horizons. This is a *mechanical* guarantee of loss, independent of signal quality.

**Fix, in order of value:**
1. **Hysteresis bands.** Enter on top-10%, exit only below top-30%. Typically cuts turnover 40–60% for ~5% loss of average signal exposure. On a 21-day book this alone moves the cost drag from 5.4%/yr to ~2.5%/yr.
2. **Turnover-constrained construction.** Replace the `sorted()[:top_n]` sort with an optimiser maximising `wᵀα − λ·wᵀΣw − κ·|w − w_prev|₁`, with κ calibrated to the *all-in* cost including DP and spread. A sort cannot trade off alpha against cost; an optimiser can.
3. **Declared horizon with a minimum hold.** Cost amortisation is a design parameter, not an emergent property.

### 4.4 Risk governor — execution-economics findings

- **F-7 (P1):** `evaluate_fill` computes `gross_pos_val` using `p.average_price` for non-traded positions. The pre-trade path's own comment documents this as defect R-3 and fixes it with marks and a `PORTFOLIO_VALUATION_UNAVAILABLE` refusal. **The post-fill path still marks to cost.** In a rising book this understates leverage; in a falling book it overstates it. Same fix, same file.
- **Correlated non-execution:** `PORTFOLIO_VALUATION_UNAVAILABLE` refuses all BUYs if *any* held name lacks a supplied price. On a 99-leg book, one suspended or no-quote name halts the entire portfolio. Correct posture: stale-mark with an age-dependent haircut, escalate to refusal beyond a staleness threshold, and alert. A data-availability event should not be indistinguishable from a risk event.
- **`trigger_kill_switch` default:** `equity_at_halt` falls back to `_daily_peak_equity`. That records the peak, not the halt level, corrupting post-mortem drawdown attribution.
- **The missing control (highest value in the file):** there is **no pre-trade alpha-vs-cost gate**. Add one:

```
reject if  E[alpha over declared horizon]  <  k · (statutory + DP + spread + impact_estimate)
```
with k ≈ 2. This single check, with `k=2` and a 45 bps all-in estimate, would have rejected **100%** of the hold-2 trades and roughly 95% of the hold-21 trades on the observed IC. It converts an economic truth into an enforceable control.

### 4.5 Capacity valley

At **₹10 L / 99 legs (₹10k each)**: DP charges alone are 15–20 bps round trip and integer flooring distorts the portfolio. Economically dead from *fixed* costs.
At **₹100 cr / 85 names (₹1.2 cr each)**: against the 423-liquid tail's median ADV, participation reaches 5–50%, implying 50–300 bps of impact. Economically dead from *variable* costs.
**The viable notional window for a 400-name monthly book on NSE is roughly ₹25 cr – ₹400 cr.** Neither the current book nor any plausible institutional mandate sits inside it. State the target AUM before the next research cycle — it determines which structures are even admissible.

---

## 5. Turnaround Blueprint

### 5.1 Choose the instrument before choosing the signal

The dominant fact in Indian quant is that **STT is instrument-dependent, and the spread across instruments is an order of magnitude.**

| Product | STT | Approx. all-in round trip (statutory + typical spread) | Cost ratio vs delivery |
|---|---|---|---|
| Equity delivery (CNC) | 0.10% buy + 0.10% sell | **~22 bps + DP + spread → 35–60 bps** | 1.0× |
| Equity intraday (MIS) | **0.025% sell only** | ~4 bps + spread → **10–20 bps** | ~0.3× |
| Index futures | **0.02% sell only** | ~2.5 bps + ~0.2 bps tick → **~3 bps** | **~0.1×** |
| Index options | 0.10% of premium, sell | Low in notional; spread/decay dominate | context-dependent |

*(Rates per the post-Oct-2024 regime; re-verify against current NSE/CBDT circulars before capital deployment.)*

**A signal with a gross Sharpe of 0.5 expressed in index futures nets ~0.48. The same signal in cash delivery at 2-day hold nets −1.4.** You did not have a signal problem at hold-2 so much as an *instrument* problem compounding a marginal signal.

### 5.2 Ranked structures, most-to-least defensible for this firm

**Tier 1 — deploy-able with the existing daily-bar stack**

**(a) Quarterly multi-factor long-only, NIFTY 500, point-in-time.**
Composite of value (EV/EBIT, B/P), quality (ROIC stability, accruals, leverage), low-vol, and 12-1 momentum with a 1-month skip. Sector-neutralised, turnover-constrained to ≤30% one-way per quarter.
Cost: 0.30 × 22.4 bps × 4 = **27 bps/yr** — versus a documented India quality+value composite premium of 200–400 bps/yr. **The hurdle is trivial; this is the only structure in the deliverable list where the cost barrier is a rounding error.**
Realistic target: **IR 0.3–0.6 net vs NIFTY 500 TR.** Not the +0.84 the backtest printed. Anyone promising more is selling survivorship.

**(b) Event and mechanical-flow structures — highest edge-per-unit-of-model-risk at your size.**
Index reconstitution flow (NIFTY 50 / Next 50 semi-annual, MSCI/FTSE India quarterly — flow is *announced and sized*, this is arithmetic not statistics); buyback tender arbitrage (acceptance-ratio math on the retail reservation is reliably lucrative for books under ₹5 cr); rights-entitlement mispricing in the RE trading window; demerger stubs; F&O ban-period entry/exit dislocations. Modest capacity, non-statistical edges, and they suit a ₹1–10 cr book far better than a 400-name factor sleeve does.

**Tier 2 — requires new infrastructure, honestly scoped**

**(c) Cash–futures basis and calendar-roll carry.**
NSE annualised basis has been persistently 4–9% and dislocates around expiry, dividend dates and events. Trades: cash-long/futures-short when annualised basis > funding + all-in costs; calendar-spread mean reversion into last-Thursday expiry; futures/ETF/cash triangle. Genuinely profitable and widely run on NSE. **But be clear internally: this is a financing business returning ~MIBOR + 100–300 bps at Sharpe 2–4 on the spread, not an equity-alpha business.** Needs margin efficiency, SLB access for short cash legs, and intraday risk. Capacity is real.

**(d) Intraday square-off strategies.**
The 0.025% sell-side STT drops the cost floor to ~4 bps, making a 12–15 bps gross signal viable where the delivery version is not. Candidates: opening-auction imbalance reversion, VWAP reversion on high-beta names, expiry-day flow.
**Do not attempt this on a daily-bar research stack.** It requires tick/L1 data, an order-book simulator, latency-aware routing and a different validation frame. This is a different firm, not a different parameter file. Scope it as an 18-month build or not at all.

**Tier 3 — the one thing in your existing evidence worth one more week**

**(e) Reconcile the hold-2 long-short residual (F-10).** If the gross on the reversed-momentum leg is genuinely large, you have found short-horizon reversal — the best-documented anomaly in Indian mid-caps. It is unmonetisable at delivery cost and potentially monetisable at intraday/BTST cost. **One week of cost-ledger reconciliation, then decide.** Do not let this close as a null without checking.

### 5.3 Minimum viable rebuild of the cross-sectional stack

If cross-sectional equity alpha remains the mandate, the contract changes are:

1. **Kill the single-instrument dataset contract for cross-sectional models.** Pool the panel. Keep the governance boundary; change what it is a boundary *around* — bundle identity should be `(universe_id, schema, fit)`, not `(symbol, schema, fit)`.
2. **Point-in-time universe including delisted, suspended and index-deleted names**, with a documented delisting-return convention (−100% or last-traded, stated). Expect the honest backtest to lose 150–400 bps/yr against the current print. That gap *is* the survivorship bias, quantified.
3. **Residualise labels before fitting.** Target = return residual to market + size + sector, so the model learns selection rather than beta. This makes the market-EW leg unnecessary because beta is removed at source.
4. **Horizon 21–63 days, declared, with hysteresis and a minimum hold.**
5. **Cost-aware construction**: optimiser with an explicit L1 turnover penalty calibrated to all-in cost (statutory + DP + spread + impact curve), not a top-N sort.
6. **Promote on IC panels, not Sharpe.** Gate: mean rank IC ≥ +0.03 with t ≥ 3 over ≥60 non-overlapping rebalances, *and* a positive long-short leg after all-in costs, *and* stability across two disjoint sub-periods and two disjoint universe halves. Sharpe/DSR becomes a reporting statistic, not a gate — it lacks the power to be one.
7. **Pre-trade alpha-vs-cost gate in the governor** (§4.4).

### 5.4 Sign-off conditions

I will not endorse capital — including paper capital above zero notional — until:

- [ ] F-1 resolved: gross/cost/net decomposition published per leg per horizon; the three conflicting hold-2 t-stats reconciled to one number with one provenance.
- [ ] F-5 resolved: cost model extended to DP, spread, impact and non-execution; all historical results re-stated.
- [ ] F-6 resolved: no book of any notional reachable except through `ExecutionSurface` with a recorded verdict or exemption. The ₹10L watch either enters the surface or goes to zero notional.
- [ ] F-7 resolved: `evaluate_fill` marks to market, consistent with the pre-trade path.
- [ ] F-3/F-4 accepted in writing: the monthly momentum screen is **killed**, not re-parameterised. Its multiplicity ordinals are recorded as spent.
- [ ] Target AUM declared, and the strategy shortlist filtered against the capacity valley in §4.5.

---

**Closing.** The engineering discipline in this codebase is genuinely above institutional median — the point-in-time bar contract, the surface/verdict ceiling matrix, the refusal to map score sign onto BUY/SELL because only long-or-flat was validated, and the Hermes agent's decision to add the market-equal-weight leg and then publish the result that destroyed its own thesis. That last act is worth more than any Sharpe in the evidence store.

What the discipline is currently protecting is a signal that does not exist at 21 days and is six times too small to pay the toll at 2 days, deployed in the most expensive instrument on the exchange at the worst possible holding period. **Move the horizon out and the instrument down the cost curve, replace Sharpe gates with powered IC gates, put a cost gate in the governor, and point the same rigour at a structure that can clear 45 basis points.**