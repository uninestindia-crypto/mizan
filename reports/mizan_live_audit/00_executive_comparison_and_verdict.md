# QuantOS EXECUTIVE BRIEFING
## Comparative Capital Audit — Mīzān Flagship Alpha (S1) vs. Mīzān XS-Monthly Momentum (S2)

**To:** Founder / Principal
**From:** Office of the Chief Investment Officer
**Classification:** INTERNAL — CAPITAL ALLOCATION DECISION DOCUMENT
**Books under review:** ₹10,00,000 notional × 2 = **₹20,00,000 aggregate paper capital**

---

## 0. EVIDENCE GAP — READ FIRST

**The System 1 audit body was transmitted empty.** I have received only its metadata line: *15-feature ML Ridge, short-term holding, 50+ legs, −₹3,248.74*. I have the full Phase 2 report for System 2.

I am issuing this briefing anyway, because **the allocation decision does not depend on the missing document** — the capital-structure mathematics in Section 3 disqualifies both books in their current form regardless of signal quality. But you must understand the asymmetry: **System 2 has been audited and convicted. System 1 has been indicted, not tried.** Every statement I make about System 1's internals is a *ranked hypothesis with a named diagnostic test attached*, not a finding. Section 4's verdict on S1 is therefore conditional and gated, not terminal.

**Action item zero:** deliver the S1 Phase 2 audit body within 5 business days, or S1 inherits S2's disposition by default.

---

## 1. EXECUTIVE VERDICT

| | System 1 — Flagship Alpha | System 2 — XS-Monthly Momentum |
|---|---|---|
| Architecture | 15-feature ML Ridge, cross-sectional | 21-session trailing-return rank, top quintile |
| Legs | 50+ | 99 (95 filled) |
| Reported P&L | **−₹3,248.74** (−0.325%) | **+₹4,223.88** (+0.422%) |
| Cost convention | **UNKNOWN — must be confirmed** | **Gross. Costs already incurred, not deducted.** |
| Liquidation-equivalent P&L | Unknown | **−₹1,245 to −₹3,400** |
| Validated selection edge | Unaudited | **Rank IC −0.0096 / −0.0087 — negative twice** |
| Net-of-friction IR | Unaudited | **≈ −2.1** |
| **Disposition** | **DO NOT FUND. Retain as gated research.** | **HALT. DE-LABEL. UNWIND.** |
| **Real capital allocated** | **₹0** | **₹0** |

**The headline finding of this briefing:** *there is no winner and no loser.* The apparent ₹7,472 performance gap between the two systems is an **accounting-convention artefact stacked on top of a one-session sample**. Once both books are marked on the same liquidation-equivalent basis, the gap is statistically indistinguishable from zero. Any capital decision made on the basis of "S2 is up and S1 is down" would be a decision made on noise.

---

## 2. HEAD-TO-HEAD: WHY S1 IS "LOSING" AND S2 IS "WINNING"

### 2.1 It is not happening. The comparison is invalid as constructed.

Four distinct reasons, ranked by explanatory power.

#### Driver 1 — Asymmetric cost accounting (dominant, ~50% of the apparent gap)

S2's `_book_open()` marks legs **gross**: *"cost pending, never deducted early."* The audit's waterfall is unambiguous:

| S2 liquidation waterfall | ₹ |
|---|---:|
| Reported "Net P&L" | +4,223.88 |
| Statutory round-trip already committed (0.224%) | −1,932.71 |
| DP debit at exit (95 scrips × ₹23.60) | −2,242.00 |
| Realistic round-trip spread (15 bps) | −1,294.22 |
| **True liquidation-equivalent** | **−₹1,245.05** |

S2 is not up ₹4,224. **It is down ₹1,245, and under a ₹25+GST DP schedule with a 20 bps round-trip spread on this small/midcap basket, down ₹3,400.**

If S1's −₹3,248.74 is stated **net** of frictions — which is the more likely convention for a "Flagship" module — then the two books, properly normalized, sit within a few hundred rupees of one another. **The entire narrative of a winner and a loser may be nothing more than one module deducting costs and the other not.** This single reconciliation is the highest-priority item in this briefing.

