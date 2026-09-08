# Independent CIO / Quant Risk Second Opinion

## Executive conclusion

Claude reached the correct **capital decision**—fund neither strategy—but several important parts of the reasoning are overstated or technically wrong.

My conclusions are:

1. **The ₹7,472 live P&L gap cannot support a winner/loser decision.** However, Claude’s specific \(p \approx 0.24\) calculation is unsupported because the books were observed over different windows and the volatility/correlation inputs were assumed.
2. **System 2’s base liquidation waterfall is arithmetically correct:** approximately **−₹1,245** under the stated 15 bp spread assumption.
3. **The stated −₹3,400 stress case is not supported by Claude’s stated ₹25+GST DP fee and 20 bp spread.** Those inputs produce approximately **−₹2,237**, not −₹3,400.
4. **System 1 is not merely “indicted.”** The supplied evidence says it was corrected and then refuted out of sample, with essentially zero selection edge. It should not retain privileged “candidate” status.
5. **System 1 also appears to have approximately 100 positions, not 50.** Its ₹1,072.65 entry fees divided by the roughly ₹10–₹11 fee per holding strongly imply about 100 entries. It therefore suffers from both excessive frequency and excessive fragmentation.
6. **Neither model has investable alpha.** This is not only a transaction-cost problem. Cost reduction cannot manufacture a signal where benchmark-relative selection edge is zero.
7. **Allocate ₹0 of real money to both. Halt System 2 and suspend the existing System 1 paper implementation.**

---

# 1. Critical review of Claude’s findings

## 1.1 “There is no winner and no loser”

I would restate this more precisely:

- **There is no statistically defensible live winner.**
- **There are two research failures for capital-promotion purposes.**

Thus, I agree that the raw ₹7,472.62 difference should not drive allocation. I disagree with the softer implication that one model may remain an attractive salvage candidate while the other is uniquely defective.

The supplied System 1 record already contains decisive negative evidence:

- Eight features showed significantly negative in-sample IC.
- The 1-session implementation returned −41.6%, with reported friction drag of 122% annualized.
- The 10-session implementation returned −31.6% versus Buy & Hold +22%.
- Most importantly, the corrected model was tested on 378 names outside the original hypothesis-generating universe:
  - Top-quintile return: +0.6528% per period
  - Equal-weight benchmark: +0.6550%
  - Selection edge: **−0.000022**, or about **−0.22 bp per period**
  - \(t=-0.07\)
  - Selection Sharpe: −0.01

That is not an unaudited model awaiting a simple sign fix. It is an empirically null stock selector.

### My verdict on the phrase

> “No winner” is correct.  
> “No loser” is incorrect. Both lose the promotion test.

---

## 1.2 Claude’s \(p \approx 0.24\) comparison is false precision

Claude assumes:

- \(\sigma_1 \approx \sigma_2 \approx ₹10,000\)
- correlation \(\rho \approx 0.8\)
- a common one-session measurement window

Then:

\[
\sigma(S1-S2)
=10{,}000\sqrt{2-2(0.8)}
=₹6{,}325
\]

and:

\[
z = ₹7{,}472/₹6{,}325 \approx 1.18
\]

A two-sided normal \(p\)-value of approximately 0.24 is arithmetically consistent with those assumptions. But the assumptions are not established.

Specifically:

- System 1 was opened on 2026-08-31 and reports four completed sessions.
- System 2 was opened on 2026-09-02.
- Some System 2 legs remain marked `asof_date: 2026-09-03` even though the state contains 2026-09-04 runs.
- The portfolios do not appear to cover the same return interval.
- No empirical daily covariance series was supplied.
- Their position sets, cash levels and factor exposures differ.

A cumulative P&L gap over unmatched intervals cannot be assigned a valid paired-return \(p\)-value using guessed covariance.

The correct conclusion is simply:

> The live samples are too short, stale or unmatched, and too dominated by market/factor noise to support comparative inference.

No exact \(p\)-value should be reported.

---

## 1.3 System 2 liquidation waterfall: base case verified

Inputs:

