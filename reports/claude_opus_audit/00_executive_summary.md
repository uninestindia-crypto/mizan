# QuantOS Institutional Audit — Executive Synthesis

**To:** Founder & Chief Investment Officer
**From:** Executive Quantitative Director — Institutional Audit
**Re:** Adjudication of QuantOS Model Stack and Trading Strategy; Capital Disposition
**Classification:** Board-level. Governance-relevant.

---

## 0. Bottom Line Up Front

QuantOS is a **first-quartile research platform wrapped around a null hypothesis**. The infrastructure — determinism, content-addressed evidence, point-in-time discipline, cost binding at the ledger — is genuinely better than most of what I see at ₹500cr–₹5,000cr systematic desks in India. The predictive layer contains **no exploitable signal**, and the evidence across 104 trials is consistent with the true edge being **zero**, not with a real edge obscured by estimator misspecification.

That distinction is the single most important sentence in this document. You do not have a tuning problem. You have a **hypothesis-generation problem**. No amount of additional work on six technical features computed from OHLCV will change the outcome, because the search space has been exhausted and it is empty.

**Disposition: RESEARCH_ONLY. Enforced at the capital-allocation layer, not the code layer.** Do not deploy. Do not paper-trade as a proxy for deployment. Redirect research capital to the three pivots in §5.

---

## 1. The Executive Verdict

**Is the current 6-feature ridge strategy profitable or viable on NSE equities?**

**No. Not marginally, not conditionally, not "with better parameters." It is not viable, and it cannot be made viable within its current design envelope.**

The verdict rests on three independent lines of evidence that converge:

| Evidence line | Finding | Interpretation |
|---|---|---|
| **Statistical** | Implied IC at hold-2 ≈ **0.009** vs break-even IC ≈ **0.057** | Signal is ~6× too weak to clear costs. Real, but economically inert. |
| **Structural** | Selection edge over equal-weight = **+5.3 bps/period**, implied t ≈ **0.32**, IR ≈ **0.10** | ~370 years to significance. This is indistinguishable from a coin flip. |
| **Longer horizon** | At hold-21, cost hurdle collapses to ~**2.7%/yr** — yet rank IC is **negative in two independent windows with adequate power** | This is *evidence of absence*, not absence of evidence. The most damning finding in the file. |

The hold-21 result is the one that closes the case. When you extend the horizon, the friction wall falls away — the cost objection evaporates. And the signal is *still* not there; it is **negative**. That eliminates the comfortable narrative that "we have alpha, costs are eating it." You do not have alpha at the horizon where costs are survivable. At the horizon where you have a whisper of statistical signal (hold-2), the friction wall is unclimbable.

**You are caught between two walls with no corridor between them.** That is the geometry of the current design, and it is not a bug.

One caveat, and it is the only genuinely open item: the **unreconciled positive gross residual on the hold-2 long-short leg (F-10)**. Before this file is closed, that residual must be reconciled. It may be an accounting artefact. It may be a genuine short-horizon *reversal* signal that the momentum framing has been fighting rather than harvesting. That is a two-week investigation, not a strategy.

---

## 2. The Core Paradox of QuantOS

**You have built a Formula 1 chassis and installed a lawnmower engine.**

This is not a criticism. It is the diagnosis, and it is a far better position to be in than the reverse.

### 2.1 What the engineering has bought you

The platform's rigour is doing exactly what rigour is supposed to do: **it is preventing you from believing things that are not true.** Consider what the audit found:

- The `fit_ridge_classifier` intercept collapse — flagged as "intercept drift," a suspected bug — is in fact an **exact algebraic identity**. Because `StandardizationStateV1` centres on the training partition, $\mathbf{1}^\top\mathbf{X} = \mathbf{0}$ holds exactly, the first normal equation decouples, and $\hat\theta_0 = \bar{y} = (182-229)/411 = -0.114355$. Your fitted value: `-0.114355`. **Seven significant figures.** The system is not broken. It is reporting, with unusual precision, that the class prior is the only thing the model knows.
- The cost ledger binds at 0.224% and refuses to let a gross number masquerade as a net number.
- The multiplicity accounting across 104 trials is the reason you are reading a null result instead of celebrating a false positive.