#### Driver 2 — n = 1 (the sample contains no information)

S2's elapsed holding period is **one session** — 4.76% of a single 21-day rotation. On a 99-name equal-weighted mid/small basket, 1-day σ ≈ 1.0–1.3%; on ₹8.63 L deployed that is **₹8,600–₹11,200 of daily noise**. The +₹4,224 is **≈ 0.4σ**. It is Tuesday.

Now test the *difference* between the books directly. Both are long-only NSE equity, so they are heavily correlated — assume ρ ≈ 0.8 and σ ≈ ₹10,000 each:

σ(S1 − S2) = √(σ₁² + σ₂² − 2ρσ₁σ₂) = 10,000 × √0.4 = **₹6,325**

The observed gap of ₹7,472 is **1.18 standard deviations. p ≈ 0.24.** By the conventions of every institution that has ever managed money, that is *nothing*. You would need dozens of independent rotations before the difference between these two books carried any evidentiary weight at all.

#### Driver 3 — They occupy opposite points on the return-autocorrelation curve

This is the only *real* structural difference, and it is a factor bet, not a skill difference.

- **S2** is long the **intermediate-momentum factor** (21-session trailing return). On any day when momentum/small-cap is in favour, it prints green.
- **S1**, a short-horizon ML model on daily bars, is almost certainly loaded on the **1–3 day segment of the curve**, which in Indian equities is dominated by **short-term reversal** — the opposite sign.

On 2026-09-02 → 09-03, one of those two factors was in favour. It happened to be momentum. **Tomorrow it flips.** You are not observing two strategies competing; you are observing a coin land once.

#### Driver 4 — Cost velocity (real, persistent, and structurally against S1)

This is the one genuine, non-noise disadvantage S1 carries — and it has nothing to do with its signal. A short-holding-period book pays the full statutory friction stack **4–20× more often per year** than a 21-day rotator. Section 3 quantifies this. It will make S1 look worse than S2 over any measurement horizon regardless of which model is smarter, and it is fatal unless corrected.

---

## 3. THE TRUE ALPHA REALITY

### 3.1 System 2: this is beta, survivorship, and right-tail noise. It is not alpha.

The evidence is conclusive and does not require the live print at all:

| Test | Result | Interpretation |
|---|---|---|
| Rank IC, 10-year | **−0.0096** | Selection is *wrong-signed* |
| Rank IC, 3-year independent window | **−0.0087** | Wrong-signed **twice**, out of sample |
| Long-short net | **−0.063% / period** | The spread trade *loses* money |
| Claimed edge | +5.3 bps, **t = 0.60** | Indistinguishable from zero |
| Friction | **58–90 bps / period** | **11×–17× the claimed edge** |
| Net IR | **≈ −2.1** | Reliable underperformance |
| Rebalances to validate | **~1,285 ≈ 108 years** | **Unfalsifiable in practice** |

A negative Rank IC in two independent windows plus a negative long-short spread is the definition of *no cross-sectional selection skill*. Therefore **every rupee of the positive long-only backtest print is attributable to non-skill sources**:

1. **Market beta.** A ~1.0-beta long-only basket in a rising Indian market prints positive. Free.
2. **Size/small-cap beta.** The top quintile of a 21-day momentum score in India is systematically a small/midcap basket. That is a factor tilt, purchasable in an index fund.
3. **Survivorship.** The research owner (Hermes) named this explicitly: *"the long-only print is beta + survivorship, not skill."*
4. **Right-tail idiosyncratic noise.** Confirmed in the live book: of 37 visible legs, **20 down / 17 up, netting ~+₹134**. The headline sits in the truncated tail, and **NUVAMA alone is 10.1% of total P&L from 0.89% of the book.** That is a lottery ticket, not a diversified edge.
5. **Unconstrained sector concentration.** NUVAMA, MOTILALOFS, IIFL, MCX, CUB, MAHABANK, LICI, PAYTM, SAGILITY — this is a **capital-markets/financials thematic bet wearing 99 tickers as camouflage.** There is no sector cap, no beta neutralisation, no vol scaling, no correlation constraint, no ADV check.

