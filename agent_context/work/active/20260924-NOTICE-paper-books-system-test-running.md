# NOTICE: both paper books are running as a system test until 2026-10-28

STATUS: NOTICE, standing until the test ends; then it moves to `work/completed/`. Additive: no
other record, `CURRENT.md`, or `.launch/STATE.md` is edited.  
FILED_BY: Claude Code (Opus 5.5), 2026-09-24, recording a founder decision  
DECISION: `agent_context/decisions/20260923-paper-books-system-test-end-date.md`, section
"Restarted, 2026-09-24"  
SUPERSEDES: `work/completed/20260923-NOTICE-paper-books-stopped-for-fixes.md`  
UPDATED: 2026-09-28, the start slipped (below)

## What is running

- The Mizan flagship and XS-Monthly books restarted fresh at Rs 10L each.
- The start slipped:
  - The flagship's first session, due Fri 2026-09-25, was missed. The laptop had hibernated on a
    flat battery. The flagship is due to start Mon 2026-09-28.
  - XS's first cohort entered at the 2026-09-23 open, one session early. Its 09-25 run read a cache
    that ended 09-23, because the flagship's missed run does the refresh.
  - It slipped again on 2026-09-29. The start-up check that took hours was fixed (`45f95604`),
    but the laptop was put to sleep at 10:34 and the session was lost. **As of 15:30 on
    2026-09-29 the flagship has still not run a session.** Its real start is the
    `inception_on` in `portfolio_state.json`, once that file exists.
  - Detail: the decision record, sections "Start slipped, recorded 2026-09-28" and
    "Start slipped again, recorded 2026-09-29".
- They run the same frozen models as before, now with fixes F1-F5: the like-for-like report, re-weighting,
  scheduling, and the corporate-action guard with its review tool.
- **The end date now follows the flagship's real start:** its second rebalance, session 21, and
  XS's exit at the 2026-10-26 open. Hard stop Mon 2026-11-09 is unchanged.
- A one-time reminder in the founder's Claude desktop app (`end-paper-book-test`) fires on
  2026-10-29 at 18:07 IST. It works out the real dates from `inception_on`, checks read-only and
  asks the founder for the go-ahead.

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
