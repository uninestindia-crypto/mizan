# QuantOS Institutional Audit — Phase 1
## Quantitative Model Analysis: Structural Findings and Adjudication

**Auditor role:** Senior Quantitative Research Director, Systematic Equities (India)
**Scope:** Predictive model stack — `modeling/ridge.py`, `modeling/features.py`, `modeling/labels.py`, `analytics/multiplicity.py`, and 104 trials of empirical campaign evidence
**Overall verdict:** **The engineering is materially better than the research.** The governance layer, determinism, point-in-time discipline, and cost binding are above the median of what I see at institutional desks. The *predictive content is zero, and the campaign evidence is consistent with zero being the true value, not with a mis-specified estimator hiding a real signal.* Several of the reported "failures" are in fact the system correctly reporting the absence of edge. There are, however, **four genuine mathematical defects** and **two silent methodological leaks** that must be fixed before any further research is trusted — not because fixing them will produce alpha, but because without fixing them a future false positive will be indistinguishable from a real one.

I have organised the audit against your six questions, then closed with a prioritised defect register.

---

# 1. Mathematical Formulation & Bias

## 1.1 What the estimator actually is

Despite the name `fit_ridge_classifier`, the code fits **no classifier**. It fits an L2-penalised ordinary least squares regression of a ±1 coded target on standardised features:

$$
\hat{\boldsymbol\theta} = \arg\min_{\theta_0,\boldsymbol\beta} \; \big\| \mathbf{y} - \theta_0\mathbf{1} - \mathbf{X}\boldsymbol\beta \big\|_2^2 + \lambda \|\boldsymbol\beta\|_2^2,
\qquad y_i \in \{-1,+1\}
$$

with the intercept correctly exempted from the penalty (`regularizer[0,0] = 0.0` — this is right, and many implementations get it wrong). The solution is the standard augmented normal equation:

$$
\hat{\boldsymbol\theta} = \big(\mathbf{Z}^\top\mathbf{Z} + \lambda \mathbf{P}\big)^{-1}\mathbf{Z}^\top\mathbf{y},
\qquad \mathbf{Z} = [\mathbf{1}\;\; \mathbf{X}], \;\; \mathbf{P} = \mathrm{diag}(0,1,\dots,1)
$$

This is **Linear Discriminant Analysis up to an affine transformation** (Hastie, Tibshirani & Friedman §4.3.2): for two-class ±1 targets, OLS on the indicator produces a direction vector proportional to the LDA direction, but *the intercept is not the LDA decision boundary*. That distinction is the entire origin of the Trial 1/2 degeneracy, and it is worth stating precisely because the CURRENT.md root-cause note gets the arithmetic right but the conceptual framing incomplete.

## 1.2 Why the intercept equals the mean target — exactly, not coincidentally

This is not "intercept drift." It is an **algebraic identity**, and it is guaranteed by the preprocessing contract.

Because `StandardizationStateV1` centres features on the **training partition** mean, the training design matrix satisfies $\mathbf{1}^\top\mathbf{X} = \mathbf{0}$ exactly (to floating point). The first row of the normal equations is the unpenalised intercept equation:

$$
\begin{bmatrix} n & \mathbf{1}^\top\mathbf{X} \\ \mathbf{X}^\top\mathbf{1} & \mathbf{X}^\top\mathbf{X}+\lambda I \end{bmatrix}
\begin{bmatrix}\hat\theta_0 \\ \hat{\boldsymbol\beta}\end{bmatrix}
=
\begin{bmatrix}\mathbf{1}^\top\mathbf{y} \\ \mathbf{X}^\top\mathbf{y}\end{bmatrix}
$$

With $\mathbf{1}^\top\mathbf{X} = \mathbf{0}$, the first row **decouples completely**:

$$
n\hat\theta_0 = \mathbf{1}^\top\mathbf{y} \;\;\Longrightarrow\;\; \boxed{\hat\theta_0 = \bar{y} = \frac{n_{\text{UP}} - n_{\text{DOWN}}}{n}}
$$

Substituting your reported partition: $n_{\text{UP}}=182$, $n_{\text{DOWN}}=229$, $n=411$:

$$
\hat\theta_0 = \frac{182-229}{411} = \frac{-47}{411} = -0.1143552\overline{31}
$$

Your fitted intercept is `-0.114355`. **Agreement to seven significant figures.** This is not evidence of a bug; it is confirmation that the linear algebra is exact and the centring is exact. The system is working.

## 1.3 The zero-trade guarantee — a bound, not an accident

The validation score for row $j$ is $s_j = \bar y + \mathbf{x}_j^\top\hat{\boldsymbol\beta}$. Trading requires $s_j > \tau$ with $\tau = 0$, i.e.

$$
\mathbf{x}_j^\top\hat{\boldsymbol\beta} > -\bar y = +0.1144
$$

Now bound the achievable signal amplitude. Let $R^2_{\text{train}}$ be the in-sample coefficient of determination of the ±1 regression. Since $\mathrm{Var}(y) = 1 - \bar y^2 = 1 - 0.01308 = 0.98692$, the standard deviation of the *fitted* component is

$$
\sigma_{\hat s} = \sqrt{R^2 \cdot \mathrm{Var}(y)} \approx 0.9934\sqrt{R^2}
$$

Your observed validation score dispersion is $\sigma_s = 0.053$, implying an **effective out-of-sample $R^2$ of $\approx 0.0028$**, i.e. a multiple correlation of $\rho \approx 0.053$. To clear the threshold you require a $+0.1144$ excursion from a distribution with $\sigma = 0.053$ — a **+2.16σ event in the score distribution**, and the observed maximum was $-0.026$, which is only $+2.15\sigma$ *from the score mean of $-0.140$* but still $0.114$ below zero.

The correct way to state this: **under a Gaussian approximation, the probability that at least one of 63 i.i.d. scores exceeds zero is**

$$
1 - \Phi\!\left(\frac{0 - (-0.140)}{0.053}\right)^{\!\!} \Rightarrow \; p_{\text{single}} = 1-\Phi(2.642) = 0.00412,
\quad P(\text{any of }63) = 1-(1-0.00412)^{63} = 0.229
$$

So there was a **77% ex-ante probability of zero trades** before the trial was ever run. Trials 1 and 2 were not an unlucky draw; they were the modal outcome. **A pre-trial feasibility check on $\Phi\big((\tau-\mu_s)/\sigma_s\big)$ would have caught this without burning two ordinals against the deflation count.** That is Defect D-3 below.

## 1.4 The deeper failure: squared-error loss on ±1 targets is a *base-rate estimator* under weak signal

This is the finding that matters, and it generalises far beyond your INFY case.

Decompose the ridge score into base rate and signal:

$$
s_j = \underbrace{\bar y}_{\text{class imbalance}} + \underbrace{\mathbf{x}_j^\top\hat{\boldsymbol\beta}}_{\text{signal}}
$$

The signal term's scale is governed by the shrinkage identity. For standardised, near-orthogonal features,

$$
\hat\beta_k \approx \frac{n}{n+\lambda}\,\hat\rho_k\,\sigma_y \;\approx\; \frac{n}{n+\lambda}\,\hat\rho_k
$$

where $\hat\rho_k$ is the sample point-biserial correlation between feature $k$ and the ±1 label. Your alternative-screen evidence reports mean IC of **+0.007 to +0.015**. With six features and generous assumption of orthogonality:

$$
\sigma_{\text{signal}} = \Big\|\hat{\boldsymbol\beta}\Big\|_2 \approx \sqrt{\textstyle\sum_k \hat\rho_k^2} \le \sqrt{6}\times 0.015 = 0.0367
$$

**The base-rate term $|\bar y|=0.1144$ exceeds the maximum achievable signal dispersion by a factor of 3.1.** The score distribution is therefore a tight cloud parked at the class prior, with the features contributing a perturbation an order of magnitude too small to cross any fixed decision boundary. The model is, functionally, a constant predictor with cosmetic noise.

This has three named consequences:

**(a) The MSE-optimal solution under weak signal is the prior.** As $\rho \to 0$, ridge converges to $\hat s_j \to \bar y \;\forall j$. Squared-error loss on ±1 labels *rewards* prior-matching because the Bayes risk of the constant predictor is $1-\bar y^2$ and any signal reduces it only by $O(\rho^2)$. With $\rho^2 \approx 0.0002$, the estimator is being asked to detect a 0.02% risk reduction. **It cannot, and MSE gives it no incentive to try.**

**(b) The ±1 coding conflates calibration with discrimination.** Logistic regression separates these: the intercept absorbs the base rate on the *log-odds* scale, and the decision threshold at $p=0.5$ corresponds to $\eta=0$ *regardless of class balance in the linear predictor's interpretation*, because the practitioner is forced to choose an operating point on the probability scale. With ±1 OLS the intercept and the threshold live on the same undefined scale, and the analyst is silently invited to compare a *conditional mean of a ±1 variable* against zero — which is only meaningful under exact class balance. **The `score_threshold=0` default embeds an unstated and false assumption that $P(\text{UP})=0.5$.**