**Verdict: S2's return is beta you can buy for 25 bps p.a. in an ETF, being sold to you at 7–9% p.a. of friction, with a negative-signed stock selection overlay attached.**

### 3.2 System 1: inversion or noise? Here is the decision tree.

I cannot answer this without the audit. But I can tell you exactly how to answer it in 48 hours, and I can tell you that **the answer materially changes S1's value.**

**Run this single diagnostic: compute the live and out-of-sample Rank IC of the S1 score against realized forward returns, at h = 1, 2, 3, 5, 10, 21 sessions.** Three outcomes:

| Outcome | Diagnosis | Implication |
|---|---|---|
| **IC significantly negative** (t < −2.5) at the traded horizon | **TRUE FEATURE INVERSION** | **This is the good outcome.** A robustly wrong-signed model is a wrong-signed *edge*. Sign flips are free. |
| **IC ≈ 0** (\|t\| < 1.5) | **Null signal bleeding friction** | −₹3,248.74 is pure cost. The model has no content. Rebuild or retire. |
| **IC positive but < friction** | **Real but sub-scale edge** | Signal survives; the *cost architecture* is what's killing it. Fixable via Section 5. |

**My prior, ranked, on why inversion is plausible:**

1. **Horizon mismatch (most likely).** If the 15 features are momentum-family (ROC, RSI, MA-distance, breakout) but the model is *held* 1–3 days, you are systematically buying short-term winners at exactly the horizon where Indian equities mean-revert. You have built a reversal-harvesting machine and pointed it backwards. **This is the single most common failure in retail-scale Indian ML equity models, and it is a one-line fix.**
2. **Label-join lag error.** Feature matrix at *t* joined to a return window that includes *t* → the model learns to "predict" the past. Backtest looks superb; live is inverted or null. **Control test: shuffle labels. IC must collapse to 0. If it doesn't, you have leakage.**
3. **Ridge sign instability under multicollinearity.** Fifteen features on daily OHLCV are not fifteen independent signals — they are perhaps three latent factors observed fifteen ways. Ridge shrinks but does not *select*; under near-collinearity, coefficient signs flip between folds and the ensemble sign becomes effectively arbitrary. **Diagnostic: report the condition number of the feature covariance matrix and the sign-stability of each coefficient across walk-forward folds.**
4. **Full-sample standardisation.** If features are z-scored over the entire history rather than **cross-sectionally within each date**, you have injected look-ahead into every single observation.

**Critically: option 1 is materially more attractive than anything in System 2.** A wrong-signed model with a real IC is a working model with a bug. A model with IC = −0.0096 and a −2.1 IR, as in S2, is a model with nothing in it. **This is the core reason S1 survives this briefing and S2 does not.**

---

## 4. THE CAPITAL STRUCTURE PROBLEM OF ₹10 LAKH

This section is the load-bearing wall of the entire briefing. It applies irrespective of signal quality.

### 4.1 The Indian friction stack on delivery equity

| Component | Basis | Round-trip |
|---|---|---|
| STT | 0.1% each side, delivery | **0.200%** |
| Exchange transaction charges (NSE) | ~0.00297% / side | 0.006% |
| Stamp duty | 0.015%, buy only | 0.015% |
| SEBI turnover fee + GST | — | ~0.003% |
| **Ad-valorem subtotal** | | **~0.224%** ✔ *matches audit* |
| **DP debit charge** | **FLAT ₹20 + 18% GST = ₹23.60 per scrip, per sell** | **scales with LEGS, not capital** |
| Bid-ask spread + impact (small/mid) | 7.5–12.5 bps / side | 0.15–0.25% |

> *Verify DP schedule against your actual contract note — it ranges ₹13.50 to ₹25+GST by DP. The conclusion strengthens at the higher end.*

### 4.2 The flat-fee tyranny — where the two books diverge

