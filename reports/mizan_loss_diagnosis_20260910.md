# Mizan paper-book loss diagnosis — 10 September 2026

Read-only review at code revision `35ef1f1552e0c66d4050466f1023f35023733f33`. No models, trading rules, portfolios, dependencies or scheduled tasks changed. These are research observations, not promotion evidence.

The two losses have different explanations. Flagship has marked price losses plus previously paid fees, using a frozen model whose historical evidence remains weak. XS-Monthly has a material corporate-action omission: its largest apparent loser, HEG, underwent a demerger and the book omits the resulting share entitlement. Both paper workflows evaluate fixed strategies; neither automatically learns from virtual P&L.

## Measured snapshots

Each book began with INR 1,000,000. Marks are not synchronized, so the difference between them is not an investment-performance comparison.

| Book | Saved valuation | Equity INR | P&L INR | Return on initial capital |
|---|---|---:|---:|---:|
| Flagship | September 10 session report; live-status mark timestamp 14:50:08 IST | 987,230.40 | -12,769.60 | -1.276960% |
| XS-Monthly | September 9 daily open, processed September 10 04:09:04 UTC | 998,071.67 | -1,928.33 gross | -0.192833% gross |

Flagship's report records completion at 17:16:00 IST, while its status carries 14:50:08 IST. This review does not certify quote freshness or treat that report timestamp as the price timestamp. The September 9 Flagship report was equity 989,852.96 and P&L -10,147.04; preliminary commentary used that earlier snapshot.

Sources: [Flagship session report](D:/quant_system/logs/paper_runs/paper_session_2026-09-10_paper_ses_20260910_091443_IST.json), [Flagship portfolio](D:/quant_system/logs/paper_runs/portfolio_state.json), [XS state](D:/quant_system/logs/xs_monthly_new/paper_watch/state.json).

## Flagship: what explains the number

Independent Decimal arithmetic from the saved holdings and report marks:

```text
97 positions, all opened 2026-08-31
Purchase consideration       853,407.04
Cash                        145,520.31
Historical fees               1,072.65
Sum                       1,000,000.00

Current market value        841,710.09
Cash                        145,520.31
Equity                      987,230.40

Marked price P&L            -11,696.95
Historical fees              -1,072.65
Total P&L                   -12,769.60
```

Realized P&L is zero. The current report has no new fills or session fees. Its fee display of zero is a session measure; lifetime fees are present in `portfolio_state.json` and already reduce cash. About 92% of this snapshot's reported loss comes from price movement relative to recorded acquisition cost. Acquisition cost may already embed execution slippage; this is not a pure forecast-alpha decomposition. Exit costs remain prospective.

Largest marked detractors: PFIZER -1,208.82; KEI -866.30; HFCL -763.31; NSLNISP -612.06; GRAVITA -597.30. Largest offsets: FINCABLES +1,067.99; INOXWIND +826.20; RBLBANK +702.24. HEG is absent from this book. These contributions reconcile to the reported unrealized total across all 97 positions, but individual corporate actions beyond HEG were not independently cleared in this review.

The live loader uses the 15-feature default Mizan weights, with historical label horizon 11, converted by the portfolio policy to 10 held sessions. It resumes holdings and calls `predict_scores` when rebalancing; it does not fit or update weights from paper losses. On holding days it does not re-rank. See [loader](D:/quant_system/scripts/run_paper_pilot_session.py:970), [holding policy](D:/quant_system/scripts/run_paper_pilot_session.py:1003), [scoring](D:/quant_system/scripts/run_paper_pilot_session.py:1085), and [default weights and card](D:/quant_system/src/quant_system/modeling/mizan_model.py:548).

The default model's own historical evidence is `RESEARCH_ONLY`, Sharpe about -0.4108 and deflated Sharpe about 0.176 against the documented 0.95 gate. DSR is a statistical evidence measure, not trade win probability. These historical figures describe the evaluated artifact and cannot be relabeled as the return of today's top-quintile portfolio.

