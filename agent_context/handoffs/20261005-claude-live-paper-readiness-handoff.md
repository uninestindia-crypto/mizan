# Handoff: live-market paper trading readiness (audit done, open items for the founder)

STATUS: READY_FOR_ADOPTION  
FROM: Claude Code (cloud container)  
TO: unassigned  
DATE_UTC: 2026-10-05  
ACTIVE_RECORD: `agent_context/work/active/20261005-claude-live-paper-readiness-audit.md`

## Objective and acceptance criteria

Decide independently whether the platform is ready for live-market paper trading with two delivery
modes (A: owner copies orders by hand; B: owner grants direct broker access), and bring the UI to a
consumer-grade standard. Acceptance: an evidence-backed verdict, bounded repairs with tests, and
every open item named with an owner.

## Completed

PR: https://github.com/uninestindia-crypto/mizan/pull/1

- Verdict and 14 numbered open findings: `reports/live_paper_readiness_20261005/REPORT.md`, with a
  follow-up table of what the second pass closed.
- Mode A, end to end: stale-order guard, creation refusal, order ticket, "Orders to place" inbox and
  sidebar count, a note per order (placed or skipped), tracking against the paper fills.
- Live dashboard repaired inside the app; health and readiness probes; log clock; holiday-list
  expiry warnings; Shariah labels; phone layout, contrast and touch targets; Linux-green test suite.
- Eight end-to-end tests drive the real paper runner; all 13 Red Team Round 7 survivors are killed.

## In progress

Nothing partial. Mode B (direct broker access) is deliberately **not** started: it is T4 work and
needs its own charter.

## Files and ownership

Committed on `claude/dazzling-brown-yn5qu3`; pull request 1 is open. Source, test and frontend
files are listed in the active record under "Owned paths". The frontend build output under
`src/quant_system/server/static/app/` is gitignored and was rebuilt locally only.

## Verification

See the active record, "Commands and outcomes".

## Known failures and risks

- Nothing was run against a live broker feed; no token was available. Findings O3 and O4 remain.
- The earlier live-dashboard fix (`b79351813` on `claude/amazing-lamport-e18bd1`) is not on the remote.
  This branch re-implements it; expect conflicts if that branch is ever merged, and prefer this one.
- The orders reminder is an opt-in webhook (`QUANTOS_ORDERS_WEBHOOK_URL`); it was verified against a local server only. Email is not built. Mode B is not built (T4, needs its own charter).
- The 2027 NSE holiday list is not fetched (NSE is unreachable from the container). Both the app and
  the scheduled runner warn from 90 days out; today it is 87.
- A release is due (`release_status.py`) and cannot be cut from Linux.

## Exact stop point

Report, tests and repairs written; gates run; changes committed and pushed to the designated branch.

## Next safe action

1. Review and merge PR 1 when CI is green.
2. On the Windows install root: pull the merged branch, then decide whether to cut the release with
   `scripts/release.ps1 -DryRun` first. (The claims and disk-layout audits already pass in CI.)
3. Run one governed live paper session with `UPSTOX_ANALYTICS_TOKEN`, then commission an
   independent adjudication of the live paper path (`.launch/RED-TEAM-BRIEF-20260901-ROUND7.md` was
   author-run and says so).

## Do not do

- Do not treat the order ticket as a reason to trade real money: every published model is
  `RESEARCH_ONLY`.
- Do not start Mode B without a separate T4 authorisation.
- Do not change what either running paper book trades before 2026-10-28
  (`20260924-NOTICE-paper-books-system-test-running.md`).
- Do not edit `frontend/` or `server/v2/` on the strength of the stale
  `20260928-claude-retail-redesign-build.md` claim without checking `git log -- frontend`: that
  branch is already on `main`.