| | System 1 (50 legs) | System 2 (99 legs) |
|---|---:|---:|
| Deployed | ~₹10,00,000 | ₹8,62,816 |
| **Average ticket** | **₹20,000** | **₹8,716** |
| DP charge as % of position | **11.8 bps** | **27.1 bps** |
| Total DP cost / rotation | ₹1,180 | ₹2,336 |
| Ad-valorem | 22.4 bps | 22.4 bps |
| Spread + impact | ~15 bps | ~15–25 bps |
| **All-in per rotation** | **~49 bps** | **~60–75 bps** ✔ *matches audit* |

**The DP debit charge is the entire problem, and it is invisible in every backtest ever written that models costs in basis points.** It is a flat rupee fee. Its percentage weight is *inversely proportional to ticket size*. At ₹8,716 a leg, you are paying **27 bps for the privilege of a debit instruction** — more than the entire STT bill.

### 4.3 The Minimum Viable Ticket — a hard engineering constraint

Set a policy that no single fixed fee may exceed 5 bps of a position:

**Minimum ticket = ₹23.60 / 0.0005 = ₹47,200**

| Fee tolerance | Min ticket | **Max legs at ₹10 L** |
|---|---:|---:|
| ≤ 3 bps | ₹78,667 | **12** |
| ≤ 5 bps | ₹47,200 | **21** |
| ≤ 10 bps | ₹23,600 | **42** |
| 27 bps *(S2 today)* | ₹8,716 | 115 |

**At ₹10 Lakh on NSE delivery, your book is structurally capped at ~20 names. Ninety-nine legs is not diversification; it is a fee-maximisation algorithm.**

### 4.4 Why high diversification on a small book is a *mathematical* penalty

The marginal leg buys variance reduction that decays as **1/N²**, while adding **linear** cost. At an average pairwise correlation of ρ ≈ 0.35 for Indian equities:

| Legs | Portfolio σ (relative) | DP cost / rotation |
|---|---:|---:|
| 20 | √(0.35 + 0.65/20) = **0.6185** | ₹472 |
| 99 | √(0.35 + 0.65/99) = **0.5971** | ₹2,336 |

**Going from 20 legs to 99 legs buys a 3.5% relative reduction in volatility and costs 4.95× the fee load.** You are paying ₹1,864 extra per rotation — 21.6 bps — for a risk benefit that rounds to zero, because beyond ~20 names in a single-country long-only equity book, **the residual variance is systematic and cannot be diversified away at any leg count.**

There is a further, compounding penalty: **fragmentation causes cash drag.** S2 shows **13.72% of the book uninvested (₹1,37,184)** and 4 unfilled scrips — a direct consequence of integer-lot rounding on ₹8,716 tickets against ₹500–₹2,000 share prices. That drag is exactly the **7 bps gap** between S2's gross-on-deployed (+0.4896%) and gross-on-equity (+0.4224%). You are simultaneously over-diversified *and* under-invested.

### 4.5 Cost velocity — the number that condemns System 1

Annual friction = per-rotation cost × rotations per year. S1's holding period is unstated; here is the sensitivity, at 49 bps/rotation:

| S1 holding period | Rotations / yr | **Annual friction drag** | Verdict |
|---|---:|---:|---|
| 1 day | 250 | **122.5%** | Physically impossible |
| 3 days | 83 | **40.7%** | Impossible |
| **5 days** | **50** | **24.5%** | **Requires a 24.5% gross alpha to break even** |
| 10 days | 25 | 12.3% | Implausible |
| 21 days | 12 | 5.9% | Borderline survivable |
| S2 (21-day, 99 legs) | 12 | **7.2–9.0%** | Requires 7–9% gross alpha; measured edge is 5.3 bps |

**Structural theorem for your book:** the irreducible STT floor alone is 20 bps round-trip. A strategy rotating 50×/year pays **10% p.a. in STT before touching a spread, a DP fee, or a broker.** *No long-only Indian delivery strategy at ₹10 Lakh with weekly turnover can survive its own tax code.* The Indian statutory regime enforces a **minimum viable holding period**, and it is roughly three weeks.

