# Kronos zero-shot trial: frozen declaration (short-horizon trial 10)

**Frozen 2026-09-29, before any Kronos forecast on real market data exists.** The only thing run
before this file is the environment set-up and a reading of the pinned model code. The timing probe
comes after it and uses synthetic bars. Its only job is to fix the compute scope by the rule below.

The rule this file inherits from `reports/short_horizon/TRIAL-LEDGER.md`: **a trial not listed here
cannot be added after a result is seen.**

## Why this trial exists, and what it overrides

- **Founder instruction.** On 2026-09-28 the founder said "yes" to planning a governed Kronos trial,
  then "yes go ahead" to the explained plan, its downloads and its three conflicts. The record is
  `agent_context/work/active/20260928-claude-kronos-trial.md`.
- **It overrides a standing instruction.** The short-horizon ledger says: "Do not run a tenth trial.
  It inherits ordinal 10, deflates everything here further ...". The founder chose to run exactly
  one, knowingly. This is that trial.
- **Why this model and not another checkpoint.** Kronos is pre-trained on financial candlesticks:
  12 billion K-line records from 45 exchanges, India (XNSE) among them. Independent work found
  off-the-shelf general-purpose models "perform poorly" on financial forecasting. Models pre-trained
  on financial data did better (Rahimikia, Ni and Wang, arXiv 2511.18578). TimesFM 3.0 and 2.5 are
  the general kind, and both failed here. Kronos is MIT-licensed, so it could sit in a commercial
  path.
- **The prior, stated before the result: expect it to fail.**
  - Kronos's own evidence is forecast accuracy (RankIC), not profit after Indian costs.
  - Its paper's backtest assumes 0.15% per trade, a different market and a different construction.
  - Every model tested on this data so far has lost to the noise control.

## Budget

| Item | Count | Notes |
|---|---:|---|
| Kronos zero-shot, hold 3 | **1 trial, ordinal 10** | Same data, subset, labels, costs and question as short-horizon trials 1-9 |
| `NOISE-K` control, 30 seeds | 0 | A control, not a candidate, as in the short-horizon ledger |
| Diagnostics (a)-(d) below | 0 | Declared now and reported, but never verdict-bearing and never promotable |

- The DSR is deflated against **10**.
- Trials 1-9 were published at 9. Against 10 each would read lower. Those figures are not edited
  here. See `agent_context/work/active/20260928-NOTICE-kronos-trial-10-declared.md`.
- **Nothing follows this trial:** no second model size after a result, no other hold, no threshold
  search and no fine-tuning. Any further attempt is ordinal 11, with its own dated declaration.

## Declared design