- Entry capital deployed: ₹8,62,815.98
- Reported gross gain: ₹4,223.88
- Statutory round-trip rate: 0.224%
- Filled positions: 95
- DP charge: ₹23.60 per filled scrip
- Assumed round-trip spread/slippage: 15 bp

### Calculation

#### Statutory costs

\[
₹8{,}62{,}815.98 \times 0.00224
= ₹1{,}932.71
\]

#### DP charges

\[
95 \times ₹23.60 = ₹2{,}242.00
\]

#### Spread/slippage

\[
₹8{,}62{,}815.98 \times 0.0015
= ₹1{,}294.22
\]

#### Liquidation-equivalent P&L

\[
₹4{,}223.88
-₹1{,}932.71
-₹2{,}242.00
-₹1{,}294.22
=
\boxed{-₹1{,}245.05}
\]

Claude’s base arithmetic is correct.

Minor refinements would calculate sell-side taxes on sale value rather than entry value, but the difference is only a few rupees here.

### Important terminology correction

Only the buy-side costs are already economically incurred at entry. Sell-side statutory charges, DP fees and exit impact are **liquidation liabilities**, not yet incurred costs. Deducting them is appropriate for liquidation-equivalent NAV, but “already incurred” is imprecise.

---

## 1.4 The −₹3,400 stress case is not supported by the stated assumptions

Claude invokes:

- DP charge of ₹25 + GST = ₹29.50
- Round-trip spread of 20 bp

The calculation is:

\[
95 \times ₹29.50 = ₹2{,}802.50
\]

\[
₹8{,}62{,}815.98 \times 0.0020 = ₹1{,}725.63
\]

Therefore:

\[
₹4{,}223.88
-₹1{,}932.71
-₹2{,}802.50
-₹1{,}725.63
=
\boxed{-₹2{,}236.96}
\]

Not −₹3,400.

To reach approximately −₹3,400:

- with ₹23.60 DP fees, spread/impact must be approximately **40 bp round trip**; or
- with ₹29.50 DP fees, spread/impact must be approximately **33.5 bp round trip**.

Those may be defensible stress assumptions for less-liquid names, opening-auction execution, limit moves and market impact, but they are not the 20 bp case Claude described.

### Corrected range

| Assumption | Liquidation-equivalent P&L |
|---|---:|
| ₹23.60 DP, 15 bp spread | **−₹1,245** |
| ₹23.60 DP, 20 bp spread | **−₹1,676** |
| ₹29.50 DP, 20 bp spread | **−₹2,237** |
| ₹29.50 DP, ~33.5 bp spread | **~−₹3,400** |

---

## 1.5 System 1 is probably not stated on a fully net liquidation basis

Claude speculated that System 1 might already be net of all costs. The state argues otherwise:

- `total_fees = ₹1,072.65`
- Every open position contains an `entry_fee`
- No positions have been closed
- `realized_pnl = 0`
- Exit DP and exit execution costs therefore appear unreserved

System 1’s equity seems to deduct entry fees but not prospective exit costs.

Furthermore, the typical entry fee in the sample is approximately ₹10–₹11. Dividing:

\[
₹1{,}072.65 / ₹10.7 \approx 100
\]

This strongly suggests approximately 100 positions, not 50. With current holding market value:

\[
₹9{,}96{,}751.26 - ₹1{,}45{,}520.31
= ₹8{,}51{,}230.95
\]

A rough liquidation reserve for about 100 names would be:

- Sell statutory charges: approximately ₹850–₹950
- DP fees: approximately ₹2,360
- Exit half-spread at 7.5 bp: approximately ₹638

Total additional exit reserve: approximately **₹3,850–₹3,950**.

That would place System 1 near **−₹7,100 liquidation-equivalent**, before reserving any unmodeled buy-side implementation shortfall.

Therefore, Claude’s suggestion that normalizing accounting could reduce the two books to “within a few hundred rupees” is not supported by the supplied state. It may instead leave System 2 ahead by several thousand rupees—but still over an incomparable, statistically useless live sample.

---

# 2. The physics of Indian delivery trading at ₹10 lakh

## 2.1 DP fee arithmetic

For System 2:

- Filled names: 95
- Deployed capital: ₹8,62,815.98
- Average filled ticket:

