​I am treating the supplied performance as an audit record rather than evidence of efficacy. The critical distinction is between a positive absolute return and an incremental, correctly costed, out-of-sample return after the actual implementation geometry.# First Opinion: Both Models Fail the Current Institutional Alpha Standard

The live paper P&Ls are not evidence of a deployable edge. System 1 has direct falsification evidence. System 2 has positive market exposure but no economically credible selection edge once implementation costs and benchmark equivalence are handled correctly.

The appropriate immediate action is to stop treating either model as production-candidate alpha. Keep System 2 only as a governed research/control portfolio; halt System 1 signal-driven paper allocation pending a rebuilt, independently validated research process.

## 1. System 1: Mizan Flagship Alpha

### Verdict: reject the current model and feature-to-horizon specification

The evidence does not show a weak model needing tuning. It shows that the model is aligned with the wrong conditional return regime.

The IC diagnostic reports 8 of 14 measurable features as statistically significantly negative, but names only five in the supplied summary. That discrepancy must be reconciled in the research artifact before any governance sign-off. It does not change the main conclusion: the documented significant signals are all negative, including short-term returns, RSI, SMA distance, and cross-sectional momentum.

A positive `return_1`, `return_5`, elevated RSI, and positive distance from a moving average predicting *lower* subsequent returns is the signature of short-horizon reversal, conditional mean reversion, liquidity provision effects, and possibly temporary price-pressure reversal. It is not evidence that “momentum is weak.” It is evidence that the model’s assumed direction is wrong at the tested forecast horizon.

A Ridge model does not solve this. Ridge stabilizes coefficients under correlated features; it does not infer an economically valid horizon or protect against a regime error. With strongly correlated momentum-style inputs:

- `return_1`, `return_5`, `rsi_14_centered`, `sma_20_distance`, and `cs_rank_momentum_5` all encode overlapping recent-price-strength information.
- The model can put unstable or offsetting weights across these correlated variables.
- If training labels, feature standardization, universe membership, or folds are imperfectly point-in-time, apparent fit can be further distorted.
- If the production model is materially long positive short-term-strength exposure while forward IC is negative, it is systematically buying locally overextended names and selling or underweighting locally depressed names.

The issue is not that Indian equities must always mean-revert over one to five days. That claim would be too broad and cannot be established from the supplied tests alone. The defensible conclusion is narrower and more important: **in this liquid NSE universe, with this feature set, sampling protocol, and tested holding horizons, the measured conditional relationship is reversal rather than continuation.** This must be validated by date-blocked, purged, embargoed, point-in-time out-of-sample tests before assuming it is a persistent anomaly.

### The friction hurdle is decisive

Trial 1 generated a gross mean return of:

\[
7.6\text{ bps} = 0.076\%
\]

against a stated round-trip friction of:

\[
22.25\text{ bps} = 0.2225\%
\]

The exact expected net return before any unmodeled slippage is therefore:

\[
7.6 - 22.25 = -14.65\text{ bps per round trip}
\]

The gross return must be:

\[
22.25 / 7.6 = 2.93\times
\]

the observed gross result merely to break even on the stated friction model. It must exceed that materially to compensate for spread, impact, adverse open execution, rejected/locked names, stale pricing, and model error.

This explains why 45 of 45 names were negative net. That result is not a temporary drawdown. It is the arithmetic consequence of a gross edge far below the trading hurdle.

Sub-five-day delivery trading on NSE is not universally mathematically impossible, but it is effectively nonviable for this implementation unless the strategy has a large, stable, *net-of-all-costs* forecast advantage. A 7.6 bps gross signal cannot support a 22.25 bps round trip. It is structurally dead as currently specified.

The 10-session trial is equally adverse:

- Strategy total return: `-31.57%`
- Benchmark buy-and-hold: `+22.0%`
- Sharpe: `-0.4108`
- DSR: `0.1760`, well below the required `0.95` gate

This is negative alpha, not merely a poor risk-adjusted implementation.

### 97 holdings is false diversification for this model

At ₹10 lakh, 97 holdings imply approximately ₹10,309 target capital per name before integer-share effects. The current book is broadly consistent with this, with stated positions around ₹8,000 to ₹12,000.

Holding 97 names is not inherently wrong. It can be appropriate for a robust cross-sectional model with a demonstrable low-turnover edge and capacity constraints. Here it is harmful because:

- The model has no demonstrated positive selection edge.
- The portfolio approximates a broad, noisy NIFTY 500 exposure while incurring active-management turnover.
- Tiny delivery positions magnify fixed per-scrip exit charges.
- The portfolio has little ability to express conviction, yet retains nearly every operational and microstructure burden of stock selection.
- A 97-name book makes reported P&L look diversified while obscuring whether any ranking efficacy exists beyond market and sector beta.

For a model whose rank ordering is wrong, 97 names diversify the mistake. It does not convert it into alpha.

## 2. System 2: XS-Monthly Momentum

### Verdict: positive absolute return, no credible demonstrated alpha