**(c) Squared-error loss on ±1 is the wrong loss for the economic objective anyway.** You do not care about $\mathbb{E}[(y-\hat s)^2]$. You care about $\mathbb{E}[r \cdot \mathbb{1}\{s>\tau\}]$. Discretising a continuous net return into ±1 discards the entire magnitude distribution — a $+3\%$ day and a $+0.01\%$ day are the same label. Given that the net-return distribution of Indian large caps is leptokurtic with $\kappa \approx 6$–$9$, **you have thrown away the fat tail that is the only part of the distribution where a real edge could show up.** The label constructor in `labels.py` already computes `net_return` in full Decimal precision and then destroys it on the final line:

```python
target="UP" if Decimal(net_return_text) > 0 else "DOWN",
```

This single line is, in my assessment, the **largest single information destruction event in the stack.**

## 1.5 Verdict on the Trial 3 threshold shift

Setting $\tau = \bar y$ is the *correct* fix in the sense that it restores the decision boundary to the class-conditional midpoint (it is precisely the LDA intercept correction under equal covariance and equal misclassification cost). Formally, at $\tau=\bar y$ the rule reduces to $\mathbf{x}_j^\top\hat{\boldsymbol\beta} > 0$, which is scale-free and prior-free. **CURRENT.md's self-criticism that this was "an informed choice, not a blind one" is honest but excessively harsh: the choice is theoretically mandated, not data-snooped.** The ordinal-3 deflation penalty is being applied to a *bug fix*, not a hyperparameter search.

That said, the *result* is unambiguous. At $\tau=\bar y$ the model traded 22 times and delivered:

- Sharpe $-0.704$ vs. NO_TRADE $0.000$ and PREVIOUS_SIGN $+0.144$
- Accuracy $0.524$ vs. NO_TRADE's $0.587$ — **the model is 6.3pp worse than the unconditional base rate**

A 52.4% accuracy on 22 trades has standard error $\sqrt{0.25/22}=0.107$, so the accuracy is $0.22\sigma$ from a coin flip and $-0.59\sigma$ from the base rate. **The correct statistical statement is: 22 trades cannot distinguish this model from a fair coin, and the point estimate is worse than not trading.** There is no rescue here.

---

# 2. Feature Engineering & Window Stability

## 2.1 The six-feature family, audited

```
f1 = C_t/C_{t-1}  − 1                          1-bar return
f2 = C_t/C_{t-5}  − 1                          5-bar return
f3 = C_t/C_{t-10} − 1                          10-bar return
f4 = (RSI_14 − 50)/50                          Wilder RSI, rescaled
f5 = (C_t − SMA_20)/C_t                        distance from 20-bar mean
f6 = ATR_14/C_t                                normalised true range
```

### Finding F-1: The feature set has effective rank ≈ 2, not 6.

$f_1, f_2, f_3$ are overlapping cumulative sums of the same daily return series. For an i.i.d. return series, $\mathrm{Corr}(f_2,f_3) = \sqrt{5/10} = 0.707$ and $\mathrm{Corr}(f_1,f_3)=\sqrt{1/10}=0.316$. Worse, $f_5 = (C_t - \text{SMA}_{20})/C_t$ is, to first order in log returns,

$$
f_5 \approx \frac{1}{20}\sum_{i=1}^{19}(20-i)\,r_{t-i+1}\Big/20 \;=\; \text{a triangular-weighted 20-bar momentum}
$$

which loads on the **same latent factor** as $f_2$ and $f_3$. And $f_4$ (RSI) is a bounded monotone transform of the ratio of Wilder-smoothed gains to losses — empirically $\mathrm{Corr}(\text{RSI}_{14}, r^{(14)}) \approx 0.85$–$0.92$ on Indian large caps.

**Practical consequence:** the effective degrees of freedom of the ridge fit are

$$
\mathrm{df}(\lambda) = \sum_{k=1}^{6}\frac{d_k^2}{d_k^2+\lambda}
$$

where $d_k$ are the singular values of the standardised $\mathbf{X}$. With one dominant "momentum" eigenvalue, one "volatility" eigenvalue ($f_6$, and only $f_6$), and four near-null directions, **$\mathrm{df}(\lambda) \approx 2$**. You are not running a 6-feature model. You are running a 2-feature model with four channels of amplified estimation noise, and the ridge penalty is doing all the work of suppressing them.

**Recommendation:** the audit should report the condition number $\kappa(\mathbf{X}^\top\mathbf{X})$ and $\mathrm{df}(\lambda)$ per fold as first-class evidence artifacts. Neither is currently computed. A model whose $\mathrm{df}$ is 2 but whose deflation count assumes 6 free parameters is *under*-deflating its own complexity.

### Finding F-2: The feature family contains no cross-sectional, no microstructure, and no non-price information.

Every one of the six features is a **deterministic function of a single instrument's own OHLC over 21 bars**. This class of predictor has been the most heavily mined signal family in the history of quantitative finance. The prior probability that an unmined, cost-surviving daily-horizon edge exists in $\{r^{(1)}, r^{(5)}, r^{(10)}, \text{RSI}_{14}, \text{SMA}_{20}\text{-dist}, \text{ATR}_{14}\}$ on NIFTY 50 constituents is, charitably, **below 2%**. The campaign result (median Sharpe $-1.18$ on v1, $-0.23$ on v2) is the expected outcome under the correct prior. **This is not a modelling failure. It is a hypothesis-selection failure that occurred before any code was written.**

### Finding F-3: Schema v1 → v2, the 21-bar canonical window — the fix was correct and the improvement is diagnostic.

The v2 change enforces `records[-FEATURE_WARMUP_BARS_V1:]` inside `compute_feature_values` itself. This matters because **Wilder smoothing is an IIR filter with infinite memory**:

$$
\bar{G}_t = \frac{(N-1)\bar{G}_{t-1} + G_t}{N} \;\;\Longrightarrow\;\; \bar{G}_t = \sum_{i\ge 0}\frac{1}{N}\Big(\frac{N-1}{N}\Big)^{i}G_{t-i} + \Big(\frac{N-1}{N}\Big)^{t-t_0}\bar{G}_{t_0}
$$

With $N=14$, the seed persistence factor is $(13/14)^k$. After 21 bars the residual seed weight is $(13/14)^{7} = 0.601$ — **60% of the initial seed survives.** Under v1, if training rows were built from a 400-bar history and execution rows from a 21-bar buffer, the RSI and ATR values would differ by a *first-order*, not a rounding-order, amount. The docstring's warning ("Reimplementing this for execution is what allowed a second, ungoverned ridge to diverge") describes exactly this failure and the fix is correct.

**But the empirical signature is the important part.** Median Sharpe improved from $-1.1791$ (v1) to $-0.2278$ (v2) and positive-Sharpe hit rate from 35% to 42%. **The correct interpretation is not "v2 is better." It is: v1 was contaminated by a train/serve feature skew of first-order magnitude, and removing the contamination moved performance from 'systematically wrong' to 'indistinguishable from zero.'**

Test the hit-rate change formally. Under $H_0$: true hit rate 50%, v2's 21/50 gives $z = (0.42-0.50)/\sqrt{0.25/50} = -1.13$, $p=0.26$ — **v2 is statistically indistinguishable from a coin flip.** v1's 14/40 gives $z=-1.90$, $p=0.058$ — **v1 was significantly *worse* than a coin flip**, which is a signature of systematic sign error, not of noise. The v2 result is *consistent with the model having exactly zero information*. That is the honest reading, and it is a substantially stronger conclusion than "the strategy underperformed."

### Finding F-4: The 21-bar window is one bar too short for the declared feature set — a latent off-by-one.

`_wilder_atr` builds `true_ranges` with `records[0].high - records[0].low` as the first element (no previous close available), then requires `true_ranges[:14]` for the seed and iterates over `true_ranges[14:]`. With 21 records you get 21 true ranges, seed from 14, and only **7 smoothing iterations**. As computed above, that leaves 60% seed weight, and the seed's first element is a *contaminated* true range (H−L only, missing the gap component). Similarly `_wilder_rsi` gets 20 deltas from 21 closes, seeds on 14, iterates 6 times, leaving $(13/14)^6=0.647$ seed weight.

The window is *internally consistent* (v2 guarantees train and serve see the same 21 bars), so there is **no leakage and no skew** — but the resulting "RSI_14" and "ATR_14" are **not** the RSI_14 and ATR_14 that any other system on the planet computes. They are 21-bar-truncated approximations with ~60% seed dominance. If you ever benchmark against an external indicator library, or compare to published literature, **the numbers will not match and the discrepancy will be attributed to the wrong cause.**