**Most funds do not fail because their models are bad. They fail because their infrastructure cannot tell them their models are bad.** QuantOS can. That capability is worth more than the model it is currently testing.

### 2.2 Why the paradox exists

Engineering excellence and research excellence are **orthogonal disciplines**, and they attract different failure modes:

- Engineering rewards **determinism, invariants, reproducibility**. QuantOS has these.
- Research rewards **economic imagination, hypothesis diversity, and the discipline to search where others cannot**. QuantOS has searched the single most crowded, most arbitraged, lowest-capacity region of the Indian equity feature space: **six technical indicators derived from public daily OHLCV.**

Every retail screener, every broker's "smart" product, every college quant club, and every one of the ~400 systematic PMS/AIF desks in India computes those same six transforms from the same NSE bhavcopy. **There is no informational asymmetry in that dataset, and therefore there can be no persistent, capacity-bearing edge in it.** The efficient-markets objection is not theoretical here; it is empirical, and your own 104 trials are the evidence.

### 2.3 The corollary — and it is the good news

**The platform is the asset. The model is a disposable test article.**

You have built the thing that is hard to build. Swapping the alpha hypothesis is comparatively cheap. A fund with a broken platform and a working signal will blow up within eighteen months, because it cannot distinguish luck from skill and will size into noise. A fund with a working platform and no signal yet is **one good hypothesis away from a business.**

Your remaining risk is not technical. It is **organisational**: the temptation to keep polishing the engine because the chassis is so satisfying to work on. Resist it.

---

## 3. The Friction Wall

### 3.1 The arithmetic

The 0.224% statutory round-trip verifies exactly:

| Component | Round trip |
|---|---|
| STT (delivery, 0.10%/side) | 20.00 bps |
| NSE transaction charge | 0.59 bps |
| SEBI turnover fee | 0.02 bps |
| Stamp duty (buy only) | 1.50 bps |
| GST 18% on applicable | 0.11 bps |
| **Statutory floor, zero brokerage** | **22.2 bps** |

### 3.2 Why it is insurmountable for daily swing trading

Convert cost into the only currency that matters — **required information coefficient**.

For a cross-sectional strategy, the break-even condition is approximately:

$$
\mathrm{IC}_{\text{required}} \;\approx\; \frac{c_{\text{round-trip}}}{\sigma_{\text{period}} \cdot \sqrt{\text{breadth-adjusted dispersion}}}
$$

At a 2-day horizon on NSE, per-period cross-sectional return dispersion is roughly 2.5–4%. Against a 22 bps floor, break-even IC lands at **≈ 0.057**. Your measured IC is **≈ 0.009**.

**You need six times the signal you have.** For calibration: a *world-class* cross-sectional equity signal runs IC 0.03–0.05. **The 2-day NSE horizon demands an IC that exceeds the best signals in global systematic equity — merely to break even before compounding.** This is not a hurdle you clear with better features. It is a hurdle that is above the ceiling of the discipline.

### 3.3 The wall is taller than 22 bps

The statutory floor is the *least* of it. Real all-in cost:

| Omitted component | Magnitude |
|---|---|
| **DP/demat debit** (₹13–20 + GST per scrip per sell) | On a ₹10,000 leg: **15–20 bps**. On your ₹10L/99-leg book this roughly **doubles** statutory cost. |
| Half-spread × 2 | 4–10 bps NIFTY 50; **20–60 bps** in the 423-name liquid tail |
| Market impact | ~0 at ₹10k/leg; **50–300 bps** at ₹1cr/leg against tail ADV |
| Delay (close-signal → open-fill) | Consumes **30–60% of gross edge** on daily-horizon momentum |
| Non-execution (upper circuit, ASM/GSM call auction, F&O ban) | Systematically removes the **best-performing** names — a negative-selection bias that is invisible in backtest |
| STCG 20% vs LTCG 12.5% | A **7.5 percentage-point** economic wedge on sub-12-month holdings |

