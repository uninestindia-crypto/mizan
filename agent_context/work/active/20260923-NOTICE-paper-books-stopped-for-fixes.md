# NOTICE: both paper books are stopped for fixes, and restart fresh later as a system test

STATUS: NOTICE, standing until the restart; then it moves to `work/completed/`. Additive: no other
record, `CURRENT.md`, or `.launch/STATE.md` is edited.  
FILED_BY: Claude Code (Opus 5.5), 2026-09-23, recording a founder decision  
OBSERVED_AT: `main` = `525b3997`  
DECISION: `agent_context/decisions/20260923-paper-books-system-test-end-date.md`  
WORK: `agent_context/work/active/20260923-claude-paper-books-stop-fix-restart.md`

## Addressed to

- `20260826-antigravity-paper-trade-live-market-testing.md`: flagship runner, `logs/paper_runs/`,
  live dashboard.
- `20260903-hermes-xs-monthly-screen-new.md`: XS-Monthly watch and `logs/xs_monthly_new/`.
- `20260914-claude-paper-book-accounting-repairs.md` and `20260915-0900Z-claude-paper-report-baselines.md`:
  book accounting and the session report's baseline lines.
- `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md`: owns the weights the
  flagship loads (`src/quant_system/modeling/mizan_model.py`).
- `20260909-claude-lid-fix-and-xs-supervision.md` and `20260918-CLAIM-paper-session-keep-awake-branch.md`:
  the scheduling of both books.
- `20260820-codex-slice4-ridge-training.md` and `20260821-claude-ci-workflow.md`: the claimants of
  `CURRENT.md`, for the next reconciliation.

## What the founder decided, 2026-09-23

1. **Both books are stopped.** `QuantOS Mizan Paper Session`, `QuantOS Trigger Verification` and
   `QuantOS-XSMonthly-PaperWatch` are disabled. **Do not re-enable them or run a session by hand**
   until the restart checklist in the decision is met and the founder says go.
2. **Nothing is deleted.** Copies of every record are in `logs/archive/paper-books-20260923/`,
   fingerprinted in `reports/paper_books_20260923/archive-manifest.json`. The live files are the
   frozen final state; do not write to them.
3. **Their P&L is not evidence about the model**, for or against. Do not cite it as model
   performance.
4. **Fixes first (F1-F5 in the decision), then a fresh restart at Rs 10L each** with the same
   models, labelled a system test, with an end date.

## Your claimed paths will be edited

The fixes touch files your records claim. They are edited on founder instruction, the precedent
being `20260829-claude-live-mizan-feature-provider.md`. The work record lists each path before its
first edit, with the commit that changes it. Nothing you wrote is reverted. If you are mid-change
in any of those files, say so in your record and the work will stop on that path.

## Claimed paths

None. This notice claims nothing; it informs.

## Update 2026-09-24: founder chose the review tool, and the XS guard

The founder answered the open F5 items: build a review tool, and give XS the same protection.

- **Hermes Agent (`20260903-hermes-xs-monthly-screen-new.md`), your paths changed.**
  - `research_xs_monthly/paper.py` gains `unreviewed_corporate_actions`.
  - `settle_positions` now carries a leg's `corporate_actions` reviews through the open, closed
    and unresolved states.
  - `scripts/run_xs_monthly_paper_watch.py` gains `--corporate-actions-dir`. It leaves a leg
    unvalued when it was held across a split, bonus, consolidation, demerger or rights issue in the
    stored NSE records and no one has reviewed it. Your hand-kept authority still takes precedence
    where both name a leg.
- **Flagship state is schema v7.** `reviewed_actions` records each review in the same
  hash-protected write as the adjustment; v3-v6 files migrate.
- **The shared finder moved** to `src/quant_system/data/held_corporate_actions.py`, so the XS
  package imports nothing from the execution layer.
- **The tool is `scripts/apply_paper_corporate_action.py`.** It is a dry run without `--apply`,
  refuses a ratio that contradicts NSE's record, and records each action once.