A concrete validation mismatch also exists: the live runner says its top-20% selection reproduces `screen_mizan_out_of_sample.py`, but that screen fits an eight-feature model with within-date ranks and raw-return targets, whereas the live runner loads the older 15-feature weights. Matching holding period and selection fraction does not make these the same model. See [live claim](D:/quant_system/scripts/run_paper_pilot_session.py:1094), [screen features](D:/quant_system/scripts/screen_mizan_out_of_sample.py:54), and [screen fit](D:/quant_system/scripts/screen_mizan_out_of_sample.py:185).

The short paper history cannot establish persistent negative alpha. A same-date, same-exposure total-return benchmark is needed to separate market movement from selection skill. It is nevertheless incorrect to expect this frozen model to improve automatically merely because it is being run with virtual money.

## XS-Monthly: corporate-action accounting dominates the displayed loss

The state contains 99 selected legs, 91 with positive share quantities, eight with zero shares, and no closed legs. Cash is 137,184.02 and invested entry value is 862,815.98. It is a fixed trailing-momentum ranking rule with a 21-session hold, not a trained neural model. See [rule and sizing](D:/quant_system/src/quant_system/research_xs_monthly/paper.py:1).

HEG alone contributes:

```text
13 shares x INR 725 entry       = INR 9,425
13 shares x INR 257 latest open = INR 3,341
Displayed HEG price P&L         = INR -6,084
Other 98 selected legs combined = INR +4,155.67
Total gross P&L                 = INR -1,928.33
```

HEG's August 24 company filing sets September 7, 2026 as the record date and specifies one HEG Graphite share for each eligible HEG share. The paper holding predates that date. Its economic simulation should therefore track an entitlement corresponding to 13 resulting-company shares. The saved state has no such position or receivable; the marking function simply multiplies the remaining HEG quote by the unchanged quantity. [Company filing reproduced with full document text](https://bazaarwatch.com/announcement/88270/heg-ltd-attached), [marking function](D:/quant_system/src/quant_system/research_xs_monthly/paper.py:97).

This is a material omission, not proof of a 65% economic loss on HEG. The issuer's own website returned HTTP 403 during direct retrieval; the diagnosis uses the reproduced company filing, corroborated by the issuer's indexed disclosure listing. It does not rely on the host's AI summary.

Do not erase HEG, reverse all INR 6,084 of loss, or invent a market price for the new entitlement. Corrected total wealth needs both securities or a disclosed, evidenced valuation of the entitlement. Removing HEG from the attribution gives +4,155.67 only as a diagnostic, not as corrected portfolio P&L.

The current XS display is also gross of its own cost convention. Its fixed 0.224% round-trip assumption on entry notional equals INR 1,932.7077952. Reserving that amount would move the uncorrected result to about -3,861.04 before any additional broker-specific charges or spread. This is an illustrative accrual of the existing simulator assumption, not an authoritative executable liquidation quote. The code charges it at closing, not on open marks. [Cost handling](D:/quant_system/src/quant_system/research_xs_monthly/paper.py:74).

Historical XS screens do not establish a strong selection edge: the 423-name screen's average 21-session return exceeds its equal-weight comparator by only about 5.27 basis points, and the 499-name screen by about 9.98 basis points. Their rank-IC t-statistics are -0.85 and -0.38, respectively: neither establishes useful predictive ranking. These are overlapping research histories with active-listing universe bias, not independent proof of profitability. See [423-name screen](D:/quant_system/logs/xs_monthly_new/20260903-104002Z/xs_monthly_screen.md) and [499-name screen](D:/quant_system/logs/xs_monthly_new/20260903-104119Z/xs_monthly_screen.md).

## TimesFM recommendation

TimesFM is worth considering as a separately measured forecast challenger after the accounting and validation problems are addressed. A larger model does not fix an omitted corporate-action asset, cost conventions, or a mismatch between evaluated and executed weights.