**Realistic all-in: 35–60 bps retail-mid; 60–300 bps at institutional size in the tail.**

The DP charge deserves special emphasis because it is the one people forget. It is a **flat fee per scrip per sell**, which means it is a **regressive tax on small position sizes**. Your 99-leg book at ₹10L is paying a cost structure that would be immaterial at ₹10cr and is ruinous at ₹10L. Diversification — normally free — is being charged at 15–20 bps per name.

### 3.4 The strategic implication

The friction wall is not an argument against systematic trading in India. It is an argument against **one specific point in the design space**: high-turnover, small-notional, cash-delivery, cross-sectional daily trading.

Three exits exist, and only three:

1. **Lengthen the horizon** so the fixed cost amortises (hold-21 hurdle is ~2.7%/yr — entirely survivable).
2. **Change the instrument** so STT and DP charges do not apply per-scrip-per-sell (index futures: STT 0.02% sell-side only, no DP charge, no stamp on the same basis).
3. **Find a signal large enough to clear 60 bps.** This does not exist in public daily OHLCV. It may exist in event, flow, or microstructure data.

**Every viable pivot in §5 is an instance of one of these three exits.** That is not a coincidence; it is the structure of the problem.

---

## 4. Key Flaws Identified

I separate these into **defects that must be fixed** (because without them a future false positive will be indistinguishable from a real one) and **design errors that explain the null result**.

### 4.1 Model flaws

**(a) Loss function mismatch — the estimator is not a classifier.**
`fit_ridge_classifier` fits L2-penalised OLS on a ±1 target. This is LDA *up to an affine transformation* (HTF §4.3.2): the **direction** is proportional to the LDA direction, but **the intercept is not the LDA decision boundary**. Squared-error loss on a binary target penalises confident-correct predictions and is not calibrated to probability. Consequence: any threshold applied to the raw score is arbitrary and drifts with class balance. This is the root of the Trial 1/2 degeneracy.

**(b) Negative drift / class-prior contamination.**
With $n_{\mathrm{UP}}=182$, $n_{\mathrm{DOWN}}=229$, the intercept is *exactly* the class imbalance: $\hat\theta_0 = -0.1144$. The model's dominant output component encodes **the training-window base rate**, not conditional information. Every score is shifted by the label imbalance of an arbitrary historical partition. In a cross-sectional long-short book this is harmless (it differences out). In a **long-only or thresholded** book it is a direct, unhedged bet on a stale sample prior. **This must be neutralised — either by demeaning labels cross-sectionally or by ranking scores within each date.**

**(c) Score collapse.**
When features carry no conditional information, $\mathbf{X}^\top\mathbf{y} \to \mathbf{0}$, the penalised solution shrinks $\hat{\boldsymbol\beta} \to \mathbf{0}$, and every score converges to the intercept. The observed collapse is therefore **the correct behaviour of a correct estimator applied to an empty signal.** Do not "fix" it by lowering λ. Lowering λ does not create information; it converts shrinkage into variance and will manufacture spurious cross-sectional dispersion that looks like a signal in backtest and is noise in production.

**(d) The 21-bar window.**
A 21-bar label horizon paired with a training partition of ~411 observations yields an **effective sample size of roughly 20 independent observations** after accounting for overlap. Overlapping labels inflate apparent t-statistics by approximately $\sqrt{h}$ — up to **4.6×** at h=21. Two consequences: (i) any positive result at hold-21 must be discounted by that factor before it is believed; (ii) the *negative* rank IC observed at hold-21 is, if anything, understated in its adverse significance. **Newey-West or block-bootstrap inference is mandatory at any horizon > 1 bar.** Its absence is a P0 defect for future work.