**Recommendation:** either extend the warmup to $\ge 14 + 5\times 14 = 84$ bars (reducing seed weight to $(13/14)^{70}=0.6\%$) and re-declare the schema as v3, or **rename the features** `rsi14_trunc21` / `atr14_trunc21` so the truncation is on the record. The latter is cheaper and equally honest.

## 2.2 Why gross IC of +0.015 collapses net of statutory friction

This is the arithmetic that should have terminated the programme before trial 1.

**The friction.** NSE round-trip statutory cost on delivery equity: STT 0.1% on both legs (0.2%), exchange transaction charge ~0.00297%×2, SEBI turnover fee 0.0001%×2, stamp duty 0.015% (buy only), GST 18% on (brokerage + txn charges), plus brokerage. Your quoted **0.224%** round trip is credible and, if anything, *optimistic* because it appears to exclude:

- **Slippage on market-on-open orders.** Your labels use `entry_at = open_at` and `exit_at = open_at`. NSE opens via a call auction (09:00–09:08 pre-open) followed by continuous trading. Filling at the *printed* open is achievable only for the auction match; any size beyond the auction depth pays the post-open spread, which on NIFTY 50 names is 2–6 bps and materially wider in the first minutes.
- **Impact.** Even at ₹50L notional, a 1–3 bps permanent impact on a NIFTY 50 name is realistic.

**A defensible all-in round trip is 0.26%–0.32%, not 0.224%.** Everything below is therefore a *lower bound* on the required edge.

**The required IC.** For a long-only binary rule on a 1-day horizon, the expected gross return conditional on a signal is approximately

$$
\mathbb{E}[r \mid s > \tau] \approx \rho \cdot \sigma_r \cdot \lambda(\tau)
$$

where $\lambda(\tau)=\phi(\tau)/(1-\Phi(\tau))$ is the inverse Mills ratio at the standardised threshold. Daily volatility of a NIFTY 50 constituent is $\sigma_r \approx 1.5\%$. Taking $\rho = 0.015$ (your best screen) and a moderately selective threshold at the 80th percentile ($\tau=0.842$, $\lambda=1.40$):

$$
\mathbb{E}[r \mid \text{signal}] \approx 0.015 \times 0.015 \times 1.40 = \boxed{0.000315 = 3.15\text{ bps}}
$$

**Against a 22.4 bp round trip.** The cost is **71× the edge.** Net expectancy per trade:

$$
\mathbb{E}[r_{\text{net}}] = 3.15 - 22.4 = -19.25 \text{ bps}
$$

**Invert for the break-even IC:**

$$
\rho^{*} = \frac{c}{\sigma_r \lambda(\tau)} = \frac{0.00224}{0.015\times 1.40} = \boxed{0.1067}
$$

**You need an information coefficient of ~0.107 to break even at this horizon and threshold.** You measured 0.007–0.015. **You are short by a factor of 7 to 15.** For calibration: a *world-class* daily equity signal runs IC 0.03–0.05. An IC of 0.107 on daily returns from six price-derived features does not exist and has never existed.

**This is the single most important number in the audit.** No estimator change — LightGBM, transformers, ensembles, anything — recovers a 7× IC shortfall. The constraint is not the model. **The constraint is the cost-to-horizon ratio.**

**The corollary is the strategic path.** Break-even IC scales as $c/(\sigma_r\sqrt{h}\,\lambda)$ for an $h$-day horizon (since $\sigma_{r,h}=\sigma_r\sqrt h$ while cost is horizon-invariant). At $h=21$ days:

$$
\rho^{*}_{21} = \frac{0.00224}{0.015\sqrt{21}\times 1.40} = 0.0233
$$

**Still 1.6× above your best measured IC, but within an order of magnitude — and this is precisely why the cross-sectional monthly screen produced t=1.18 while every daily screen produced flat negatives.** The horizon arithmetic, not the estimator, explains the entire pattern of your empirical results. Your own campaign evidence independently confirms the formula. That is a strong internal consistency check on this audit's conclusion.

Additionally, `_row_from_quote` charges the full round-trip cost to **every label**, including the DOWN labels that are never traded. This is correct for *labelling* (it defines "profitable after costs") but it means the UP base rate is depressed by the cost hurdle: a name must clear +22.4 bps to be labelled UP. On a symmetric return distribution with $\sigma=1.5\%$, this shifts $P(\text{UP})$ from 0.50 to $1-\Phi(0.224/1.5)=0.441$. **Your 182/229 = 44.3% UP rate matches this prediction to within 0.2pp.** The class imbalance that broke Trials 1–2 is *entirely* explained by the cost hurdle — it is not a market-direction effect, and any model that "learns" it is learning the fee schedule.

---

# 3. Purged Cross-Validation & Embargo

## 3.1 The file does not exist.

```
### 2. `modeling/purging.py`:
[FILE NOT FOUND]
```

`build_purged_fold` is referenced in the CURRENT.md pipeline chain and produces `train=411, validation=63, embargo=2`, but the implementation was not supplied to this audit. **I cannot certify what I cannot read.** Everything in §3 is therefore an analysis of the *declared parameters* against the *label geometry*, which is sufficient to reach a firm conclusion on adequacy but not on correctness of implementation.

**Audit action required:** produce `purging.py` for Phase 2. Given that CURRENT.md itself states *"the training runner, the campaign driver, and every research result they produced"* have **not** been independently adjudicated, the purging logic is in the unadjudicated set. This is the highest-risk unreviewed component in the stack, because purging bugs produce *optimistic* results and are invisible in every downstream metric.

## 3.2 Is a 2-session embargo adequate? — Yes for label overlap, no for the actual leakage channels.

### Channel A: Label horizon overlap — **CORRECTLY HANDLED.**

The label spans decision $t$ → entry open $t{+}1$ → exit open $t{+}2$. The last training label consumes information through session $t_{\text{train,last}}+2$. An embargo of 2 sessions removes exactly the rows whose label windows overlap the validation boundary. Under López de Prado's framework (*Advances in Financial Machine Learning*, §7.4), the required purge is $h$ sessions where $h$ is the label horizon; with `LABEL_HORIZON_SESSIONS_V1 = 2`, **embargo = 2 is exactly correct.** No over- or under-purging on this channel.

### Channel B: Feature-window overlap — **NOT HANDLED. THIS IS A REAL LEAK.**

Each feature row consumes a **21-bar trailing window**. The last training row at $t_{\text{tr}}$ reads bars $[t_{\text{tr}}-20, t_{\text{tr}}]$. The first validation row at $t_{\text{tr}}+3$ (post-embargo) reads bars $[t_{\text{tr}}-17, t_{\text{tr}}+3]$.

**These windows share 18 of 21 bars — an 85.7% overlap.**

For the Wilder indicators this is worse than a simple shared-bar count, because of the IIR memory demonstrated in §2.1. The RSI and ATR of the first validation row are ~60% determined by the seed, which is computed from bars that are *entirely inside the training partition*.

The consequence is not classical look-ahead — no future information reaches the past. It is **an inflation of the effective sample size and a correlation between training and validation feature vectors that breaks the i.i.d. assumption underpinning every downstream statistic.** Specifically:

Let $\rho_{\text{feat}}$ be the serial autocorrelation of the feature vector across the fold boundary. The **effective number of independent validation observations** is approximately

$$
n_{\text{eff}} = n\,\frac{1-\rho_1}{1+\rho_1}
$$

For a 21-bar-window feature with $\rho_1 \approx 1 - 1/21 = 0.952$ (dominant for $f_5$, RSI, ATR):

$$
n_{\text{eff}} \approx 63 \times \frac{0.048}{1.952} = \boxed{1.55}
$$

**Your 63-session validation fold contains, for the slow features, on the order of 1.5 to 3 independent observations.** This is the number that should be feeding `sample_length_bars` in the DSR (see §4, Defect D-1). It is not.

**Required remedy:** the embargo must be $\max(h_{\text{label}},\; w_{\text{feature}}) = \max(2, 21) = \mathbf{21}$ sessions, not 2. With a 21-session embargo, training and validation feature windows are disjoint and the Wilder seeds no longer share bars. Cost: 19 additional rows out of 476 (4%). **This is the cheapest high-value fix in the entire register.**

### Channel C: Cross-sectional contemporaneous leakage in the 50-name campaigns — **NOT HANDLED.**

Each of the 50 NIFTY names was trialled independently, but they were fit and validated over the *same calendar window* (2024-01-01 to 2025-12-31). NIFTY 50 constituents have a dominant common factor: average pairwise daily return correlation on Indian large caps is $\bar\rho \approx 0.45$–$0.55$. The effective number of independent cross-sectional bets is