The live paper gain of ₹4,223.88, or `+0.422%`, is economically indistinguishable from ordinary equity-market movement over a single monthly holding window. The model’s own long-history evidence confirms this:

| Measure | Top 20% Momentum | Equal-Weight Market | Increment |
|---|---:|---:|---:|
| Mean net return / period | +1.74% | +1.69% | +0.053% |
| Sharpe | +0.84 | +0.83 | +0.01 |
| Rank IC | -0.0096 |  | t = -0.85 |

The actual measured selection premium is just:

\[
5.3\text{ bps per 21-session period}
\]

The rank IC is slightly negative and statistically insignificant. A rank IC of `-0.0096` with `t = -0.85` does not support the proposition that higher-ranked names subsequently outperform lower-ranked names. The Sharpe difference of `0.01` is immaterial without a paired-return confidence interval and bootstrapped significance test.

The 3-year result, `+10 bps` of return edge and Sharpe `0.91` versus `0.89`, is directionally better but still too small to survive minor deviations in universe, costs, rebalance timing, and survivorship controls. It is a research lead, not investable evidence.

The current positive P&L should be classified as **unattributed beta plus noise until a holdings-based attribution proves otherwise**. At a minimum, compare the live basket daily against:

1. An identical-capital equal-weight liquid-universe control.
2. A NIFTY 500 or appropriate tradable benchmark.
3. A same-cardinality, same-turnover random-selection control.
4. A sector-neutral random-selection control, if the signal carries sector tilts.

Without those controls, “profit” is simply a portfolio-level outcome, not alpha.

### The 99-leg DP fee makes the claimed edge non-economic

The stated entry capital is ₹862,815.98 across 99 positions:

\[
\text{Average entry value} = ₹8,715.31
\]

The DP debit charge on a delivery sell is per ISIN, not proportional to the notional. Using the stated range inclusive of GST:

| DP fee per exit | Per-position drag on ₹8,715.31 | 99-leg cost | Drag on ₹10 lakh capital |
|---|---:|---:|---:|
| ₹15.50 | 17.79 bps | ₹1,534.50 | 15.35 bps |
| ₹17.70 (`₹15 + GST`) | 20.31 bps | ₹1,752.30 | 17.52 bps |
| ₹23.60 (`₹20 + GST`) | 27.08 bps | ₹2,336.40 | 23.36 bps |

The 10-year selection edge on ₹10 lakh is:

\[
₹10,00,000 \times 0.053\% = ₹530\text{ per period}
\]

Thus the DP exit charge alone is:

\[
₹1,534.50 \text{ to } ₹2,336.40
\]

or `2.90x` to `4.41x` the measured ₹530 expected selection premium.

Even at the lowest supplied DP cost, the expected post-DP selection result is:

\[
₹530 - ₹1,534.50 = -₹1,004.50
\]

before spread, impact, incomplete fills, locked names, tracking variance, and any cost-model deficiencies.

There is a material implementation inconsistency in the supplied code. `paper.py` charges only:

```python
cost = COST_RATIO * entry_value
```

with `COST_RATIO = 0.224%` for the full round trip. It does not apply a per-scrip DP charge. Therefore the runner’s statement that returns are “net” is incomplete for a delivery implementation with 99 separately sold ISINs. The live paper equity overstates deployable net performance if the paper book is intended to represent actual delivery execution.

This needs correction before the next reported paper mark. Every exit should use a broker-specific fee schedule with:

- brokerage and GST;
- buy and sell STT at the applicable product rate;
- exchange transaction charges and GST;
- SEBI turnover charge;
- stamp duty;
- DP debit fee, GST-inclusive, once per ISIN sold per settlement day;
- bid-ask spread and a conservative market-impact model;
- taxes and charges rounded according to the broker contract note rules.

The DP cost should be charged only for actual distinct ISINs sold, not mechanically for all 99 names each month. But that qualification does not rescue the current strategy. A high-turnover 99-name monthly rotation is precisely the profile likely to realize a large share of those charges.

### Cardinality math

For the DP charge alone to stay below the 5.3 bps historical selection edge on ₹10 lakh, the maximum monthly number of distinct sold ISINs is:

\[
₹530 / ₹15.50 = 34.19
\]

at the lowest fee, or:

\[
₹530 / ₹23.60 = 22.46
\]

at the high fee.

In practical whole-position terms, this means no more than approximately:

- `34` sold names at ₹15.50 DP cost;
- `29` sold names at ₹17.70 DP cost;
- `22` sold names at ₹23.60 DP cost.

This is only a DP constraint. It leaves no allowance for the rest of the implementation shortfall. A 99-name portfolio cannot clear the hurdle.

Reducing to 20 names raises target position size to roughly ₹50,000. The DP drag becomes:

- ₹310 to ₹472 total per full rotation;
- `3.10` to `4.72 bps` of ₹10 lakh.