| Element | Declaration |
|---|---|
| Model | Kronos zero-shot, **`NeoQuasar/Kronos-base`** (102.3M) or **`NeoQuasar/Kronos-small`** (24.7M), chosen by the compute rule below, with `NeoQuasar/Kronos-Tokenizer-base`. Weights are MIT and in `.safetensors`, downloaded 2026-09-29 into plain folders under the workspace and verified by SHA-256 every time they are loaded, offline:<br>• tokenizer `0e0117387f39004a9016484a186a908917e22426`, `59d85f6a…2fc6bee`<br>• small `901c26c1332695a2a8f243eb2f37243a37bea320`, `b082dfcb…b3c3e020`<br>• base `2b554741eca47781b64468546e77fef3e85130e6`, `abff193a…11403b6d…5f4b83` |
| Code | `shiyu-coder/Kronos` model files at commit `67b630e67f6a18c9e9be918d9b4337c960db1e9a`, kept outside this repository. Verified against the commit's git blob SHA-1s. SHA-256: `model/__init__.py` `f8f856ca…6240c`, `model/kronos.py` `0a5f9028…41032`, `model/module.py` `a07edbad…a409f`. Read in full before any execution: no network access except the Hub download, no file writes, no subprocess. |
| Environment | Isolated **native ARM64** CPython 3.12.10 at `D:\quant_system_workspaces\scratch\kronos-trial-20260928\venv`. `torch 2.14.0+cpu` (`win_arm64`, from download.pytorch.org), `numpy 2.5.3`, `pandas 3.0.6`, `einops 0.8.1`, `huggingface_hub 0.33.1`, `safetensors 0.8.0`. The QuantOS `.venv`, `pyproject.toml` and `uv.lock` are untouched. |
| Universe | The **same 45-name subset** as trials 1-9, selected by the same imported code: `train_mizan.governed_acquisitions`, `universe_bound`, `turnover_ranked`, subset size 50, 45 universe-bound. Its survivorship and non-point-in-time liquidity biases are inherited and favour the candidate. |
| Data | Governed store `data/evidence/market-cache/nifty50-current-20160822-20260821/store`, adjusted by `build_mizan_feature_store.adjusted_bar_points(..., total_return=True, validated_factors=...)`. This is the same adjusted, total-return series the TimesFM generator used, in full OHLCV rather than close only. |
| Labels and costs | `run_short_horizon_experiment.build_decisions`, imported unchanged: the governed label path, dated NSE statutory costs quoted on raw executable opens, quantity 1, calendar `provider-derived-v1`. |
| Window | Decisions dated **on or after 2024-07-01** only. The Kronos paper (arXiv 2508.02739) says its pre-training data "extends up to June 2024", and its own tests begin in July 2024. The window runs to the last decision with a complete label; the store ends 2026-08-21. |
| Hold | **3 sessions only** (`horizon_sessions` 4). Decide at the close of k, enter at the open of k+1, exit at the open of k+4. |
| Input per decision | The trailing **512** adjusted daily bars ending at session k: open, high, low, close and volume. `amount` is derived by Kronos's own predictor as volume times mean(OHLC). Timestamps are session dates at 00:00. Future timestamps are the store's next four session dates; NSE publishes its trading calendar in advance. Nothing after the close of k is supplied. |
| Prediction | A 4-step autoregressive forecast. **`predicted_return = predicted_open[k+4] / predicted_open[k+1] - 1`**, the same open-to-open span the label measures. Both opens are model outputs. This improves on the TimesFM arm, whose model predicted only closes. |
| Sampling | `T = 1.0`, `top_p = 0.9`, `top_k = 0`, Kronos's documented defaults. `sample_count` S is set by the compute rule; Kronos's predictor averages the S paths. One batch holds all names on one decision date, seeded with `torch.manual_seed(20260929 + date.toordinal())`, so a resumed run reproduces the same draws. |
| Candidate rule | **Long a name at decision k if and only if `predicted_return > 0.00224`**, the round-trip cost figure used throughout this repository; otherwise cash. Fixed: no calibration and no abstention grid (C1 is not used). The clean window, about 530 sessions, is shorter than the harness's 756-session training minimum, and a fixed rule has nothing to fit, so the whole window is out of sample and is scored once. |
| Scoring | `research_short_horizon.evaluation.score_decisions`, the repaired staggered-tranche ledger (`056fb1c6`), with `held_sessions = 3` and `periods_per_year = 84`. DSR is `OverfittingDiagnostics.deflated_sharpe_ratio(sharpe, num_trials=10, sample_length_bars=max(portfolio_periods, 3), periods_per_year=84)`. |
| Gate | `GatePolicyV1` defaults, not adjusted: DSR >= 0.95, max drawdown <= 0.15, trades >= 5. |
| Controls | **`NOISE-K`:** 30 seeds, 0-29, of `run_short_horizon_experiment._noise_predictions` on the identical decisions, through the identical rule. **`ALWAYS_TRADE`, `PREVIOUS_SIGN` and `CASH`** are scored on the identical decisions. |
| **Verdict** | **PASS only if all three hold:** (1) the gate passes; (2) the candidate's Sharpe beats the best of the 30 `NOISE-K` seeds; (3) the candidate's Sharpe beats `ALWAYS_TRADE`. Otherwise `RESEARCH_ONLY`. A pass reads `PASS_PENDING_INDEPENDENT_CHECK` and promotes nothing: an agent that did not write this code must re-run it, and a forward paper period must follow. No live-money path exists (T4 is excluded). |
| Diagnostics | Declared now and **never verdict-bearing**: (a) `CANDIDATE_ANY_POSITIVE`, long when `predicted_return > 0`. (b) Daily cross-sectional Spearman rank IC between prediction and realised net return, with mean and t over every third decision date, which do not overlap. (c) Top-quintile selection edge: the top 20% by prediction minus the equal-weight mean, on the same dates. (d) The count of decisions with no forecast; a missing forecast is cash. |
| Separation | No result may move Flagship or XS-Monthly, and neither book is touched. |

## Compute scope rule, declared before the timing probe

1. On synthetic bars only, measure seconds per forecast, batched as above, for each configuration.
2. Take the first configuration in this order whose projected total runtime is **14 hours or
   less**, one night:
   - (base, S = 5)
   - (base, S = 1)
   - (small, S = 5)
   - (small, S = 1)
3. If none fits, run (small, S = 1) across as many off-hours windows as it needs. **Never cut the
   names, dates or context to make it fit.**
4. The run pauses on weekdays from 08:45 to 16:30 IST, and whenever the laptop is on battery, so
   the paper books keep their machine. It checkpoints after every decision date and resumes
   without re-drawing.
5. The probe's numbers and the chosen configuration are appended below as Amendment 1, before any
   real forecast is generated.

## Contamination and disclosed biases

- **Every scored target is dated after the stated pre-training cutoff.** Contexts include earlier
  history; those bars are inputs, not answers.
- **The cutoff is the authors' statement.** If the corpus in fact runs later, a positive result
  would be contaminated. It is recorded here, before the result, as a reason a pass is only
  provisional.
- **Survivorship and liquidity selection** in the 45-name subset favour the candidate. Both are
  inherited from trials 1-9.
- **The window overlaps the reserved holdout.** It includes the final 252 sessions the
  short-horizon program set aside. Those sessions stop being unseen by anyone reading this result.
- **Demergers.** Decisions near an unsized corporate action have no label, so they are not scored,
  exactly as in trials 1-9. Such a gap can still sit inside an earlier context window, as it could
  for TimesFM.

## Ledger

| # | Family | Hold | Status | Result | Recorded |
|---|---|---:|---|---|---|
| 10 | Kronos zero-shot (MIT) | 3 | **DECLARED** | not yet run | 2026-09-29 |
| NOISE-K | Control, 30 seeds, consumes no trial | 3 | **DECLARED** | not yet run | 2026-09-29 |