$$
N_{\text{eff}} = \frac{N}{1+(N-1)\bar\rho} = \frac{50}{1+49(0.50)} = \boxed{1.96}
$$

**The 50-name campaign is not 50 independent trials. It is approximately 2.** This cuts both ways and must be stated in both directions:

- **Against the programme:** the 21/50 positive-Sharpe count is not $\mathrm{Binomial}(50, p)$ evidence. The correct binomial test uses $N_{\text{eff}}\approx 2$, so **21/50 carries essentially no evidential weight in either direction.** Any future claim of "we succeeded on 30 of 50 names" is similarly worthless without a factor adjustment.
- **In mitigation:** the DSR deflation using `num_trials = 50` or `101` is **over-conservative** on the cross-sectional dimension, because $\mathbb{E}[\max]$ of 50 *correlated* trials is far below $\mathbb{E}[\max]$ of 50 independent ones. See §4, Defect D-2.

### Channel D: Expanding-window folds and the single-split reality — **UNDER-DIAGNOSED.**

The evidence reports one fold (`train=411, validation=63`). If the "walk-forward expanding folds" produced only a single terminal split, then:

1. There is **one** out-of-sample period, covering roughly Oct–Dec 2025.
2. That period's market regime is a single draw. INFY's realised Sharpe over the window was $-0.547$ (buy-and-hold), i.e. **a falling market**. A long-only model in a falling market produces a negative Sharpe *mechanically*, independent of skill.
3. **The reported Sharpe of $-0.704$ against a buy-and-hold of $-0.547$ is therefore not a clean skill measurement.** The relevant statistic is the *conditional* comparison: the model traded 22 of 63 sessions and lost more per unit of exposure than the passive alternative. That is still a negative result, but the headline number overstates its precision.

**Required remedy:** report *per-fold* Sharpe across $\ge 5$ expanding folds, plus the market's own Sharpe per fold, and evaluate the model's *alpha* (regression intercept vs. the underlying) rather than raw Sharpe. Without regime stratification, a single 63-day OOS window in a downtrend cannot discriminate "no skill" from "long-only bias in a bear tape."

---

# 4. Deflated Sharpe Ratio — Implementation Audit

## 4.1 What the implementation gets right

The formula is a faithful transcription of Bailey & López de Prado (2014), *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality*:

$$
\widehat{\mathrm{DSR}} = \Phi\!\left(\frac{(\hat{SR}-SR^{*})\sqrt{T-1}}{\sqrt{1-\gamma_3\hat{SR}+\frac{\gamma_4-1}{4}\hat{SR}^2}}\right)
$$

with the expected-maximum benchmark

$$
SR^{*} = \sigma_{SR}\left[(1-\gamma)\Phi^{-1}\!\left(1-\tfrac{1}{N}\right) + \gamma\,\Phi^{-1}\!\left(1-\tfrac{1}{Ne}\right)\right]
$$

Correct elements:
- Euler–Mascheroni constant to full binary64 precision. ✔
- Gumbel-limit expected-maximum approximation — the standard and correct choice. ✔
- $N=1 \Rightarrow SR^{*}=0$, reducing exactly to PSR. ✔ (Correct and often botched.)
- De-annualisation of both $\hat{SR}$ and $\sigma_{SR}$ by $\sqrt{252}$ before combining with $\sqrt{T-1}$ — **dimensionally correct**, and this is the most common error in DSR implementations in the wild. ✔
- The Pearson bound check $\gamma_4 \ge 1+\gamma_3^2$ with a scaled epsilon envelope. ✔ Thoughtful; the two-point-distribution rationale in the comment is exactly right.
- Explicit refusal to fabricate $\sigma_{SR}=1$ when cross-trial dispersion is unavailable; falls back to the null sampling error $1/\sqrt{T-1}$. ✔ This is a genuinely good decision and better than most vendor implementations.
- Clamping to $[0,1]$. ✔

**On code quality alone this is one of the better DSR implementations I have audited.** The defects below are about *how it is being called*, not primarily about the mathematics inside it.

## 4.2 Defect D-1 (P1 — CRITICAL): `sample_length_bars` uses nominal, not effective, sample size

The term $\sqrt{T-1}$ is the reciprocal of the asymptotic standard error of the Sharpe estimator **under i.i.d. returns**. Your validation returns are not i.i.d.:

- Overlapping 21-bar feature windows induce feature autocorrelation $\approx 0.95$ (§3.2 Channel B).
- The strategy holds one session and re-decides daily, so *return* autocorrelation is lower, but the *signal* autocorrelation is high, which clusters trades and inflates realised-Sharpe variance.
- Only 22 of 63 periods have nonzero return; the remaining 41 are exact zeros.

**That last point is the sharpest issue.** `_portfolio_period_returns` records $0.0$ on non-UP days. The Sharpe is then computed over a series with 65% structural zeros. This **deflates the sample standard deviation** relative to the standard deviation of the *active* returns, and inflates the magnitude of the Sharpe ratio (in whichever direction the mean points). Concretely, if active returns have mean $\mu_a$ and sd $\sigma_a$, then the padded series has

$$
\mu_p = \tfrac{22}{63}\mu_a, \qquad
\sigma_p^2 = \tfrac{22}{63}\sigma_a^2 + \tfrac{22}{63}\tfrac{41}{63}\mu_a^2 \approx \tfrac{22}{63}\sigma_a^2
$$
$$
\Rightarrow \quad SR_p \approx \sqrt{\tfrac{22}{63}}\; SR_a = 0.591\,SR_a
$$

The padded Sharpe is a *scaled* version of the active Sharpe — mathematically defensible as a measure of capital-weighted performance, but the **variance of the estimator is governed by the 22 active observations, not the 63 padded ones.** Feeding $T=63$ into $\sqrt{T-1}$ overstates the precision by $\sqrt{62/21}=1.72\times$.

**Combined with the overlapping-window effect (§3.2, $n_{\text{eff}}\approx 1.5$–$3$ for slow features), the true effective sample size for the INFY trial is plausibly single digits, not 63.**

**Consequence:** the DSR is being computed with a $\sqrt{T-1}$ that is too large by a factor of 2–5. **For a *negative* Sharpe this makes DSR too small — the gate fails harder than it should.** So no false positive has been produced. **But the moment a positive Sharpe appears, this defect flips sign and manufactures false confidence.** It must be fixed before, not after, the first promising result.

**Remedy:**
```python
# Use effective sample size, not nominal bar count.
# n_eff = T * (1 - rho1) / (1 + rho1), floored at the number of
# genuinely active (nonzero-exposure) periods.
n_eff = min(
    active_periods,
    int(T * (1.0 - rho1) / (1.0 + rho1)),
)
```
and add `newey_west_lag` support so the Sharpe standard error uses an HAC estimator:

$$
\widehat{\mathrm{se}}(SR) = \sqrt{\frac{1 + \sum_{k=1}^{q}\left(1-\frac{k}{q+1}\right)2\hat\rho_k}{T}}\cdot\sqrt{1-\gamma_3 SR + \tfrac{\gamma_4-1}{4}SR^2}
$$

## 4.3 Defect D-2 (P1 — CRITICAL): the trial count is both under- and over-stated, and no reconciliation exists

`multiplicity_count = 3` for the INFY trial. But by the time that number was recorded, the programme had executed:

| Search activity | Trials |
|---|---:|
| INFY threshold variants | 3 |
| NIFTY 50 campaign, schema v1 | 51 |
| NIFTY 50 campaign, schema v2 | 50 |
| Alternative feature screens (gap, CLV, range expansion, volume z, dollar volume, control) | ≥ 6 |
| Cross-sectional horizon screens | ≥ 6 |
| Feature schema versions (v1, v2) | ×2 multiplier on the above |
| **Total pre-declared configurations touching this data** | **≥ 116** |

**The DSR deflated against 3 when the honest search count is ≥116.** Compute the difference:

$$
\mathbb{E}[\max_{N=3}] = (1-\gamma)\Phi^{-1}(2/3) + \gamma\Phi^{-1}(1-\tfrac{1}{3e}) = 0.4228(0.4307) + 0.5772(1.0938) = 0.8135
$$
$$
\mathbb{E}[\max_{N=116}] = 0.4228\,\Phi^{-1}(0.99138) + 0.5772\,\Phi^{-1}(0.99683) = 0.4228(2.3818)+0.5772(2.7278) = \boxed{2.5815}
$$

**The correct selection benchmark is 3.17× the one applied.** In annualised terms with $\sigma_{SR}=1/\sqrt{62}=0.127$ periodic → $2.015$ annualised, the hurdle moves from $SR^{*}=1.64$ to $SR^{*}=5.20$ annualised. Every DSR in the campaign is **overstated**. Since all of them failed anyway, no harm has been done — but the audit trail is wrong, and **a future campaign that reports DSR = 0.96 against `num_trials=3` would be reporting a number that is off by three standard errors.**

