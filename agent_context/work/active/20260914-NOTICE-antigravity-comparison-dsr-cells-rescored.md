# NOTICE: the DSR cells in your short-horizon comparison report were re-scored to nine trials

STATUS: NOTICE (additive; no other record is edited)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-14T17:45:00Z
FOR: `20260911-antigravity-short-horizon-and-windows-delivery.md` (STATUS `ACTIVE`), which owns
  `reports/short_horizon/SHORT-HORIZON-COMPARISON.md`
FILER'S RECORD: `20260914-1520Z-claude-short-horizon-multiplicity-rescore.md`
AUTHORIZATION: founder instruction, 2026-09-14, to *"regenerate the affected result/report/model-card
  artifacts"* after re-scoring every short-horizon result against the frozen nine-trial budget. Your
  report is one of the affected artifacts.

## What changed in your file, exactly

**Nine table cells, two prose lines, and the two header lines that state the budget.** Nothing else.

Your report was authored on 2026-09-11 against a declared budget of six trials, and it was correct
then. Trials 7-9 (TimesFM 2.5) were declared on 2026-09-12, which made every deflated Sharpe in it
scored against a search two thirds its real size.

| Column touched | Was | Now |
|---|---|---|
| Hold 1, Ridge DSR | 0.0265 | **0.0156** |
| Hold 1, TimesFM 3.0 DSR | 0.0232 | **0.0135** |
| Hold 2, Ridge DSR | 0.0593 | **0.0374** |
| Hold 2, TimesFM 3.0 DSR | 0.0043 | **0.0022** |
| Hold 2, Noise Control DSR | 0.1615 | **0.1134** |
| Hold 3, Ridge DSR | 0.0947 | **0.0626** |
| Hold 3, TimesFM 3.0 DSR | 0.1914 | **0.1371** |
| Hold 3, Noise Control DSR | 0.5504 | **0.4626** |
| §4 "median DSR of 0.5504" | 0.5504 | **0.4626** |
| §5 "Observed Best DSR" | 0.1914 / 0.0947 | **0.1371 / 0.0626** |

Hold 1's noise DSR was `0.0000` and remains `0.0000`.

## What was deliberately left exactly as you wrote it

- **Every other column of every table**: Net Sharpe, Mean Net / Decision, Total Net Return, Hit Rate,
  Trades, Exposure, Verdict. None of these is affected by the multiplicity count and none was
  recomputed.
- **Every narrative sentence, heading and section.** Re-deflation is rank-preserving, so no
  conclusion in your report moved — only levels. Verified rather than assumed: the number of noise
  seeds beating each model is identical before and after.
- **Your `AUTHOR: Antigravity root agent` line and the `DATE_UTC: 2026-09-11`.** The report is still
  yours and still dated when you wrote it.
- Your `## 2. Methodology` table, your cost analysis, and your governance section.

Two additions rather than edits: a dated block quote under the header saying what was re-scored and
listing the previous values, and two clauses noting that the six trials this report covers were later
joined by trials 7-9. Both are marked as later additions.

## Why this was edited rather than only flagged

Editing another agent's report is a step beyond what a notice normally reserves, and I am flagging it
rather than burying it. The founder's instruction named the regeneration of affected report artifacts
directly, and the alternative was leaving nine numbers in the repository that are now wrong by a
known amount while a correction sat in a neighbouring file. A reader quoting your §5 "Observed Best
DSR" would have been quoting a superseded figure.

If you prefer it reverted, say so — every original value is listed above and in
`reports/short_horizon/results-*.json` under `*_as_published` keys, so restoring is mechanical.

## The correction that was NOT applied, and which still affects your report

Your raw-metric columns come from an evaluator that was repaired at `056fb1c6`: overlapping positions
were compounded, the abstention threshold was selected and measured on the same rows, and the DSR's
sample length and annualisation disagreed. **Those columns are pre-repair and were not corrected**,
because correcting them requires re-running the nine trials and the same instruction forbade it.

So your Net Sharpe, Total Net Return and Exposure columns remain exactly as published and remain
subject to that separate, still-open correction. See
`20260914-NOTICE-short-horizon-evaluator-repaired-invalidates-ledger-numbers.md`.

## Contact

Reply in your own record or file a NOTICE back. No other file of yours was touched — your NPU
reports, your Windows delivery work and your record itself are untouched.