**Conclusion of Section 3:** S1's disease is **frequency**. S2's disease is **fragmentation**. Both are terminal in their current specification, and neither is a signal problem.

---

## 5. DEFINITIVE CAPITAL ALLOCATION VERDICT

### 5.1 The allocation

| Book | Real capital | Notional | Disposition |
|---|---:|---:|---|
| **System 2 — XS-Monthly Momentum** | **₹0** | **₹0** | **HALT & UNWIND.** De-label from "System 2." Remove `NOTIONAL_CAPITAL_INR`. Kill the scheduled task, the dashboard tab, the equity curve. Re-tag `RESEARCH_ONLY`. Archive as a **negative result of genuine value** — you now know 21-day naïve momentum ranking has a *negative* IC on your universe. That is a real finding. Write it down and never re-test it. |
| **System 1 — Flagship Alpha** | **₹0** | **₹10,00,000 (shadow, unlabelled)** | **DO NOT FUND. RETAIN AS GATED RESEARCH.** It is the only asset here with a plausible structural path to alpha: a learned, multi-feature, cross-sectional model whose failure modes are *diagnosable and fixable*. Demote from "Flagship." Re-tag `CANDIDATE`. Subject to the gates in §7. |
| **Aggregate real deployment** | **₹0 of ₹20,00,000** | | |

### 5.2 On merging — the answer is an unqualified no

Combining signals is only valid when **both sleeves carry independently validated, positive, out-of-sample IC with low mutual correlation.** Neither condition holds:

- S2's IC is **negative in two independent windows**. Adding it to any other signal **subtracts** expected return.
- S1's IC is **unmeasured**.
- The two are **highly correlated by construction** — both long-only NSE equity, both drawing from an overlapping mid/small universe, both loading on the same market and size factors. Blending them diversifies almost nothing.
- Merging would produce a **~150-leg book at ₹6,700 per ticket**, driving the DP charge to **35 bps of position**. You would double the friction and dilute the signal.

**A blend of a negative-IC signal and an unmeasured signal is not a portfolio. It is two mistakes sharing a custody account.**

### 5.3 What to do with the founder's actual money in the interim

I will not leave you without a recommendation. If you want Indian equity exposure today:

**Buy the beta directly.** S2's entire realised return — market beta plus a small/mid momentum tilt — is available in a **Nifty Midcap 150 Momentum 50 index fund or a broad Nifty 50 index fund at ~20–30 bps p.a. total cost.** You are currently paying **7–9% p.a. in friction (S2)** or **potentially 24%+ p.a. (S1)** to manufacture, badly and with negative selection skill, a return stream you can buy for a quarter of a percent.

**That comparison — 25 bps versus 900 bps for the same exposure — is the single most important sentence in this document.** Until a system clears the gates in §7, the index fund *is* the benchmark, and it is winning by roughly 8 percentage points a year before a single stock is picked.

---

## 6. TOP 3 ENGINEERING & QUANTITATIVE UPGRADES

### UPGRADE 1 — Re-architect around a cost-aware objective and a hard leg budget
*Converts a fee-maximisation engine into an executable portfolio. Highest immediate ROI.*

**Quant changes:**
- Replace "rank → equal-weight top quintile" with a constrained optimiser: **max wᵀα − λwᵀΣw − c(w, w_prev)**, where `c` explicitly includes the **flat DP term** (a cardinality-linked, non-convex cost — approximate with an L0 penalty or a hard cardinality constraint).
- **Hard cap: N ≤ 20 legs at ₹10 L. Minimum ticket ₹45,000.** Non-negotiable, machine-enforced at order generation.
- **Turnover hysteresis / no-trade band:** a name enters at rank ≤ N, exits only at rank > 1.5N. Typical empirical effect: **40–60% turnover reduction for <10% of gross alpha.** This is the highest Sharpe-per-line-of-code change available to you.
- **Minimum holding period floor of 15 sessions**, enforced in the scheduler, derived directly from §3.5.
- Size by **inverse-volatility**, not 1/N, capped at 1.5 × (1/N).