**The offsetting correction:** as established in §3.2 Channel D, the 50 NIFTY names are ~2 effective independent trials because of the $\bar\rho\approx 0.5$ common factor. So the *honest* trial count is not a raw 116 either. The defensible construction is:

$$
N_{\text{eff}} = \underbrace{N_{\text{config}}}_{\text{genuinely distinct hypotheses}} \times \underbrace{\frac{N_{\text{names}}}{1+(N_{\text{names}}-1)\bar\rho}}_{\text{cross-sectional effective breadth}}
$$

With $N_{\text{config}} \approx 15$ genuinely distinct specifications and $N_{\text{eff,names}}\approx 2$: $N_{\text{eff}} \approx 30$, giving $\mathbb{E}[\max_{30}] = 2.156$. **That is the number that should be in the evidence store**, with $\bar\rho$ computed and stored per campaign rather than assumed.

**Remedy:** `multiplicity_count` must be sourced from a **monotonic, append-only, cross-campaign trial ledger** that cannot be reset by starting a new script. It must record every configuration ever evaluated against the same underlying data, and it must apply the correlation adjustment with a stored, auditable $\bar\rho$. **A trial counter that resets per-script is not a multiplicity control; it is a formality.**

## 4.4 Defect D-3 (P2 — MAJOR): default `skewness=0.0, kurtosis=3.0` silently discards the non-normality correction

The entire *raison d'être* of PSR/DSR over the naive Sharpe is the $\gamma_3, \gamma_4$ correction. Defaulting to Gaussian moments reduces the variance term to $1 + \tfrac{1}{2}SR^2$, which is the classic Lo (2002) i.i.d.-normal result — i.e. **the implementation defaults to the thing it exists to improve upon.**

Indian equity daily returns exhibit $\gamma_3 \approx -0.3$ to $-0.8$ and $\gamma_4 \approx 6$–$12$. Strategy returns with a binary entry filter are worse: the padded-zero structure alone produces extreme excess kurtosis. For the INFY trial with 41 zeros and 22 active returns, if active returns are roughly Gaussian with $SR_a$ periodic $\approx -0.075$, the padded series has

$$
\gamma_4 \approx \frac{63}{22}\times 3 = 8.6
$$

Substituting into the variance term at $SR_p = -0.0443$ periodic:

$$
V_{\text{gauss}} = 1 - 0 + \tfrac{3-1}{4}(0.0443)^2 = 1.00098
$$
$$
V_{\text{fat}} = 1 - 0 + \tfrac{8.6-1}{4}(0.0443)^2 = 1.00373
$$

Small here — **but only because $SR$ is near zero.** The correction scales as $SR^2$, so at $SR=1.5$ annualised ($0.0945$ periodic) with $\gamma_4=8.6$, $V$ rises from $1.0045$ to $1.017$, and at monthly frequency with $SR$ periodic $\approx 0.43$ the correction is a $30\%$ change in the standard error. **Defaulting to Gaussian is safe only in the regime where DSR does not matter.**

**Remedy:** make `skewness` and `kurtosis` **required arguments** computed from the realised return series. Remove the defaults. Add a guard rejecting any DSR call where the moments were not empirically estimated from $\ge 30$ active observations.

## 4.5 Defect D-4 (P2 — MAJOR): no feasibility pre-check; degenerate outcomes consume deflation ordinals

Trials 1 and 2 produced no trades, zero variance, and undefined Sharpe — yet incremented `multiplicity_count`. This is doubly wrong:

1. **A trial that takes zero positions has tested no hypothesis.** It should not count against multiplicity, because it cannot have selected a winner. Counting it is conservative but incoherent — DSR's $\mathbb{E}[\max]$ is over the *distribution of achieved Sharpes*, and a zero-variance run has no Sharpe to contribute to that maximum.
2. **It was avoidable.** As shown in §1.3, a two-line pre-check on the training-partition score distribution would have flagged $P(\text{any } s_j > \tau) = 0.229$ before execution.

**Remedy:**
```python
def assert_threshold_feasible(train_scores, tau, min_expected_signals=5):
    mu, sd = train_scores.mean(), train_scores.std(ddof=1)
    if sd <= 0:
        raise ModelingError(DEGENERATE_SCORE_DISTRIBUTION, ...)
    p = 1.0 - NormalDist(mu, sd).cdf(tau)
    expected = p * n_validation
    if expected < min_expected_signals:
        raise ModelingError(
            THRESHOLD_INFEASIBLE,
            f"threshold {tau} yields {expected:.2f} expected signals; "
            f"train score dist is N({mu:.4f}, {sd:.4f})",
        )
```
Raise this **before** the ordinal is assigned. Infeasible-threshold rejections should be logged but excluded from the multiplicity ledger.

## 4.6 Defect D-5 (P3 — MINOR): `periods_per_year=252` is wrong for NSE

NSE trades approximately **246 sessions/year** (2024: 250; 2025: 245; long-run mean ≈ 246 after Diwali Muhurat, exchange holidays, and occasional closures). Using 252 inflates annualised Sharpe by $\sqrt{252/246}=1.0121$, i.e. **1.21%**. Immaterial to any conclusion here, but it is a hardcoded foreign-market constant in an Indian-equities system and should be sourced from `SessionCalendarV1`, which already knows the true session count.

Additionally: `_expected_max_standard_normal` is called with `num_trials` and evaluates `inv_cdf(1 - 1/(N*e))`. For $N=1$ the guard returns 0.0 correctly. For very large $N$ (>10^6) the Gumbel approximation degrades, but this is not a live concern.

---

# 5. Root Cause Adjudication

## 5.1 The question, posed precisely

Is the ridge estimator generating false signals from a feature family that contains real information, or is the feature family itself informationless?

**Answer: the feature family is informationless at the tested horizon net of costs, and the estimator is behaving correctly by refusing to produce signals. The estimator is not the problem, and replacing it will not help.**

## 5.2 The evidentiary chain

**Evidence 1 — Direct IC measurement.** Mean IC across all screened feature families: $+0.007$ to $+0.015$, against a required break-even of $\rho^{*}=0.107$ (§2.2). Deficit factor 7–15×. **This is a direct, model-free measurement of information content that does not depend on the estimator at all.**

**Evidence 2 — The v2 result is statistically identical to zero.** 21/50 positive Sharpe, $z=-1.13$, $p=0.26$. Median Sharpe $-0.2278$ with a cross-sectional dispersion that is fully consistent with sampling noise around zero on a 63-day window. **Failing to reject $H_0: \text{IC}=0$ at 50 names is strong evidence, because 50 names in a correlated market is $N_{\text{eff}}\approx 2$ — but the *pooled* IC estimate has $n \approx 50\times 63 = 3150$ observations, and even at $N_{\text{eff}}=2$ names the pooled standard error on IC is $\approx 1/\sqrt{63\times 2} = 0.089$. Your measured 0.015 is $0.17\sigma$ from zero.**

**Evidence 3 — The estimator's own diagnostic.** The fitted intercept equals the class prior to seven digits, and $\|\hat{\boldsymbol\beta}\|$ implies score dispersion of $0.053$ against a base-rate offset of $0.114$. **A ridge whose signal component is 46% of its prior component is telling you, in its own coefficients, that it found nothing.** This is not a failure mode — this is ridge regression working exactly as designed under $\lambda>0$ and $\rho\approx 0$: shrink toward the mean.

**Evidence 4 — PREVIOUS_SIGN beat the model.** A one-bit rule with zero parameters achieved $+0.144$ Sharpe while the 6-parameter ridge achieved $-0.704$. Note that PREVIOUS_SIGN's $+0.144$ Sharpe on 63 observations has standard error $\approx\sqrt{252/63}=2.0$, so **it is also indistinguishable from zero** — do not chase it. But the ordering is diagnostic: **when a zero-parameter rule outperforms a fitted model on the same data, the fitted model is fitting noise.** The 6 estimated parameters cost more in variance than they earn in bias reduction, which is the textbook signature of $\text{signal} \approx 0$.

**Evidence 5 — The horizon gradient.** Every daily-horizon screen: flat negative. The monthly cross-sectional screen: $t=1.18$, inconclusive. This matches the break-even-IC formula's $1/\sqrt{h}$ scaling *exactly* (§2.2). **The programme has independently rediscovered its own cost constraint.**

**Evidence 6 — The v1→v2 improvement diagnoses contamination, not progress.** v1's 14/40 was *significantly worse than chance* ($p=0.058$), the signature of a systematic error (train/serve feature skew via Wilder IIR seeds). v2's 21/50 is *indistinguishable from chance*. **Fixing a first-order bug moved the result from "wrong" to "nothing." There was never a hidden edge underneath.**

## 5.3 The three genuine defects that did *not* cause the null result