\[
₹8{,}62{,}815.98/95 = ₹9{,}082
\]

DP cost as a percentage of the average filled ticket:

\[
₹23.60/₹9{,}082 = 0.260\%
\]

or:

\[
\boxed{26.0\text{ bp}}
\]

Claude’s 27.1 bp uses deployed capital divided by all 99 selected names, including four zero-share positions. The correct filled-ticket figure is about 26 bp. The economic conclusion remains unchanged: aggregate DP cost exceeds the roughly 20 bp round-trip STT bill.

On deployed capital, System 2’s approximate full-rotation costs are:

| Component | Cost |
|---|---:|
| Statutory | 22.4 bp |
| DP | 26.0 bp |
| Spread/impact assumption | 15.0 bp |
| **Total** | **63.4 bp** |

On total ₹10 lakh capital, because 13.7% is idle, that is approximately 54.7 bp per rotation.

---

## 2.2 Is ₹47,200 a valid minimum ticket?

If DP cost may not exceed 5 bp of a ticket:

\[
\frac{₹23.60}{0.0005}=₹47{,}200
\]

That arithmetic is correct.

At ₹10 lakh:

\[
₹10{,}00{,}000/₹47{,}200 \approx 21
\]

Thus a 20–21 name cap follows from the chosen 5 bp DP tolerance.

But the 5 bp tolerance is an investment-policy choice, not a theorem. Optimal cardinality depends on:

- signal breadth;
- expected alpha concentration;
- stock-specific risk;
- sector and factor exposure;
- actual DP tariff;
- turnover;
- spreads and impact;
- whether residual cash is reallocated;
- the value of the marginal name.

My institutional conclusion is:

> A 15–25 name book is a reasonable engineering envelope for a ₹10 lakh delivery portfolio. A hard 20-name cap is defensible, but not universally mathematically compulsory.

Ninety-five names is plainly uneconomic in this implementation because the model has no measurable per-name alpha capable of paying the extra fixed costs.

---

## 2.3 Claude understates System 1’s fragmentation

System 1 likely has approximately 100 positions based on its fee ledger. Its average deployed ticket is therefore approximately ₹8,500, not ₹20,000.

System 1’s actual structural disease appears to be:

- excessive cardinality;
- very short holding periods;
- approximately 14.5% cash;
- weak or absent selection edge.

It is not merely a 50-leg book suffering from frequency.

---

## 2.4 Annual friction depends on turnover, not just rebalance frequency

The correct approximation is:

\[
C_{\text{annual}}
\approx
C_{\text{full rotation}}
\times
\frac{252}{H}
\times q
\]

where:

- \(H\) = average holding period in sessions;
- \(q\) = fraction of the portfolio replaced per rebalance;
- \(C_{\text{full rotation}}\) = cost of selling and replacing 100% of capital.

Claude effectively assumes \(q=1\): complete replacement every holding period.

Using:

- approximately 42 bp per full rotation for a 20-name book;
- approximately 63 bp for the current 95-name System 2 implementation;

we obtain:

| Holding period | 20 names, full replacement | 95 names, full replacement |
|---:|---:|---:|
| 1 session | 106% p.a. | 160% p.a. |
| 3 sessions | 35% p.a. | 53% p.a. |
| 5 sessions | 21% p.a. | 32% p.a. |
| 10 sessions | 10.6% p.a. | 15.9% p.a. |
| 21 sessions | 5.0% p.a. | 7.6% p.a. |
| 42 sessions | 2.5% p.a. | 3.8% p.a. |
| 63 sessions | 1.7% p.a. | 2.5% p.a. |

These are approximate and exclude brokerage where applicable.

### Assessment

Claude is directionally correct:

- Daily or 1–3 day full turnover is economically impossible for this delivery structure.
- Weekly full replacement is overwhelmingly likely to be fatal.
- A 95-name monthly rotation consumes approximately 7%–8% annually before any model error.

But the statement that any weekly rebalance is “mathematically fatal” is too broad. A weekly **evaluation** with a no-trade band and only 10% turnover is very different from replacing the whole portfolio weekly.

### Minimum viable holding period