**Engineering changes:**
- **Kill gross P&L reporting permanently.** Accrue statutory + DP + a modelled spread at fill. The dashboard shows exactly three numbers: **Gross → Net → Liquidation-Equivalent NAV.** No "Net P&L" label may ever again sit above a gross figure.
- **Eliminate cash drag by design:** integer-lot solver targeting ≥98% deployment, or an explicit, sized cash sleeve. 13.72% idle capital must be a *decision*, never a rounding residue.

**Expected effect:** friction from **60–75 bps → ~33–36 bps per rotation**; annual drag from **7–9% → ~4%**.

---

### UPGRADE 2 — Fix the signal science: sign, horizon, and a pre-registered validation protocol
*This is the upgrade that determines whether you have a business.*

**Immediate (48 hours), on System 1:**
- **Horizon scan.** Rank IC of every one of the 15 features at h = 1, 2, 3, 5, 10, 21, 63 days. Expect **negative IC at h = 1–3 (short-term reversal)** and **positive at h = 21–126 (intermediate momentum)** in Indian equities. If S1's features are momentum-family but held 1–3 days, **you have found the inversion, and the fix is to flip the sign or move the horizon.**
- **Leakage control.** Shuffle the labels. IC must collapse to zero. If it does not, your feature/label join has look-ahead and every backtest to date is void.
- **Sign-stability report.** Condition number of the feature covariance matrix; per-coefficient sign consistency across walk-forward folds. Ridge on 15 collinear OHLCV derivatives will produce unstable signs — **replace with cross-sectional-within-date z-scoring → PCA/orthogonalisation or elastic-net selection.**

**Structural:**
- **Purged, embargoed walk-forward CV** (López de Prado) as the *only* permitted validation. No random K-fold on time series, ever.
- **Point-in-time universe reconstruction** with delistings, index-constituent history, and decision-time eligibility screens (ADV, circuit filters, ASM/GSM, T2T). This kills the survivorship bias Hermes correctly identified in S2.
- **Pre-registered promotion criteria — write these down before you look at the results:**
  1. Out-of-sample Rank IC **> +0.02** with **t > 3.0**
  2. Positive top-decile spread **net of the full §3.1 cost stack**
  3. Survives a regime split (2015–2020 vs. 2020–2025) with the same sign
  4. Positive alpha versus a **matched benchmark** (Nifty Midcap 150 / Smallcap 250), not versus zero

**Point 4 is the one that kills System 2 and will kill most of what you build next. Institutionalise it now.**

---

### UPGRADE 3 — Impose a risk model and a machine-enforced promotion firewall
*Addresses the governance drift finding, which the S2 audit correctly rates as equal in severity to the quant finding.*