To be scrupulously fair to the engineering, and to prevent these from being scapegoated:

| Defect | Would it have created edge if fixed? |
|---|---|
| Intercept/threshold mismatch (Trials 1–2) | **No.** Fixed in Trial 3; result was $-0.704$ Sharpe. |
| v1 Wilder seed contamination | **No.** Fixed in v2; result moved to "statistically zero." |
| 2-session embargo (should be 21) | **No — it works the wrong way.** Insufficient embargo *inflates* apparent performance. Fixing it makes results *worse*, not better. |

**All three known defects, when corrected, move the result toward or past zero. None of them was suppressing a real signal.** This is the decisive argument.

## 5.4 The actual root cause, stated plainly

> **The hypothesis space was exhausted before the code was written.** Six univariate price-derived technical indicators on daily NIFTY 50 bars is the most heavily arbitraged signal family in existence. The 22.4 bp statutory round trip on NSE — driven overwhelmingly by the 0.1% double-sided STT, which is a *tax*, not a spread, and therefore cannot be reduced by better execution — imposes a break-even IC of ~0.107 at a 1-day horizon. **No price-only daily signal on liquid Indian large caps has ever attained an IC within a factor of three of that.** The campaign correctly measured zero.

The secondary root cause is structural and organisational:

> **The estimator, loss function, label encoding, and horizon were all fixed before the cost-to-edge feasibility arithmetic in §2.2 was performed.** That single calculation — five lines, no data required beyond a volatility estimate and the NSE fee schedule — would have shown a 71× cost-to-edge ratio and redirected the entire programme. **The system built an exceptional apparatus for measuring a quantity that could be shown a priori to be unmeasurable at the chosen horizon.**

## 5.5 What the system got right, and should be preserved verbatim

I want this on the record because it is unusual:

1. **The DEGENERATE_RETURN_SERIES guard.** Refusing to publish DSR ≈ 0.5 for a strategy that never traded is exactly correct. A do-nothing model must not outrank a losing model. Most institutional backtesters silently report 0.0 Sharpe here and let it pass screens.
2. **Cost binding at the label level.** `RoundTripCostQuoteV1` binds instrument, entry price, exit price, and execution contract version, and `_validate_quote` rejects any mismatch. Costs cannot be silently changed after the fact. **This is better than most production systems.**
3. **Point-in-time enforcement.** `record.available_at > session.close_at` → `POINT_IN_TIME_VIOLATION`, checked per-record, per-row. Combined with the canonical feature window, this closes the two most common leakage vectors.
4. **The single feature kernel.** One `compute_feature_values` called by both training and execution, with a docstring that names the historical incident it prevents. This is the correct architecture and the correct documentation of it.
5. **Publishing the null.** 101 trials, no edge, `verdict=RESEARCH_ONLY`, and the result written down as *"the platform works and the strategy does not."* **This is the single most valuable artifact in the repository.** It is also the behaviour that most research organisations structurally cannot produce.
6. **The refusal to sweep a fourth threshold.** CURRENT.md explicitly declines to continue searching and states why. Correct.

## 5.6 The one place the discipline slipped

CURRENT.md flags this itself, and the flag is right:

> *"the prior record stopped after three negative screens and argued stopping was disciplined. That argument does not expire because a result finally came out positive. Stopping on negatives and continuing on a positive is precisely how false positives are manufactured."*