### 4.2 Strategy flaws

**(e) Single-name constraint / breadth starvation.**
The Fundamental Law: $\mathrm{IR} \approx \mathrm{IC} \times \sqrt{\mathrm{Breadth}}$. A concentrated book with IC 0.009 produces an IR indistinguishable from zero **regardless of execution quality**. Breadth is the only free lunch in the equation and the current construction is not consuming it. Conversely, breadth at ₹10L notional collides directly with the flat DP charge (§3.3) — **breadth and cost efficiency are in direct conflict at your current AUM.** This is a capital-structure problem masquerading as a strategy problem.

**(f) Momentum decay and horizon mismatch.**
`ml_equity` turnover is **score-churn driven**: there is no declared holding horizon, no hysteresis, no rebalance band. The strategy therefore *structurally guarantees* hold-2 economics — it lands on the worst point of the cost/signal frontier by default rather than by choice. Meanwhile short-horizon NSE equity is dominated by **reversal**, not continuation, while the momentum framing assumes continuation. This may be why F-10's residual is positive in gross: **the strategy may be systematically on the wrong side of its own best signal.**

**(g) Survivorship and universe-selection bias on the broader universe.**
The "423 liquid names" universe is defined using **present-day** liquidity and listing status. Names that delisted, were suspended, moved to ASM/GSM, or failed the liquidity screen historically are absent. In Indian equities — with high delisting/suspension incidence in the mid- and small-cap tail — this bias reliably contributes **2–6% p.a. of phantom return**, and it is concentrated precisely in the high-volatility names a momentum signal will select. **Any backtest on this universe is upward-biased by an amount comparable to the entire alpha being sought.** A point-in-time universe reconstruction is non-negotiable before any future result is credited.

### 4.3 Governance and evidence-integrity defects — **fix these first**

These are the items I will not sign off without, and they are independent of whether you ever trade this model:

| ID | Defect | Why it is P0 |
|---|---|---|
| **F-1** | Cost ledger does not reconcile: gross (+0.15%) − cost (0.224%) ≠ net (−0.21%). **Three different hold-2 t-stats in circulation: −5.68, −7.85, −1.97.** | If the evidence chain cannot reconcile, **no future result is believable**, positive or negative. This is the highest-priority item in the entire audit. |
| **F-6** | `GOVERNED_BARS_KEY` is populated by nothing — **the governed execution path has never run.** Meanwhile a scheduled ₹10L paper book runs off `research_xs_monthly`, an **ungoverned** package. | The "second system" defect has **recurred in a new location**. This is the failure pattern that precedes real capital loss. Recurrence indicates the fix was local, not structural. |
| **F-7** | `evaluate_fill` marks non-traded positions at `average_price` (cost basis) — the **R-3 mark-to-cost defect the pre-trade path documents as fixed.** | Systematically suppresses reported drawdown and understates risk. Same class of defect, second location. |
| **F-8** | No pre-trade alpha-vs-cost gate anywhere in `governor.py`. | The system can place a trade whose expected alpha is *known* to be below its expected cost. |
| **F-9** | Promotion gates are Sharpe-based. **A monthly strategy's Sharpe cannot be distinguished from zero within a career.** | Structurally under-powered gates will eventually **promote noise**. Replace with a cost-adjusted, multiplicity-corrected, horizon-appropriate deflated-Sharpe test. |

**Pattern observation for the founder:** F-6 and F-7 are *recurrences* of previously-closed defects in new code paths. That is a signal about process, not about code. **Your defect closure is fixing instances rather than eliminating classes.** Governed execution and mark-to-market should be enforced by a single choke-point that is architecturally impossible to bypass, not by convention repeated at each call site.

---

## 5. Top 3 Actionable Pivots

Selection criteria: each pivot must (i) escape the friction wall by construction, (ii) draw on data or structure **not** available in public daily OHLCV, and (iii) be testable on the existing QuantOS platform with modest new plumbing.

---