**Risk model (quant):**
- Build or license a factor model: **market, size, value, momentum, sector.** Attribute daily P&L into **market / size / sector / residual** — this is the only mechanism that will ever answer "is this alpha or beta?" With n = 1 and no attribution, α and β are mathematically unidentifiable, which is precisely why S2's +₹4,224 was ambiguous.
- Hard constraints: **sector ≤ 25%** (S2's unconstrained financials/capital-markets cluster is exhibit A), **beta 0.9–1.1**, **single name ≤ 1.5/N**, portfolio vol targeted not accidental.
- **Capacity guards:** position ≤ 5% of 20-day ADV; exclude ADV < ₹5 cr, price < ₹50, and all ASM/GSM/T2T names at decision time.

**Governance firewall (engineering) — the fix for how a `RESEARCH_ONLY` artefact acquired ₹10,00,000, a P&L line, an equity curve, a scheduled task, a dashboard port, and the name "System 2":**

Implement a machine-enforced artefact lifecycle:

`RESEARCH` → `CANDIDATE` → `SHADOW` → `PILOT` → `CORE`

with the following **hard interlocks in code, not policy**:

| Tag | May have `NOTIONAL_CAPITAL_INR`? | Scheduler entry? | Dashboard tab? | "System N" label? | Real capital? |
|---|---|---|---|---|---|
| RESEARCH | **NO — throws** | NO | NO | **NO** | NO |
| CANDIDATE | Shadow only | Yes | Research tab only | NO | NO |
| SHADOW | Yes, notional | Yes | Yes, watermarked | NO | NO |
| PILOT | Yes | Yes | Yes | Yes | **Capped, ≤ 10%** |
| CORE | Yes | Yes | Yes | Yes | Yes |

Promotion requires a **signed gate record containing the pre-registered §Upgrade-2 statistics**. No exceptions, no manual overrides, no "it's just paper."

**Two additional integrity guards:**
- **System-clock assertion.** The live book is timestamped **2026-09-02 / 2026-09-03**, which is forward-dated. Either the harness runs on a shifted/simulated clock — in which case this is *not* a live paper run and must not be described as one — or the timestamps are wrong. **Resolve before any print from either system is treated as evidence.**
- **Realistic fill model:** VWAP-with-slippage, partial fills, and a daily three-line reconciliation (Gross → Net → Liquidation-Equivalent).

---

## 7. 90-DAY GATED ROADMAP

| Window | Gate | Pass condition | Fail action |
|---|---|---|---|
| **Days 1–5** | **G0 — Evidence** | S1 Phase 2 audit body delivered. S2 fully de-labelled and unwound. Clock discrepancy resolved. Both books restated on liquidation-equivalent NAV. | S1 inherits S2's disposition. |
| **Days 6–20** | **G1 — Signal triage** | S1 horizon scan + leakage control + sign-stability report complete. A defensible answer to *inversion vs. null* is on paper. | If IC ≈ 0 with no recoverable horizon: **retire S1.** |
| **Days 21–45** | **G2 — Validation** | Pre-registered criteria met: OOS Rank IC > +0.02, t > 3.0, regime-split stable, positive net-of-cost decile spread, positive alpha vs. matched benchmark. | Return to research. No capital. |
| **Days 46–60** | **G3 — Implementability** | Rebuilt under Upgrade 1: ≤ 20 legs, ≥ ₹45k tickets, ≥ 15-session hold, hysteresis, ≥ 98% deployed. **Net-of-full-cost IR > 0.7 over 5 years.** | Return to research. |
| **Days 61–90** | **G4 — Shadow** | 60 sessions of shadow-paper tracking backtest within tolerance; slippage attribution within model. | Extend shadow. |
| **Day 90+** | **G5 — Pilot** | **First real capital: ₹1,00,000 (10% of one book).** Scale only on realised, cost-verified, benchmark-relative performance. | — |

**Real money before G5 is not a strategy decision. It is a governance failure.**

---

## 8. CIO CLOSING NOTE

Founder — three things, plainly.

**First, you have not built a losing system and a winning system. You have built two books whose one-day P&L difference is 1.18 standard deviations, one of which reports gross and one of which may report net.** The temptation will be to fund the green number. The green number is red once it is marked to liquidation. Resist it. **This exact instinct — allocating to the tab that is up — is the mechanism by which research artefacts become live losses.**

**Second, the binding constraint on this enterprise is not model quality. It is arithmetic.** At ₹10 Lakh on NSE delivery, a flat ₹23.60 DP fee and a 20 bps STT floor jointly dictate that your book holds **roughly twenty names for roughly a month**. Every architecture that violates that envelope — 99 legs, or weekly rotation — is disqualified before a single feature is engineered. Design *inside* the envelope and a modest edge survives. Design outside it and a brilliant edge dies anyway.

**Third — and this is the finding I want you to sit with — the most valuable output of this entire audit cycle is Hermes's own `RESEARCH_ONLY` verdict on System 2, which was correct, was written down, and was then quietly overridden by the accumulation of infrastructure: a capital figure, a scheduled task, a dashboard port, a tab number.** Nobody decided to promote System 2. It was promoted by convenience. The engineering firewall in Upgrade 3 exists so that the *next* correct call your research process makes cannot be undone by a config file.

**Deploy ₹0. Fix the arithmetic. Then measure the signal. In that order.**

*— Office of the CIO*