There is no universal minimum. It depends on the gross alpha and the allowed cost budget:

\[
H_{\min} \ge \frac{252C_{\text{rotation}}}{\text{annual cost budget}}
\]

For a 20-name portfolio at 42 bp per rotation:

- 10% annual cost budget: about 11 sessions
- 5% cost budget: about 21 sessions
- 3% cost budget: about 35 sessions

For the existing 95-name structure at 63 bp:

- 10% budget: about 16 sessions
- 5% budget: about 32 sessions
- 3% budget: about 53 sessions

For modest technical alpha, the realistic envelope is therefore closer to **one to three months**, unless turnover is sharply reduced through persistence and no-trade bands.

---

# 3. System 1 negative IC diagnosis

## 3.1 What eight negative ICs probably mean

For features such as:

- ROC;
- RSI;
- Bollinger %b;
- price/SMA distance;
- recent volume trend;

a negative cross-sectional IC over a 1–3 day forward horizon is economically plausible. High recent winners often experience short-horizon reversal because of:

- temporary liquidity pressure;
- closing-price reversals;
- bid-ask and microstructure effects;
- crowded short-term positioning;
- overnight/intraday return decomposition;
- profit-taking after sharp moves.

Thus, the first-order economic interpretation is:

> The feature family is largely momentum/state based, while the chosen 1–3 day label lies in a short-term reversal regime.

However, “eight of fourteen” is not eight independent confirmations. These features are highly correlated manifestations of perhaps two or three latent factors. Their t-statistics also require correction for:

- overlapping forward-return labels;
- serial correlation in daily IC;
- cross-sectional dependence;
- multiple testing.

A Newey-West or date-block bootstrap should be used, with lag at least \(H-1\) for an \(H\)-session label.

---

## 3.2 Negative IC is not, by itself, evidence of look-ahead bias

Look-ahead leakage more commonly produces an implausibly strong positive backtest. It can produce arbitrary signs if the feature/label join is shifted incorrectly, but negative IC alone does not diagnose leakage.

The supplied history records genuine data defects:

- duplicate rows;
- overstated universe coverage;
- same-close optimistic targets;
- survivorship-biased universe;
- market-wide features that cannot rank stocks.

But it also says the feature store was rebuilt, labels were changed to governed next-open returns, and a corrected model was tested out of sample.

Therefore the dominant current conclusion is not “look-ahead caused the negative IC.” It is:

> A short-term reversal relationship appeared in the hypothesis-generating sample, but it failed to produce stock-selection edge on the broader test universe.

Required causal tests should include:

- unique `(date, symbol)` assertions;
- feature timestamp \(t\), decision after close \(t\), execution no earlier than \(t+1\);
- deliberate one-day lead/lag perturbations;
- point-in-time universe membership;
- purging for overlapping labels;
- date-based temporal holdouts, not only new-name holdouts.

Label shuffling is a useful smoke test but does not prove the absence of leakage.

---

## 3.3 Ridge collinearity affects coefficient signs, not univariate IC signs

ROC, RSI, SMA distance and Bollinger %b are strongly collinear. Ridge will generally stabilize predictions relative to OLS, but individual coefficients can still be economically uninterpretable because the same latent exposure is distributed among correlated variables.

Important distinction:

- **Negative univariate feature IC** is a property of feature-versus-return association.
- **Unstable Ridge coefficient signs** are a property of the multivariate fit.

Collinearity cannot explain why the univariate ICs themselves are negative. It can explain why the fitted model initially pointed in an incoherent direction or why coefficients changed signs across folds.

The supplied research history says the corrected Ridge did learn the reversal structure—seven of eight coefficients became negative—and still produced essentially zero out-of-sample selection edge. That is decisive.

---

## 3.4 Can System 1 be salvaged by sign inversion?

### Mechanical score-orientation bug

If code is demonstrably sorting predicted returns in the wrong direction, correcting that is legitimate.

### Statistical post-hoc inversion

Flipping \(\hat\beta\rightarrow-\hat\beta\) because the realized IC was negative is a new data-mined hypothesis. It must be tested on untouched data.