Google's TimesFM 3 announcement describes 330 million parameters, native multivariate forecasting, covariates, and point/quantile forecasts. Its reported benchmarks measure forecasting quality; they do not establish NSE trading profit after costs. [Google announcement](https://www.research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/).

The default 3.0 license is non-commercial and non-production. It restricts commercial decision-making and production use, and also training other models for commercial use. Virtual capital alone does not establish permission. Qualifying isolated research may be allowed; commercial integration requires appropriate rights from Google. Version 2.5 remains Apache-2.0 according to the official repository, making it the clearer licensing candidate to investigate for a commercial product. [3.0 license](https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE), [official repository](https://github.com/google-research/timesfm).

Start with frozen zero-shot forecasts and predeclare one trading use and horizon. Compare against cash, last-price/zero-return forecasts, simple momentum, the same-universe benchmark and the exact running Mizan model. Use chronological walk-forward evaluation, train-only transformations, purging for overlapping labels, identical next-eligible execution and costs, adverse-cost/delay tests, and a preserved final holdout. Measure incremental net return, drawdown, turnover and stability, not price RMSE alone. Count model, feature, threshold and horizon searches.

The model card does not establish one exhaustive pretraining cutoff for all data; retrospective tests cannot be assumed uncontaminated. Only genuinely known future inputs may be used as future covariates. The official fine-tuning example examined is for 2.5; 3.0 fine-tuning support and this Windows ARM machine's performance have not been validated here. No model was downloaded or installed. [Model card](https://huggingface.co/google/timesfm-3.0-pytorch), [fine-tuning example](https://github.com/google-research/timesfm/tree/master/timesfm-forecasting/examples/finetuning).

## Next engineering priorities

1. Record and value the HEG entitlement with instrument identity, dated corporate-action authority, event provenance and an explicit unpriced state when necessary. Reconcile the correction without overwriting the original evidence.
2. Give both books synchronized valuation dates and consistent gross, paid-cost, accrued-exit-cost and net fields; distinguish selected zero-share legs from funded positions.
3. Bind the executed model, features, preprocessing, selection rule and holding policy to the exact validation artifact. Preserve current weights while evaluating a separately specified challenger.
4. Add an identical-timing benchmark and determine whether loss is market exposure or selection underperformance before changing the strategy.
5. Evaluate TimesFM only after those measurement foundations and its licensing route are settled.

This review completes the diagnosis; it does not implement those changes or certify either model. Existing active claims on source/runtime paths were respected. Prior AI opinion reports were treated as hypotheses, not independent financial evidence.

## Reproducibility and checks

Read-only Python probes used Decimal from persisted strings, reconstructed Flagship position P&L from report marks, and summed XS position values and pending costs. No training campaign, holdout or paper session was rerun. Both `scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1` passed. No source change warranted a new test suite run.

SHA-256 identities at the final read (runtime files may subsequently change):

| File | SHA-256 |
|---|---|
| September 10 Flagship session JSON | `2f5878b3d60a85bcb08de2125a88823f7d95884ffdd83df72aa80b3d30268643` |
| Flagship portfolio state | `aeb1be9ce80b2e807ee0c2d0111d1c12c64d67ad2e18b82a07896008b45ba496` |
| XS state | `af25735eeffe297a403d2d61c4bc089c815760cdf618bf93e2e4c0c950e7a367` |
| mizan_model.py | `1ef542449b50743d7305b193cea4e462b7241a5cfe9129dc1b3973a3ac2a430c` |
| run_paper_pilot_session.py | `cff199a7bc635cf9217a0e149fa2ea27e314ee6538423c092550ae45cde0ec94` |
| research_xs_monthly/paper.py | `13eacf9c6b008037cce6fcfe8782dd8a2ea49a5471907e4ce0f26156e37b0e72` |