The cross-sectional $t=1.18$ ($p=0.24$ two-sided) received continued investigation while equally-inconclusive negative results did not. **The stopping rule must be pre-declared and symmetric.** Formally: declare $N_{\text{screens}}$, the horizon set, and the promotion threshold *before* the first screen, and either run all of them or stop by a pre-registered sequential boundary (O'Brien–Fleming or alpha-spending). A $t$ of 1.18 does not justify a multi-instrument dataset contract, and the document is correct to say so.

---

# 6. Actionable Alpha Blueprint

## 6.0 The governing constraint — read this before anything else

$$
\boxed{\rho^{*} = \frac{c}{\sigma_r \sqrt{h}\;\lambda(\tau)}}
$$

Every design decision below exists to move this inequality. There are exactly four levers:

| Lever | Mechanism | Feasible range | Verdict |
|---|---|---|---|
| **↓ $c$** | Reduce round-trip cost | 22.4 → ~10 bp (intraday MIS: no STT on delivery leg, but STT 0.025% sell-side; net ~8–12 bp) | Available but requires intraday infra |
| **↑ $h$** | Lengthen holding period | 1 → 21 days: $\rho^{*}$ falls 4.6× | **Cheapest, highest-leverage, do this first** |
| **↑ $\lambda(\tau)$** | Increase selectivity | 1.40 → 2.66 at 99th pctile: 1.9× | Available, but shrinks trade count → widens CIs |
| **↑ $\rho$** | Find better information | 0.015 → 0.03–0.05 requires *new data*, not new models | **Necessary; models alone cannot do this** |

Combining $h=21$, $\tau$ at the 90th percentile ($\lambda=1.755$), and $\sigma_r=1.5\%$:

$$
\rho^{*}_{\text{target}} = \frac{0.00224}{0.015\times\sqrt{21}\times 1.755} = \boxed{0.0186}
$$

**An IC of 0.019 is achievable with real cross-sectional data.** An IC of 0.107 is not. **This is the reframing that makes the programme viable.**

---

## 6.1 IMMEDIATE — Estimator and label corrections (Week 1–2)

These do not create alpha. They ensure that when alpha appears, you can believe it.

### 6.1.1 Replace ±1 MSE with continuous, volatility-scaled targets

Delete the binarisation in `_row_from_quote`. Regress on the net return directly, scaled by conditional volatility:

$$
\tilde{y}_t = \frac{r^{\text{net}}_{t\to t+h}}{\hat\sigma_t \sqrt{h}}, \qquad \hat\sigma_t = \text{EWMA}_{\lambda=0.94}(r) \;\; \text{or} \;\; \text{ATR}_{14}/C_t
$$

Then clip $\tilde y$ at $\pm 4$ to bound the influence of single events. Rationale:

- Recovers the magnitude information currently destroyed.
- Volatility scaling makes the target **homoscedastic and pooled across instruments**, which is what enables cross-sectional models.
- Eliminates the class-imbalance/intercept pathology entirely: $\mathbb{E}[\tilde y]\approx 0$ by construction, so $\tau=0$ becomes correct rather than accidentally wrong.

**If a classifier is genuinely required for a downstream contract**, use **logistic regression with an explicit intercept offset**:
$$
\eta_j = \mathbf{x}_j^\top\boldsymbol\beta + \beta_0, \qquad \text{trade iff } \eta_j > \mathrm{logit}(p^*), \;\; p^* = \frac{c}{c + \mathbb{E}[|r| \mid \text{move}]}
$$
This sets the operating point from the **cost/payoff ratio**, not from an arbitrary zero.

### 6.1.2 Adopt López de Prado triple-barrier labelling

Replace the fixed 2-session horizon with:

$$
\text{Upper barrier: } P_t(1 + k_u \hat\sigma_t), \quad
\text{Lower: } P_t(1 - k_l \hat\sigma_t), \quad
\text{Vertical: } t + h_{\max}
$$

with $k_u \approx 2$, $k_l \approx 1$ (asymmetric, reflecting the cost hurdle), $h_{\max}=21$. Assign **sample weights** by return attribution and **uniqueness weights** $u_i = 1/\bar c_i$ where $\bar c_i$ is the average concurrency of label $i$'s span. This is mandatory once labels overlap.

### 6.1.3 Fix the embargo, the effective sample size, and the trial ledger

| Fix | Change |
|---|---|
| Embargo | $2 \to \max(h_{\text{label}}, w_{\text{feature}}) = 21$ sessions minimum |
| DSR `sample_length_bars` | nominal $T$ → $n_{\text{eff}} = \min(\text{active periods},\; T\frac{1-\rho_1}{1+\rho_1})$ |
| DSR moments | remove Gaussian defaults; require empirical $\gamma_3, \gamma_4$ |
| DSR `num_trials` | per-script counter → **append-only cross-campaign ledger** with $\bar\rho$-adjusted $N_{\text{eff}}$ |
| Sharpe SE | i.i.d. → **Newey–West HAC**, lag $q = \lfloor 4(T/100)^{2/9}\rfloor$ |
| `periods_per_year` | hardcoded 252 → derived from `SessionCalendarV1` (≈246) |
| Threshold | add pre-execution feasibility gate (§4.5) |
| Purging | **produce `modeling/purging.py` for independent adjudication** |

### 6.1.4 Add mandatory pre-trial feasibility gate

Before any trial consumes an ordinal, require:

$$
\hat\rho_{\text{IC}} \cdot \sigma_r \sqrt{h}\cdot\lambda(\tau) > 1.5\,c
$$

on the **training partition only**. A 50% margin over costs. If it fails, the trial is rejected as economically infeasible and does not increment multiplicity. **This gate alone would have stopped 101 of your 104 trials before execution.**

---

## 6.2 PRIMARY RECOMMENDATION — Cross-Sectional Residual Momentum (Weeks 3–10)

This is the highest expected-value direction and your own evidence points to it.

### Architecture

**Step 1 — Universe.** NSE 500 with hard liquidity screens applied *point-in-time*:
- 20-day median traded value $\ge$ ₹10 crore
- Price $\ge$ ₹50 (avoids tick-size and penny-stock effects)
- Not in ASM/GSM surveillance, not in T2T segment, not suspended
- Free-float market cap $\ge$ ₹1,000 crore

Critically: **reconstruct historical index membership**. Your existing `HistoricalUniverseSnapshotV1` machinery already enforces this — extend it, do not bypass it. Using current NSE 500 membership over a 2020–2025 backtest is a survivorship bias worth 2–4% p.a. in India, which is larger than any edge you are looking for.

**Step 2 — Factor model and residualisation.** This is where the alpha is.

$$
r_{i,t} = \alpha_i + \beta_i^{\text{MKT}} r^{\text{NIFTY}}_t + \beta_i^{\text{SMB}} f^{\text{SMB}}_t + \beta_i^{\text{HML}} f^{\text{HML}}_t + \beta_i^{\text{SECTOR}} f^{\text{sector}}_t + \varepsilon_{i,t}
$$

Estimate $\boldsymbol\beta_i$ on a rolling 252-day window (or via Barra-style cross-sectional regression). Then:

$$
\text{RESMOM}_{i,t} = \frac{\sum_{s=t-251}^{t-21}\varepsilon_{i,s}}{\hat\sigma_{\varepsilon,i}\sqrt{231}}
$$

Note the **21-day skip** — this excludes the short-term reversal window, which is the single most important construction detail and is why raw 12-month momentum underperforms residual momentum.

**Why residual momentum specifically for India:**
- Blitz, Huij & Martens (2011) document residual momentum Sharpe roughly **double** conventional momentum in developed markets, driven by the elimination of factor-timing risk.
- Indian equity markets are **highly sector-concentrated** (Financials ~35% of NIFTY, IT ~13%). Raw momentum in India is substantially a sector bet, which produces violent drawdowns on sector rotations (Mar 2020: raw momentum $-40\%$; Feb 2021 value rotation: raw momentum $-18\%$). **Residualising against sector removes the dominant drawdown driver.**
- Momentum crashes are conditional on market state (Daniel & Moskowitz 2016). Residualisation plus the dynamic scaling in Step 5 addresses both.

**Step 3 — Complementary signal blocks.** Each must be residualised and neutralised identically:

| Block | Signals | Rationale for India |
|---|---|---|
| **Residual momentum** | 12-1 resmom, 6-1 resmom | Core |
| **Short-term reversal** | 5-day resid return (sign-flipped) | Strong in India due to retail flow; **but check cost survival at $h=5$** |
| **Quality** | Gross profitability, accruals, ROIC stability, debt/EBITDA | Robust in India; promoter-pledge data is a genuine India-specific edge |
| **Low volatility** | 60d idiosyncratic vol, beta | Low-vol anomaly is unusually strong in India |
| **Value** | EV/EBITDA, FCF yield, B/P — **sector-neutral** | Raw value in India is a financials bet; must neutralise |
| **India-specific ★** | FII/DII daily flows, promoter pledge Δ, bulk/block deal flow, F&O OI + rollover %, index rebalance anticipation, delivery % | **This is where genuinely unmined information lives** |

The last row is the most important line in this document. **FII/DII flow data, promoter pledge disclosures, delivery-percentage data, and F&O open-interest positioning are published by NSE/SEBI, are not in any global dataset, and are materially under-researched.** If a real edge exists for this programme, it is here — not in another transform of OHLC.

**Step 4 — Combination.** Do **not** start with LightGBM.

**Phase A (baseline):** cross-sectional z-score each signal within date and sector, winsorise at $\pm 3$, equal-weight combine. This is your benchmark. If a gradient-boosted model cannot beat an equal-weight composite out-of-sample, the model is fitting noise.

**Phase B (if and only if Phase A shows IC > 0.02 net):** LightGBM with hard constraints:
```python
LGBMRegressor(
    objective="huber",          # robust to return outliers
    num_leaves=15,              # hard cap — financial data supports ~4 interactions max
    max_depth=4,
    min_child_samples=200,      # large; prevents leaf-level noise fitting
    learning_rate=0.02,
    n_estimators=400,
    subsample=0.7, subsample_freq=1,
    colsample_bytree=0.7,
    reg_alpha=1.0, reg_lambda=10.0,
    monotone_constraints=[...],  # ENFORCE economic priors
)
```
`monotone_constraints` is not optional. If you believe higher quality → higher expected return, **encode it**. A tree model free to learn a non-monotone quality response is a tree model free to fit noise. This is the single most effective regulariser in financial GBMs.

Train on **pooled cross-section with uniqueness weights**, not per-instrument. Your current architecture trains 50 independent models on ~400 rows each; a pooled model sees $50\times400 = 20{,}000$ rows for the same 6 parameters. **The sample-size gain is 50×, which is worth more than any estimator upgrade.** Note that `modeling/labels.py` binds each feature row to one acquisition manifest — this is the architectural change CURRENT.md correctly identified as expensive, and it is the change I am recommending you make. The $t=1.18$ did not justify it; **the break-even-IC arithmetic in §2.2 does.**

**Step 5 — Portfolio construction.** This is where residual momentum's Sharpe actually comes from, and it is currently absent from the stack entirely.

Long-only (Indian short-selling in cash equity is impractical for most mandates; SLB is thin):

$$
\begin{aligned}
\max_{\mathbf{w}} \quad & \mathbf{w}^\top\hat{\boldsymbol\mu} - \tfrac{\kappa}{2}\mathbf{w}^\top\boldsymbol\Sigma\mathbf{w} - c^\top|\mathbf{w}-\mathbf{w}_{\text{prev}}| \\
\text{s.t.}\quad
& \mathbf{1}^\top\mathbf{w} = 1, \quad 0 \le w_i \le 0.04 \\
& |\mathbf{w}^\top\boldsymbol\beta^{\text{sector}} - \mathbf{w}_{\text{bm}}^\top\boldsymbol\beta^{\text{sector}}| \le 0.05 \;\;\forall\text{ sector} \\
& |\mathbf{w}^\top\boldsymbol\beta^{\text{MKT}} - 1| \le 0.10 \\
& \|\mathbf{w}-\mathbf{w}_{\text{prev}}\|_1 \le 0.15 \;\;\text{(monthly turnover cap)}
\end{aligned}
$$

**The $\ell_1$ transaction-cost term inside the objective is mandatory, not a post-hoc adjustment.** Optimising gross then subtracting costs produces a portfolio that is not cost-aware; it produces the wrong *portfolio*, not just the wrong *estimate*. With a 22.4 bp round trip and a 15% monthly turnover cap, annual cost drag is $0.15\times12\times0.00224 = 0.40\%$ — **entirely tolerable, versus the 56% p.a. drag of daily trading.** This is the horizon lever in §6.0, made concrete.

Add **volatility targeting** at the portfolio level: scale gross exposure to hit 10% annualised realised vol, which mechanically improves Sharpe under vol clustering and cuts momentum-crash tail risk (Barroso & Santa-Clara 2015 — this raised momentum Sharpe from 0.53 to 0.97 in US data).

**Step 6 — Validation.** Combinatorially Purged Cross-Validation (CPCV): $N=8$ groups, $k=2$ test groups → 28 paths, purge $=h_{\max}$, embargo $=\max(h,w)$. This gives a **distribution** of Sharpe ratios, from which you compute the **Probability of Backtest Overfitting** (PBO):

$$
\text{PBO} = P\big(\text{rank}_{\text{OOS}}(\text{IS-best}) < \text{median}\big)
$$

**Require PBO < 0.20 AND DSR > 0.95 AND net-of-cost IC > 0.02 AND positive alpha vs. the six baselines you already run.** All four, pre-declared, no exceptions.

### Realistic expectation

| Metric | Honest range |
|---|---|
| Gross IC (monthly, pooled) | 0.02 – 0.04 |
| Net Sharpe after 40 bp/yr costs | **0.5 – 0.9** |
| Max drawdown | 18% – 30% |
| Annual turnover | 150% – 250% |
| Capacity | ₹200–800 cr before impact bites |
| P(reaching DSR > 0.95) | **~30–40%** |

**A net Sharpe of 0.7 is a genuinely good, institutionally fundable systematic equity product in India. It is also roughly ten times better than anything the current stack has produced. Calibrate expectations to 0.7, not to 2.0.**

---

## 6.3 SECONDARY — Regime-conditional overlay (only after 6.2 is validated)

Do **not** build a regime-switching *return* model. Markov-switching mean models are notoriously unstable out-of-sample and add 2–4 parameters per state to a problem that already lacks data.

**Do** build a regime-conditional **exposure** model, which is far more robust because regimes are much more detectable in volatility than in means:

$$
\text{State}_t = f\big(\text{India VIX level \& term structure},\; \text{realised/implied vol ratio},\; \text{NIFTY 200DMA},\; \text{cross-sectional dispersion},\; \text{FII net flow 20d}\big)
$$

Use a **2-state Gaussian HMM on volatility and dispersion only** (not returns), or simply a rule-based classifier — the rule usually wins. Then:

| State | Action |
|---|---|
| Calm / trending | Full momentum weight, target vol 10% |
| Stressed (VIX > 80th pctile, index < 200DMA) | Cut momentum weight 50%, raise quality/low-vol, target vol 6% |
| Recovery (post-crash, index crossing back above 200DMA) | **Momentum crash regime** — cut momentum to zero for 21 sessions |

The third row addresses the specific failure mode that killed momentum in Mar–Apr 2020 and Feb 2021. Daniel & Moskowitz show momentum's conditional Sharpe is *negative* in the two months following a market bottom. **A single rule that flattens momentum in that window is worth more than any estimator upgrade.**

Validate the overlay on a **separate holdout period from the one used to fit 6.2**, or the regime rule becomes another selection dimension in your multiplicity count.

---

## 6.4 TERTIARY — Intraday cost restructuring (only if daily horizon is a hard requirement)

If a 1-day horizon is mandated for reasons outside this audit, the *only* viable lever is $c$:

- **MIS (intraday square-off):** STT drops from 0.1% both legs to 0.025% sell-side only. All-in round trip falls to roughly **8–12 bp**, reducing $\rho^{*}$ from 0.107 to ~0.045.
- **Still 3× above your measured IC.** Feasible only with genuinely new information: order-flow imbalance from full-depth tick data, F&O basis and OI dynamics, or opening-auction imbalance.
- Requires colocation-adjacent latency, tick-data infrastructure, and a materially different risk framework.

**I do not recommend this path.** The infrastructure cost is high, the capacity is low, and the competitive field (domestic prop desks and HFT firms with NSE colocation) is the most sophisticated in the market. **The cross-sectional monthly path in §6.2 has better risk-adjusted expected value per unit of engineering effort by a wide margin.**

---

# 7. Prioritised Defect Register

| ID | Severity | Component | Finding | Remedy |
|---|---|---|---|---|
| **D-0** | **P1 BLOCKER** | `modeling/purging.py` | **File absent from audit package.** Highest-risk unadjudicated component; purging bugs produce optimistic results invisible downstream | Produce for Phase 2 independent adjudication |
| **D-1** | **P1** | `multiplicity.py` | `sample_length_bars` uses nominal $T=63$; true $n_{\text{eff}}\approx 2$–$21$ due to 21-bar window overlap and 41 structural zeros. Overstates precision 2–5× | Effective sample size + Newey–West HAC SE |
| **D-2** | **P1** | Campaign driver | `multiplicity_count=3` vs. ≥116 actual configurations. Correct $\mathbb{E}[\max]$ is 3.17× larger. Counter resets per script | Append-only cross-campaign ledger with $\bar\rho$-adjusted $N_{\text{eff}}$ |
| **D-3** | **P1** | Fold construction | Embargo of 2 covers label horizon but **not** the 21-bar feature window. Train/val features share 18/21 bars; Wilder seeds 60% shared | Embargo $= \max(h_{\text{label}}, w_{\text{feature}}) = 21$ |
| **D-4** | **P1** | `labels.py:_row_from_quote` | Binarisation `"UP" if net_return > 0` destroys the full magnitude distribution — the largest information loss in the stack | Continuous vol-scaled target; triple-barrier |
| **D-5** | **P2** | `multiplicity.py` | Gaussian moment defaults ($\gamma_3{=}0,\gamma_4{=}3$) disable the non-normality correction that is DSR's entire purpose | Make moments required; estimate empirically |
| **D-6** | **P2** | `ridge.py` / runner | No threshold-feasibility pre-check; degenerate zero-trade trials consume deflation ordinals | Pre-execution gate on $\Phi((\tau-\mu_s)/\sigma_s)$; exclude infeasible runs from ledger |
| **D-7** | **P2** | `ridge.py` | Named `fit_ridge_classifier` but fits penalised OLS on ±1. `score_threshold=0` embeds a false $P(\text{UP})=0.5$ assumption | Rename, or migrate to logistic with cost-derived operating point |
| **D-8** | **P2** | `features.py` | 21-bar window truncates Wilder-14 to 6–7 smoothing iterations; ~60% residual seed weight. Internally consistent but **not** standard RSI/ATR | Extend warmup to ≥84 bars (schema v3), **or** rename to `rsi14_trunc21`/`atr14_trunc21` |
| **D-9** | **P2** | Validation | Single 63-day OOS fold in a declining tape; long-only bias confounds skill measurement | ≥5 expanding folds + CPCV; report alpha vs. underlying, not raw Sharpe |
| **D-10** | **P2** | `features.py` | Effective rank ≈ 2 of 6; $\mathrm{df}(\lambda)$ and $\kappa(\mathbf{X}^\top\mathbf{X})$ never computed or stored | Emit per-fold condition number and effective df as evidence artifacts |
| **D-11** | **P3** | `multiplicity.py` | `periods_per_year=252` hardcoded; NSE trades ≈246. Inflates annualised Sharpe 1.21% | Derive from `SessionCalendarV1` |
| **D-12** | **P3** | Cost model | 0.224% excludes MOO slippage and impact. True all-in 26–32 bp | Add slippage/impact model to `RoundTripCostQuoteV1` |
| **D-13** | **P3** | Process | Stopping rule was asymmetric — continued on the one positive, stopped on negatives | Pre-registered symmetric stopping with alpha-spending boundary |

---

# 8. Adjudication

**On the engineering:** The determinism, hashing, point-in-time enforcement, cost binding, single-kernel feature computation, and the DEGENERATE_RETURN_SERIES guard are of institutional quality and in several respects exceed what I observe at established desks. The system's willingness to publish `verdict=RESEARCH_ONLY` and to write down *"the platform works and the strategy does not"* is the strongest signal in the entire repository. **Preserve this apparatus. It is the asset.**

**On the research:** The result is correct and the conclusion should be accepted without reservation. **104 trials found no edge because no edge exists in six price-derived technical features on daily NIFTY 50 bars net of a 22.4 bp statutory round trip.** The break-even IC is ~0.107; the measured IC is 0.007–0.015; the deficit is 7–15×. Every known defect, when corrected, moved the result *toward* zero, never away from it — which is the decisive evidence that no signal was being suppressed.

**On the path forward:** The binding constraint is the **cost-to-horizon ratio**, not the estimator. Moving from a 1-day to a 21-day horizon reduces the required IC by 4.6×; moving from single-name to pooled cross-sectional increases the effective training sample by ~50×; and adding India-specific data (FII/DII flows, promoter pledges, delivery percentage, F&O positioning) is the only lever that can raise measured IC. **Cross-sectional residual momentum with sector neutralisation, cost-aware portfolio optimisation, and monthly rebalancing is the recommended architecture**, with a realistic target of net Sharpe 0.5–0.9 and a ~30–40% probability of clearing the DSR 0.95 gate.

**Non-negotiable preconditions** before any further campaign consumes an ordinal:

1. **D-0** — produce `purging.py` for independent adjudication.
2. **D-3** — embargo raised to 21 sessions.
3. **D-1, D-2, D-5** — DSR corrected for effective sample size, cross-campaign trial ledger, and empirical moments.
4. **D-6** — pre-execution economic feasibility gate: $\hat\rho\,\sigma_r\sqrt{h}\,\lambda(\tau) > 1.5c$ on training data only.
5. **D-4** — continuous vol-scaled labels replacing binary UP/DOWN.

The fourth precondition deserves emphasis. **A feasibility gate that requires the expected edge to exceed 1.5× costs, evaluated on training data before any trial is scored, would have rejected 101 of the 104 trials at zero cost and zero multiplicity penalty.** Installing it is the highest-return single change available, and it converts the multiplicity ledger from a passive accountant into an active constraint on the search.

Finally, on the governance contradiction flagged in CURRENT.md — `PHASE: P5 (Release Certified)` against *"Zero slices beyond 3 have a valid independent adjudication"* — I concur with the document's own resolution. **Read P5 as "code complete and statically green," not as certified.** The training runner, campaign driver, and all 104 research results sit in the unadjudicated set, and this audit does not change that status; it constrains what a future adjudication must examine.