More importantly, Ridge trained on continuous forward returns should already learn negative coefficients when the relationship is reliably negative. The corrected model did so and still failed.

Feature-by-feature sign inversion before fitting an unconstrained Ridge is largely cosmetic: the fitted coefficient can reverse correspondingly, leaving the prediction space essentially unchanged.

Finally, inversion does not reverse transaction costs. A gross spread of a few basis points cannot pay 40–60+ bp per rotation.

### Verdict

\[
\boxed{\text{Do not salvage System 1 by post-hoc sign inversion.}}
\]

---

## 3.5 Can horizon elongation salvage it?

Elongating the horizon can materially reduce friction and may move the signal from short-term reversal toward intermediate momentum. But this would be a **new model**, not a harmless implementation adjustment.

It requires:

- new 21-, 42- and 63-session labels;
- refitting the model;
- re-estimating IC decay;
- turnover-aware portfolio construction;
- new untouched temporal validation;
- full net-of-cost benchmark-relative testing.

Simply holding a 1–3 day forecast for 21 days is not justified.

System 2’s failure also shows that naïve 21-day momentum is not automatically the answer. Longer horizon is necessary for cost control, but it does not establish alpha.

---

# 4. Final capital-allocation verdict

## System 2 — XS-Monthly Momentum

**Halt immediately.**

Actions:

- Stop presenting it as a live investment system.
- Freeze the scheduler except for final reconciliation.
- Mark the book to liquidation-equivalent NAV.
- Archive it as a research result or negative control.
- Allocate no real capital.

Its benchmark-relative edge is statistically null, its rank IC is negative, its long-short spread is negative, and its implementation cost is an order of magnitude larger than its estimated selection benefit.

---

## System 1 — Flagship Alpha

**No real capital. Suspend the current paper portfolio.**

It should not retain “Flagship,” “Pilot” or privileged candidate status. The supplied record explicitly says:

- corrected;
- refuted out of sample;
- not promotable;
- do not paper trade.

A materially new lower-turnover model may be researched, but it should receive a new experiment identity and pre-registered validation plan. The existing failed model should not be silently repurposed through sign flips or horizon changes.

---

## Founder’s ₹20,00,000

| Allocation | Amount |
|---|---:|
| System 1 | **₹0** |
| System 2 | **₹0** |
| Total systematic active deployment | **₹0** |

Until a strategy passes a hard net-of-cost, benchmark-relative gate, the ₹20 lakh should remain outside these models.

If the money is genuinely awaiting research deployment, hold it in cash equivalents, Treasury bills or a suitable liquid vehicle. If the founder independently wants long-term Indian equity beta, use a low-cost broad-market index fund according to the founder’s investment policy rather than treating either model as an alpha source.

---

# 5. The single most actionable upgrade

## Build one machine-enforced, liquidation-equivalent net-alpha promotion engine

The same engine must be used by backtest, shadow, paper and live books and must:

1. Accrue actual buy-side charges at entry.
2. Reserve sell-side statutory charges, DP fees and estimated exit impact continuously.
3. Model DP costs by filled ISIN—not as a simple basis-point approximation.
4. Use quantity-aware integer sizing and explicit cash handling.
5. Measure active return against a matched point-in-time benchmark.
6. Apply actual turnover, no-trade bands and nonlinear transaction costs.
7. Prohibit a scheduler, capital field or “System” label unless the model passes the net-of-cost promotion gate.

The promotion statistic should be economic, not cosmetic:

\[
\text{Net active return}
=
R_{\text{strategy}}
-
R_{\text{matched benchmark}}
-
\text{incremental implementation costs}
\]

No optimizer, cardinality cap or sign inversion can rescue a strategy whose expected net active return is zero. The platform’s next priority is therefore not another feature experiment; it is making it technically impossible for a research-null model to appear as an investable portfolio.

## Bottom line

Claude was right to recommend **₹0 deployment**, but too charitable toward System 1 and too confident in several numerical claims.

The institutional verdict is unequivocal:

> **Halt System 2. Suspend the current System 1 implementation. Fund neither. Archive both as failed research specifications, and enforce a single net-of-cost promotion gate before conducting any further pilot.**