# Active work: stop the paper books, fix what they exposed, prepare a fresh restart

STATUS: ACTIVE  
OWNER: Claude Code session, on founder instruction  
TOOL: Claude Code  
STARTED_UTC: 2026-09-23T11:05:00Z  
STARTING_REVISION: 525b39978ead92f29aacd43a9da3c28ea3a02216  
WORKTREE_OR_BRANCH: `D:\quant_system`, `main` (shared checkout; no other agent active in the last
6 hours; explicit paths staged only)  
FOLLOWS: `agent_context/work/completed/20260923-claude-paper-books-end-date.md`

## Objective

Founder instruction, 2026-09-23, after reviewing why the Rs 20L paper books lose money:
"yes go ahead, stop them and start fixing". This amends the decision recorded an hour earlier
(end on 6 Oct) to: stop both books now, keep their records, fix what they exposed, then restart
fresh at Rs 10L each as a labelled system test.

## Owned paths

Records:

- `agent_context/work/active/20260923-claude-paper-books-stop-fix-restart.md` (this record)
- `agent_context/decisions/20260923-paper-books-system-test-end-date.md` (my uncommitted file,
  rewritten for the amended decision)
- `agent_context/work/active/20260923-NOTICE-paper-books-end-6-oct.md`, renamed to
  `20260923-NOTICE-paper-books-stopped-for-fixes.md` (my uncommitted file)
- `agent_context/decisions/20260901-two-open-paper-pilot-decisions.md`: `STATUS` line only
- `agent_context/work/completed/20260923-claude-paper-books-end-date.md`: a forward pointer only
- `reports/paper_books_20260923/` (adds the archive manifest)
- `logs/archive/paper-books-20260923/` (new, gitignored copies of both books' records)

Code paths are added here, each before its first edit. Every one is claimed by an older active
record, so each edit is made on founder instruction and announced in the NOTICE.

## Non-goals

- No new model, retrain, or change to model weights or the XS rule.
- No restart of either book. That needs the fixes verified and the founder's go-ahead.
- No deletion of any book record. Copies are archived; the live files stay as frozen.
- No change to `CURRENT.md` or `.launch/`.

## Plan

1. Stop both books: disable the three Windows tasks. DONE, see below.
2. Archive copies of both books' records with a SHA-256 manifest.
3. Rewrite the decision and NOTICE for the amended plan; point the 1 Sep decision at it; commit
   the records (founder asked for the commit).
4. Fixes, in order:
   - F1: session report baselines compare like with like.
   - F2: rebalance resets held names to target weight (the measured strategy).
   - F3: XS exit path checked by replaying past data through the runner on a scratch copy.
   - F4: scheduling: XS refused on battery; a session running past midnight blocks the next day.
   - F5: demerger entitlements with no price (HEG Graphite).
5. Restart checklist for the founder.

## Current step

2. Archiving.

## Decision rationale

Waiting until 6 Oct only bought one live run of XS's exit path, which can be exercised now by
replaying past data. Restarting after fixes gives clean books; it does not make them profitable,
because the same models still carry no edge (101 governed trials; flagship DSR 0.175990 against
0.95). So the restart is labelled a system test with an end date, per the 23 Sep decision's rule
for any paper book.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `Get-CimInstance Win32_Process` filtered on the paper runners | none running | Checked before disabling |
| `Disable-ScheduledTask` for `QuantOS Mizan Paper Session`, `QuantOS Trigger Verification`, `QuantOS-XSMonthly-PaperWatch` | PASS | All three `Disabled`; the three supervisors were already `Disabled`; only `QuantOS-DailyAutoSync` (git, 23:00) remains `Ready` |

## Files changed

- To be listed at completion.

## Blockers and conflicts

- Every code path in F1-F5 is claimed by an older active record (Antigravity paper pilot, Hermes
  XS watch, and five Claude records). Edited on founder instruction with a NOTICE, per repository
  precedent (`20260829-claude-live-mizan-feature-provider.md`, founder override).
- `QuantOS-DailyAutoSync` pushes `main` at 23:00, so commits made here reach `origin` tonight.

## Stop point

Books stopped. Nothing else changed yet in this task.

## Next safe action

Archive copies of `logs/paper_runs/` and `logs/xs_monthly_new/paper_watch/` with a manifest.
