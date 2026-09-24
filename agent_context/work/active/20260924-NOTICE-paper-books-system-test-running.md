# NOTICE: both paper books are running as a system test until 2026-10-28

STATUS: NOTICE, standing until the test ends; then it moves to `work/completed/`. Additive: no
other record, `CURRENT.md`, or `.launch/STATE.md` is edited.  
FILED_BY: Claude Code (Opus 5.5), 2026-09-24, recording a founder decision  
DECISION: `agent_context/decisions/20260923-paper-books-system-test-end-date.md`, section
"Restarted, 2026-09-24"  
SUPERSEDES: `work/completed/20260923-NOTICE-paper-books-stopped-for-fixes.md`

## What is running

- The Mizan flagship and XS-Monthly books restarted fresh at Rs 10L each.
- The flagship's first session is Fri 2026-09-25. XS's first cohort enters at the 2026-09-24 open.
- They run the same frozen models as before, now with fixes F1-F5: the like-for-like report, re-weighting,
  scheduling, and the corporate-action guard with its review tool.
- **Ends Wed 2026-10-28; hard stop Mon 2026-11-09.**

## What every agent must do

1. **Do not change what either book trades** until the end: no model swap, retrained weights, rule,
   universe or sizing change, or manual trade. Fixes to the system are allowed and are the point.
2. **Do not cite either book's P&L as model performance.** It is market plus costs; the models
   carry no demonstrated edge.
3. **If a flagship session exits 11, or an XS leg is unvalued for `CORPORATE_ACTION_NOT_REVIEWED`**,
   review the action against the company's filing and record it with
   `scripts/apply_paper_corporate_action.py`: first without `--apply`, then with it. Never
   hand-edit either book's state.
4. **Do not disable, re-enable or reconfigure** the three paper-book tasks without the founder.
5. **Do not start another paper book** without the rule of decision point 7: a written purpose,
   the decision its result could change, a benchmark, and an end date.

## Claimed paths

None. This notice claims nothing; it informs.