That is below the reported 5.3 bps selection edge, but only narrowly and only before all other costs. A 20-name basket is not automatically the answer: concentration, sector skew, idiosyncratic risk, liquidity, and the signal’s rank-decay profile must be retested from scratch. The appropriate test is a cardinality and turnover frontier, not an arbitrary reduction.

### Backtest concerns

The 2016-2026 result must be re-audited for:

- **Survivorship and constituent timing:** A static 423-name “liquid” universe can materially inflate results if delisted, distressed, suspended, or historically illiquid names are excluded using information unavailable at the decision date.
- **Point-in-time data:** Corporate actions, symbol changes, split adjustments, index membership, liquidity qualification, and available bars must be known only as of formation.
- **Open-price attainability:** “Next-open entry” is not automatically executable at the official opening print for 99 names. Opening auction participation, opening spread, gaps, price bands, and locked names must be modeled.
- **Rebalance overlap:** Measure actual monthly name turnover, not only 99 active holdings. DP applies to distinct sold names; turnover determines cost.
- **Benchmark cost parity:** The equal-weight market comparator must receive a matching, realistic rebalance methodology and implementation-cost model. Otherwise the reported 5.3 bps may be an artifact of mismatched turnover and cost assumptions.
- **Multiple testing:** The 21-day/21-day/top-20% rule needs a research family log. A frozen specification is valuable only if it was frozen before the final out-of-sample evaluation.
- **Statistical uncertainty:** Report paired active-return mean, Newey-West t-statistic, block-bootstrap confidence interval, drawdowns, rolling active Sharpe, factor regressions, and performance by market regime.

## 3. Head-to-Head Assessment

| Dimension | System 1: Flagship Alpha | System 2: XS-Monthly |
|---|---|---|
| Signal evidence | Directly contradicted by significant negative ICs | Weak and statistically unconfirmed |
| Historical outcome | Deeply negative versus positive benchmark | Nearly identical to equal-weight market |
| Primary failure | Wrong sign/horizon plus impossible short-horizon costs | Selection edge below fixed per-scrip implementation costs |
| Portfolio geometry | 97 small, high-friction positions | 99 small, DP-fee-dominated positions |
| Current recommendation | Retire from live signal allocation | Retain only as a control/research watch |
| Production readiness | No | No |

System 1 is demonstrably adverse. System 2 is not demonstrated to be beneficial after real implementation.

## 4. Definitive Engineering Roadmap

1. **Immediately stop System 1 capital allocation.** Preserve the paper history, model artifact hashes, feature store, decision logs, and cost assumptions for forensic reproducibility. Do not tune its current weights in response to the paper drawdown.

2. **Do not mechanically invert System 1 weights.** Negative univariate ICs justify a new contrarian research hypothesis, not a sign flip of a multivariate Ridge model. Retrain a reversal specification with explicitly signed features, date-blocked walk-forward validation, purging/embargo, sector and beta controls, realistic turnover costs, and predeclared acceptance gates.

3. **Disable delivery strategies with expected gross alpha below a modeled all-in cost hurdle.** The research platform should reject a candidate if its lower-confidence-bound net active return is not positive after broker-specific costs and conservative implementation shortfall.

4. **Correct System 2 accounting before further performance reporting.** Add an immutable fee ledger and broker fee schedule. DP charges must be applied per actual distinct delivery ISIN sold per settlement date. Report gross return, statutory costs, DP charges, estimated spread/impact, and net active return separately.

5. **Reframe System 2 as a benchmark experiment.** Run the top-20% basket, equal-weight market basket, random 99-name basket, and random sector-neutral basket with identical execution assumptions. The relevant output is paired active return, not standalone return.

6. **Run a precommitted portfolio frontier.** Test `N = 10, 20, 30, 50, 75, 99`, each with the realized turnover and full cost ledger. Select cardinality by net active-return confidence and capacity, not by gross Sharpe. Based on DP arithmetic alone, the plausible region is approximately 20 to 30 names, not 99.

7. **Do not switch to intraday cash or futures merely to avoid DP fees.** Intraday cash avoids delivery DP charges but retains spread, impact, STT and execution-risk problems; it also demands a genuinely short-horizon alpha, which System 1 currently lacks. Futures may improve fixed-fee economics for broad beta or liquid factor exposure, but introduce roll, basis, margin, lot-size, and concentration constraints. Instrument choice follows validated alpha horizon and capacity; it cannot manufacture alpha.

8. **Separate alpha research from platform architecture.** The canonical feature implementation, window governance, model serialization, and point-in-time safeguards are valuable engineering work. They do not validate the economic premise of the model. Model governance must permit a candidate to be rejected even when its code path is reproducible and operationally clean.

**Final determination:** System 1 should be rejected in its present form because its signal direction and cost structure are both invalidated. System 2 should not be called alpha or advanced toward production because its observed selection premium is smaller than its omitted fixed delivery-exit cost. The near-term objective is not optimization of either live book; it is construction of a cost-complete, benchmark-paired, point-in-time research harness capable of proving a positive net active return.