### **Pivot 1 — Move to the 1–3 month horizon and build a *fundamental-plus-quality* cross-section**
**Horizon: 21–63 trading days. Rebalance: monthly, with hysteresis bands.**

**The economic argument.** At hold-21 your cost hurdle is **~2.7% p.a.** — entirely survivable. The audit already proved the wall falls away here. What is missing is not the horizon; it is that **you brought technical features to a fundamental horizon.** Six OHLCV transforms have no reason to predict 1–3 month returns; accounting and estimate-revision data do.

**What to build:**
- **Quality/profitability:** gross profitability (Novy-Marx), ROIC, accruals, cash-conversion — sourced point-in-time from filings with **explicit reporting-lag stamps** (Indian filing lags run 45–60 days; QuantOS's PIT discipline is exactly the right tool for this).
- **Earnings-estimate revision & post-announcement drift:** analyst revision breadth and the PEAD effect are among the most persistent, most independently replicated anomalies globally, and are **materially stronger in India** than in the US because of thinner analyst coverage.
- **Value, sector-neutralised:** raw value in India is a sector bet on financials and materials. Neutralise it.
- **Low-volatility / defensive:** the low-vol anomaly is robust in Indian equities and improves the risk-adjusted profile of everything it is combined with.

**Why this is the highest-probability pivot:** these effects are documented, economically motivated, capacity-bearing, and — critically — **their edge decays over months, not days**, which makes them structurally compatible with a 22–60 bps cost base.

**Prerequisites (non-negotiable):** point-in-time fundamentals with reporting-lag stamps; **point-in-time universe reconstruction** including delisted/suspended names (fixes §4.2g); sector- and size-neutralisation in portfolio construction.

**Realistic expectation:** IC 0.03–0.05, IR 0.6–1.0 gross of costs, at capacity well beyond ₹10L. **This is the business.**

---

### **Pivot 2 — Change the instrument: express the signal in index/stock futures, not cash delivery**
**Horizon: any. This is a cost-structure arbitrage, not an alpha idea.**

**The economic argument.** The friction wall is composed almost entirely of instrument-specific taxes: STT delivery 10 bps/side (**20 bps round trip**), DP charge per scrip per sell, stamp duty on purchase. **None of these apply in the same form to futures.** STT on futures is 0.02% on the sell side only, there is no DP debit, and margining is capital-efficient.

**What this does to the arithmetic:** the round-trip statutory floor falls from ~22 bps toward **~3–5 bps**, and the DP charge — which was *doubling* your cost at ₹10L — **disappears entirely**. The break-even IC at short horizons drops from ~0.057 to roughly **0.012–0.015**. Your measured IC of 0.009 is still below that, but it moves from *six times away* to *marginally away* — which means it becomes a legitimate research target rather than a fantasy.

**What to build:**
- Re-express any surviving cross-sectional signal within the **F&O-eligible universe** (~180–200 names). Note this universe is *also* far more liquid, which collapses spread and impact costs.
- **Immediately reconcile F-10** — the unreconciled positive gross residual on the hold-2 long-short leg — in the futures cost frame. **If that residual is a genuine short-horizon reversal signal, futures is the only instrument in which it could ever have been profitable.** This is the single highest-expected-value two-week investigation available to you.
- Index-level timing and calendar/basis structures become viable at this cost level and are entirely absent from the current research programme.

**Caveats:** F&O eligibility changes over time — **PIT universe discipline applies here too**; roll cost and basis must be explicitly modelled; leverage requires a hard risk-limit layer *before* any capital is committed.

---

### **Pivot 3 — Acquire a genuine informational asymmetry: event, flow, and microstructure data**
**Horizon: 1–20 days, event-anchored.**

**The economic argument.** The deepest lesson of the 104 trials is not that the model was wrong. It is that **you searched a dataset in which no one can have an edge.** Alpha is compensation for bearing risk others avoid, or for possessing information others lack. Public daily OHLCV offers neither. **The pivot is not to a better model; it is to better data.**

**Indian-specific datasets with real asymmetry, ranked by cost-to-acquire:**
1. **Bulk/block deal disclosures & insider (SAST/PIT) filings** — free from NSE/BSE, structured, and **underexploited because ingestion is tedious.** Insider-buying clusters are one of the most robust predictors in Indian equities.
2. **FII/DII daily flow, index-inclusion and rebalance events, promoter pledge changes, buybacks, corporate actions** — mechanical, calendar-anchored, forced-flow-driven, and **not a crowded systematic trade in India.**
3. **Intraday microstructure** (order-book imbalance, opening-auction dynamics, closing-auction pressure) — this is where the F-10 reversal residual, if it is real, actually lives.
4. **Earnings-call and filing text** — sentiment and language-change signals; higher build cost, longer runway, but genuinely differentiated.

**Why this fits QuantOS specifically:** event-driven signals demand exactly the capabilities you have already built — **strict point-in-time discipline, content-addressed evidence, deterministic replay, and rigorous multiplicity control.** The platform's investment now finally gets a research programme worthy of it. **You built the vault before you had anything to put in it. This pivot fills the vault.**

---

## 6. Sequencing and Conditions of Sign-Off

| Priority | Action | Window |
|---|---|---|
| **0** | **Reconcile F-1.** Three t-stats cannot coexist. Nothing else is credible until the evidence chain closes. | Immediate |
| **0** | **Fix F-6 and F-7 structurally, not locally.** One choke-point for governed execution; one for mark-to-market. Eliminate the *class* of defect, not the instance. | Immediate |
| **0** | **Halt the ungoverned ₹10L paper book.** It is running an ungoverned package and generating evidence that will be mistaken for governed evidence. | Immediate |
| **1** | **Formally kill the 6-feature technical model.** Write the negative result up, archive the 104 trials, and close the file. A documented null is a research asset. | Week 1–2 |
| **1** | **Reconcile F-10 in a futures cost frame.** Highest expected value per hour of any open item. | Week 1–3 |
| **1** | **Replace Sharpe-based promotion gates (F-9)** with cost-adjusted, multiplicity-corrected, horizon-appropriate deflated-Sharpe tests. **Add the pre-trade alpha-vs-cost gate (F-8).** | Week 2–4 |
| **2** | **Build PIT universe reconstruction incl. delisted/suspended names.** Prerequisite to every pivot. | Month 1–2 |
| **2** | **Begin Pivot 1** (PIT fundamentals + revisions, monthly horizon). | Month 2–4 |
| **3** | **Begin Pivot 3** data acquisition (bulk/block/insider ingestion first — free, structured, underexploited). | Month 3–6 |

---

## 7. Closing Judgement

Three things are simultaneously true, and the founder must hold all three:

1. **The strategy is dead.** Not underperforming — dead. It fails at short horizons on cost and at long horizons on signal, and the failure is confirmed by 104 multiplicity-controlled trials. Continuing to tune it is the most expensive thing you could do with the next six months.

2. **The platform is excellent and is your actual asset.** It correctly reported the absence of edge with seven-significant-figure precision, resisted the temptation to manufacture a result, and bound its own costs honestly. Very few teams build this. Nearly every team that skips it eventually loses money it cannot explain.

3. **The governance defects are the real emergency.** F-1, F-6 and F-7 are not academic. F-6 and F-7 are *recurrences* — the same defect classes reappearing in new code paths. That pattern, left uncorrected, is precisely how a firm eventually trades an ungoverned package with real money and marks the position to cost while it does so. **Fix the classes, not the instances.**

The mandate is straightforward: **stop searching for a better model in a dataset that cannot contain one; start searching for better data on a horizon your cost structure can survive.** You have already built the hardest part. Point it somewhere worth pointing it.

**Audit disposition: RESEARCH_ONLY, enforced at the capital-allocation layer. Sign-off conditional on closure of F-1, F-6, F-7.**